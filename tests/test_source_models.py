from __future__ import annotations

from datetime import datetime, timezone

from src.models.commitments import Commitment, CommitmentStatus
from src.models.events import NormalizedEvent
from src.models.sources import (
    ContentType,
    SourceItem,
    SourceType,
    SynthesisSource,
)


def _make_source_item(**kwargs) -> SourceItem:
    defaults = {
        "id": "slack_C123_1234567890",
        "source_type": SourceType.SLACK_MESSAGE,
        "content_type": ContentType.MESSAGE,
        "title": "Message in #general",
        "timestamp": datetime(2026, 4, 1, 10, 0, 0, tzinfo=timezone.utc),
        "content": "Hey team, the deploy is done.",
        "source_url": "https://slack.com/archives/C123/p1234567890",
    }
    defaults.update(kwargs)
    return SourceItem(**defaults)


def _make_commitment(**kwargs) -> Commitment:
    defaults = {
        "id": "commit_001",
        "owner": "Sarah Chen",
        "description": "Update the API docs by Friday",
        "source_id": "slack_C123_1234567890",
        "source_type": "source_item",
    }
    defaults.update(kwargs)
    return Commitment(**defaults)


class TestSourceType:
    def test_all_expected_members_exist(self):
        expected = [
            "SLACK_MESSAGE", "SLACK_THREAD",
            "HUBSPOT_DEAL", "HUBSPOT_CONTACT", "HUBSPOT_TICKET", "HUBSPOT_ACTIVITY",
            "GOOGLE_DOC_EDIT", "GOOGLE_DOC_COMMENT",
            "MEETING",
        ]
        for member in expected:
            assert hasattr(SourceType, member), f"Missing SourceType.{member}"

    def test_values_are_lowercase_snake_case(self):
        assert SourceType.SLACK_MESSAGE == "slack_message"
        assert SourceType.HUBSPOT_DEAL == "hubspot_deal"
        assert SourceType.GOOGLE_DOC_EDIT == "google_doc_edit"
        assert SourceType.MEETING == "meeting"

    def test_str_enum_comparison(self):
        assert SourceType.SLACK_MESSAGE == "slack_message"
        assert isinstance(SourceType.SLACK_MESSAGE, str)


class TestContentType:
    def test_all_expected_members_exist(self):
        expected = [
            "MESSAGE", "THREAD", "NOTE", "EDIT",
            "STAGE_CHANGE", "COMMENT", "ACTIVITY",
        ]
        for member in expected:
            assert hasattr(ContentType, member), f"Missing ContentType.{member}"

    def test_values_are_lowercase(self):
        assert ContentType.MESSAGE == "message"
        assert ContentType.STAGE_CHANGE == "stage_change"
        assert ContentType.ACTIVITY == "activity"

    def test_str_enum_comparison(self):
        assert ContentType.THREAD == "thread"
        assert isinstance(ContentType.THREAD, str)


class TestCommitmentStatus:
    def test_all_expected_members_exist(self):
        expected = ["OPEN", "COMPLETED", "DEFERRED"]
        for member in expected:
            assert hasattr(CommitmentStatus, member), f"Missing CommitmentStatus.{member}"

    def test_values_are_lowercase(self):
        assert CommitmentStatus.OPEN == "open"
        assert CommitmentStatus.COMPLETED == "completed"
        assert CommitmentStatus.DEFERRED == "deferred"

    def test_str_enum_comparison(self):
        assert CommitmentStatus.OPEN == "open"
        assert isinstance(CommitmentStatus.OPEN, str)


class TestSourceItem:
    def test_minimal_required_fields(self):
        item = _make_source_item()
        assert item.id == "slack_C123_1234567890"
        assert item.source_type == SourceType.SLACK_MESSAGE
        assert item.content_type == ContentType.MESSAGE
        assert item.title == "Message in #general"
        assert item.content == "Hey team, the deploy is done."
        assert item.source_url == "https://slack.com/archives/C123/p1234567890"

    def test_full_field_instantiation(self):
        item = _make_source_item(
            summary="Deploy completed",
            participants=["Sarah", "Mike"],
            context={"channel": "general", "thread_ts": "123.456"},
            display_context="Slack #general",
            raw_data={"ts": "1234567890.000"},
        )
        assert item.summary == "Deploy completed"
        assert item.participants == ["Sarah", "Mike"]
        assert item.context == {"channel": "general", "thread_ts": "123.456"}
        assert item.display_context == "Slack #general"
        assert item.raw_data == {"ts": "1234567890.000"}

    def test_default_values(self):
        item = _make_source_item()
        assert item.summary is None
        assert item.participants == []
        assert item.context == {}
        assert item.display_context == ""
        assert item.raw_data is None

    def test_json_round_trip(self):
        item = _make_source_item(
            summary="Deploy done",
            participants=["Sarah"],
            display_context="Slack #general",
        )
        json_str = item.model_dump_json()
        restored = SourceItem.model_validate_json(json_str)
        assert restored.id == item.id
        assert restored.source_type == item.source_type
        assert restored.content_type == item.content_type
        assert restored.title == item.title
        assert restored.content == item.content
        assert restored.summary == item.summary
        assert restored.participants == item.participants
        assert restored.display_context == item.display_context

    def test_source_id_property_returns_id(self):
        item = _make_source_item(id="test_abc")
        assert item.source_id == "test_abc"

    def test_participants_list_property_returns_participants(self):
        item = _make_source_item(participants=["Alice", "Bob"])
        assert item.participants_list == ["Alice", "Bob"]

    def test_content_for_synthesis_returns_summary_when_present(self):
        item = _make_source_item(summary="Short version", content="Long content here")
        assert item.content_for_synthesis == "Short version"

    def test_content_for_synthesis_returns_content_when_no_summary(self):
        item = _make_source_item(summary=None, content="Full content text")
        assert item.content_for_synthesis == "Full content text"

    def test_attribution_text_with_display_context(self):
        item = _make_source_item(display_context="Slack #general")
        assert item.attribution_text() == "(per Slack #general)"

    def test_attribution_text_falls_back_to_source_type(self):
        item = _make_source_item(display_context="")
        assert item.attribution_text() == "(per slack_message)"


