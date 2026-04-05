# Architecture: Entity Layer Integration

**Domain:** Entity registry + discovery + attribution + scoped views for work intelligence pipeline
**Researched:** 2026-04-05
**Overall confidence:** HIGH (based on direct codebase analysis + established patterns)

## Recommended Architecture

The entity layer adds four new components that integrate with the existing async pipeline at specific, well-defined points. The core principle is **additive integration** -- the existing pipeline flow (ingest -> normalize -> dedup -> synthesize -> write) remains intact. Entity operations hook in as post-processing steps or extensions to existing models, never replacing current behavior.

```
EXISTING PIPELINE (unchanged)                 NEW ENTITY LAYER
================                              ================

ingest (parallel) ----+
                      |
normalize/dedup ------+
                      |
synthesize -----------+----> entity_discover() ----> SQLite registry
                      |           ^                      |
commit extraction ----+           |                      |
                      |     (names, orgs from            |
output (md + json) ---+      synthesis output)           |
                      |                                  |
                      +----> entity_attribute() ---------+
                      |     (tag sidecar items           |
                      |      with entity IDs)            |
                      |                                  v
                      +----> scoped_views() -------> entity reports
                             (CLI query +            (md per entity)
                              report gen)
```

### Integration Points (Specific Modules)

| Hook Point | Existing Module | What Happens | New Module |
|------------|----------------|--------------|------------|
| After synthesis | `pipeline_async.py` line ~265 (after `synthesize_daily()` returns) | Extract entity mentions from synthesis output | `src/entities/discoverer.py` |
| After commitment extraction | `pipeline_async.py` line ~353 (after `extract_commitments()`) | Tag commitments with entity IDs | `src/entities/attributor.py` |
| After sidecar write | `pipeline_async.py` line ~413 (after `write_daily_sidecar()`) | Write entity-attributed sidecar | `src/entities/attributor.py` |
| New CLI command | `src/main.py` (new `entity` subcommand) | Query and report on entities | `src/entities/views.py` |
| Pipeline startup | `pipeline_async.py` line ~188 (start of `async_pipeline()`) | Open SQLite connection, pass to context | `src/entities/registry.py` |

### Component Boundaries

| Component | Responsibility | Communicates With | New Files |
|-----------|---------------|-------------------|-----------|
| **Entity Registry** | SQLite CRUD for partners, people, initiatives; alias management; merge operations | All entity components | `src/entities/registry.py`, `src/entities/models.py`, `src/entities/db.py` |
| **Entity Discoverer** | Extract entity mentions from synthesis text; propose new entities; match against registry | Registry, Synthesis output | `src/entities/discoverer.py` |
| **Entity Attributor** | Tag synthesis items (substance, decisions, commitments) with entity IDs; write attributed sidecar | Registry, Discoverer, Sidecar | `src/entities/attributor.py` |
| **Scoped Views** | CLI query interface; per-entity markdown report generation | Registry, Attributor output | `src/entities/views.py`, `src/entities/cli.py` |

## Data Model: SQLite Schema

Use raw `sqlite3`/`aiosqlite` with Pydantic models for validation -- no ORM. The project already uses Pydantic everywhere and the schema is simple enough that an ORM adds complexity without value.

### Tables

