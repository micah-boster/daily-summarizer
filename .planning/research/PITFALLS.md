# Domain Pitfalls: v2.0 Entity Layer

**Domain:** Adding entity tracking (partners, people, initiatives), resolution, and attribution to an existing work intelligence pipeline
**Researched:** 2026-04-05
**Overall confidence:** HIGH (based on codebase inspection, entity resolution domain research, and verified community sources)

## Critical Pitfalls

Mistakes that cause rewrites, data corruption, or permanent damage to the entity graph.

### Pitfall 1: False Merges Are Catastrophic, False Misses Are Cheap

**What goes wrong:** You tune entity resolution for recall ("find all the duplicates!") and merge "Colin" from a Slack thread about Affirm with "Colin" from a HubSpot deal at a different company. Two real people become one entity. Every attribution that touched either Colin is now wrong. Splitting them later requires re-processing every synthesis item attributed to the merged entity.

**Why it happens:** Entity resolution literature emphasizes precision vs. recall tradeoffs, but most guides discuss it in the context of customer databases where both errors are roughly equal cost. In a personal intelligence system, the costs are wildly asymmetric: a missed merge means you see "Colin" and "Colin Rodriguez" as separate entries -- annoying but the data is still correct. A false merge means the system tells you Colin from Affirm said something that Colin from another partner actually said. That corrupts trust in the entire system.

**Consequences:** False merges cascade through all downstream attributions. If you ask "what's happening with Affirm?" and get items from the wrong Colin, you lose trust in scoped views -- which is the entire point of v2.0. Undoing a false merge requires: identifying the merge was wrong, splitting the entity, reassigning every attribution to the correct entity, and re-generating any scoped reports that included the merged entity.

**Prevention:**
- Default to zero auto-merges. Every fuzzy match is a proposal requiring confirmation. Only deterministic signals (same email address, same Slack user ID, same HubSpot contact ID) can auto-merge.
- Design the entity schema so merges are soft links, not hard deletes. A merge creates a `merge_target_id` pointer -- the original entity row stays intact. This makes splits a simple pointer removal, not a data reconstruction.
- Implement split (undo merge) before implementing merge. If you cannot split, do not ship merge.
- Cap merge proposals: if a backfill batch produces more than 20 proposals, the matching logic is too aggressive. Tighten thresholds.

**Detection:** An entity that appears across unrelated partner contexts is suspect. Track the number of distinct partners associated with each person entity -- most people should be associated with 1-2 partners, not 5.

**Phase recommendation:** Merge logic must include split/undo capability in the same phase. Do not ship merge without split.

---

### Pitfall 2: Contaminating the Working Pipeline with Entity Logic

**What goes wrong:** Entity discovery code gets woven into `synthesizer.py` and `extractor.py`, creating tight coupling between the daily synthesis pipeline (which works and produces value every day) and the new entity layer (which is experimental and evolving). A bug in entity extraction crashes the daily summary. An entity schema migration breaks the pipeline startup.

**Why it happens:** The natural impulse is "while the LLM is summarizing, also tag entities." This is architecturally wrong for two reasons: (1) it makes the synthesis prompt do two jobs, degrading quality at both, and (2) it means entity layer failures can block daily summary generation.

**Consequences:** The v1.x pipeline stops producing daily summaries because of entity layer problems. This is unacceptable -- the daily summary is the validated core value of the system. Every morning without a summary is a regression, not a "known issue."

**Prevention:**
- Entity discovery and attribution must be a **separate pipeline stage** that runs after synthesis. The current `DailySynthesisOutput` already has structured items with `participants` lists and `source` fields -- entity attribution consumes this output without modifying synthesis.
- Wrap the entire entity stage in a try/except with graceful degradation. If entity processing fails, the daily summary still generates. Log the failure, continue.
- If adding entity reference fields to `DailySynthesisOutput` or other models, make them `Optional` with `None` defaults. The synthesis pipeline must be able to run with no entity layer present.
- SQLite connection failures must not propagate to the synthesis stage. Entity DB is optional state, not required state.
- Test the pipeline with the entity DB deleted/missing/corrupted. It must still produce a valid daily summary.

