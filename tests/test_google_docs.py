"""Tests for Google Docs ingestion module."""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.models.sources import ContentType, SourceType


# --- Fixture helpers ---


def _make_doc_meta(
    file_id: str = "doc-123",
    name: str = "Test Document",
    mime_type: str = "application/vnd.google-apps.document",
    modified_time: str = "2026-04-04T14:00:00.000Z",
    modifier_email: str = "user@example.com",
    modifier_me: bool = True,
) -> dict:
    return {
        "id": file_id,
        "name": name,
        "mimeType": mime_type,
        "modifiedTime": modified_time,
        "owners": [{"emailAddress": "user@example.com"}],
        "lastModifyingUser": {
            "emailAddress": modifier_email,
            "me": modifier_me,
        },
    }


def _make_comment(
    comment_id: str = "comment-1",
    content: str = "This looks good",
    author_name: str = "Alice",
    created_time: str = "2026-04-04T10:00:00.000Z",
    modified_time: str = "2026-04-04T10:00:00.000Z",
    resolved: bool = False,
    quoted_text: str | None = None,
    replies: list | None = None,
) -> dict:
    comment: dict = {
        "id": comment_id,
        "content": content,
        "author": {"displayName": author_name, "emailAddress": "alice@example.com"},
        "createdTime": created_time,
        "modifiedTime": modified_time,
        "resolved": resolved,
        "replies": replies or [],
    }
    if quoted_text is not None:
        comment["quotedFileContent"] = {"value": quoted_text}
    return comment


def _base_config(enabled: bool = True, **overrides) -> dict:
    docs_config = {
        "enabled": enabled,
        "content_max_chars": 2500,
        "comment_max_chars": 500,
        "max_docs_per_day": 50,
        "exclude_ids": [],
        "exclude_title_patterns": [],
    }
    docs_config.update(overrides)
    return {"google_docs": docs_config}


def _mock_drive_service(files: list[dict] | None = None, comments: list[dict] | None = None):
    """Build a mock Drive API service."""
    service = MagicMock()

    # files().list()
    files_list_result = {"files": files or [], "nextPageToken": None}
    service.files.return_value.list.return_value.execute.return_value = files_list_result

    # about().get()
    service.about.return_value.get.return_value.execute.return_value = {
        "user": {"emailAddress": "user@example.com"}
    }

    # comments().list()
    comments_list_result = {"comments": comments or [], "nextPageToken": None}
    service.comments.return_value.list.return_value.execute.return_value = comments_list_result

    return service


def _mock_docs_service(content: str = "Hello world"):
    """Build a mock Docs API service."""
    service = MagicMock()
    return service


# --- Tests ---


class TestFetchDisabled:
    def test_returns_empty_when_disabled(self):
        from src.ingest.google_docs import fetch_google_docs_items

        config = _base_config(enabled=False)
        creds = MagicMock()
        result = fetch_google_docs_items(config, creds, date(2026, 4, 4))
        assert result == []


class TestShouldExclude:
    def test_exclude_by_id(self):
        from src.ingest.google_docs import _should_exclude

        config = _base_config(exclude_ids=["doc-123"])
        doc = _make_doc_meta(file_id="doc-123")
        assert _should_exclude(doc, config) is True

    def test_not_excluded_by_different_id(self):
        from src.ingest.google_docs import _should_exclude

        config = _base_config(exclude_ids=["doc-999"])
        doc = _make_doc_meta(file_id="doc-123")
        assert _should_exclude(doc, config) is False

    def test_exclude_by_title_pattern(self):
        from src.ingest.google_docs import _should_exclude

        config = _base_config(exclude_title_patterns=["1:1 Notes", "Personal Journal"])
        doc = _make_doc_meta(name="Weekly 1:1 Notes with Manager")
        assert _should_exclude(doc, config) is True

    def test_not_excluded_when_no_match(self):
        from src.ingest.google_docs import _should_exclude

        config = _base_config(exclude_title_patterns=["1:1 Notes"])
        doc = _make_doc_meta(name="Project Roadmap")
        assert _should_exclude(doc, config) is False


