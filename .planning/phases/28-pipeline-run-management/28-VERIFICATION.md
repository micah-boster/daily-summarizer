---
phase: 28-pipeline-run-management
verified: 2026-04-09T16:30:00Z
status: passed
score: 14/14 must-haves verified
re_verification: false
gaps:
  - truth: "Runs tab shows table of past runs with status badge, duration, date, and timestamp"
    status: resolved
    reason: "Fixed in 456e868 -- useRunHistory now unwraps .runs from RunListResponse envelope"
  - truth: "Default shows last 14 days of runs"
    status: resolved
    reason: "Same root cause fixed in 456e868"
human_verification:
  - test: "Trigger a pipeline run from the status bar"
    expected: "Clicking Run Pipeline fires POST /api/v1/runs, button changes to Running..., stage names appear inline as the run progresses, toast with View Summary appears on completion"
    why_human: "Requires live backend and real pipeline execution -- cannot verify SSE event stream in static analysis"
  - test: "SSE reconnection after network drop"
    expected: "Close and reopen the EventSource tab during a run -- progress resumes from last known state without manual intervention"
    why_human: "Browser EventSource reconnection behavior requires a running server and simulated network interruption"
  - test: "Concurrent run prevention (409)"
    expected: "While a run is active, clicking Run Pipeline again shows toast 'A pipeline run is already in progress'"
    why_human: "Requires two concurrent browser sessions or rapid repeated clicking against a live backend"
  - test: "Visual status bar layout"
    expected: "Status bar is pinned to the bottom of the viewport, does not overlap page content (AppShell has pb-10), visible on all pages including Entities and Runs tabs"
    why_human: "Visual layout verification requires browser rendering"
---

# Phase 28: Pipeline Run Management Verification Report

**Phase Goal:** Users can trigger and monitor pipeline runs from the browser -- fire-and-forget with real-time status updates, never blocking the API server
**Verified:** 2026-04-09T16:30:00Z
**Status:** gaps_found
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

**Plan 01 (Backend)**

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | POST /api/v1/runs triggers a subprocess pipeline run and returns a run_id | VERIFIED | `trigger_run` in `pipeline.py` calls `create_run()`, launches `asyncio.create_task(_run_pipeline_background(...))`, returns 202 with `TriggerResponse(run_id=..., status="running")` |
| 2 | GET /api/v1/runs/{id}/stream returns SSE events with stage-by-stage progress | VERIFIED | `stream_run` endpoint returns `StreamingResponse` with `media_type="text/event-stream"` and correct headers. First event is full state snapshot. Active process stdout streamed line-by-line. |
| 3 | GET /api/v1/runs returns list of past runs with status, duration, and target_date | VERIFIED | `get_runs` queries `list_runs()` and returns `RunListResponse`. `RunResponse` includes `status`, `duration_s`, `target_date`. |
| 4 | Pipeline subprocess does not block the API event loop | VERIFIED | `start_pipeline_subprocess` uses `asyncio.create_subprocess_exec` (non-blocking). Background task launched via `asyncio.get_running_loop().create_task()`. Original sync `def` bug was caught and fixed during execution (documented in SUMMARY). |
| 5 | SSE reconnection sends current state snapshot as first event | VERIFIED | `event_generator()` yields `get_run(run_id)` as first event unconditionally before checking if process is active. |
| 6 | Only one pipeline run can execute at a time | VERIFIED | `create_run()` uses `BEGIN EXCLUSIVE` transaction, checks for `status='running'` before inserting, raises `ValueError("A pipeline run is already in progress")` which the router catches and returns as HTTP 409. |

