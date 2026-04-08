---
phase: 22-merge-split-review
plan: 02
status: complete
duration: 5min
tasks_completed: 2
tasks_total: 2
requirements: [DISC-03, DISC-04]
---

# Plan 22-02 Summary: Merge Execution + Split/Undo

## What Was Built
Merge execution (soft-delete, mention reassignment, alias transfer) and split reversal with deterministic mention re-attribution. CLI review now merges inline on accept. New `entity split` command.

## Key Files

### Modified
- `src/entity/merger.py` -- Added execute_merge() and execute_split() with deterministic mention tracking via stored mention IDs in proposal reason field
- `src/entity/repository.py` -- Added get_by_name_including_deleted() for split entity lookup
- `src/entity/cli.py` -- Review now calls execute_merge on accept; added `entity split` subcommand
- `tests/test_merger.py` -- Added 11 new tests for merge execution, split reversal, end-to-end integration

## Decisions Made
- Stored source entity's original mention IDs in merge proposal reason field (JSON) for deterministic split reversal -- avoids heuristic re-attribution
- execute_merge uses try/except for alias collision (INSERT OR IGNORE pattern)
- Split fallback for old proposals without JSON reason: match by context_snippet containing source name
- CLI review prints "Merged 'X' into 'Y'" on accept (inline execution, not deferred)

## Test Results
28 merger tests, 60 entity tests total, 651 full suite -- all passing.

## Self-Check: PASSED
- [x] execute_merge soft-deletes source with merge_target_id
- [x] Mentions reassigned from source to target
- [x] Aliases transferred, source name added as alias
- [x] Alias collisions handled gracefully
- [x] execute_split restores entity, clears merge_target_id
- [x] Split re-attributes mentions deterministically using stored IDs
- [x] Transferred aliases moved back on split
- [x] CLI review executes merges inline
- [x] CLI split command works end-to-end
- [x] All 651 tests pass
