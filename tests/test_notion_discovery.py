"""Tests for Notion database discovery module."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.ingest.notion_discovery import _scan_databases, run_notion_discovery


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db(db_id: str, title: str, last_edited: str = "2026-04-05T10:00:00Z") -> dict:
    """Build a minimal Notion database search result."""
    return {
        "id": db_id,
        "title": [{"plain_text": title}],
        "description": [],
        "last_edited_time": last_edited,
    }


def _search_response(results: list[dict], has_more: bool = False, next_cursor: str | None = None) -> dict:
    return {
        "results": results,
        "has_more": has_more,
        "next_cursor": next_cursor,
    }


# ---------------------------------------------------------------------------
# _scan_databases
# ---------------------------------------------------------------------------


@patch("httpx.post")
@patch("time.sleep")
def test_scan_databases_returns_sorted_list(mock_sleep, mock_post):
    """Databases are sorted by last_edited_time descending."""
    db_a = _make_db("id-a", "Older DB", "2026-04-01T00:00:00Z")
    db_b = _make_db("id-b", "Newer DB", "2026-04-05T00:00:00Z")

    mock_resp = MagicMock()
    mock_resp.json.return_value = _search_response([db_a, db_b])
    mock_resp.raise_for_status = MagicMock()
    mock_post.return_value = mock_resp

    result = _scan_databases("test-token")

    assert len(result) == 2
    assert result[0]["title"] == "Newer DB"
    assert result[1]["title"] == "Older DB"


@patch("httpx.post")
@patch("time.sleep")
def test_scan_databases_empty(mock_sleep, mock_post):
    """Returns empty list when no databases found."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = _search_response([])
    mock_resp.raise_for_status = MagicMock()
    mock_post.return_value = mock_resp

    result = _scan_databases("test-token")
    assert result == []


@patch("httpx.post")
@patch("time.sleep")
def test_scan_databases_pagination(mock_sleep, mock_post):
    """Combines results from multiple pages."""
    db_a = _make_db("id-a", "DB A", "2026-04-05T00:00:00Z")
    db_b = _make_db("id-b", "DB B", "2026-04-04T00:00:00Z")

    resp1 = MagicMock()
    resp1.json.return_value = _search_response([db_a], has_more=True, next_cursor="cursor-1")
    resp1.raise_for_status = MagicMock()

    resp2 = MagicMock()
    resp2.json.return_value = _search_response([db_b], has_more=False)
    resp2.raise_for_status = MagicMock()

    mock_post.side_effect = [resp1, resp2]

    result = _scan_databases("test-token")
    assert len(result) == 2
    assert mock_post.call_count == 2


@patch("httpx.post")
@patch("time.sleep")
def test_scan_databases_extracts_title(mock_sleep, mock_post):
    """Title is extracted from rich_text array."""
    db = {
        "id": "id-1",
        "title": [{"plain_text": "Project "}, {"plain_text": "Tasks"}],
        "description": [{"plain_text": "Track all tasks"}],
        "last_edited_time": "2026-04-05T10:00:00Z",
    }
    mock_resp = MagicMock()
    mock_resp.json.return_value = _search_response([db])
    mock_resp.raise_for_status = MagicMock()
    mock_post.return_value = mock_resp

    result = _scan_databases("test-token")
    assert result[0]["title"] == "Project Tasks"
    assert result[0]["description"] == "Track all tasks"


# ---------------------------------------------------------------------------
# run_notion_discovery
# ---------------------------------------------------------------------------


@patch("src.ingest.notion_discovery.load_config")
def test_run_discovery_no_token(mock_load_config, capsys):
    """Prints error when no token is configured."""
    mock_config = MagicMock()
    mock_config.notion.token = ""
    mock_load_config.return_value = mock_config

    run_notion_discovery("config/config.yaml")

    output = capsys.readouterr().out
    assert "No Notion token configured" in output
