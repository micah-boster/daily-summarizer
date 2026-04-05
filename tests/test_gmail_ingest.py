"""Tests for Gmail ingestion utilities and Gemini transcript parsing."""

from __future__ import annotations

import base64
from datetime import date

from src.ingest.gmail import (
    build_transcript_query,
    extract_body_text,
    extract_headers,
)
from src.config import make_test_config
from src.ingest.transcripts import parse_gemini_transcript, strip_filler


def _make_message(
    subject: str = "Test Subject",
    from_addr: str = "test@example.com",
    date_str: str = "Thu, 03 Apr 2026 10:30:00 -0400",
    body_text: str = "Hello world",
    mime_type: str = "text/plain",
    multipart: bool = False,
    msg_id: str = "msg123",
) -> dict:
    """Create a mock Gmail message dict for testing."""
    encoded_body = base64.urlsafe_b64encode(body_text.encode("utf-8")).decode("ascii")

    headers = [
        {"name": "Subject", "value": subject},
        {"name": "From", "value": from_addr},
        {"name": "To", "value": "me@example.com"},
        {"name": "Date", "value": date_str},
    ]

    if multipart:
        payload = {
            "mimeType": "multipart/alternative",
            "headers": headers,
            "parts": [
                {
                    "mimeType": mime_type,
                    "body": {"data": encoded_body},
                },
            ],
        }
    else:
        payload = {
            "mimeType": mime_type,
            "headers": headers,
            "body": {"data": encoded_body},
        }

    return {"id": msg_id, "payload": payload}


# --- strip_filler tests ---


def test_strip_filler_basic():
    """Verify common filler words are removed."""
    text = "So um we discussed uh the project ah timeline"
    result = strip_filler(text)
    assert "um" not in result.split()
    assert "uh" not in result.split()
    assert "ah" not in result.split()
    assert "discussed" in result
    assert "project" in result
    assert "timeline" in result


def test_strip_filler_repeated_words():
    """Verify repeated consecutive words are collapsed."""
    text = "We need to to review the the requirements"
    result = strip_filler(text)
    # "to to" -> "to", "the the" -> "the"
    assert "to to" not in result
    assert "the the" not in result
    assert "review" in result
    assert "requirements" in result


def test_strip_filler_preserves_content():
    """Verify meaningful text is not altered by filler stripping."""
    text = "The quarterly revenue increased by 15% compared to last quarter"
    result = strip_filler(text)
    assert result == text


# --- extract_headers tests ---


def test_extract_headers():
    """Test header extraction from mock message payload."""
    message = _make_message(
        subject="Meeting Notes: Weekly Sync",
        from_addr="calendar-notification@google.com",
        date_str="Thu, 03 Apr 2026 10:30:00 -0400",
    )
    headers = extract_headers(message)
    assert headers["subject"] == "Meeting Notes: Weekly Sync"
    assert headers["from"] == "calendar-notification@google.com"
    assert headers["to"] == "me@example.com"
    assert headers["date"] == "Thu, 03 Apr 2026 10:30:00 -0400"


# --- extract_body_text tests ---


def test_extract_body_text_single_part():
    """Test base64url decoding of single-part plain text message."""
    message = _make_message(body_text="This is the meeting transcript content.")
    body = extract_body_text(message)
    assert body == "This is the meeting transcript content."


def test_extract_body_text_multipart():
    """Test multipart message body extraction (prefers text/plain)."""
    message = _make_message(
        body_text="Plain text version of the transcript.",
        multipart=True,
    )
    body = extract_body_text(message)
    assert body == "Plain text version of the transcript."


def test_extract_body_text_multipart_html_fallback():
    """Test multipart message falls back to HTML when no text/plain."""
    html_body = "<p>This is <b>HTML</b> content.</p>"
    message = _make_message(
        body_text=html_body,
        mime_type="text/html",
        multipart=True,
    )
    body = extract_body_text(message)
    assert "HTML" in body
    assert "<p>" not in body  # Tags stripped
    assert "<b>" not in body


# --- build_transcript_query tests ---


def test_build_transcript_query():
    """Test query string construction with date formatting."""
    query = build_transcript_query(
        sender_patterns=["calendar-notification@google.com", "meetings-noreply@google.com"],
        subject_patterns=["Transcript", "Meeting notes"],
        target_date=date(2026, 4, 3),
    )
    assert "from:calendar-notification@google.com" in query
    assert "from:meetings-noreply@google.com" in query
    assert "subject:Transcript" in query
    assert "subject:Meeting notes" in query
    assert "after:2026/04/03" in query
    assert "before:2026/04/04" in query
    assert " OR " in query


# --- parse_gemini_transcript tests ---


def test_parse_gemini_transcript():
    """Test full Gemini parsing pipeline with mock message."""
    config = make_test_config(transcripts={"preprocessing": {"strip_filler": True}})
    message = _make_message(
        subject="Transcript for Weekly Team Sync",
        from_addr="calendar-notification@google.com",
        date_str="Thu, 03 Apr 2026 10:30:00 -0400",
        body_text="We um discussed the um project timeline and uh decided to proceed.",
    )

    result = parse_gemini_transcript(message, config)
    assert result is not None
    assert result["source"] == "gemini"
    assert result["title"] == "Weekly Team Sync"  # "Transcript for " prefix stripped
    assert result["meeting_time"] is not None
    assert result["message_id"] == "msg123"
    # Filler stripped
    assert "um" not in result["transcript_text"].split()
    assert "uh" not in result["transcript_text"].split()
    assert "discussed" in result["transcript_text"]
    assert "decided" in result["transcript_text"]


def test_parse_gemini_transcript_empty_body():
    """Test that empty body returns None."""
    config = make_test_config(transcripts={"preprocessing": {"strip_filler": True}})
    message = _make_message(body_text="", subject="Transcript for Empty Meeting")

    # Need to handle empty body - manually create message with empty data
    message["payload"]["body"]["data"] = base64.urlsafe_b64encode(b"").decode("ascii")
    result = parse_gemini_transcript(message, config)
    assert result is None


def test_parse_gemini_transcript_meeting_notes_prefix():
    """Test subject prefix 'Meeting notes: ' is stripped."""
    config = make_test_config(transcripts={"preprocessing": {"strip_filler": False}})
    message = _make_message(
        subject="Meeting notes: Product Review",
        body_text="Reviewed product roadmap.",
    )

    result = parse_gemini_transcript(message, config)
    assert result is not None
    assert result["title"] == "Product Review"