**Detection:** If your PR to add entity features modifies `synthesizer.py`, `extractor.py`, or `prompts.py` in non-additive ways (changing existing logic rather than adding new optional fields), you have coupling. The entity layer should be callable from `pipeline.py` as a new stage, not interleaved into existing stages.

**Phase recommendation:** Phase 1 proves entity discovery works as a standalone stage consuming existing synthesis outputs. Attribution integration with synthesis happens in a later phase, and only through optional output fields.

---

### Pitfall 3: LLM Entity Extraction is Brittle and Non-Deterministic

**What goes wrong:** Claude extracts "Colin" from one summary and "Colin R." from another summary about the same meeting. A minor prompt change causes 30% of entities to be extracted differently across the corpus. The entity registry fills with extraction variants that are not real different entities but artifacts of LLM non-determinism.

**Why it happens:** Research from the GDELT project demonstrates that LLM entity extraction is "massively more brittle and unpredictable than traditional extractors" -- a single apostrophe or typo correction can completely change the list of extracted entities, including entities unrelated to the changed text. This is inherent to transformer-based extraction and cannot be fully eliminated. Additionally, the system ingests from 6+ sources, each with different name formats: Slack display names, calendar attendee emails, HubSpot contact records, transcript speaker labels.

**Consequences:** The entity registry accumulates duplicates that are extraction artifacts. Backfill produces different entity names than ongoing extraction for the same people. The merge proposal queue fills with "Colin" / "Colin R." type proposals that are really extraction consistency failures, not genuine ambiguity.

**Prevention:**
- **Normalize before registry insertion.** Build a name normalization layer between LLM extraction and the entity registry: strip titles (Mr., Dr.), normalize whitespace, lowercase for matching, standardize "First Last" format.
- **Use structured output constraints.** Force the LLM to output entities in a fixed schema: `{"name": str, "type": "person|partner|initiative", "source_evidence": str}`. The `source_evidence` field forces the LLM to cite where in the text it found the entity, catching hallucinations.
- **Cross-reference against the registry.** Before creating a new entity, check if the extracted name fuzzy-matches an existing entity. If it does, link to the existing entity rather than creating a new one. This is the "resolve, don't create" principle.
- **Pin the model version** for entity extraction (the project already pins `claude-sonnet-4-20250514` for synthesis). Use the same pinned version for backfill and ongoing extraction.
- **Validate extraction consistency.** Run extraction twice on 10 sample summaries during development. If entity lists differ by more than 10%, the prompt needs work before building further.

**Detection:** Track new entity creation rate. After the initial backfill, the rate should decline steeply (most entities already exist). If new entity creation stays high, extraction is not converging on consistent names.

**Phase recommendation:** Entity extraction prompt engineering and the normalization layer must be validated on 20-30 real historical summaries before building the full backfill or merge pipeline.

---

### Pitfall 4: SQLite Schema That Cannot Evolve

**What goes wrong:** The initial entity registry schema is designed for people and partners. When initiatives are added later, the schema needs structural changes. But SQLite cannot drop columns, cannot add columns with certain constraints after table creation, and ALTER TABLE is severely limited. Without a migration strategy, you end up with ad-hoc scripts that corrupt data or lose provenance.

**Why it happens:** This project has been flat-files only through v1.5.1. SQLite is the first structured storage. The developer may not have recent experience with SQLite's ALTER TABLE limitations or schema evolution patterns for embedded databases.

**Consequences:** Adding initiative entities requires creating new tables, copying data, and dropping old tables. Without versioned migrations, this is manual and error-prone. Hard-deletes of merged entities lose provenance. Missing audit columns make it impossible to debug entity resolution quality.

