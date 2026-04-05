# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.5.1 — Notion + Performance + Reliability

**Shipped:** 2026-04-05
**Phases:** 7 | **Plans:** 16 | **Tasks:** 38

### What Was Built
- Typed Pydantic config model replacing raw dict access across 15 source files
- All 6 Claude API call sites migrated from regex/markdown parsing to json_schema structured outputs
- Notion page and database ingestion completing the 6-source work surface
- Slack batch user resolution, cache retention policy, algorithmic dedup pre-filter
- Async pipeline parallelization — concurrent ingest + parallel extraction with semaphore
- Production bug fixes (beta header 400 errors, notion discovery CLI crash)

### What Worked
- TDD approach on Phase 16 plans produced clean, testable code with no regressions
- Structured output migration pattern (Pydantic model + output_config + model_validate) was highly repeatable — copy from extractor.py to each new call site
- Parallel agent execution for independent plans within a wave — 2 plans complete simultaneously
- Milestone audit caught real gaps (missing Phase 16 verification, notion discovery bug, dead code) that would have rotted

### What Was Inefficient
- Phase 14 (structured output migration) didn't fully scope STRUCT-01 — missed weekly.py and monthly.py, requiring Phase 18 gap closure
- Phase 16 skipped verification during execute-phase, requiring Phase 18.1 to create it retroactively
- Beta header fallback (try/except → fallback function) was a premature compatibility shim that became the bug itself when the API rejected the header

### Patterns Established
- Decimal phase numbering (18.1) for gap closure after milestone audit — clear insertion semantics
- 3-source requirements cross-reference (VERIFICATION + SUMMARY + traceability) catches gaps that single-source checks miss
- Integration checker as part of milestone audit catches cross-phase wiring issues automated tests don't cover

### Key Lessons
1. Scope requirements at the call-site level, not the module level — "migrate extractor.py" is not the same as "migrate all Claude API calls"
2. Always run phase verification during execute-phase, never skip — the cost of retroactive verification is higher
3. Beta/preview API features should have explicit sunset dates in code comments, not silent fallback paths
4. Dead code from refactors (Phase 17 async migration leaving sync code) should be cleaned in the same phase, not deferred

### Cost Observations
- Model mix: ~70% sonnet (executors, verifiers, checkers), ~30% opus (orchestrator, planner)
- Entire milestone completed in a single day (2026-04-05)
- Notable: Gap closure phases (18, 18.1) added ~20% overhead but caught real issues

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.0 | 6 | 14 | Initial GSD workflow established |
| v1.5 | 7 | 18 | Multi-source expansion, pipeline decomposition |
| v1.5.1 | 7 | 16 | Milestone audit + gap closure cycle proven |

### Cumulative Quality

| Milestone | Tests | Key Metric |
|-----------|-------|------------|
| v1.0 | ~150 | First test suite |
| v1.5 | ~380 | Pipeline orchestration tests added |
| v1.5.1 | 468 | Async tests, config validation, structured output tests |

### Top Lessons (Verified Across Milestones)

1. Requirements must be scoped to verifiable, grep-able artifacts — not vague descriptions
2. TDD (red-green) produces cleaner code than write-then-test, especially for data transformation
3. Milestone audits with 3-source cross-reference catch gaps that phase-level verification misses
