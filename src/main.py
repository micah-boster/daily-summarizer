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

    current = from_date
    while current <= to_date:
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
        logger.info("Wrote daily summary for %s -> %s", current, path)

        current += timedelta(days=1)


if __name__ == "__main__":
    main()
