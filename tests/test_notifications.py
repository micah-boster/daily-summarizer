"""Tests for Slack notification module."""

from datetime import date
from unittest.mock import patch

import pytest

from src.notifications.slack import _build_blocks, _split_text, send_slack_summary


class TestSplitText:
    def test_short_text_single_chunk(self):
        result = _split_text("Hello world", max_len=100)
        assert result == ["Hello world"]

    def test_splits_on_double_newline(self):
        text = "Section 1 content\n\nSection 2 content"
        result = _split_text(text, max_len=25)
        assert len(result) == 2
        assert result[0] == "Section 1 content"

    def test_splits_on_single_newline_fallback(self):
        text = "Line 1\nLine 2\nLine 3"
        result = _split_text(text, max_len=10)
        assert len(result) >= 2

    def test_empty_text(self):
        assert _split_text("") == [""]


class TestBuildBlocks:
    def test_header_present(self):
        blocks = _build_blocks("Test content", date(2026, 3, 18))
        assert blocks[0]["type"] == "header"
        assert "2026-03-18" in blocks[0]["text"]["text"]

    def test_content_in_section_block(self):
        blocks = _build_blocks("Test content", date(2026, 3, 18))
        assert len(blocks) >= 2
        assert blocks[1]["type"] == "section"
        assert "Test content" in blocks[1]["text"]["text"]


class TestSendSlackSummary:
    def test_no_webhook_returns_false(self):
        with patch.dict("os.environ", {}, clear=True):
            assert send_slack_summary("content", date(2026, 3, 18)) is False

    @patch("src.notifications.slack.httpx.post")
    def test_successful_send(self, mock_post):
        mock_post.return_value.status_code = 200
        result = send_slack_summary(
            "Test summary", date(2026, 3, 18), webhook_url="https://hooks.slack.com/test"
        )
        assert result is True
        mock_post.assert_called_once()

    @patch("src.notifications.slack.httpx.post")
    def test_failed_send_returns_false(self, mock_post):
        mock_post.return_value.status_code = 500
        mock_post.return_value.text = "error"
        result = send_slack_summary(
            "Test summary", date(2026, 3, 18), webhook_url="https://hooks.slack.com/test"
        )
        assert result is False

    @patch("src.notifications.slack.httpx.post", side_effect=Exception("connection error"))
    def test_exception_returns_false(self, mock_post):
        result = send_slack_summary(
            "Test summary", date(2026, 3, 18), webhook_url="https://hooks.slack.com/test"
        )
        assert result is False
