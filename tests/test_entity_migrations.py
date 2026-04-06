"""Tests for entity registry schema migrations and database connection."""

from __future__ import annotations

import sqlite3

import pytest

from src.config import EntityConfig
from src.entity.db import get_connection, get_connection_from_config
from src.entity.migrations import MIGRATIONS, SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Migration tests
# ---------------------------------------------------------------------------


class TestMigrations:
    """Verify schema migration infrastructure."""

    def test_schema_version_matches_migrations(self) -> None:
        assert SCHEMA_VERSION == len(MIGRATIONS)

    def test_fresh_db_gets_all_tables(self, tmp_path: object) -> None:
        db_path = str(tmp_path / "test.db")
        conn = get_connection(db_path)
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        expected = {"entities", "aliases", "entity_mentions", "merge_proposals", "relationships"}
        assert expected.issubset(tables)
        conn.close()

    def test_pragma_user_version_is_1(self, tmp_path: object) -> None:
        db_path = str(tmp_path / "test.db")
        conn = get_connection(db_path)
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == 1
        conn.close()

    def test_idempotent_migration(self, tmp_path: object) -> None:
        db_path = str(tmp_path / "test.db")
        conn1 = get_connection(db_path)
        conn1.close()
        # Re-open — migrations should be a no-op
        conn2 = get_connection(db_path)
        version = conn2.execute("PRAGMA user_version").fetchone()[0]
        assert version == 1
        conn2.close()

    def test_wal_mode_enabled(self, tmp_path: object) -> None:
        db_path = str(tmp_path / "test.db")
        conn = get_connection(db_path)
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal"
        conn.close()

    def test_foreign_keys_enabled(self, tmp_path: object) -> None:
        db_path = str(tmp_path / "test.db")
        conn = get_connection(db_path)
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1
        conn.close()

    def test_entity_table_columns(self, tmp_path: object) -> None:
        db_path = str(tmp_path / "test.db")
        conn = get_connection(db_path)
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(entities)").fetchall()
        }
        expected = {
            "id", "name", "entity_type", "organization_id", "hubspot_id",
            "slack_channel", "metadata", "merge_target_id",
            "created_at", "updated_at", "deleted_at",
        }
        assert expected == columns
        conn.close()

    def test_expected_indexes_exist(self, tmp_path: object) -> None:
        db_path = str(tmp_path / "test.db")
        conn = get_connection(db_path)
        indexes = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
            ).fetchall()
        }
        assert "idx_entities_type" in indexes
        assert "idx_aliases_alias" in indexes
        assert "idx_mentions_entity" in indexes
        conn.close()


# ---------------------------------------------------------------------------
# Connection factory tests
# ---------------------------------------------------------------------------


class TestGetConnection:
    """Verify get_connection behaviour."""

    def test_auto_creates_parent_dir(self, tmp_path: object) -> None:
        db_path = str(tmp_path / "nested" / "deep" / "test.db")
        conn = get_connection(db_path)
        assert conn is not None
        conn.close()

    def test_raises_when_auto_create_false(self, tmp_path: object) -> None:
        db_path = str(tmp_path / "nonexistent" / "test.db")
        with pytest.raises(FileNotFoundError):
            get_connection(db_path, auto_create=False)


class TestGetConnectionFromConfig:
    """Verify config-driven connection with graceful degradation."""

    def test_returns_none_when_disabled(self) -> None:
        config = EntityConfig(enabled=False)
        assert get_connection_from_config(config) is None

    def test_returns_connection_when_enabled(self, tmp_path: object) -> None:
        config = EntityConfig(enabled=True, db_path=str(tmp_path / "test.db"))
        conn = get_connection_from_config(config)
        assert conn is not None
        conn.close()

    def test_graceful_degradation_on_invalid_path(self) -> None:
        config = EntityConfig(
            enabled=True,
            db_path="/nonexistent/readonly/path/test.db",
            auto_create=True,
        )
        # Should return None, not raise
        result = get_connection_from_config(config)
        assert result is None
