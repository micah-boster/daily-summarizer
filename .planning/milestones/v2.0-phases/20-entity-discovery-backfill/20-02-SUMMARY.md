---
phase: 20-entity-discovery-backfill
plan: 02
subsystem: entity
tags: [sqlite, backfill, cli, entity-discovery, pipeline-integration, weekly-batching]
requirements: [DISC-01, DISC-02]

# Dependency graph
requires:
  - phase: 20-entity-discovery-backfill
    plan: 01
    provides: Name normalization (normalizer.py) and entity extraction (discovery.py)
  - phase: 19-entity-registry-foundation
    provides: EntityRepository, Entity models, SQLite schema v1
provides:
  - Backfill orchestrator with weekly batching, checkpoint/resume, progress display
  - Schema v2 migration adding backfill_progress table
  - Extended CLI with entity backfill subcommand
  - Post-synthesis entity discovery wired into async_pipeline
  - EntityConfig with auto_register_threshold and review_threshold
affects: [20-03-hubspot-crossref, 21-entity-attribution, 22-entity-merge]

# Tech tracking
tech-stack:
  added: []
  patterns: [weekly-batch-checkpoint, fire-and-forget-entity-discovery, graceful-degradation-pipeline]

key-files:
  created:
    - src/entity/backfill.py
    - tests/test_backfill.py
  modified:
    - src/entity/migrations.py
    - src/entity/cli.py
    - src/config.py
    - src/pipeline_async.py
    - tests/test_entity_migrations.py

key-decisions:
  - "Sidecar JSON preferred over markdown for backfill content extraction (structured data more reliable)"
  - "Weekly batching with per-batch checkpoint commit for resilience"
  - "Pipeline entity discovery is synchronous (SQLite writes are lightweight, no async needed)"
  - "Person vs partner type detection via name capitalization heuristic in pipeline discovery"

patterns-established:
  - "Backfill progress tracking via dedicated SQLite table with per-day status"
  - "Fire-and-forget entity discovery: wrapped in try/except, pipeline never crashes on entity failure"
  - "Lazy imports for entity modules inside pipeline functions to avoid import errors"

requirements-completed: [DISC-01, DISC-02]

# Metrics
duration: 5min
completed: 2026-04-06
---

# Phase 20 Plan 02: Backfill Pipeline & Ongoing Discovery Summary

**Entity backfill CLI with weekly batching and checkpoint/resume, plus post-synthesis entity discovery wired into async_pipeline**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-06T17:57:57Z
- **Completed:** 2026-04-06T18:02:52Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Backfill orchestrator processes historical summaries in weekly batches with per-batch checkpointing
- Schema v2 migration adds backfill_progress table for tracking processed days (skip on re-run, --force to reprocess)
- CLI: `entity backfill --from YYYY-MM-DD --to YYYY-MM-DD [--force]` with inline progress display
- Post-synthesis entity discovery in async_pipeline collects entity_names from SynthesisItem/CommitmentRow
- EntityConfig extended with auto_register_threshold (0.7) and review_threshold (0.4)
- 16 new backfill tests, all 585 tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Backfill orchestrator, schema migration, and CLI command** - `fa40f34` (feat)
2. **Task 2: Wire ongoing entity discovery into async_pipeline** - `a219f7e` (feat)

## Files Created/Modified
- `src/entity/backfill.py` - Backfill orchestrator with weekly batching, checkpoint/resume, progress display
- `src/entity/migrations.py` - Schema v2 migration adding backfill_progress table
- `src/entity/cli.py` - Extended with backfill subcommand (--from, --to, --force)
- `src/config.py` - EntityConfig with auto_register_threshold and review_threshold fields
- `src/pipeline_async.py` - _discover_and_register_entities post-synthesis step
- `tests/test_backfill.py` - 16 tests for backfill orchestrator
- `tests/test_entity_migrations.py` - Updated for schema v2

## Decisions Made
- Sidecar JSON is preferred over markdown for backfill content extraction (structured tasks/decisions/commitments)
- Weekly batching with per-batch checkpoint commit provides resilience for large date ranges
- Pipeline entity discovery is synchronous (SQLite writes are lightweight, no async overhead needed)
- Person vs partner type detection uses name capitalization heuristic (2-4 capitalized words = person)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated existing migration tests for schema v2**
- **Found during:** Task 1 (after schema migration change)
- **Issue:** test_entity_migrations.py had hardcoded `assert version == 1` and missing backfill_progress from expected tables
- **Fix:** Changed assertions to use SCHEMA_VERSION constant and added backfill_progress to expected tables set
- **Files modified:** tests/test_entity_migrations.py
- **Verification:** All 585 tests pass
- **Committed in:** fa40f34 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Necessary update to existing tests after schema version change. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Backfill can now populate entity registry from historical summaries
- Ongoing pipeline discovery automatically registers new entities
- Ready for HubSpot cross-reference enrichment (Plan 03)
- Entity registry populated for future attribution (Phase 21) and merge (Phase 22)

## Self-Check: PASSED

All 7 files verified on disk. Both task commits (fa40f34, a219f7e) verified in git log.

---
*Phase: 20-entity-discovery-backfill*
*Completed: 2026-04-06*
