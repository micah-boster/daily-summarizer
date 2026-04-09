---
phase: 27-entity-management-ui
plan: 01
subsystem: api
tags: [fastapi, shadcn-ui, pydantic, sqlite, entity-crud, merge-proposals]

requires:
  - phase: 26-entity-api-browser
    provides: "Entity read API, EntityRepository, entity list/scoped view endpoints"
provides:
  - "Entity CRUD write endpoints (POST/PUT/DELETE)"
  - "Alias add/remove endpoints with duplicate detection"
  - "Merge proposal list/approve/reject endpoints with merge execution"
  - "apiMutate frontend helper for write operations"
  - "shadcn-ui Sheet, Command, Dialog, Input, Select, Label components"
  - "TypeScript types for entity write payloads and responses"
affects: [27-02, 27-03, 27-04]

tech-stack:
  added: [cmdk, @radix-ui/react-dialog, @radix-ui/react-select, @radix-ui/react-label]
  patterns: ["apiMutate for POST/PUT/DELETE with error parsing and 204 handling", "BEGIN IMMEDIATE for SQLite write safety", "source:target encoded proposal IDs for fresh proposals"]

key-files:
  created:
    - src/api/models/requests.py
    - src/api/routers/merge_proposals.py
    - web/src/components/ui/sheet.tsx
    - web/src/components/ui/command.tsx
    - web/src/components/ui/dialog.tsx
    - web/src/components/ui/input.tsx
    - web/src/components/ui/select.tsx
    - web/src/components/ui/label.tsx
  modified:
    - src/api/models/responses.py
    - src/api/routers/entities.py
    - src/entity/repository.py
    - src/api/app.py
    - web/src/lib/api.ts
    - web/src/lib/types.ts

key-decisions:
  - "Fresh merge proposals use source:target encoded IDs since they lack DB records until approved/rejected"
  - "Unmatched mentions endpoint returns empty list as stub with TODO for full SQL join implementation"
  - "Approve endpoint allows caller to pick primary_entity_id (which entity survives the merge)"

patterns-established:
  - "apiMutate<T>(path, {method, body?}): standard frontend mutation helper"
  - "Entity write endpoints wrap repo calls in try/except for sqlite3.OperationalError -> 503"
  - "409 Conflict for duplicate alias detection via IntegrityError"

requirements-completed: [ENT-03, ENT-04, NAV-05]

duration: 3min
completed: 2026-04-08
---

# Phase 27 Plan 01: API Foundation + Frontend Infrastructure Summary

**Entity CRUD/alias/merge write endpoints with shadcn-ui components and apiMutate helper for Phase 27 UI plans**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-09T03:03:16Z
- **Completed:** 2026-04-09T03:06:22Z
- **Tasks:** 3
- **Files modified:** 18

## Accomplishments
- Full entity CRUD API: POST (201), PUT (200), DELETE (204) with proper validation and error handling
- Alias management endpoints with 409 duplicate detection and 404 for missing aliases
- Merge proposal list/approve/reject endpoints with actual merge execution (mention reassignment, alias transfer, soft-delete)
- Frontend apiMutate helper and all TypeScript types ready for UI consumption
- Six shadcn-ui components installed for Phase 27 UI work

## Task Commits

Each task was committed atomically:

1. **Task 1: Entity write API endpoints and request models** - `5deb4d2` (feat)
2. **Task 2: Merge proposal API endpoints and register router** - `1049dde` (feat)
3. **Task 3: shadcn-ui components and frontend API/types** - `4cacae4` (feat)

## Files Created/Modified
- `src/api/models/requests.py` - Pydantic request models (CreateEntity, UpdateEntity, AddAlias)
- `src/api/models/responses.py` - Added EntityResponse, AliasResponse, MergeProposalResponse
- `src/api/routers/entities.py` - Added POST/PUT/DELETE entity and alias endpoints
- `src/entity/repository.py` - Added update_entity method with BEGIN IMMEDIATE
- `src/api/routers/merge_proposals.py` - Merge proposal list/approve/reject router
- `src/api/app.py` - Registered merge_proposals router
- `web/src/lib/api.ts` - Added apiMutate helper
- `web/src/lib/types.ts` - Added write payload and response types
- `web/src/components/ui/{sheet,command,dialog,input,select,label}.tsx` - shadcn-ui components

## Decisions Made
- Fresh merge proposals use "source_id:target_id" encoded IDs since generate_proposals() returns in-memory results without DB records
- Approve endpoint accepts primary_entity_id to let the user choose which entity survives
- Unmatched mentions endpoint returns empty list as a stub (full SQL join deferred)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] App file is app.py not main.py**
- **Found during:** Task 2 (register merge proposals router)
- **Issue:** Plan referenced src/api/main.py but the actual file is src/api/app.py
- **Fix:** Registered router in correct file (app.py)
- **Files modified:** src/api/app.py
- **Verification:** Import and route check passes
- **Committed in:** 1049dde

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Trivial filename correction. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All write API endpoints ready for entity edit panel (Plan 02)
- All shadcn-ui components ready for entity detail sheet (Plan 02)
- apiMutate helper ready for frontend mutation hooks
- Merge proposal endpoints ready for merge review UI (Plan 03)

---
*Phase: 27-entity-management-ui*
*Completed: 2026-04-08*
