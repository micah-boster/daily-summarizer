# Project Research Summary

**Project:** Work Intelligence System — Entity Layer (v2.0)
**Domain:** Entity registry, discovery, resolution, attribution, and scoped views for an existing personal work intelligence pipeline
**Researched:** 2026-04-05
**Confidence:** HIGH

## Executive Summary

The v2.0 entity layer is an additive enhancement to an existing, working Python pipeline. The system already ingests 6+ sources (calendar, Gmail, Slack, HubSpot, Notion, transcripts), deduplicates, synthesizes via Claude structured outputs, and writes daily/weekly/monthly markdown reports. The goal is to make named entities — partners, people, and initiatives — first-class citizens so a user can ask "what's happening with Affirm?" and get a coherent, time-filtered view of all related intelligence. The recommended approach treats entity processing as a strict post-synthesis stage: the existing pipeline runs unchanged, and entity operations layer on top via optional fields and a dedicated SQLite registry.

The stack requires only one new dependency: `aiosqlite` for async SQLite access. Everything else — Claude for entity extraction, rapidfuzz for fuzzy matching, Pydantic for models, argparse for CLI, Jinja2 for reports — is already in the project. The architecture adds a single new package (`src/entities/`) with clean boundaries: it reads synthesis output, writes to SQLite, and surfaces results via CLI commands. Critically, the existing `async_pipeline()` wraps the entity stage in graceful degradation — if entity processing fails for any reason, the daily summary still generates.

The most important risk is false entity merges, which corrupt downstream attribution and erode trust in the entire system. Research is unambiguous: false merges are catastrophic, false misses are merely annoying. The correct default is zero auto-merging on fuzzy signals. Only deterministic signals (matching email, Slack user ID, HubSpot contact ID) should trigger automatic merges. All fuzzy matches become proposals requiring user confirmation. The second major risk is pipeline contamination — entity logic must never block the daily summary. Both risks have straightforward mitigations, and the architecture is designed around them from the start.

## Key Findings

### Recommended Stack

The entity layer needs exactly one new package. `aiosqlite` (v0.22.0+) provides async SQLite access compatible with the existing asyncio pipeline. SQLite itself (v3.51.0 on system) handles the scale comfortably: hundreds of entities, tens of thousands of mentions, database size under 20MB even at 3 years of data. No ORM, no server, no migration framework — hand-written SQL with a `schema_version` table via `PRAGMA user_version`.

Entity extraction reuses the existing Claude structured output infrastructure by extending `DailySynthesisOutput` with `entity_names` fields on `SynthesisItem` and `CommitmentRow`. This is a near-zero-cost addition to an existing API call, not a new one. Entity merge uses rapidfuzz (already in deps from v1.5.1) with a two-tier threshold: 0.95+ auto-merges on deterministic signals, 0.85–0.95 proposes for confirmation, below 0.85 stays separate. Scoped views use existing argparse subcommands and Jinja2 templates.

**Core technologies:**
- `sqlite3` + `aiosqlite 0.22.x`: Entity registry storage — zero new dependencies beyond aiosqlite; WAL mode for concurrent pipeline reads
- `anthropic` (existing): Entity extraction via extended structured output schema — no second LLM call, piggybacks on synthesis
- `rapidfuzz` (existing): Fuzzy name matching for merge proposals — already a project dependency from v1.5.1
- `pydantic` (existing): Entity and mention models, config section — consistent with all existing project patterns
- `argparse` (existing): New `entity` CLI subcommand — consistent with existing daily/weekly/monthly/discover subcommands
- `jinja2` (existing): Scoped markdown report generation — same output pattern as daily reports

### Expected Features

See `.planning/research/FEATURES.md` for full specifications with schema, Pydantic models, and CLI interface examples.

**Must have (table stakes):**
- Entity registry (SQLite) for partners and people — without persistent storage, nothing else works
- Backfill entity discovery from existing daily summaries — 6+ months of summaries exist; without backfill the registry starts empty and is useless
- Ongoing entity discovery on new pipeline runs — entity layer must stay current without manual intervention
- Entity attribution in synthesis output — synthesis items must carry entity references for scoped filtering
- Entity merge proposals with CLI confirmation — name fragmentation across sources ("Colin" / "Colin R." / "colin@partner.com") is the norm, not the exception
- Scoped entity CLI views (`entity show "Affirm"`) — this is the core value proposition

