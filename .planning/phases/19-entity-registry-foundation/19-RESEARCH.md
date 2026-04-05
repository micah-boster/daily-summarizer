# Phase 19: Entity Registry Foundation - Research

**Researched:** 2026-04-05
**Domain:** SQLite persistent storage, entity modeling, schema migration, CLI subcommands
**Confidence:** HIGH

## Summary

Phase 19 introduces the first database-backed storage in the project. The core challenge is designing a SQLite schema and Python data access layer that serves as the foundation for four subsequent phases (20-23) while keeping the implementation simple and aligned with existing project patterns (Pydantic models, argparse subcommands, async-ready architecture).

The project already uses Pydantic extensively for config validation and Claude structured outputs, `argparse` with subparsers for CLI commands, and an async pipeline via `asyncio`. The entity layer should mirror these patterns: Pydantic models for entity data, a repository class that abstracts all SQLite access, argparse subparsers for entity CLI commands, and aiosqlite for async compatibility.

**Primary recommendation:** Use Python's stdlib `sqlite3` for sync operations (CLI, migrations) and `aiosqlite` 0.22.x for async pipeline integration. Keep all database access behind a repository class. Use `PRAGMA user_version` for migrations with hand-written SQL functions -- no ORM, no Alembic.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- DB path configurable in config.yaml, default `data/entities.db`
- Auto-create DB on first access (no explicit init command needed)
- Graceful degradation: pipeline runs without entity features if DB is unavailable or corrupted
- `data/` directory and `*.db` files added to .gitignore (personal data, binary format)
- WAL mode enabled for async compatibility
- Subcommand style: `python -m src.main entity add/list/alias/show/remove`
- Output: human-readable table by default, `--json` flag for structured output
- Entity type is required: `--type partner` or `--type person`
- Soft-delete on remove (mark deleted_at timestamp, can be restored)
- Single `entities` table with `entity_type` column ('partner', 'person', 'initiative')
- Minimal typed columns: name, entity_type, organization_id (optional), external IDs (hubspot_id, slack_channel)
- JSON `metadata` column for extensible key-value pairs
- People have optional `organization_id` foreign key referencing a partner entity
- `merge_target_id` column baked in from day one
- Full schema created in Phase 19: entities, aliases, entity_mentions, merge_proposals, relationships tables
- Tables for later phases sit empty until needed
- 'initiative' included in entity_type enum from day one (feature deferred to v2.1)
- Simple migration: PRAGMA user_version + hand-written SQL migration functions (no Alembic/SQLAlchemy)
- Follow existing project pattern: Pydantic models for entity data, config validation at startup
- Repository layer should abstract SQLite access (clean swap path to Postgres at v5.0)
- Keep all sqlite3/aiosqlite imports confined to the repository module
- Standard SQL only -- avoid SQLite-specific features that don't exist in Postgres

### Claude's Discretion
- Exact schema DDL and column types
- Migration function structure and versioning approach
- Repository pattern design for data access layer
- Pydantic model field naming and validation rules
- Table indexing strategy
- WAL mode configuration details
- CLI argument parsing implementation (argparse subparsers)

### Deferred Ideas (OUT OF SCOPE)
- Initiative tracking feature -- v2.1 (schema slot reserved in entity_type enum)
- Seed file for bootstrapping known entities (config/entities.yaml) -- consider for Phase 20
- Entity import/export for backup -- future enhancement
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ENTY-01 | Entity registry persists partners and people in SQLite with schema migration support and soft-delete | Schema DDL, migration infrastructure, repository CRUD, soft-delete pattern |
| ENTY-02 | User can add, remove, and manage aliases for an entity via CLI (e.g., "CR" = "Colin Roberts") | Aliases table design, CLI subcommand pattern, alias resolution query |
| ENTY-03 | Entity mentions include confidence scoring (high for direct attribution, low for indirect/ambient) | entity_mentions table with confidence float column, ConfidenceLevel enum, scoring model |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sqlite3 | stdlib | Sync database access (CLI, migrations) | Zero dependency; sufficient for single-user app |
| aiosqlite | 0.22.x | Async database access (pipeline integration) | Production-stable asyncio bridge to sqlite3; MIT license |
| pydantic | 2.12.x (existing) | Entity models, config validation | Already used throughout project for config and structured outputs |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| json (stdlib) | stdlib | Metadata column serialization | Storing/retrieving extensible key-value pairs in metadata column |
| uuid (stdlib) | stdlib | Entity ID generation | Generating unique entity IDs (uuid4 hex strings) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| sqlite3 + aiosqlite | SQLAlchemy | Over-engineered for single-user app; adds large dependency; user explicitly rejected ORM |
| PRAGMA user_version | Alembic | User explicitly chose hand-written migrations; Alembic adds SQLAlchemy dependency |
| uuid4 strings | integer autoincrement | UUIDs are merge-safe across databases; integer PKs collide on merge |

