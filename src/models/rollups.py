"""Pydantic models for temporal roll-ups: weekly threads and monthly narratives."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class ThreadEntry(BaseModel):
    """A single day's contribution to a thread."""

    date: date
    content: str
    category: str  # "decision", "commitment", "substance"


class WeeklyThread(BaseModel):
    """A thread traced across multiple days in a week."""

    title: str
    significance: str  # "high", "medium"
    entries: list[ThreadEntry] = Field(default_factory=list)
    progression: str  # Narrative arc: "raised -> explored -> decided"
    status: str  # "resolved", "open", "escalated"
    tags: list[str] = Field(default_factory=list)  # ["decision", "commitment"]


class WeeklySynthesis(BaseModel):
    """Complete weekly roll-up with threads and single-day items."""

    week_number: int
    year: int
    start_date: date
    end_date: date
    generated_at: datetime
    daily_count: int
    is_partial: bool
    meeting_count: int
    total_meeting_hours: float
    threads: list[WeeklyThread] = Field(default_factory=list)
    single_day_items: list[ThreadEntry] = Field(default_factory=list)
    still_open: list[dict] = Field(default_factory=list)
    daily_dates: list[date] = Field(default_factory=list)


class ThematicArc(BaseModel):
    """A thematic arc spanning multiple weeks in a month."""

    title: str
    description: str  # 2-3 sentence analytical summary
    weeks_active: list[int] = Field(default_factory=list)
    trajectory: str  # "growing", "declining", "stable", "emerging", "resolved"
    key_moments: list[str] = Field(default_factory=list)


class MonthlyMetrics(BaseModel):
    """Aggregate metrics for a month of meetings."""

    total_meetings: int = 0
    total_hours: float = 0.0
    total_decisions: int = 0
    top_attendees: list[str] = Field(default_factory=list)
    weekly_meeting_counts: list[int] = Field(default_factory=list)


class MonthlySynthesis(BaseModel):
    """Complete monthly narrative with thematic arcs and metrics."""

    month: int
    year: int
    generated_at: datetime
    weekly_count: int
    thematic_arcs: list[ThematicArc] = Field(default_factory=list)
    strategic_shifts: list[str] = Field(default_factory=list)
    emerging_risks: list[str] = Field(default_factory=list)
    metrics: MonthlyMetrics = Field(default_factory=MonthlyMetrics)
    still_open: list[dict] = Field(default_factory=list)