```sql
-- Core entity tables
CREATE TABLE entities (
    id TEXT PRIMARY KEY,              -- UUID
    entity_type TEXT NOT NULL,        -- 'partner', 'person', 'initiative'
    canonical_name TEXT NOT NULL,     -- Display name
    created_at TEXT NOT NULL,         -- ISO datetime
    updated_at TEXT NOT NULL,         -- ISO datetime
    metadata TEXT DEFAULT '{}',       -- JSON blob for type-specific fields
    status TEXT DEFAULT 'active'      -- 'active', 'archived', 'merged'
);

CREATE TABLE entity_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT NOT NULL REFERENCES entities(id),
    alias TEXT NOT NULL,              -- Lowercase normalized alias
    alias_type TEXT DEFAULT 'name',   -- 'name', 'email', 'slack_handle', 'channel'
    created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX idx_alias_unique ON entity_aliases(alias, alias_type);
CREATE INDEX idx_alias_entity ON entity_aliases(entity_id);

-- Attribution: links synthesis items to entities
CREATE TABLE entity_mentions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT NOT NULL REFERENCES entities(id),
    date TEXT NOT NULL,               -- ISO date of the daily summary
    section TEXT NOT NULL,            -- 'substance', 'decision', 'commitment'
    item_index INTEGER NOT NULL,      -- Position within section
    item_content TEXT NOT NULL,       -- The synthesis item text
    source_attribution TEXT,          -- e.g., "Team Sync", "Slack #proj-alpha"
    confidence REAL DEFAULT 1.0,      -- Match confidence (1.0 = exact, <1.0 = fuzzy)
    created_at TEXT NOT NULL
);
CREATE INDEX idx_mention_entity ON entity_mentions(entity_id);
CREATE INDEX idx_mention_date ON entity_mentions(date);
CREATE INDEX idx_mention_entity_date ON entity_mentions(entity_id, date);

-- Merge tracking
CREATE TABLE merge_proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_entity_id TEXT NOT NULL REFERENCES entities(id),
    target_entity_id TEXT NOT NULL REFERENCES entities(id),
    reason TEXT NOT NULL,             -- Why merge was proposed
    status TEXT DEFAULT 'pending',    -- 'pending', 'accepted', 'rejected'
    created_at TEXT NOT NULL,
    resolved_at TEXT
);

-- Relationship: person <-> partner, person <-> initiative
CREATE TABLE entity_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id_a TEXT NOT NULL REFERENCES entities(id),
    entity_id_b TEXT NOT NULL REFERENCES entities(id),
    relationship_type TEXT NOT NULL,  -- 'works_at', 'involved_in', 'owns'
    created_at TEXT NOT NULL
);
CREATE INDEX idx_rel_a ON entity_relationships(entity_id_a);
CREATE INDEX idx_rel_b ON entity_relationships(entity_id_b);
```

### Why This Schema

**Alias table separate from entities:** The central problem is name resolution -- "Colin", "Colin R.", "colin@partner.com" must all resolve to one entity. A separate alias table with a unique index makes lookup fast and merge operations clean (merge = reassign aliases from source to target entity).

**Mentions table stores item_content:** Denormalized by design. The alternative is joining against daily sidecar JSON files, which requires scanning hundreds of files for scoped views. Storing content in SQLite makes "show me all Affirm activity" a single indexed query.

**JSON metadata blob:** Partner-specific fields (domain, HubSpot ID) and person-specific fields (email, Slack handle) differ. A JSON blob avoids wide-table sparse columns. Schema is simple enough that the flexibility is worth the trade-off.

### Pydantic Models (src/entities/models.py)

```python
class EntityType(StrEnum):
    PARTNER = "partner"
    PERSON = "person"
    INITIATIVE = "initiative"

class Entity(BaseModel):
    id: str                           # UUID
    entity_type: EntityType
    canonical_name: str
    aliases: list[str] = []
    metadata: dict = {}               # Type-specific: partner has "domain", person has "email"
    status: str = "active"
    created_at: datetime
    updated_at: datetime

class EntityMention(BaseModel):
    entity_id: str
    date: date
    section: str                      # 'substance', 'decision', 'commitment'
    item_index: int
    item_content: str
    source_attribution: str | None
    confidence: float = 1.0

class MergeProposal(BaseModel):
    source_entity_id: str
    target_entity_id: str
    reason: str
    status: str = "pending"
```

## Data Flow: How Entity Operations Integrate

### Flow 1: Ongoing Entity Discovery (per pipeline run)

