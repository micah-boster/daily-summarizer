"""Tests for EntityRepository CRUD, alias management, and name resolution."""

from __future__ import annotations

import pytest

from src.entity.repository import EntityRepository


def _make_repo(tmp_path: object) -> EntityRepository:
    """Create a connected repository with a fresh test database."""
    repo = EntityRepository(str(tmp_path / "test.db"))
    repo.connect()
    return repo


# ---------------------------------------------------------------------------
# Entity CRUD
# ---------------------------------------------------------------------------


class TestEntityCRUD:
    def test_add_entity_creates_and_returns(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        entity = repo.add_entity("Affirm", "partner")
        assert entity.name == "Affirm"
        assert entity.entity_type == "partner"
        assert entity.id
        assert entity.created_at
        repo.close()

    def test_add_entity_generates_unique_ids(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        e1 = repo.add_entity("Affirm", "partner")
        e2 = repo.add_entity("Cherry", "partner")
        assert e1.id != e2.id
        repo.close()

    def test_add_entity_empty_name_raises(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        with pytest.raises(ValueError, match="must not be empty"):
            repo.add_entity("", "partner")
        repo.close()

    def test_get_by_id_returns_entity(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        created = repo.add_entity("Affirm", "partner")
        found = repo.get_by_id(created.id)
        assert found is not None
        assert found.name == "Affirm"
        repo.close()

    def test_get_by_id_returns_none_for_missing(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        assert repo.get_by_id("nonexistent") is None
        repo.close()

    def test_get_by_name_case_insensitive(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        repo.add_entity("Affirm", "partner")
        found = repo.get_by_name("affirm")
        assert found is not None
        assert found.name == "Affirm"
        repo.close()

    def test_list_entities_all(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        repo.add_entity("Affirm", "partner")
        repo.add_entity("Cherry", "partner")
        repo.add_entity("Colin", "person")
        entities = repo.list_entities()
        assert len(entities) == 3
        repo.close()

    def test_list_entities_by_type(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        repo.add_entity("Affirm", "partner")
        repo.add_entity("Colin", "person")
        partners = repo.list_entities(entity_type="partner")
        assert len(partners) == 1
        assert partners[0].name == "Affirm"
        repo.close()

    def test_list_entities_excludes_deleted(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        e1 = repo.add_entity("Affirm", "partner")
        repo.add_entity("Cherry", "partner")
        repo.remove_entity(e1.id)
        entities = repo.list_entities()
        assert len(entities) == 1
        assert entities[0].name == "Cherry"
        repo.close()

    def test_remove_entity_soft_deletes(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        entity = repo.add_entity("Affirm", "partner")
        result = repo.remove_entity(entity.id)
        assert result is True
        # Should not appear in normal list
        assert repo.get_by_id(entity.id) is None
        # Should appear with include_deleted
        all_entities = repo.list_entities(include_deleted=True)
        assert any(e.id == entity.id and e.deleted_at is not None for e in all_entities)
        repo.close()

    def test_remove_entity_returns_false_for_missing(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        assert repo.remove_entity("nonexistent") is False
        repo.close()

    def test_entity_metadata_roundtrip(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        meta = {"industry": "fintech", "tier": 1}
        entity = repo.add_entity("Affirm", "partner", metadata=meta)
        found = repo.get_by_id(entity.id)
        assert found.metadata == meta
        repo.close()


# ---------------------------------------------------------------------------
# Alias management
# ---------------------------------------------------------------------------


class TestAliasManagement:
    def test_add_alias_and_list(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        entity = repo.add_entity("Colin Roberts", "person")
        alias = repo.add_alias(entity.id, "CR")
        assert alias.alias == "CR"
        aliases = repo.list_aliases(entity.id)
        assert len(aliases) == 1
        assert aliases[0].alias == "CR"
        repo.close()

    def test_add_duplicate_alias_raises(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        entity = repo.add_entity("Colin Roberts", "person")
        repo.add_alias(entity.id, "CR")
        with pytest.raises(ValueError, match="already exists"):
            repo.add_alias(entity.id, "CR")
        repo.close()

    def test_remove_alias(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        entity = repo.add_entity("Colin Roberts", "person")
        repo.add_alias(entity.id, "CR")
        result = repo.remove_alias("CR")
        assert result is True
        assert repo.list_aliases(entity.id) == []
        repo.close()

    def test_remove_alias_case_insensitive(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        entity = repo.add_entity("Colin Roberts", "person")
        repo.add_alias(entity.id, "CR")
        result = repo.remove_alias("cr")
        assert result is True
        repo.close()


# ---------------------------------------------------------------------------
# Name resolution
# ---------------------------------------------------------------------------


class TestNameResolution:
    def test_resolve_by_canonical_name(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        repo.add_entity("Affirm", "partner")
        resolved = repo.resolve_name("Affirm")
        assert resolved is not None
        assert resolved.name == "Affirm"
        repo.close()

    def test_resolve_by_alias(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        entity = repo.add_entity("Colin Roberts", "person")
        repo.add_alias(entity.id, "CR")
        resolved = repo.resolve_name("CR")
        assert resolved is not None
        assert resolved.name == "Colin Roberts"
        repo.close()

    def test_resolve_case_insensitive(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        entity = repo.add_entity("Colin Roberts", "person")
        repo.add_alias(entity.id, "CR")
        resolved = repo.resolve_name("cr")
        assert resolved is not None
        assert resolved.name == "Colin Roberts"
        repo.close()

    def test_resolve_returns_none_for_unknown(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        assert repo.resolve_name("Unknown") is None
        repo.close()

    def test_resolve_follows_merge_target(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        target = repo.add_entity("Colin Roberts", "person")
        source = repo.add_entity("C. Roberts", "person")
        # Set merge target directly in DB
        repo._conn.execute(
            "UPDATE entities SET merge_target_id = ? WHERE id = ?",
            (target.id, source.id),
        )
        repo._conn.commit()
        resolved = repo.resolve_name("C. Roberts")
        assert resolved is not None
        assert resolved.id == target.id
        repo.close()


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


class TestContextManager:
    def test_context_manager_opens_and_closes(self, tmp_path: object) -> None:
        with EntityRepository(str(tmp_path / "test.db")) as repo:
            entity = repo.add_entity("Affirm", "partner")
            assert entity.name == "Affirm"
        # Connection should be closed after exiting context
        assert repo._conn is None
