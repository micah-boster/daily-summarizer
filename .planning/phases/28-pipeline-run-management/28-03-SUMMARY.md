---
phase: 28-pipeline-run-management
plan: 03
subsystem: ui
tags: [react, tanstack-query, zustand, date-fns, pipeline, run-history]

requires:
  - phase: 28-pipeline-run-management
    provides: "Plan 01 REST API for /api/v1/runs, Plan 02 pipeline store and SSE hooks"
provides:
  - "Runs tab in left nav for browsing pipeline run history"
  - "Run history table with status badges, duration, timestamps"
  - "Expandable error detail for failed runs"
  - "Navigation from successful run to corresponding summary"
affects: [29-config-polish]

tech-stack:
  added: []
  patterns: ["Run history list with expandable error panels"]

key-files:
  created:
    - web/src/components/pipeline/run-history.tsx
  modified:
    - web/src/stores/ui-store.ts
    - web/src/components/nav/nav-tab-switcher.tsx
    - web/src/components/layout/left-nav.tsx
    - web/src/components/layout/right-sidebar.tsx
    - web/src/hooks/use-pipeline.ts

key-decisions:
  - "Widened right-sidebar activeTab prop to accept 'runs' for type compatibility"

patterns-established:
  - "Run history row pattern: click success -> navigate to summary, click failed -> expand error detail"

requirements-completed: [PIPE-03]

duration: 2min
completed: 2026-04-09
---

# Phase 28 Plan 03: Run History View Summary

**Runs tab in left nav with past run listing, status badges, duration display, and expandable failure drill-down**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-09T15:46:02Z
- **Completed:** 2026-04-09T15:47:56Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Runs tab added alongside Summaries and Entities in left nav tab switcher
- Run history table fetches last 14 days of runs with 30-second auto-refresh
- Status badges: green "Success", red "Failed", yellow pulsing "Running"
- Successful run click navigates to that date's summary
- Failed run click expands error detail panel with stage and message

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Runs tab to left nav** - `7906e58` (feat)
2. **Task 2: Run history table with expandable error details** - `1c55cc9` (feat)

## Files Created/Modified
- `web/src/components/pipeline/run-history.tsx` - Run history table with expandable error detail rows
- `web/src/hooks/use-pipeline.ts` - Added useRunHistory hook and RunResponse interface
- `web/src/stores/ui-store.ts` - Extended activeTab type to include 'runs'
- `web/src/components/nav/nav-tab-switcher.tsx` - Added third tab for Runs
- `web/src/components/layout/left-nav.tsx` - Conditional render of RunHistory when runs tab active
- `web/src/components/layout/right-sidebar.tsx` - Widened activeTab prop type

## Decisions Made
- Widened right-sidebar activeTab prop to accept 'runs' rather than casting in page.tsx -- cleaner type flow

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Widened right-sidebar activeTab prop type**
- **Found during:** Task 1 (TypeScript compilation)
- **Issue:** RightSidebar prop typed as "summaries" | "entities" conflicted with store's new 3-way union
- **Fix:** Widened prop type to include "runs" in right-sidebar.tsx
- **Files modified:** web/src/components/layout/right-sidebar.tsx
- **Verification:** TypeScript compiles cleanly
- **Committed in:** 7906e58 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary type widening for consistency. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All 3 plans of Phase 28 complete: API endpoints, pipeline store + SSE, and run history UI
- Pipeline run management fully functional end-to-end
- Ready for Phase 29 (Config + Polish)

---
*Phase: 28-pipeline-run-management*
*Completed: 2026-04-09*
