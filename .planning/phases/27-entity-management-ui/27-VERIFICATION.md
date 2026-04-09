---
phase: 27-entity-management-ui
verified: 2026-04-09T04:00:00Z
status: passed
score: 25/25 must-haves verified
re_verification:
  previous_status: gaps_found
  previous_score: 21/25
  gaps_closed:
    - "EntityFormPanel is now imported and rendered in providers.tsx (line 6 + line 26)"
    - "EntityDeleteDialog is now imported and rendered in providers.tsx (line 7 + line 27)"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Click Edit on an entity header, confirm the slide-over Sheet appears pre-filled"
    expected: "Sheet opens at ~400px wide, entity name and type pre-populated. Submit updates entity and shows toast."
    why_human: "Cannot simulate React state-driven Sheet open from static analysis"
  - test: "Click Delete on an entity header, type the entity name in the confirmation dialog, click Delete"
    expected: "Dialog opens, Delete button enabled only when typed text matches entity name exactly. On confirm, entity soft-deleted, view resets, toast shown."
    why_human: "Cannot simulate DOM interaction or verify DB soft-delete from static analysis"
  - test: "Press Cmd+K, search for an entity, press Enter to navigate"
    expected: "Entity scoped view opens for selected entity. Escape closes palette."
    why_human: "Keyboard interaction cannot be verified from static code analysis"
  - test: "Use alias input within an entity scoped view; observe autocomplete suggestions"
    expected: "Suggestions are empty (unmatched-mentions endpoint returns []) but typed input still submits on Enter. Graceful degradation."
    why_human: "Requires live DB to test real suggestions; stub behavior needs runtime confirmation"
  - test: "In merge review panel, select a primary entity and click Approve Merge"
    expected: "Entities merge, one soft-deleted, mentions reassigned, toast shown, panel auto-advances to next proposal."
    why_human: "Cannot verify actual DB mutation or queue advancement from static analysis"
---

# Phase 27: Entity Management UI Verification Report

**Phase Goal:** Entity Management UI — CRUD forms, merge review, command palette. Users can manage the entity registry entirely from the browser.
**Verified:** 2026-04-09T04:00:00Z
**Status:** passed
**Re-verification:** Yes — after gap closure (Plan 27-05 mounted orphaned components)

## Re-verification Focus

Previous verification (2026-04-08T04:30:00Z) found two blockers:

- `EntityFormPanel` fully implemented but never mounted — create/edit slide-over unreachable
- `EntityDeleteDialog` fully implemented but never mounted — delete confirmation unreachable

Plan 27-05 added two imports and two JSX elements to `web/src/app/providers.tsx`. Commit `2e7afb3` confirms the change. This re-verification checks both gaps are closed and that nothing regressed.

## Goal Achievement

### Observable Truths

**Plan 01 — API Foundation**

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | POST /api/v1/entities creates entity, returns 201 | VERIFIED | `entities.py` line 47: `@router.post("", status_code=201)` calls `repo.add_entity` |
| 2 | PUT /api/v1/entities/{id} updates entity, returns 200 | VERIFIED | `entities.py` line 66: `@router.put("/{entity_id}")` calls `repo.update_entity` with 404 guard |
| 3 | DELETE /api/v1/entities/{id} soft-deletes, returns 204 | VERIFIED | `entities.py` line 90: `@router.delete("/{entity_id}", status_code=204)` calls `repo.remove_entity` |
| 4 | POST /api/v1/entities/{id}/aliases adds alias, returns 201 | VERIFIED | `entities.py` line 104: `status_code=201`, handles `ValueError` as 409 |
| 5 | DELETE /api/v1/entities/{id}/aliases/{alias} removes alias, returns 204 | VERIFIED | `entities.py` line 127: `status_code=204`, 404 if not found |
| 6 | GET /api/v1/merge-proposals returns pending proposals | VERIFIED | `merge_proposals.py` line 24: calls `generate_proposals(repo)`, enriches with entity stats |
| 7 | POST /api/v1/merge-proposals/{id}/approve executes merge | VERIFIED | `merge_proposals.py` line 67: calls `execute_merge(repo, ...)` after validating primary_entity_id |
| 8 | POST /api/v1/merge-proposals/{id}/reject updates status | VERIFIED | `merge_proposals.py` line 154: saves rejected proposal or updates status |
| 9 | apiMutate helper in web/src/lib/api.ts | VERIFIED | `api.ts` lines 12-27: full implementation with error parsing and 204 handling |
| 10 | shadcn Sheet, Command, Dialog, Input, Select, Label installed | VERIFIED | All 6 files present in `web/src/components/ui/` |

