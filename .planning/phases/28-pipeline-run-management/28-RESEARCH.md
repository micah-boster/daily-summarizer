# Phase 28: Pipeline Run Management - Research

**Researched:** 2026-04-09
**Domain:** SSE real-time updates, subprocess isolation, run history persistence
**Confidence:** HIGH

## Summary

Phase 28 adds browser-triggered pipeline runs with real-time SSE progress, subprocess isolation, and a run history view. The existing codebase has `run_pipeline()` which calls `asyncio.run(async_pipeline(ctx))` -- this MUST be refactored since `asyncio.run()` cannot be called from within FastAPI's already-running event loop. The solution is `subprocess.Popen` with JSON-line progress output piped back to the API via an async reader, then forwarded to the browser as SSE events.

FastAPI has built-in SSE support via `StreamingResponse` with `text/event-stream` content type -- no additional library needed. The browser's native `EventSource` API handles reconnection automatically. Run state is persisted to SQLite so the history view works and SSE reconnects can resume mid-run.

**Primary recommendation:** Use `subprocess.Popen` to launch pipeline as a child process with `--json-progress` flag, persist run records to entity DB SQLite, and stream progress via FastAPI `StreamingResponse` with `text/event-stream`.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Persistent button in the app status bar -- always one click away
- Default target date is yesterday; expandable option to pick a different date
- No confirmation step -- click and go, pipeline is safe and idempotent
- If a run is already in progress: button disables and shows "Running..." with inline progress
- Cannot start a second concurrent run
- Real-time progress lives inline in the status bar where the trigger button is
- Shows each pipeline stage with running/complete/failed status and elapsed time
- Stage-level granularity only -- no sub-step detail, no raw logs
- Compact by default, expandable if needed for stage list
- On success: toast notification with link that auto-navigates to that day's summary
- New "Runs" tab in the left nav alongside Summaries and Entities
- Table layout: each row shows date processed, status badge, duration, timestamp
- Default shows last 14 days of runs
- Click a failed run row to expand: which stage failed, error message, stack trace snippet
- Click a successful run to navigate to that date's summary
- Full re-run only -- no partial retry from failed stage
- SSE auto-reconnect: backend sends current state on connect
- On failure: error toast + status bar turns red with error indicator until dismissed
- Run state persisted to SQLite -- survives server restart

### Claude's Discretion
- Status bar layout and icon design
- SSE event format and reconnection protocol details
- SQLite schema for run records
- Subprocess vs thread pool isolation strategy (roadmap pitfall warnings lean subprocess)
- Exact stage names and progress percentages

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PIPE-01 | User can trigger a pipeline run from the browser and receive real-time status via SSE | StreamingResponse SSE pattern, EventSource client, status bar trigger button |
| PIPE-02 | Pipeline runs execute in isolation (subprocess/thread) -- never block the API server | subprocess.Popen with JSON-line output, async stdout reader |
| PIPE-03 | Run history is visible with status, duration, and date processed | SQLite pipeline_runs table, /api/v1/runs endpoint, Runs tab in left nav |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI StreamingResponse | 0.135+ (installed) | SSE endpoint | Built-in, no extra dependency |
| subprocess.Popen | stdlib | Process isolation | Explicit process boundary, no event loop conflict |
| sqlite3 | stdlib | Run history persistence | Already used for entity DB, same patterns |
| EventSource | browser native | SSE client | Auto-reconnect built-in, no npm package needed |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncio.subprocess | stdlib | Async pipe reading | Read subprocess stdout without blocking event loop |
| date-fns | 4.1.0 (installed) | Date formatting | Duration display, relative timestamps in run history |
| sonner | 2.0.7 (installed) | Toast notifications | Success/failure toasts |
| zustand | 5.0.12 (installed) | Pipeline state | Run status, SSE connection state |
| lucide-react | 1.7.0 (installed) | Icons | Play, check, x, loader icons |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| subprocess.Popen | asyncio.to_thread(run_pipeline) | Thread shares process memory but still hits asyncio.run() conflict -- subprocess is cleaner |
| subprocess.Popen | multiprocessing.Process | More Pythonic but harder to capture structured output |
| EventSource | fetch() + ReadableStream | EventSource has automatic reconnection; manual fetch would need custom retry logic |

## Architecture Patterns

### Recommended Project Structure
```
src/api/routers/
├── pipeline.py          # POST /runs, GET /runs, GET /runs/{id}, GET /runs/{id}/stream
src/api/services/
├── pipeline_runner.py   # Subprocess launch, async stdout reader, run record management
src/api/models/
├── pipeline.py          # RunResponse, RunStage, RunStatus Pydantic models
web/src/
├── hooks/use-pipeline.ts    # usePipelineRun, useRunHistory hooks
├── stores/pipeline-store.ts # Run state, SSE connection management
├── components/
│   ├── layout/status-bar.tsx      # Persistent status bar with trigger button
│   ├── pipeline/
│   │   ├── run-trigger.tsx        # Trigger button + inline progress
│   │   ├── run-progress.tsx       # Stage-by-stage progress display
│   │   └── run-history.tsx        # Runs tab table view
│   └── nav/nav-tab-switcher.tsx   # Updated: add "runs" tab
```

