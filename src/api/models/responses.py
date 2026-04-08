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
