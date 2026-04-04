---
phase: 10-cross-source-synthesis-commitments
plan: 01
subsystem: synthesis
tags: [claude-prompt, deduplication, jinja2, commitments]

requires:
  - phase: 08-hubspot-crm-ingestion
    provides: HubSpot SourceItem ingestion integrated into synthesis pipeline
provides:
  - Enhanced SYNTHESIS_PROMPT with cross-source deduplication rules
  - Commitments table format (Who/What/By When/Source) in prompt and template
  - Reordered daily template with Commitments before Substance
affects: [10-02, output, synthesis]

tech-stack:
  added: []
  patterns:
    - "Cross-source dedup via LLM prompt instructions (conservative merge policy)"
    - "Pipe-delimited table rows as commitment interchange format between synthesizer and writer"

key-files:
  created: []
  modified:
    - src/synthesis/synthesizer.py
    - templates/daily.md.j2
    - src/output/writer.py
    - tests/test_synthesizer.py

key-decisions:
  - "Conservative dedup: uncertain matches stay SEPARATE (two items > one incorrectly merged)"
  - "Commitments rendered as Who/What/By When/Source table, positioned before Substance for visibility"
  - "Pipe-delimited table rows as intermediate format between synthesizer response and template rendering"

patterns-established:
  - "Template backward compatibility: commitment_rows (new) vs split_emdash fallback (legacy)"

requirements-completed:
  - SYNTH-06

duration: 5 min
completed: 2026-04-04
---

# Phase 10 Plan 01: Cross-Source Dedup Rules and Commitments Table Summary

**Enhanced synthesis prompt with cross-source dedup rules and restructured daily template with Commitments table (Who/What/By When/Source) positioned before Substance**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-04T16:10:00Z
- **Completed:** 2026-04-04T16:15:00Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- SYNTHESIS_PROMPT now instructs Claude to consolidate same-topic items across meetings, Slack, Docs, and HubSpot with multi-source attribution
- Conflicting details shown side-by-side with per-source attribution
- Daily template reordered: Commitments table appears after Executive Summary, before Substance
- _parse_synthesis_response handles both table-format and bullet-list commitments

## Task Commits

Each task was committed atomically:

1. **Task 1: Enhance SYNTHESIS_PROMPT with dedup rules and table format** - `3379983` (feat)
2. **Task 2: Reorder daily template with Commitments before Substance** - `f477fb3` (feat)
3. **Task 3: Update synthesizer tests** - `57b85ff` (test)

## Files Created/Modified
- `src/synthesis/synthesizer.py` - Added CROSS-SOURCE DEDUPLICATION rules, Commitments table format in prompt, updated _parse_synthesis_response for table rows
- `templates/daily.md.j2` - Reordered sections, added commitment_rows template variable with fallback
- `src/output/writer.py` - Parse pipe-delimited commitments into structured dicts for template
- `tests/test_synthesizer.py` - 10 new tests for dedup rules and table-format commitment parsing

## Decisions Made
- Conservative dedup policy: uncertain matches stay separate to avoid incorrect merges
- Pipe-delimited table rows as interchange format (simpler than structured JSON between synthesizer and writer)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Prompt and template ready for Plan 10-02 to add structured commitment extraction and sidecar integration
- commitment_rows template variable ready to receive structured data from extraction module

---
*Phase: 10-cross-source-synthesis-commitments*
*Completed: 2026-04-04*