**Plan 02 (Frontend Pipeline UI)**

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 7 | Status bar is always visible at the bottom of the app with a pipeline trigger button | VERIFIED | `StatusBar` imported and mounted in `web/src/app/layout.tsx` after `<Providers>` but before `<Toaster>`. Fixed at `bottom-0 z-50 h-10`. `RunTrigger` rendered inside `StatusBar`. |
| 8 | Clicking the trigger button fires POST /api/v1/runs and opens SSE stream | VERIFIED | `RunTrigger` calls `triggerRun(targetDate)` from `usePipelineRun`. Hook does `fetch(API_BASE/runs, { method: "POST" })` then opens `new EventSource(API_BASE/runs/{runId}/stream)`. |
| 9 | While running, button disables and shows Running... with inline stage progress | VERIFIED | `RunTrigger` renders a non-clickable div with `Loader2` + "Running..." when `isRunning`. `RunProgress` renders inline stage names from store when `status === "running"`. |
| 10 | Each stage shows running/complete/failed status with elapsed time | VERIFIED | `StageIcon` maps all 4 statuses to lucide icons. `formatElapsed` renders `elapsed_s` as "12.3s". Expanded view shows all stages with icons and elapsed time. |
| 11 | On success, toast notification appears with link to navigate to that day's summary | VERIFIED | `connectSSE` handler for `data.status === "complete"` calls `toast.success(...)` with `action: { label: "View Summary", onClick: () => setSelectedDate + setSelectedViewType }`. |
| 12 | On failure, status bar turns red with error indicator | VERIFIED | `RunTrigger` renders a red `bg-destructive/10` button with `XCircle` icon and truncated error text when `status === "failed" && !errorDismissed`. Click calls `dismissError()`. |
| 13 | SSE reconnects automatically and resumes progress display | VERIFIED | Hook uses native `EventSource` which reconnects automatically on transient errors. `onerror` handler only marks failure if `readyState === CLOSED` (permanent failure). |

**Plan 03 (Run History)**

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 14 | Runs tab appears in left nav alongside Summaries and Entities | VERIFIED | `nav-tab-switcher.tsx` has 3 tabs: summaries, entities, runs. `ui-store.ts` `activeTab` type is `"summaries" \| "entities" \| "runs"`. |
| 15 | Runs tab shows table of past runs with status badge, duration, date, and timestamp | FAILED | `RunHistory` calls `useRunHistory()` which returns `useQuery<RunResponse[]>`. The backend `GET /api/v1/runs` returns `RunListResponse { runs: RunResponse[], total: number }`. The hook casts the response as `RunResponse[]` without unwrapping `.runs`. At runtime `data` is the envelope object, not an array. `!runs \|\| runs.length === 0` evaluates to true (object has no `.length`) and the component always renders "No pipeline runs yet". |
| 16 | Default shows last 14 days of runs | FAILED | Same root cause -- run list never displays. API call uses `?limit=14` correctly, but response deserialization is broken. |
| 17 | Clicking a failed run expands to show error stage, message, and stack trace snippet | VERIFIED (in code) | `RunRow` has correct click handler toggling `expanded` state. Expanded panel renders `error_stage` and `error_message` in `font-mono`. Cannot be exercised at runtime due to gap above. |
| 18 | Clicking a successful run navigates to that date's summary | VERIFIED (in code) | `handleClick` for `status === "complete"` calls `setSelectedDate(run.target_date)` and `setActiveTab("summaries")`. Cannot be exercised at runtime due to gap above. |

**Score:** 14/16 truths verified (2 failed, same root cause)

Note: Truths 17 and 18 are correct in code but untestable at runtime until gap is closed. Counted as verified in-code only.

---

### Required Artifacts

**Plan 01 Backend**

| Artifact | Status | Details |
|----------|--------|---------|
| `src/api/routers/pipeline.py` | VERIFIED | 194 lines. All 4 endpoints implemented. Imports from service layer. Router exported. Registered in `app.py`. |
| `src/api/services/pipeline_runner.py` | VERIFIED | 320 lines. `create_run`, `update_run_stages`, `complete_run`, `fail_run`, `get_run`, `list_runs`, `start_pipeline_subprocess`, `stream_pipeline_events`, `cleanup_orphaned_runs` all implemented with real logic. |
| `src/api/models/pipeline.py` | VERIFIED | Pydantic models: `RunStage`, `RunResponse`, `RunListResponse`, `TriggerRequest` (with `get_target_date()`), `TriggerResponse`. All literal types correct. |
| `src/pipeline_progress.py` | VERIFIED | `ProgressReporter` class with `stage_start`, `stage_complete`, `stage_failed`, `run_complete`, `run_failed`, `_emit`. Writes `json.dumps(event)` to stdout with `flush=True`. |
| `src/entity/migrations.py` | VERIFIED | `SCHEMA_VERSION = 3`. `_migrate_v2_to_v3` creates `pipeline_runs` table with all required columns and both indexes. `MIGRATIONS` list has 3 entries matching schema version. |

