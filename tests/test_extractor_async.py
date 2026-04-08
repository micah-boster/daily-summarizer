"""Tests for async extraction functions with concurrency and error isolation."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import anthropic
import pytest

from src.config import make_test_config
from src.models.events import Attendee, NormalizedEvent
from src.synthesis.extractor import extract_all_meetings_async, extract_meeting_async


# --- Helpers ---


VALID_EXTRACTION_JSON = {
    "reasoning": "Test meeting analysis.",
    "decisions": [],
    "commitments": [],
    "substance": [
        {
            "content": "Q2 pipeline review discussed",
            "participants": ["Alice"],
            "rationale": None,
        }
    ],
    "open_questions": [],
    "tensions": [],
}


def _make_mock_response(data: dict) -> MagicMock:
    """Create a mock API response with structured tool output."""
    content_block = MagicMock()
    content_block.input = data
    response = MagicMock()
    response.content = [content_block]
    return response


def _make_event(event_id: str, title: str, transcript: str | None = "Some transcript") -> NormalizedEvent:
    """Create a NormalizedEvent for testing."""
    return NormalizedEvent(
        id=event_id,
        title=title,
        start_time=datetime(2026, 4, 3, 10, 0, tzinfo=timezone.utc),
        transcript_text=transcript,
        attendees=[
            Attendee(email="alice@test.com", name="Alice", is_self=False),
        ],
    )


# --- Tests ---


@pytest.mark.asyncio
async def test_extract_meeting_async_basic():
    """Verify extract_meeting_async returns a MeetingExtraction from mock response."""
    mock_client = MagicMock(spec=anthropic.AsyncAnthropic)
    mock_client.messages = MagicMock()
    mock_client.messages.create = AsyncMock(
        return_value=_make_mock_response(VALID_EXTRACTION_JSON)
    )

    event = _make_event("test-async-1", "Team Sync")
    config = make_test_config()

    result = await extract_meeting_async(event, config, client=mock_client)

    assert result is not None
    assert result.meeting_title == "Team Sync"
    assert len(result.substance) == 1
    assert result.substance[0].content == "Q2 pipeline review discussed"
    assert result.low_signal is False
    mock_client.messages.create.assert_called_once()


@pytest.mark.asyncio
async def test_extract_all_meetings_async_parallel():
    """Verify extract_all_meetings_async runs all extractions with semaphore."""
    events = [
        _make_event("par-1", "Meeting 1"),
        _make_event("par-2", "Meeting 2"),
        _make_event("par-3", "Meeting 3"),
    ]

    mock_client = MagicMock(spec=anthropic.AsyncAnthropic)
    mock_client.messages = MagicMock()
    mock_client.messages.create = AsyncMock(
        return_value=_make_mock_response(VALID_EXTRACTION_JSON)
    )

    config = make_test_config(synthesis={"max_concurrent_extractions": 2})

    results = await extract_all_meetings_async(events, config, client=mock_client)

    assert len(results) == 3
    assert mock_client.messages.create.call_count == 3
    for r in results:
        assert r.low_signal is False
        assert len(r.substance) == 1


@pytest.mark.asyncio
async def test_extract_all_meetings_async_error_isolation():
    """Verify one extraction failure does not crash others."""
    events = [
        _make_event("iso-1", "Meeting 1"),
        _make_event("iso-2", "Meeting 2"),
        _make_event("iso-3", "Meeting 3"),
    ]

    call_titles: list[str] = []

    async def _side_effect(**kwargs):
        # Extract meeting title from the prompt to identify which event
        prompt = kwargs.get("messages", [{}])[0].get("content", "")
        call_titles.append(prompt)
        if "Meeting 2" in prompt:
            raise anthropic.APIConnectionError(request=MagicMock())
        return _make_mock_response(VALID_EXTRACTION_JSON)

    mock_client = MagicMock(spec=anthropic.AsyncAnthropic)
    mock_client.messages = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=_side_effect)

    config = make_test_config(synthesis={"max_concurrent_extractions": 1})

    results = await extract_all_meetings_async(events, config, client=mock_client)

    # 2 successful, 1 failed (the 2nd)
    assert len(results) == 2
    assert all(r.low_signal is False for r in results)


@pytest.mark.asyncio
async def test_extract_all_meetings_async_skips_no_transcript():
    """Verify events without transcript_text are skipped."""
    events = [
        _make_event("skip-1", "Meeting With Transcript", transcript="Some content"),
        _make_event("skip-2", "Meeting Without Transcript", transcript=None),
    ]

    mock_client = MagicMock(spec=anthropic.AsyncAnthropic)
    mock_client.messages = MagicMock()
    mock_client.messages.create = AsyncMock(
        return_value=_make_mock_response(VALID_EXTRACTION_JSON)
    )

    config = make_test_config()

    results = await extract_all_meetings_async(events, config, client=mock_client)

    assert len(results) == 1
    assert results[0].meeting_title == "Meeting With Transcript"
    # Only 1 API call made (the one with transcript)
    mock_client.messages.create.assert_called_once()
