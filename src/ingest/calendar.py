"""Google Calendar ingestion: fetch, normalize, categorize events."""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dateutil.parser import isoparse
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from src.config import PipelineConfig
from src.models.events import Attendee, NormalizedEvent, ResponseStatus
from src.retry import retry_api_call

logger = logging.getLogger(__name__)


def build_calendar_service(creds: Credentials):
    """Create a Google Calendar API v3 service instance."""
    return build("calendar", "v3", credentials=creds)


@retry_api_call
def _execute_with_retry(request):
    """Execute a Google API request with retry on transient errors."""
    return request.execute()


def fetch_raw_events(
    service,
    target_date: date,
    calendar_ids: list[str],
    timezone: str = "America/New_York",
) -> list[dict]:
    """Fetch all events for a given date across configured calendar IDs.

    Args:
        service: Google Calendar API service instance.
        target_date: The date to fetch events for.
        calendar_ids: List of calendar IDs to query.
        timezone: IANA timezone for day boundaries.

    Returns:
        Combined list of raw event dicts, each tagged with _calendar_id.
    """
    tz = ZoneInfo(timezone)
    start_of_day = datetime(
        target_date.year, target_date.month, target_date.day, tzinfo=tz
    )
    end_of_day = start_of_day + timedelta(days=1)

    all_events: list[dict] = []

    for cal_id in calendar_ids:
        page_token = None
        while True:
            request = service.events().list(
                calendarId=cal_id,
                timeMin=start_of_day.isoformat(),
                timeMax=end_of_day.isoformat(),
                singleEvents=True,
                orderBy="startTime",
                showDeleted=True,
                pageToken=page_token,
            )
            response = _execute_with_retry(request)

            for event in response.get("items", []):
                event["_calendar_id"] = cal_id
                all_events.append(event)

            page_token = response.get("nextPageToken")
            if not page_token:
                break

    return all_events


def extract_meeting_link(event: dict) -> str | None:
    """Extract meeting link from event data.

    Checks in order: conferenceData entryPoints (video), hangoutLink, location URL.
    """
    # 1. Conference data entry points
    conference_data = event.get("conferenceData", {})
    for entry_point in conference_data.get("entryPoints", []):
        if entry_point.get("entryPointType") == "video":
            return entry_point.get("uri")

    # 2. Hangout link
    hangout_link = event.get("hangoutLink")
    if hangout_link:
        return hangout_link

    # 3. URL pattern in location
    location = event.get("location", "") or ""
    url_match = re.search(r"https?://\S+", location)
    if url_match:
        return url_match.group(0)

    return None


def normalize_event(
    event: dict, user_email: str | None = None
) -> NormalizedEvent:
    """Convert a raw Google Calendar API event dict to a NormalizedEvent.

    Args:
        event: Raw event dict from the Calendar API.
        user_email: The authenticated user's email, used for attendee matching.

    Returns:
        A NormalizedEvent instance.
    """
    start = event.get("start", {})
    end = event.get("end", {})

    # Detect all-day vs timed
    is_all_day = "date" in start and "dateTime" not in start

    start_time = None
    end_time = None
    duration_minutes = None
    event_date = None

    if is_all_day:
        event_date = start.get("date")
    else:
        start_dt_str = start.get("dateTime")
        end_dt_str = end.get("dateTime")
        if start_dt_str:
            start_time = isoparse(start_dt_str)
        if end_dt_str:
            end_time = isoparse(end_dt_str)
        if start_time and end_time:
            duration_minutes = int((end_time - start_time).total_seconds() / 60)

    # Build attendee list
    attendees: list[Attendee] = []
    for att in event.get("attendees", []):
        response_str = att.get("responseStatus", "needsAction")
        try:
            response_status = ResponseStatus(response_str)
        except ValueError:
            response_status = ResponseStatus.NEEDS_ACTION

        attendees.append(
            Attendee(
                name=att.get("displayName"),
                email=att.get("email", ""),
                response_status=response_status,
                is_self=att.get("self", False),
                is_organizer=att.get("organizer", False),
            )
        )

    # Detect recurring
    is_recurring = "recurringEventId" in event

    # Extract meeting link
    meeting_link = extract_meeting_link(event)

    # Truncate description to 500 chars
    description = event.get("description")
    if description and len(description) > 500:
        description = description[:500]

    return NormalizedEvent(
        id=event.get("id", ""),
        title=event.get("summary", "(No title)"),
        start_time=start_time,
        end_time=end_time,
        all_day=is_all_day,
        date=event_date,
        duration_minutes=duration_minutes,
        attendees=attendees,
        description=description,
        location=event.get("location"),
        meeting_link=meeting_link,
        is_recurring=is_recurring,
        event_type=event.get("eventType", "default"),
        status=event.get("status", "confirmed"),
        calendar_id=event.get("_calendar_id", "primary"),
        raw_data=event,
    )


