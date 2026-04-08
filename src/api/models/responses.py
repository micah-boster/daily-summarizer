"""Pydantic response models for the Daily Summarizer API."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class SummaryListItem(BaseModel):
    """A single entry in the summary list endpoint."""

    date: date
    meeting_count: int | None = None
    commitment_count: int | None = None
    has_sidecar: bool = False


class SummaryResponse(BaseModel):
    """Full summary detail for a single date."""

    date: date
    markdown: str
    sidecar: dict | None = None


class StatusResponse(BaseModel):
    """API health / status check response."""

    status: str = "ok"
    db_connected: bool = False
    summary_count: int = 0
    last_summary_date: date | None = None


# --- Weekly roll-up models ---


class WeeklyListItem(BaseModel):
    """A single entry in the weekly roll-up list endpoint."""

    week_label: str
    year: int
    week_number: int
    start_date: date | None = None
    end_date: date | None = None
    daily_count: int = 0


class WeeklyResponse(BaseModel):
    """Full weekly roll-up detail."""

    week_number: int
    year: int
    start_date: date | None = None
    end_date: date | None = None
    markdown: str
    sidecar: dict | None = None


# --- Monthly roll-up models ---


class MonthlyListItem(BaseModel):
    """A single entry in the monthly roll-up list endpoint."""

    month_label: str
    year: int
    month: int


class MonthlyResponse(BaseModel):
    """Full monthly roll-up detail."""

    month: int
    year: int
    markdown: str
    sidecar: dict | None = None
