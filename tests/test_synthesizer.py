"""Tests for daily cross-meeting synthesis formatting and parsing."""

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

from src.config import make_test_config
from src.models.sources import ContentType, SourceItem, SourceType
from src.synthesis.models import ExtractionItem, MeetingExtraction
from src.synthesis.synthesizer import (
    SYNTHESIS_PROMPT,
    _format_extractions_for_prompt,
    _format_slack_items_for_prompt,
    _parse_synthesis_response,
)


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

    result = synthesize_daily([], date(2026, 4, 3), make_test_config())

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

    result = synthesize_daily(extractions, date(2026, 4, 3), make_test_config())

    assert result["substance"] == []
    assert result["decisions"] == []
    assert result["commitments"] == []


# --- Slack items integration tests ---


def _make_slack_item(**overrides) -> SourceItem:
    defaults = {
        "id": "slack_C123_1234567890",
        "source_type": SourceType.SLACK_MESSAGE,
        "content_type": ContentType.MESSAGE,
        "title": "Message from Alice",
        "timestamp": datetime(2026, 4, 1, 10, 0, 0, tzinfo=timezone.utc),
        "content": "Let's discuss the API redesign",
        "source_url": "https://slack.com/archives/C123/p1234567890",
        "display_context": "Slack #design-team",
        "participants": ["Alice"],
    }
    defaults.update(overrides)
    return SourceItem(**defaults)


def test_format_slack_items_channel_message():
    """Verify channel messages formatted with attribution."""
    items = [_make_slack_item()]
    text = _format_slack_items_for_prompt(items)
    assert "Slack #design-team" in text
    assert "Message from Alice" in text
    assert "API redesign" in text
    assert "(per Slack #design-team)" in text


def test_format_slack_items_dm_message():
    """Verify DM messages formatted with DM attribution."""
    items = [
        _make_slack_item(
            display_context="Slack DM with Bob",
            title="Message from Bob",
            content="Project update",
        )
    ]
    text = _format_slack_items_for_prompt(items)
    assert "Slack DM with Bob" in text
    assert "(per Slack DM with Bob)" in text


def test_format_slack_items_thread():
    """Verify thread items include full content."""
    items = [
        _make_slack_item(
            source_type=SourceType.SLACK_THREAD,
            content_type=ContentType.THREAD,
            title="Thread: What do we think about...",
            content="Alice: What do we think?\nBob: I agree\nCarol: Me too",
        )
    ]
    text = _format_slack_items_for_prompt(items)
    assert "Thread:" in text
    assert "Alice: What do we think?" in text
    assert "Bob: I agree" in text


def test_format_slack_items_empty():
    """Verify empty list produces empty string."""
    assert _format_slack_items_for_prompt([]) == ""


def test_synthesize_daily_accepts_slack_items_none():
    """Verify backward compat: slack_items=None doesn't break."""
    from src.synthesis.synthesizer import synthesize_daily

    result = synthesize_daily([], date(2026, 4, 3), make_test_config(), slack_items=None)
    assert result["substance"] == []


@patch("src.synthesis.synthesizer.anthropic")
def test_synthesize_daily_with_slack_only(mock_anthropic):
    """Verify synthesis runs with only Slack items (no meeting extractions)."""
    from src.synthesis.synthesizer import synthesize_daily

    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(text="## Substance\n- API redesign discussed — (per Slack #design-team)\n\n## Decisions\nNo items for this day.\n\n## Commitments\nNo items for this day.\n")
    ]
    mock_client.messages.create.return_value = mock_response

    items = [_make_slack_item()]
    result = synthesize_daily([], date(2026, 4, 3), make_test_config(), slack_items=items)

    assert len(result["substance"]) == 1
    assert "API redesign" in result["substance"][0]


# --- Cross-source dedup and table-format commitment tests ---