class TestCommitment:
    def test_minimal_required_fields(self):
        c = _make_commitment()
        assert c.id == "commit_001"
        assert c.owner == "Sarah Chen"
        assert c.description == "Update the API docs by Friday"
        assert c.source_id == "slack_C123_1234567890"
        assert c.source_type == "source_item"

    def test_full_fields_with_by_when(self):
        c = _make_commitment(
            by_when=datetime(2026, 4, 5, 17, 0, 0, tzinfo=timezone.utc),
            status=CommitmentStatus.COMPLETED,
            source_context="Slack #general",
            extracted_at=datetime(2026, 4, 1, 10, 5, 0, tzinfo=timezone.utc),
        )
        assert c.by_when == datetime(2026, 4, 5, 17, 0, 0, tzinfo=timezone.utc)
        assert c.status == CommitmentStatus.COMPLETED
        assert c.source_context == "Slack #general"
        assert c.extracted_at is not None

    def test_default_status_is_open(self):
        c = _make_commitment()
        assert c.status == CommitmentStatus.OPEN

    def test_optional_by_when_defaults_to_none(self):
        c = _make_commitment()
        assert c.by_when is None

    def test_json_round_trip(self):
        c = _make_commitment(
            by_when=datetime(2026, 4, 5, 17, 0, 0, tzinfo=timezone.utc),
            source_context="Slack #general",
        )
        json_str = c.model_dump_json()
        restored = Commitment.model_validate_json(json_str)
        assert restored.id == c.id
        assert restored.owner == c.owner
        assert restored.description == c.description
        assert restored.by_when == c.by_when
        assert restored.source_id == c.source_id
        assert restored.source_type == c.source_type
        assert restored.source_context == c.source_context


class TestSynthesisSourceProtocol:
    def test_source_item_satisfies_protocol(self):
        item = _make_source_item()
        assert isinstance(item, SynthesisSource)

    def test_normalized_event_satisfies_protocol(self):
        event = NormalizedEvent(id="evt1", title="Standup")
        assert isinstance(event, SynthesisSource)

    def test_source_item_attribution_text_format(self):
        item = _make_source_item(display_context="Slack #general")
        text = item.attribution_text()
        assert text.startswith("(per ")
        assert text.endswith(")")

    def test_normalized_event_attribution_text_format(self):
        event = NormalizedEvent(id="evt1", title="Standup")
        text = event.attribution_text()
        assert text.startswith("(per ")
        assert text.endswith(")")

    def test_source_item_protocol_properties(self):
        item = _make_source_item(
            id="si_1",
            participants=["Alice"],
            summary="Quick update",
        )
        assert item.source_id == "si_1"
        assert item.timestamp is not None
        assert item.participants_list == ["Alice"]
        assert item.content_for_synthesis == "Quick update"

    def test_normalized_event_protocol_properties(self):
        event = NormalizedEvent(
            id="evt1",
            title="Standup",
            start_time=datetime(2026, 4, 1, 9, 0, 0, tzinfo=timezone.utc),
            transcript_text="Discussed roadmap",
        )
        assert event.source_id == "evt1"
        assert event.timestamp == datetime(2026, 4, 1, 9, 0, 0, tzinfo=timezone.utc)
        assert event.participants_list == []
        assert event.content_for_synthesis == "Discussed roadmap"

    def test_normalized_event_participants_list_uses_name_or_email(self):
        from src.models.events import Attendee

        event = NormalizedEvent(
            id="evt1",
            title="Meeting",
            attendees=[
                Attendee(name="Sarah", email="sarah@example.com"),
                Attendee(name=None, email="bob@example.com"),
            ],
        )
        assert event.participants_list == ["Sarah", "bob@example.com"]
