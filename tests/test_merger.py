"""Tests for entity merge proposal generation and repository extensions."""

from __future__ import annotations

import pytest

from src.entity.merger import execute_merge, execute_split, generate_proposals, score_pair
from src.entity.models import MergeProposal, _now_utc
from src.entity.repository import EntityRepository


def _make_repo(tmp_path: object) -> EntityRepository:
    """Create a connected repository with a fresh test database."""
    repo = EntityRepository(str(tmp_path / "test.db"))
    repo.connect()
    return repo


def _add_mention(repo: EntityRepository, entity_id: str, source_type: str = "gmail",
                 source_id: str = "msg-1", source_date: str = "2026-04-01") -> None:
    """Insert a mention directly into the database."""
    from uuid import uuid4
    repo._conn.execute(
        "INSERT INTO entity_mentions (id, entity_id, source_type, source_id, source_date, confidence, created_at) "
        "VALUES (?, ?, ?, ?, ?, 1.0, ?)",
        (uuid4().hex, entity_id, source_type, source_id, source_date, _now_utc()),
    )
    repo._conn.commit()


# ---------------------------------------------------------------------------
# score_pair
# ---------------------------------------------------------------------------


class TestScorePair:
    def test_identical_names(self) -> None:
        assert score_pair("Affirm", "Affirm") == 100.0

    def test_similar_names(self) -> None:
        score = score_pair("Affirm Inc", "Affirm")
        assert score >= 80

    def test_different_names(self) -> None:
        score = score_pair("Affirm", "Cherry Financial")
        assert score < 80

    def test_normalizes_before_scoring(self) -> None:
        # "Affirm Inc" and "Affirm Inc." should normalize to same base
        score = score_pair("Affirm Inc", "Affirm Inc.")
        assert score >= 95


# ---------------------------------------------------------------------------
# generate_proposals
# ---------------------------------------------------------------------------