**Prevention:**
- **Version from day one.** Use `PRAGMA user_version` to track schema version. Check version on startup, run numbered migrations sequentially. Migrations are SQL files: `001_create_entities.sql`, `002_add_initiatives.sql`.
- **Design for merge from the start.** Every entity table needs: `id` (UUID or integer), `canonical_name`, `entity_type`, `created_at`, `updated_at`, `is_active` (soft delete flag), `merge_target_id` (nullable self-referencing FK).
- **Use junction tables for relationships.** Person-to-partner is a many-to-many (people move between partners). Entity-to-synthesis-item attribution is a junction table, not a foreign key on the synthesis item. This keeps the synthesis output tables unmodified.
- **Store all surface forms as aliases.** A separate `entity_aliases` table with `(entity_id, alias_text, source, discovered_at)`. Merging repoints aliases; splitting removes the repoint. The canonical name is just one of the aliases marked as canonical.
- **Enable `PRAGMA foreign_keys = ON` explicitly** -- SQLite defaults to OFF. Discover referential integrity bugs at development time, not after 6 months of data accumulation.
- **Soft-delete everything.** `is_active = false` instead of `DELETE`. You will need to undo things. Hard deletes make that impossible.

**Detection:** If you find yourself writing `DROP TABLE` or manual data fixup scripts more than once, your migration strategy has failed. If you need to reconstruct entity history and cannot, your audit trail is insufficient.

**Phase recommendation:** Schema design, migration tooling, and the aliases table must be phase 1 deliverables. The schema will change when initiatives are added -- plan for it now.

---

## Moderate Pitfalls

### Pitfall 5: Backfill That Overwhelms or Produces Inconsistent Results

**What goes wrong:** Processing all historical summaries for entity discovery in one batch hits Claude API rate limits, produces hundreds of merge proposals that nobody reviews, or creates an entity registry that looks different from what ongoing processing produces (because the extraction prompt was tuned after backfill).

**Why it happens:** The project has ~365+ days of daily summaries. Processing all of them requires 365+ API calls. At current Claude pricing this is affordable but the volume creates secondary problems: too many merge proposals at once, and entity extraction quality at the start of backfill may differ from the end if you change prompts mid-backfill.

**Prevention:**
- Process in chronological batches (one week at a time). Inspect results after each batch before proceeding.
- Use the same extraction prompt and model version for the entire backfill. Do not change prompts mid-backfill.
- Set a per-batch cap on merge proposals. If one week generates 50+ proposals, something is wrong with matching thresholds.
- Make backfill idempotent: re-running on the same summary should not create duplicate entities. Use `(summary_date, source_id)` as a processed-marker.
- Estimate cost upfront. 365 summaries x ~1000 tokens each x Sonnet pricing = modest cost, but budget it explicitly.
- Process the most recent 4 weeks first (not oldest-first). This validates that entity discovery works on representative data before investing in the full corpus.

**Detection:** Compare entity registry state after week 1 vs. after month 3 of backfill. If early entities get heavily merged or modified, the extraction is not stable and the prompt needs work.

---

### Pitfall 6: Merge Proposal Fatigue

**What goes wrong:** The entity resolution system generates dozens of merge proposals per backfill batch. The user (a busy executive) reviews the first 10, then stops. The queue grows. Unreviewed proposals mean the entity registry diverges from reality. Entity-scoped views return incomplete results because unmerged duplicates split the data.

**Why it happens:** Name variation across 6+ sources is genuinely high. "Colin Rodriguez" in HubSpot, "Colin R." in calendar, "colin" in Slack, "Colin" in transcript -- that is 4 proposals for one person, and this pattern repeats for every person in the system.

