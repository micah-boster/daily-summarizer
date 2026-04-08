---
phase: 22-merge-split-review
status: passed
verified: 2026-04-08
---

# Phase 22: Merge + Split Review - Verification

## Phase Goal
Users can consolidate fragmented entity references via merge proposals and undo incorrect merges via split -- so scoped views return clean, consolidated results.

## Success Criteria Verification

### 1. System generates merge proposals when name similarity exceeds threshold
**Status:** PASSED

- `generate_proposals()` uses rapidfuzz `token_sort_ratio` with threshold >= 80
- Proposals ranked by score descending
- Full context included: mention counts and source types per entity
- Tests: `test_above_threshold`, `test_includes_mention_context`
- Evidence: `uv run pytest tests/test_merger.py::TestGenerateProposals -v` -- 8 tests pass

### 2. User can review merge proposals via CLI and accept/reject
**Status:** PASSED

- `entity review` CLI subcommand with interactive accept/reject/skip/quit loop
- Rejections persisted as merge_proposals rows with status='rejected'
- Rejected pairs never re-proposed (checked both orderings)
- Tests: `test_excludes_rejected`, `test_checks_both_orderings`
- Evidence: `entity review --limit 5 --type partner` parses correctly

### 3. User can split an incorrectly merged entity
**Status:** PASSED

- `entity split <name>` CLI command reverses a merge
- Restores soft-deleted entity (clears deleted_at, merge_target_id)
- Mentions re-attributed deterministically using stored mention IDs
- Aliases transferred during merge are moved back
- Tests: `test_end_to_end_merge_and_split`, `test_reattributes_mentions`, `test_returns_aliases`
- Evidence: `uv run pytest tests/test_merger.py::TestExecuteSplit -v` -- 5 tests pass

### 4. Merge proposals capped per review session
**Status:** PASSED

- `--limit N` flag on `entity review` (default 10)
- `generate_proposals()` accepts `limit` parameter, caps result list
- Tests: `test_respects_limit`

## Requirement Coverage

| ID | Description | Status | Evidence |
|----|-------------|--------|----------|
| DISC-03 | Merge proposals with CLI review and persistent rejection | PASSED | 22-01-PLAN.md, 22-02-PLAN.md |
| DISC-04 | Split/undo with mention re-attribution | PASSED | 22-02-PLAN.md |

## Test Summary

- 28 merger-specific tests (proposal generation, execution, split)
- 60 entity module tests total
- 651 full test suite -- all passing
- No regressions

## Artifacts Created

| File | Purpose |
|------|---------|
| `src/entity/merger.py` | Proposal generation, merge execution, split reversal |
| `src/entity/repository.py` | Extended with mention/proposal queries, get_by_name_including_deleted |
| `src/entity/cli.py` | `entity review` and `entity split` CLI subcommands |
| `tests/test_merger.py` | 28 TDD tests |
