"""Summary, roll-up, and status endpoints for the Daily Summarizer API."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import get_config, get_rollup_reader, get_summary_reader
from src.api.models.responses import (
    MonthlyListItem,
    MonthlyResponse,
    StatusResponse,
    SummaryListItem,
    SummaryResponse,
    WeeklyListItem,
    WeeklyResponse,
)
from src.api.services.rollup_reader import RollupReader
from src.api.services.summary_reader import SummaryReader
from src.config import PipelineConfig
from src.entity.repository import EntityRepository

router = APIRouter(tags=["summaries"])


# --- Daily summary endpoints ---


@router.get("/summaries", response_model=list[SummaryListItem])
def list_summaries(reader: SummaryReader = Depends(get_summary_reader)):
    """Return all available summary dates with preview data."""
    return reader.list_available_dates_with_previews()


# NOTE: Weekly and monthly routes MUST be registered before /{target_date}
# so FastAPI does not try to parse "weekly" or "monthly" as a date string.


# --- Weekly roll-up endpoints ---


@router.get("/summaries/weekly", response_model=list[WeeklyListItem])
def list_weekly_rollups(reader: RollupReader = Depends(get_rollup_reader)):
    """Return all available weekly roll-up summaries."""
    return reader.list_weekly()


@router.get("/summaries/weekly/{year}/{week}", response_model=WeeklyResponse)
def get_weekly_rollup(
    year: int, week: int, reader: RollupReader = Depends(get_rollup_reader)
):
    """Return the full weekly roll-up for a specific year and week number."""
    result = reader.get_weekly(year, week)
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"No weekly roll-up for {year}-W{week:02d}"
        )
    return result


# --- Monthly roll-up endpoints ---


@router.get("/summaries/monthly", response_model=list[MonthlyListItem])
def list_monthly_rollups(reader: RollupReader = Depends(get_rollup_reader)):
    """Return all available monthly roll-up summaries."""
    return reader.list_monthly()


@router.get("/summaries/monthly/{year}/{month}", response_model=MonthlyResponse)
def get_monthly_rollup(
    year: int, month: int, reader: RollupReader = Depends(get_rollup_reader)
):
    """Return the full monthly roll-up for a specific year and month."""
    result = reader.get_monthly(year, month)
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"No monthly roll-up for {year}-{month:02d}"
        )
    return result


# --- Daily detail endpoint (AFTER weekly/monthly to avoid route conflict) ---


@router.get("/summaries/{target_date}", response_model=SummaryResponse)
def get_summary(target_date: date, reader: SummaryReader = Depends(get_summary_reader)):
    """Return the full summary for a specific date."""
    result = reader.get_summary(target_date)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No summary found for {target_date}")
    return result


# --- Status ---


@router.get("/status", response_model=StatusResponse)
def get_status(
    reader: SummaryReader = Depends(get_summary_reader),
    config: PipelineConfig = Depends(get_config),
):
    """Health check with DB connectivity and summary stats."""
    db_connected = False
    try:
        repo = EntityRepository(config.entity.db_path)
        repo.connect()
        repo.close()
        db_connected = True
    except Exception:
        pass

    dates = reader.list_available_dates()
    return StatusResponse(
        status="ok",
        db_connected=db_connected,
        summary_count=len(dates),
        last_summary_date=dates[0] if dates else None,
    )