```
synthesize_daily() returns synthesis_result dict
    |
    v
entity_discover(synthesis_result, registry)
    |
    +-- For each substance/decision/commitment item:
    |     1. Extract entity_names from structured output (Claude already parsed them)
    |     2. Match against entity_aliases table (case-insensitive)
    |     3. If match: record EntityMention
    |     4. If no match + high confidence name: create pending Entity
    |     5. If fuzzy match (e.g., "Colin" vs "Colin R."): create MergeProposal
    |
    v
Returns: list[EntityMention], list[Entity] (new), list[MergeProposal]
```

### Flow 2: Entity Attribution (extends sidecar)

```
extract_commitments() returns extracted_commitments
    |
    v
entity_attribute(synthesis_result, extracted_commitments, mentions)
    |
    +-- Enrich each CommitmentRow with entity_ids: list[str]
    +-- Enrich each SynthesisItem with entity_ids: list[str]
    +-- Build EntityAttributedSidecar (extends DailySidecar)
    |
    v
write_daily_sidecar() receives enriched data
    (sidecar JSON now includes entity_ids per item)
```

### Flow 3: Backfill Discovery (one-time historical scan)

```
CLI: python -m src.main entity backfill --from 2025-01-01 --to 2026-04-04
    |
    v
For each existing daily sidecar JSON:
    1. Load sidecar (tasks, decisions, commitments)
    2. Run entity_discover() against each item
    3. Store EntityMentions in SQLite
    4. Propose new Entities for unmatched names
    |
    v
CLI: python -m src.main entity review
    (Review pending entities and merge proposals)
```

### Flow 4: Scoped Views (query and report)

```
CLI: python -m src.main entity show affirm
    |
    v
1. Resolve "affirm" -> Entity via alias lookup
2. Query entity_mentions WHERE entity_id = X ORDER BY date DESC
3. Group by section (substance, decisions, commitments)
4. Render to stdout or markdown file
    |
    v
Output:
  # Affirm
  ## Recent Activity
  - [2026-04-03] Q2 pipeline review discussed integration timeline (per Team Sync)
  - [2026-04-02] API sandbox access granted to dev team (per Slack #affirm-integration)
  ## Open Commitments
  - Colin: Send technical spec by 2026-04-10 (per Team Sync, 2026-04-03)
```

## Modifications to Existing Components

### Modified: PipelineContext (src/pipeline.py)

Add SQLite connection to shared pipeline state:

```python
@dataclass
class PipelineContext:
    config: PipelineConfig
    target_date: date
    output_dir: Path
    template_dir: Path
    claude_client: anthropic.Anthropic
    google_creds: object | None = None
    calendar_service: object | None = None
    gmail_service: object | None = None
    user_email: str | None = None
    entity_registry: EntityRegistry | None = None  # NEW
```

### Modified: PipelineConfig (src/config.py)

Add entity configuration section:

```python
class EntityConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    db_path: str = "data/entities.db"
    auto_discover: bool = True         # Discover entities on each run
    discovery_confidence: float = 0.8  # Minimum confidence for auto-create
    merge_threshold: float = 0.85      # Fuzzy match threshold for merge proposals

class PipelineConfig(BaseModel):
    # ... existing sections ...
    entities: EntityConfig = Field(default_factory=EntityConfig)  # NEW
```

### Modified: DailySynthesisOutput (src/synthesis/models.py)

Extend structured output to include entity references. This is the cleanest integration point -- Claude already sees entity names in the synthesis text. Adding `entity_names` to the structured output schema means Claude extracts them during synthesis at zero additional API cost.

```python
class SynthesisItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str
    entity_names: list[str] = Field(default_factory=list)  # NEW: mentioned entities

class CommitmentRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    who: str
    what: str
    by_when: str
    source: str
    related_entities: list[str] = Field(default_factory=list)  # NEW
```

### Modified: Synthesis Prompt (src/synthesis/synthesizer.py)

Add entity extraction guidance to the existing SYNTHESIS_PROMPT. This is a prompt extension, not a new Claude call:

```
entity_names: List ALL partner names, person names, and initiative names mentioned
in this item. Use the exact name as it appears. Include company names (e.g., "Affirm"),
person first names (e.g., "Colin"), and initiative names (e.g., "HubSpot Migration").
If no entities are mentioned, leave empty.
```