**Installation:**
```bash
uv add aiosqlite
```

No other new dependencies needed -- sqlite3, json, uuid are all stdlib.

## Architecture Patterns

### Recommended Project Structure
```
src/
  entity/
    __init__.py          # Public API exports
    models.py            # Pydantic models (Entity, Alias, EntityMention, etc.)
    repository.py        # EntityRepository class -- ALL sqlite3/aiosqlite imports here
    migrations.py        # Schema versioning and migration functions
    cli.py               # argparse subparser registration and command handlers
  config.py              # Add EntityConfig section to PipelineConfig
  main.py                # Register entity subcommand parser
```

### Pattern 1: PRAGMA user_version Migration
**What:** Check schema version on connection, apply pending migrations sequentially.
**When to use:** Every time a database connection is opened (auto-migrate on startup).
**Example:**
```python
# Source: SQLite docs + community pattern (levlaz.org)
import sqlite3

SCHEMA_VERSION = 1  # Increment when adding migrations

def _get_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]

def _set_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(f"PRAGMA user_version = {version}")

MIGRATIONS: list[callable] = [
    _migrate_v0_to_v1,  # Initial schema creation
]

def run_migrations(conn: sqlite3.Connection) -> None:
    current = _get_version(conn)
    for i, migration in enumerate(MIGRATIONS):
        target = i + 1
        if target > current:
            migration(conn)
            _set_version(conn, target)
            conn.commit()
```

### Pattern 2: Repository with Pydantic Row Mapping
**What:** Repository class that accepts/returns Pydantic models, maps to/from SQL rows internally.
**When to use:** All database access goes through the repository.
**Example:**
```python
# Source: nickgeorge.net/pydantic-sqlite3 + project conventions
from src.entity.models import Entity

class EntityRepository:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row  # dict-like access
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        run_migrations(conn)
        return conn

    def add_entity(self, name: str, entity_type: str, **kwargs) -> Entity:
        entity_id = uuid4().hex
        # INSERT then return Pydantic model
        ...
        return Entity(id=entity_id, name=name, entity_type=entity_type, **kwargs)

    def get_by_id(self, entity_id: str) -> Entity | None:
        row = self._conn.execute(
            "SELECT * FROM entities WHERE id = ? AND deleted_at IS NULL",
            (entity_id,)
        ).fetchone()
        if row is None:
            return None
        return Entity(**dict(row))
```

### Pattern 3: Graceful Degradation
**What:** Pipeline runs normally even if entity DB is unavailable.
**When to use:** Pipeline startup and any entity-related pipeline step.
**Example:**
```python
def get_entity_repository(config: PipelineConfig) -> EntityRepository | None:
    """Return repository or None if DB unavailable."""
    try:
        repo = EntityRepository(config.entity.db_path)
        repo.connect()
        return repo
    except Exception as e:
        logger.warning("Entity DB unavailable, entity features disabled: %s", e)
        return None
```

