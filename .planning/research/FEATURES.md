# Feature Research: v2.0 -- Entity Layer

**Domain:** Work intelligence pipeline -- entity registry, discovery, merge/resolution, attribution, scoped views, initiative tracking
**Researched:** 2026-04-05
**Confidence:** HIGH (existing pipeline well-understood, entity resolution patterns well-established, LLM entity extraction proven with current structured output infrastructure)

## Feature Landscape

### Table Stakes (Users Expect These)

Features without which "entity-aware intelligence" feels broken or useless.

| Feature | Why Expected | Complexity | Depends On (Existing) |
|---------|--------------|------------|----------------------|
| Entity registry (SQLite) for partners and people | Cannot attribute, query, or merge entities without persistent storage. Foundation for everything. | MEDIUM | First SQLite usage in project. Schema: entities table + entity_mentions junction table. Pydantic models for Entity, EntityMention. |
| Entity discovery from existing summaries (backfill) | 6+ months of daily summaries already exist. Without backfill, entity layer starts empty and feels useless until weeks of new runs accumulate. | MEDIUM-HIGH | Existing `DailySynthesisOutput` structured outputs. Async pipeline patterns from v1.5.1. LLM extracts entities from historical synthesis text. |
| Ongoing entity discovery from new pipeline runs | New synthesis runs must tag entities automatically or the system falls out of date after day one. | MEDIUM | Extends current `DailySynthesisOutput` Pydantic model with entity reference fields. Runs as post-synthesis step. |
| Entity attribution in synthesis output | Synthesis items must reference entities so scoped views can filter. Without attribution, entities exist in a registry but are disconnected from intelligence. | MEDIUM | Extends `SynthesisItem`, `CommitmentRow`, `ExtractionItemOutput` with `entity_refs: list[str]` fields. Prompt engineering to instruct Claude to tag items with known entity names. |
| Entity merge proposals with user confirmation | Names fragment across sources ("Colin" in meetings, "Colin R." in Slack, "colin@partner.com" in HubSpot). Without merge, same person appears as 3 entities. | MEDIUM | Entity registry must exist. Similarity detection (string distance + LLM verification). CLI prompt for confirm/reject/skip. |
| Scoped entity views (CLI query) | The core value proposition: "what's happening with Affirm?" Without query, the entity layer has no user-facing surface. | LOW-MEDIUM | Entity registry + attribution. CLI command `python -m src.main entity "Affirm"` that queries entity_mentions, aggregates synthesis items, prints markdown. |

### Differentiators (Competitive Advantage)

Features that make this entity layer meaningfully better than a naive tag-and-search.

