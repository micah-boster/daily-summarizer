from __future__ import annotations

import argparse
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)

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
        description="Work intelligence pipeline: daily summaries, weekly roll-ups, and monthly narratives.",
    )
    subparsers = parser.add_subparsers(dest="command")

    # Daily subcommand (default behavior)
    daily_parser = subparsers.add_parser("daily", help="Generate daily summaries")
    daily_parser.add_argument(
        "--from",
        dest="from_date",
        type=date.fromisoformat,
        default=date.today(),
        help="Start date (YYYY-MM-DD). Defaults to today.",
    )
    daily_parser.add_argument(
        "--to",
        dest="to_date",
        type=date.fromisoformat,
        default=None,
        help="End date (YYYY-MM-DD). Defaults to --from date.",
    )
    daily_parser.add_argument(
        "--config",
        type=str,
        default="config/config.yaml",
        help="Path to config YAML file.",
    )

    # Weekly subcommand
    weekly_parser = subparsers.add_parser("weekly", help="Generate weekly roll-up summary")
    weekly_parser.add_argument(
        "--date",
        dest="target_date",
        type=date.fromisoformat,
        default=date.today(),
        help="Any date within the target week (YYYY-MM-DD). Defaults to today.",
    )
    weekly_parser.add_argument(
        "--config",
        type=str,
        default="config/config.yaml",
        help="Path to config YAML file.",
    )

    # Monthly subcommand
    monthly_parser = subparsers.add_parser("monthly", help="Generate monthly narrative summary")
    monthly_parser.add_argument(
        "--date",
        dest="target_month",
        type=str,
        default=None,
        help="Target month (YYYY-MM). Defaults to previous month.",
    )
    monthly_parser.add_argument(
        "--config",
        type=str,
        default="config/config.yaml",
        help="Path to config YAML file.",
    )

    # Discover-slack subcommand
    discover_parser = subparsers.add_parser(
        "discover-slack", help="Discover and configure Slack channels/DMs for ingestion"
    )
    discover_parser.add_argument(
        "--config",
        type=str,
        default="config/config.yaml",
        help="Path to config YAML file.",
    )

    # For backward compatibility: add --from and --to at top level
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