class TestDocEditToSourceItem:
    @patch("src.ingest.google_docs._extract_doc_text", return_value="This is document content for testing purposes.")
    @patch("src.ingest.google_docs._get_user_email", return_value="user@example.com")
    def test_google_doc_produces_edit_source_item(self, mock_email, mock_extract):
        from src.ingest.google_docs import _build_doc_edit_items

        doc = _make_doc_meta(
            name="Project Roadmap",
            mime_type="application/vnd.google-apps.document",
        )
        drive_svc = _mock_drive_service()
        docs_svc = _mock_docs_service()
        config = _base_config()

        items = _build_doc_edit_items(drive_svc, docs_svc, [doc], config)

        assert len(items) == 1
        item = items[0]
        assert item.source_type == SourceType.GOOGLE_DOC_EDIT
        assert item.content_type == ContentType.EDIT
        assert item.title == "Project Roadmap"
        assert item.display_context.startswith("Google Doc")
        assert "document" in item.source_url

    @patch("src.ingest.google_docs._extract_doc_text", return_value="Short content")
    @patch("src.ingest.google_docs._get_user_email", return_value="user@example.com")
    def test_sheet_edit_metadata_only(self, mock_email, mock_extract):
        from src.ingest.google_docs import _build_doc_edit_items

        doc = _make_doc_meta(
            name="Budget 2026",
            mime_type="application/vnd.google-apps.spreadsheet",
        )
        drive_svc = _mock_drive_service()
        docs_svc = _mock_docs_service()
        config = _base_config()

        items = _build_doc_edit_items(drive_svc, docs_svc, [doc], config)

        assert len(items) == 1
        item = items[0]
        assert item.display_context.startswith("Google Sheet")
        assert "spreadsheet" in item.source_url
        # Content should be metadata string, not extracted text
        assert "Google Sheet edited" in item.content
        # _extract_doc_text should NOT have been called for sheets
        mock_extract.assert_not_called()

    @patch("src.ingest.google_docs._extract_doc_text", return_value="Short content")
    @patch("src.ingest.google_docs._get_user_email", return_value="user@example.com")
    def test_slides_edit_metadata_only(self, mock_email, mock_extract):
        from src.ingest.google_docs import _build_doc_edit_items

        doc = _make_doc_meta(
            name="Q1 Review",
            mime_type="application/vnd.google-apps.presentation",
        )
        drive_svc = _mock_drive_service()
        docs_svc = _mock_docs_service()
        config = _base_config()

        items = _build_doc_edit_items(drive_svc, docs_svc, [doc], config)

        assert len(items) == 1
        item = items[0]
        assert item.display_context.startswith("Google Slides")
        assert "presentation" in item.source_url
        assert "Google Slides edited" in item.content
        mock_extract.assert_not_called()


class TestCommentToSourceItem:
    def test_comment_produces_correct_source_item(self):
        from src.ingest.google_docs import _build_comment_items

        doc = _make_doc_meta(name="Design Doc")
        comment = _make_comment(
            content="Looks good to me!",
            author_name="Bob",
            created_time="2026-04-04T11:00:00.000Z",
        )
        drive_svc = _mock_drive_service(comments=[comment])
        config = _base_config()

        items = _build_comment_items(drive_svc, [doc], date(2026, 4, 4), config)

        assert len(items) == 1
        item = items[0]
        assert item.source_type == SourceType.GOOGLE_DOC_COMMENT
        assert item.content_type == ContentType.COMMENT
        assert "Bob" in item.title
        assert "Design Doc" in item.title
        assert item.participants == ["Bob"]
        assert item.content == "Looks good to me!"

    def test_suggestion_includes_quoted_content(self):
        from src.ingest.google_docs import _build_comment_items

        doc = _make_doc_meta(name="RFC Doc")
        comment = _make_comment(
            content="Should use async here",
            author_name="Carol",
            created_time="2026-04-04T12:00:00.000Z",
            quoted_text="def process_data(items):",
        )
        drive_svc = _mock_drive_service(comments=[comment])
        config = _base_config()

        items = _build_comment_items(drive_svc, [doc], date(2026, 4, 4), config)

        assert len(items) == 1
        assert 'Suggested: "def process_data(items):"' in items[0].content
        assert "Should use async here" in items[0].content

    def test_resolved_comments_included(self):
        from src.ingest.google_docs import _build_comment_items

        doc = _make_doc_meta(name="API Spec")
        comment = _make_comment(
            content="Fixed the typo",
            resolved=True,
            created_time="2026-04-04T09:00:00.000Z",
        )
        drive_svc = _mock_drive_service(comments=[comment])
        config = _base_config()

        items = _build_comment_items(drive_svc, [doc], date(2026, 4, 4), config)

        # Resolved comments should NOT be filtered out
        assert len(items) == 1
        assert items[0].content == "Fixed the typo"


class TestLimitsAndTruncation:
    @patch("src.ingest.google_docs._extract_doc_text", return_value="A" * 5000)
    @patch("src.ingest.google_docs._get_user_email", return_value="user@example.com")
    def test_content_truncation(self, mock_email, mock_extract):
        from src.ingest.google_docs import _build_doc_edit_items

        doc = _make_doc_meta(mime_type="application/vnd.google-apps.document")
        drive_svc = _mock_drive_service()
        docs_svc = _mock_docs_service()
        config = _base_config(content_max_chars=100)

        items = _build_doc_edit_items(drive_svc, docs_svc, [doc], config)

        assert len(items) == 1
        assert len(items[0].content) == 100

    @patch("src.ingest.google_docs._extract_doc_text", return_value="Short")
    @patch("src.ingest.google_docs._get_user_email", return_value="user@example.com")
    def test_max_docs_limit(self, mock_email, mock_extract):
        from src.ingest.google_docs import _build_doc_edit_items

        docs = [
            _make_doc_meta(file_id=f"doc-{i}", name=f"Doc {i}")
            for i in range(10)
        ]
        drive_svc = _mock_drive_service()
        docs_svc = _mock_docs_service()
        config = _base_config(max_docs_per_day=3)

        items = _build_doc_edit_items(drive_svc, docs_svc, docs, config)

        assert len(items) == 3


class TestCommentDateFiltering:
    def test_comments_outside_date_range_excluded(self):
        from src.ingest.google_docs import _build_comment_items

        doc = _make_doc_meta(name="Old Doc")
        old_comment = _make_comment(
            content="Old comment",
            created_time="2026-04-03T10:00:00.000Z",
            modified_time="2026-04-03T10:00:00.000Z",
        )
        drive_svc = _mock_drive_service(comments=[old_comment])
        config = _base_config()

        items = _build_comment_items(drive_svc, [doc], date(2026, 4, 4), config)

        assert len(items) == 0
