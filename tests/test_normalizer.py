"""Tests for normalization pipeline: matching, deduplication, integration."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from src.ingest.normalizer import (
    build_normalized_output,
    deduplicate_events,
    match_transcript_to_event,
    match_transcripts_to_events,
)
from src.models.events import NormalizedEvent

TZ = ZoneInfo("America/New_York")


def _make_event(
    title: str = "Weekly Sync",
    start_hour: int = 10,
    start_minute: int = 0,
    event_id: str = "evt1",
    all_day: bool = False,
    transcript_text: str | None = None,
    transcript_source: str | None = None,
    attendees: list | None = None,
    description: str | None = None,
) -> NormalizedEvent:
    """Create a mock NormalizedEvent for testing."""
    return NormalizedEvent(
        id=event_id,
        title=title,
        start_time=datetime(2026, 4, 3, start_hour, start_minute, tzinfo=TZ) if not all_day else None,
        end_time=datetime(2026, 4, 3, start_hour + 1, start_minute, tzinfo=TZ) if not all_day else None,
        all_day=all_day,
        date="2026-04-03" if all_day else None,
        duration_minutes=60 if not all_day else None,
        transcript_text=transcript_text,
        transcript_source=transcript_source,
        attendees=attendees or [],
        description=description,
    )


def _make_transcript(
    title: str = "Weekly Sync",
    hour: int = 10,
    minute: int = 15,
    source: str = "gemini",
    text: str = "Discussed project timeline.",
) -> dict:
    """Create a mock transcript dict for testing."""
    return {
        "source": source,
        "title": title,
        "meeting_time": datetime(2026, 4, 3, hour, minute, tzinfo=TZ),
        "transcript_text": text,
        "raw_email": {"id": f"msg_{source}_{title.replace(' ', '_')}"},
        "message_id": f"msg_{source}_{title.replace(' ', '_')}",
    }


# --- match_transcript_to_event tests ---


def test_match_transcript_to_event_exact_title():
    """Transcript title matches event title exactly, within time window."""
    event = _make_event(title="Weekly Sync", start_hour=10)
    transcript = _make_transcript(title="Weekly Sync", hour=10, minute=15)

    result = match_transcript_to_event(transcript, [event], time_window_minutes=30)
    assert result is not None
    assert result.id == "evt1"


def test_match_transcript_to_event_fuzzy_title():
    """Transcript title similar but not exact — should still match."""
    event = _make_event(title="Weekly Sync", start_hour=10)
    transcript = _make_transcript(title="Weekly Sync Meeting", hour=10, minute=10)

    result = match_transcript_to_event(transcript, [event], time_window_minutes=30)
    assert result is not None
    assert result.id == "evt1"


def test_match_transcript_to_event_outside_window():
    """Transcript time far from event — should NOT match."""
    event = _make_event(title="Weekly Sync", start_hour=10)
    transcript = _make_transcript(title="Weekly Sync", hour=14, minute=0)

    result = match_transcript_to_event(transcript, [event], time_window_minutes=30)
    assert result is None


def test_match_transcript_to_event_no_candidates():
    """No events at all — returns None."""
    transcript = _make_transcript(title="Weekly Sync", hour=10)

    result = match_transcript_to_event(transcript, [], time_window_minutes=30)
    assert result is None


# --- match_transcripts_to_events tests ---


def test_match_transcripts_gemini_priority():
    """When both Gemini and Gong match same event, Gemini should win."""
    event = _make_event(title="Product Review", start_hour=14)
    gemini_t = _make_transcript(
        title="Product Review", hour=14, minute=5, source="gemini", text="Gemini version"
    )
    gong_t = _make_transcript(
        title="Product Review", hour=14, minute=3, source="gong", text="Gong version"
    )

    config = {
        "transcripts": {"matching": {"time_window_minutes": 30}},
        "pipeline": {"timezone": "America/New_York"},
    }

    events, unmatched = match_transcripts_to_events(
        [gemini_t, gong_t], [event], config
    )

    assert event.transcript_source == "gemini"
    assert event.transcript_text == "Gemini version"
    assert len(unmatched) == 1
    assert unmatched[0]["source"] == "gong"


# --- deduplicate_events tests ---


def test_deduplicate_events_removes_duplicates():
    """Two events with same title and start_time — merge to one."""
    evt1 = _make_event(title="Team Standup", start_hour=9, event_id="evt_cal1")
    evt2 = _make_event(title="Team Standup", start_hour=9, event_id="evt_cal2")

    result = deduplicate_events([evt1, evt2])
    assert len(result) == 1


def test_deduplicate_events_keeps_transcript():
    """Duplicate events where one has transcript — keep the transcript one."""
    evt_no_transcript = _make_event(
        title="Design Review", start_hour=11, event_id="evt_a"
    )
    evt_with_transcript = _make_event(
        title="Design Review",
        start_hour=11,
        event_id="evt_b",
        transcript_text="We reviewed the mockups.",
        transcript_source="gemini",
    )

    result = deduplicate_events([evt_no_transcript, evt_with_transcript])
    assert len(result) == 1
    assert result[0].transcript_text == "We reviewed the mockups."


# --- Unmatched transcript tests ---


def test_unmatched_transcripts_surfaced():
    """Transcript with no matching event appears in unmatched list."""
    event = _make_event(title="Weekly Sync", start_hour=10)
    orphan = _make_transcript(title="Random Call", hour=20, minute=0)

    config = {
        "transcripts": {"matching": {"time_window_minutes": 30}},
        "pipeline": {"timezone": "America/New_York"},
    }

    events, unmatched = match_transcripts_to_events([orphan], [event], config)
    assert len(unmatched) == 1
    assert unmatched[0]["title"] == "Random Call"


# --- build_normalized_output integration test ---


def test_build_normalized_output_integration():
    """Full integration: match, dedup, re-categorize."""
    events_categorized = {
        "timed_events": [
            _make_event(title="Morning Standup", start_hour=9, event_id="e1"),
            _make_event(title="Design Review", start_hour=14, event_id="e2"),
        ],
        "all_day_events": [],
        "declined_events": [],
        "cancelled_events": [],
    }

    transcripts = [
        _make_transcript(
            title="Morning Standup", hour=9, minute=5, source="gemini", text="Standup notes"
        ),
        _make_transcript(
            title="Orphan Call", hour=20, minute=0, source="gong", text="Random call notes"
        ),
    ]

    config = {
        "transcripts": {"matching": {"time_window_minutes": 30}},
        "pipeline": {"timezone": "America/New_York"},
    }

    updated, unmatched = build_normalized_output(events_categorized, transcripts, config)

    # Standup should have transcript attached
    standup = next(e for e in updated["timed_events"] if e.title == "Morning Standup")
    assert standup.transcript_text == "Standup notes"
    assert standup.transcript_source == "gemini"

    # Design Review should have no transcript
    design = next(e for e in updated["timed_events"] if e.title == "Design Review")
    assert design.transcript_text is None

    # Orphan call should be in unmatched
    assert len(unmatched) == 1
    assert unmatched[0]["title"] == "Orphan Call"