def run_daily(args: argparse.Namespace) -> None:
    """Run the daily summary pipeline."""
    config = load_config(Path(args.config))

    from_date = args.from_date
    to_date = args.to_date or from_date

    output_dir = Path(config.get("pipeline", {}).get("output_dir", "output"))
    template_dir = Path("templates")

    # Try to load OAuth credentials for calendar + gmail ingestion
    calendar_service = None
    gmail_service = None
    user_email = None
    creds = None
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
        # --- Slack ingestion (independent of Google auth) ---
        slack_items: list = []
        try:
            slack_config = config.get("slack", {})
            if slack_config.get("enabled", False):
                from src.ingest.slack import (
                    build_slack_client,
                    fetch_slack_items,
                    load_slack_state,
                    save_slack_state,
                )

                slack_items = fetch_slack_items(config, target_date=current)
                logger.info("Fetched %d Slack items", len(slack_items))

                # --- Periodic new-channel auto-suggest ---
                try:
                    from src.ingest.slack_discovery import check_new_channels

                    state = load_slack_state(Path("config"))
                    last_check = state.get("last_discovery_check")
                    check_interval = slack_config.get("discovery_check_days", 7)
                    should_check = (
                        last_check is None
                        or datetime.fromisoformat(last_check)
                        < datetime.now() - timedelta(days=check_interval)
                    )
                    if should_check:
                        client = build_slack_client()
                        new_channels = check_new_channels(client, state, config)
                        if new_channels:
                            logger.info(
                                "New active Slack channels detected: %s — run discover-slack to add them.",
                                ", ".join(f"#{name}" for name in new_channels),
                            )
                        state["last_discovery_check"] = datetime.now().isoformat()
                        save_slack_state(state, Path("config"))
                except Exception as e:
                    logger.debug("Periodic channel check skipped: %s", e)
        except Exception as e:
            logger.warning(
                "Slack ingestion failed: %s. Continuing without Slack data.", e
            )

        # --- Google Docs ingestion (uses same Google OAuth creds) ---
        docs_items: list = []
        try:
            docs_config = config.get("google_docs", {})
            if docs_config.get("enabled", False) and creds is not None:
                from src.ingest.google_docs import fetch_google_docs_items

                docs_items = fetch_google_docs_items(config, creds, current)
                logger.info("Fetched %d Google Docs items", len(docs_items))
        except Exception as e:
            logger.warning(
                "Google Docs ingestion failed: %s. Continuing without Docs data.", e
            )

        # --- HubSpot CRM ingestion (independent of Google auth) ---
        hubspot_items: list = []
        try:
            hubspot_config = config.get("hubspot", {})
            if hubspot_config.get("enabled", False):
                from src.ingest.hubspot import fetch_hubspot_items

                hubspot_items = fetch_hubspot_items(config, current)
                logger.info("Fetched %d HubSpot items", len(hubspot_items))
        except Exception as e:
            logger.warning(
                "HubSpot ingestion failed: %s. Continuing without HubSpot data.", e
            )

        # Initialize synthesis_result before the calendar branch so it's always
        # defined for commitment extraction, even in the no-creds path.
        synthesis_result: dict = {
            "substance": [],
            "decisions": [],
            "commitments": [],
            "executive_summary": None,
        }
        extractions: list = []

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
                        transcripts = fetch_all_transcripts(gmail_service, current, config, creds=creds)

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
                try:
                    from src.synthesis.extractor import extract_all_meetings

                    events_with_transcripts = [e for e in active_events if e.transcript_text]
                    if events_with_transcripts:
                        extractions = extract_all_meetings(events_with_transcripts, config)
                        logger.info("Extracted %d meetings", len(extractions))
                except Exception as e:
                    logger.warning("Extraction failed: %s. Continuing without synthesis.", e)

                # --- Stage 2: Daily synthesis ---
                try:
                    from src.synthesis.synthesizer import synthesize_daily

                    if extractions or slack_items or docs_items or hubspot_items:
                        synthesis_result = synthesize_daily(
                            extractions, current, config,
                            slack_items=slack_items, docs_items=docs_items,
                            hubspot_items=hubspot_items,
                        )
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
                # No Google credentials: still synthesize Slack/HubSpot/Docs data if available
                if slack_items or docs_items or hubspot_items:
                    try:
                        from src.synthesis.synthesizer import synthesize_daily

                        synthesis_result = synthesize_daily(
                            [], current, config,
                            slack_items=slack_items, docs_items=docs_items,
                            hubspot_items=hubspot_items,
                        )
                        logger.info("Daily synthesis complete (no-creds path)")
                    except Exception as e:
                        logger.warning("Synthesis failed (no-creds path): %s", e)

                synthesis = DailySynthesis(
                    date=current,
                    generated_at=datetime.now(timezone.utc),
                    meeting_count=0,
                    total_meeting_hours=0.0,
                    transcript_count=0,
                    executive_summary=synthesis_result.get("executive_summary"),
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

            # --- Structured commitment extraction (second Claude call) ---
            extracted_commitments: list = []
            try:
                from src.synthesis.commitments import extract_commitments

                # Build synthesis text from sections for extraction
                synthesis_text_parts: list[str] = []
                if synthesis_result.get("executive_summary"):
                    synthesis_text_parts.append(synthesis_result["executive_summary"])
                for section in ["substance", "decisions", "commitments"]:
                    for item in synthesis_result.get(section, []):
                        synthesis_text_parts.append(item)
                synthesis_text = "\n".join(synthesis_text_parts)
                if synthesis_text.strip():
                    extracted_commitments = extract_commitments(
                        synthesis_text, current, config
                    )
                    logger.info(
                        "Extracted %d structured commitments",
                        len(extracted_commitments),
                    )
            except Exception as e:
                logger.warning(
                    "Commitment extraction failed: %s. Continuing without structured commitments.",
                    e,
                )

            # Quality tracking: detect edits on previous raw output before overwriting
            try:
                from src.quality import detect_edits, save_raw_output, update_quality_report

                edit_result = detect_edits(current, output_dir)
                if edit_result is not None:
                    report_path = update_quality_report(edit_result, output_dir)
                    if edit_result["edited"]:
                        logger.info(
                            "Edit detected for %s: similarity=%.0f%%, sections=%s",
                            current,
                            edit_result["similarity"] * 100,
                            ", ".join(edit_result["sections_changed"]) or "none",
                        )
                    else:
                        logger.info("No edits detected for %s", current)
            except Exception as e:
                logger.warning("Quality tracking (detect) failed: %s", e)

            path = write_daily_summary(synthesis, output_dir, template_dir, slack_items=slack_items, docs_items=docs_items, hubspot_items=hubspot_items)
            logger.info(
                "Wrote daily summary for %s -> %s (%d meetings, %.1fh)",
                current,
                path,
                synthesis.meeting_count,
                synthesis.total_meeting_hours,
            )

            # Quality tracking: save raw output for future comparison
            try:
                from src.quality import save_raw_output

                raw_content = path.read_text(encoding="utf-8")
                raw_path = save_raw_output(raw_content, current, output_dir)
                logger.info("Saved raw output -> %s", raw_path)
            except Exception as e:
                logger.warning("Quality tracking (save) failed: %s", e)

            # JSON sidecar: structured data output for downstream tools
            try:
                from src.output.writer import write_daily_sidecar

                sidecar_path = write_daily_sidecar(
                    synthesis, extractions, output_dir,
                    extracted_commitments=extracted_commitments,
                )
                logger.info("Wrote JSON sidecar -> %s", sidecar_path)
            except Exception as e:
                logger.warning("Sidecar generation failed: %s. Daily summary still written.", e)

            # Slack notification: post full summary
            try:
                from src.notifications.slack import send_slack_summary

                summary_content = path.read_text(encoding="utf-8")
                send_slack_summary(summary_content, current)
            except Exception as e:
                logger.warning("Slack notification failed: %s", e)

        except Exception as e:
            logger.error("Failed to process %s: %s", current, e)

        current += timedelta(days=1)


def run_weekly(args: argparse.Namespace) -> None:
    """Run the weekly roll-up pipeline."""
    from src.output.writer import insert_weekly_backlinks, write_weekly_summary
    from src.synthesis.weekly import synthesize_weekly

    config = load_config(Path(args.config))
    output_dir = Path(config.get("pipeline", {}).get("output_dir", "output"))
    template_dir = Path("templates")

    target_date = args.target_date
    synthesis = synthesize_weekly(target_date, config, output_dir)

    path = write_weekly_summary(synthesis, output_dir, template_dir)
    logger.info(
        "Wrote weekly summary for %d-W%02d -> %s (%d threads, %d single-day items)",
        synthesis.year,
        synthesis.week_number,
        path,
        len(synthesis.threads),
        len(synthesis.single_day_items),
    )

    # Insert backlinks into daily files
    daily_paths = []
    for d in synthesis.daily_dates:
        daily_path = output_dir / "daily" / str(d.year) / f"{d.month:02d}" / f"{d.isoformat()}.md"
        daily_paths.append(daily_path)

    inserted = insert_weekly_backlinks(path, daily_paths)
    if inserted:
        logger.info("Inserted %d backlink(s) into daily files", inserted)


def run_monthly(args: argparse.Namespace) -> None:
    """Run the monthly narrative synthesis pipeline."""
    from src.output.writer import write_monthly_summary
    from src.synthesis.monthly import synthesize_monthly

    config = load_config(Path(args.config))
    output_dir = Path(config.get("pipeline", {}).get("output_dir", "output"))
    template_dir = Path("templates")

    # Parse target month
    if args.target_month:
        parts = args.target_month.split("-")
        year = int(parts[0])
        month = int(parts[1])
    else:
        # Default to previous month
        today = date.today()
        if today.month == 1:
            year = today.year - 1
            month = 12
        else:
            year = today.year
            month = today.month - 1

    synthesis = synthesize_monthly(year, month, config, output_dir)

    path = write_monthly_summary(synthesis, output_dir, template_dir)
    logger.info(
        "Wrote monthly summary for %d-%02d -> %s (%d arcs, %d shifts, %d risks)",
        year,
        month,
        path,
        len(synthesis.thematic_arcs),
        len(synthesis.strategic_shifts),
        len(synthesis.emerging_risks),
    )


def run_discover_slack(args: argparse.Namespace) -> None:
    """Run Slack channel/DM discovery."""
    config = load_config(Path(args.config))
    from src.ingest.slack_discovery import run_discovery

    run_discovery(config)


def main() -> None:
    args = parse_args()

    if args.command == "weekly":
        run_weekly(args)
    elif args.command == "monthly":
        run_monthly(args)
    elif args.command == "discover-slack":
        run_discover_slack(args)
    else:
        # Default: daily pipeline (backward compatible)
        run_daily(args)


if __name__ == "__main__":
    main()