**Prevention:**
- **Deterministic merges first, fuzzy merges later.** Phase 1 should only auto-merge on unique identifiers (email, Slack user ID, HubSpot contact ID). These require no review and clean up the majority of obvious duplicates.
- **Rank proposals by confidence.** Present only top 5-10 per review session. The rest wait.
- **"Reject and never ask again" option.** Dismissed proposals must not resurface. Store rejections in the DB.
- **Batch similar proposals.** If "Colin", "Colin R.", and "Colin Rodriguez" are all proposed as merges of the same entity, present them as ONE decision ("Are these all the same person?"), not THREE separate proposals.
- **Track acceptance rate.** If it drops below 50%, the matching logic is too aggressive.
- **CLI workflow, not batch dump.** A command like `gsd entity review` that presents one proposal at a time with full context (which sources, which synthesis items mention each variant).

**Detection:** If the unreviewed proposal queue grows faster than the user processes it, the system is failing. Monitor queue depth as a health metric.

---

### Pitfall 7: Attribution Accuracy Degrades Silently

**What goes wrong:** Entity attribution (tagging synthesis items with entity references) starts accurate but quietly degrades. New name variants appear that the normalizer does not handle. The entity registry grows and fuzzy matching becomes less precise. Nobody checks because there is no feedback loop.

**Prevention:**
- **Build a spot-check command.** `gsd entity audit --sample 10` shows 10 random synthesis items with their entity attributions. The user eyeballs them weekly. This is manual but catches drift.
- **Log confidence scores.** Track attribution confidence distribution over time. A shift toward lower confidence indicates problems.
- **Store attribution as a junction table.** `(synthesis_item_id, entity_id, confidence, attribution_source)`. This is reversible -- you can delete and re-attribute without modifying synthesis outputs.
- **Do not bake entity IDs into markdown output files.** Entity references belong in the SQLite DB and the JSON sidecar, not in the rendered markdown. Markdown is the human-readable output; the DB is the queryable layer.

**Detection:** The most dangerous failure is silent: everything looks fine because nobody is checking. The spot-check habit must be established in phase 1.

---

### Pitfall 8: Initiative Entities Are Fundamentally Different from People/Partners

**What goes wrong:** You design the entity schema around people and partners (proper nouns with stable identities and unique identifiers), then try to fit initiatives ("Q2 Launch", "MSA Renegotiation", "Platform Migration") into the same model. Initiatives have fuzzy boundaries, evolve over time (rename, split, merge), lack stable identifiers, and their names are semantic descriptions rather than proper nouns.

**Why it happens:** The entity type enum (`person | partner | initiative`) suggests they are interchangeable. They are not. People have emails, Slack IDs, and HubSpot contact IDs. Partners have company names and domains. Initiatives have... nothing stable. "Q2 Launch" might be called "Spring Release" in Slack and "Product Launch" in a meeting transcript.

**Prevention:**
- **Ship people + partners first. Add initiatives in a separate phase** after learning from the people/partner experience.
- **Initiatives need temporal boundaries** (start_date, end_date, status) that people/partners do not. The schema must accommodate this difference.
- **Initiative matching requires semantic similarity,** not string comparison. "Q2 Launch" and "Spring Product Release" might be the same initiative. This likely needs LLM-assisted matching, which is more expensive and less deterministic than the deterministic ID matching that works for people/partners.
- **Consider making initiatives user-created** (top-down: the user defines "Q2 Launch" and the system finds mentions) rather than auto-discovered (bottom-up: the system finds initiative-like phrases and proposes them). The user knows their initiatives. Auto-discovering initiative boundaries from text is an unsolved problem.

**Detection:** If initiative entity resolution produces more than 2x the false positive rate of people/partner resolution, the approach needs rethinking.

---

## Minor Pitfalls

### Pitfall 9: The Participants List Is Not Entity-Ready

**What goes wrong:** The existing `participants` field on `ExtractionItem` and `SourceItem` contains raw strings in inconsistent formats: "Colin", "colin@bounce.ai", "Colin R.", "Colin Rodriguez (Affirm)". Building entity attribution directly on these raw strings propagates all source inconsistencies into the entity registry.

