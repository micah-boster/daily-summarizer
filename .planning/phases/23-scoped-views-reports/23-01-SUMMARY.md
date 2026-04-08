---
phase: 23-scoped-views-reports
plan: 01
status: complete
duration: 5min
started: 2026-04-08
completed: 2026-04-08
tasks_completed: 2
tasks_total: 2
---

# Plan 23-01 Summary: Entity Views + Enriched CLI

## What Was Built

Created `src/entity/views.py` module providing:
- **score_significance()**: Rule-based scoring (decisions=3.0, commitments=2.5, substance=1.0) with recency bonus and confidence multiplier
- **get_entity_scoped_view()**: Assembles EntityScopedView with open commitments, top-5 highlights, and date-grouped activity
- **get_enriched_entity_list()**: Returns entities with mention_count, commitment_count, last_active_date; supports sort by active/mentions/name
- **generate_entity_report()**: Jinja2-based report generation (used by Plan 02)

Extended `src/entity/repository.py` with:
- **get_entity_mentions_in_range()**: Date-filtered mention query with merged entity aggregation
- **get_entity_stats()**: Aggregate stats (mention count, commitment count, last-active date) including merged entities

Updated `src/entity/cli.py`:
- `entity show` now displays scoped activity view with --from/--to/--all flags
- `entity list` now shows enriched columns (mentions, commitments, last active) with --sort flag

## Key Files

| File | Action | Lines |
|------|--------|-------|
| src/entity/views.py | Created | ~220 |
| src/entity/repository.py | Modified | +55 |
| src/entity/cli.py | Modified | +40, -20 |
| tests/test_entity_views.py | Created | ~200 |

## Test Results

23 new tests, 55 total entity tests passing.

## Decisions Made

- Significance scoring: decisions=3.0, commitments=2.5, substance=1.0. Recency: +1.0 within 7 days, +0.5 within 14 days. Multiplied by confidence.
- Merged entity aggregation: Views include mentions from entities whose merge_target_id points to the queried entity.
- "Open commitments" = all mentions with source_type='commitment' in the date range.
- Default sort for enriched list: last_active_date descending, breaking ties by name.