| Feature | Value Proposition | Complexity | Depends On (Existing) |
|---------|-------------------|------------|----------------------|
| Scoped entity markdown reports | Generated markdown file per entity covering configurable time range. Portable, shareable, reviewable. Goes beyond CLI output to persistent artifact. | LOW | Scoped CLI views (same query, different output target). Uses existing `output/writer.py` patterns. |
| Initiative tracking as entity type | "Q2 launch" or "MSA renegotiation" -- cross-cutting themes that span multiple partners and people. Most work intelligence tools only track people and orgs. | MEDIUM | Partners + people must be stable first. Initiatives have different lifecycle (start/end dates, status). Schema extension. |
| Confidence scoring on entity mentions | Not all mentions are equal. "Colin will send the contract" (high confidence, direct attribution) vs "the team discussed contract terms" (low confidence, indirect). | LOW | Extends entity_mentions with `confidence: float` field. LLM provides confidence during extraction. Scoped views can filter by confidence threshold. |
| Temporal entity activity summaries | Roll-up entity activity over weeks/months: "Affirm: 12 mentions across 8 days, 3 open commitments, last active April 3." | MEDIUM | Entity registry + attribution + existing weekly/monthly roll-up infrastructure. Piggybacks on `src/synthesis/weekly.py` and `monthly.py`. |
| HubSpot entity cross-reference | Auto-link discovered entities to HubSpot contacts/deals when names match. Enriches entity records with CRM context without manual mapping. | LOW-MEDIUM | HubSpot ingestion already fetches contacts/deals with names. String matching between entity names and HubSpot contact/deal names. |
| Alias management (explicit) | User can manually add aliases ("CR" = "Colin R." = "Colin Roberts") beyond what merge proposals catch. Power-user feature for known abbreviations. | LOW | Entity registry. Simple CLI: `entity alias add "CR" --target "Colin Roberts"`. Updates aliases JSON array on entity record. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Full NER model (spaCy/BERT) for entity extraction | "Use a proper NER pipeline for accuracy" | Adds heavy dependencies (spaCy models, torch). Claude already performs zero-shot NER extremely well via structured outputs -- it is the extraction engine. Adding a second NER system creates conflicting results, dual maintenance, and complexity for marginal accuracy gain at this scale (50-100 items/day). | Use Claude structured outputs for entity extraction. The LLM already reads the full context and can extract people/org names with high accuracy. No second model needed. |
| Automatic entity merge (no confirmation) | "Just merge obvious duplicates automatically" | False merges are catastrophic and irreversible in practice. "Chris" could be Chris Chen or Chris Park. "Amazon" could be AWS or Amazon Retail. Auto-merge destroys data integrity. | Semi-automated: system proposes merges, user confirms. High-confidence merges (email match) can be auto-approved with a config flag, but default to manual confirmation. |
| Knowledge graph / relationship mapping | "Build a graph of who knows whom, which partners are connected" | Over-engineered for a personal intelligence tool. Graph databases (Neo4j), graph visualization, relationship inference -- all add massive complexity. The user's actual question is "what's happening with X?" not "show me the social graph." | Flat entity registry with mentions. Relationships are implicit (entities co-mentioned in same synthesis item). If graph is ever needed, the mention data supports future extraction. |
| Real-time entity notifications | "Alert me when a key entity is mentioned in Slack" | Requires always-on Slack listener, push notification infrastructure, real-time event processing. Contradicts the batch-pipeline architecture. Massive scope increase. | Entity scoped views after daily pipeline run. If urgent, the user is already in Slack and sees it live. The pipeline provides structured retrospective intelligence, not real-time alerts. |
| Entity-level sentiment tracking | "Is the Affirm relationship getting better or worse?" | Personnel framing constraint from PROJECT.md: "evidence only, never evaluative language." Sentiment scoring violates this core constraint. Subjective, unreliable from text alone, and potentially harmful if used in business decisions. | Surface activity frequency and commitment status. "3 meetings this week, 2 open commitments" is objective. Let the user form their own assessment. |
| Embedding-based entity resolution | "Use vector similarity for smarter entity matching" | Requires embedding model, vector storage, adds latency and complexity. At the scale of this system (hundreds of entities, not millions), string similarity + LLM verification is sufficient and simpler. | Levenshtein/Jaro-Winkler distance for candidate generation + LLM for ambiguous cases. Two-tier approach handles the scale perfectly. |

## Feature Dependencies

```
[Entity Registry (SQLite)]
    +--enables--> [Backfill Discovery]
    +--enables--> [Ongoing Discovery]
    +--enables--> [Entity Merge Proposals]
    +--enables--> [Alias Management]

[Backfill Discovery]
    +--populates--> [Entity Registry]
    +--enables--> [Entity Attribution] (entities must exist to reference)

[Ongoing Discovery]
    +--extends--> [Entity Attribution] (discovers new entities from new runs)

[Entity Attribution in Synthesis]
    +--requires--> [Entity Registry] (needs entity list for prompt context)
    +--extends--> [DailySynthesisOutput model] (adds entity_refs fields)
    +--extends--> [Synthesis prompts] (instructions to tag items)
    +--enables--> [Scoped CLI Views]
    +--enables--> [Scoped Markdown Reports]

[Entity Merge Proposals]
    +--requires--> [Entity Registry] (needs entities to compare)
    +--enhances--> [All Scoped Views] (merged entities consolidate results)

[Scoped CLI Views]
    +--requires--> [Entity Attribution] (needs entity_refs to filter)
    +--enables--> [Scoped Markdown Reports] (same query, file output)

[Initiative Tracking]
    +--requires--> [Entity Registry stable] (schema extension)
    +--requires--> [Entity Attribution working] (initiative tagging in synthesis)

[Temporal Entity Summaries]
    +--requires--> [Scoped Views]
    +--extends--> [Weekly/Monthly roll-ups]

[HubSpot Cross-Reference]
    +--requires--> [Entity Registry]
    +--enhances--> [Entity records with CRM data]
```