### Pattern 4: CLI Subcommand Registration (matches existing project style)
**What:** Add `entity` as a subparser in main.py, delegate to entity/cli.py handlers.
**When to use:** All entity CLI commands.
**Example:**
```python
# In src/entity/cli.py
def register_entity_parser(subparsers) -> None:
    entity_parser = subparsers.add_parser("entity", help="Manage entities")
    entity_sub = entity_parser.add_subparsers(dest="entity_command")

    # entity add
    add_parser = entity_sub.add_parser("add", help="Create a new entity")
    add_parser.add_argument("name", help="Entity name")
    add_parser.add_argument("--type", required=True, choices=["partner", "person"],
                           dest="entity_type", help="Entity type")
    add_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # entity alias add
    alias_parser = entity_sub.add_parser("alias", help="Manage aliases")
    alias_sub = alias_parser.add_subparsers(dest="alias_command")
    alias_add = alias_sub.add_parser("add", help="Add alias")
    alias_add.add_argument("entity_name", help="Canonical entity name")
    alias_add.add_argument("alias", help="Alias to add")
```

### Anti-Patterns to Avoid
- **Importing sqlite3 outside repository module:** All DB imports must stay in entity/repository.py for future Postgres swap.
- **SQLite-specific SQL features:** Avoid `INSERT OR REPLACE`, `UPSERT` syntax differences, `typeof()`, `json_extract()`. Use standard SQL that works in Postgres too.
- **Autoincrement integer PKs:** Use UUID strings -- they survive database merges and cross-system transfers.
- **Storing Python objects via pickle:** Use JSON for the metadata column; it is human-readable and Postgres-compatible.
- **Opening multiple concurrent write connections:** WAL mode allows concurrent reads but only one writer. Use a single connection or serialize writes.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async SQLite access | Custom thread pool | aiosqlite 0.22.x | Handles thread safety, connection lifecycle, cursor management |
| UUID generation | Custom ID scheme | uuid.uuid4().hex | Collision-proof, merge-safe, standard |
| Config validation | Manual dict checking | Pydantic BaseModel (existing pattern) | Already used project-wide; provides type coercion, defaults, error messages |
| JSON serialization | Custom encoder | json.dumps/loads (stdlib) | Metadata column only needs basic types; Pydantic handles model serialization |
| CLI argument parsing | Custom parser | argparse subparsers (existing pattern) | Already used in main.py for daily/weekly/monthly/discover commands |

**Key insight:** This phase is infrastructure -- the domain logic is simple (CRUD + aliases). The complexity is in getting the foundation right so Phases 20-23 can build on it without rework.

## Common Pitfalls

### Pitfall 1: Forgetting PRAGMA foreign_keys=ON
**What goes wrong:** SQLite does NOT enforce foreign keys by default. organization_id and merge_target_id references silently allow orphaned values.
**Why it happens:** SQLite's default is foreign_keys=OFF for backward compatibility.
**How to avoid:** Execute `PRAGMA foreign_keys=ON` on every new connection, before any queries.
**Warning signs:** Inserting a person with a nonexistent organization_id succeeds without error.

### Pitfall 2: WAL Mode Not Persisting Correctly
**What goes wrong:** WAL mode must be set per-connection in some configurations, or may revert if database is deleted and recreated.
**Why it happens:** WAL mode is stored in the database file but must be set before any transactions begin.
**How to avoid:** Set `PRAGMA journal_mode=WAL` immediately after connecting, before any other operations. Verify the return value -- it should echo "wal".
**Warning signs:** `PRAGMA journal_mode` returns "delete" instead of "wal".

### Pitfall 3: JSON Metadata Column Type Confusion
**What goes wrong:** SQLite stores JSON as TEXT. Inserting a Python dict directly fails; retrieving returns a string, not a dict.
**Why it happens:** No automatic serialization between Python dicts and SQLite TEXT.
**How to avoid:** Always `json.dumps()` on write, `json.loads()` on read. Handle None/NULL explicitly. Use a Pydantic model property or validator for this.
**Warning signs:** Getting `"{'key': 'value'}"` (Python repr) instead of valid JSON.

### Pitfall 4: Soft-Delete Leaking Into Queries
**What goes wrong:** Deleted entities appear in query results because `WHERE deleted_at IS NULL` is forgotten.
**Why it happens:** Every query needs the filter, and it is easy to miss one.
**How to avoid:** All repository query methods should include `AND deleted_at IS NULL` by default. Provide an explicit `include_deleted=False` parameter for admin operations.
**Warning signs:** "Removed" entities still appear in `entity list` output.

