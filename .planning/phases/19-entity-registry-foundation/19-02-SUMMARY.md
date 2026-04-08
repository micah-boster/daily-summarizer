---
phase: 19-entity-registry-foundation
plan: 02
subsystem: database
tags: [sqlite, entity-registry, cli, repository-pattern]

requires:
  - phase: 19-01
    provides: Entity models, schema, db connection
provides:
  - EntityRepository with CRUD, alias management, and name resolution
  - CLI commands: entity add/list/show/remove/alias add/list/remove
  - Case-insensitive alias resolution with merge target following
  - data/ and *.db gitignored
affects: [20-entity-discovery, 21-entity-attribution, 22-merge-split, 23-scoped-views]

tech-stack:
  added: []
  patterns: [repository pattern for entity data access, CLI subparser registration]

key-files:
  created: [src/entity/repository.py, src/entity/cli.py, tests/test_entity_repository.py, tests/test_entity_cli.py]
  modified: [src/main.py, .gitignore]

key-decisions:
  - "Repository pattern with context manager for connection lifecycle"
  - "Soft-delete via deleted_at timestamp, never hard delete"
  - "Two-step name resolution: canonical name first, then alias lookup"
  - "Merge target following is one level only (no recursive chain)"
  - "Case-insensitive matching via LOWER() in SQL"

patterns-established:
  - "Entity repository pattern: EntityRepository(db_path) with context manager, used by all entity features"
  - "CLI subparser pattern: register_entity_parser + handle_entity_command wired into main.py"
---

# Plan 19-02: Entity Repository, CLI, and Main Integration

**One-liner:** EntityRepository with full CRUD + alias management + two-step name resolution, CLI commands wired into main.py, data/ gitignored

## What Was Built
- `src/entity/repository.py` — EntityRepository class with add/get/list/remove entities, add/remove/list aliases, resolve_name (canonical then alias with merge target following)
- `src/entity/cli.py` — CLI subparser for entity management with human-readable and --json output
- `src/main.py` — entity subcommand registered and dispatched
- `.gitignore` — data/ and *.db exclusions

## Key Files
- `src/entity/repository.py` — Data access layer for all entity operations
- `src/entity/cli.py` — CLI handlers for entity management
- `tests/test_entity_repository.py` — Repository CRUD and resolution tests
- `tests/test_entity_cli.py` — CLI handler tests

## Decisions Made
- Repository pattern with context manager for connection lifecycle
- Soft-delete via deleted_at timestamp (never hard delete)
- Two-step name resolution: canonical name first, then alias lookup
- Merge target following limited to one level (no recursive chain)

## Deviations from Plan
None — followed plan as specified.

## Issues Encountered
None.

## Next Phase Readiness
- Entity registry fully operational via CLI
- EntityRepository ready for programmatic use by discovery (Phase 20) and attribution (Phase 21)

---
*Phase: 19-entity-registry-foundation*
*Completed: 2026-04-08 (retroactive)*
