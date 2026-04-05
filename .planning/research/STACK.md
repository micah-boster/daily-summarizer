# Stack Research: Entity Layer Additions (v2.0)

**Domain:** Entity registry, discovery, merge/resolution, scoped views for work intelligence pipeline
**Researched:** 2026-04-05
**Confidence:** HIGH

## Existing Stack (Validated, Not Changing)

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | >=3.12 | Runtime |
| anthropic | >=0.45.0 (0.88.0 installed) | Claude API (Sonnet/Opus) with structured outputs |
| pydantic | >=2.12.5 | Config models, structured output schemas |
| httpx | >=0.28.1 | Async HTTP client |
| tenacity | >=9.1.4 | Retry logic |
| jinja2 | >=3.1.6 | Output template rendering |
| argparse | stdlib | CLI subcommands |
| asyncio | stdlib | Concurrent pipeline execution |
| rapidfuzz | >=3.12.0 (already added in v1.5.1) | Fuzzy string matching |

## New Dependencies: Only ONE Package

### Core: SQLite Entity Registry

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| sqlite3 | stdlib (SQLite 3.51.0 on system) | Entity registry storage | Zero new dependencies. Python 3.12 bundles it. JSON1 extension built-in for flexible metadata columns. WAL mode for concurrent reads during pipeline runs. This is a single-user personal tool -- SQLite is the correct database. |
| aiosqlite | >=0.22.0,<1.0 | Async SQLite access from pipeline | The pipeline is already async (pipeline_async.py). Entity backfill and discovery run alongside ingestion. aiosqlite wraps stdlib sqlite3 with async context managers -- same API surface, non-blocking. Thin wrapper, no ORM overhead. |

**Why aiosqlite and not just sqlite3 with asyncio.to_thread():**
- `to_thread()` works but requires manual connection management per call
- aiosqlite provides async context managers (`async with aiosqlite.connect() as db:`) matching the project's existing async patterns
- Connection pooling through a single shared thread per connection -- safe for SQLite's single-writer model
- The project already uses async patterns extensively in pipeline_async.py; aiosqlite fits naturally

**Schema approach:** Hand-written SQL with a `schema_version` table. Migration functions in `src/entity/migrations.py` run on startup, check current version, apply incremental changes. Pydantic models for Python-side representations (consistent with existing config.py and synthesis/models.py patterns). No ORM.

### Entity Discovery: Claude Structured Outputs (Already in Stack)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| anthropic (existing) | >=0.45.0 | NER / entity extraction from text | The project already uses Claude structured outputs for meeting extraction (ExtractionItemOutput) and synthesis (DailySynthesisOutput). Entity discovery is the same pattern: send text, get structured JSON with entity mentions. Zero new dependencies. |

**Why NOT spaCy / GLiNER / dedicated NER libraries:**
- The project already sends all source text through Claude for extraction. Entity discovery is a prompt change plus a schema extension, not a new library.
- spaCy adds approximately 500MB of model downloads for marginal accuracy gain over Claude Sonnet on business-domain text (partner names, people, initiatives are not standard NER categories).
- Claude already sees participant lists, meeting titles, Slack usernames, HubSpot deal/company names -- it has rich context for entity recognition that a standalone NER model would lack.
- Adding a separate NER pipeline creates a second extraction pass over the same text. Instead, extend the existing structured output schemas with entity reference fields. One pass, zero new dependencies.

**Implementation approach:** Add `entity_mentions: list[EntityMention]` fields to existing ExtractionItemOutput and DailySynthesisOutput Pydantic models. EntityMention is a new Pydantic model with `name`, `type` (partner/person/initiative), and `confidence` fields. Claude extracts entities during its existing synthesis pass. For backfill over historical summaries, a dedicated discovery prompt reads stored markdown and outputs entity mentions.

### Entity Merge/Resolution: RapidFuzz (Already in Stack)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| rapidfuzz (existing) | >=3.12.0 | Fuzzy string matching for entity merge proposals | Already added in v1.5.1 for cross-source dedup. Reuse for matching "Colin" = "Colin R." = "Colin Richardson". Token sort ratio and partial ratio algorithms handle name variations. No new dependency. |

**Merge strategy (algorithmic + LLM hybrid):**
1. Normalize names: lowercase, strip suffixes (Inc, LLC), collapse whitespace
2. Compute rapidfuzz.fuzz.token_sort_ratio for all entity name pairs within same type
3. Above 95: auto-merge (high confidence)
4. Between 85-95: propose merge, optionally confirm with Claude (reuse existing client)
5. Below 85: separate entities
6. Store aliases in entity registry so merged entities retain all known name variants

**Why NOT a full entity resolution framework (dedupe, entity-resolution, zingg):**
- Those frameworks handle millions of records across messy datasets with active learning
- This system has hundreds to low thousands of entity mentions
- The existing SequenceMatcher pattern in src/dedup.py proves lightweight fuzzy matching works for this project's scale
- rapidfuzz is already a dependency -- zero incremental cost