### Pattern 1: Subprocess with JSON-line Progress
**What:** Launch pipeline as `python -m src.main --from YYYY-MM-DD --json-progress` subprocess. Pipeline emits JSON lines to stdout for each stage transition. API reads stdout asynchronously and forwards as SSE events.
**When to use:** Always -- this is the isolation pattern.
**Example:**
```python
# src/api/services/pipeline_runner.py
import asyncio
import subprocess
import json

async def run_pipeline_subprocess(target_date: str) -> AsyncIterator[dict]:
    proc = await asyncio.create_subprocess_exec(
        "python", "-m", "src.main", "--from", target_date, "--to", target_date, "--json-progress",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    async for line in proc.stdout:
        event = json.loads(line.decode().strip())
        yield event
    await proc.wait()
```

### Pattern 2: FastAPI SSE via StreamingResponse
**What:** Yield `data: {json}\n\n` formatted strings from an async generator.
**When to use:** For the /runs/{id}/stream endpoint.
**Example:**
```python
from fastapi.responses import StreamingResponse

@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: str):
    async def event_generator():
        async for event in pipeline_events(run_id):
            yield f"data: {json.dumps(event)}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### Pattern 3: EventSource Client with Reconnection
**What:** Browser EventSource connects to SSE endpoint. On reconnect, backend sends current state snapshot first, then live updates.
**When to use:** For run-progress.tsx component.
**Example:**
```typescript
const es = new EventSource(`/api/v1/runs/${runId}/stream`);
es.onmessage = (event) => {
  const data = JSON.parse(event.data);
  updateRunState(data);
};
es.onerror = () => {
  // EventSource auto-reconnects; backend sends full state on new connection
};
```

### Pattern 4: SQLite Run Records
**What:** Pipeline runs stored in SQLite with status, stages JSON, timestamps. Enables history view and SSE reconnection state.
**When to use:** Every run trigger creates a record; stage transitions update it.

### Anti-Patterns to Avoid
- **asyncio.run() inside FastAPI:** The existing `run_pipeline()` calls `asyncio.run(async_pipeline(ctx))`. This CANNOT be called from FastAPI's event loop. Must use subprocess.
- **Thread pool with asyncio.run():** Even in a thread, `asyncio.run()` creates a new event loop which works but is fragile. Subprocess is the clean boundary.
- **Polling instead of SSE:** Adding a polling endpoint works but wastes bandwidth and adds latency. SSE is simpler and real-time.
- **Storing run state in memory only:** Server restart loses all state. Must persist to SQLite.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSE protocol | Custom event formatting | FastAPI StreamingResponse with `text/event-stream` | Protocol is simple but edge cases (reconnection, last-event-id) matter |
| SSE client | Custom fetch + retry | Browser native EventSource | Built-in reconnection, standardized API |
| Process management | Custom fork/exec | asyncio.create_subprocess_exec | Proper async pipe handling, cross-platform |
| Toast notifications | Custom notification system | sonner (already installed) | Consistent with existing app UX |

## Common Pitfalls

### Pitfall 1: Event Loop Conflict
**What goes wrong:** Calling `asyncio.run()` from within FastAPI's running event loop raises RuntimeError.
**Why it happens:** `run_pipeline()` currently uses `asyncio.run(async_pipeline(ctx))` which creates a new event loop.
**How to avoid:** Use subprocess isolation. The child process has its own event loop.
**Warning signs:** `RuntimeError: This event loop is already running`

### Pitfall 2: Zombie Processes
**What goes wrong:** Pipeline subprocess outlives the API server or SSE connection.
**Why it happens:** Client disconnects but subprocess keeps running.
**How to avoid:** Track subprocess PID in run record. On server startup, check for orphaned runs (status=running but process dead) and mark as failed. Use `proc.terminate()` if client explicitly cancels.
**Warning signs:** Multiple python processes in `ps aux` after runs should be complete.

### Pitfall 3: Lost SSE State on Reconnect
**What goes wrong:** Client reconnects after network blip but has no idea what stages completed.
**Why it happens:** SSE events are fire-and-forget; missed events are gone.
**How to avoid:** On new SSE connection, read current run state from SQLite and send a full state snapshot as the first event. Then continue with live updates.
**Warning signs:** Progress bar resets to 0% after brief network interruption.

### Pitfall 4: Concurrent Run Race Condition
**What goes wrong:** Two users (or double-click) start two pipelines simultaneously.
**Why it happens:** No lock between "check if running" and "start new run".
**How to avoid:** Use SQLite transaction: INSERT new run only if no row has status='running'. Single-writer SQLite guarantees atomicity.
**Warning signs:** Two pipeline processes running simultaneously.

### Pitfall 5: Subprocess Python Path
**What goes wrong:** Subprocess can't find `src.*` modules.
**Why it happens:** Subprocess may have different working directory or PYTHONPATH.
**How to avoid:** Use `sys.executable` for the Python binary. Set `cwd` to project root. Pass `env` with proper PYTHONPATH.
**Warning signs:** `ModuleNotFoundError: No module named 'src'`

## Code Examples

### SSE Event Format
```python
# Each event is a JSON object sent as SSE data
{
    "run_id": "abc123",
    "status": "running",  # running | complete | failed
    "stage": "calendar_ingest",  # current stage name
    "stage_status": "running",  # running | complete | failed
    "stages": [
        {"name": "calendar_ingest", "status": "complete", "elapsed_s": 12.3},
        {"name": "transcript_ingest", "status": "running", "elapsed_s": 5.1},
        {"name": "synthesis", "status": "pending", "elapsed_s": null},
    ],
    "target_date": "2026-04-08",
    "started_at": "2026-04-09T10:30:00Z",
    "elapsed_s": 17.4,
    "error": null
}
```

### SQLite Schema for Run Records
```sql
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id TEXT PRIMARY KEY,  -- UUID
    target_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',  -- running | complete | failed
    stages_json TEXT,  -- JSON array of stage objects
    started_at TEXT NOT NULL,
    completed_at TEXT,
    duration_s REAL,
    error_message TEXT,
    error_stage TEXT,
    pid INTEGER  -- subprocess PID for orphan detection
);
CREATE INDEX idx_pipeline_runs_status ON pipeline_runs(status);
CREATE INDEX idx_pipeline_runs_started ON pipeline_runs(started_at DESC);
```

### Pipeline JSON Progress Output
```python
# Added to src/main.py or new src/pipeline_progress.py
import json
import sys

