"""Normalization pipeline: transcript-calendar linking, deduplication, merge."""

from __future__ import annotations

import logging
from datetime import datetime
from difflib import SequenceMatcher
from zoneinfo import ZoneInfo

from src.models.events import NormalizedEvent

logger = logging.getLogger(__name__)


def _make_aware(dt: datetime, timezone: str = "America/New_York") -> datetime:
    """Ensure a datetime is timezone-aware.

    If naive, assumes the configured timezone. If already aware, returns as-is.

    Args:
        dt: Datetime to make aware.
        timezone: IANA timezone string for naive datetimes.

    Returns:
        Timezone-aware datetime.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=ZoneInfo(timezone))
    return dt


def match_transcript_to_event(
    transcript: dict,
    events: list[NormalizedEvent],
    time_window_minutes: int = 30,
    timezone: str = "America/New_York",
) -> NormalizedEvent | None:
    """Find the best matching calendar event for a transcript.

    Matches by time proximity (within window) and title similarity.
    Returns the single best match or None.

    Args:
        transcript: Transcript dict with 'meeting_time' and 'title'.
        events: List of NormalizedEvent candidates.
        time_window_minutes: Maximum minutes between transcript and event times.
        timezone: Timezone for normalizing naive datetimes.

    Returns:
        Best matching NormalizedEvent, or None if no match within window.
    """
    transcript_time = transcript.get("meeting_time")
    transcript_title = transcript.get("title", "")

    if transcript_time is None:
        logger.debug("Transcript '%s' has no meeting_time, cannot match", transcript_title)
        return None

    transcript_time = _make_aware(transcript_time, timezone)
    candidates: list[tuple[NormalizedEvent, float, float]] = []

    for event in events:
        if event.start_time is None:
            continue

        event_time = _make_aware(event.start_time, timezone)
        time_diff = abs((transcript_time - event_time).total_seconds() / 60)

        if time_diff <= time_window_minutes:
            title_score = SequenceMatcher(
                None, transcript_title.lower(), event.title.lower()
            ).ratio()
            candidates.append((event, title_score, time_diff))

    if not candidates:
        return None

    # Sort by title similarity (desc), then time proximity (asc)
    candidates.sort(key=lambda x: (-x[1], x[2]))
    return candidates[0][0]


def match_transcripts_to_events(
    transcripts: list[dict],
    events: list[NormalizedEvent],
    config: dict,
) -> tuple[list[NormalizedEvent], list[dict]]:
    """Batch-match transcripts to calendar events.

    When both Gemini and Gong match the same event, Gemini wins (per user decision).

    Args:
        transcripts: List of transcript dicts from fetch_all_transcripts.
        events: List of NormalizedEvent from calendar ingestion.
        config: Pipeline configuration with transcripts.matching settings.

    Returns:
        Tuple of (updated_events, unmatched_transcripts).
    """
    matching_config = config.get("transcripts", {}).get("matching", {})
    time_window = matching_config.get("time_window_minutes", 30)
    timezone = config.get("pipeline", {}).get("timezone", "America/New_York")

    unmatched: list[dict] = []
    matched_count = 0

    # Sort transcripts: Gemini first so it gets priority in case of conflicts
    sorted_transcripts = sorted(
        transcripts,
        key=lambda t: 0 if t.get("source") == "gemini" else 1,
    )

    for transcript in sorted_transcripts:
        match = match_transcript_to_event(transcript, events, time_window, timezone)

        if match is None:
            unmatched.append(transcript)
            continue

        # Check source priority: Gemini wins over Gong
        existing_source = match.transcript_source
        new_source = transcript.get("source", "")

        if existing_source == "gemini" and new_source == "gong":
            # Gemini already attached — Gong loses, becomes unmatched
            logger.debug(
                "Skipping Gong transcript for '%s' — Gemini already attached",
                match.title,
            )
            unmatched.append(transcript)
            continue

        # Attach transcript to event
        match.transcript_text = transcript.get("transcript_text")
        match.transcript_source = new_source
        matched_count += 1

    logger.info(
        "Matched %d/%d transcripts to calendar events. %d unmatched.",
        matched_count,
        len(transcripts),
        len(unmatched),
    )
    return events, unmatched


def deduplicate_events(events: list[NormalizedEvent]) -> list[NormalizedEvent]:
    """Remove duplicate calendar events from overlapping sources.

    Groups by (title + start_time) for timed events or (title + date) for
    all-day events. Keeps the event with the most data (has transcript >
    no transcript, has attendees > no attendees).

    Args:
        events: List of NormalizedEvent, potentially with duplicates.

    Returns:
        Deduplicated list of events.
    """
    seen: dict[str, NormalizedEvent] = {}
    original_count = len(events)

    for event in events:
        # Build dedup key
        title_key = event.title.lower().strip()
        if event.all_day:
            dedup_key = f"{title_key}|allday|{event.date}"
        elif event.start_time:
            dedup_key = f"{title_key}|{event.start_time.isoformat()}"
        else:
            # No time info — use ID as unique key (can't dedup)
            dedup_key = f"noid|{event.id}"

        if dedup_key not in seen:
            seen[dedup_key] = event
        else:
            existing = seen[dedup_key]
            # Keep the one with more data
            new_score = _data_richness_score(event)
            existing_score = _data_richness_score(existing)
            if new_score > existing_score:
                seen[dedup_key] = event

    deduped = list(seen.values())
    if original_count != len(deduped):
        logger.info(
            "Deduplicated %d events down to %d",
            original_count,
            len(deduped),
        )
    return deduped


def _data_richness_score(event: NormalizedEvent) -> int:
    """Score an event by how much data it contains.

    Higher score = more data. Used for deduplication preference.
    """
    score = 0
    if event.transcript_text:
        score += 10
    if event.attendees:
        score += 5
    if event.description:
        score += 2
    if event.meeting_link:
        score += 1
    return score


def build_normalized_output(
    categorized: dict,
    transcripts: list[dict],
    config: dict,
) -> tuple[dict, list[dict]]:
    """Top-level normalization: match transcripts, deduplicate, re-categorize.

    Args:
        categorized: Dict from calendar categorize_events (all_day_events,
            timed_events, declined_events, cancelled_events).
        transcripts: List of transcript dicts from fetch_all_transcripts.
        config: Pipeline configuration dict.

    Returns:
        Tuple of (updated_categorized_dict, unmatched_transcripts).
    """
    # Combine timed + all_day for matching (transcripts can match either)
    all_events = categorized.get("timed_events", []) + categorized.get("all_day_events", [])

    # Match transcripts to events
    matched_events, unmatched = match_transcripts_to_events(
        transcripts, all_events, config
    )

    # Deduplicate
    deduped = deduplicate_events(matched_events)

    # Re-categorize into timed/all_day
    timed = [e for e in deduped if not e.all_day]
    all_day = [e for e in deduped if e.all_day]

    # Sort timed events by start_time
    timed.sort(key=lambda e: e.start_time or datetime.min)

    categorized["timed_events"] = timed
    categorized["all_day_events"] = all_day

    return categorized, unmatched