### Dependency Notes

- **Entity Registry is the absolute foundation.** Every other feature depends on it. Must be first.
- **Backfill before ongoing discovery** because the entity list produced by backfill seeds the prompt context for ongoing discovery. Without backfill, ongoing discovery starts cold with no entity list to reference, producing fragmented names.
- **Attribution requires entity list** because the synthesis prompt needs to know which entities exist to tag items with canonical names. Discovery produces the list, attribution uses it.
- **Merge proposals can run anytime after registry has data** but should run before scoped views are the primary workflow, so views show consolidated entities.
- **Initiative tracking deferred until people/partners stable** because initiatives reference people and partners. Building initiatives on an unstable entity foundation creates orphaned references.

## MVP Definition

### Phase 1: Registry + Backfill Discovery

- [ ] **SQLite entity registry** -- schema design, Pydantic models, CRUD operations. Partners and people entity types. This is the data foundation.
- [ ] **Backfill entity discovery** -- LLM extraction from existing daily synthesis markdown files. Populates registry with historical entities. Async batch processing.
- [ ] **Basic merge detection** -- string similarity (Jaro-Winkler) on entity names to flag likely duplicates during backfill. Store as pending merge proposals.

### Phase 2: Attribution + Ongoing Discovery

- [ ] **Entity attribution in synthesis** -- extend `SynthesisItem`, `CommitmentRow` Pydantic models with `entity_refs` field. Update synthesis prompt to tag items with known entity names from registry.
- [ ] **Ongoing entity discovery** -- post-synthesis step that extracts new entities from each run and adds to registry. Checks for near-matches before creating new entries.
- [ ] **Entity merge CLI** -- `entity merge list` (show proposals), `entity merge accept <id>`, `entity merge reject <id>`. Merging updates all historical references.

### Phase 3: Scoped Views + Initiative Tracking

- [ ] **Scoped CLI views** -- `entity view "Affirm"` or `entity view "Colin"` with time range. Queries entity_mentions, aggregates synthesis items, prints structured markdown.
- [ ] **Scoped markdown reports** -- same query, writes to `output/entities/affirm_2026-04.md`. Configurable time range.
- [ ] **Initiative tracking** -- third entity type with start/end dates, status, linked partners/people. Discovery and attribution support.

### Future Consideration (v2.x+)

- [ ] **Temporal entity summaries in roll-ups** -- defer until weekly/monthly roll-ups incorporate entity data
- [ ] **HubSpot cross-reference** -- defer until entity registry is stable and naming conventions are understood
- [ ] **Confidence scoring on mentions** -- defer until attribution is working and there is real data to calibrate thresholds

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Entity registry (SQLite) | HIGH | MEDIUM | P1 |
| Backfill discovery | HIGH | MEDIUM-HIGH | P1 |
| Entity attribution in synthesis | HIGH | MEDIUM | P1 |
| Ongoing entity discovery | HIGH | MEDIUM | P1 |
| Entity merge proposals + CLI | HIGH | MEDIUM | P1 |
| Scoped CLI views | HIGH | LOW-MEDIUM | P1 |
| Scoped markdown reports | MEDIUM | LOW | P2 |
| Initiative tracking | MEDIUM | MEDIUM | P2 |
| Alias management | LOW | LOW | P2 |
| Confidence scoring | LOW | LOW | P3 |
| Temporal entity summaries | MEDIUM | MEDIUM | P3 |
| HubSpot cross-reference | LOW | LOW-MEDIUM | P3 |

**Priority key:**
- P1: Must have -- core entity layer that delivers the v2.0 value proposition
- P2: Should have -- completes the experience, add once core is stable
- P3: Nice to have -- valuable refinements, defer to v2.x

## Detailed Feature Specifications

### Entity Registry (SQLite)

**What it does:** Persistent storage for entity records with types, aliases, metadata, and mention tracking.