### Modified: DailySidecar (src/sidecar.py)

```python
class DailySidecar(BaseModel):
    date: str
    generated_at: str
    meeting_count: int
    transcript_count: int
    tasks: list[SidecarTask] = Field(default_factory=list)
    decisions: list[SidecarDecision] = Field(default_factory=list)
    commitments: list[SidecarCommitment] = Field(default_factory=list)
    source_meetings: list[SidecarMeeting] = Field(default_factory=list)
    entity_mentions: list[dict] = Field(default_factory=list)  # NEW
```

### Modified: async_pipeline() (src/pipeline_async.py)

New steps inserted after existing synthesis and before output:

```python
async def async_pipeline(ctx: PipelineContext) -> None:
    # ... existing Phase 1 (ingest) and Phase 2 (synthesis) ...

    # Phase 2.5: Entity Discovery + Attribution (NEW)
    entity_mentions = []
    if ctx.entity_registry and ctx.config.entities.enabled:
        try:
            entity_mentions = await asyncio.to_thread(
                discover_and_attribute,
                synthesis_result,
                extracted_commitments,
                ctx.entity_registry,
                ctx.config,
                current,
            )
            logger.info("Entity discovery: %d mentions attributed", len(entity_mentions))
        except Exception as e:
            logger.warning("Entity discovery failed: %s. Continuing without.", e)

    # ... existing Phase 3 (output) with entity_mentions passed to sidecar ...
```

### Modified: _convert_synthesis_to_dict() (src/synthesis/synthesizer.py)

Currently this function strips the Pydantic structure and returns plain strings. It must be extended to carry entity_names through:

```python
def _convert_synthesis_to_dict(output: DailySynthesisOutput) -> dict:
    return {
        "executive_summary": output.executive_summary,
        "substance": [item.content for item in output.substance],
        "decisions": [item.content for item in output.decisions],
        "commitments": [
            f"| {c.who} | {c.what} | {c.by_when} | {c.source} |"
            for c in output.commitments
        ],
        # NEW: entity names per item for downstream attribution
        "substance_entities": [item.entity_names for item in output.substance],
        "decision_entities": [item.entity_names for item in output.decisions],
        "commitment_entities": [c.related_entities for c in output.commitments],
    }
```

### NOT Modified

These components require zero changes:

- **All ingest modules** (`src/ingest/*`) -- entity discovery operates on synthesis output, not raw ingest data
- **Dedup** (`src/dedup.py`) -- operates pre-synthesis, before entities are relevant
- **Quality tracking** (`src/quality.py`) -- tracks edit detection, orthogonal to entities
- **Notifications** (`src/notifications/slack.py`) -- entity-scoped notifications are a future feature
- **Templates** (`templates/*.j2`) -- entity data lives in sidecar JSON, not markdown (initially)
- **Roll-ups** (`src/synthesis/weekly.py`, `monthly.py`) -- entity-aware roll-ups deferred to after core entity layer stabilizes
- **Extractor** (`src/synthesis/extractor.py`) -- per-meeting extraction already captures participants; entity attribution happens at the daily synthesis level

## New File Structure

```
src/entities/
    __init__.py
    models.py           # Pydantic models: Entity, EntityMention, MergeProposal, EntityType
    db.py               # SQLite connection management, schema creation, migrations
    registry.py         # CRUD operations: create/read/update/merge entities + alias resolution
    discoverer.py       # Match entity_names from synthesis output against registry
    attributor.py       # Tag synthesis items with entity IDs, enrich sidecar
    views.py            # Scoped query logic: entity timeline, commitments, activity feed
    cli.py              # CLI subcommands: show, list, review, backfill, merge

data/
    entities.db         # SQLite database file (gitignored)

config/
    entities.yaml       # Optional: pre-seeded entity definitions for bootstrap
```

## Patterns to Follow

### Pattern 1: Non-Blocking Entity Operations

