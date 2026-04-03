"""Tests for Gong transcript parsing and combined fetch."""

from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

from src.ingest.transcripts import (
    fetch_all_transcripts,
    parse_gong_transcript,
    strip_filler,
)


def _make_message(
    subject: str = "Call with John Smith",
    from_addr: str = "notifications@gong.io",
    date_str: str = "Thu, 03 Apr 2026 14:00:00 -0400",
    body_text: str = "Call highlights: Discussed Q2 targets.",
    msg_id: str = "gong_msg_001",
) -> dict:
    """Create a mock Gmail message dict for Gong testing."""
    encoded_body = base64.urlsafe_b64encode(body_text.encode("utf-8")).decode("ascii")

    return {
        "id": msg_id,
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "Subject", "value": subject},
                {"name": "From", "value": from_addr},
                {"name": "To", "value": "me@example.com"},
                {"name": "Date", "value": date_str},
            ],
            "body": {"data": encoded_body},
        },
    }


def test_parse_gong_transcript_basic():
    """Test parsing a mock Gong email with 'Call with' subject."""
    config = {"transcripts": {"preprocessing": {"strip_filler": True}}}
    message = _make_message(
        subject="Call with John Smith",
        body_text="Discussed quarterly targets and pipeline review. Action items were assigned.",
    )

    result = parse_gong_transcript(message, config)
    assert result is not None
    assert result["source"] == "gong"
    assert result["title"] == "John Smith"  # "Call with " prefix stripped
    assert result["meeting_time"] is not None
    assert result["message_id"] == "gong_msg_001"
    assert "quarterly targets" in result["transcript_text"]


def test_parse_gong_transcript_conversation_subject():
    """Test subject format 'Conversation: Product Review'."""
    config = {"transcripts": {"preprocessing": {"strip_filler": False}}}
    message = _make_message(
        subject="Conversation: Product Review",
        body_text="Team reviewed product roadmap milestones.",
    )

    result = parse_gong_transcript(message, config)
    assert result is not None
    assert result["title"] == "Product Review"  # "Conversation: " prefix stripped
    assert result["source"] == "gong"


def test_parse_gong_transcript_empty_body():
    """Test that empty body returns None."""
    config = {"transcripts": {"preprocessing": {"strip_filler": True}}}
    message = _make_message(body_text="")
    # Encode empty string
    message["payload"]["body"]["data"] = base64.urlsafe_b64encode(b"").decode("ascii")

    result = parse_gong_transcript(message, config)
    assert result is None


def test_parse_gong_transcript_filler_stripped():
    """Test that filler words in Gong summary are stripped when configured."""
    config = {"transcripts": {"preprocessing": {"strip_filler": True}}}
    message = _make_message(
        body_text="So um we discussed uh the pipeline and ah decided to proceed.",
    )

    result = parse_gong_transcript(message, config)
    assert result is not None
    assert "um" not in result["transcript_text"].split()
    assert "uh" not in result["transcript_text"].split()
    assert "discussed" in result["transcript_text"]
    assert "decided" in result["transcript_text"]


def test_fetch_all_transcripts_combines_sources():
    """Verify combined list contains transcripts from both sources."""
    config = {
        "transcripts": {
            "gemini": {
                "sender_patterns": ["calendar-notification@google.com"],
                "subject_patterns": ["Transcript"],
            },
            "gong": {
                "sender_patterns": ["notifications@gong.io"],
                "subject_patterns": ["call"],
            },
            "preprocessing": {"strip_filler": False},
        }
    }

    mock_service = MagicMock()

    # Mock search_messages to return different stubs for different queries
    gemini_stub = [{"id": "gem1", "threadId": "t1"}]
    gong_stub = [{"id": "gong1", "threadId": "t2"}]

    gemini_msg = _make_message(
        subject="Transcript for Weekly Sync",
        from_addr="calendar-notification@google.com",
        body_text="Gemini transcript content.",
        msg_id="gem1",
    )
    gong_msg = _make_message(
        subject="Call with Jane Doe",
        from_addr="notifications@gong.io",
        body_text="Gong call summary content.",
        msg_id="gong1",
    )

    with patch("src.ingest.transcripts.search_messages") as mock_search, \
         patch("src.ingest.transcripts.get_message_content") as mock_get:
        # search_messages returns different results based on call order
        mock_search.side_effect = [gemini_stub, gong_stub]
        mock_get.side_effect = [gemini_msg, gong_msg]

        from datetime import date

        result = fetch_all_transcripts(mock_service, date(2026, 4, 3), config)

    assert len(result) == 2
    sources = {t["source"] for t in result}
    assert "gemini" in sources
    assert "gong" in sources