**Schema design:**
```sql
CREATE TABLE entities (
    id TEXT PRIMARY KEY,           -- UUID
    canonical_name TEXT NOT NULL,  -- "Affirm", "Colin Roberts"
    entity_type TEXT NOT NULL,     -- "partner", "person", "initiative"
    aliases TEXT DEFAULT '[]',     -- JSON array: ["Affirm Inc", "Affirm Holdings"]
    metadata TEXT DEFAULT '{}',    -- JSON: {"hubspot_id": "...", "domain": "affirm.com"}
    created_at TEXT NOT NULL,      -- ISO timestamp
    updated_at TEXT NOT NULL,      -- ISO timestamp
    merged_into TEXT,              -- NULL or entity_id if this was merged
    FOREIGN KEY (merged_into) REFERENCES entities(id)
);

CREATE TABLE entity_mentions (
    id TEXT PRIMARY KEY,           -- UUID
    entity_id TEXT NOT NULL,       -- FK to entities
    synthesis_date TEXT NOT NULL,  -- Date of the synthesis (YYYY-MM-DD)
    item_type TEXT NOT NULL,       -- "substance", "decision", "commitment"
    item_content TEXT NOT NULL,    -- The synthesis item text
    source_context TEXT,           -- Attribution text from synthesis
    confidence REAL DEFAULT 1.0,  -- 0.0-1.0 extraction confidence
    created_at TEXT NOT NULL,
    FOREIGN KEY (entity_id) REFERENCES entities(id)
);

CREATE TABLE merge_proposals (
    id TEXT PRIMARY KEY,
    source_entity_id TEXT NOT NULL,
    target_entity_id TEXT NOT NULL,
    similarity_score REAL NOT NULL,
    reason TEXT,                   -- "name_similarity", "email_match", "llm_proposed"
    status TEXT DEFAULT 'pending', -- "pending", "accepted", "rejected"
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    FOREIGN KEY (source_entity_id) REFERENCES entities(id),
    FOREIGN KEY (target_entity_id) REFERENCES entities(id)
);

CREATE INDEX idx_mentions_entity ON entity_mentions(entity_id);
CREATE INDEX idx_mentions_date ON entity_mentions(synthesis_date);
CREATE INDEX idx_entities_type ON entities(entity_type);
CREATE INDEX idx_entities_name ON entities(canonical_name);
CREATE INDEX idx_merge_status ON merge_proposals(status);
```

**Pydantic models:**
```python
class EntityType(StrEnum):
    PARTNER = "partner"
    PERSON = "person"
    INITIATIVE = "initiative"

class Entity(BaseModel):
    id: str
    canonical_name: str
    entity_type: EntityType
    aliases: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    merged_into: str | None = None

class EntityMention(BaseModel):
    id: str
    entity_id: str
    synthesis_date: date
    item_type: str  # "substance", "decision", "commitment"
    item_content: str
    source_context: str | None = None
    confidence: float = 1.0
    created_at: datetime
```

**Why SQLite:** First structured storage in the project. SQLite is zero-config, file-based (matches existing flat-file patterns), supports concurrent reads, and handles the scale (thousands of entities, tens of thousands of mentions) easily. No server process needed.

**Why not a heavier DB:** The system is a personal tool running locally. SQLite handles the volume. PostgreSQL or similar would add deployment complexity for zero benefit.

**Confidence:** HIGH -- SQLite is well-suited, schema is straightforward, Pydantic models follow existing project patterns.

### Backfill Entity Discovery

**What it does:** Scans existing daily synthesis markdown files, extracts entity mentions via LLM, populates the entity registry.

**Approach:**
1. Glob `output/daily/YYYY-MM-DD.md` files (or structured JSON sidecars if available)
2. Batch files into groups of 5-10 (to manage LLM context window and cost)
3. For each batch, send synthesis text to Claude with structured output schema requesting entity extraction
4. LLM returns: `[{name: "Affirm", type: "partner", mentions: [{item: "...", item_type: "decision"}]}, ...]`
5. Deduplicate extracted entities against existing registry (string similarity check)
6. Insert new entities, create entity_mentions records, flag potential merges

**Structured output model for extraction:**
```python
class ExtractedEntity(BaseModel):
    name: str
    entity_type: str  # "partner" or "person"
    mentions: list[str]  # synthesis item texts where entity appears

class EntityExtractionOutput(BaseModel):
    reasoning: str = ""
    entities: list[ExtractedEntity]
```

**Scale estimate:** ~180 daily files (6 months). At 5 per batch = 36 LLM calls. At ~3s each = ~2 minutes total. Cost: ~$2-5 with Sonnet.

**Confidence:** HIGH -- LLM entity extraction from structured text is a solved problem. The synthesis output is already well-structured (sections, bullet points), making extraction reliable.

