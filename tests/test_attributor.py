"""Tests for entity attribution: matching, hashing, persistence, sidecar enrichment."""

from __future__ import annotations

import sqlite3

import pytest

from src.entity.db import get_connection
from src.entity.models import Entity, EntityMention, EntityType
from src.entity.repository import EntityRepository
from src.synthesis.models import CommitmentRow, DailySynthesisOutput, SynthesisItem


def _make_repo(tmp_path) -> EntityRepository:
    """Create a connected repository with a fresh test database."""
    repo = EntityRepository(str(tmp_path / "test.db"))
    repo.connect()
    return repo


def _seed_entities(repo: EntityRepository) -> dict[str, Entity]:
    """Seed test entities and return mapping by name."""
    affirm = repo.add_entity("Affirm", "partner")
    colin = repo.add_entity("Colin Roberts", "person")
    project_alpha = repo.add_entity("Project Alpha", "initiative")
    # Add alias for Affirm (use a name that won't normalize to "affirm")
    repo.add_alias(affirm.id, "Affirm Financial")
    return {"Affirm": affirm, "Colin Roberts": colin, "Project Alpha": project_alpha}


# ---------------------------------------------------------------------------
# Content hashing
# ---------------------------------------------------------------------------


class TestContentHash:
    def test_content_hash_deterministic(self) -> None:
        from src.entity.attributor import content_hash

        h1 = content_hash("hello world")
        h2 = content_hash("hello world")
        assert h1 == h2
        assert len(h1) == 16
        assert all(c in "0123456789abcdef" for c in h1)

    def test_content_hash_different_inputs(self) -> None:
        from src.entity.attributor import content_hash

        h1 = content_hash("hello world")
        h2 = content_hash("goodbye world")
        assert h1 != h2

    def test_commitment_content_hash(self) -> None:
        from src.entity.attributor import commitment_content_hash

        h = commitment_content_hash("Colin", "Review PR", "2026-04-10")
        assert len(h) == 16
        # Verify format is who|what|by_when
        from src.entity.attributor import content_hash

        expected = content_hash("Colin|Review PR|2026-04-10")
        assert h == expected


# ---------------------------------------------------------------------------
# Name matching
# ---------------------------------------------------------------------------


class TestMatchNameToEntity:
    def test_match_name_direct(self, tmp_path) -> None:
        from src.entity.attributor import match_name_to_entity

        repo = _make_repo(tmp_path)
        entities = _seed_entities(repo)
        result = match_name_to_entity("Affirm", repo)
        assert result is not None
        entity, confidence = result
        assert entity.id == entities["Affirm"].id
        assert confidence == 1.0
        repo.close()

    def test_match_name_alias(self, tmp_path) -> None:
        from src.entity.attributor import match_name_to_entity

        repo = _make_repo(tmp_path)
        entities = _seed_entities(repo)
        result = match_name_to_entity("Affirm Financial", repo)
        assert result is not None
        entity, confidence = result
        assert entity.id == entities["Affirm"].id
        assert confidence == 0.7
        repo.close()

    def test_match_name_not_found(self, tmp_path) -> None:
        from src.entity.attributor import match_name_to_entity

        repo = _make_repo(tmp_path)
        _seed_entities(repo)
        result = match_name_to_entity("Unknown Corp", repo)
        assert result is None
        repo.close()

    def test_match_follows_merge_target(self, tmp_path) -> None:
        from src.entity.attributor import match_name_to_entity

        repo = _make_repo(tmp_path)
        entities = _seed_entities(repo)
        # Create a duplicate entity with merge target pointing to Affirm
        dup = repo.add_entity("Affirm Holdings", "partner")
        repo._conn.execute(
            "UPDATE entities SET merge_target_id = ? WHERE id = ?",
            (entities["Affirm"].id, dup.id),
        )
        repo._conn.commit()
        result = match_name_to_entity("Affirm Holdings", repo)
        assert result is not None
        entity, confidence = result
        assert entity.id == entities["Affirm"].id  # Followed merge target
        assert confidence == 1.0
        repo.close()


