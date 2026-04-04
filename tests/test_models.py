from __future__ import annotations

from datetime import date, datetime, timezone

from src.models.events import (
    Attendee,
    DailySynthesis,
    NormalizedEvent,
    ResponseStatus,
    Section,
)


def _make_synthesis(**kwargs) -> DailySynthesis:
    defaults = {
        "date": date(2026, 4, 1),
        "generated_at": datetime(2026, 4, 1, 8, 0, 0, tzinfo=timezone.utc),
    }
    defaults.update(kwargs)
    return DailySynthesis(**defaults)


class TestNormalizedEvent:
    def test_minimal_required_fields(self):
        event = NormalizedEvent(id="evt1", title="Standup")
        assert event.id == "evt1"
        assert event.title == "Standup"
        assert event.source == "google_calendar"
        assert event.attendees == []
        assert event.status == "confirmed"
        assert event.event_type == "default"
        assert event.all_day is False
        assert event.start_time is None
        assert event.duration_minutes is None

    def test_full_attendee_detail(self):
        attendee = Attendee(
            name="Sarah Chen",
            email="sarah@example.com",
            response_status=ResponseStatus.ACCEPTED,
            is_self=False,
            is_organizer=True,
        )
        event = NormalizedEvent(
            id="evt2",
            title="1:1 with Sarah",
            attendees=[attendee],
        )
        assert len(event.attendees) == 1
        assert event.attendees[0].name == "Sarah Chen"
        assert event.attendees[0].email == "sarah@example.com"
        assert event.attendees[0].response_status == ResponseStatus.ACCEPTED
        assert event.attendees[0].is_organizer is True

    def test_all_day_event(self):
        event = NormalizedEvent(
            id="evt3",
            title="Company Holiday",
            all_day=True,
            date="2026-04-01",
            start_time=None,
            end_time=None,
        )
        assert event.all_day is True
        assert event.date == "2026-04-01"
        assert event.start_time is None
        assert event.end_time is None


    def test_model_dump_does_not_contain_protocol_properties(self):
        event = NormalizedEvent(id="evt1", title="Standup")
        dumped = event.model_dump()
        # Protocol properties must NOT appear in serialized output
        assert "source_id" not in dumped
        assert "source_type" not in dumped
        assert "timestamp" not in dumped
        assert "participants_list" not in dumped
        assert "content_for_synthesis" not in dumped

    def test_attribution_text_returns_expected_string(self):
        event = NormalizedEvent(id="evt1", title="Weekly Sync")
        assert event.attribution_text() == "(per Weekly Sync)"


class TestResponseStatus:
    def test_enum_values_match_google_calendar_api(self):
        assert ResponseStatus.ACCEPTED == "accepted"
        assert ResponseStatus.DECLINED == "declined"
        assert ResponseStatus.TENTATIVE == "tentative"
        assert ResponseStatus.NEEDS_ACTION == "needsAction"

    def test_enum_is_str(self):
        assert isinstance(ResponseStatus.ACCEPTED, str)


class TestDailySynthesis:
    def test_default_stub_sections(self):
        synthesis = _make_synthesis()
        assert synthesis.substance.title == "Substance"
        assert synthesis.substance.items == []
        assert synthesis.decisions.title == "Decisions"
        assert synthesis.decisions.items == []
        assert synthesis.commitments.title == "Commitments"
        assert synthesis.commitments.items == []

    def test_model_dump_json_produces_valid_json(self):
        import json

        synthesis = _make_synthesis()
        json_str = synthesis.model_dump_json()
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)
        assert parsed["date"] == "2026-04-01"
        assert parsed["meeting_count"] == 0

    def test_round_trip_json_serialization(self):
        synthesis = _make_synthesis(
            meeting_count=3,
            total_meeting_hours=2.5,
            timed_events=[
                NormalizedEvent(
                    id="evt10",
                    title="Team Sync",
                    start_time=datetime(2026, 4, 1, 14, 0, 0, tzinfo=timezone.utc),
                    end_time=datetime(2026, 4, 1, 14, 30, 0, tzinfo=timezone.utc),
                    duration_minutes=30,
                )
            ],
        )
        json_str = synthesis.model_dump_json()
        restored = DailySynthesis.model_validate_json(json_str)
        assert restored.meeting_count == 3
        assert restored.total_meeting_hours == 2.5
        assert len(restored.timed_events) == 1
        assert restored.timed_events[0].title == "Team Sync"
        assert restored.timed_events[0].duration_minutes == 30

    def test_defaults(self):
        synthesis = _make_synthesis()
        assert synthesis.meeting_count == 0
        assert synthesis.total_meeting_hours == 0.0
        assert synthesis.transcript_count == 0
        assert synthesis.all_day_events == []
        assert synthesis.timed_events == []
        assert synthesis.declined_events == []
        assert synthesis.cancelled_events == []