### Entity Attribution in Synthesis

**What it does:** Extends existing synthesis pipeline so each output item is tagged with entity references.

**Model changes:**
```python
# Extend existing SynthesisItem
class SynthesisItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str
    entity_refs: list[str] = Field(default_factory=list)  # Canonical entity names

# Extend existing CommitmentRow
class CommitmentRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    who: str
    what: str
    by_when: str
    source: str
    entity_refs: list[str] = Field(default_factory=list)
```

**Prompt engineering:** The synthesis prompt receives a list of known entity canonical names from the registry. Claude is instructed to tag each synthesis item with the entity names that appear or are referenced. The structured output schema enforces the `entity_refs` field.

**Why not post-hoc tagging:** Tagging during synthesis is more accurate because Claude has full context of the source material. Post-hoc tagging from the synthesis text alone loses source context.

**Confidence:** HIGH -- extends the existing structured output pattern. Adding a list field to Pydantic models is trivial. Prompt update is the main work.

### Ongoing Entity Discovery

**What it does:** After each daily synthesis, checks for entities mentioned in the output that are not yet in the registry.

**Approach:**
1. After synthesis completes, collect all `entity_refs` from the output
2. For each ref, check registry: exact match or alias match?
3. For unmatched refs, check near-matches (Jaro-Winkler > 0.85)
4. If near-match found: create merge proposal (do not auto-merge)
5. If no match: create new entity record with type inferred from context

**Type inference heuristic:**
- Name appears in `CommitmentRow.who` -> likely "person"
- Name appears with org-related context ("deal with X", "X's contract") -> likely "partner"
- LLM can classify when heuristics are ambiguous

**Confidence:** HIGH -- straightforward extension of backfill logic, running on a single day instead of batch.

### Entity Merge Proposals

**What it does:** Detects likely-duplicate entities and presents them for user resolution via CLI.

**Detection methods (ranked by confidence):**
1. **Email domain match:** colin@affirm.com -> link person "Colin" to partner "Affirm" (HIGH confidence)
2. **Substring match:** "Colin R." contains "Colin" (MEDIUM confidence, needs confirmation)
3. **Jaro-Winkler similarity > 0.85:** "Colin Roberts" vs "Colin Robers" (MEDIUM confidence)
4. **LLM verification for ambiguous cases:** Send candidate pairs to Claude: "Are these the same entity?" (LOW-MEDIUM confidence, used as tiebreaker)

**CLI interface:**
```
$ python -m src.main entity merge list
Pending merge proposals:
  [1] "Colin" + "Colin R." (score: 0.87, reason: name_similarity) -> MERGE / SKIP / REJECT
  [2] "Affirm" + "Affirm Inc" (score: 0.91, reason: name_similarity) -> MERGE / SKIP / REJECT

$ python -m src.main entity merge accept 1
Merged "Colin" into "Colin R." -> canonical: "Colin R."
Updated 14 historical mentions.

$ python -m src.main entity merge reject 2
Rejected. "Affirm" and "Affirm Inc" will remain separate.
```

**Merge mechanics:** When merging A into B:
1. Update A.merged_into = B.id
2. Move all entity_mentions from A to B
3. Add A's canonical_name to B's aliases
4. A remains in DB (soft delete via merged_into) for audit trail

**Confidence:** HIGH -- merge/dedup patterns are well-established. The user-confirmation model avoids the catastrophic false-merge anti-pattern.

### Scoped Entity Views (CLI)

**What it does:** Query command that shows all intelligence related to a specific entity over a time range.

**CLI interface:**
```
$ python -m src.main entity view "Affirm"
$ python -m src.main entity view "Affirm" --since 2026-03-01 --until 2026-04-05
$ python -m src.main entity view "Colin" --type commitments
```

**Output format (printed to terminal):**
```markdown
# Entity Report: Affirm (partner)
Aliases: Affirm Inc, Affirm Holdings
Period: 2026-03-01 to 2026-04-05
Activity: 23 mentions across 12 days

## Recent Substance
- [2026-04-03] Contract terms for Q3 renewal discussed in detail (per weekly sync)
- [2026-04-01] Affirm requesting expanded API scope for payment processing (per Slack #partnerships)

## Decisions
- [2026-03-28] Affirm MSA renewal approved at existing terms (per exec sync)

## Open Commitments
- Colin to send revised pricing sheet by 2026-04-10 (per weekly sync, 2026-04-03)
```

