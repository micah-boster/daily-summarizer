---
phase: 20-entity-discovery-backfill
plan: 01
subsystem: entity
tags: [pydantic, claude-structured-outputs, name-normalization, entity-extraction, regex]
requirements: [DISC-01, DISC-02]

# Dependency graph
requires:
  - phase: 19-entity-registry-foundation
    provides: Entity/EntityType/ConfidenceLevel models and repository
provides:
  - Name normalization for companies (suffix stripping) and people (abbreviation matching)
  - Claude-based entity extraction from synthesis text via structured outputs
  - Extended SynthesisItem/CommitmentRow models with entity_names field
  - Synthesis prompt entity extraction instruction
affects: [20-02-backfill-pipeline, 20-03-hubspot-crossref, 21-entity-attribution]

# Tech tracking
tech-stack:
  added: []
  patterns: [regex-based-suffix-stripping, claude-structured-output-entity-extraction, graceful-degradation-on-api-failure]

key-files:
  created:
    - src/entity/normalizer.py
    - src/entity/discovery.py
    - tests/test_entity_normalizer.py
    - tests/test_discovery.py
  modified:
    - src/synthesis/models.py
    - src/synthesis/synthesizer.py

key-decisions:
  - "Used compiled regex for suffix stripping rather than iterative string replacement"
  - "Person name matching uses prefix-based last name comparison for abbreviation support"
  - "Entity extraction uses separate retry-decorated function (same pattern as synthesizer.py)"

patterns-established:
  - "Entity extraction graceful degradation: return empty list on any failure, log warning"
  - "Suffix stripping preserves original name if result would be empty"

requirements-completed: [DISC-01, DISC-02]

# Metrics
duration: 3min
completed: 2026-04-06
---

# Phase 20 Plan 01: Entity Extraction Foundation Summary

**Name normalization with 16 suffix variants, person abbreviation matching, and Claude structured output entity extraction from synthesis text**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-06T17:52:48Z
- **Completed:** 2026-04-06T17:55:52Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Company name normalizer strips 16 suffix variants (Inc, LLC, Corp, Corporation, Ltd, Co, LP, Partners, Group, Holdings + dotted variants)
- Person name matching enforces first+last requirement and handles abbreviations (Colin R. = Colin Roberts)
- Entity extraction via Claude structured outputs with DiscoveredEntity/EntityExtractionOutput models
- SynthesisItem and CommitmentRow extended with backward-compatible entity_names field
- Synthesis prompt includes entity_names extraction instruction
- 38 new tests (28 normalizer + 10 discovery), all 569 existing tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Name normalization module with TDD** - `57211f8` (feat)
2. **Task 2: Entity extraction module and synthesis model extension with TDD** - `5979e1c` (feat)

## Files Created/Modified
- `src/entity/normalizer.py` - Company suffix stripping, normalize_for_matching, person name matching
- `src/entity/discovery.py` - Claude structured output entity extraction with graceful degradation
- `src/synthesis/models.py` - Added entity_names field to SynthesisItem and CommitmentRow
- `src/synthesis/synthesizer.py` - Added entity extraction instruction to SYNTHESIS_PROMPT
- `tests/test_entity_normalizer.py` - 28 test cases for normalization and person matching
- `tests/test_discovery.py` - 10 test cases for entity extraction models and function

## Decisions Made
- Used compiled regex for suffix stripping rather than iterative string replacement (faster, cleaner)
- Person name matching uses prefix-based last name comparison for abbreviation support (handles "R." and "Rob" matching "Roberts")
- Entity extraction uses a separate retry-decorated function following the same pattern as synthesizer.py and commitments.py

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- normalizer.py and discovery.py ready for backfill pipeline (Plan 02)
- Entity extraction can be called on any synthesis text
- SynthesisItem/CommitmentRow entity_names populated during ongoing synthesis

## Self-Check: PASSED

All 6 files verified on disk. Both task commits (57211f8, 5979e1c) verified in git log.

---
*Phase: 20-entity-discovery-backfill*
*Completed: 2026-04-06*