Entity operations must follow the existing pipeline pattern of graceful degradation. An entity discovery failure must never block daily summary output. This matches every other optional feature in the pipeline (Slack, HubSpot, Notion all use this pattern).

```python
# Correct: wrap in try/except, log warning, continue
try:
    mentions = discover_entities(synthesis_result, registry)
except Exception as e:
    logger.warning("Entity discovery failed: %s. Continuing without.", e)
    mentions = []
```

### Pattern 2: SQLite Connection Lifecycle

Open connection at pipeline start, close at pipeline end. Use `aiosqlite` for the async pipeline path, `sqlite3` for sync CLI commands (backfill, query, review).

```python
# In pipeline startup
from src.entities.db import open_entity_db

async def async_pipeline(ctx: PipelineContext) -> None:
    if ctx.config.entities.enabled:
        ctx.entity_registry = await open_entity_db(ctx.config.entities.db_path)
    try:
        # ... pipeline ...
    finally:
        if ctx.entity_registry:
            await ctx.entity_registry.close()
```

For CLI commands that run outside the async pipeline:
```python
# Sync connection for CLI
import sqlite3
conn = sqlite3.connect(config.entities.db_path)
registry = EntityRegistry(conn)
```

### Pattern 3: Entity Discovery via Structured Output Extension

Rather than a separate LLM call for entity extraction, extend the existing `DailySynthesisOutput` schema with `entity_names` fields. Claude already processes all source material during synthesis -- extracting entity names is a near-zero-cost addition to the existing prompt.

This eliminates an entire Claude API call per pipeline run. The synthesis prompt already sees every person name, company name, and initiative name. Asking Claude to list them in a structured field adds negligible latency to the existing call.

### Pattern 4: Alias-Based Matching

All entity lookups go through the alias table, never direct name comparison. This handles the "Colin" = "Colin R." = "colin@partner.com" problem at the data layer.

```python
class EntityRegistry:
    def resolve(self, name: str) -> Entity | None:
        """Resolve a name/alias to an entity. Case-insensitive."""
        normalized = name.strip().lower()
        row = self.conn.execute(
            "SELECT entity_id FROM entity_aliases WHERE alias = ?",
            (normalized,)
        ).fetchone()
        if row:
            return self.get_entity(row[0])
        return None
```

### Pattern 5: Schema Versioning Without an ORM

Simple version tracking for schema migrations:

