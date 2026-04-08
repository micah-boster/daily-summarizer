# Phase 19: Entity Registry Foundation - Context

**Gathered:** 2026-04-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Persistent SQLite storage for partner and people entities with alias management, confidence scoring model, CLI commands, and schema migration infrastructure. This is the foundation layer — no discovery, attribution, or views in this phase.

</domain>

<decisions>
## Implementation Decisions

### Database Location & Lifecycle
- DB path configurable in config.yaml, default `data/entities.db`
- Auto-create DB on first access (no explicit init command needed)
- Graceful degradation: pipeline runs without entity features if DB is unavailable or corrupted
- `data/` directory and `*.db` files added to .gitignore (personal data, binary format)
- WAL mode enabled for async compatibility

### CLI Command Design
- Subcommand style: `python -m src.main entity add/list/alias/show/remove`
- Output: human-readable table by default, `--json` flag for structured output
- Entity type is required: `--type partner` or `--type person`
- Soft-delete on remove (mark deleted_at timestamp, can be restored)

### Entity Type Modeling
- Single `entities` table with `entity_type` column ('partner', 'person', 'initiative')
- Minimal typed columns: name, entity_type, organization_id (optional, links person → partner), external IDs (hubspot_id, slack_channel)
- JSON `metadata` column for extensible key-value pairs (future fields without schema migration)
- People have optional `organization_id` foreign key referencing a partner entity
- Soft-delete via `deleted_at` timestamp column
- `merge_target_id` column baked in from day one for future merge support

### Schema Forward-Compatibility
- Full schema created in Phase 19: entities, aliases, entity_mentions, merge_proposals, relationships tables
- Tables for later phases sit empty until needed — avoids migrations in Phases 20-22
- 'initiative' included in entity_type enum from day one (feature deferred to v2.1)
- Simple migration approach: PRAGMA user_version + hand-written SQL migration functions (no Alembic/SQLAlchemy)

### Claude's Discretion
- Exact schema DDL and column types
- Migration function structure and versioning approach
- Repository pattern design for data access layer
- Pydantic model field naming and validation rules
- Table indexing strategy
- WAL mode configuration details
- CLI argument parsing implementation (argparse subparsers)

</decisions>

<specifics>
## Specific Ideas

- Follow existing project pattern: Pydantic models for entity data, config validation at startup
- Repository layer should abstract SQLite access (clean swap path to Postgres at v5.0)
- Keep all `sqlite3`/`aiosqlite` imports confined to the repository module
- Standard SQL only — avoid SQLite-specific features that don't exist in Postgres

</specifics>

<deferred>
## Deferred Ideas

- Initiative tracking feature — v2.1 (schema slot reserved in entity_type enum)
- Seed file for bootstrapping known entities (config/entities.yaml) — consider for Phase 20
- Entity import/export for backup — future enhancement

</deferred>

---

*Phase: 19-entity-registry-foundation*
*Context gathered: 2026-04-05*
