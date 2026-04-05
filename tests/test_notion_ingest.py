"""Tests for the Notion ingestion module."""
from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.config import PipelineConfig
from src.ingest.notion import (
    NotionClient,
    _extract_db_properties,
    _extract_page_title,
    _extract_text_from_blocks,
    fetch_notion_items,
)
from src.models.sources import ContentType, SourceType


def _make_config(**notion_overrides) -> PipelineConfig:
    """Build a PipelineConfig with Notion enabled."""
    return PipelineConfig(notion={"enabled": True, "token": "test-token", **notion_overrides})


# ---------------------------------------------------------------------------
# Guard tests
# ---------------------------------------------------------------------------


def test_fetch_notion_items_disabled():
    config = PipelineConfig()  # notion.enabled defaults to False
    result = fetch_notion_items(config, date(2026, 4, 5))
    assert result == []


def test_fetch_notion_items_no_token():
    config = PipelineConfig(notion={"enabled": True, "token": ""})
    result = fetch_notion_items(config, date(2026, 4, 5))
    assert result == []


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------


def test_extract_text_from_blocks():
    blocks = [
        {
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"plain_text": "Hello world"}],
            },
        },
        {
            "type": "heading_1",
            "heading_1": {
                "rich_text": [{"plain_text": "Title"}],
            },
        },
        {
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [{"plain_text": "Item one"}],
            },
        },
        {
            "type": "image",
            "image": {
                "type": "external",
                "external": {"url": "https://example.com/img.png"},
            },
        },
        {
            "type": "code",
            "code": {
                "rich_text": [{"plain_text": "print('hi')"}],
                "language": "python",
            },
        },
    ]
    result = _extract_text_from_blocks(blocks)
    assert "Hello world" in result
    assert "Title" in result
    assert "Item one" in result
    # image and code should NOT be extracted
    assert "img.png" not in result
    assert "print" not in result


def test_extract_text_from_blocks_empty():
    assert _extract_text_from_blocks([]) == ""


def test_extract_text_from_blocks_callout_and_toggle():
    blocks = [
        {
            "type": "callout",
            "callout": {
                "rich_text": [{"plain_text": "Important note"}],
            },
        },
        {
            "type": "toggle",
            "toggle": {
                "rich_text": [{"plain_text": "Click to expand"}],
            },
        },
    ]
    result = _extract_text_from_blocks(blocks)
    assert "Important note" in result
    assert "Click to expand" in result


# ---------------------------------------------------------------------------
# Title extraction
# ---------------------------------------------------------------------------


def test_extract_page_title():
    page = {
        "properties": {
            "Name": {
                "type": "title",
                "title": [{"plain_text": "My Page Title"}],
            },
        },
    }
    assert _extract_page_title(page) == "My Page Title"


def test_extract_page_title_multi_segment():
    page = {
        "properties": {
            "Title": {
                "type": "title",
                "title": [
                    {"plain_text": "Part "},
                    {"plain_text": "One"},
                ],
            },
        },
    }
    assert _extract_page_title(page) == "Part One"


def test_extract_page_title_untitled():
    page = {"properties": {}}
    assert _extract_page_title(page) == "Untitled"


def test_extract_page_title_empty_rich_text():
    page = {
        "properties": {
            "Name": {
                "type": "title",
                "title": [],
            },
        },
    }
    assert _extract_page_title(page) == "Untitled"


# ---------------------------------------------------------------------------
# Database property extraction
# ---------------------------------------------------------------------------


def test_extract_db_properties():
    properties = {
        "Status": {
            "type": "status",
            "status": {"name": "Done"},
        },
        "Priority": {
            "type": "select",
            "select": {"name": "High"},
        },
        "Count": {
            "type": "number",
            "number": 42,
        },
        "Active": {
            "type": "checkbox",
            "checkbox": True,
        },
        "Tags": {
            "type": "multi_select",
            "multi_select": [{"name": "Bug"}, {"name": "Urgent"}],
        },
    }
    result = _extract_db_properties(properties)
    assert "Status: Done" in result
    assert "Priority: High" in result
    assert "Count: 42" in result
    assert "Active: Yes" in result
    assert "Tags: Bug, Urgent" in result