```python
# In db.py
SCHEMA_VERSION = 1

def _ensure_schema(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER)")
    row = conn.execute("SELECT version FROM schema_version").fetchone()
    current = row[0] if row else 0

    if current < 1:
        _apply_v1_schema(conn)
        conn.execute("INSERT OR REPLACE INTO schema_version VALUES (1)")

    conn.commit()
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Separate LLM Call for Entity Extraction

Do NOT add a third Claude API call just for entity extraction. The synthesis call already has all the context. Extend the structured output schema instead.

**Why bad:** Adds 3-5s latency, ~$0.01 API cost per run, and a new failure point. The synthesis prompt already contains every name, organization, and initiative mention.

**Instead:** Add `entity_names: list[str]` to `SynthesisItem` and `CommitmentRow` in the structured output schema.

### Anti-Pattern 2: ORM for Simple Schema

Do NOT use SQLAlchemy, SQLModel, or any ORM. The schema is 5 tables with straightforward queries. An ORM adds dependency weight, migration complexity, and obscures the simple SQL.

**Why bad:** The project has zero ORM dependencies. Adding SQLAlchemy pulls in a large dependency tree and Alembic for migrations. The entity schema needs ~10 distinct queries total. Raw SQL with Pydantic validation is simpler.

**Instead:** Use `sqlite3`/`aiosqlite` directly. Write SQL strings in `db.py`. Use a version table for migrations.

### Anti-Pattern 3: Entity Discovery on Raw Ingest Data

Do NOT try to discover entities from raw `SourceItem` content. Raw Slack messages, HubSpot activities, and transcript text are noisy.

**Why bad:** Raw content has a much higher noise-to-signal ratio than synthesized output. "Hey Colin, can you pass the link?" is a raw Slack message -- tracking it as a Colin mention adds noise. Synthesis already filters for what matters.

**Instead:** Discover entities from synthesis output only. The synthesis stage has already distilled source material to substance, decisions, and commitments.

### Anti-Pattern 4: Storing Entity Data in Flat Files

Do NOT follow the existing flat-file pattern for entities. Entity data requires joins (entity -> mentions, entity -> aliases, entity -> relationships) that flat files cannot support.

**Why bad:** Scoped views like "show me all Affirm commitments" require aggregating across hundreds of daily files. SQLite handles this in milliseconds; flat file scanning takes seconds and grows linearly.

**Instead:** SQLite is the right tool. This is the project's first database -- accept that architectural transition.

### Anti-Pattern 5: Modifying DailySynthesis (events.py) for Entities

Do NOT add entity fields to `DailySynthesis` (the Pydantic model in `src/models/events.py` that feeds Jinja2 templates). Entity data should flow through the sidecar JSON, not the markdown rendering pipeline.

**Why bad:** `DailySynthesis` feeds Jinja2 templates. Adding entity fields means modifying templates, which adds coupling between entity layer and output rendering. Entity data is structured metadata, not prose for daily markdown.

**Instead:** Enrich `DailySidecar` (JSON output) with entity references. Scoped views read from SQLite directly, not from daily markdown.

## Build Order (Dependency-Driven)

The build order follows strict dependency chains. Each phase produces something testable before the next begins.

### Phase 1: Entity Registry (SQLite Foundation)

**What:** SQLite schema, connection management, Pydantic models, CRUD operations, config section.

**New files:** `src/entities/__init__.py`, `src/entities/models.py`, `src/entities/db.py`, `src/entities/registry.py`

**Modified files:** `src/config.py` (add `EntityConfig` section)

**Why first:** Everything else depends on being able to store and retrieve entities. No discovery, attribution, or views work without the registry.

**Dependencies:** None (new module, no integration with existing pipeline yet).

**Test surface:** Unit tests for CRUD operations, alias resolution, schema creation, fuzzy matching for merge proposals.

### Phase 2: Entity Discovery

**What:** Extract entity mentions from synthesis output. Extend `DailySynthesisOutput` with `entity_names` field. Match against registry. Auto-create high-confidence entities. Generate merge proposals for fuzzy matches.

**New files:** `src/entities/discoverer.py`

**Modified files:** `src/synthesis/models.py` (add `entity_names` to `SynthesisItem`, `related_entities` to `CommitmentRow`), `src/synthesis/synthesizer.py` (extend prompt, modify `_convert_synthesis_to_dict()`)

**Why second:** Discovery is the data source for attribution and views. Without discovery, the registry stays empty.

**Dependencies:** Phase 1 (registry must exist to store discoveries).

**Test surface:** Unit tests for name extraction, alias matching, merge proposal generation. Integration test: run discovery on real synthesis output and verify entity creation.

### Phase 3: Entity Attribution (Pipeline Integration)

**What:** Wire discovery into `async_pipeline()`. Enrich sidecar with entity references. Add `entity_registry` to `PipelineContext`. Run discovery after synthesis, store mentions in SQLite.

**New files:** `src/entities/attributor.py`

**Modified files:** `src/pipeline.py` (add `entity_registry` to `PipelineContext`), `src/pipeline_async.py` (add Phase 2.5 entity step), `src/sidecar.py` (add `entity_mentions` field), `src/output/writer.py` (pass entity data to sidecar)

**Why third:** This is where the entity layer joins the live pipeline. Requires both registry (Phase 1) and discovery logic (Phase 2).

**Dependencies:** Phase 1 + Phase 2.

**Test surface:** Integration test: run full pipeline with entities enabled, verify sidecar contains entity references. Verify pipeline completes normally with `entities.enabled: false` (default).

### Phase 4: Backfill + Merge Review

**What:** CLI command to scan historical sidecar JSONs and run entity discovery retroactively. CLI command to review/accept/reject merge proposals and pending entities.

**New files:** `src/entities/cli.py`

**Modified files:** `src/main.py` (add `entity` subcommand with `backfill`, `review`, `merge` actions)

**Why fourth:** Backfill uses the same discovery logic from Phase 2 applied to historical data. Merge review requires entities to exist (from backfill or live runs). This phase populates the registry with historical data, making scoped views useful.

**Dependencies:** Phase 1 + Phase 2 (discovery logic reused). Phase 3 optional but helpful for testing.

**Test surface:** Integration test: backfill 5 days of sidecar data, verify entities and mentions created. Test merge accept/reject workflow.

### Phase 5: Scoped Views

**What:** CLI query commands (`entity show X`, `entity commitments --owner Y`). Per-entity markdown report generation.

**New files:** `src/entities/views.py`

**Modified files:** `src/entities/cli.py` (add `show`, `list`, `commitments` subcommands)

**Why last:** Views consume everything built in Phases 1-4. They read from the entity_mentions table populated by discovery/attribution/backfill. Without populated data, views return nothing.

**Dependencies:** Phase 1 + Phase 3 or Phase 4 (needs populated data to query against).

**Test surface:** Integration test: query entity with known mentions, verify output format. Test empty entity and missing entity gracefully.

### Phase Dependency Graph

```
Phase 1: Registry ──────────────────────────────────────────┐
    |                                                        |
