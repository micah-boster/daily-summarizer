"""Service for reading weekly and monthly roll-up summary files."""

from __future__ import annotations

import calendar
import json
import logging
import re
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)


class RollupReader:
    """Reads weekly and monthly roll-up summaries from the output tree.

    Expected layout::

        {output_dir}/weekly/YYYY/YYYY-WXX.md   (with optional .json sidecar)
        {output_dir}/monthly/YYYY/YYYY-MM.md    (with optional .json sidecar)
    """

    def __init__(self, output_dir: str = "output") -> None:
        self._weekly_base = Path(output_dir) / "weekly"
        self._monthly_base = Path(output_dir) / "monthly"

    # ------------------------------------------------------------------
    # Weekly
    # ------------------------------------------------------------------

    def list_weekly(self) -> list[dict]:
        """Return all available weekly roll-ups, sorted descending."""
        items: list[dict] = []
        for md_path in self._weekly_base.glob("**/*.md"):
            match = re.match(r"(\d{4})-W(\d{2})", md_path.stem)
            if not match:
                continue
            year, week = int(match.group(1)), int(match.group(2))

            # Try to load sidecar for richer metadata
            start_date = None
            end_date = None
            daily_count = 0
            json_path = md_path.with_suffix(".json")
            if json_path.exists():
                try:
                    raw = json.loads(json_path.read_text())
                    start_date = raw.get("start_date")
                    end_date = raw.get("end_date")
                    daily_count = raw.get("daily_count", 0)
                except Exception:
                    logger.warning("Failed to parse weekly sidecar %s", json_path)

            # Fallback: derive start_date from ISO week
            if start_date is None:
                try:
                    d = date.fromisocalendar(year, week, 1)
                    start_date = d.isoformat()
                except ValueError:
                    pass

            items.append(
                {
                    "week_label": f"Week {week}, {year}",
                    "year": year,
                    "week_number": week,
                    "start_date": start_date,
                    "end_date": end_date,
                    "daily_count": daily_count,
                }
            )

        items.sort(key=lambda x: (x["year"], x["week_number"]), reverse=True)
        return items

    def get_weekly(self, year: int, week: int) -> dict | None:
        """Load a specific weekly roll-up. Returns None if not found."""
        md_path = self._weekly_base / str(year) / f"{year}-W{week:02d}.md"
        if not md_path.exists():
            return None

        markdown = md_path.read_text()
        sidecar = self._load_sidecar(md_path)

        start_date = None
        end_date = None
        if sidecar:
            start_date = sidecar.get("start_date")
            end_date = sidecar.get("end_date")
        if start_date is None:
            try:
                d = date.fromisocalendar(year, week, 1)
                start_date = d.isoformat()
            except ValueError:
                pass

        return {
            "week_number": week,
            "year": year,
            "start_date": start_date,
            "end_date": end_date,
            "markdown": markdown,
            "sidecar": sidecar,
        }

    # ------------------------------------------------------------------
    # Monthly
    # ------------------------------------------------------------------

    def list_monthly(self) -> list[dict]:
        """Return all available monthly roll-ups, sorted descending."""
        items: list[dict] = []
        for md_path in self._monthly_base.glob("**/*.md"):
            match = re.match(r"(\d{4})-(\d{2})", md_path.stem)
            if not match:
                continue
            year, month = int(match.group(1)), int(match.group(2))
            month_name = calendar.month_name[month]
            items.append(
                {
                    "month_label": f"{month_name} {year}",
                    "year": year,
                    "month": month,
                }
            )

        items.sort(key=lambda x: (x["year"], x["month"]), reverse=True)
        return items

    def get_monthly(self, year: int, month: int) -> dict | None:
        """Load a specific monthly roll-up. Returns None if not found."""
        md_path = self._monthly_base / str(year) / f"{year}-{month:02d}.md"
        if not md_path.exists():
            return None

        markdown = md_path.read_text()
        sidecar = self._load_sidecar(md_path)

        return {
            "month": month,
            "year": year,
            "markdown": markdown,
            "sidecar": sidecar,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_sidecar(md_path: Path) -> dict | None:
        json_path = md_path.with_suffix(".json")
        if not json_path.exists():
            return None
        try:
            return json.loads(json_path.read_text())
        except Exception:
            logger.warning("Failed to read sidecar for %s", md_path)
            return None
