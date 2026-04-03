from __future__ import annotations

import argparse
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from src.config import load_config
from src.models.events import DailySynthesis, Section
from src.output.writer import write_daily_summary

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Daily intelligence pipeline: summarize calendar, email, and meeting data.",
    )
    parser.add_argument(
        "--from",
        dest="from_date",
        type=date.fromisoformat,
        default=date.today(),
        help="Start date (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--to",
        dest="to_date",
        type=date.fromisoformat,
        default=None,
        help="End date (YYYY-MM-DD). Defaults to --from date.",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config/config.yaml",
        help="Path to config YAML file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(Path(args.config))

    from_date = args.from_date
    to_date = args.to_date or from_date

    output_dir = Path(config.get("pipeline", {}).get("output_dir", "output"))
    template_dir = Path("templates")

    # Try to load OAuth credentials for calendar + gmail ingestion
    calendar_service = None
    gmail_service = None
    user_email = None
    try:
        from google.auth.transport.requests import Request

        from src.auth.google_oauth import load_credentials, save_credentials
        from src.ingest.calendar import build_calendar_service, cache_raw_response, fetch_events_for_date
        from src.ingest.gmail import build_gmail_service, cache_raw_emails
        from src.ingest.normalizer import build_normalized_output
        from src.ingest.transcripts import fetch_all_transcripts

        creds = load_credentials()
        if creds is None:
            logger.warning(
                "No valid credentials found. Run `python -m src.auth.google_oauth` to authenticate. "
                "Producing empty summary."
            )
        else:
            # Refresh if expired
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                save_credentials(creds)

            calendar_service = build_calendar_service(creds)
            gmail_service = build_gmail_service(creds)

            # Get user email for attendee matching (declined detection)
            try:
                primary_cal = calendar_service.calendarList().get(calendarId="primary").execute()
                user_email = primary_cal.get("id")
                logger.info("Authenticated as: %s", user_email)
            except Exception as e:
                logger.warning("Could not fetch user email: %s", e)

    except Exception as e:
        logger.warning("Calendar ingestion unavailable: %s. Producing empty summaries.", e)

    current = from_date
    while current <= to_date:
        try:
            if calendar_service is not None:
                # Full pipeline: fetch real calendar data
                categorized, raw_events = fetch_events_for_date(
                    calendar_service, current, config, user_email
                )

                # Cache raw calendar response
                cache_raw_response(raw_events, current, output_dir)

                # Fetch and link transcripts
                transcripts: list[dict] = []
                unmatched: list[dict] = []
                try:
                    if gmail_service is not None:
                        transcripts = fetch_all_transcripts(gmail_service, current, config)

                        if transcripts:
                            # Cache raw transcript emails
                            raw_emails = [t["raw_email"] for t in transcripts]
                            cache_raw_emails(raw_emails, "transcripts", current, output_dir)

                        # Normalize: match transcripts to events, deduplicate
                        categorized, unmatched = build_normalized_output(
                            categorized, transcripts, config
                        )
                except Exception as e:
                    logger.warning("Transcript ingestion failed: %s. Continuing with calendar only.", e)
                    transcripts = []
                    unmatched = []

                # Compute stats
                active_events = categorized["timed_events"] + categorized["all_day_events"]
                meeting_count = len(active_events)
                total_meeting_hours = sum(
                    (e.duration_minutes or 0) for e in categorized["timed_events"]
                ) / 60.0

                # Count events that have transcripts attached
                transcript_count = sum(
                    1 for e in active_events if e.transcript_text is not None
                )

                # --- Stage 1: Per-meeting extraction ---
                extractions: list = []
                try:
                    from src.synthesis.extractor import extract_all_meetings

                    events_with_transcripts = [e for e in active_events if e.transcript_text]
                    if events_with_transcripts:
                        extractions = extract_all_meetings(events_with_transcripts, config)
                        logger.info("Extracted %d meetings", len(extractions))
                except Exception as e:
                    logger.warning("Extraction failed: %s. Continuing without synthesis.", e)

                # --- Stage 2: Daily synthesis ---
                synthesis_result: dict = {
                    "substance": [],
                    "decisions": [],
                    "commitments": [],
                    "executive_summary": None,
                }
                try:
                    from src.synthesis.synthesizer import synthesize_daily

                    if extractions:
                        synthesis_result = synthesize_daily(extractions, current, config)
                        logger.info("Daily synthesis complete")
                except Exception as e:
                    logger.warning("Synthesis failed: %s. Continuing with empty synthesis.", e)

                # --- Build meetings without transcripts list ---
                meetings_without_transcripts = [
                    e for e in active_events if e.transcript_text is None
                ]

                synthesis = DailySynthesis(
                    date=current,
                    generated_at=datetime.now(timezone.utc),
                    meeting_count=meeting_count,
                    total_meeting_hours=total_meeting_hours,
                    transcript_count=transcript_count,
                    all_day_events=categorized["all_day_events"],
                    timed_events=categorized["timed_events"],
                    declined_events=categorized["declined_events"],
                    cancelled_events=categorized["cancelled_events"],
                    unmatched_transcripts=unmatched,
                    executive_summary=synthesis_result.get("executive_summary"),
                    extractions=extractions,
                    meetings_without_transcripts=meetings_without_transcripts,
                    substance=Section(
                        title="Substance",
                        items=synthesis_result.get("substance", []),
                    ),
                    decisions=Section(
                        title="Decisions",
                        items=synthesis_result.get("decisions", []),
                    ),
                    commitments=Section(
                        title="Commitments",
                        items=synthesis_result.get("commitments", []),
                    ),
                )
            else:
                # No credentials: produce empty summary
                synthesis = DailySynthesis(
                    date=current,
                    generated_at=datetime.now(timezone.utc),
                    meeting_count=0,
                    total_meeting_hours=0.0,
                    transcript_count=0,
                    substance=Section(title="Substance"),
                    decisions=Section(title="Decisions"),
                    commitments=Section(title="Commitments"),
                )

            path = write_daily_summary(synthesis, output_dir, template_dir)
            logger.info(
                "Wrote daily summary for %s -> %s (%d meetings, %.1fh)",
                current,
                path,
                synthesis.meeting_count,
                synthesis.total_meeting_hours,
            )

        except Exception as e:
            logger.error("Failed to process %s: %s", current, e)

        current += timedelta(days=1)


if __name__ == "__main__":
    main()