Phase 2: Discovery (extends synthesis models + prompt) ──────┤
    |                                                        |
Phase 3: Attribution (wires into pipeline_async.py) ─────────┤
    |                                                        |
Phase 4: Backfill + Merge Review (CLI commands) ─────────────┤
    |                                                        |
Phase 5: Scoped Views (CLI queries + reports) ───────────────┘
```

Phases 4 and 5 could be built in parallel since they share Phase 1-2 dependencies but don't depend on each other. However, backfill (Phase 4) populates the data that makes views (Phase 5) useful, so sequential order is recommended.

## Scalability Considerations

| Concern | Current Scale (~200 days) | At 1 Year (~365 days) | At 3 Years (~1000 days) |
|---------|---------------------------|----------------------|------------------------|
| SQLite DB size | <1 MB | <5 MB | <20 MB |
| Entity count | ~50-100 (partners + people) | ~200 | ~500 |
| Mention count | ~2,000 | ~5,000 | ~15,000 |
| Query latency (entity show) | <10ms | <20ms | <50ms |
| Backfill time (full) | ~30s | ~60s | ~3 min |
| Pipeline overhead (entity step) | <100ms | <200ms | <500ms |

SQLite handles this scale trivially. No sharding, connection pooling, or read replicas needed. The entire database will fit in memory for the foreseeable future. WAL mode should be enabled for concurrent read/write during pipeline runs.

## Sources

- Direct codebase analysis of `src/pipeline_async.py`, `src/synthesis/synthesizer.py`, `src/synthesis/models.py`, `src/models/sources.py`, `src/sidecar.py`, `src/config.py`, `src/pipeline.py`, `src/output/writer.py` (HIGH confidence)
- [aiosqlite documentation](https://aiosqlite.omnilib.dev/en/latest/) -- async SQLite bridge for Python asyncio (HIGH confidence)
- [aiosqlite GitHub](https://github.com/omnilib/aiosqlite) -- latest release Dec 2025, actively maintained (HIGH confidence)
- [SQLite documentation](https://sqlite.org/docs.html) -- schema design patterns, WAL mode (HIGH confidence)
- `.planning/V2_VISION.md` -- entity layer data model and phasing (HIGH confidence, project-internal)
- `.planning/codebase/ARCHITECTURE.md` -- current pipeline architecture (HIGH confidence, project-internal)

---
*Architecture research for: Work Intelligence System v2.0 Entity Layer*
*Researched: 2026-04-05*