def categorize_events(
    events: list[NormalizedEvent], user_email: str | None = None
) -> dict:
    """Categorize normalized events into all-day, timed, declined, cancelled.

    Args:
        events: List of normalized events.
        user_email: User's email for declined detection.

    Returns:
        Dict with keys: all_day_events, timed_events, declined_events, cancelled_events.
    """
    all_day_events: list[NormalizedEvent] = []
    timed_events: list[NormalizedEvent] = []
    declined_events: list[NormalizedEvent] = []
    cancelled_events: list[NormalizedEvent] = []

    for event in events:
        # Cancelled first
        if event.status == "cancelled":
            cancelled_events.append(event)
            continue

        # Check if user declined
        user_declined = False
        for att in event.attendees:
            if att.is_self or (user_email and att.email == user_email):
                if att.response_status == ResponseStatus.DECLINED:
                    user_declined = True
                    break

        if user_declined:
            declined_events.append(event)
            continue

        # All-day vs timed
        if event.all_day:
            all_day_events.append(event)
        else:
            timed_events.append(event)

    # Sort timed events by start_time
    timed_events.sort(key=lambda e: e.start_time or datetime.min)

    return {
        "all_day_events": all_day_events,
        "timed_events": timed_events,
        "declined_events": declined_events,
        "cancelled_events": cancelled_events,
    }


def apply_exclusion_patterns(
    events: list[NormalizedEvent], patterns: list[str]
) -> list[NormalizedEvent]:
    """Filter out events whose title matches any exclusion pattern.

    Args:
        events: Events to filter.
        patterns: List of case-insensitive substring patterns to exclude.

    Returns:
        Events not matching any pattern.
    """
    if not patterns:
        return events

    return [
        event
        for event in events
        if not any(p.lower() in event.title.lower() for p in patterns)
    ]


def cache_raw_response(
    raw_events: list[dict], target_date: date, output_dir: Path
) -> Path:
    """Write raw API response to JSON cache file.

    Creates: output_dir/raw/YYYY/MM/DD/calendar.json

    Args:
        raw_events: List of raw event dicts from the API.
        target_date: The date these events are for.
        output_dir: Base output directory.

    Returns:
        Path to the written JSON file.
    """
    cache_dir = (
        output_dir
        / "raw"
        / str(target_date.year)
        / f"{target_date.month:02d}"
        / f"{target_date.day:02d}"
    )
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / "calendar.json"

    # Strip raw_data from events before caching (avoid circular nesting)
    cache_path.write_text(
        json.dumps(raw_events, indent=2, default=str), encoding="utf-8"
    )
    return cache_path


def fetch_events_for_date(
    service,
    target_date: date,
    config: PipelineConfig,
    user_email: str | None = None,
) -> tuple[dict, list[dict]]:
    """Orchestrate event fetching, normalization, and categorization for a date.

    Args:
        service: Google Calendar API service instance.
        target_date: The date to process.
        config: Pipeline configuration.
        user_email: User's email for declined detection.

    Returns:
        Tuple of (categorized_dict, raw_events_list).
    """
    calendar_ids = config.calendars.ids
    timezone = config.pipeline.timezone
    exclude_patterns = config.calendars.exclude_patterns

    # Fetch raw events
    raw_events = fetch_raw_events(service, target_date, calendar_ids, timezone)
    logger.info("Fetched %d raw events for %s", len(raw_events), target_date)

    # Normalize all events
    normalized = [normalize_event(event, user_email) for event in raw_events]

    # Apply exclusion patterns
    normalized = apply_exclusion_patterns(normalized, exclude_patterns)

    # Categorize
    categorized = categorize_events(normalized, user_email)

    return categorized, raw_events
