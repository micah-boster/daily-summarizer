"""Pipeline run management: subprocess isolation, run persistence, SSE event streaming.

Uses sqlite3 directly (no ORM) following project convention. Each function
opens its own connection (connection-per-call pattern) for thread safety.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

from src.config import load_config

logger = logging.getLogger(__name__)


def get_db_path() -> str:
    """Load config and return the entity db_path."""
    config = load_config()
    return config.entity.db_path


def _get_conn(db_path: str | None = None) -> sqlite3.Connection:
    """Open a connection to the entity DB with migrations applied."""
    from src.entity.db import get_connection

    path = db_path or get_db_path()
    return get_connection(path)


def create_run(target_date: str, db_path: str | None = None) -> str:
    """Create a new pipeline run record.

    Uses BEGIN EXCLUSIVE to prevent concurrent runs. Raises ValueError
    if another run is already in progress.

    Returns:
        The generated run_id (UUID).
    """
    conn = _get_conn(db_path)
    try:
        conn.execute("BEGIN EXCLUSIVE")
        row = conn.execute(
            "SELECT id FROM pipeline_runs WHERE status = 'running'"
        ).fetchone()
        if row:
            conn.rollback()
            raise ValueError("A pipeline run is already in progress")

        run_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """INSERT INTO pipeline_runs (id, target_date, status, started_at)
               VALUES (?, ?, 'running', ?)""",
            (run_id, target_date, started_at),
        )
        conn.commit()
        return run_id
    finally:
        conn.close()


def update_run_stages(run_id: str, stages_json: str, db_path: str | None = None) -> None:
    """Update the stages_json column for a run."""
    conn = _get_conn(db_path)
    try:
        conn.execute(
            "UPDATE pipeline_runs SET stages_json = ? WHERE id = ?",
            (stages_json, run_id),
        )
        conn.commit()
    finally:
        conn.close()


def update_run_pid(run_id: str, pid: int, db_path: str | None = None) -> None:
    """Store the subprocess PID in the pipeline_runs row."""
    conn = _get_conn(db_path)
    try:
        conn.execute(
            "UPDATE pipeline_runs SET pid = ? WHERE id = ?",
            (pid, run_id),
        )
        conn.commit()
    finally:
        conn.close()


def complete_run(run_id: str, duration_s: float, db_path: str | None = None) -> None:
    """Mark a run as complete."""
    conn = _get_conn(db_path)
    try:
        completed_at = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """UPDATE pipeline_runs
               SET status = 'complete', completed_at = ?, duration_s = ?
               WHERE id = ?""",
            (completed_at, duration_s, run_id),
        )
        conn.commit()
    finally:
        conn.close()


def fail_run(
    run_id: str,
    error_message: str,
    error_stage: str | None = None,
    db_path: str | None = None,
) -> None:
    """Mark a run as failed."""
    conn = _get_conn(db_path)
    try:
        completed_at = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """UPDATE pipeline_runs
               SET status = 'failed', completed_at = ?, error_message = ?, error_stage = ?
               WHERE id = ?""",
            (completed_at, error_message, error_stage, run_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_run(run_id: str, db_path: str | None = None) -> dict | None:
    """Fetch a single run by ID. Returns dict or None."""
    conn = _get_conn(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM pipeline_runs WHERE id = ?", (run_id,)
        ).fetchone()
        if row is None:
            return None
        return _row_to_dict(row)
    finally:
        conn.close()


def list_runs(limit: int = 14, db_path: str | None = None) -> list[dict]:
    """List recent runs ordered by started_at DESC."""
    conn = _get_conn(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a plain dict with parsed stages."""
    d = dict(row)
    # Parse stages_json into a list
    stages_raw = d.get("stages_json")
    if stages_raw:
        try:
            d["stages"] = json.loads(stages_raw)
        except (json.JSONDecodeError, TypeError):
            d["stages"] = []
    else:
        d["stages"] = []
    return d


def _get_project_root() -> str:
    """Return the project root directory (where pyproject.toml lives)."""
    # Walk up from this file to find the project root
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            return str(parent)
    # Fallback: cwd
    return os.getcwd()


async def start_pipeline_subprocess(
    run_id: str, target_date: str
) -> asyncio.subprocess.Process:
    """Launch the pipeline as a subprocess with --json-progress.

    Returns the asyncio subprocess handle.
    """
    project_root = _get_project_root()
    cmd = [
        sys.executable,
        "-m",
        "src.main",
        "--from",
        target_date,
        "--to",
        target_date,
        "--json-progress",
        "--run-id",
        run_id,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=project_root,
    )

    # Store PID
    if proc.pid:
        update_run_pid(run_id, proc.pid)

    return proc


async def stream_pipeline_events(
    run_id: str, proc: asyncio.subprocess.Process
) -> AsyncIterator[dict]:
    """Read JSON progress lines from subprocess stdout, update DB, yield events.

    On process exit code != 0, marks the run as failed.
    On exit code 0, marks the run as complete.
    """
    import time

    start_time = time.time()

    assert proc.stdout is not None

    async for raw_line in proc.stdout:
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            event = json.loads(line)
            # Persist stages to DB
            if "stages" in event:
                update_run_stages(run_id, json.dumps(event["stages"]))
            yield event
        except json.JSONDecodeError:
            # Non-JSON line from subprocess (shouldn't happen with --json-progress)
            logger.debug("Non-JSON subprocess output: %s", line[:200])
            continue

    # Wait for process to finish
    return_code = await proc.wait()
    duration_s = time.time() - start_time

    if return_code == 0:
        complete_run(run_id, duration_s)
        yield {
            "run_id": run_id,
            "status": "complete",
            "stage": None,
            "elapsed_s": round(duration_s, 2),
            "error": None,
        }
    else:
        # Read stderr for error details
        stderr_data = b""
        if proc.stderr:
            stderr_data = await proc.stderr.read()
        error_msg = stderr_data.decode("utf-8", errors="replace").strip()[-500:] or f"Process exited with code {return_code}"
        fail_run(run_id, error_msg)
        yield {
            "run_id": run_id,
            "status": "failed",
            "stage": None,
            "elapsed_s": round(duration_s, 2),
            "error": error_msg,
        }


def cleanup_orphaned_runs(db_path: str | None = None) -> int:
    """Find runs with status='running' whose PID is no longer alive. Mark as failed.

    Returns the number of orphaned runs cleaned up.
    """
    conn = _get_conn(db_path)
    cleaned = 0
    try:
        rows = conn.execute(
            "SELECT id, pid FROM pipeline_runs WHERE status = 'running'"
        ).fetchall()
        for row in rows:
            run_id = row["id"]
            pid = row["pid"]
            if pid is None or not _is_pid_alive(pid):
                completed_at = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    """UPDATE pipeline_runs
                       SET status = 'failed', completed_at = ?,
                           error_message = 'Server restarted during run'
                       WHERE id = ?""",
                    (completed_at, run_id),
                )
                cleaned += 1
                logger.info("Cleaned up orphaned run %s (pid=%s)", run_id, pid)
        if cleaned:
            conn.commit()
    finally:
        conn.close()
    return cleaned


def _is_pid_alive(pid: int) -> bool:
    """Check if a process with the given PID is still running."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False
