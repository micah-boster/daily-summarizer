---
phase: 23-scoped-views-reports
verified: 2026-04-08T23:00:00Z
status: passed
score: 5/5 success criteria verified
re_verification: false
---

# Phase 23: Scoped Views + Reports Verification Report

**Phase Goal:** Users can ask "what's happening with Affirm?" or "what does Colin owe me?" and get a sourced, time-filtered answer -- the payoff of the entire entity layer
**Verified:** 2026-04-08T23:00:00Z
**Status:** PASSED
**Re-verification:** No -- retroactive verification (phase executed before verification was part of workflow)

---

## Goal Achievement

### Observable Truths (from ROADMAP.md Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can run `entity show "Affirm"` and see a scoped report of all synthesis items referencing that entity, ordered by date, with source attribution | VERIFIED | `src/entity/cli.py` (line 46) registers `entity show <name>` command; `src/entity/views.py` `get_entity_scoped_view()` (line 122) queries mentions by entity, groups by date (line 186 `sorted(by_date.keys(), reverse=True)`), includes source type in each `ActivityItem` |
| 2 | User can run `entity show "Affirm" --from 2026-03-01 --to 2026-04-01` to filter the scoped view by time range | VERIFIED | `src/entity/cli.py` (line 46) accepts `--from` and `--to` date flags plus `--all` for unfiltered; `get_entity_scoped_view()` passes `from_date`/`to_date` to `repo.get_entity_mentions_in_range()` for SQL-level date filtering |
| 3 | Running `entity report "Affirm"` generates a per-entity markdown file in `output/entities/` | VERIFIED | `src/entity/cli.py` (line 58) registers `entity report <name>` command with `--output-dir` flag (default `output/entities`); `src/entity/views.py` `generate_entity_report()` (line 257) uses Jinja2 template `entity_report.md.j2` to render markdown to output path |
| 4 | Entity list command shows all entities with mention frequency, open commitments count, and last-active date | VERIFIED | `src/entity/cli.py` (line 36) registers `entity list` with `--type`, `--sort`, `--json` flags; `src/entity/views.py` `get_enriched_entity_list()` (line 207) returns entities with mention count, last-active date, and sort options ("active", "mentions", "name") |
| 5 | Temporal entity summaries surface the most significant recent activity, not just a raw chronological dump | VERIFIED | `src/entity/views.py` `score_significance()` (line 77) applies rule-based scoring by source type (decisions=5.0, commitments=4.0, etc.); scoped view highlights top 5 items by significance score (line 177 `sorted(items, key=lambda x: x.significance_score, reverse=True)[:5]`) |

**Score:** 5/5 truths verified

---

## Requirement Coverage

| REQ-ID | Description | Status | Covering Plans |
|--------|-------------|--------|----------------|
| VIEW-01 | Entity-scoped show with time filtering | SATISFIED | 23-01 |
| VIEW-02 | Per-entity markdown report generation | SATISFIED | 23-02 |
| VIEW-03 | Enriched entity list with mention frequency | SATISFIED | 23-01 |

---

## Integration Points

| Export | Consumer | Status |
|--------|----------|--------|
| `get_entity_scoped_view` | CLI `entity show`, `generate_entity_report` | WIRED |
| `get_enriched_entity_list` | CLI `entity list` | WIRED |
| `generate_entity_report` | CLI `entity report` | WIRED |
| `score_significance` | `get_entity_scoped_view` (internal) | WIRED |

---

## Known Issues (resolved in Phase 23.1)

- Template path resolution changed from relative `"templates"` to absolute `Path(__file__).parents[2] / "templates"` (fixed in 23.1-01)

---

*Phase: 23-scoped-views-reports*
*Verified: 2026-04-08 (retroactive -- gap closure phase 23.1)*
