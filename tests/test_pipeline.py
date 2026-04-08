"""Tests for pipeline orchestration: happy path, source failures, degradation."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.config import make_test_config
from src.models.events import DailySynthesis, NormalizedEvent, Section
from src.models.sources import SourceItem, SourceType, ContentType
from src.pipeline import PipelineContext, _ingest_slack, _ingest_hubspot, _ingest_docs, run_pipeline
from src.synthesis.models import SynthesisItem, CommitmentRow


def _make_ctx(tmp_path: Path, **overrides) -> PipelineContext:
    """Build a minimal PipelineContext for testing."""
    if "config" not in overrides:
        overrides["config"] = make_test_config()
    defaults = {
        "config": make_test_config(),
        "target_date": date(2026, 4, 1),
        "output_dir": tmp_path,
        "template_dir": Path("templates"),
        "claude_client": MagicMock(),
        "google_creds": None,
        "calendar_service": None,
        "gmail_service": None,
    }
    defaults.update(overrides)
    return PipelineContext(**defaults)


def _make_source_item(title: str = "Test Item", source: str = "slack") -> SourceItem:
    """Build a minimal SourceItem for testing."""
    return SourceItem(
        id=f"test-{title.lower().replace(' ', '-')}",
        source_type=SourceType.SLACK_MESSAGE,
        title=title,
        content="Test content for " + title,
        timestamp=datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc),
        content_type=ContentType.MESSAGE,
        source_url="https://slack.com/test",
    )


# --- Ingest function tests ---


class TestIngestSlack:
    def test_slack_disabled_returns_empty(self, tmp_path: Path):
        ctx = _make_ctx(tmp_path, config=make_test_config(slack={"enabled": False}))
        result = _ingest_slack(ctx)
        assert result == []

    @patch("src.pipeline.fetch_slack_items")
    @patch("src.pipeline.build_slack_client")
    @patch("src.pipeline.load_slack_state")
    @patch("src.pipeline.save_slack_state")
    @patch("src.pipeline.check_new_channels")
    def test_slack_enabled_success(
        self, mock_check, mock_save, mock_load, mock_build, mock_fetch, tmp_path: Path
    ):
        ctx = _make_ctx(tmp_path, config=make_test_config(slack={"enabled": True, "channels": ["general"]}))
        mock_build.return_value = MagicMock()
        mock_load.return_value = {}
        items = [_make_source_item("Slack 1"), _make_source_item("Slack 2")]
        mock_fetch.return_value = items
        result = _ingest_slack(ctx)
        assert len(result) == 2

    @patch("src.pipeline.build_slack_client")
    def test_slack_failure_returns_empty(self, mock_build, tmp_path: Path):
        ctx = _make_ctx(tmp_path, config=make_test_config(slack={"enabled": True, "channels": ["general"]}))
        mock_build.side_effect = Exception("Slack API down")
        result = _ingest_slack(ctx)
        assert result == []


class TestIngestHubspot:
    def test_hubspot_disabled_returns_empty(self, tmp_path: Path):
        ctx = _make_ctx(tmp_path, config=make_test_config(hubspot={"enabled": False}))
        result = _ingest_hubspot(ctx)
        assert result == []

    @patch("src.pipeline.fetch_hubspot_items")
    def test_hubspot_failure_returns_empty(self, mock_fetch, tmp_path: Path):
        ctx = _make_ctx(tmp_path, config=make_test_config(hubspot={"enabled": True, "owner_id": "123"}))
        mock_fetch.side_effect = Exception("HubSpot API down")
        result = _ingest_hubspot(ctx)
        assert result == []


class TestIngestDocs:
    def test_docs_disabled_returns_empty(self, tmp_path: Path):
        ctx = _make_ctx(tmp_path, config=make_test_config(google_docs={"enabled": False}))
        result = _ingest_docs(ctx)
        assert result == []

    def test_docs_no_creds_returns_empty(self, tmp_path: Path):
        ctx = _make_ctx(tmp_path, config=make_test_config(google_docs={"enabled": True}), google_creds=None)
        result = _ingest_docs(ctx)
        assert result == []


# --- Pipeline orchestration tests ---


class TestRunPipeline:
    @patch("src.pipeline_async.send_slack_summary")
    @patch("src.pipeline_async.write_daily_sidecar")
    @patch("src.pipeline_async.save_raw_output")
    @patch("src.pipeline_async.detect_edits", return_value=None)
    @patch("src.pipeline_async.write_daily_summary")
    @patch("src.pipeline_async._ingest_notion", return_value=[])
    @patch("src.pipeline_async._ingest_docs", return_value=[])
    @patch("src.pipeline_async._ingest_hubspot", return_value=[])
    @patch("src.pipeline_async._ingest_slack", return_value=[])
    @patch("src.pipeline_async.anthropic.AsyncAnthropic")
    def test_happy_path_no_sources(
        self, mock_async_anthropic,
        mock_slack, mock_hubspot, mock_docs, mock_notion,
        mock_write, mock_detect, mock_save_raw, mock_sidecar, mock_slack_notify, tmp_path: Path
    ):
        """All sources disabled: pipeline runs to completion writing an empty summary."""
        output_file = tmp_path / "daily" / "2026" / "04" / "2026-04-01.md"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text("# Daily Summary")
        mock_write.return_value = output_file
        mock_async_anthropic.return_value = MagicMock()

        ctx = _make_ctx(tmp_path)
        run_pipeline(ctx)

        mock_write.assert_called_once()

    @patch("src.pipeline_async.send_slack_summary")
    @patch("src.pipeline_async.write_daily_sidecar")
    @patch("src.pipeline_async.save_raw_output")
    @patch("src.pipeline_async.detect_edits", return_value=None)
    @patch("src.pipeline_async.write_daily_summary")
    @patch("src.pipeline_async.synthesize_daily")
    @patch("src.pipeline_async._ingest_notion", return_value=[])
    @patch("src.pipeline_async._ingest_docs", return_value=[])
    @patch("src.pipeline_async._ingest_hubspot", return_value=[])
    @patch("src.pipeline_async._ingest_slack")
    @patch("src.pipeline_async.anthropic.AsyncAnthropic")
    def test_happy_path_with_slack(
        self, mock_async_anthropic,
        mock_slack, mock_hubspot, mock_docs, mock_notion,
        mock_synthesize, mock_write, mock_detect, mock_save_raw, mock_sidecar, mock_slack_notify,
        tmp_path: Path,
    ):
        """Slack enabled: items flow through to synthesize_daily."""
        ctx = _make_ctx(tmp_path, config=make_test_config(slack={"enabled": True, "channels": ["general"]}))
        slack_items = [_make_source_item("Slack item")]
        mock_slack.return_value = slack_items
        mock_async_anthropic.return_value = MagicMock()
        mock_synthesize.return_value = {
            "substance": [SynthesisItem(content="Item from Slack")],
            "decisions": [],
            "commitments": [],
            "executive_summary": None,
        }
        output_file = tmp_path / "daily" / "2026" / "04" / "2026-04-01.md"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text("# Summary")
        mock_write.return_value = output_file

        run_pipeline(ctx)

        mock_synthesize.assert_called_once()
        call_kwargs = mock_synthesize.call_args
        assert call_kwargs.kwargs.get("slack_items") == slack_items

    @patch("src.pipeline_async.send_slack_summary")
    @patch("src.pipeline_async.write_daily_sidecar")
    @patch("src.pipeline_async.save_raw_output")
    @patch("src.pipeline_async.detect_edits", return_value=None)
    @patch("src.pipeline_async.write_daily_summary")
    @patch("src.pipeline_async.synthesize_daily")
    @patch("src.pipeline_async._ingest_hubspot")
    @patch("src.pipeline_async._ingest_notion", return_value=[])
    @patch("src.pipeline_async._ingest_docs", return_value=[])
    @patch("src.pipeline_async._ingest_slack")
    @patch("src.pipeline_async.anthropic.AsyncAnthropic")
    def test_single_source_failure_continues(
        self, mock_async_anthropic,
        mock_slack, mock_docs, mock_notion, mock_hubspot,
        mock_synthesize, mock_write, mock_detect, mock_save_raw, mock_sidecar, mock_slack_notify,
        tmp_path: Path,
    ):
        """Slack fails but HubSpot succeeds: pipeline continues with partial data."""
        ctx = _make_ctx(tmp_path, config=make_test_config(
            slack={"enabled": True, "channels": ["general"]},
            hubspot={"enabled": True, "owner_id": "123"},
        ))
        mock_async_anthropic.return_value = MagicMock()
        # Slack fails
        mock_slack.side_effect = Exception("Slack down")
        # HubSpot succeeds
        hubspot_items = [_make_source_item("HubSpot deal")]
        mock_hubspot.return_value = hubspot_items
        mock_synthesize.return_value = {
            "substance": [SynthesisItem(content="HubSpot item")], "decisions": [], "commitments": [], "executive_summary": None,
        }
        output_file = tmp_path / "daily" / "2026" / "04" / "2026-04-01.md"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text("# Summary")
        mock_write.return_value = output_file

        # Should NOT raise even though Slack failed
        run_pipeline(ctx)

        # Synthesis was called with hubspot items, slack_items=[]
        mock_synthesize.assert_called_once()
        call_kwargs = mock_synthesize.call_args
        assert call_kwargs.kwargs.get("slack_items") == []
        assert call_kwargs.kwargs.get("hubspot_items") == hubspot_items

    @patch("src.pipeline_async.send_slack_summary")
    @patch("src.pipeline_async.write_daily_sidecar")
    @patch("src.pipeline_async.save_raw_output")
    @patch("src.pipeline_async.detect_edits", return_value=None)
    @patch("src.pipeline_async.write_daily_summary")
    @patch("src.pipeline_async.synthesize_daily")
    @patch("src.pipeline_async._ingest_notion", return_value=[])
    @patch("src.pipeline_async._ingest_docs", return_value=[])
    @patch("src.pipeline_async._ingest_hubspot", return_value=[])
    @patch("src.pipeline_async._ingest_slack")
    @patch("src.pipeline_async.anthropic.AsyncAnthropic")
    def test_synthesis_failure_still_writes(
        self, mock_async_anthropic,
        mock_slack, mock_hubspot, mock_docs, mock_notion,
        mock_synthesize, mock_write, mock_detect, mock_save_raw, mock_sidecar, mock_slack_notify,
        tmp_path: Path,
    ):
        """Synthesis fails: pipeline still writes a summary with empty synthesis."""
        ctx = _make_ctx(tmp_path, config=make_test_config(slack={"enabled": True, "channels": ["general"]}))
        mock_slack.return_value = [_make_source_item("Item")]
        mock_async_anthropic.return_value = MagicMock()
        mock_synthesize.side_effect = Exception("Claude API down")
        output_file = tmp_path / "daily" / "2026" / "04" / "2026-04-01.md"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text("# Summary")
        mock_write.return_value = output_file

        # Should NOT raise even though synthesis failed
        run_pipeline(ctx)

        # Writer was still called
        mock_write.assert_called_once()
