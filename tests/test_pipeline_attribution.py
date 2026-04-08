"""Integration tests for entity attribution in the pipeline."""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.config import make_test_config
from src.entity.attributor import AttributionResult, EntityReference, EntitySummaryEntry
from src.entity.db import get_connection
from src.entity.repository import EntityRepository
from src.models.events import DailySynthesis, Section
from src.sidecar import build_daily_sidecar
from src.synthesis.models import CommitmentRow, SynthesisItem


def _make_repo_with_entity(tmp_path) -> tuple[EntityRepository, str]:
    """Create a repo with a test entity, return (repo, entity_id)."""
    repo = EntityRepository(str(tmp_path / "test.db"))
    repo.connect()
    entity = repo.add_entity("Affirm", "partner")
    return repo, entity.id


class TestAttributeEntitiesFunction:
    """Test _attribute_entities pipeline function directly."""

    def test_happy_path(self, tmp_path) -> None:
        from src.pipeline_async import _attribute_entities

        db_path = str(tmp_path / "test.db")
        repo = EntityRepository(db_path)
        repo.connect()
        entity = repo.add_entity("Affirm", "partner")
        repo.close()

        config = make_test_config(entity={"enabled": True, "db_path": db_path})
        synthesis_result = {
            "executive_summary": None,
            "substance": [SynthesisItem(content="Affirm deal update", entity_names=["Affirm"])],
            "decisions": [],
            "commitments": [],
        }

        result = _attribute_entities(synthesis_result, date(2026, 4, 7), config)

        assert result is not None
        assert len(result.substance_refs) == 1
        assert len(result.substance_refs[0]) == 1
        assert result.substance_refs[0][0].entity_id == entity.id
        assert result.substance_refs[0][0].confidence == 1.0

        # Check mentions persisted
        conn = get_connection(db_path)
        rows = conn.execute(
            "SELECT * FROM entity_mentions WHERE source_date = '2026-04-07'"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["source_type"] == "substance"
        conn.close()

    def test_disabled_returns_none(self) -> None:
        from src.pipeline_async import _attribute_entities

        config = make_test_config(entity={"enabled": False})
        result = _attribute_entities({}, date(2026, 4, 7), config)
        assert result is None

    def test_no_db_returns_none(self, tmp_path) -> None:
        from src.pipeline_async import _attribute_entities

        # Point to nonexistent path with auto_create=False
        config = make_test_config(entity={
            "enabled": True,
            "db_path": str(tmp_path / "nonexistent" / "does_not_exist.db"),
            "auto_create": False,
        })
        result = _attribute_entities({}, date(2026, 4, 7), config)
        assert result is None

    def test_exception_graceful(self) -> None:
        from src.pipeline_async import _attribute_entities

        config = make_test_config(entity={"enabled": True, "db_path": "/tmp/test.db"})

        with patch("src.pipeline_async._attribute_entities.__module__"):
            # Force an error by making imports fail inside the try
            with patch.dict("sys.modules", {"src.entity.attributor": None}):
                result = _attribute_entities({}, date(2026, 4, 7), config)
                assert result is None

    def test_idempotent_reruns(self, tmp_path) -> None:
        from src.pipeline_async import _attribute_entities

        db_path = str(tmp_path / "test.db")
        repo = EntityRepository(db_path)
        repo.connect()
        repo.add_entity("Affirm", "partner")
        repo.close()

        config = make_test_config(entity={"enabled": True, "db_path": db_path})
        synthesis_result = {
            "executive_summary": None,
            "substance": [SynthesisItem(content="Affirm deal", entity_names=["Affirm"])],
            "decisions": [],
            "commitments": [],
        }

        # Run twice
        _attribute_entities(synthesis_result, date(2026, 4, 7), config)
        _attribute_entities(synthesis_result, date(2026, 4, 7), config)

        # Check mentions not doubled
        conn = get_connection(db_path)
        rows = conn.execute(
            "SELECT * FROM entity_mentions WHERE source_date = '2026-04-07'"
        ).fetchall()
        assert len(rows) == 1  # Replaced, not doubled
        conn.close()


class TestSidecarWithAttribution:
    """Test sidecar enrichment via build_daily_sidecar."""

    def test_sidecar_with_attribution(self) -> None:
        attribution = AttributionResult(
            substance_refs=[[EntityReference(entity_id="e1", name="Affirm", confidence=1.0)]],
            decision_refs=[],
            commitment_refs=[],
            mentions=[],
            entity_summary=[
                EntitySummaryEntry(entity_id="e1", name="Affirm", entity_type="partner", mention_count=1)
            ],
        )

        synthesis = DailySynthesis(
            date=date(2026, 4, 7),
            generated_at=datetime(2026, 4, 7, 8, 0, 0, tzinfo=timezone.utc),
            meeting_count=0,
            total_meeting_hours=0.0,
            transcript_count=0,
            substance=Section(title="Substance", items=["Affirm deal"]),
            decisions=Section(title="Decisions"),
            commitments=Section(title="Commitments"),
        )

        sidecar = build_daily_sidecar(synthesis, [], entity_attribution=attribution)
        assert len(sidecar.substance_entity_refs) == 1
        assert sidecar.substance_entity_refs[0][0].entity_id == "e1"
        assert len(sidecar.entity_summary) == 1
        assert sidecar.entity_summary[0].name == "Affirm"

    def test_sidecar_without_attribution(self) -> None:
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
