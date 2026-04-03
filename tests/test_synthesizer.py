"""Tests for daily cross-meeting synthesis formatting and parsing."""

from src.synthesis.models import ExtractionItem, MeetingExtraction
from src.synthesis.synthesizer import _format_extractions_for_prompt, _parse_synthesis_response


# --- Formatting tests ---


def test_format_extractions_for_prompt():
    """Verify formatting includes meeting title, participants, and non-empty categories."""
    extractions = [
        MeetingExtraction(
            meeting_title="Team Sync",
            meeting_time="2026-04-03T10:00:00-04:00",
            meeting_participants=["Sarah", "Mike"],
            decisions=[
                ExtractionItem(
                    content="Delay launch to Q3",
                    participants=["Sarah"],
                    rationale="API dependency",
                ),
            ],
            substance=[
                ExtractionItem(
                    content="Pipeline review",
                    participants=["Mike"],
                ),
            ],
        ),
    ]

    text = _format_extractions_for_prompt(extractions)
    assert "Team Sync" in text
    assert "Sarah, Mike" in text
    assert "Delay launch to Q3" in text
    assert "Pipeline review" in text
    assert "Decisions" in text
    assert "Substance" in text


def test_format_extractions_skips_low_signal():
    """Verify low_signal extractions are excluded from prompt."""
    extractions = [
        MeetingExtraction(
            meeting_title="Quick Chat",
            meeting_time="2026-04-03T11:00:00-04:00",
            low_signal=True,
        ),
        MeetingExtraction(
            meeting_title="Real Meeting",
            meeting_time="2026-04-03T14:00:00-04:00",
            decisions=[
                ExtractionItem(content="Something decided", participants=["Tom"]),
            ],
        ),
    ]

    text = _format_extractions_for_prompt(extractions)
    assert "Quick Chat" not in text
    assert "Real Meeting" in text


def test_format_extractions_empty_list():
    """Verify empty extraction list produces empty string."""
    text = _format_extractions_for_prompt([])
    assert text == ""


# --- Parsing tests ---


FULL_SYNTHESIS_RESPONSE = """## Substance
- **Item:** Q2 pipeline has 3 deals over $100k, strongest quarter in 2 years (Team Sync -- Tom, Sarah)
- **Item:** New compliance requirement from legal must be addressed before any product launch (Team Sync -- Sarah, Legal)

## Decisions
- **Decision:** Delay product launch to Q3 | **Who:** Sarah, Mike | **Rationale:** API dependency from vendor not ready (Team Sync -- Sarah, Mike)
- **Decision:** Switch internal API from REST to GraphQL | **Who:** Tom, Sarah | **Rationale:** Not stated (Team Sync -- Tom, Sarah)

## Commitments
- **Commitment:** Write API migration spec | **Owner:** Mike | **Deadline:** Friday April 10 | **Status:** created (Team Sync -- Mike)
- **Commitment:** Schedule vendor call | **Owner:** Sarah | **Deadline:** Not stated | **Status:** created (Team Sync -- Sarah)
"""

SYNTHESIS_WITH_EXEC_SUMMARY = """## Executive Summary
Today was dominated by the Q3 launch delay decision and the API migration to GraphQL. Mike committed to writing the migration spec by Friday, and Sarah will coordinate with the vendor on revised timelines. The legal compliance requirement adds a new blocker that needs resolution before any launch can proceed.

## Substance
- **Item:** Q2 pipeline review showed strong numbers (Team Sync -- Tom)

## Decisions
- **Decision:** Delay launch to Q3 (Team Sync -- Sarah, Mike)

## Commitments
- **Commitment:** Write spec by Friday (Team Sync -- Mike)
"""

EMPTY_SYNTHESIS = """## Substance
No items for this day.

## Decisions
No items for this day.

## Commitments
No items for this day.
"""


def test_parse_synthesis_response_full():
    """Test parsing a complete synthesis response with all three sections."""
    result = _parse_synthesis_response(FULL_SYNTHESIS_RESPONSE)

    assert len(result["substance"]) == 2
    assert "Q2 pipeline" in result["substance"][0]
    assert "Team Sync" in result["substance"][0]

    assert len(result["decisions"]) == 2
    assert "Delay product launch" in result["decisions"][0]

    assert len(result["commitments"]) == 2
    assert "API migration spec" in result["commitments"][0]

    assert result["executive_summary"] is None  # No executive summary in this response


def test_parse_synthesis_response_with_executive_summary():
    """Test parsing when executive summary is present."""
    result = _parse_synthesis_response(SYNTHESIS_WITH_EXEC_SUMMARY)

    assert result["executive_summary"] is not None
    assert "Q3 launch delay" in result["executive_summary"]

    assert len(result["substance"]) == 1
    assert len(result["decisions"]) == 1
    assert len(result["commitments"]) == 1


def test_parse_synthesis_response_empty_day():
    """Test parsing when sections say 'No items for this day.'"""
    result = _parse_synthesis_response(EMPTY_SYNTHESIS)

    assert result["substance"] == []
    assert result["decisions"] == []
    assert result["commitments"] == []
    assert result["executive_summary"] is None


def test_synthesize_daily_no_extractions():
    """Verify empty sections returned when no extractions provided."""
    from src.synthesis.synthesizer import synthesize_daily
    from datetime import date

    result = synthesize_daily([], date(2026, 4, 3), {})

    assert result["substance"] == []
    assert result["decisions"] == []
    assert result["commitments"] == []
    assert result["executive_summary"] is None


def test_synthesize_daily_all_low_signal():
    """Verify empty sections when all extractions are low-signal."""
    from src.synthesis.synthesizer import synthesize_daily
    from datetime import date

    extractions = [
        MeetingExtraction(
            meeting_title="Chat",
            meeting_time="2026-04-03T10:00:00",
            low_signal=True,
        ),
    ]

    result = synthesize_daily(extractions, date(2026, 4, 3), {})

    assert result["substance"] == []
    assert result["decisions"] == []
    assert result["commitments"] == []