### Scoped Views: No New Dependencies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| argparse (existing) | stdlib | New `entity` subcommand for CLI queries | Already used in main.py with subparsers. Add `entity` subcommand with filters. Consistent with existing CLI patterns. |
| jinja2 (existing) | >=3.1.6 | Scoped markdown report generation | Already in dependencies for daily/weekly output. Entity-scoped reports are the same pattern: query data, render template, write markdown file. |

## Installation

```bash
# Single new dependency
pip install "aiosqlite>=0.22.0,<1.0"
```

**pyproject.toml change:**
```toml
dependencies = [
    # ... all existing dependencies unchanged ...
    "aiosqlite>=0.22.0,<1.0",           # NEW: async SQLite for entity registry
]
```

That is it. One new package. Everything else leverages the existing stack.

## Integration Points with Existing Code

### Pydantic Models (src/synthesis/models.py)

Extend existing structured output models with entity fields:

```python
class EntityMention(BaseModel):
    """Entity reference extracted during synthesis."""
    model_config = ConfigDict(extra="forbid")

    name: str           # As mentioned in text ("Affirm", "Colin", "Q2 launch")
    entity_type: str    # "partner" | "person" | "initiative"

class ExtractionItemOutput(BaseModel):
    """Extended: each extraction item now carries entity mentions."""
    model_config = ConfigDict(extra="forbid")

    content: str
    participants: list[str] = Field(default_factory=list)
    rationale: str | None = None
    entity_mentions: list[EntityMention] = Field(default_factory=list)  # NEW
```

This is backward-compatible: the `entity_mentions` field defaults to an empty list, so existing extraction results remain valid.

### Async Pipeline (src/pipeline_async.py)

Entity processing slots into the existing async pipeline:

```
Ingest (existing)
  -> Extract with entity mentions (extended schema)
  -> Dedup (existing)
  -> Synthesize with entity attribution (extended schema)
  -> Persist entities to SQLite registry
  -> Write Output (existing + entity-tagged)
```

Entity persistence is a new step after synthesis. It runs sequentially after synthesis completes (needs the synthesis results) but uses aiosqlite for non-blocking DB writes.

### Config (src/config.py)

Add entity config section to existing Pydantic config model:

```python
class EntityConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    db_path: str = "data/entities.db"
    merge_threshold: float = 0.85
    auto_merge_threshold: float = 0.95
    discovery_model: str = "claude-sonnet-4-20250514"
```

### CLI (src/main.py)

New argparse subcommands alongside existing daily/weekly/monthly/discover-slack/discover-notion:

```
python -m src.main entity list [--type partner|person|initiative]
python -m src.main entity show <name> [--from DATE] [--to DATE]
python -m src.main entity merge <id1> <id2>
python -m src.main entity merge-proposals [--auto-apply]
python -m src.main entity report <name> [--format md|terminal]
```

### Existing Dedup (src/dedup.py)

The dedup module already uses difflib.SequenceMatcher for title similarity. Entity merge uses the same conceptual pattern but operates on entity names via rapidfuzz (already in deps). No changes to existing dedup code needed.

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| sqlite3 + aiosqlite | SQLAlchemy + Alembic | If the schema grew to 15+ tables with complex relationships and multiple developers. Not this project. |
| sqlite3 + aiosqlite | PostgreSQL | If multi-user, concurrent writes, or full-text search at scale were needed. Not a personal tool. |
| Claude structured outputs for NER | spaCy + en_core_web_lg | If you needed offline NER without API costs. But we already pay for Claude calls during extraction -- entity fields are free marginal cost. |
| Claude structured outputs for NER | GLiNER (zero-shot NER) | If you needed NER without any API and wanted custom entity types. Good library, but redundant when Claude is already in the loop. |
| rapidfuzz for merge | dedupe library | If you had 100K+ entities with training data. Overkill for hundreds of entities. |
| Hand-written SQL migrations | Alembic | If using SQLAlchemy. Alembic requires SQLAlchemy -- circular dependency on a decision we already rejected. |
| argparse | click / typer | If building a standalone CLI tool. But main.py already uses argparse -- switching frameworks for one subcommand creates inconsistency. |