**Should have (differentiators):**
- Scoped markdown reports per entity — persistent, shareable artifact vs. ephemeral CLI output
- Initiative tracking as a third entity type — cross-cutting themes that span partners and people; deferred until people/partners are stable
- Confidence scoring on entity mentions — allows filtering by attribution quality
- Alias management (explicit user-defined aliases) — power-user feature for known abbreviations
- Temporal entity activity summaries in weekly/monthly roll-ups

**Defer to v2.x:**
- HubSpot entity cross-reference — enrichment once the entity registry naming conventions are stable
- Embedding-based entity resolution — string similarity + LLM is sufficient at this scale
- Full NER model (spaCy/BERT) — Claude structured outputs already perform LLM-quality NER; a separate model adds cost and inconsistency
- Real-time entity notifications — contradicts the batch pipeline architecture
- Entity-level sentiment tracking — violates the project's "evidence only, never evaluative" constraint

### Architecture Approach

The entity layer follows a strict additive integration pattern. The existing pipeline flow (ingest → normalize → dedup → synthesize → write) is untouched. A new Phase 2.5 inserts after synthesis: `entity_discover()` extracts entity names from structured synthesis output, matches against the SQLite registry, persists mentions, and generates merge proposals. A new `src/entities/` package provides clean component boundaries with no circular imports into existing modules. SQLite is the only new storage class — connection is opened at pipeline start, passed through `PipelineContext`, closed at pipeline end.

**Major components:**
1. `src/entities/registry.py` — SQLite CRUD, alias resolution, merge/split operations; the single source of truth for entity state
2. `src/entities/discoverer.py` — matches entity names from synthesis output against the registry; creates new entities and merge proposals
3. `src/entities/attributor.py` — enriches sidecar JSON with entity references; writes entity_mentions to SQLite
4. `src/entities/views.py` + `cli.py` — scoped query logic and CLI surface (`entity show`, `entity list`, `entity backfill`, `entity review`)
5. `src/entities/db.py` — connection management, WAL mode, versioned schema migrations via `PRAGMA user_version`

### Critical Pitfalls

See `.planning/research/PITFALLS.md` for full analysis with 12 documented pitfalls across critical, moderate, and minor severity levels.

1. **False merges corrupt the system irreversibly** — Default to zero auto-merge on fuzzy signals. Only deterministic identifiers (email, Slack ID, HubSpot ID) trigger auto-merge. Implement split before shipping merge. Design merges as soft pointer links (`merge_target_id`) so splits are a pointer removal, not a data reconstruction.

2. **Entity logic must never block the daily summary** — Wrap the entire entity stage in `try/except` with graceful degradation. All entity fields on existing Pydantic models must be `Optional` with `None` defaults. Test the pipeline with the entity DB deleted, corrupt, and missing — it must still produce a valid daily summary.

3. **LLM entity extraction is non-deterministic by nature** — Normalize all extracted names before registry insertion (lowercase, strip titles/suffixes, standardize format). Use structured output constraints with `source_evidence` fields to catch hallucinations. Validate extraction consistency on 20-30 real historical summaries before building the full backfill pipeline.

4. **SQLite schema must be designed for evolution from day one** — Use `PRAGMA user_version` for migrations, numbered SQL migration files, soft deletes (`is_active`), `merge_target_id` nullable FK on all entity rows, and a separate `entity_aliases` table. The schema will change when initiatives are added; plan for it now.

5. **Merge proposal fatigue will stall the workflow** — Present proposals ranked by confidence, cap at 5-10 per review session, batch similar proposals (all "Colin" variants as one decision), and provide a "reject and never ask again" option that persists to the DB.

## Implications for Roadmap

Based on combined research, the entity layer has a strict dependency chain that dictates phase order. Each phase produces a testable, independently valuable artifact before the next begins.

### Phase 1: Entity Registry Foundation

**Rationale:** The SQLite registry is the absolute prerequisite for every other feature. No discovery, attribution, merge, or view can work without persistent entity storage. This phase has zero integration with the existing pipeline — it is a standalone new module, making it safe to build and validate independently.

