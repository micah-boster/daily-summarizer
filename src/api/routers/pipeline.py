"""Pipeline run API endpoints: trigger, list, detail, and SSE streaming."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse

from src.api.models.pipeline import (
    RunListResponse,
    RunResponse,
    RunStage,
    TriggerRequest,
    TriggerResponse,
)
from src.api.services.pipeline_runner import (
    cleanup_orphaned_runs,
    complete_run,
    create_run,
    fail_run,
    get_run,
    list_runs,
    start_pipeline_subprocess,
    stream_pipeline_events,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["pipeline"])

# Module-level dict tracking active subprocess handles by run_id.
# Used by the SSE stream endpoint to tap into a running process.
_active_processes: dict[str, asyncio.subprocess.Process] = {}
_active_tasks: dict[str, asyncio.Task] = {}


def _row_to_response(row: dict) -> RunResponse:
    """Convert a DB row dict to a RunResponse model."""
    stages = [
        RunStage(
            name=s.get("name", ""),
            status=s.get("status", "pending"),
            elapsed_s=s.get("elapsed_s"),
        )
        for s in row.get("stages", [])
    ]
    return RunResponse(
        id=row["id"],
        target_date=row["target_date"],
        status=row["status"],
        stages=stages,
        started_at=row["started_at"],
        completed_at=row.get("completed_at"),
        duration_s=row.get("duration_s"),
        error_message=row.get("error_message"),
        error_stage=row.get("error_stage"),
    )


async def _run_pipeline_background(run_id: str, target_date: str) -> None:
    """Background task: start subprocess, consume events, update DB."""
    try:
        proc = await start_pipeline_subprocess(run_id, target_date)
        _active_processes[run_id] = proc

        # Consume all events (updates DB via stream_pipeline_events)
        async for _event in stream_pipeline_events(run_id, proc):
            pass  # Events are persisted inside stream_pipeline_events

    except Exception as e:
        logger.error("Background pipeline run %s failed: %s", run_id, e)
        fail_run(run_id, str(e))
    finally:
        _active_processes.pop(run_id, None)
        _active_tasks.pop(run_id, None)


@router.post("/runs", status_code=202, response_model=TriggerResponse)
async def trigger_run(body: TriggerRequest | None = None):
    """Trigger a new pipeline run.

    Returns 202 Accepted with run_id. Returns 409 if a run is already in progress.
    The pipeline subprocess is launched as a fire-and-forget background task.
    """
    if body is None:
        body = TriggerRequest()
    target_date = body.get_target_date()

    try:
        run_id = create_run(target_date)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    # Launch background task for the pipeline subprocess.
    # create_task schedules it on the event loop without blocking the response.
    task = asyncio.get_running_loop().create_task(
        _run_pipeline_background(run_id, target_date)
    )
    _active_tasks[run_id] = task

    return TriggerResponse(run_id=run_id, status="running")


@router.get("/runs", response_model=RunListResponse)
def get_runs(limit: int = 14):
    """List recent pipeline runs."""
    runs = list_runs(limit=limit)
    return RunListResponse(
        runs=[_row_to_response(r) for r in runs],
        total=len(runs),
    )


@router.get("/runs/{run_id}", response_model=RunResponse)
def get_run_detail(run_id: str):
    """Get details for a single pipeline run."""
    row = get_run(run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return _row_to_response(row)


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: str):
    """SSE stream for pipeline run progress.

    First event is the current state snapshot (for reconnection).
    Then streams live events if the process is still active.
    """
    row = get_run(run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Run not found")

    async def event_generator() -> AsyncIterator[str]:
        # First event: current state snapshot (supports SSE reconnection)
        snapshot = _row_to_response(row).model_dump()
        yield f"data: {json.dumps(snapshot)}\n\n"

        # If run is already complete/failed, we're done
        if row["status"] in ("complete", "failed"):
            return

        # If we have an active process, stream from it
        proc = _active_processes.get(run_id)
        if proc is None or proc.stdout is None:
            # Process not tracked (maybe started before this server instance)
            # Poll DB for updates instead
            last_status = row["status"]
            while True:
                await asyncio.sleep(1)
                current = get_run(run_id)
                if current is None:
                    return
                if current["status"] != last_status or current.get("stages_json") != row.get("stages_json"):
                    event = _row_to_response(current).model_dump()
                    yield f"data: {json.dumps(event)}\n\n"
                    last_status = current["status"]
                if current["status"] in ("complete", "failed"):
                    return
        else:
            # Stream directly from subprocess stdout
            try:
                async for raw_line in proc.stdout:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        yield f"data: {json.dumps(event)}\n\n"
                    except json.JSONDecodeError:
                        continue
            except Exception:
                pass

            # Send final state
            final = get_run(run_id)
            if final:
                final_event = _row_to_response(final).model_dump()
                yield f"data: {json.dumps(final_event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