# ---------------------------------------------------------------------------
# Attribution of synthesis items
# ---------------------------------------------------------------------------


class TestAttributeSynthesisItems:
    def test_attribute_substance_items(self, tmp_path) -> None:
        from src.entity.attributor import attribute_synthesis_items

        repo = _make_repo(tmp_path)
        entities = _seed_entities(repo)

        output = DailySynthesisOutput(
            executive_summary="Test summary",
            substance=[
                SynthesisItem(content="Affirm deal progressing", entity_names=["Affirm"]),
                SynthesisItem(content="No entities here", entity_names=[]),
            ],
            decisions=[],
            commitments=[],
        )

        result = attribute_synthesis_items(output, repo, "2026-04-07")
        assert len(result.substance_refs) == 2
        assert len(result.substance_refs[0]) == 1  # Affirm matched
        assert result.substance_refs[0][0].entity_id == entities["Affirm"].id
        assert result.substance_refs[0][0].confidence == 1.0
        assert len(result.substance_refs[1]) == 0  # No matches
        repo.close()

    def test_attribute_commitments_who(self, tmp_path) -> None:
        from src.entity.attributor import attribute_synthesis_items

        repo = _make_repo(tmp_path)
        entities = _seed_entities(repo)

        output = DailySynthesisOutput(
            substance=[],
            decisions=[],
            commitments=[
                CommitmentRow(
                    who="Colin Roberts",
                    what="Review PR",
                    by_when="2026-04-10",
                    source="standup",
                    entity_names=[],  # entity_names empty, but who should match
                ),
            ],
        )

        result = attribute_synthesis_items(output, repo, "2026-04-07")
        assert len(result.commitment_refs) == 1
        assert len(result.commitment_refs[0]) >= 1
        # Colin Roberts matched via who field
        ref_names = [r.name for r in result.commitment_refs[0]]
        assert "Colin Roberts" in ref_names
        repo.close()

    def test_attribute_skips_empty_names(self, tmp_path) -> None:
        from src.entity.attributor import attribute_synthesis_items

        repo = _make_repo(tmp_path)
        _seed_entities(repo)

        output = DailySynthesisOutput(
            substance=[
                SynthesisItem(content="Test", entity_names=["", "  ", "Affirm"]),
            ],
            decisions=[],
            commitments=[],
        )

        result = attribute_synthesis_items(output, repo, "2026-04-07")
        # Only Affirm should match, empty/whitespace skipped
        assert len(result.substance_refs[0]) == 1
        assert result.substance_refs[0][0].name == "Affirm"
        repo.close()

    def test_entity_summary_computed(self, tmp_path) -> None:
        from src.entity.attributor import attribute_synthesis_items

        repo = _make_repo(tmp_path)
        entities = _seed_entities(repo)

        output = DailySynthesisOutput(
            substance=[
                SynthesisItem(content="Affirm update 1", entity_names=["Affirm"]),
                SynthesisItem(content="Affirm update 2", entity_names=["Affirm"]),
            ],
            decisions=[
                SynthesisItem(content="Colin's decision", entity_names=["Colin Roberts"]),
            ],
            commitments=[],
        )

        result = attribute_synthesis_items(output, repo, "2026-04-07")
        assert len(result.entity_summary) == 2  # Affirm (2 mentions) + Colin (1)
        affirm_summary = next(s for s in result.entity_summary if s.name == "Affirm")
        assert affirm_summary.mention_count == 2
        repo.close()


# ---------------------------------------------------------------------------
# Mention persistence
# ---------------------------------------------------------------------------


