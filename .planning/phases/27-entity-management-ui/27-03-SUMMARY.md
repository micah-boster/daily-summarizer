---
phase: 27-entity-management-ui
plan: 03
subsystem: ui
tags: [react, tanstack-query, zustand, merge-review, shadcn-ui, sonner]

requires:
  - phase: 27-entity-management-ui
    plan: 01
    provides: "Merge proposal API endpoints (list/approve/reject), apiMutate helper, TypeScript types"
provides:
  - "Queue-based merge review UI with side-by-side entity comparison"
  - "Primary entity picker for merge approval"
  - "Merge review button with proposal count badge in entity nav"
  - "showMergeReview Zustand state for panel toggle"
affects: [27-04]

tech-stack:
  added: []
  patterns: ["useMutation with queryClient.invalidateQueries for merge operations", "Queue-based review flow with local index tracking and auto-advance"]

key-files:
  created:
    - web/src/components/merge/merge-comparison-card.tsx
    - web/src/components/merge/merge-primary-picker.tsx
    - web/src/components/merge/merge-review-panel.tsx
    - web/src/components/merge/merge-review-button.tsx
  modified:
    - web/src/stores/ui-store.ts
    - web/src/components/layout/left-nav.tsx
    - web/src/app/page.tsx

key-decisions:
  - "Used local state (useState) for queue index and primary selection rather than Zustand -- review state is ephemeral and per-session"
  - "Merge review button shows in entity nav only when proposals exist -- avoids cluttering UI when no merges pending"
  - "showMergeReview in Zustand clears selectedEntityId to avoid stale entity view behind merge panel"

patterns-established:
  - "useMutation pattern: mutationFn + onSuccess with toast + invalidateQueries + advance"
  - "Queue review: local index state, advance() resets selection and increments, empty state at end"

requirements-completed: [ENT-04]

duration: 3min
completed: 2026-04-09
---

# Phase 27 Plan 03: Merge Review UI Summary

**Queue-based merge review panel with side-by-side entity comparison cards, primary name picker, and approve/reject/skip flow**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-09T03:08:39Z
- **Completed:** 2026-04-09T03:12:09Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Side-by-side comparison cards showing entity name, type badge, aliases, mention count, and color-coded similarity score
- Primary entity picker with visual selection state and "will become alias" label
- Queue-based merge review panel with progress bar, approve/reject/skip actions, and auto-advance
- Merge review button in entity nav with live proposal count badge
- Integration into main page center panel via Zustand showMergeReview toggle

## Task Commits

Each task was committed atomically:

1. **Task 1: Create merge comparison card and primary picker components** - `6fef614` (feat)
2. **Task 2: Create merge review panel with queue flow and integrate into entity tab** - `7e32c25` (feat)

## Files Created/Modified
- `web/src/components/merge/merge-comparison-card.tsx` - Entity comparison card with name, type, aliases, mentions, similarity score
- `web/src/components/merge/merge-primary-picker.tsx` - Side-by-side picker composing two comparison cards with center divider
- `web/src/components/merge/merge-review-panel.tsx` - Queue-based review panel with approve/reject/skip and auto-advance
- `web/src/components/merge/merge-review-button.tsx` - Nav button with proposal count badge
- `web/src/stores/ui-store.ts` - Added showMergeReview state and setShowMergeReview action
- `web/src/components/layout/left-nav.tsx` - Added MergeReviewButton to entity tab content
- `web/src/app/page.tsx` - Added MergeReviewPanel to center content routing

## Decisions Made
- Used local state for queue index and primary selection (ephemeral per-session, no persistence needed)
- Merge review button only visible when proposals exist to avoid UI clutter
- showMergeReview clears selectedEntityId to prevent stale entity view

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Merge review UI complete, ready for command palette (Plan 04)
- All merge/ components self-contained in dedicated directory
- Pattern established for useMutation with cache invalidation

---
*Phase: 27-entity-management-ui*
*Completed: 2026-04-09*
