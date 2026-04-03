"""Main validation entry point with retry logic.

Authenticates with Google, fetches today's calendar events,
writes timestamped output, logs the result, and sends Slack notifications.
This is a single-shot script -- Cowork handles scheduling.
"""

import json
import sys
import time
import traceback
import zoneinfo
from datetime import datetime, timedelta, timezone
from pathlib import Path

from googleapiclient.discovery import build

from src.auth.google_oauth import load_credentials
from src.notifications.slack import notify_slack
from src.validation.run_log import append_to_log, count_passes

RETRY_DELAY_SECONDS = 15 * 60  # 15 minutes

EASTERN = zoneinfo.ZoneInfo("America/New_York")
OUTPUT_DIR = Path("output/validation")


def fetch_todays_events(creds) -> list[dict]:
    """Fetch today's calendar events in US/Eastern timezone.

    Returns a list of dicts with title, start, end, attendees, and
    duration_minutes for each event.
    """
    now = datetime.now(EASTERN)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)

    service = build("calendar", "v3", credentials=creds)
    events_result = service.events().list(
        calendarId="primary",
        timeMin=start_of_day.isoformat(),
        timeMax=end_of_day.isoformat(),
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    raw_events = events_result.get("items", [])
    events = []
    for e in raw_events:
        start_str = e.get("start", {}).get("dateTime", "")
        end_str = e.get("end", {}).get("dateTime", "")

        # Calculate duration if both start and end are present
        duration_minutes = None
        if start_str and end_str:
            try:
                from dateutil.parser import isoparse

                start_dt = isoparse(start_str)
                end_dt = isoparse(end_str)
                duration_minutes = int((end_dt - start_dt).total_seconds() / 60)
            except (ValueError, TypeError):
                pass

        events.append({
            "title": e.get("summary", "No title"),
            "start": start_str,
            "end": end_str,
            "attendees": [
                a.get("email", "") for a in e.get("attendees", [])
            ],
            "duration_minutes": duration_minutes,
        })

    return events


def run_validation() -> dict:
    """Single validation attempt: auth + Calendar API call.

    Raises RuntimeError if credentials are unavailable (triggers Slack
    notification for re-auth in the caller).
    """
    creds = load_credentials()
    if creds is None:
        raise RuntimeError(
            "OAuth credentials unavailable or refresh failed. "
            "Run: uv run python -m src.auth.google_oauth to re-authenticate."
        )

    events = fetch_todays_events(creds)
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "pass",
        "event_count": len(events),
        "events": events,
    }


def write_output(result: dict) -> Path:
    """Write validation result to a timestamped JSON file.

    Filename format: YYYY-MM-DD_HH-MM.json (UTC timestamp).
    Returns the path to the written file.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    now_utc = datetime.now(timezone.utc)
    filename = now_utc.strftime("%Y-%m-%d_%H-%M") + ".json"
    output_path = OUTPUT_DIR / filename
    output_path.write_text(json.dumps(result, indent=2))
    return output_path


def main():
    """Entry point with retry logic.

    On first failure: log error, notify Slack, wait 15 min, retry once.
    On second failure: log error, notify Slack, exit.
    On success: write output, append to log, notify Slack with event count.
    """
    try:
        result = run_validation()
    except Exception as first_error:
        error_detail = (
            f"Validation FAILED (attempt 1/2): {type(first_error).__name__}: "
            f"{first_error}\nRetrying in 15 minutes..."
        )
        print(error_detail, file=sys.stderr)
        notify_slack(error_detail)
        append_to_log({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "fail",
            "attempt": 1,
            "error": str(first_error),
        })

        time.sleep(RETRY_DELAY_SECONDS)

        try:
            result = run_validation()
        except Exception as second_error:
            error_detail = (
                f"Validation FAILED (attempt 2/2, giving up): "
                f"{type(second_error).__name__}: {second_error}\n"
                f"Manual intervention needed. Check credentials and API access."
            )
            print(error_detail, file=sys.stderr)
            notify_slack(error_detail)
            append_to_log({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "fail",
                "attempt": 2,
                "error": str(second_error),
            })
            return

    # Success path
    output_path = write_output(result)
    append_to_log(result)
    pass_count = count_passes()
    success_msg = (
        f"Validation PASSED: {result['event_count']} calendar events found. "
        f"Output: {output_path.name} | Total passes: {pass_count}/5"
    )
    print(success_msg)
    notify_slack(success_msg)


if __name__ == "__main__":
    main()