**Prevention:**
- Add a normalization step between raw participant strings and entity matching. This is the critical seam.
- **Do not modify the existing `participants` field.** Add a new field (`entity_refs: list[EntityRef] | None = None`) for resolved references. Keep raw participants for backward compatibility and debugging.
- The Slack user resolution (v1.5.1) is a model: Slack user IDs map to display names via API. Extend this pattern: each source has a "resolve raw identifier to canonical form" step.

---

### Pitfall 10: Testing Entity Resolution Requires Real Ambiguity

**What goes wrong:** Unit tests use toy examples ("John" = "John Smith" -> merge). These pass. In production, the system encounters "Alex" who could be Alex from Affirm or Alex from the internal team. The toy tests never covered same-first-name disambiguation because it seemed like an edge case. It is not an edge case -- it is the common case.

**Prevention:**
- **Build a golden test set from real data.** Take 20 actual name pairs from backfill results (10 that should merge, 10 that should NOT merge). Use these as the test corpus.
- **Test the negative cases rigorously.** "Should NOT merge" tests are harder to write but more important than "should merge" tests. False positive prevention is the critical path.
- **Property-based testing for normalization.** Generate random name variants and verify the normalizer is idempotent (`normalize(normalize(x)) == normalize(x)`) and consistent.

---

### Pitfall 11: Overengineering Before Validation

**What goes wrong:** Spending weeks designing a comprehensive entity model (types, subtypes, relationship graphs, temporal validity, confidence chains, provenance tracking, multi-level merge hierarchies) before validating that entity discovery even works reliably on existing summaries.

**Prevention:**
- Start with the minimal entity: `{id, canonical_name, entity_type, aliases[], is_active, created_at}`. Add complexity only when a real use case demands it.
- **Validate discovery on 20 summaries before finalizing the schema.** The discovery results inform what the schema actually needs.
- **Ship the "what's happening with Affirm?" query as early as possible.** This is the feature that validates the entity layer. If scoped views are not useful after phase 1, the entity model needs to change before further investment.

---

### Pitfall 12: SQLite File Locking with Async Pipeline

**What goes wrong:** The pipeline uses `asyncio.to_thread()` for parallel execution (from v1.5.1). Multiple threads reading/writing the SQLite entity DB can hit `database is locked` errors because SQLite's default locking allows only one writer at a time.

**Prevention:**
- Use WAL mode: `PRAGMA journal_mode=WAL`. This allows concurrent reads with a single writer, which is sufficient for this use case.
- Use a single SQLite connection for all entity operations within a pipeline run, not one-per-thread. Pass the connection through `PipelineContext`.
- If using multiple threads, serialize all writes through a single writer function (queue pattern) or use `check_same_thread=False` with careful locking.

---

## Integration-Specific Warnings (Adding to an Existing v1.x Pipeline)

These pitfalls are specific to retrofitting an entity layer onto a working pipeline, not greenfield concerns:

1. **Do not break the daily summary.** The v1.x pipeline produces value every morning. Entity features are additive. If the entity DB is missing, corrupt, or the entity stage throws, the daily summary must still generate. Wrap entity stages in try/except with graceful degradation.

2. **Do not re-run synthesis for backfill.** The existing daily summaries (markdown + JSON sidecar) are the input for entity discovery. Re-running synthesis would be expensive, produce different results (model version drift since the summary was originally generated), and waste validated v1.x outputs. Process the outputs, not the raw sources.

3. **SQLite is a new dependency class.** The project has no database today. Adding SQLite means connection management, file locking concerns, migration tooling, a new class of errors (corrupt DB, missing file), and a new thing to back up. Keep the DB path configurable and include it in any backup strategy.

4. **Existing Pydantic models must not break.** `DailySynthesisOutput`, `MeetingExtractionOutput`, `CommitmentRow`, and `SourceItem` are used in production with `json_schema` constrained decoding. Entity fields added to these models must be `Optional` with `None` defaults and must not use `extra="forbid"` in a way that rejects current outputs.