## What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| SQLAlchemy | 3-4 simple tables. ORM adds session management, migration tooling, and abstraction for no benefit at this scale. Raw SQL is more readable for simple entity CRUD. | sqlite3/aiosqlite + Pydantic models |
| Alembic | Requires SQLAlchemy. A `schema_version` table with Python migration functions is simpler and sufficient for a personal tool with one developer. | Hand-written migrations |
| spaCy | 500MB+ model downloads. Separate extraction pass duplicates work Claude already does. Business entity types (partners, initiatives) are not standard NER categories -- would need custom training. | Claude structured output extension |
| Neo4j / graph DB | Entity relationships are simple (person belongs to partner, initiative involves people). These are foreign keys, not graph traversals. | SQLite junction tables |
| FTS5 (SQLite full-text search) | Premature optimization. Entity queries filter by entity ID + date range, which indexed columns handle. | Standard SQL with indexes on entity_id and date |
| instructor | Wraps anthropic SDK for structured outputs. Unnecessary -- the project already uses native structured outputs via output_config. | Direct anthropic SDK |
| langchain | Massive dependency tree. The project makes direct Claude API calls which are simpler and more maintainable. | Direct anthropic SDK |

## Stack Patterns by Feature

**Entity discovery (new pipeline runs):**
- Extend existing Claude structured output schema with EntityMention fields
- No new libraries, no new API calls -- piggyback on existing extraction

**Entity discovery (historical backfill):**
- Read stored markdown summaries from output/ directory
- Send through dedicated Claude prompt with EntityMention output schema
- Use AsyncAnthropic for concurrent processing of multiple days
- Persist discovered entities to SQLite via aiosqlite

**Entity merge proposals:**
- Query all entities from SQLite grouped by type
- Compute pairwise rapidfuzz.fuzz.token_sort_ratio within each type
- Above auto_merge_threshold (0.95): merge automatically, log action
- Between merge_threshold (0.85) and auto_merge_threshold: present to user via CLI
- Store merge decisions (alias table) so rejected merges are not re-proposed

**Scoped views:**
- SQL query: join entity mentions to synthesis items by date range
- Render with existing Jinja2 templates
- Output as markdown (consistent with daily/weekly reports) or terminal display

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| aiosqlite 0.22.x | Python >=3.9 | Well within our >=3.12 requirement |
| aiosqlite 0.22.x | sqlite3 stdlib | Uses stdlib sqlite3 under the hood, no version conflicts |
| rapidfuzz 3.14.x (existing) | aiosqlite 0.22.x | No interaction -- different domains |

## Capability-to-Library Mapping

Quick reference for plan authors -- which library addresses which v2.0 feature.

| Feature | Library | Key API / Pattern |
|---------|---------|-------------------|
| Entity registry storage | sqlite3 + aiosqlite | `aiosqlite.connect()`, hand-written SQL, Pydantic hydration |
| Entity discovery (new runs) | anthropic (existing) | Extended structured output schema with EntityMention |
| Entity discovery (backfill) | anthropic (existing) | Dedicated prompt + AsyncAnthropic for concurrent processing |
| Entity merge proposals | rapidfuzz (existing) | `fuzz.token_sort_ratio()`, threshold-based merge/propose |
| Entity merge confirmation | anthropic (existing) | Optional LLM confirmation for ambiguous pairs |
| Entity merge CLI | argparse (existing) | New `entity merge-proposals` subcommand |
| Scoped view queries | sqlite3 + aiosqlite | SQL joins: entity -> mentions -> synthesis items |
| Scoped view rendering | jinja2 (existing) | Markdown templates for entity reports |
| Scoped view CLI | argparse (existing) | New `entity show` and `entity report` subcommands |
| Entity config | pydantic (existing) | New EntityConfig model in config.py |

## Sources

- [aiosqlite PyPI](https://pypi.org/project/aiosqlite/) -- version 0.22.1, released 2025-12-23 (HIGH confidence)
- [aiosqlite docs](https://aiosqlite.omnilib.dev/) -- API reference, async context managers (HIGH confidence)
- [aiosqlite GitHub](https://github.com/omnilib/aiosqlite) -- threading model, sqlite3 compatibility (HIGH confidence)
- [RapidFuzz PyPI](https://pypi.org/project/RapidFuzz/) -- version 3.14.3 (HIGH confidence, already in project deps)
- [RapidFuzz GitHub](https://github.com/rapidfuzz/RapidFuzz) -- benchmarks vs thefuzz, algorithm documentation (HIGH confidence)
- [Python sqlite3 docs](https://docs.python.org/3/library/sqlite3.html) -- WAL mode, JSON1 support (HIGH confidence)
- System SQLite version verified: `python3 -c "import sqlite3; print(sqlite3.sqlite_version)"` returned 3.51.0 (HIGH confidence)
- LLM-based NER approaches validated via [AWS Bedrock NER patterns](https://aws.amazon.com/blogs/machine-learning/use-zero-shot-large-language-models-on-amazon-bedrock-for-custom-named-entity-recognition/) and [GPT-NER research](https://arxiv.org/abs/2304.10428) (MEDIUM confidence -- approach is sound, prompt design needs iteration)
- Existing project code reviewed: src/synthesis/models.py, src/dedup.py, src/pipeline_async.py, src/config.py, src/main.py (HIGH confidence)

---
*Stack research for: Entity layer additions (v2.0) to Work Intelligence System*
*Researched: 2026-04-05*
