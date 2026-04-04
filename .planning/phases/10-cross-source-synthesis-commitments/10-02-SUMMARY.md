---
phase: 10-cross-source-synthesis-commitments
plan: 02
subsystem: synthesis
tags: [claude-api, structured-outputs, pydantic, sidecar, commitments]

requires:
  - phase: 10-cross-source-synthesis-commitments
    provides: Enhanced SYNTHESIS_PROMPT with commitments table format (Plan 01)
provides:
  - Structured commitment extraction via Claude structured outputs (extract_commitments)
  - SidecarCommitment model in DailySidecar JSON
  - Pipeline wiring for commitment extraction after synthesis
affects: [output, sidecar]

tech-stack:
  added: []
  patterns:
    - "Second Claude call for structured extraction (narrative first, structured second)"
    - "output_config structured outputs with Pydantic model_json_schema()"
    - "Graceful degradation: extraction failure returns empty list, never blocks pipeline"

key-files:
  created:
    - src/synthesis/commitments.py
  modified:
    - src/sidecar.py
    - src/output/writer.py
    - src/main.py
    - tests/test_sidecar.py

key-decisions:
  - "Second Claude call pattern: narrative synthesis + structured extraction as separate calls"
  - "output_config with fallback to betas header for SDK compatibility"
  - "Graceful degradation: commitment extraction failure never blocks pipeline"

patterns-established:
  - "ConfigDict(extra='forbid') for all Pydantic models used with Claude structured outputs"

requirements-completed:
  - SYNTH-08

duration: 6 min
completed: 2026-04-04
---

# Phase 10 Plan 02: Structured Commitment Extraction and Sidecar Integration Summary

**Second Claude API call using structured outputs extracts commitments as machine-readable who/what/by_when records, integrated into JSON sidecar with backward-compatible schema**

## Performance

- **Duration:** 6 min
- **Started:** 2026-04-04T16:15:00Z
- **Completed:** 2026-04-04T16:21:00Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments
- New commitments.py module with ExtractedCommitment/CommitmentsOutput Pydantic models and Claude structured outputs call
- SidecarCommitment model added to DailySidecar with default_factory=list for backward compatibility
- Pipeline in main.py calls extract_commitments after synthesis and passes results to sidecar writer
- Extraction failure degrades gracefully -- never blocks daily summary generation

## Task Commits

Each task was committed atomically:

1. **Task 1: Create commitment extraction module** - `709fd86` (feat)
2. **Task 2: Wire into sidecar and pipeline** - `0449c20` (feat)
3. **Task 3: Update sidecar tests** - `468634a` (test)

## Files Created/Modified
- `src/synthesis/commitments.py` - NEW: ExtractedCommitment model, COMMITMENT_EXTRACTION_PROMPT, extract_commitments() with structured outputs
- `src/sidecar.py` - Added SidecarCommitment model and commitments array to DailySidecar
- `src/output/writer.py` - Updated write_daily_sidecar to pass extracted_commitments through
- `src/main.py` - Added commitment extraction call after synthesis, passes to sidecar writer
- `tests/test_sidecar.py` - 6 new tests for commitment model, backward compat, pipeline integration

## Decisions Made
- Used output_config with fallback to betas header for SDK version compatibility
- Commitment extraction runs after synthesis on already-synthesized text (cheap, small input)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 10 complete: cross-source dedup and structured commitments fully integrated
- Ready for phase transition

---
*Phase: 10-cross-source-synthesis-commitments*
*Completed: 2026-04-04*
