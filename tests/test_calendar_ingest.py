"""Tests for Google Calendar ingestion and event normalization."""

from __future__ import annotations

from datetime import datetime, timezone

from src.ingest.calendar import (
    apply_exclusion_patterns,
    categorize_events,
    extract_meeting_link,
    normalize_event,
)
from src.models.events import NormalizedEvent, ResponseStatus


def _make_timed_event(**overrides) -> dict:
    """Create a realistic mock timed event dict from Google Calendar API."""
    event = {
        "id": "evt_timed_1",
        "summary": "Team Standup",
        "status": "confirmed",
        "start": {"dateTime": "2026-04-01T09:00:00-04:00"},
        "end": {"dateTime": "2026-04-01T09:30:00-04:00"},
        "attendees": [
            {
                "email": "me@example.com",
                "displayName": "Me",
                "responseStatus": "accepted",
                "self": True,
            },
            {
                "email": "sarah@example.com",
                "displayName": "Sarah Chen",
                "responseStatus": "accepted",
            },
        ],
        "_calendar_id": "primary",
    }
    event.update(overrides)
    return event


def _make_all_day_event(**overrides) -> dict:
    """Create a realistic mock all-day event dict."""
    event = {
        "id": "evt_allday_1",
        "summary": "Company Holiday",
        "status": "confirmed",
        "start": {"date": "2026-04-01"},
        "end": {"date": "2026-04-02"},
        "_calendar_id": "primary",
    }
    event.update(overrides)
    return event


class TestNormalizeTimedEvent:
    def test_produces_correct_normalized_event(self):
        raw = _make_timed_event()
        event = normalize_event(raw, user_email="me@example.com")
        assert isinstance(event, NormalizedEvent)
        assert event.title == "Team Standup"
        assert event.all_day is False
        assert event.start_time is not None
        assert event.end_time is not None
        assert event.duration_minutes == 30
        assert event.status == "confirmed"
        assert len(event.attendees) == 2

    def test_attendee_detail(self):
        raw = _make_timed_event()
        event = normalize_event(raw)
        sarah = next(a for a in event.attendees if a.email == "sarah@example.com")
        assert sarah.name == "Sarah Chen"
        assert sarah.response_status == ResponseStatus.ACCEPTED
        assert sarah.is_self is False

    def test_self_attendee(self):
        raw = _make_timed_event()
        event = normalize_event(raw)
        me = next(a for a in event.attendees if a.is_self)
        assert me.email == "me@example.com"
        assert me.is_self is True


class TestNormalizeAllDayEvent:
    def test_all_day_detection(self):
        raw = _make_all_day_event()
        event = normalize_event(raw)
        assert event.all_day is True
        assert event.date == "2026-04-01"
        assert event.start_time is None
        assert event.end_time is None
        assert event.duration_minutes is None


class TestRecurringDetection:
    def test_recurring_event_tagged(self):
        raw = _make_timed_event(recurringEventId="recur_abc123")
        event = normalize_event(raw)
        assert event.is_recurring is True

    def test_non_recurring_event(self):
        raw = _make_timed_event()
        event = normalize_event(raw)
        assert event.is_recurring is False


class TestExtractMeetingLink:
    def test_from_conference_data_entry_points(self):
        event = {
            "conferenceData": {
                "entryPoints": [
                    {
                        "entryPointType": "video",
                        "uri": "https://meet.google.com/abc-def-ghi",
                    }
                ]
            }
        }
        assert extract_meeting_link(event) == "https://meet.google.com/abc-def-ghi"

    def test_from_hangout_link_fallback(self):
        event = {"hangoutLink": "https://meet.google.com/xyz-uvw"}
        assert extract_meeting_link(event) == "https://meet.google.com/xyz-uvw"

    def test_from_location_url(self):
        event = {"location": "Room 5A - https://zoom.us/j/123456"}
        assert extract_meeting_link(event) == "https://zoom.us/j/123456"

    def test_no_meeting_link(self):
        event = {"location": "Conference Room B"}
        assert extract_meeting_link(event) is None

    def test_conference_data_takes_priority(self):
        event = {
            "conferenceData": {
                "entryPoints": [
                    {
                        "entryPointType": "video",
                        "uri": "https://meet.google.com/priority",
                    }
                ]
            },
            "hangoutLink": "https://meet.google.com/fallback",
        }
        assert extract_meeting_link(event) == "https://meet.google.com/priority"


class TestCategorizeEvents:
    def _make_normalized(self, **kwargs) -> NormalizedEvent:
        defaults = {"id": "e1", "title": "Test"}
        defaults.update(kwargs)
        return NormalizedEvent(**defaults)

    def test_separates_cancelled(self):
        events = [
            self._make_normalized(id="e1", title="Active", status="confirmed"),
            self._make_normalized(id="e2", title="Cancelled", status="cancelled"),
        ]
        result = categorize_events(events)
        assert len(result["cancelled_events"]) == 1
        assert result["cancelled_events"][0].title == "Cancelled"
        assert len(result["timed_events"]) == 1

    def test_separates_declined(self):
        from src.models.events import Attendee

        events = [
            self._make_normalized(
                id="e1",
                title="Declined Meeting",
                attendees=[
                    Attendee(
                        email="me@example.com",
                        response_status=ResponseStatus.DECLINED,
                        is_self=True,
                    )
                ],
            ),
        ]
        result = categorize_events(events, user_email="me@example.com")
        assert len(result["declined_events"]) == 1
        assert len(result["timed_events"]) == 0

    def test_separates_all_day(self):
        events = [
            self._make_normalized(id="e1", title="Holiday", all_day=True),
            self._make_normalized(
                id="e2",
                title="Meeting",
                start_time=datetime(2026, 4, 1, 9, 0, tzinfo=timezone.utc),
            ),
        ]
        result = categorize_events(events)
        assert len(result["all_day_events"]) == 1
        assert len(result["timed_events"]) == 1

    def test_timed_events_sorted_by_start_time(self):
        events = [
            self._make_normalized(
                id="e2",
                title="Afternoon",
                start_time=datetime(2026, 4, 1, 14, 0, tzinfo=timezone.utc),
            ),
            self._make_normalized(
                id="e1",
                title="Morning",
                start_time=datetime(2026, 4, 1, 9, 0, tzinfo=timezone.utc),
            ),
        ]
        result = categorize_events(events)
        assert result["timed_events"][0].title == "Morning"
        assert result["timed_events"][1].title == "Afternoon"


class TestApplyExclusionPatterns:
    def _make_event(self, title: str) -> NormalizedEvent:
        return NormalizedEvent(id="e1", title=title)

    def test_filters_matching_titles(self):
        events = [
            self._make_event("Daily Standup"),
            self._make_event("Q3 Planning"),
            self._make_event("Weekly Standup Review"),
        ]
        result = apply_exclusion_patterns(events, ["standup"])
        assert len(result) == 1
        assert result[0].title == "Q3 Planning"

    def test_case_insensitive(self):
        events = [self._make_event("LUNCH BLOCK")]
        result = apply_exclusion_patterns(events, ["lunch"])
        assert len(result) == 0

    def test_empty_patterns_returns_all(self):
        events = [
            self._make_event("Meeting A"),
            self._make_event("Meeting B"),
        ]
        result = apply_exclusion_patterns(events, [])
        assert len(result) == 2
