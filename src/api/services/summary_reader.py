"""Service for reading daily summary files from the output directory."""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

from src.api.models.responses import SummaryListItem, SummaryResponse

logger = logging.getLogger(__name__)


class SummaryReader:
    """Reads daily summary markdown and sidecar JSON from the output tree.

    Expected layout::

        {output_dir}/daily/YYYY/MM/YYYY-MM-DD.md
        {output_dir}/daily/YYYY/MM/YYYY-MM-DD.json   (optional sidecar)
    """

    def __init__(self, output_dir: str = "output") -> None:
        self._base = Path(output_dir) / "daily"

    def list_available_dates(self) -> list[date]:
        """Return all dates that have a markdown summary, sorted descending."""
        dates: list[date] = []
        for md_path in self._base.glob("**/*.md"):
            try:
                d = date.fromisoformat(md_path.stem)
                dates.append(d)
            except ValueError:
                continue
        dates.sort(reverse=True)
        return dates

    def list_available_dates_with_previews(self) -> list[SummaryListItem]:
        """Return summary list items with preview data from sidecars."""
        from src.sidecar import DailySidecar

        items: list[SummaryListItem] = []
        for d in self.list_available_dates():
            json_path = self._path_for_date(d).with_suffix(".json")
            if json_path.exists():
                try:
                    raw = json.loads(json_path.read_text())
                    sidecar = DailySidecar.model_validate(raw)
                    items.append(
                        SummaryListItem(
                            date=d,
                            meeting_count=sidecar.meeting_count,
                            commitment_count=len(sidecar.commitments),
                            has_sidecar=True,
                        )
                    )
                except Exception:
                    logger.warning("Failed to parse sidecar for %s", d, exc_info=True)
                    items.append(SummaryListItem(date=d, has_sidecar=False))
            else:
                items.append(SummaryListItem(date=d, has_sidecar=False))
        return items

    def get_summary(self, target_date: date) -> SummaryResponse | None:
        """Load a single day's summary. Returns None if no markdown exists."""
        md_path = self._path_for_date(target_date)
        if not md_path.exists():
            return None

        markdown = md_path.read_text()

        sidecar: dict | None = None
        json_path = md_path.with_suffix(".json")
        if json_path.exists():
            try:
                sidecar = json.loads(json_path.read_text())
            except Exception:
                logger.warning("Failed to read sidecar for %s", target_date, exc_info=True)

        return SummaryResponse(date=target_date, markdown=markdown, sidecar=sidecar)

    def _path_for_date(self, d: date) -> Path:
        """Build the filesystem path for a given date's markdown file."""
        return self._base / str(d.year) / f"{d.month:02d}" / f"{d.isoformat()}.md"
