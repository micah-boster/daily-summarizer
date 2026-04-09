"""Schema versioning and migration infrastructure for the entity registry.

Uses SQLite PRAGMA user_version to track schema versions. Migrations are
hand-written SQL functions applied in order on each connection open.
"""

from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 3


def _get_version(conn: sqlite3.Connection) -> int:
    """Read the current schema version from PRAGMA user_version."""
    return conn.execute("PRAGMA user_version").fetchone()[0]


def _set_version(conn: sqlite3.Connection, version: int) -> None:
    """Set the schema version via PRAGMA user_version."""
    conn.execute("PRAGMA user_version = %d" % version)


def _migrate_v0_to_v1(conn: sqlite3.Connection) -> None:
    """Create initial entity registry schema (5 tables + indexes)."""
    conn.executescript(
        """
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
        """
    )


def _migrate_v1_to_v2(conn: sqlite3.Connection) -> None:
    """Add backfill_progress table for tracking backfill state."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS backfill_progress (
            id TEXT PRIMARY KEY,
            source_date TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'completed'
                CHECK(status IN ('completed', 'failed', 'skipped')),
            entities_found INTEGER DEFAULT 0,
            processed_at TEXT NOT NULL
                DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        );

        CREATE INDEX IF NOT EXISTS idx_backfill_date
            ON backfill_progress(source_date);
        """
    )


def _migrate_v2_to_v3(conn: sqlite3.Connection) -> None:
    """Add pipeline_runs table for tracking pipeline execution history."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            id TEXT PRIMARY KEY,
            target_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'running',
            stages_json TEXT,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            duration_s REAL,
            error_message TEXT,
            error_stage TEXT,
            pid INTEGER
        );

        CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status
            ON pipeline_runs(status);
        CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started
            ON pipeline_runs(started_at DESC);
        """
    )


# Ordered list of migration functions. Index + 1 = target version.
MIGRATIONS: list = [
    _migrate_v0_to_v1,
    _migrate_v1_to_v2,
    _migrate_v2_to_v3,
]

# Safety check: migration count must match declared schema version.
assert len(MIGRATIONS) == SCHEMA_VERSION, (
    "MIGRATIONS list length (%d) does not match SCHEMA_VERSION (%d)"
    % (len(MIGRATIONS), SCHEMA_VERSION)
)


def run_migrations(conn: sqlite3.Connection) -> None:
    """Apply any pending migrations to bring the database up to date.

    Checks the current PRAGMA user_version and applies each migration
    function whose target version exceeds the current version. Each
    migration is committed individually.
    """
    current = _get_version(conn)
    for i, migration in enumerate(MIGRATIONS):
        target = i + 1
        if target > current:
            migration(conn)
            _set_version(conn, target)
            conn.commit()
