---
phase: 21-entity-attribution
plan: 01
subsystem: entity
tags: [attribution, sqlite, pydantic, tdd, sidecar]
requirements: [ATTR-01, ATTR-02]

requires:
  - phase: 19-entity-registry
    provides: EntityRepository, Entity model, aliases table, normalize_for_matching
  - phase: 20-entity-discovery
    provides: entity_names on SynthesisItem/CommitmentRow, entity discovery pipeline

provides:
  - Entity attribution module (match_name_to_entity, attribute_synthesis_items, persist_mentions)
  - Content hashing (deterministic 16-char hex)
  - SidecarEntityReference/SidecarEntitySummary models on DailySidecar
  - Full SynthesisItem/CommitmentRow objects in synthesis_result dict

affects: [21-02-pipeline-wiring, entity-views, entity-merge]

tech-stack:
  added: []
  patterns: [two-step matching with confidence scores, idempotent delete-then-insert persistence]

key-files:
  created:
    - src/entity/attributor.py
    - tests/test_attributor.py
  modified:
    - src/sidecar.py
    - src/synthesis/synthesizer.py
    - src/pipeline_async.py
    - tests/test_pipeline.py
    - tests/test_synthesizer.py

key-decisions:
  - "Alias name 'Affirm Financial' used for alias test instead of 'Affirm Inc' which normalizes to canonical name"
  - "Two-step matching: direct canonical (1.0) then alias SQL (0.7), with merge-target following"
  - "Sidecar enrichment uses getattr for graceful degradation when attribution is None"

patterns-established:
  - "Attribution confidence: 1.0 for direct name match, 0.7 for alias match"
  - "Content hashing: SHA256[:16] for deterministic source_id"
  - "Idempotent mention persistence: DELETE by date then INSERT"

requirements-completed: [ATTR-01, ATTR-02]

duration: 5min
completed: 2026-04-08
---

# Phase 21 Plan 01: TDD Attributor Module and Sidecar Models Summary

**Entity attributor with two-step name matching (direct 1.0, alias 0.7), content hashing, mention persistence, and sidecar entity enrichment**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-08T15:10:38Z
- **Completed:** 2026-04-08T15:16:00Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Built TDD attributor module: content_hash, match_name_to_entity, attribute_synthesis_items, persist_mentions
- Extended DailySidecar with entity_references per section and entity_summary top-level
- Changed _convert_synthesis_to_dict to preserve full SynthesisItem/CommitmentRow objects for downstream attribution
- All 616 tests pass including 15 new attribution tests

## Task Commits

Each task was committed atomically:

1. **Task 1a (RED): Failing tests** - `44a9da7` (test)
2. **Task 1b (GREEN): Attributor + sidecar models** - `a96494c` (feat)
3. **Task 2: Synthesizer preserves entity_names** - `a8f6662` (feat)

## Files Created/Modified
- `src/entity/attributor.py` - Entity attribution module with matching, hashing, persistence
- `tests/test_attributor.py` - 15 TDD tests for attribution logic
- `src/sidecar.py` - SidecarEntityReference, SidecarEntitySummary models; build_daily_sidecar accepts entity_attribution
- `src/synthesis/synthesizer.py` - _convert_synthesis_to_dict returns full objects
- `src/pipeline_async.py` - Updated to extract .content from SynthesisItem objects
- `tests/test_pipeline.py` - Updated mock return values to use SynthesisItem objects
- `tests/test_synthesizer.py` - Updated assertions for object-based return values

## Decisions Made
- Used "Affirm Financial" as alias test name since "Affirm Inc" normalizes to canonical "Affirm" (suffix stripping)
- Sidecar enrichment uses getattr() pattern for AttributionResult fields for graceful degradation

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Alias test used name that normalized to canonical**
- **Found during:** Task 1 GREEN phase (test_match_name_alias)
- **Issue:** "Affirm Inc" normalizes to "affirm" via suffix stripping, matching canonical at 1.0 instead of alias at 0.7
- **Fix:** Changed alias to "Affirm Financial" which does not normalize to canonical
- **Verification:** test_match_name_alias passes with confidence == 0.7
- **Committed in:** a96494c (part of GREEN commit)

**2. [Rule 3 - Blocking] Downstream consumers expected strings, not objects**
- **Found during:** Task 2 (synthesizer change)
- **Issue:** test_pipeline.py and test_synthesizer.py mock return values used plain strings
- **Fix:** Updated mocks to return SynthesisItem objects; updated assertions to use .content
- **Verification:** All 616 tests pass
- **Committed in:** a8f6662

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking)
**Impact on plan:** Both necessary for correctness. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Attributor module ready for pipeline wiring (Plan 21-02)
- build_daily_sidecar accepts entity_attribution parameter
- synthesis_result contains full objects with entity_names

---
*Phase: 21-entity-attribution*
*Completed: 2026-04-08*
