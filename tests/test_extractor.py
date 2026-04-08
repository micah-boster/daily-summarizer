"""Tests for structured output extraction models and API integration."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import anthropic

from src.config import make_test_config
from src.models.events import Attendee, NormalizedEvent
from src.synthesis.extractor import _convert_output_to_extraction, extract_meeting
from src.synthesis.models import (
    ExtractionItem,
    ExtractionItemOutput,
    MeetingExtraction,
    MeetingExtractionOutput,
)


# --- Model tests ---


def test_extraction_item_model():
    """Validate ExtractionItem creation with all fields."""
    item = ExtractionItem(
        content="Launch delayed to Q3",
        participants=["Sarah", "Mike"],
        rationale="API dependency not ready",
    )
    assert item.content == "Launch delayed to Q3"
    assert item.participants == ["Sarah", "Mike"]
    assert item.rationale == "API dependency not ready"


def test_extraction_item_defaults():
    """Validate ExtractionItem with minimal fields."""
    item = ExtractionItem(content="Something happened")
    assert item.participants == []
    assert item.rationale is None


def test_meeting_extraction_model():
    """Validate MeetingExtraction with populated categories."""
    extraction = MeetingExtraction(
        meeting_title="Team Sync",
        meeting_time="2026-04-03T10:00:00-04:00",
        meeting_participants=["Sarah", "Mike", "Tom"],
        decisions=[
            ExtractionItem(content="Delay launch", participants=["Sarah"]),
        ],
        commitments=[
            ExtractionItem(content="Write spec by Friday", participants=["Mike"]),
        ],
        substance=[
            ExtractionItem(content="Q2 pipeline review", participants=["Tom"]),
        ],
    )
    assert extraction.meeting_title == "Team Sync"
    assert len(extraction.decisions) == 1
    assert len(extraction.commitments) == 1
    assert len(extraction.substance) == 1
    assert len(extraction.open_questions) == 0
    assert len(extraction.tensions) == 0
    assert extraction.low_signal is False


def test_meeting_extraction_low_signal():
    """Verify low_signal=True when all categories empty."""
    extraction = MeetingExtraction(
        meeting_title="Quick Chat",
        meeting_time="2026-04-03T11:00:00-04:00",
        low_signal=True,
    )
    assert extraction.low_signal is True
    assert len(extraction.decisions) == 0
    assert len(extraction.commitments) == 0


# --- Output model tests ---


def test_extraction_item_output_model():
    """Validate ExtractionItemOutput creation with all fields."""
    item = ExtractionItemOutput(
        content="Launch delayed to Q3",
        participants=["Sarah", "Mike"],
        rationale="API dependency not ready",
    )
    assert item.content == "Launch delayed to Q3"
    assert item.participants == ["Sarah", "Mike"]
    assert item.rationale == "API dependency not ready"


def test_extraction_item_output_defaults():
    """Validate ExtractionItemOutput with minimal fields."""
    item = ExtractionItemOutput(content="Something happened")
    assert item.participants == []
    assert item.rationale is None


def test_meeting_extraction_output_schema():
    """Validate MeetingExtractionOutput.model_json_schema() produces valid schema."""
    schema = MeetingExtractionOutput.model_json_schema()
    assert "properties" in schema
    assert "reasoning" in schema["properties"]
    assert "decisions" in schema["properties"]
    assert "commitments" in schema["properties"]
    assert "substance" in schema["properties"]
    assert "open_questions" in schema["properties"]
    assert "tensions" in schema["properties"]


def test_meeting_extraction_output_from_json():
    """Validate parsing a JSON dict into MeetingExtractionOutput."""
    data = {
        "reasoning": "The meeting covered launch timing and API migration.",
        "decisions": [
            {
                "content": "Delay product launch to Q3",
                "participants": ["Sarah", "Mike"],
                "rationale": "API dependency from vendor not ready",
            }
        ],
        "commitments": [
            {
                "content": "Write API migration spec",
                "participants": ["Mike"],
                "rationale": "Friday April 10",
            }
        ],
        "substance": [
            {
                "content": "Q2 pipeline has 3 deals over $100k",
                "participants": ["Tom"],
                "rationale": None,
            }
        ],
        "open_questions": [],
        "tensions": [],
    }
    output = MeetingExtractionOutput.model_validate(data)
    assert output.reasoning == "The meeting covered launch timing and API migration."
    assert len(output.decisions) == 1
    assert output.decisions[0].content == "Delay product launch to Q3"
    assert output.decisions[0].participants == ["Sarah", "Mike"]
    assert len(output.commitments) == 1
    assert len(output.substance) == 1
    assert len(output.open_questions) == 0
    assert len(output.tensions) == 0


def test_meeting_extraction_output_empty():
    """Validate MeetingExtractionOutput with all empty categories."""
    data = {
        "reasoning": "No substantive content in this meeting.",
        "decisions": [],
        "commitments": [],
        "substance": [],
        "open_questions": [],
        "tensions": [],
    }
    output = MeetingExtractionOutput.model_validate(data)
    assert len(output.decisions) == 0
    assert len(output.commitments) == 0
    assert len(output.substance) == 0


# --- Conversion tests ---


def test_convert_output_to_extraction():
    """Verify _convert_output_to_extraction maps fields correctly."""
    output = MeetingExtractionOutput(
        reasoning="Test reasoning",
        decisions=[
            ExtractionItemOutput(
                content="Delay launch",
                participants=["Sarah"],
                rationale="API dependency",
            )
        ],
        substance=[
            ExtractionItemOutput(
                content="Pipeline review",
                participants=["Tom"],
            )
        ],
    )
    extraction = _convert_output_to_extraction(
        output,
        meeting_title="Team Sync",
        meeting_time="2026-04-03T10:00:00-04:00",
        participants=["Sarah", "Tom"],
    )
    assert extraction.meeting_title == "Team Sync"
    assert extraction.meeting_time == "2026-04-03T10:00:00-04:00"
    assert extraction.meeting_participants == ["Sarah", "Tom"]
    assert len(extraction.decisions) == 1
    assert extraction.decisions[0].content == "Delay launch"
    assert isinstance(extraction.decisions[0], ExtractionItem)
    assert len(extraction.substance) == 1
    assert extraction.low_signal is False


def test_convert_output_to_extraction_empty():
    """Verify low_signal=True when all categories empty."""
    output = MeetingExtractionOutput(reasoning="Nothing here")
    extraction = _convert_output_to_extraction(
        output, "Quick Chat", "2026-04-03T11:00:00", []
    )
    assert extraction.low_signal is True


# --- Integration tests with mocked API ---


def _make_mock_response(data: dict) -> MagicMock:
    """Create a mock API response containing structured tool output."""
    content_block = MagicMock()
    content_block.input = data
    response = MagicMock()
    response.content = [content_block]
    return response


STRUCTURED_RESPONSE_DATA = {
    "reasoning": "Meeting covered launch delay and API migration decisions.",
    "decisions": [
        {
            "content": "Delay product launch to Q3",
            "participants": ["Sarah", "Mike"],
            "rationale": "API dependency from vendor not ready",
        },
        {
            "content": "Switch from REST to GraphQL for internal API",
            "participants": ["Tom", "Sarah"],
            "rationale": None,
        },
    ],
    "commitments": [
        {
            "content": "Write API migration spec by Friday",
            "participants": ["Mike"],
            "rationale": "Friday April 10",
        }
    ],
    "substance": [
        {
            "content": "Q2 pipeline has 3 deals over $100k",
            "participants": ["Tom"],
            "rationale": None,
        }
    ],
    "open_questions": [
        {
            "content": "Will the vendor API support batch operations?",
            "participants": ["Mike"],
            "rationale": None,
        }
    ],
    "tensions": [],
}


def test_extract_meeting_structured_output():
    """Verify extract_meeting returns correct MeetingExtraction from structured JSON."""
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_mock_response(
        STRUCTURED_RESPONSE_DATA
    )

    event = NormalizedEvent(
        id="test-1",
        title="Team Sync",
        start_time=datetime(2026, 4, 3, 10, 0, tzinfo=timezone.utc),
        transcript_text="Some transcript content here...",
        attendees=[
            Attendee(email="sarah@test.com", name="Sarah", is_self=False),
            Attendee(email="mike@test.com", name="Mike", is_self=False),
        ],
    )

    config = make_test_config()
    result = extract_meeting(event, config, client=mock_client)

    assert result is not None
    assert result.meeting_title == "Team Sync"
    assert len(result.decisions) == 2
    assert result.decisions[0].content == "Delay product launch to Q3"
    assert result.decisions[0].participants == ["Sarah", "Mike"]
    assert result.decisions[0].rationale == "API dependency from vendor not ready"
    assert len(result.commitments) == 1
    assert len(result.substance) == 1
    assert len(result.open_questions) == 1
    assert len(result.tensions) == 0
    assert result.low_signal is False

    # Verify API was called with tool-based structured output
    call_kwargs = mock_client.messages.create.call_args
    assert "tools" in call_kwargs.kwargs
    assert call_kwargs.kwargs["tool_choice"]["name"] == "output"


def test_extract_meeting_structured_output_empty():
    """Verify extract_meeting returns low_signal=True when all categories empty."""
    empty_data = {
        "reasoning": "No substantive content.",
        "decisions": [],
        "commitments": [],
        "substance": [],
        "open_questions": [],
        "tensions": [],
    }
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_mock_response(empty_data)

    event = NormalizedEvent(
        id="test-2",
        title="Quick Call",
        start_time=datetime(2026, 4, 3, 11, 0, tzinfo=timezone.utc),
        transcript_text="Just some chatter.",
    )

    config = make_test_config()
    result = extract_meeting(event, config, client=mock_client)

    assert result is not None
    assert result.low_signal is True
    assert len(result.decisions) == 0
    assert len(result.commitments) == 0


def test_extract_meeting_no_transcript():
    """Verify extract_meeting returns None when event has no transcript_text."""
    event = NormalizedEvent(
        id="test-4",
        title="Meeting Without Transcript",
        start_time=datetime(2026, 4, 3, 10, 0, tzinfo=timezone.utc),
        transcript_text=None,
    )
    config = make_test_config()
    result = extract_meeting(event, config)
    assert result is None


def test_extract_meeting_empty_transcript():
    """Verify extract_meeting returns None when event has empty transcript."""
    event = NormalizedEvent(
        id="test-5",
        title="Meeting With Empty Transcript",
        start_time=datetime(2026, 4, 3, 10, 0, tzinfo=timezone.utc),
        transcript_text="",
    )
    config = make_test_config()
    result = extract_meeting(event, config)
    assert result is None
