"""Tests for entity backfill orchestrator."""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.config import PipelineConfig
from src.entity.backfill import (
    _extract_text_from_sidecar,
    _is_day_processed,
    _read_day_content,
    _record_day_processed,
    run_backfill,
)
from src.entity.discovery import DiscoveredEntity
from src.entity.migrations import run_migrations


@pytest.fixture
def config(tmp_path):
    """Create a PipelineConfig with output_dir and entity db in tmp_path."""
    db_path = str(tmp_path / "entities.db")
    output_dir = str(tmp_path / "output")
    return PipelineConfig(
        pipeline={"output_dir": output_dir},
        entity={"db_path": db_path, "auto_register_threshold": 0.7, "review_threshold": 0.4},
    )


@pytest.fixture
def migrated_conn(config):
    """Return a connection with schema migrations applied."""
    from src.entity.db import get_connection

    conn = get_connection(config.entity.db_path)
    yield conn
    conn.close()


def _write_sidecar(output_dir: str, d: date, data: dict) -> None:
    """Helper to write a sidecar JSON file for a date."""
    path = Path(output_dir) / "daily" / str(d.year) / f"{d.month:02d}" / f"{d.isoformat()}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _write_markdown(output_dir: str, d: date, content: str) -> None:
    """Helper to write a markdown file for a date."""
    path = Path(output_dir) / "daily" / str(d.year) / f"{d.month:02d}" / f"{d.isoformat()}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# _extract_text_from_sidecar
# ---------------------------------------------------------------------------


class TestExtractTextFromSidecar:
    def test_extracts_tasks_decisions_commitments(self):
        data = {
            "tasks": [{"description": "Ship v2 API"}],
            "decisions": [{"description": "Use PostgreSQL", "rationale": "Better scaling"}],
            "commitments": [{"what": "Demo on Friday"}],
        }
        text = _extract_text_from_sidecar(data)
        assert "Ship v2 API" in text
        assert "Use PostgreSQL" in text
        assert "Better scaling" in text
        assert "Demo on Friday" in text

    def test_empty_sidecar_returns_empty(self):
        assert _extract_text_from_sidecar({}) == ""

    def test_handles_missing_sections(self):
        data = {"tasks": [{"description": "Only task"}]}
        text = _extract_text_from_sidecar(data)
        assert "Only task" in text


# ---------------------------------------------------------------------------
# _read_day_content
# ---------------------------------------------------------------------------


class TestReadDayContent:
    def test_returns_sidecar_text_when_json_exists(self, tmp_path):
        d = date(2026, 3, 15)
        _write_sidecar(
            str(tmp_path / "output"),
            d,
            {"tasks": [{"description": "Reviewed Affirm integration"}]},
        )
        text = _read_day_content(d, str(tmp_path / "output"))
        assert text is not None
        assert "Affirm" in text

    def test_falls_back_to_markdown_when_json_missing(self, tmp_path):
        d = date(2026, 3, 15)
        _write_markdown(str(tmp_path / "output"), d, "# Daily Summary\nDiscussed Stripe deal")
        text = _read_day_content(d, str(tmp_path / "output"))
        assert text is not None
        assert "Stripe" in text

    def test_falls_back_to_markdown_when_json_empty(self, tmp_path):
        d = date(2026, 3, 15)
        # Write empty sidecar (no tasks/decisions/commitments)
        _write_sidecar(str(tmp_path / "output"), d, {"tasks": [], "decisions": []})
        _write_markdown(str(tmp_path / "output"), d, "# Daily Summary\nDiscussed Stripe deal")
        text = _read_day_content(d, str(tmp_path / "output"))
        assert text is not None
        assert "Stripe" in text

    def test_returns_none_when_neither_exists(self, tmp_path):
        d = date(2026, 3, 15)
        text = _read_day_content(d, str(tmp_path / "output"))
        assert text is None


# ---------------------------------------------------------------------------
# _is_day_processed / _record_day_processed
# ---------------------------------------------------------------------------


class TestBackfillProgress:
    def test_is_day_processed_false_initially(self, migrated_conn):
        assert _is_day_processed(migrated_conn, "2026-03-15") is False

    def test_is_day_processed_true_after_record(self, migrated_conn):
        _record_day_processed(migrated_conn, "2026-03-15", "completed", 3)
        migrated_conn.commit()
        assert _is_day_processed(migrated_conn, "2026-03-15") is True


