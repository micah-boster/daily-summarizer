---
phase: 04-temporal-roll-ups
status: passed
verified: "2026-04-03"
score: 4/4
---

# Phase 4: Temporal Roll-Ups - Verification

## Phase Goal
Users can review weekly and monthly intelligence that traces threads across days rather than just concatenating summaries.

## Success Criteria Verification

### 1. Weekly roll-up groups related items into threads
**Status:** PASSED
- `WeeklyThread` model traces entries across days with `progression` narrative arc
- `_build_thread_detection_prompt` instructs Claude to link items that "genuinely refer to the same topic"
- Prompt explicitly prohibits concatenation: "Only link items that genuinely refer to the same topic"
- Thread entries carry date + category + content for cross-day tracing
- `tests/test_weekly.py::TestParseWeeklyResponse` validates thread parsing from Claude response

### 2. Weekly identifies 3-5 most significant threads with progression
**Status:** PASSED
- Prompt requests "3-5 most significant" threads
- `WeeklyThread.significance` field with "high"/"medium" values
- `WeeklyThread.progression` captures narrative arc (e.g., "raised -> explored -> decided")
- Significance-based ranking enforced in prompt: "Rank threads by SIGNIFICANCE, not frequency"

### 3. Monthly synthesizes into thematic arcs, not longer list
**Status:** PASSED
- `ThematicArc` model with title, description, trajectory, weeks_active, key_moments
- `MONTHLY_NARRATIVE_PROMPT` explicitly says "This is NOT a longer weekly. Do NOT chronologically list weeks."
- Prompt enforces analytical third-person tone
- `MonthlyMetrics` provides light context (total meetings, hours, decisions, top attendees)
- `tests/test_monthly.py::TestParseMonthlyResponse` validates arc/shift/risk parsing

### 4. Roll-up structure consistent with daily structure
**Status:** PASSED
- Same categories used as tags on threads: decision, commitment, substance
- `ThreadEntry.category` maps directly to daily synthesis categories
- Weekly and monthly use same Jinja2 environment and custom filters as daily
- Evidence-only validation (`validate_evidence_only`) applied to both weekly and monthly output

## Requirement Coverage

| Requirement | Status | Evidence |
|-------------|--------|----------|
| TEMP-01 (weekly from dailies) | Complete | `src/synthesis/weekly.py`, `templates/weekly.md.j2`, CLI `weekly` subcommand |
| TEMP-02 (monthly with themes) | Complete | `src/synthesis/monthly.py`, `templates/monthly.md.j2`, CLI `monthly` subcommand |

## Test Results

128 tests pass (99 existing + 18 weekly + 11 monthly).

## Artifacts Created

| File | Purpose |
|------|---------|
| `src/models/rollups.py` | Pydantic models: ThreadEntry, WeeklyThread, WeeklySynthesis, ThematicArc, MonthlyMetrics, MonthlySynthesis |
| `src/synthesis/weekly.py` | Weekly pipeline: daily reader, thread detection, Claude synthesis |
| `src/synthesis/monthly.py` | Monthly pipeline: weekly reader, metrics aggregation, narrative synthesis |
| `src/synthesis/prompts.py` | Added WEEKLY_THREAD_DETECTION_PROMPT and MONTHLY_NARRATIVE_PROMPT |
| `src/output/writer.py` | Added write_weekly_summary, write_monthly_summary, insert_weekly_backlinks, format_date, format_month_name |
| `src/main.py` | Refactored to subparsers: daily/weekly/monthly |
| `templates/weekly.md.j2` | Thread-based weekly template |
| `templates/monthly.md.j2` | Thematic arc monthly template |
| `config/config.yaml` | Added weekly/monthly token settings |
| `tests/test_weekly.py` | 18 weekly tests |
| `tests/test_monthly.py` | 11 monthly tests |
