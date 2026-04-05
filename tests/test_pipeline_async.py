"""Tests for async pipeline orchestrator: parallel ingest, error isolation, sync wrapper."""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import make_test_config
from src.models.sources import SourceItem, SourceType, ContentType
from src.pipeline import PipelineContext, run_pipeline
from src.pipeline_async import async_ingest_all, async_pipeline


# --- Helpers ---


def _make_ctx(tmp_path: Path, **overrides) -> PipelineContext:
    """Build a minimal PipelineContext for testing."""
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


def _make_source_item(title: str = "Test Item", source_type: SourceType = SourceType.SLACK_MESSAGE) -> SourceItem:
    """Build a minimal SourceItem for testing."""
    return SourceItem(
        id=f"test-{title.lower().replace(' ', '-')}",
        source_type=source_type,
        title=title,
        content="Test content for " + title,
        timestamp=datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc),
        content_type=ContentType.MESSAGE,
        source_url="https://example.com/test",
    )


# --- Test 1: Parallel ingest returns all source results ---


@pytest.mark.asyncio
@patch("src.pipeline_async._ingest_notion")
@patch("src.pipeline_async._ingest_docs")
@patch("src.pipeline_async._ingest_hubspot")
@patch("src.pipeline_async._ingest_slack")
@patch("src.pipeline_async.anthropic.AsyncAnthropic")
async def test_async_ingest_all_runs_concurrently(
    mock_async_anthropic,
    mock_slack,
    mock_hubspot,
    mock_docs,
    mock_notion,
    tmp_path,
):
    """All five ingest sources run and return data correctly."""
    slack_items = [_make_source_item("Slack msg", SourceType.SLACK_MESSAGE)]
    hubspot_items = [_make_source_item("HubSpot deal", SourceType.HUBSPOT_DEAL)]
    docs_items = [_make_source_item("Doc edit", SourceType.GOOGLE_DOC_EDIT)]
    notion_items = [_make_source_item("Notion page", SourceType.NOTION_PAGE)]

    mock_slack.return_value = slack_items
    mock_hubspot.return_value = hubspot_items
    mock_docs.return_value = docs_items
    mock_notion.return_value = notion_items
    mock_async_anthropic.return_value = MagicMock()

    ctx = _make_ctx(tmp_path)  # calendar_service=None -> calendar returns empty

    result = await async_ingest_all(ctx)

    (
        r_slack, r_hubspot, r_docs, r_notion,
        r_categorized, r_transcripts, r_unmatched, r_extractions,
    ) = result

    assert r_slack == slack_items
    assert r_hubspot == hubspot_items
    assert r_docs == docs_items
    assert r_notion == notion_items
    assert r_categorized is None  # no calendar_service
    assert r_transcripts == []
    assert r_unmatched == []
    assert r_extractions == []


# --- Test 2: Error isolation ---


@pytest.mark.asyncio
@patch("src.pipeline_async._ingest_notion")
@patch("src.pipeline_async._ingest_docs")
@patch("src.pipeline_async._ingest_hubspot")
@patch("src.pipeline_async._ingest_slack")
@patch("src.pipeline_async.anthropic.AsyncAnthropic")
async def test_async_ingest_error_isolation(
    mock_async_anthropic,
    mock_slack,
    mock_hubspot,
    mock_docs,
    mock_notion,
    tmp_path,
):
    """One source failure does not crash others -- error caught, defaults used."""
    mock_slack.side_effect = RuntimeError("Slack broke")
    hubspot_items = [_make_source_item("HubSpot deal", SourceType.HUBSPOT_DEAL)]
    docs_items = [_make_source_item("Doc edit", SourceType.GOOGLE_DOC_EDIT)]
    notion_items = [_make_source_item("Notion page", SourceType.NOTION_PAGE)]

    mock_hubspot.return_value = hubspot_items
    mock_docs.return_value = docs_items
    mock_notion.return_value = notion_items
    mock_async_anthropic.return_value = MagicMock()

    ctx = _make_ctx(tmp_path)

    result = await async_ingest_all(ctx)

    (
        r_slack, r_hubspot, r_docs, r_notion,
        r_categorized, r_transcripts, r_unmatched, r_extractions,
    ) = result

    # Slack failed -> empty list
    assert r_slack == []
    # Others succeeded
    assert r_hubspot == hubspot_items
    assert r_docs == docs_items
    assert r_notion == notion_items


# --- Test 3: Sync wrapper ---


@patch("src.pipeline.cleanup_raw_cache", return_value=(0, 0))
@patch("src.pipeline_async.async_pipeline", new_callable=AsyncMock)
def test_run_pipeline_sync_wrapper(mock_async_pipeline, mock_cleanup, tmp_path):
    """run_pipeline() calls asyncio.run(async_pipeline(ctx)) as sync wrapper."""
    ctx = _make_ctx(tmp_path)
    run_pipeline(ctx)
    mock_async_pipeline.assert_called_once_with(ctx)


# --- Test 4: End-to-end async pipeline ---


@pytest.mark.asyncio
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
async def test_async_pipeline_end_to_end(
    mock_async_anthropic,
    mock_slack,
    mock_hubspot,
    mock_docs,
    mock_notion,
    mock_write,
    mock_detect,
    mock_save_raw,
    mock_sidecar,
    mock_slack_notify,
    tmp_path,
):
    """Full async pipeline runs through to write_daily_summary call."""
    output_file = tmp_path / "daily" / "2026" / "04" / "2026-04-01.md"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text("# Daily Summary")
    mock_write.return_value = output_file
    mock_async_anthropic.return_value = MagicMock()

    ctx = _make_ctx(tmp_path)
    await async_pipeline(ctx)

    mock_write.assert_called_once()
