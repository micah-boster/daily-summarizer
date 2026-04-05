"""Tests for Slack notification module."""

from datetime import date
from unittest.mock import patch

import pytest

from src.notifications.slack import _build_blocks, send_slack_summary


class TestBuildBlocks:
    def test_header_present(self):
        blocks = _build_blocks("Test content", date(2026, 3, 18))
        assert blocks[0]["type"] == "header"
        assert "March" in blocks[0]["text"]["text"]

    def test_no_transcript_fallback(self):
        blocks = _build_blocks("No useful content here", date(2026, 3, 18))
        # Should have at least header + fallback message + footer
        assert len(blocks) >= 3

    def test_decisions_section_extracted(self):
        content = """## Decisions
- Approved new vendor contract -- Sarah -- standup
"""
        blocks = _build_blocks(content, date(2026, 3, 18))
        block_texts = [b.get("text", {}).get("text", "") for b in blocks if b.get("type") == "section"]
        has_decisions = any("Decisions" in t for t in block_texts)
        assert has_decisions

    def test_footer_present(self):
        blocks = _build_blocks("Test content", date(2026, 3, 18))
        last_block = blocks[-1]
        assert last_block["type"] == "context"


class TestSendSlackSummary:
    def test_no_webhook_returns_false(self):
        with patch.dict("os.environ", {}, clear=True):
            assert send_slack_summary("content", date(2026, 3, 18)) is False

    @patch("src.notifications.slack._post_with_retry")
    def test_successful_send(self, mock_post):
        mock_post.return_value.status_code = 200
        result = send_slack_summary(
            "Test summary", date(2026, 3, 18), webhook_url="https://hooks.slack.com/test"
        )
        assert result is True
        mock_post.assert_called_once()

    @patch("src.notifications.slack._post_with_retry")
    def test_failed_send_returns_false(self, mock_post):
        mock_post.return_value.status_code = 500
        mock_post.return_value.text = "error"
        result = send_slack_summary(
            "Test summary", date(2026, 3, 18), webhook_url="https://hooks.slack.com/test"
        )
        assert result is False

    @patch("src.notifications.slack._post_with_retry", side_effect=Exception("connection error"))
    def test_exception_returns_false(self, mock_post):
        result = send_slack_summary(
            "Test summary", date(2026, 3, 18), webhook_url="https://hooks.slack.com/test"
        )
        assert result is False
