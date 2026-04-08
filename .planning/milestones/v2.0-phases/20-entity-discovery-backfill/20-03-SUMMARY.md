---
phase: 20-entity-discovery-backfill
plan: 03
subsystem: entity
tags: [hubspot, rapidfuzz, fuzzy-matching, cross-reference, crm-enrichment]
requirements: [DISC-05]

# Dependency graph
requires:
  - phase: 20-entity-discovery-backfill
    plan: 01
    provides: Name normalization (normalizer.py) for fuzzy matching
  - phase: 20-entity-discovery-backfill
    plan: 02
    provides: Backfill pipeline and pipeline_async entity discovery
  - phase: 19-entity-registry-foundation
    provides: EntityRepository, Entity models, SQLite schema
provides:
  - HubSpot contact search with exact and fuzzy matching (rapidfuzz)
  - HubSpot deal search with exact and fuzzy matching
  - cross_reference_entity dispatcher for person/partner entity types
  - update_hubspot_id method on EntityRepository
  - HubSpot cross-reference wired into backfill (batch-level)
  - HubSpot cross-reference wired into pipeline_async (per-entity)
  - access_token field on HubSpotConfig
affects: [21-entity-attribution, 22-entity-merge, 23-entity-views]

# Tech tracking
tech-stack:
  added: [rapidfuzz]
  patterns: [fuzzy-name-matching-with-threshold, batch-hubspot-enrichment, best-effort-crm-crossref]

key-files:
  created:
    - src/entity/hubspot_xref.py
    - tests/test_hubspot_xref.py
  modified:
    - src/entity/repository.py
    - src/entity/backfill.py
    - src/pipeline_async.py
    - src/config.py
    - pyproject.toml

key-decisions:
  - "Added access_token field to HubSpotConfig (was only env-var based) for cross-reference auth check"
  - "Backfill cross-references in batch after all entities registered (not per-day) to reduce API calls"
  - "Pipeline cross-reference is per-entity with lazy import and full try/except wrapping"
  - "FUZZY_THRESHOLD=80 for token_sort_ratio matching"

patterns-established:
  - "HubSpot cross-reference is best-effort: never crashes pipeline or backfill on failure"
  - "Batch-level API failure detection: first failure flags remaining entities as pending_enrichment"
  - "Lazy import of hubspot_xref to avoid import errors when HubSpot SDK not configured"

requirements-completed: [DISC-05]

# Metrics
duration: 3min
completed: 2026-04-06
---

# Phase 20 Plan 03: HubSpot Cross-Reference Summary

**HubSpot contact/deal search with exact+fuzzy name matching via rapidfuzz, enriching entity records with CRM identifiers in both backfill and pipeline paths**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-06T18:04:38Z
- **Completed:** 2026-04-06T18:08:02Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- HubSpot contact search with exact name match and fuzzy fallback (threshold 80) using rapidfuzz token_sort_ratio
- HubSpot deal search with normalized exact match and fuzzy fallback
- cross_reference_entity dispatches to contact/deal search based on entity type (person->contacts, partner->deals+contacts)
- EntityRepository.update_hubspot_id merges HubSpot metadata into entity records
- Backfill cross-references new entities in batch with API failure detection and pending_enrichment flagging
- Pipeline cross-references each newly registered entity inline (best-effort)
- 16 new tests, all 601 tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Add rapidfuzz dependency and EntityRepository.update_hubspot_id** - `3f539d5` (feat)
2. **Task 2 RED: Failing tests for HubSpot cross-reference** - `9f30624` (test)
3. **Task 2 GREEN: HubSpot cross-reference module and pipeline wiring** - `26e05f4` (feat)

## Files Created/Modified
- `src/entity/hubspot_xref.py` - Contact/deal search with exact+fuzzy matching, cross_reference_entity dispatcher
- `src/entity/repository.py` - Added update_hubspot_id method for HubSpot enrichment
- `src/entity/backfill.py` - Batch-level HubSpot cross-reference after entity registration
- `src/pipeline_async.py` - Per-entity HubSpot cross-reference in ongoing discovery
- `src/config.py` - Added access_token field to HubSpotConfig
- `pyproject.toml` - Added rapidfuzz>=3.0,<4.0 dependency
- `tests/test_hubspot_xref.py` - 16 tests for contact/deal search and cross-reference

## Decisions Made
- Added `access_token` field to HubSpotConfig with default "" -- existing config uses env vars via build_hubspot_client(), but cross-reference needs a config-level check to skip gracefully when no token is set
- Backfill uses batch-level cross-reference (accumulate new entities per batch, then cross-reference all at once) to avoid per-day HubSpot API calls
- Pipeline uses per-entity cross-reference with lazy import and full try/except wrapping (enrichment is optional)
- FUZZY_THRESHOLD=80 for token_sort_ratio -- high enough to avoid false matches, low enough to catch abbreviations

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added access_token field to HubSpotConfig**
- **Found during:** Task 1
- **Issue:** Plan references config.hubspot.access_token but HubSpotConfig had no such field (existing code used env vars only)
- **Fix:** Added `access_token: str = ""` to HubSpotConfig with extra="forbid" compatibility
- **Files modified:** src/config.py
- **Verification:** All tests pass, field accessible via config object
- **Committed in:** 3f539d5 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Necessary addition for cross-reference auth check. No scope creep.

## Issues Encountered
None

## User Setup Required
None - HubSpot cross-reference activates automatically when hubspot.access_token is configured. Without it, cross-reference is silently skipped.

## Next Phase Readiness
- Entity registry now enriched with HubSpot contact/deal identifiers
- Entities without matches flagged as pending_enrichment for future retry
- Ready for Phase 21 (Entity Attribution) with full CRM context
- Phase 20 (Entity Discovery & Backfill) is now complete

## Self-Check: PASSED

All 7 files verified on disk. All 3 task commits (3f539d5, 9f30624, 26e05f4) verified in git log.

---
*Phase: 20-entity-discovery-backfill*
*Completed: 2026-04-06*
