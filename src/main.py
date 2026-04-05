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
from src.retry import retry_api_call


@retry_api_call
def _execute_with_retry(request):
    """Execute a Google API request with retry on transient errors."""
    return request.execute()

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

    # Discover-notion subcommand
    discover_notion_parser = subparsers.add_parser(
        "discover-notion", help="Discover and configure Notion databases for ingestion"
    )
    discover_notion_parser.add_argument(
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
    """Run the daily summary pipeline.

    Constructs a PipelineContext and delegates to run_pipeline() for each day
    in the date range. All pipeline logic lives in src/pipeline.py.
    """
    import anthropic

    from src.pipeline import PipelineContext, run_pipeline

    config = load_config(Path(args.config))

    from_date = args.from_date
    to_date = args.to_date or from_date

    output_dir = Path(config.pipeline.output_dir)
    template_dir = Path("templates")

    # Try to load OAuth credentials for calendar + gmail ingestion
    calendar_service = None
    gmail_service = None
    user_email = None
    creds = None
    try:
        from google.auth.transport.requests import Request

        from src.auth.google_oauth import load_credentials, save_credentials
        from src.ingest.calendar import build_calendar_service
        from src.ingest.gmail import build_gmail_service

        creds = load_credentials()
        if creds is None:
            logger.warning(
                "No valid credentials found. Run `python -m src.auth.google_oauth` to authenticate. "
                "Producing empty summary."
            )
        else:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                save_credentials(creds)

            calendar_service = build_calendar_service(creds)
            gmail_service = build_gmail_service(creds)

            try:
                primary_cal = _execute_with_retry(calendar_service.calendarList().get(calendarId="primary"))
                user_email = primary_cal.get("id")
                logger.info("Authenticated as: %s", user_email)
            except Exception as e:
                logger.warning("Could not fetch user email: %s", e)

    except Exception as e:
        logger.warning("Calendar ingestion unavailable: %s. Producing empty summaries.", e)

    # Create ONE shared Anthropic client for the entire run
    claude_client = anthropic.Anthropic()

    current = from_date
    while current <= to_date:
        ctx = PipelineContext(
            config=config,
            target_date=current,
            output_dir=output_dir,
            template_dir=template_dir,
            claude_client=claude_client,
            google_creds=creds,
            calendar_service=calendar_service,
            gmail_service=gmail_service,
            user_email=user_email,
        )
        try:
            run_pipeline(ctx)
        except Exception as e:
            logger.error("Failed to process %s: %s", current, e)

        current += timedelta(days=1)


def run_weekly(args: argparse.Namespace) -> None:
    """Run the weekly roll-up pipeline."""
    from src.output.writer import insert_weekly_backlinks, write_weekly_summary
    from src.synthesis.weekly import synthesize_weekly

    config = load_config(Path(args.config))
    output_dir = Path(config.pipeline.output_dir)
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
    output_dir = Path(config.pipeline.output_dir)
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


def run_discover_notion(args: argparse.Namespace) -> None:
    """Run Notion database discovery."""
    from src.ingest.notion_discovery import run_notion_discovery

    run_notion_discovery(args.config)


def main() -> None:
    args = parse_args()

    if args.command == "weekly":
        run_weekly(args)
    elif args.command == "monthly":
        run_monthly(args)
    elif args.command == "discover-slack":
        run_discover_slack(args)
    elif args.command == "discover-notion":
        run_discover_notion(args)
    else:
        # Default: daily pipeline (backward compatible)
        run_daily(args)


if __name__ == "__main__":
    main()