**Query implementation:** SQL query on entity_mentions joining entities, filtered by entity_id (resolved via name/alias lookup), date range, and optionally item_type. Group by date, format as markdown.

**Confidence:** HIGH -- standard SQL query + markdown formatting. Follows existing output patterns.

### Initiative Tracking

**What it does:** Third entity type representing cross-cutting work themes (e.g., "Q2 Launch", "MSA Renegotiation").

**Schema extension:**
```python
class Initiative(Entity):
    """Extends base entity with initiative-specific fields."""
    status: str = "active"  # "active", "completed", "paused", "cancelled"
    start_date: date | None = None
    target_date: date | None = None
    linked_entities: list[str] = Field(default_factory=list)  # partner/people entity IDs
```

**Why defer until people/partners stable:** Initiatives reference people ("who owns it") and partners ("who is it about"). If the people/partner entity layer is still churning (frequent merges, schema changes), initiatives built on top will be fragile.

**Discovery:** Initiatives are harder to auto-discover than people/partners because they are conceptual, not named entities. Likely approach: user creates initiatives manually (`entity add --type initiative "Q2 Launch"`), and the system tags mentions during synthesis. LLM-assisted discovery can suggest initiatives ("these 5 mentions seem related to a common theme").

**Confidence:** MEDIUM -- the concept is clear but discovery heuristics need experimentation. Manual creation with LLM-assisted tagging is the pragmatic path.

## Competitor/Reference Analysis

| Capability | Capacities (PKM) | Notion Databases | HubSpot CRM | Our Approach |
|-----------|-------------------|------------------|-------------|--------------|
| Entity types | Flexible object types | Freeform databases | Contacts, companies, deals | Three types: partner, person, initiative. Intentionally constrained. |
| Entity discovery | Manual creation only | Manual creation only | Manual + form capture | Semi-automated: LLM extracts from synthesis, user confirms |
| Merge/dedup | No built-in | Manual | Built-in merge tool | Proposal-based with user confirmation |
| Attribution | Manual tagging/linking | Manual relations | Automatic via CRM activity | Automatic via LLM during synthesis |
| Scoped views | Object-centric pages | Database views + filters | Contact/company timeline | CLI query + markdown reports |
| Initiative tracking | No special support | Possible via databases | Deals as proxy | First-class entity type with lifecycle |

**Key insight:** CRM tools (HubSpot) have sophisticated entity resolution but operate on explicitly entered data. PKM tools (Capacities, Notion) have flexible schemas but no automated discovery. This system's differentiator is **automated entity discovery from passive data ingestion** -- entities emerge from daily work without manual entry.

## Sources

- [Entity Resolution at Scale (Medium, Jan 2026)](https://medium.com/@shereshevsky/entity-resolution-at-scale-deduplication-strategies-for-knowledge-graph-construction-7499a60a97c3) -- MEDIUM confidence, community source but aligns with established patterns
- [Structured Entity Extraction Using LLMs (Simon Willison, Feb 2025)](https://simonwillison.net/2025/Feb/28/llm-schemas/) -- HIGH confidence, demonstrates Pydantic + LLM structured extraction
- [Building with LLMs: Structured Extraction (PyCon 2025)](https://building-with-llms-pycon-2025.readthedocs.io/en/latest/structured-data-extraction.html) -- HIGH confidence, verified patterns for entity extraction with structured outputs
- [NER with LLMs for Conversation Metadata (Medium)](https://medium.com/@grisanti.isidoro/named-entity-recognition-with-llms-extract-conversation-metadata-94d5536178f2) -- MEDIUM confidence, demonstrates LLM NER from conversational text
- [Jaro-Winkler Distance (Wikipedia)](https://en.wikipedia.org/wiki/Jaro%E2%80%93Winkler_distance) -- HIGH confidence, well-established string similarity metric
- [SQLite Documentation](https://sqlite.org/docs.html) -- HIGH confidence, official docs
- Existing codebase analysis: `src/synthesis/models.py`, `src/models/sources.py`, `src/dedup.py`, `src/config.py` -- HIGH confidence, direct code inspection

---
*Feature research for: Work Intelligence Pipeline v2.0 -- Entity Layer*
*Researched: 2026-04-05*