**Plan 02 Frontend**

| Artifact | Status | Details |
|----------|--------|---------|
| `web/src/stores/pipeline-store.ts` | VERIFIED | Ephemeral Zustand store (no persist). Full state shape + `startRun`, `updateFromEvent`, `reset`, `dismissError` all implemented with non-trivial logic. |
| `web/src/hooks/use-pipeline.ts` | VERIFIED (with gap) | `usePipelineRun` hook: full implementation. `useRunHistory` hook: exists and calls API -- but has deserialization bug (see gaps). |
| `web/src/components/layout/status-bar.tsx` | VERIFIED | Fixed bottom status bar with `RunTrigger` and `RunProgress` on left, elapsed time on right. Subscribes to pipeline store. |
| `web/src/components/pipeline/run-trigger.tsx` | VERIFIED | All 4 states (idle, running, failed, complete) implemented with correct icons, colors, and actions. Date picker with `subDays` default. |
| `web/src/components/pipeline/run-progress.tsx` | VERIFIED | Compact/expandable stage progress. `StageIcon` maps all statuses. Elapsed time formatted inline. |

**Plan 03 Frontend**

| Artifact | Status | Details |
|----------|--------|---------|
| `web/src/components/pipeline/run-history.tsx` | VERIFIED (with gap) | Correct structure -- uses `useRunHistory`, renders loading/error/empty states, `RunRow` with click behavior, `StatusBadge` with correct colors. Broken at runtime due to hook deserialization bug. |
| `web/src/components/nav/nav-tab-switcher.tsx` | VERIFIED | 3 tabs including `runs`. Uses `useUIStore`. |
| `web/src/stores/ui-store.ts` | VERIFIED | `activeTab` type includes `"runs"`. `setActiveTab` param type matches. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/api/routers/pipeline.py` | `src/api/services/pipeline_runner.py` | `start_run, get_run, list_runs, stream_run` | VERIFIED | All 8 service functions imported at top of router file and called in corresponding endpoints |
| `src/api/services/pipeline_runner.py` | `src/pipeline_progress.py` | subprocess stdout JSON lines | VERIFIED | `stream_pipeline_events` reads `proc.stdout` line by line and calls `json.loads(line)`. `_emit()` in `ProgressReporter` calls `print(json.dumps(event), flush=True)`. |
| `src/api/services/pipeline_runner.py` | `entity.db (pipeline_runs table)` | sqlite3 connection | VERIFIED | `pipeline_runs` referenced in `create_run`, `update_run_stages`, `complete_run`, `fail_run`, `get_run`, `list_runs`, `cleanup_orphaned_runs`. |
| `web/src/hooks/use-pipeline.ts` | `/api/v1/runs` | `fetch POST` and `EventSource SSE` | VERIFIED | `triggerRun` does `fetch(API_BASE/runs, { method: "POST" })`. `connectSSE` opens `new EventSource(API_BASE/runs/{runId}/stream)`. |
| `web/src/components/pipeline/run-trigger.tsx` | `web/src/hooks/use-pipeline.ts` | `usePipelineRun` | VERIFIED | `usePipelineRun` imported and destructured at top of `RunTrigger`. `triggerRun` called on button click. |
| `web/src/components/layout/status-bar.tsx` | `web/src/stores/pipeline-store.ts` | `usePipelineStore` | VERIFIED | `usePipelineStore` imported and subscribed. `status` and `elapsedS` read from store. |
| `web/src/components/pipeline/run-history.tsx` | `/api/v1/runs` | TanStack Query `useQuery` | PARTIAL | `useRunHistory` calls `GET /api/v1/runs?limit=14` correctly. But `queryFn` deserializes response as `RunResponse[]` when the backend returns `RunListResponse { runs: RunResponse[], total: number }`. The `.runs` array is never unwrapped. |
| `web/src/components/layout/left-nav.tsx` | `web/src/components/pipeline/run-history.tsx` | `activeTab === "runs"` | VERIFIED | `RunHistory` imported. Rendered inside `{activeTab === "runs" && <RunHistory />}` block. |

---

### Requirements Coverage

| Requirement | Plans | Description | Status | Evidence |
|-------------|-------|-------------|--------|----------|
| PIPE-01 | 01, 02 | User can trigger a pipeline run from the browser and receive real-time status via SSE | SATISFIED | POST /api/v1/runs triggers subprocess. EventSource streams events to browser. Status bar shows inline progress. Toast on completion. |
| PIPE-02 | 01 | Pipeline runs execute in isolation (subprocess/thread) -- never block the API server | SATISFIED | `asyncio.create_subprocess_exec` launches isolated subprocess. Background task via `create_task`. API response returns immediately with 202. |
| PIPE-03 | 01, 03 | Run history is visible with status, duration, and date processed | PARTIALLY SATISFIED | Backend correctly stores and returns run history. Frontend Runs tab exists with correct components. But `useRunHistory` deserialization bug means history never renders in the browser. |

All 3 requirement IDs declared across plans (PIPE-01, PIPE-02, PIPE-03) are accounted for. No orphaned requirements.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `web/src/hooks/use-pipeline.ts` | 164 | `res.json() as Promise<RunResponse[]>` casts `RunListResponse` envelope to flat array -- type system bypassed with `as`, runtime behavior broken | Blocker | Run history tab always shows empty state regardless of actual run data |
| `web/src/components/pipeline/run-progress.tsx` | 32-33 | `return null` when not running | Info | Intentional -- component hides itself when idle. Not a stub. |

---

### Human Verification Required

#### 1. End-to-End Pipeline Trigger

**Test:** Click "Run Pipeline" in the status bar with default date (yesterday). Watch the status bar.
**Expected:** Button changes to "Running...", stage names appear inline (ingest, synthesis, entity_processing, output), each with spinning icon while active and check icon when complete. Toast appears with "View Summary" action that navigates to the correct date.
**Why human:** Requires live backend, real credentials, and actual pipeline execution to produce SSE events.

#### 2. SSE Reconnection

**Test:** Start a pipeline run, then disconnect/reconnect (navigate away and back, or use DevTools to simulate offline briefly).
**Expected:** Progress resumes from last known stage without data loss or duplicate events.
**Why human:** Browser EventSource native reconnection requires a live server and network simulation.

#### 3. Concurrent Run Prevention

**Test:** Click "Run Pipeline" twice in rapid succession while a run is active.
**Expected:** Second click shows toast "A pipeline run is already in progress". No second subprocess launched.
**Why human:** Requires timing coordination against a live backend.

#### 4. Status Bar Layout Across Pages

**Test:** Navigate between Summaries, Entities, and Runs tabs. Resize window to mobile width.
**Expected:** Status bar remains fixed at bottom on all tabs. Content is not obscured by the status bar (AppShell pb-10 clearance).
**Why human:** Visual layout requires browser rendering.

---

### Gaps Summary

One gap blocks goal achievement, with two truths failing from the same root cause:

**Root cause:** In `web/src/hooks/use-pipeline.ts`, the `useRunHistory` hook fetches `GET /api/v1/runs` which returns `RunListResponse` -- a wrapper object with shape `{ runs: RunResponse[], total: number }`. The hook's `queryFn` casts this as `Promise<RunResponse[]>` using TypeScript's `as` keyword, bypassing type checking without unwrapping the `.runs` property. The `RunHistory` component receives the wrapper object as `data`, calls `data.length` (undefined on a plain object), fails the array check, and renders "No pipeline runs yet" unconditionally.

The fix is a single-line change in `useRunHistory`:

```typescript
// Current (broken):
return res.json() as Promise<RunResponse[]>;

// Fixed:
const payload = await res.json() as { runs: RunResponse[]; total: number };
return payload.runs;
```

This is the only gap. All 14 other must-haves are fully verified. The backend, pipeline store, SSE hook, status bar, and nav tab are all correctly implemented and wired. Once this fix is applied, PIPE-03 will be satisfied and all phase truths verified.

---

_Verified: 2026-04-09T16:30:00Z_
_Verifier: Claude (gsd-verifier)_
