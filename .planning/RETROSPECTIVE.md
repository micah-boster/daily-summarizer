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

## Milestone: v2.0 — Entity Layer

**Shipped:** 2026-04-08
**Phases:** 6 | **Plans:** 12

### What Was Built
- SQLite entity registry with 5-table schema, PRAGMA-based migrations, CLI CRUD + alias management
- Entity discovery from synthesis output (Claude structured outputs) with historical backfill from 6 months of sidecars
- HubSpot cross-referencing via rapidfuzz fuzzy name matching
- Entity attribution — every synthesis item tagged with entity references, persisted to SQLite + JSON sidecar
- Merge proposal generation (rapidfuzz), interactive CLI review, reversible split/undo
- Scoped entity views (`entity show`), enriched list (`entity list`), per-entity markdown reports (`entity report`)

### What Worked
- Reusing existing patterns (Pydantic models, structured outputs, CLI subparsers) made each phase faster
- Entity module isolation (src/entity/) kept complexity contained — 2,736 LOC in a single package
- Retroactive summaries + verification backfill in 23.1 cleaned up paperwork debt efficiently
- discuss-phase → plan-phase → execute-phase auto-advance pipeline shipped entire phases in single sessions

### What Was Inefficient
- Phases 12 and 19 were executed before the verification/summary workflow matured — required retroactive paperwork
- Summary frontmatter `requirements` field was consistently missing — had to backfill 12 files in gap closure
- First audit found documentation gaps (missing VERIFICATIONs) that could have been caught by executor agents writing them during execution
- Roadmap plan checkboxes not auto-checked after execution — required manual cleanup of 7 unchecked plans

### Patterns Established
- Entity package pattern: models → migrations → db → repository → CLI, each building on the last
- Graceful degradation pattern: get_connection_from_config returns None, pipeline try/except wraps entity features
- Name normalization: normalize_for_matching as shared utility across discovery, attribution, merge
- Merge pattern: soft-delete with merge_target_id, resolve_name follows pointer

### Key Lessons
1. Executor agents should write VERIFICATION.md as part of phase completion — not left for audits to catch
2. Summary frontmatter requirements field should be mandatory in the summary template
3. Pipeline ordering matters — discovery before attribution is not optional
4. Gap closure phases are lightweight but essential — Phase 23.1 was 1 plan, 4 tasks, fixed 4 real issues

### Cost Observations
- Model mix: ~70% sonnet (executors, verifiers, checkers), ~30% opus (orchestrator, planner)
- Entity milestone completed across Apr 5-8 (4 calendar days)
- Auto-advance pipeline (discuss → plan → execute) reduced manual orchestration significantly

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.0 | 6 | 14 | Initial GSD workflow established |
| v1.5 | 7 | 18 | Multi-source expansion, pipeline decomposition |
| v1.5.1 | 7 | 16 | Milestone audit + gap closure cycle proven |
| v2.0 | 6 | 12 | Entity layer, auto-advance pipeline, retroactive cleanup |

### Cumulative Quality

| Milestone | Tests | Key Metric |
|-----------|-------|------------|
| v1.0 | ~150 | First test suite |
| v1.5 | ~380 | Pipeline orchestration tests added |
| v1.5.1 | 468 | Async tests, config validation, structured output tests |
| v2.0 | 651+ | 14 entity test files, TDD attributor/merger/views |

### Top Lessons (Verified Across Milestones)

1. Requirements must be scoped to verifiable, grep-able artifacts — not vague descriptions
2. TDD (red-green) produces cleaner code than write-then-test, especially for data transformation
3. Milestone audits with 3-source cross-reference catch gaps that phase-level verification misses
4. Executor agents should write VERIFICATION.md + populate summary frontmatter during execution, not after
5. Auto-advance (discuss → plan → execute) is a major throughput multiplier — entire phases in single sessions