def test_extract_db_properties_skips_relation():
    properties = {
        "Name": {
            "type": "title",
            "title": [{"plain_text": "Item"}],
        },
        "Parent": {
            "type": "relation",
            "relation": [{"id": "abc"}],
        },
        "Created": {
            "type": "created_time",
            "created_time": "2026-04-05T10:00:00Z",
        },
    }
    result = _extract_db_properties(properties)
    assert "Name: Item" in result
    # relation and created_time should be skipped
    assert "Parent" not in result
    assert "Created" not in result


def test_extract_db_properties_truncates():
    properties = {
        f"Prop{i}": {"type": "rich_text", "rich_text": [{"plain_text": "x" * 50}]}
        for i in range(20)
    }
    result = _extract_db_properties(properties, max_chars=100)
    assert len(result) <= 100


# ---------------------------------------------------------------------------
# NotionClient
# ---------------------------------------------------------------------------


def test_notion_client_throttle_config():
    client = NotionClient(token="test", notion_version="2022-06-28")
    assert client._min_interval == 0.35
    assert client._base == "https://api.notion.com/v1"
    assert "Bearer test" in client._headers["Authorization"]


# ---------------------------------------------------------------------------
# SourceItem conversion (with mocked API calls)
# ---------------------------------------------------------------------------


@patch("src.ingest.notion.NotionClient")
def test_fetch_edited_pages_converts_to_source_items(MockClient):
    """Verify page fetching produces SourceItems with correct types."""
    mock_client = MockClient.return_value

    # Mock search response
    mock_client.paginate_post.return_value = [
        {
            "id": "page-123",
            "object": "page",
            "last_edited_time": "2026-04-05T10:00:00.000Z",
            "url": "https://notion.so/page-123",
            "properties": {
                "Name": {
                    "type": "title",
                    "title": [{"plain_text": "Test Page"}],
                },
            },
        },
    ]

    # Mock block children response
    mock_client.get.return_value = {
        "results": [
            {
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"plain_text": "Page content here"}],
                },
            },
        ],
    }

    config = _make_config()
    items = fetch_notion_items(config, date(2026, 4, 5))

    assert len(items) >= 1
    page_items = [i for i in items if i.source_type == SourceType.NOTION_PAGE]
    assert len(page_items) >= 1

    item = page_items[0]
    assert item.source_type == SourceType.NOTION_PAGE
    assert item.content_type == ContentType.EDIT
    assert item.title == "Test Page"
    assert "Page content here" in item.content
    assert item.display_context.startswith("Notion")
    assert "(per Notion" in item.attribution_text()


@patch("src.ingest.notion.NotionClient")
def test_fetch_database_changes_converts_to_source_items(MockClient):
    """Verify database querying produces SourceItems with correct types."""
    mock_client = MockClient.return_value

    # paginate_post for search (pages) returns empty
    def mock_paginate(path, body=None):
        if "/search" in path:
            return []  # no pages
        elif "/databases/" in path and "/query" in path:
            return [
                {
                    "id": "item-456",
                    "object": "page",
                    "last_edited_time": "2026-04-05T14:00:00.000Z",
                    "url": "https://notion.so/item-456",
                    "properties": {
                        "Name": {
                            "type": "title",
                            "title": [{"plain_text": "Bug Fix Task"}],
                        },
                        "Status": {
                            "type": "status",
                            "status": {"name": "Done"},
                        },
                    },
                },
            ]
        return []

    mock_client.paginate_post.side_effect = mock_paginate

    # Mock database metadata
    mock_client.get.return_value = {
        "title": [{"plain_text": "Project Tasks"}],
    }

    config = _make_config(watched_databases=["db-789"])
    items = fetch_notion_items(config, date(2026, 4, 5))

    db_items = [i for i in items if i.source_type == SourceType.NOTION_DB]
    assert len(db_items) >= 1

    item = db_items[0]
    assert item.source_type == SourceType.NOTION_DB
    assert item.content_type == ContentType.STAGE_CHANGE
    assert item.title == "Bug Fix Task"
    assert "Status: Done" in item.content
    assert item.display_context == "Notion Project Tasks"
    assert "(per Notion Project Tasks)" == item.attribution_text()
