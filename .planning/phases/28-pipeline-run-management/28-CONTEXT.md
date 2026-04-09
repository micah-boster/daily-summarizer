# Phase 28: Pipeline Run Management - Context

**Gathered:** 2026-04-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Trigger and monitor pipeline runs from the browser with real-time SSE status updates, subprocess isolation, and a run history view. Pipeline runs once daily processing a target date. Creating new pipeline stages, modifying pipeline logic, or adding scheduling are out of scope.

</domain>

<decisions>
## Implementation Decisions

### Run trigger UX
- Persistent button in the app status bar -- always one click away
- Default target date is yesterday; expandable option to pick a different date
- No confirmation step -- click and go, pipeline is safe and idempotent
- If a run is already in progress: button disables and shows "Running..." with inline progress
- Cannot start a second concurrent run

### Progress display
- Real-time progress lives inline in the status bar where the trigger button is
- Shows each pipeline stage (calendar_ingest, transcript_ingest, synthesis, etc.) with running/complete/failed status and elapsed time
- Stage-level granularity only -- no sub-step detail, no raw logs
- Compact by default, expandable if needed for stage list
- On success: toast notification "Pipeline complete for Apr 8" with link that auto-navigates to that day's summary

### Run history view
- New "Runs" tab in the left nav alongside Summaries and Entities
- Table layout: each row shows date processed, status badge (success/failed/running), duration, timestamp
- Default shows last 14 days of runs
- Click a failed run row to expand: which stage failed, error message, stack trace snippet
- Click a successful run to navigate to that date's summary

### Failure & recovery
- Full re-run only -- no partial retry from failed stage (pipeline stages are fast enough)
- SSE auto-reconnect: EventSource reconnects automatically, backend sends current state on connect so progress resumes seamlessly
- On failure: error toast + status bar turns red with error indicator until dismissed
- Run state persisted to SQLite -- survives server restart, enables history even after crashes

### Claude's Discretion
- Status bar layout and icon design
- SSE event format and reconnection protocol details
- SQLite schema for run records
- Subprocess vs thread pool isolation strategy (roadmap pitfall warnings lean subprocess)
- Exact stage names and progress percentages

</decisions>

<specifics>
## Specific Ideas

- Status bar should feel like a CI/CD pipeline indicator -- compact, always visible, but not distracting
- The "Runs" tab in left nav follows the same tab pattern as Summaries and Entities (already built in Phase 26)
- Auto-navigate to new summary on success is the key UX win -- run completes, you're already looking at the result

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 28-pipeline-run-management*
*Context gathered: 2026-04-09*
