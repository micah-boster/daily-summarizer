"""Tests for synthesis extraction models and response parsing."""

from datetime import datetime, timezone

from src.models.events import Attendee, NormalizedEvent
from src.synthesis.extractor import _parse_extraction_response, _parse_section_items
from src.synthesis.models import ExtractionItem, MeetingExtraction


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


# --- Parser tests ---


FULL_RESPONSE = """## Decisions
- **Decision:** Delay product launch to Q3
- **Participants:** Sarah, Mike
- **Rationale:** API dependency from vendor not ready until June

- **Decision:** Switch from REST to GraphQL for internal API
- **Participants:** Tom, Sarah
- **Rationale:** Not stated

## Commitments
- **Commitment:** Write API migration spec
- **Owner:** Mike
- **Deadline:** Friday April 10

- **Commitment:** Schedule vendor call
- **Owner:** Sarah
- **Deadline:** Not stated

## Substance
- **Item:** Q2 pipeline has 3 deals over $100k
- **Participants:** Tom
- **Context:** Pipeline review showed strong quarter

- **Item:** New compliance requirement from legal
- **Participants:** Sarah, Legal team
- **Context:** Must be addressed before launch

## Open Questions
- **Question:** Will the vendor API support batch operations?
- **Raised by:** Mike

## Tensions
- **Tension:** Timeline feasibility for Q3 launch
- **Participants:** Sarah, Tom
- **Status:** unresolved
"""

EMPTY_RESPONSE = """## Decisions
None

## Commitments
None

## Substance
None

## Open Questions
None

## Tensions
None
"""

PARTIAL_RESPONSE = """## Decisions
- **Decision:** Approved the new hiring plan
- **Participants:** HR Lead
- **Rationale:** Budget confirmed for Q3

## Commitments
- **Commitment:** Post job listings by next week
- **Owner:** HR Lead
- **Deadline:** April 10

## Substance
None

## Open Questions
None

## Tensions
None
"""


def test_parse_extraction_response_full():
    """Test parsing a complete Claude response with all five sections."""
    result = _parse_extraction_response(
        FULL_RESPONSE,
        meeting_title="Team Sync",
        meeting_time="2026-04-03T10:00:00-04:00",
        participants=["Sarah", "Mike", "Tom"],
    )

    assert result.meeting_title == "Team Sync"
    assert len(result.decisions) == 2
    assert result.decisions[0].content == "Delay product launch to Q3"
    assert result.decisions[0].participants == ["Sarah", "Mike"]
    assert result.decisions[0].rationale == "API dependency from vendor not ready until June"
    assert result.decisions[1].rationale is None  # "Not stated" -> None

    assert len(result.commitments) == 2
    assert result.commitments[0].participants == ["Mike"]
    assert result.commitments[0].rationale == "Friday April 10"  # Deadline captured

    assert len(result.substance) == 2
    assert "Q2 pipeline" in result.substance[0].content

    assert len(result.open_questions) == 1
    assert "batch operations" in result.open_questions[0].content

    assert len(result.tensions) == 1
    assert result.tensions[0].rationale == "unresolved"

    assert result.low_signal is False


def test_parse_extraction_response_empty():
    """Test parsing a response where all sections say 'None'."""
    result = _parse_extraction_response(
        EMPTY_RESPONSE,
        meeting_title="Quick Call",
        meeting_time="2026-04-03T11:00:00-04:00",
        participants=[],
    )

    assert len(result.decisions) == 0
    assert len(result.commitments) == 0
    assert len(result.substance) == 0
    assert len(result.open_questions) == 0
    assert len(result.tensions) == 0
    assert result.low_signal is True


def test_parse_extraction_response_partial():
    """Test parsing response with only some sections populated."""
    result = _parse_extraction_response(
        PARTIAL_RESPONSE,
        meeting_title="HR Meeting",
        meeting_time="2026-04-03T14:00:00-04:00",
        participants=["HR Lead"],
    )

    assert len(result.decisions) == 1
    assert len(result.commitments) == 1
    assert len(result.substance) == 0
    assert len(result.open_questions) == 0
    assert len(result.tensions) == 0
    assert result.low_signal is False


def test_parse_section_items_none():
    """Test that 'None' text produces empty list."""
    items = _parse_section_items("None", "decisions")
    assert items == []


def test_parse_section_items_empty():
    """Test that empty text produces empty list."""
    items = _parse_section_items("", "decisions")
    assert items == []


def test_extract_meeting_no_transcript():
    """Verify extract_meeting returns None when event has no transcript_text."""
    from src.synthesis.extractor import extract_meeting

    event = NormalizedEvent(
        id="test-1",
        title="Meeting Without Transcript",
        start_time=datetime(2026, 4, 3, 10, 0, tzinfo=timezone.utc),
        transcript_text=None,
    )
    result = extract_meeting(event, {})
    assert result is None


def test_extract_meeting_empty_transcript():
    """Verify extract_meeting returns None when event has empty transcript."""
    from src.synthesis.extractor import extract_meeting

    event = NormalizedEvent(
        id="test-2",
        title="Meeting With Empty Transcript",
        start_time=datetime(2026, 4, 3, 10, 0, tzinfo=timezone.utc),
        transcript_text="",
    )
    result = extract_meeting(event, {})
    assert result is None