**Delivers:** `src/entities/` package with Pydantic models, db connection management (WAL mode on), registry CRUD, and `EntityConfig` section in `src/config.py`. SQLite schema with all 5 tables (entities, entity_aliases, entity_mentions, merge_proposals, entity_relationships). Schema migrations via `PRAGMA user_version`. Soft delete and `merge_target_id` fields baked in from the start.

**Addresses:** Entity registry (P1 table stakes from FEATURES.md)

**Avoids:** Schema-that-cannot-evolve (#4) by building migration infrastructure first; SQLite file locking (#12) by enabling WAL mode on creation; overengineering before validation (#11) by starting with a minimal entity model validated against 20 real summaries.

**Research flag:** Standard patterns — SQLite + Pydantic + versioned migrations is well-documented. No phase research needed.

---

### Phase 2: Entity Discovery + Extraction

**Rationale:** Discovery populates the registry. Without data in the registry, attribution has nothing to tag against and views return nothing. This phase extends existing Pydantic models and the synthesis prompt — all changes are additive (optional fields with defaults) and do not affect existing pipeline behavior.

**Delivers:** Extended `SynthesisItem` and `CommitmentRow` with `entity_names`/`related_entities` fields. Updated synthesis prompt requesting entity extraction. `src/entities/discoverer.py` that matches extracted names against the registry. Name normalization layer. Merge proposal generation logic.

**Addresses:** Ongoing entity discovery (P1), basic merge detection

**Avoids:** LLM extraction brittleness (#3) via normalization layer and prompt engineering validated on 20+ real summaries before full rollout; pipeline contamination (#2) via optional fields only.

**Research flag:** Needs validation — entity extraction prompt engineering should be tested on real historical data before this phase is considered complete. The extraction schema and normalization rules will need iteration based on actual entity names in the corpus.

---

### Phase 3: Pipeline Attribution Integration

**Rationale:** This is where the entity layer joins the live pipeline. Discovery logic from Phase 2 runs as Phase 2.5 in `async_pipeline()`, persisting mentions to SQLite and enriching the sidecar JSON. Requires both registry (Phase 1) and discovery logic (Phase 2) to be stable.

**Delivers:** `src/entities/attributor.py`. Modified `PipelineContext` with `entity_registry: EntityRegistry | None` field. New Phase 2.5 in `async_pipeline()` with try/except graceful degradation. Enriched `DailySidecar` with `entity_mentions` field. End-to-end: daily pipeline run produces entity-tagged sidecar JSON.

**Addresses:** Entity attribution in synthesis (P1), ongoing entity discovery fully wired into the live pipeline

**Avoids:** Pipeline contamination (#2) — the entire entity stage wrapped in try/except; silent attribution degradation (#7) via confidence tracking and junction table storage.

**Research flag:** Standard patterns — async pipeline integration follows existing v1.5.1 patterns (Slack, HubSpot, Notion all use the same optional-stage pattern with graceful degradation).

---

### Phase 4: Backfill + Merge Review CLI

**Rationale:** Backfill populates the registry with 6+ months of historical intelligence — without it, the entity layer has minimal data and scoped views are nearly empty on day one. Merge review is necessary before views become the primary workflow, so queries return consolidated entities rather than fragmented duplicates.

**Delivers:** `src/entities/cli.py` with `backfill` and `review` commands. `entity backfill --from DATE --to DATE` processes historical sidecar JSONs in weekly batches. `entity review` presents merge proposals one at a time with full context (which sources, which synthesis items). `entity merge accept/reject` with persistent rejection storage. Split (undo merge) ships in the same phase as merge.

**Addresses:** Backfill entity discovery (P1), entity merge proposals + CLI (P1)

**Avoids:** Backfill overwhelming volume (#5) via weekly batching with inspection between batches; merge proposal fatigue (#6) via ranked, capped, context-rich review UI; false merges (#1) — split capability ships in the same phase as merge, never merge without split.

**Research flag:** Standard patterns for the CLI mechanics. The backfill batching strategy and cost estimate (~$2-5 for 180 days with Sonnet) are already established in research.

---

### Phase 5: Scoped Views + Reports

**Rationale:** Scoped views are the user-facing payoff of the entire entity layer. They deliberately come last because they require populated data (from backfill, Phase 4) and stable entity attribution (from Phase 3). Shipping a simple `entity show` query during Phase 4 as a validation mechanism is recommended — if the output is not immediately useful, the entity model needs adjustment before Phase 5 investment.

**Delivers:** `src/entities/views.py` with SQL query logic. CLI commands `entity show "Affirm"`, `entity list [--type partner|person]`, `entity commitments [--owner NAME]`. Per-entity markdown reports written to `output/entities/`. Terminal and file output modes using existing Jinja2 patterns.

**Addresses:** Scoped CLI views (P1), scoped markdown reports (P2)

**Avoids:** Overengineering before validation (#11) — the `entity show` query acts as the validation signal: if scoped views are not useful, the entity model needs to change before further investment.

**Research flag:** Standard patterns — SQL query + Jinja2 markdown rendering matches existing daily/weekly output module patterns exactly.

---

### Phase 6: Initiative Tracking

**Rationale:** Initiatives are fundamentally different from people and partners. They lack stable identifiers, have fuzzy semantic boundaries ("Q2 Launch" vs "Spring Release" vs "Product Launch" could all be the same initiative), and require temporal fields (start/end dates, status). Research is explicit: ship people and partners first, then add initiatives as a distinct phase after learning from Phases 1-5.

**Delivers:** Initiative entity type with lifecycle fields (status, start_date, target_date, linked_entities). Schema migration (Phase 1 migration infrastructure makes this safe). User-created initiative workflow (`entity add --type initiative "Q2 Launch"`). LLM-assisted mention detection during synthesis.

**Addresses:** Initiative tracking (P2 from FEATURES.md)

**Avoids:** Initiative entities as a different beast (#8) — treated as a separate effort with its own schema extension, not squeezed into the same model as people/partners.

**Research flag:** Needs research — initiative auto-discovery heuristics are not well-established. The recommended approach (user-created, LLM-assisted tagging) is the pragmatic fallback, but the detection approach for "these mentions seem related to a common initiative" requires a dedicated investigation before planning.

---

### Phase Ordering Rationale

- **Strict dependency chain:** Registry → Discovery → Attribution → Backfill → Views. Each phase depends on the prior and produces something independently testable.
- **Backfill before views as primary workflow:** Views are useless without populated data. Backfill fills 6+ months of historical data to make views immediately valuable.
- **Merge before views as primary workflow:** Fragmented entities in scoped views produce misleading results. Merge review (Phase 4) happens before Phase 5 views become standard.
- **Initiatives last:** They depend on a stable entity foundation and have genuinely different characteristics (semantic boundaries, no stable identifiers) that would complicate earlier phases if included.
- **Pipeline safety throughout every phase:** Each phase adds entity features as optional, gracefully degrading additions to the existing pipeline. The daily summary is never at risk.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2 (Entity Discovery):** Prompt engineering for entity extraction needs validation on 20-30 real historical summaries before the phase plan is finalized. The specific normalization rules for business names in the actual corpus need to be derived empirically.
- **Phase 6 (Initiative Tracking):** Initiative auto-discovery heuristics are not well-established. This phase needs dedicated research before planning begins. User-created initiatives with LLM-assisted tagging is the recommended fallback approach.

Phases with standard patterns (skip research):
- **Phase 1 (Registry):** SQLite + Pydantic + versioned migrations is thoroughly documented; WAL mode and soft-delete patterns are standard.
- **Phase 3 (Attribution Integration):** Follows the exact same optional-stage pattern used in v1.5.1 for Slack, HubSpot, and Notion.
- **Phase 4 (Backfill CLI):** CLI mechanics and batching strategy are straightforward given existing argparse patterns.
- **Phase 5 (Scoped Views):** SQL query + Jinja2 rendering matches existing output module patterns exactly.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Codebase directly inspected; aiosqlite is the only net-new dependency; all other choices reuse existing project packages with confirmed installed versions |
| Features | HIGH | Feature dependencies are clearly mapped; must-haves vs. differentiators vs. anti-features are explicitly reasoned; dependency graph in FEATURES.md is deterministic |
| Architecture | HIGH | Based on direct codebase analysis of all integration points (`pipeline_async.py`, `synthesis/models.py`, `sidecar.py`, `config.py`, `pipeline.py`); build order is dependency-driven with clear testable deliverables per phase |
| Pitfalls | HIGH | Entity resolution pitfalls are well-documented (GDELT research, production system guides); integration-specific pitfalls derived from direct codebase inspection of the actual production code |

**Overall confidence:** HIGH

### Gaps to Address

- **Entity extraction prompt wording:** The exact prompt text for extracting entity names from synthesis output needs iteration against real data. The structured output schema is defined, but prompt instructions will need tuning based on extraction quality on 20+ real historical summaries. Address at the start of Phase 2 before full backfill.

- **Normalization rules for business names:** Name normalization (stripping "Inc", "LLC", "Holdings", handling "Affirm" vs "Affirm Inc") needs a concrete ruleset derived from the actual entity names in the existing corpus — not assumed from general patterns. Address at the start of Phase 2.

- **Backfill cost calibration:** The estimate ($2-5 for 180 days with Sonnet) needs verification against actual sidecar JSON structure and token counts. Run a 5-day backfill pilot at the start of Phase 4 to calibrate before committing to the full corpus.

- **Initiative auto-discovery boundary:** Research concludes that user-created initiatives with LLM-assisted tagging is the pragmatic path, but the exact detection approach for "these mentions seem related to a common initiative" is unresolved. Address during Phase 6 research (before planning).

## Sources

### Primary (HIGH confidence)

- Direct codebase analysis: `src/pipeline_async.py`, `src/synthesis/synthesizer.py`, `src/synthesis/models.py`, `src/models/sources.py`, `src/sidecar.py`, `src/config.py`, `src/pipeline.py`, `src/output/writer.py`, `src/dedup.py`
- [Python sqlite3 docs](https://docs.python.org/3/library/sqlite3.html) — WAL mode, JSON1, schema patterns
- [aiosqlite documentation](https://aiosqlite.omnilib.dev/en/latest/) — async context managers, threading model
- [aiosqlite GitHub](https://github.com/omnilib/aiosqlite) — v0.22.1 (Dec 2025), actively maintained
- [RapidFuzz PyPI](https://pypi.org/project/RapidFuzz/) — v3.14.3, algorithm documentation
- [SQLite documentation](https://sqlite.org/docs.html) — schema design patterns, WAL mode
- [Structured Entity Extraction Using LLMs (Simon Willison, Feb 2025)](https://simonwillison.net/2025/Feb/28/llm-schemas/) — Pydantic + LLM structured extraction patterns
- [Building with LLMs: Structured Extraction (PyCon 2025)](https://building-with-llms-pycon-2025.readthedocs.io/en/latest/structured-data-extraction.html) — verified entity extraction with structured outputs
- `.planning/V2_VISION.md` — entity layer data model and phasing (project-internal)
- `.planning/codebase/ARCHITECTURE.md` — current pipeline architecture (project-internal)

### Secondary (MEDIUM confidence)

- [GDELT: LLM Entity Extraction Hallucination and Brittleness](https://blog.gdeltproject.org/experiments-in-entity-extraction-using-llms-hallucination-how-a-single-apostrophe-can-change-the-results/) — extraction non-determinism patterns and mitigation strategies
- [The Entity Resolution Playbook for Production Systems](https://www.minimalistinnovation.com/post/entity-resolution-orchestration-framework) — merge/split workflow design
- [System Design for Entity Resolution](https://www.sheshbabu.com/posts/system-design-for-entity-resolution/) — schema patterns for entity registry
- [Suckless SQLite Schema Migrations in Python](https://eskerda.com/sqlite-schema-migrations-python/) — version table migration pattern
- [Entity Resolution at Scale (Medium, Jan 2026)](https://medium.com/@shereshevsky/entity-resolution-at-scale-deduplication-strategies-for-knowledge-graph-construction-7499a60a97c3) — general deduplication strategies
- [NER with LLMs for Conversation Metadata (Medium)](https://medium.com/@grisanti.isidoro/named-entity-recognition-with-llms-extract-conversation-metadata-94d5536178f2) — LLM NER from conversational text

### Tertiary (LOW confidence)

- [AWS Bedrock NER patterns](https://aws.amazon.com/blogs/machine-learning/use-zero-shot-large-language-models-on-amazon-bedrock-for-custom-named-entity-recognition/) — zero-shot LLM NER approach validation (approach is sound, prompt design needs iteration)
- [GPT-NER research](https://arxiv.org/abs/2304.10428) — LLM-based NER accuracy benchmarks (validates approach, not specific to Claude)

---
*Research completed: 2026-04-05*
*Ready for roadmap: yes*
