---
phase: 18-structured-output-completion
plan: 01
subsystem: synthesis
tags: [pydantic, structured-output, json-schema, claude-api]

# Dependency graph
requires:
  - phase: structured-output (extractor/synthesizer)
    provides: Established json_schema structured output pattern with output_config
provides:
  - WeeklySynthesisOutput and MonthlySynthesisOutput Pydantic models for Claude API
  - _convert_weekly_output and _convert_monthly_output converter functions
  - Structured output calls in weekly.py and monthly.py
affects: [weekly-rendering, monthly-rendering, rollup-pipeline]

# Tech tracking
tech-stack:
  added: []
  patterns: [json_schema structured output for all Claude API call sites]

key-files:
  created: []
  modified:
    - src/synthesis/models.py
    - src/synthesis/weekly.py
    - src/synthesis/monthly.py
    - src/synthesis/prompts.py
    - tests/test_weekly.py
    - tests/test_monthly.py

key-decisions:
  - "Used same day_label string matching as original regex parser for date resolution, with added non-padded day support"
  - "Kept evidence-only validation removal since structured output makes it unnecessary (validator checked free-text output)"

patterns-established:
  - "All Claude API call sites now use json_schema structured output via output_config"

requirements-completed: [STRUCT-01]

# Metrics
duration: 5min
completed: 2026-04-05
---

# Phase 18 Plan 01: Weekly/Monthly Structured Output Migration Summary

**Migrated weekly.py and monthly.py from regex-parsed free-text to json_schema structured outputs with Pydantic model validation**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-05T21:22:35Z
- **Completed:** 2026-04-05T21:27:16Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Added 6 new Pydantic output models (WeeklyThreadEntryOutput, StillOpenItemOutput, WeeklyThreadOutput, WeeklySynthesisOutput, ThematicArcOutput, MonthlySynthesisOutput) with ConfigDict(extra="forbid") and reasoning scratchpads
- Replaced all regex parsers in weekly.py and monthly.py with structured output API calls and type-safe converter functions
- Updated prompts to describe JSON field structure instead of markdown formatting instructions
- All 468 tests pass with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Define Pydantic output models and write converter tests (RED)** - `ad7dc92` (test)
2. **Task 2: Implement structured output calls and converters (GREEN)** - `9d1e35d` (feat)

_Note: TDD tasks have separate test and implementation commits._

## Files Created/Modified
- `src/synthesis/models.py` - Added 6 new structured output models for weekly and monthly pipelines
- `src/synthesis/weekly.py` - Replaced regex parser with structured output call and converter
- `src/synthesis/monthly.py` - Replaced regex parser with structured output call and converter
- `src/synthesis/prompts.py` - Updated weekly and monthly prompts for JSON field descriptions
- `tests/test_weekly.py` - Added TestWeeklyStructuredOutput (3 tests), skipped legacy parser tests
- `tests/test_monthly.py` - Added TestMonthlyStructuredOutput (3 tests), skipped legacy parser tests

## Decisions Made
- Used same day_label string matching approach as original regex parser for date resolution, adding non-padded day format support to handle both "March 30" and "March 03" formats
- Removed evidence-only validation call from synthesize_weekly/monthly since structured output eliminates free-text response parsing where evaluative language was a concern

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed date resolution for non-padded day labels**
- **Found during:** Task 2 (converter implementation)
- **Issue:** strftime %d produces zero-padded days ("01") but Claude may return non-padded ("1"), causing date resolution failures
- **Fix:** Added non-padded day format matching alongside zero-padded in _resolve_date_from_label
- **Files modified:** src/synthesis/weekly.py
- **Verification:** test_convert_weekly_output_to_domain passes with "April 1" matching date(2026, 4, 1)
- **Committed in:** 9d1e35d (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Essential for correctness of date resolution. No scope creep.

## Issues Encountered
None beyond the date padding issue documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All Claude API call sites now use json_schema structured output
- STRUCT-01 requirement is complete
- Ready for Plan 02 (prompt optimization / cleanup if applicable)

---
*Phase: 18-structured-output-completion*
*Completed: 2026-04-05*