class TestPersistMentions:
    def test_persist_mentions_returns_count(self, tmp_path) -> None:
        from src.entity.attributor import persist_mentions

        conn = get_connection(str(tmp_path / "test.db"))
        mentions = [
            EntityMention(
                id="m1",
                entity_id="e1",
                source_type="substance",
                source_id="hash1",
                source_date="2026-04-07",
                confidence=1.0,
                created_at="2026-04-07T00:00:00Z",
            ),
            EntityMention(
                id="m2",
                entity_id="e2",
                source_type="decision",
                source_id="hash2",
                source_date="2026-04-07",
                confidence=0.7,
                created_at="2026-04-07T00:00:00Z",
            ),
        ]
        # Need to create dummy entity rows for FK constraint
        conn.execute("PRAGMA foreign_keys=OFF")
        count = persist_mentions(conn, mentions, "2026-04-07")
        assert count == 2
        conn.close()

    def test_persist_mentions_idempotent(self, tmp_path) -> None:
        from src.entity.attributor import persist_mentions

        conn = get_connection(str(tmp_path / "test.db"))
        conn.execute("PRAGMA foreign_keys=OFF")

        mentions = [
            EntityMention(
                id="m1",
                entity_id="e1",
                source_type="substance",
                source_id="hash1",
                source_date="2026-04-07",
                confidence=1.0,
                created_at="2026-04-07T00:00:00Z",
            ),
        ]

        persist_mentions(conn, mentions, "2026-04-07")
        # Second call with different ID but same date - should replace
        mentions2 = [
            EntityMention(
                id="m2",
                entity_id="e1",
                source_type="substance",
                source_id="hash1",
                source_date="2026-04-07",
                confidence=1.0,
                created_at="2026-04-07T00:00:00Z",
            ),
        ]
        persist_mentions(conn, mentions2, "2026-04-07")

        rows = conn.execute(
            "SELECT * FROM entity_mentions WHERE source_date = '2026-04-07'"
        ).fetchall()
        assert len(rows) == 1  # Replaced, not doubled
        assert rows[0]["id"] == "m2"
        conn.close()


# ---------------------------------------------------------------------------
# Sidecar enrichment
# ---------------------------------------------------------------------------


class TestSidecarEnrichment:
    def test_enrich_sidecar_with_attribution(self) -> None:
        from datetime import date, datetime, timezone

        from src.entity.attributor import (
            AttributionResult,
            EntityReference,
            EntitySummaryEntry,
        )
        from src.models.events import DailySynthesis, Section
        from src.sidecar import build_daily_sidecar

        attribution = AttributionResult(
            substance_refs=[[EntityReference(entity_id="e1", name="Affirm", confidence=1.0)]],
            decision_refs=[],
            commitment_refs=[],
            mentions=[],
            entity_summary=[
                EntitySummaryEntry(
                    entity_id="e1", name="Affirm", entity_type="partner", mention_count=1
                )
            ],
        )

        synthesis = DailySynthesis(
            date=date(2026, 4, 7),
            generated_at=datetime(2026, 4, 7, 8, 0, 0, tzinfo=timezone.utc),
            meeting_count=0,
            total_meeting_hours=0.0,
            transcript_count=0,
            substance=Section(title="Substance", items=["Affirm deal progressing"]),
            decisions=Section(title="Decisions"),
            commitments=Section(title="Commitments"),
        )

        sidecar = build_daily_sidecar(synthesis, [], entity_attribution=attribution)
        assert len(sidecar.substance_entity_refs) == 1
        assert len(sidecar.substance_entity_refs[0]) == 1
        assert sidecar.substance_entity_refs[0][0].entity_id == "e1"
        assert len(sidecar.entity_summary) == 1
        assert sidecar.entity_summary[0].name == "Affirm"

    def test_sidecar_without_attribution(self) -> None:
        from datetime import date, datetime, timezone

        from src.models.events import DailySynthesis, Section
        from src.sidecar import build_daily_sidecar

        synthesis = DailySynthesis(
            date=date(2026, 4, 7),
            generated_at=datetime(2026, 4, 7, 8, 0, 0, tzinfo=timezone.utc),
            meeting_count=0,
            total_meeting_hours=0.0,
            transcript_count=0,
            substance=Section(title="Substance"),
            decisions=Section(title="Decisions"),
            commitments=Section(title="Commitments"),
        )

        sidecar = build_daily_sidecar(synthesis, [])
        assert sidecar.substance_entity_refs == []
        assert sidecar.entity_summary == []
