"""Pydantic models for pipeline run API responses."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, Field


class RunStage(BaseModel):
    """A single pipeline stage within a run."""

    name: str
    status: Literal["pending", "running", "complete", "failed"]
    elapsed_s: float | None = None


class RunResponse(BaseModel):
    """Full details for a single pipeline run."""

    id: str
    target_date: str
    status: Literal["running", "complete", "failed"]
    stages: list[RunStage] = Field(default_factory=list)
    started_at: str
    completed_at: str | None = None
    duration_s: float | None = None
    error_message: str | None = None
    error_stage: str | None = None


class RunListResponse(BaseModel):
    """Paginated list of pipeline runs."""

    runs: list[RunResponse]
    total: int


class TriggerRequest(BaseModel):
    """Request body to trigger a new pipeline run."""

    target_date: str | None = None  # Defaults to yesterday if not provided

    def get_target_date(self) -> str:
        """Return target_date or default to yesterday."""
        if self.target_date:
            return self.target_date
        return (date.today() - timedelta(days=1)).isoformat()


class TriggerResponse(BaseModel):
    """Response after triggering a pipeline run."""

    run_id: str
    status: str
