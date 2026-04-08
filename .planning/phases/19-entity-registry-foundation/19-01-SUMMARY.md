---
phase: 19-entity-registry-foundation
plan: 01
subsystem: database
tags: [sqlite, pydantic, entity-registry, migrations]

requires:
  - phase: 11-pipeline-hardening
    provides: stable pipeline foundation
provides:
  - Entity, Alias, EntityMention, MergeProposal, ConfidenceLevel Pydantic models
  - SQLite schema v1 with 5 tables and indexes
  - PRAGMA user_version migration system
  - get_connection / get_connection_from_config with WAL mode and graceful degradation
  - EntityConfig added to PipelineConfig
affects: [19-02-repository-cli, 20-entity-discovery, 21-entity-attribution, 22-merge-split, 23-scoped-views]

tech-stack:
  added: []
  patterns: [PRAGMA user_version migrations, WAL mode connections, graceful DB degradation]

key-files:
  created: [src/entity/__init__.py, src/entity/models.py, src/entity/migrations.py, src/entity/db.py, tests/test_entity_models.py, tests/test_entity_migrations.py]
  modified: [src/config.py]

key-decisions:
  - "PRAGMA user_version for schema versioning — simple, no external migration tool"
  - "get_connection_from_config returns None on failure for graceful degradation"
  - "All timestamps generated in Python via _now_utc(), not SQLite strftime"
  - "ConfidenceLevel as plain class with float constants, not enum"

patterns-established:
  - "Entity DB pattern: get_connection_from_config wraps connection with auto-migrate + graceful fallback"
  - "Migration ordering: MIGRATIONS list length must equal SCHEMA_VERSION (assert at module level)"
---

# Plan 19-01: Entity Models, Schema, and Database Foundation

**One-liner:** SQLite entity registry with 5-table schema, Pydantic models, PRAGMA-based migrations, and graceful degradation via get_connection_from_config

## What Was Built
- `src/entity/models.py` — Pydantic models: Entity, Alias, EntityMention, MergeProposal, ConfidenceLevel with metadata JSON deserialization validator
- `src/entity/migrations.py` — Schema v1 creates entities, aliases, entity_mentions, merge_proposals, relationships tables with indexes; PRAGMA user_version versioning
- `src/entity/db.py` — get_connection (WAL mode, foreign keys, auto-migrate, auto-create dirs) and get_connection_from_config (graceful degradation)
- `src/config.py` — EntityConfig(enabled=True, db_path="data/entities.db", auto_create=True) added to PipelineConfig

## Key Files
- `src/entity/models.py` — All entity Pydantic models
- `src/entity/migrations.py` — Schema versioning and DDL
- `src/entity/db.py` — Connection factory with WAL + auto-migration
- `tests/test_entity_models.py` — Model validation tests
- `tests/test_entity_migrations.py` — Schema and connection tests

## Decisions Made
- Used PRAGMA user_version for schema versioning — simple, no external migration tool needed
- get_connection_from_config returns None on failure for graceful degradation in pipeline
- All timestamps generated in Python via _now_utc(), not SQLite strftime
- ConfidenceLevel as plain class with float constants (HIGH=1.0, MEDIUM=0.7, LOW=0.4, FUZZY=0.2)

## Deviations from Plan
None — followed plan as specified.

## Issues Encountered
None.

## Next Phase Readiness
- Schema and models ready for repository layer (Plan 19-02)
- get_connection_from_config ready for pipeline integration

---
*Phase: 19-entity-registry-foundation*
*Completed: 2026-04-08 (retroactive)*