**Plan 02 — Entity CRUD Forms (previously gap items)**

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 11 | User can open slide-over panel to create entity | VERIFIED (was FAILED) | `providers.tsx` line 26: `<EntityFormPanel />` mounted; reads `formPanelOpen` from Zustand; entity-header calls `openFormPanel("edit", entityId)` |
| 12 | User can open panel pre-filled to edit entity | VERIFIED (was FAILED) | Same mount; `entity-form-panel.tsx` lines 38-41: reads `formPanelMode`, `formPanelEntityId` from store; pre-fills fields in `useEffect` |
| 13 | Inline validation errors appear on submit/blur | VERIFIED | `entity-form-panel.tsx` lines 95-110: validation logic present; now reachable via mount |
| 14 | User can delete entity by typing name in confirmation dialog | VERIFIED (was FAILED) | `providers.tsx` line 27: `<EntityDeleteDialog />` mounted; `entity-delete-dialog.tsx` line 60: `canDelete = confirmText === entityName` controls button; `entity-header.tsx` line 45: calls `openDeleteDialog(entityId)` |
| 15 | User can see alias chips below entity name | VERIFIED | `entity-scoped-view.tsx` line 48: `<AliasChipList aliases={data.aliases} entityId={data.entity_id} />` |
| 16 | User can remove alias with undo toast | VERIFIED | `alias-chip-list.tsx`: optimistic removal, 5s undo toast via sonner, restore on failure |
| 17 | User can add alias via type-to-add input | VERIFIED | `alias-input.tsx`: fetches `/entities/unmatched-mentions`, Enter/comma to submit, Escape to clear |
| 18 | Duplicate alias blocked with message showing owner entity | VERIFIED | `alias-input.tsx` line 57: catches 409, sets inline error |

**Plan 03 — Merge Review UI**

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 19 | User can see list of pending proposals with scores | VERIFIED | `merge-review-panel.tsx` line 25: `useQuery` fetches `/merge-proposals` |
| 20 | Side-by-side cards show name, type, aliases, mentions, score | VERIFIED | `merge-comparison-card.tsx`: all fields rendered with color-coded score |
| 21 | User picks primary entity before approving | VERIFIED | `merge-primary-picker.tsx`: selectedPrimaryId controls Approve button disabled state |
| 22 | Approving executes merge immediately | VERIFIED | `merge-review-panel.tsx` line 32: calls `apiMutate POST /merge-proposals/{id}/approve`; backend calls `execute_merge` |
| 23 | Empty state shown when no proposals remain | VERIFIED | `EmptyMergeState` shown when `proposals=[]` or `currentIndex >= proposals.length` |

