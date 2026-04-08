---
phase: 22-merge-split-review
plan: 01
status: complete
duration: 5min
tasks_completed: 2
tasks_total: 2
---

# Plan 22-01 Summary: Merge Proposal Generation + CLI Review

## What Was Built
Merge proposal generation module using rapidfuzz similarity scoring, with extended repository methods for mention/proposal queries, and interactive CLI review workflow.

## Key Files

### Created
- `src/entity/merger.py` -- score_pair() and generate_proposals() with rapidfuzz token_sort_ratio, MERGE_THRESHOLD=80, same-type filtering, rejection exclusion
- `tests/test_merger.py` -- 17 TDD tests covering scoring, proposal generation, filtering, ranking, repository extensions

### Modified
- `src/entity/repository.py` -- Added get_mention_count(), get_mention_sources(), save_proposal(), get_existing_proposals(), update_proposal_status()
- `src/entity/cli.py` -- Added `entity review` subcommand with --limit and --type flags, interactive accept/reject/skip/quit loop

## Decisions Made
- Proposals assign source/target so most-mentioned entity is always `target_entity` (canonical survivor)
- Both pair orderings (A,B) and (B,A) checked against existing proposals to prevent re-proposals
- EOFError and KeyboardInterrupt caught in CLI input loop for graceful exit
- Review prints "Run merge execution to apply accepted proposals" hint when proposals are accepted

## Test Results
17 new tests, 49 total entity tests, all passing.

## Self-Check: PASSED
- [x] score_pair uses rapidfuzz token_sort_ratio on normalized names
- [x] generate_proposals returns same-type pairs above threshold
- [x] Rejected, merged, deleted entities excluded
- [x] Proposals include mention counts and source types
- [x] CLI review subcommand registered and dispatched
- [x] All tests pass
