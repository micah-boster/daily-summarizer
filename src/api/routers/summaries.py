"""Summary and status endpoints for the Daily Summarizer API."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import get_config, get_summary_reader
from src.api.models.responses import StatusResponse, SummaryListItem, SummaryResponse
from src.api.services.summary_reader import SummaryReader
from src.config import PipelineConfig
from src.entity.repository import EntityRepository

router = APIRouter(tags=["summaries"])


@router.get("/summaries", response_model=list[SummaryListItem])
def list_summaries(reader: SummaryReader = Depends(get_summary_reader)):
    """Return all available summary dates with preview data."""
    return reader.list_available_dates_with_previews()


@router.get("/summaries/{target_date}", response_model=SummaryResponse)
def get_summary(target_date: date, reader: SummaryReader = Depends(get_summary_reader)):
    """Return the full summary for a specific date."""
    result = reader.get_summary(target_date)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No summary found for {target_date}")
    return result


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