**Plan 04 — Command Palette**

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 24 | Cmd+K opens command palette from anywhere | VERIFIED | `command-palette.tsx` line 173: keydown listener for `metaKey+k`/`ctrlKey+k`; mounted in `providers.tsx` line 25 |
| 25 | Results grouped under Entities, Dates, Actions headers | VERIFIED | `command-palette.tsx` lines 364, 391, 406: three `CommandGroup` blocks |
| 26 | Prefix filters (/ @ #) isolate groups | VERIFIED | `prefixMode` logic lines 197-203; `showEntities/Dates/Actions` booleans lines 293-295 |
| 27 | Selecting entity navigates to scoped view | VERIFIED | `handleSelectEntity` line 246: `setActiveTab("entities"); selectEntity(entityId)` |
| 28 | Selecting "Create Entity" opens form panel | VERIFIED | `handleCreateEntity` line 266: `openFormPanel("create")`; panel now mounted in providers.tsx |

**Score: 25/25 truths verified**

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `web/src/app/providers.tsx` | Global mount for all overlays | VERIFIED | Imports and renders `CommandPalette`, `EntityFormPanel`, `EntityDeleteDialog` — all wired |
| `web/src/components/entity/entity-form-panel.tsx` | Slide-over create/edit form | VERIFIED | Mounted in providers.tsx; reads `formPanelOpen/Mode/EntityId` from Zustand; calls `apiMutate POST/PUT` |
| `web/src/components/entity/entity-delete-dialog.tsx` | Name-confirmation delete dialog | VERIFIED | Mounted in providers.tsx; reads `deleteDialogOpen/EntityId` from Zustand; button gated on name match |
| `src/api/routers/entities.py` | Entity CRUD + alias endpoints | VERIFIED | POST/PUT/DELETE entity and alias add/remove all substantive |
| `src/api/routers/merge_proposals.py` | Merge proposal list/approve/reject | VERIFIED | All 3 endpoints substantive, `execute_merge` called on approve |
| `web/src/components/entity/alias-chip-list.tsx` | Alias chip management | VERIFIED | Renders, wired to API, optimistic removal with undo |
| `web/src/components/entity/alias-input.tsx` | Autocomplete alias input | VERIFIED | Wired to API, keyboard handling, 409 error handling |
| `web/src/components/merge/merge-review-panel.tsx` | Queue-based merge review | VERIFIED | Mounted in `page.tsx`, full implementation |
| `web/src/components/command/command-palette.tsx` | Global command palette | VERIFIED | Mounted in `providers.tsx`, full implementation |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `providers.tsx` | `entity-form-panel.tsx` | import + `<EntityFormPanel />` | WIRED | Lines 6 and 26 — confirmed in commit `2e7afb3` |
| `providers.tsx` | `entity-delete-dialog.tsx` | import + `<EntityDeleteDialog />` | WIRED | Lines 7 and 27 — confirmed in commit `2e7afb3` |
| `entity-header.tsx` | `ui-store.ts` | `openFormPanel("edit", entityId)` / `openDeleteDialog(entityId)` | WIRED | Line 37: Edit button; line 45: Delete button; both store actions confirmed in store |
| `entity-form-panel.tsx` | `/api/v1/entities` | `apiMutate POST/PUT` | WIRED | Component calls API correctly; now rendered so calls are reachable |
| `entity-delete-dialog.tsx` | `/api/v1/entities/{id}` | `apiMutate DELETE` | WIRED | Component calls API correctly; now rendered so calls are reachable |
| `providers.tsx` | `command-palette.tsx` | import + `<CommandPalette />` | WIRED | Lines 5 and 25 — unchanged, regression check passed |
| `merge-review-panel.tsx` | `/api/v1/merge-proposals` | `useQuery` + `apiMutate` | WIRED | List query and approve/reject mutations all present |
| `entities.py` | `repository.py` | `Depends(get_entity_repo)` | WIRED | All repo methods called in endpoints |

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| ENT-03 | 27-01, 27-02 | User can create, edit, and delete entities and aliases from browser | SATISFIED | API endpoints verified; alias CRUD wired; `EntityFormPanel` and `EntityDeleteDialog` now mounted and reachable via entity header buttons |
| ENT-04 | 27-01, 27-03 | Merge proposal review with side-by-side comparison, similarity score, approve/reject | SATISFIED | Backend endpoints and full merge review UI verified and wired; mounted in `page.tsx` |
| NAV-05 | 27-04 | Command palette (Cmd+K) for keyboard-first entity search, date jump, actions | SATISFIED | `CommandPalette` fully implemented and mounted globally in `providers.tsx` |

All three requirements marked complete in `.planning/REQUIREMENTS.md` (lines 27, 33-34, 101, 104-105).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/api/routers/entities.py` | 148-151 | `TODO: Implement full SQL join` — `unmatched-mentions` returns `[]` | Warning | Alias autocomplete degrades to empty suggestions; typed alias input still functional |
| `src/api/routers/merge_proposals.py` | 41 | `proposal_id=""` for fresh proposals; UI uses `source:target` fallback | Info | Functionally works via `getProposalId()` fallback; no user impact |

No blockers found. Both previous blockers (orphaned components) are resolved.

### Human Verification Required

#### 1. Entity Edit Slide-Over

**Test:** Navigate to an entity in the browser. Click the Edit button in the entity header.
**Expected:** Sheet opens at ~400px wide, pre-filled with entity name and type. Submit saves, invalidates cache, shows toast.
**Why human:** Cannot simulate React state-driven Sheet open from static analysis.

#### 2. Entity Delete Confirmation Dialog

**Test:** Click Delete on an entity header. Type the entity name exactly in the confirmation input. Click Delete.
**Expected:** Delete button disabled until name matches exactly. On confirm, entity soft-deleted, view resets, toast shown.
**Why human:** Cannot simulate DOM interaction or verify soft-delete execution from static analysis.

#### 3. Command Palette Keyboard Navigation

**Test:** Press Cmd+K anywhere. Type an entity name. Use arrow keys. Press Enter.
**Expected:** Entity scoped view opens for the selected entity. Escape closes palette.
**Why human:** Keyboard interaction cannot be verified from static code analysis.

#### 4. Alias Autocomplete Graceful Degradation

**Test:** Open an entity scoped view with a live DB. Type in the alias input.
**Expected:** Suggestions list is empty (unmatched-mentions returns []) but typed text submits on Enter.
**Why human:** Requires live DB; stub behavior needs runtime confirmation.

#### 5. Merge Approve End-to-End

**Test:** Open merge review panel (if proposals exist). Select primary entity. Click Approve Merge.
**Expected:** Merge executes (one entity soft-deleted, mentions reassigned), toast shown, panel advances to next proposal or shows empty state.
**Why human:** Cannot verify DB mutation or queue advancement from static analysis.

### Gaps Summary

No gaps remain. The two blockers from the initial verification are closed:

- `EntityFormPanel` is now imported and rendered in `providers.tsx` (lines 6 and 26)
- `EntityDeleteDialog` is now imported and rendered in `providers.tsx` (lines 7 and 27)

The change follows the exact same pattern as `CommandPalette`. Commit `2e7afb3` contains only the four required lines — two imports and two JSX elements. No other files were modified. The Zustand store state, entity-header button wiring, and component-level API calls were all already correct and remain unchanged.

The remaining warning-level anti-pattern (`unmatched-mentions` returning `[]`) is explicitly documented in the code and does not prevent any user-facing functionality — alias creation via direct text input continues to work.

---

_Verified: 2026-04-09T04:00:00Z_
_Verifier: Claude (gsd-verifier)_