class TestSynthesisPromptDedupRules:
    """Verify SYNTHESIS_PROMPT contains required dedup instructions."""

    def test_prompt_has_cross_source_dedup(self):
        assert "CROSS-SOURCE DEDUPLICATION" in SYNTHESIS_PROMPT

    def test_prompt_has_conflicting_details_rule(self):
        assert "CONFLICTING details" in SYNTHESIS_PROMPT

    def test_prompt_has_uncertain_matches_rule(self):
        assert "UNCERTAIN matches" in SYNTHESIS_PROMPT

    def test_prompt_has_commitment_table_headers(self):
        assert "| Who | What | By When | Source |" in SYNTHESIS_PROMPT

    def test_prompt_has_dedup_commitments_rule(self):
        assert "DEDUP COMMITMENTS" in SYNTHESIS_PROMPT

    def test_prompt_has_date_normalization(self):
        assert "Date normalization" in SYNTHESIS_PROMPT


COMMITMENTS_TABLE_RESPONSE = """## Substance
- Pipeline review showed strong Q2 numbers — Team Sync

## Decisions
No items for this day.

## Commitments

| Who | What | By When | Source |
|-----|------|---------|--------|
| John | Send deck to partners | 2026-04-10 | standup |
| Sarah | Schedule vendor call | unspecified | standup, Slack #proj-alpha |
"""

COMMITMENTS_BULLET_RESPONSE = """## Substance
- Pipeline review — Team Sync

## Decisions
No items for this day.

## Commitments
- **Commitment:** Send deck | **Owner:** John | **Deadline:** Friday April 10 | standup
"""


class TestParseCommitmentsTable:
    """Verify _parse_synthesis_response handles table-format commitments."""

    def test_parse_table_format_commitments(self):
        result = _parse_synthesis_response(COMMITMENTS_TABLE_RESPONSE)
        assert len(result["commitments"]) == 2
        assert "John" in result["commitments"][0]
        assert "Send deck" in result["commitments"][0]
        assert "Sarah" in result["commitments"][1]

    def test_parse_table_preserves_pipe_format(self):
        result = _parse_synthesis_response(COMMITMENTS_TABLE_RESPONSE)
        # Each commitment should be a pipe-delimited row
        assert result["commitments"][0].startswith("|")
        assert result["commitments"][0].endswith("|")

    def test_parse_bullet_format_backward_compat(self):
        """Bullet-list format commitments still parse correctly."""
        result = _parse_synthesis_response(COMMITMENTS_BULLET_RESPONSE)
        assert len(result["commitments"]) == 1
        assert "Send deck" in result["commitments"][0]

    def test_substance_still_parsed_with_table_commitments(self):
        result = _parse_synthesis_response(COMMITMENTS_TABLE_RESPONSE)
        assert len(result["substance"]) == 1
        assert "Pipeline review" in result["substance"][0]


class TestParseSynthesisEdgeCases:
    """Edge case tests for _parse_synthesis_response handling unusual Claude outputs."""

    def test_empty_response(self):
        result = _parse_synthesis_response("")
        assert result["executive_summary"] is None
        assert result["substance"] == []
        assert result["decisions"] == []
        assert result["commitments"] == []

    def test_no_sections_response(self):
        result = _parse_synthesis_response("Random text no headers")
        assert result["executive_summary"] is None
        assert result["substance"] == []
        assert result["decisions"] == []
        assert result["commitments"] == []

    def test_partial_sections(self):
        response = "## Substance\n- Item one about pipeline review\n"
        result = _parse_synthesis_response(response)
        assert len(result["substance"]) == 1
        assert "Item one" in result["substance"][0]
        assert result["decisions"] == []
        assert result["commitments"] == []

    def test_no_items_text(self):
        response = (
            "## Substance\nNo items for this day.\n\n"
            "## Decisions\nNo items for this day.\n\n"
            "## Commitments\nNo items for this day.\n"
        )
        result = _parse_synthesis_response(response)
        assert result["substance"] == []
        assert result["decisions"] == []
        assert result["commitments"] == []

    def test_missing_executive_summary(self):
        response = "## Substance\n- Something happened\n\n## Decisions\n- A decision\n"
        result = _parse_synthesis_response(response)
        assert result["executive_summary"] is None
        assert len(result["substance"]) == 1
        assert len(result["decisions"]) == 1