### Pitfall 5: Migration Running in Wrong Order or Skipping
**What goes wrong:** Migrations apply out of order or skip a version, leaving schema in inconsistent state.
**Why it happens:** File-based migration ordering relies on naming convention; function-based can have list ordering bugs.
**How to avoid:** Use a simple ordered list of migration functions indexed by version number. Assert that len(MIGRATIONS) equals SCHEMA_VERSION. Run migrations inside a transaction.
**Warning signs:** `PRAGMA user_version` does not match expected version after startup.

### Pitfall 6: Connection Not Closed on Error
**What goes wrong:** Database file stays locked, preventing subsequent operations.
**Why it happens:** Exception interrupts flow before `conn.close()`.
**How to avoid:** Always use context managers (`with` statements) for connections. The repository's connect/close should use `__enter__`/`__exit__` or explicit try/finally.
**Warning signs:** "database is locked" errors on second run.

## Code Examples

### Schema DDL (Initial Migration v0 -> v1)
```sql
-- Source: Derived from CONTEXT.md decisions + standard SQL patterns

CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL CHECK(entity_type IN ('partner', 'person', 'initiative')),
    organization_id TEXT REFERENCES entities(id),
    hubspot_id TEXT,
    slack_channel TEXT,
    metadata TEXT DEFAULT '{}',
    merge_target_id TEXT REFERENCES entities(id),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    deleted_at TEXT
);

CREATE TABLE IF NOT EXISTS aliases (
    id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL REFERENCES entities(id),
    alias TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(alias)
);

CREATE TABLE IF NOT EXISTS entity_mentions (
    id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL REFERENCES entities(id),
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_date TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 1.0 CHECK(confidence >= 0.0 AND confidence <= 1.0),
    context_snippet TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS merge_proposals (
    id TEXT PRIMARY KEY,
    source_entity_id TEXT NOT NULL REFERENCES entities(id),
    target_entity_id TEXT NOT NULL REFERENCES entities(id),
    proposed_by TEXT NOT NULL DEFAULT 'system',
    reason TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS relationships (
    id TEXT PRIMARY KEY,
    from_entity_id TEXT NOT NULL REFERENCES entities(id),
    to_entity_id TEXT NOT NULL REFERENCES entities(id),
    relationship_type TEXT NOT NULL,
    metadata TEXT DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_entities_merge_target ON entities(merge_target_id) WHERE merge_target_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_aliases_entity ON aliases(entity_id);
CREATE INDEX IF NOT EXISTS idx_aliases_alias ON aliases(alias);
CREATE INDEX IF NOT EXISTS idx_mentions_entity ON entity_mentions(entity_id);
CREATE INDEX IF NOT EXISTS idx_mentions_source_date ON entity_mentions(source_date);
CREATE INDEX IF NOT EXISTS idx_merge_proposals_status ON merge_proposals(status) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_relationships_from ON relationships(from_entity_id);
CREATE INDEX IF NOT EXISTS idx_relationships_to ON relationships(to_entity_id);
```

**Note on Postgres compatibility:** The `strftime()` defaults are SQLite-specific but only used as column defaults -- the repository layer should generate timestamps in Python code instead, using `datetime.now(timezone.utc).isoformat()`. This makes the default a safety net, not the primary mechanism.

### EntityConfig Pydantic Model
```python
# Follows existing config.py pattern (extra="forbid", sensible defaults)
class EntityConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    db_path: str = "data/entities.db"
    auto_create: bool = True  # Create DB on first access
```

### Alias Resolution Query
```python
def resolve_name(self, name: str) -> Entity | None:
    """Find entity by canonical name or alias."""
    # Try canonical name first
    row = self._conn.execute(
        "SELECT e.* FROM entities e WHERE e.name = ? AND e.deleted_at IS NULL",
        (name,)
    ).fetchone()
    if row:
        return Entity(**dict(row))

    # Try alias lookup
    row = self._conn.execute(
        """SELECT e.* FROM entities e
           JOIN aliases a ON a.entity_id = e.id
           WHERE a.alias = ? AND e.deleted_at IS NULL""",
        (name,)
    ).fetchone()
    if row:
        return Entity(**dict(row))
    return None
```