class TestGenerateProposals:
    def test_same_type_only(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        repo.add_entity("Affirm", "partner")
        repo.add_entity("Affirm Inc", "partner")
        repo.add_entity("Affirm Corp", "person")  # same name but different type
        proposals = generate_proposals(repo)
        # Only partner-partner pair should appear
        assert len(proposals) == 1
        types = {proposals[0]["source_entity"].entity_type, proposals[0]["target_entity"].entity_type}
        assert types == {"partner"}
        repo.close()

    def test_above_threshold(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        repo.add_entity("Affirm", "partner")
        repo.add_entity("Affirm Inc", "partner")
        repo.add_entity("Cherry Financial", "partner")
        proposals = generate_proposals(repo)
        # Only Affirm pair should match (>= 80)
        assert len(proposals) == 1
        names = {proposals[0]["source_entity"].name, proposals[0]["target_entity"].name}
        assert names == {"Affirm", "Affirm Inc"}
        repo.close()

    def test_excludes_rejected(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        e1 = repo.add_entity("Affirm", "partner")
        e2 = repo.add_entity("Affirm Inc", "partner")
        # Insert a rejected proposal
        repo.save_proposal(e1.id, e2.id, reason="rejected by user", status="rejected")
        proposals = generate_proposals(repo)
        assert len(proposals) == 0
        repo.close()

    def test_excludes_merged(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        e1 = repo.add_entity("Affirm", "partner")
        e2 = repo.add_entity("Affirm Inc", "partner")
        # Simulate merge: set merge_target_id on e2
        repo._conn.execute(
            "UPDATE entities SET merge_target_id = ? WHERE id = ?",
            (e1.id, e2.id),
        )
        repo._conn.commit()
        proposals = generate_proposals(repo)
        assert len(proposals) == 0
        repo.close()

    def test_excludes_deleted(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        repo.add_entity("Affirm", "partner")
        e2 = repo.add_entity("Affirm Inc", "partner")
        repo.remove_entity(e2.id)  # soft-delete
        proposals = generate_proposals(repo)
        assert len(proposals) == 0
        repo.close()

    def test_respects_limit(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        # Create several similar pairs
        for i in range(6):
            repo.add_entity(f"TestCo {i}", "partner")
            repo.add_entity(f"TestCo {i} Inc", "partner")
        proposals = generate_proposals(repo, limit=2)
        assert len(proposals) <= 2
        repo.close()

    def test_includes_mention_context(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        e1 = repo.add_entity("Affirm", "partner")
        e2 = repo.add_entity("Affirm Inc", "partner")
        _add_mention(repo, e1.id, "gmail", "msg-1")
        _add_mention(repo, e1.id, "slack", "msg-2")
        _add_mention(repo, e2.id, "gmail", "msg-3")
        proposals = generate_proposals(repo)
        assert len(proposals) == 1
        p = proposals[0]
        # Target should be e1 (more mentions: 2 vs 1)
        assert p["target_entity"].id == e1.id
        assert p["target_context"]["mention_count"] == 2
        assert set(p["target_context"]["source_types"]) == {"gmail", "slack"}
        assert p["source_context"]["mention_count"] == 1
        repo.close()

    def test_checks_both_orderings(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        e1 = repo.add_entity("Affirm", "partner")
        e2 = repo.add_entity("Affirm Inc", "partner")
        # Reject with reversed ordering (e2, e1 instead of e1, e2)
        repo.save_proposal(e2.id, e1.id, reason="rejected", status="rejected")
        proposals = generate_proposals(repo)
        assert len(proposals) == 0
        repo.close()


# ---------------------------------------------------------------------------
# Repository extensions
# ---------------------------------------------------------------------------


class TestRepositoryExtensions:
    def test_get_mention_count(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        e = repo.add_entity("Affirm", "partner")
        assert repo.get_mention_count(e.id) == 0
        _add_mention(repo, e.id, "gmail")
        _add_mention(repo, e.id, "slack")
        assert repo.get_mention_count(e.id) == 2
        repo.close()

    def test_get_mention_sources(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        e = repo.add_entity("Affirm", "partner")
        _add_mention(repo, e.id, "gmail", "msg-1")
        _add_mention(repo, e.id, "gmail", "msg-2")
        _add_mention(repo, e.id, "slack", "msg-3")
        sources = repo.get_mention_sources(e.id)
        assert set(sources) == {"gmail", "slack"}
        repo.close()

    def test_save_proposal(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        e1 = repo.add_entity("Affirm", "partner")
        e2 = repo.add_entity("Affirm Inc", "partner")
        proposal = repo.save_proposal(e1.id, e2.id, reason="test", status="pending")
        assert proposal.source_entity_id == e1.id
        assert proposal.target_entity_id == e2.id
        assert proposal.status == "pending"
        assert proposal.reason == "test"
        repo.close()

    def test_get_existing_proposals(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        e1 = repo.add_entity("Affirm", "partner")
        e2 = repo.add_entity("Affirm Inc", "partner")
        repo.save_proposal(e1.id, e2.id, reason="test", status="rejected")
        # Forward ordering
        existing = repo.get_existing_proposals(e1.id, e2.id)
        assert len(existing) == 1
        # Reverse ordering also finds it
        existing_rev = repo.get_existing_proposals(e2.id, e1.id)
        assert len(existing_rev) == 1
        repo.close()

    def test_update_proposal_status(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        e1 = repo.add_entity("Affirm", "partner")
        e2 = repo.add_entity("Affirm Inc", "partner")
        proposal = repo.save_proposal(e1.id, e2.id, reason="test", status="pending")
        assert repo.update_proposal_status(proposal.id, "approved")
        # Verify status changed
        row = repo._conn.execute(
            "SELECT status, resolved_at FROM merge_proposals WHERE id = ?",
            (proposal.id,),
        ).fetchone()
        assert row["status"] == "approved"
        assert row["resolved_at"] is not None
        repo.close()


# ---------------------------------------------------------------------------
# Merge execution
# ---------------------------------------------------------------------------


class TestExecuteMerge:
    def test_soft_deletes_source(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        source = repo.add_entity("Affirm Inc", "partner")
        target = repo.add_entity("Affirm", "partner")
        execute_merge(repo, source.id, target.id)
        # Source should be soft-deleted with merge_target_id
        row = repo._conn.execute(
            "SELECT deleted_at, merge_target_id FROM entities WHERE id = ?",
            (source.id,),
        ).fetchone()
        assert row["deleted_at"] is not None
        assert row["merge_target_id"] == target.id
        repo.close()

    def test_reassigns_mentions(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        source = repo.add_entity("Affirm Inc", "partner")
        target = repo.add_entity("Affirm", "partner")
        _add_mention(repo, source.id, "gmail", "msg-1")
        _add_mention(repo, source.id, "slack", "msg-2")
        _add_mention(repo, target.id, "gmail", "msg-3")
        execute_merge(repo, source.id, target.id)
        # All mentions should now be on target
        assert repo.get_mention_count(target.id) == 3
        assert repo.get_mention_count(source.id) == 0
        repo.close()

    def test_transfers_aliases(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        source = repo.add_entity("Affirm Inc", "partner")
        target = repo.add_entity("Affirm", "partner")
        repo.add_alias(source.id, "Afm")
        execute_merge(repo, source.id, target.id)
        # Alias should now be on target
        target_aliases = repo.list_aliases(target.id)
        alias_names = [a.alias for a in target_aliases]
        assert "Afm" in alias_names
        repo.close()

    def test_adds_source_name_as_alias(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        source = repo.add_entity("Affirm Inc", "partner")
        target = repo.add_entity("Affirm", "partner")
        execute_merge(repo, source.id, target.id)
        target_aliases = repo.list_aliases(target.id)
        alias_names = [a.alias for a in target_aliases]
        assert "Affirm Inc" in alias_names
        repo.close()

    def test_handles_alias_collision(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        source = repo.add_entity("Affirm Inc", "partner")
        target = repo.add_entity("Affirm", "partner")
        # Pre-add "Affirm Inc" as alias on target -- should not crash on merge
        repo.add_alias(target.id, "Affirm Inc")
        execute_merge(repo, source.id, target.id)  # Should not raise
        repo.close()

    def test_creates_approved_proposal(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        source = repo.add_entity("Affirm Inc", "partner")
        target = repo.add_entity("Affirm", "partner")
        execute_merge(repo, source.id, target.id, score=95.0)
        existing = repo.get_existing_proposals(source.id, target.id)
        assert len(existing) == 1
        assert existing[0].status == "approved"
        repo.close()


# ---------------------------------------------------------------------------
# Split reversal
# ---------------------------------------------------------------------------


class TestExecuteSplit:
    def test_restores_entity(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        source = repo.add_entity("Affirm Inc", "partner")
        target = repo.add_entity("Affirm", "partner")
        execute_merge(repo, source.id, target.id)
        execute_split(repo, source.id)
        # Source should be restored
        restored = repo.get_by_id(source.id)
        assert restored is not None
        assert restored.deleted_at is None
        assert restored.merge_target_id is None
        repo.close()

    def test_reattributes_mentions(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        source = repo.add_entity("Affirm Inc", "partner")
        target = repo.add_entity("Affirm", "partner")
        _add_mention(repo, source.id, "gmail", "msg-1")
        _add_mention(repo, source.id, "gmail", "msg-2")
        _add_mention(repo, target.id, "slack", "msg-3")
        # Before merge: source=2, target=1
        execute_merge(repo, source.id, target.id)
        # After merge: target=3, source=0
        assert repo.get_mention_count(target.id) == 3
        execute_split(repo, source.id)
        # After split: source's 2 original mentions should be restored
        source_count = repo.get_mention_count(source.id)
        target_count = repo.get_mention_count(target.id)
        assert source_count + target_count == 3
        assert source_count == 2  # exactly the 2 mentions that were originally on source
        assert target_count == 1  # the 1 mention that was originally on target
        repo.close()

    def test_returns_aliases(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        source = repo.add_entity("Affirm Inc", "partner")
        target = repo.add_entity("Affirm", "partner")
        repo.add_alias(source.id, "Afm")
        execute_merge(repo, source.id, target.id)
        # After merge: "Afm" and "Affirm Inc" are aliases on target
        execute_split(repo, source.id)
        # After split: "Affirm Inc" alias should be removed from target
        target_aliases = [a.alias for a in repo.list_aliases(target.id)]
        assert "Affirm Inc" not in target_aliases
        repo.close()

    def test_entity_not_merged_raises(self, tmp_path: object) -> None:
        repo = _make_repo(tmp_path)
        e = repo.add_entity("Affirm", "partner")
        with pytest.raises(ValueError, match="never merged"):
            execute_split(repo, e.id)
        repo.close()

    def test_end_to_end_merge_and_split(self, tmp_path: object) -> None:
        """Integration test: full merge -> split cycle."""
        repo = _make_repo(tmp_path)
        source = repo.add_entity("Affirm Inc", "partner")
        target = repo.add_entity("Affirm", "partner")
        repo.add_alias(source.id, "Afm")
        _add_mention(repo, source.id, "gmail", "msg-1")
        _add_mention(repo, target.id, "slack", "msg-2")

        # Pre-merge state
        assert repo.get_mention_count(source.id) == 1
        assert repo.get_mention_count(target.id) == 1
        assert len(repo.list_aliases(source.id)) == 1  # "Afm"

        # Merge
        execute_merge(repo, source.id, target.id, score=95.0)
        assert repo.get_by_id(source.id) is None  # soft-deleted
        assert repo.get_mention_count(target.id) == 2  # consolidated

        # Split
        execute_split(repo, source.id)
        restored = repo.get_by_id(source.id)
        assert restored is not None
        assert restored.name == "Affirm Inc"
        assert restored.merge_target_id is None
        # Total mentions should still be 2
        total = repo.get_mention_count(source.id) + repo.get_mention_count(target.id)
        assert total == 2
        repo.close()
