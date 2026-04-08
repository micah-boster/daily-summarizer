"""Tests for daily cross-meeting synthesis formatting and structured output."""

import json
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

from src.config import make_test_config
from src.models.sources import ContentType, SourceItem, SourceType
from src.synthesis.models import (
    CommitmentRow,
    DailySynthesisOutput,
    ExtractionItem,
    MeetingExtraction,
    SynthesisItem,
)
from src.synthesis.synthesizer import (
    SYNTHESIS_PROMPT,
    _convert_synthesis_to_dict,
    _format_extractions_for_prompt,
    _format_slack_items_for_prompt,
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


# --- Output model tests ---


def test_daily_synthesis_output_model():
    """Validate DailySynthesisOutput creation with all fields."""
    output = DailySynthesisOutput(
        reasoning="Cross-source analysis...",
        executive_summary="Big day today.",
        substance=[SynthesisItem(content="Pipeline review showed strong Q2 -- Team Sync")],
        decisions=[SynthesisItem(content="Delay launch to Q3 -- Sarah, Mike -- Team Sync")],
        commitments=[
            CommitmentRow(
                who="Mike",
                what="Write API migration spec",
                by_when="2026-04-10",
                source="Team Sync",
            )
        ],
    )
    assert output.reasoning == "Cross-source analysis..."
    assert output.executive_summary == "Big day today."
    assert len(output.substance) == 1
    assert len(output.decisions) == 1
    assert len(output.commitments) == 1
    assert output.commitments[0].who == "Mike"


def test_daily_synthesis_output_schema():
    """Validate DailySynthesisOutput.model_json_schema() produces valid schema."""
    schema = DailySynthesisOutput.model_json_schema()
    assert "properties" in schema
    assert "reasoning" in schema["properties"]
    assert "executive_summary" in schema["properties"]
    assert "substance" in schema["properties"]
    assert "decisions" in schema["properties"]
    assert "commitments" in schema["properties"]


def test_daily_synthesis_output_from_json():
    """Validate parsing a JSON dict into DailySynthesisOutput."""
    data = {
        "reasoning": "Analyzing cross-source data...",
        "executive_summary": "Key decisions on launch timing and API migration.",
        "substance": [
            {"content": "Q2 pipeline has 3 deals over $100k -- Team Sync"},
        ],
        "decisions": [
            {"content": "Delay product launch to Q3 -- Sarah, Mike -- Team Sync"},
        ],
        "commitments": [
            {
                "who": "Mike",
                "what": "Write API migration spec",
                "by_when": "2026-04-10",
                "source": "Team Sync",
            },
            {
                "who": "Sarah",
                "what": "Schedule vendor call",
                "by_when": "unspecified",
                "source": "Team Sync, Slack #proj-alpha",
            },
        ],
    }
    output = DailySynthesisOutput.model_validate(data)
    assert output.executive_summary == "Key decisions on launch timing and API migration."
    assert len(output.substance) == 1
    assert len(output.decisions) == 1
    assert len(output.commitments) == 2
    assert output.commitments[0].who == "Mike"
    assert output.commitments[1].by_when == "unspecified"


def test_daily_synthesis_output_empty():
    """Validate DailySynthesisOutput with all empty categories."""
    data = {
        "reasoning": "No content today.",
        "executive_summary": None,
        "substance": [],
        "decisions": [],
        "commitments": [],
    }
    output = DailySynthesisOutput.model_validate(data)
    assert output.executive_summary is None
    assert len(output.substance) == 0
    assert len(output.decisions) == 0
    assert len(output.commitments) == 0


# --- Conversion tests ---


def test_convert_synthesis_to_dict():
    """Verify _convert_synthesis_to_dict produces backward-compatible format."""
    output = DailySynthesisOutput(
        reasoning="Analysis...",
        executive_summary="Summary text.",
        substance=[
            SynthesisItem(content="Pipeline review -- Team Sync"),
            SynthesisItem(content="New compliance requirement -- Team Sync"),
        ],
        decisions=[
            SynthesisItem(content="Delay launch to Q3 -- Sarah, Mike -- Team Sync"),
        ],
        commitments=[
            CommitmentRow(
                who="Mike",
                what="Write spec",
                by_when="2026-04-10",
                source="Team Sync",
            ),
        ],
    )
    result = _convert_synthesis_to_dict(output)

    assert result["executive_summary"] == "Summary text."
    assert len(result["substance"]) == 2
    # Now returns full SynthesisItem objects (preserves entity_names for attribution)
    assert result["substance"][0].content == "Pipeline review -- Team Sync"
    assert len(result["decisions"]) == 1
    assert len(result["commitments"]) == 1
    # Commitment is a CommitmentRow object
    assert result["commitments"][0].who == "Mike"
    assert result["commitments"][0].what == "Write spec"


def test_convert_synthesis_to_dict_empty():
    """Verify empty output produces empty dict."""
    output = DailySynthesisOutput(reasoning="Nothing.")
    result = _convert_synthesis_to_dict(output)
    assert result["executive_summary"] is None
    assert result["substance"] == []
    assert result["decisions"] == []
    assert result["commitments"] == []


# --- Integration tests with mocked API ---


def _make_mock_response(data: dict) -> MagicMock:
    """Create a mock API response containing structured tool output."""
    content_block = MagicMock()
    content_block.input = data
    response = MagicMock()
    response.content = [content_block]
    return response


STRUCTURED_SYNTHESIS_DATA = {
    "reasoning": "Cross-source analysis: API redesign appears in both standup and Slack.",
    "executive_summary": None,
    "substance": [
        {"content": "Q2 pipeline has 3 deals over $100k -- Team Sync"},
        {"content": "New compliance requirement from legal -- Team Sync"},
    ],
    "decisions": [
        {"content": "Delay product launch to Q3 -- Sarah, Mike -- Team Sync"},
    ],
    "commitments": [
        {
            "who": "Mike",
            "what": "Write API migration spec",
            "by_when": "2026-04-10",
            "source": "Team Sync",
        },
        {
            "who": "Sarah",
            "what": "Schedule vendor call",
            "by_when": "unspecified",
            "source": "Team Sync",
        },
    ],
}


def test_synthesize_daily_structured_output():
    """Verify synthesize_daily returns correct dict from structured JSON."""
    from src.synthesis.synthesizer import synthesize_daily

    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_mock_response(
        STRUCTURED_SYNTHESIS_DATA
    )

    extractions = [
        MeetingExtraction(
            meeting_title="Team Sync",
            meeting_time="2026-04-03T10:00:00-04:00",
            meeting_participants=["Sarah", "Mike"],
            decisions=[
                ExtractionItem(content="Delay launch", participants=["Sarah"]),
            ],
        ),
    ]

    result = synthesize_daily(
        extractions, date(2026, 4, 3), make_test_config(), client=mock_client
    )

    assert len(result["substance"]) == 2
    assert "Q2 pipeline" in result["substance"][0].content
    assert len(result["decisions"]) == 1
    assert "Delay product launch" in result["decisions"][0].content
    assert len(result["commitments"]) == 2
    assert result["commitments"][0].who == "Mike"
    assert result["executive_summary"] is None

    # Verify API was called with tool-based structured output
    call_kwargs = mock_client.messages.create.call_args
    assert "tools" in call_kwargs.kwargs
    assert call_kwargs.kwargs["tool_choice"]["name"] == "output"


def test_synthesize_daily_structured_empty():
    """Verify empty result when all categories empty in structured response."""
    from src.synthesis.synthesizer import synthesize_daily

    empty_data = {
        "reasoning": "No content today.",
        "executive_summary": None,
        "substance": [],
        "decisions": [],
        "commitments": [],
    }
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_mock_response(empty_data)

    extractions = [
        MeetingExtraction(
            meeting_title="Meeting",
            meeting_time="2026-04-03T10:00:00",
            decisions=[ExtractionItem(content="Something", participants=[])],
        ),
    ]

    result = synthesize_daily(
        extractions, date(2026, 4, 3), make_test_config(), client=mock_client
    )

    assert result["substance"] == []
    assert result["decisions"] == []
    assert result["commitments"] == []
    assert result["executive_summary"] is None


def test_synthesize_daily_evidence_validation():
    """Verify evidence-only validation runs on structured content fields."""
    from src.synthesis.synthesizer import synthesize_daily

    # Include evaluative language to trigger validation (pattern: "showed leadership")
    eval_data = {
        "reasoning": "Analysis...",
        "executive_summary": None,
        "substance": [
            {"content": "Sarah showed strong leadership in the product launch -- Team Sync"},
        ],
        "decisions": [],
        "commitments": [],
    }
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_mock_response(eval_data)

    extractions = [
        MeetingExtraction(
            meeting_title="Meeting",
            meeting_time="2026-04-03T10:00:00",
            decisions=[ExtractionItem(content="Something", participants=[])],
        ),
    ]

    # Should not raise, but should log warnings
    import logging
    with patch("src.synthesis.synthesizer.logger") as mock_logger:
        result = synthesize_daily(
            extractions, date(2026, 4, 3), make_test_config(), client=mock_client
        )
        # Check that a warning was logged about evaluative language
        warning_calls = [
            call for call in mock_logger.warning.call_args_list
            if "evaluative language" in str(call)
        ]
        assert len(warning_calls) > 0

    assert len(result["substance"]) == 1


# --- No-extraction edge case tests ---


def test_synthesize_daily_no_extractions():
    """Verify empty sections returned when no extractions provided."""
    from src.synthesis.synthesizer import synthesize_daily

    result = synthesize_daily([], date(2026, 4, 3), make_test_config())

    assert result["substance"] == []
    assert result["decisions"] == []
    assert result["commitments"] == []
    assert result["executive_summary"] is None


def test_synthesize_daily_all_low_signal():
    """Verify empty sections when all extractions are low-signal."""
    from src.synthesis.synthesizer import synthesize_daily

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


# --- Slack items formatting tests ---


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


def test_synthesize_daily_with_slack_only():
    """Verify synthesis runs with only Slack items (no meeting extractions)."""
    from src.synthesis.synthesizer import synthesize_daily

    slack_data = {
        "reasoning": "Slack-only day.",
        "executive_summary": None,
        "substance": [
            {"content": "API redesign discussed -- (per Slack #design-team)"},
        ],
        "decisions": [],
        "commitments": [],
    }
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_mock_response(slack_data)

    items = [_make_slack_item()]
    result = synthesize_daily(
        [], date(2026, 4, 3), make_test_config(), slack_items=items, client=mock_client
    )

    assert len(result["substance"]) == 1
    assert "API redesign" in result["substance"][0].content


# --- Prompt content tests ---


class TestSynthesisPromptDedupRules:
    """Verify SYNTHESIS_PROMPT contains required dedup instructions."""

    def test_prompt_has_cross_source_dedup(self):
        assert "CROSS-SOURCE DEDUPLICATION" in SYNTHESIS_PROMPT

    def test_prompt_has_conflicting_details_rule(self):
        assert "CONFLICTING details" in SYNTHESIS_PROMPT

    def test_prompt_has_uncertain_matches_rule(self):
        assert "UNCERTAIN matches" in SYNTHESIS_PROMPT

    def test_prompt_has_dedup_commitments_rule(self):
        assert "DEDUPLICATE" in SYNTHESIS_PROMPT