# ---------------------------------------------------------------------------
# run_backfill
# ---------------------------------------------------------------------------


class TestRunBackfill:
    def test_empty_date_range(self, config):
        result = run_backfill(date(2026, 3, 20), date(2026, 3, 10), config)
        assert result["days_processed"] == 0

    def test_skips_already_processed_days(self, config, tmp_path):
        # Write some content
        d = date(2026, 3, 15)
        _write_markdown(config.pipeline.output_dir, d, "# Summary\nDiscussed Affirm")

        # Pre-record day as processed
        from src.entity.db import get_connection

        conn = get_connection(config.entity.db_path)
        _record_day_processed(conn, "2026-03-15", "completed", 2)
        conn.commit()
        conn.close()

        result = run_backfill(d, d, config)
        assert result["days_skipped"] == 1
        assert result["days_processed"] == 0

    @patch("src.entity.backfill.extract_entities")
    def test_force_reprocesses_completed_days(self, mock_extract, config):
        d = date(2026, 3, 15)
        _write_markdown(config.pipeline.output_dir, d, "# Summary\nDiscussed Affirm")

        mock_extract.return_value = [
            DiscoveredEntity(name="Affirm", entity_type="partner", confidence=0.9)
        ]

        # Pre-record day as processed
        from src.entity.db import get_connection

        conn = get_connection(config.entity.db_path)
        _record_day_processed(conn, "2026-03-15", "completed", 0)
        conn.commit()
        conn.close()

        result = run_backfill(d, d, config, force=True)
        assert result["days_processed"] == 1
        mock_extract.assert_called_once()

    @patch("src.entity.backfill.extract_entities")
    def test_registers_entities_above_threshold(self, mock_extract, config):
        d = date(2026, 3, 15)
        _write_markdown(config.pipeline.output_dir, d, "# Summary\nDiscussed Affirm Inc and Stripe")

        mock_extract.return_value = [
            DiscoveredEntity(name="Affirm Inc", entity_type="partner", confidence=0.9),
            DiscoveredEntity(name="Stripe", entity_type="partner", confidence=0.8),
        ]

        result = run_backfill(d, d, config)
        assert result["entities_registered"] == 2

    @patch("src.entity.backfill.extract_entities")
    def test_deduplicates_via_normalization(self, mock_extract, config):
        """Affirm Inc and Affirm should resolve to same entity."""
        d1 = date(2026, 3, 15)
        d2 = date(2026, 3, 16)
        _write_markdown(config.pipeline.output_dir, d1, "Discussed Affirm Inc")
        _write_markdown(config.pipeline.output_dir, d2, "Discussed Affirm")

        # Day 1 discovers "Affirm Inc", Day 2 discovers "Affirm"
        mock_extract.side_effect = [
            [DiscoveredEntity(name="Affirm Inc", entity_type="partner", confidence=0.9)],
            [DiscoveredEntity(name="Affirm", entity_type="partner", confidence=0.9)],
        ]

        result = run_backfill(d1, d2, config)
        # Only 1 entity should be registered (second should match via normalized name)
        assert result["entities_registered"] == 1

    @patch("src.entity.backfill.extract_entities")
    def test_skips_days_without_content(self, mock_extract, config):
        d = date(2026, 3, 15)
        # Don't create any files for this date

        result = run_backfill(d, d, config)
        assert result["days_processed"] == 1
        mock_extract.assert_not_called()

    @patch("src.entity.backfill.extract_entities")
    def test_weekly_batching(self, mock_extract, config):
        """Verify dates are processed in weekly batches."""
        from_d = date(2026, 3, 1)
        to_d = date(2026, 3, 15)  # 15 days = 3 batches (7+7+1)

        # Write content for all dates
        current = from_d
        while current <= to_d:
            _write_markdown(config.pipeline.output_dir, current, f"Summary for {current}")
            current += date.resolution

        mock_extract.return_value = []

        result = run_backfill(from_d, to_d, config)
        assert result["days_processed"] == 15
        # extract_entities called once per day with content
        assert mock_extract.call_count == 15