### Confidence Scoring Model
```python
class ConfidenceLevel:
    """Confidence levels for entity mentions."""
    HIGH = 1.0    # Direct attribution: "Colin said..."
    MEDIUM = 0.7  # Contextual: mentioned in meeting with known attendees
    LOW = 0.4     # Ambient: name appears in text without clear attribution
    FUZZY = 0.2   # Alias match or partial name match
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Alembic for all Python DB migrations | PRAGMA user_version for single-user SQLite apps | Always was simpler; community consensus 2024+ | Zero dependencies for migration infrastructure |
| SQLAlchemy ORM for everything | Raw sqlite3 + Pydantic models for small apps | Pydantic v2 (2023) made raw SQL + models viable | Cleaner code, fewer abstractions, better type safety |
| Integer autoincrement PKs | UUID string PKs | Growing pattern in distributed/merge-aware systems | Prevents ID collisions in merge scenarios |
| Synchronous sqlite3 only | aiosqlite for async contexts | aiosqlite 0.17+ (2021) became production stable | Fits async pipeline architecture without blocking |

**Deprecated/outdated:**
- pysqlite2: Superseded by stdlib sqlite3 years ago
- aiosqlite < 0.20: Use 0.22.x for Python 3.12+ support

## Open Questions

1. **Timestamp storage format: TEXT ISO-8601 vs INTEGER Unix epoch**
   - What we know: TEXT ISO-8601 is human-readable in sqlite3 CLI and Postgres-compatible. INTEGER is faster for range queries.
   - What's unclear: Performance difference is negligible at this scale (< 10K entities).
   - Recommendation: Use TEXT ISO-8601 for readability and Postgres compatibility. Generate in Python, not via SQLite defaults.

2. **Case sensitivity in alias matching**
   - What we know: SQLite LIKE is case-insensitive for ASCII but not for Unicode. Python's `str.lower()` handles Unicode.
   - What's unclear: Whether aliases like "CR" should match "cr" or "Cr".
   - Recommendation: Store aliases as-is, normalize to lowercase for lookup via `LOWER()` in queries or Python normalization. Store a `alias_normalized` column for indexed case-insensitive lookup.

3. **Connection lifecycle in CLI vs pipeline**
   - What we know: CLI commands are short-lived (open, operate, close). Pipeline runs are longer-lived.
   - What's unclear: Whether to use a single connection for the pipeline run or open/close per operation.
   - Recommendation: CLI opens a fresh connection per command. Pipeline gets a repository instance at startup that holds a connection for the run duration, closed on pipeline completion.

## Sources

### Primary (HIGH confidence)
- [SQLite PRAGMA documentation](https://sqlite.org/pragma.html) - user_version, journal_mode, foreign_keys
- [aiosqlite PyPI](https://pypi.org/project/aiosqlite/) - version 0.22.1, Python 3.9+, production stable
- [aiosqlite GitHub](https://github.com/omnilib/aiosqlite) - API surface, usage patterns

### Secondary (MEDIUM confidence)
- [SQLite DB Migrations with PRAGMA user_version](https://levlaz.org/sqlite-db-migrations-with-pragma-user_version/) - Migration function pattern
- [Returning Pydantic Models from SQLite3 Queries](https://nickgeorge.net/pydantic-sqlite3/) - Row factory pattern
- [suckless SQLite schema migrations in Python](https://eskerda.com/sqlite-schema-migrations-python/) - Alternative migration approaches
- [Going Fast with SQLite and Python](https://charlesleifer.com/blog/going-fast-with-sqlite-and-python/) - WAL mode, performance tuning

### Tertiary (LOW confidence)
- None -- all findings verified against official docs or multiple sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - sqlite3 is stdlib, aiosqlite is well-established, project already uses Pydantic
- Architecture: HIGH - Repository pattern is standard; migration approach verified against multiple sources; follows existing project conventions
- Pitfalls: HIGH - Foreign keys, WAL mode, soft-delete filtering are well-documented SQLite pitfalls

**Research date:** 2026-04-05
**Valid until:** 2026-05-05 (stable domain, unlikely to change)