class ProgressReporter:
    """Emits JSON progress lines to stdout for subprocess communication."""
    def __init__(self, target_date: str, run_id: str):
        self.target_date = target_date
        self.run_id = run_id
        self.stages = []

    def stage_start(self, name: str):
        self.stages.append({"name": name, "status": "running", "elapsed_s": 0})
        self._emit()

    def stage_complete(self, name: str, elapsed_s: float):
        for s in self.stages:
            if s["name"] == name:
                s["status"] = "complete"
                s["elapsed_s"] = elapsed_s
        self._emit()

    def _emit(self):
        print(json.dumps({"run_id": self.run_id, "stages": self.stages}), flush=True)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| WebSocket for real-time | SSE for unidirectional streams | Stable (SSE predates WS) | Simpler server, auto-reconnect, no WS library needed |
| Polling for job status | SSE streaming | N/A | Real-time UX without polling overhead |
| In-process pipeline | Subprocess isolation | Phase 28 decision | Eliminates event loop conflict entirely |

## Open Questions

1. **Pipeline stage names**
   - What we know: async_pipeline has phases: parallel ingest (calendar, slack, hubspot, docs, notion, transcripts), dedup, synthesis, entity discovery, entity attribution, output writing
   - What's unclear: Exact granularity -- should each ingest source be a separate stage or grouped as "ingest"?
   - Recommendation: Group as "ingest" (single stage) since they run in parallel and individually are fast. Keep synthesis, entity_processing, output as separate stages. Total ~4-5 stages.

2. **Entity DB vs separate runs DB**
   - What we know: Entity data lives in entity.db configured via config.yaml
   - What's unclear: Should pipeline_runs table go in entity.db or a new runs.db?
   - Recommendation: Use entity.db -- it's the only SQLite DB the API already connects to. Adding a table is simpler than managing a second DB connection.

## Sources

### Primary (HIGH confidence)
- FastAPI docs: StreamingResponse supports async generators with text/event-stream media type
- Python stdlib: asyncio.create_subprocess_exec for async subprocess management
- MDN: EventSource API with automatic reconnection behavior

### Secondary (MEDIUM confidence)
- Existing codebase analysis: src/pipeline.py, src/pipeline_async.py, src/api/app.py patterns
- Existing codebase: entity/db.py SQLite connection patterns with WAL mode

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All tools are stdlib or already-installed packages
- Architecture: HIGH - Subprocess + SSE is well-established pattern, codebase analysis confirms feasibility
- Pitfalls: HIGH - Event loop conflict is documented in STATE.md, other pitfalls are well-known

**Research date:** 2026-04-09
**Valid until:** 2026-05-09 (stable patterns, no fast-moving dependencies)