5. **The participants list is your bridge, not your enemy.** `ExtractionItem.participants` and `SourceItem.participants` already contain name strings from every source. This is the input for entity discovery. Build a resolution layer that consumes their output. Do not modify these upstream models.

6. **The dedup layer and entity layer will interact.** The existing `dedup.py` merges duplicate source items and unions their participants. If entity attribution runs after dedup, it sees the merged participant list. If it runs before dedup, attributions on items that later get merged need to be merged too. Run entity attribution after dedup to avoid this complexity.

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Severity | Mitigation |
|-------------|---------------|----------|------------|
| Schema design | Over-designing before validation (#11) | Critical | Start minimal, validate on 20 summaries first |
| Schema design | No migration strategy (#4) | Critical | `user_version` pragma, numbered SQL files, soft deletes |
| Schema design | SQLite file locking with async (#12) | Minor | WAL mode, single connection per run |
| Entity discovery | LLM extraction brittleness (#3) | Critical | Normalize output, validate consistency on sample, cross-reference registry |
| Entity discovery | Participants list not entity-ready (#9) | Minor | Normalization layer between raw strings and registry |
| Backfill | Overwhelming volume and cost (#5) | Moderate | Weekly batches, idempotent, cost estimate upfront |
| Backfill | Inconsistent results vs. ongoing (#5) | Moderate | Pin model version and prompt for full backfill |
| Merge resolution | False merges are catastrophic (#1) | Critical | Zero auto-merge on fuzzy signals, soft merges, build split first |
| Merge resolution | Proposal fatigue (#6) | Moderate | Deterministic merges first, rank and cap proposals |
| Merge resolution | Testing with real ambiguity (#10) | Minor | Golden test set from real data, test negative cases |
| Attribution | Silent accuracy degradation (#7) | Moderate | Spot-check command, confidence tracking, junction table storage |
| Attribution | Pipeline contamination (#2) | Critical | Separate stage, optional fields, graceful degradation |
| Initiative entities | Different beast than people (#8) | Moderate | Defer to separate phase, consider top-down creation |
| Scoped views | Building before entity quality validated (#11) | Moderate | Ship simple query early as validation mechanism |

## Sources

- [GDELT: LLM Entity Extraction Hallucination and Brittleness](https://blog.gdeltproject.org/experiments-in-entity-extraction-using-llms-hallucination-how-a-single-apostrophe-can-change-the-results/)
- [The Entity Resolution Playbook for Production Systems](https://www.minimalistinnovation.com/post/entity-resolution-orchestration-framework)
- [System Design for Entity Resolution](https://www.sheshbabu.com/posts/system-design-for-entity-resolution/)
- [Handling Nicknames, Abbreviations and Variants in Data Matching](https://dataladder.com/managing-nicknames-abbreviations-variants-in-entity-matching/)
- [Entity Resolution Explained: Techniques and Libraries](https://spotintelligence.com/2024/01/22/entity-resolution/)
- [Data Engineer's Guide to Entity Resolution](https://www.peopledatalabs.com/data-lab/datafication/entity-resolution-guide/)
- [Entity Resolution with Elasticsearch and LLMs](https://www.elastic.co/search-labs/blog/entity-resolution-llm-elasticsearch)
- [Suckless SQLite Schema Migrations in Python](https://eskerda.com/sqlite-schema-migrations-python/)
- [Declarative Schema Migration for SQLite](https://david.rothlis.net/declarative-schema-migration-for-sqlite/)
- [Backfilling Data Guide](https://atlan.com/backfilling-data-guide/)
- [Backfilling Historical Data with Idempotent Pipelines](https://www.ml4devs.com/what-is/backfilling-data/)
- Codebase inspection: `src/pipeline.py`, `src/models/sources.py`, `src/synthesis/models.py`, `src/synthesis/synthesizer.py`, `src/dedup.py`
