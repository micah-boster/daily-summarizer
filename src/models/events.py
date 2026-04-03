from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ResponseStatus(StrEnum):
    ACCEPTED = "accepted"
    DECLINED = "declined"
    TENTATIVE = "tentative"
    NEEDS_ACTION = "needsAction"


class Attendee(BaseModel):
    name: str | None = None
    email: str
    response_status: ResponseStatus = ResponseStatus.NEEDS_ACTION
    is_self: bool = False
    is_organizer: bool = False


class NormalizedEvent(BaseModel):
    id: str
    source: str = "google_calendar"
    title: str
    start_time: datetime | None = None
    end_time: datetime | None = None
    all_day: bool = False
    date: str | None = None
    duration_minutes: int | None = None
    attendees: list[Attendee] = Field(default_factory=list)
    description: str | None = None
    location: str | None = None
    meeting_link: str | None = None
    is_recurring: bool = False
    event_type: str = "default"
    status: str = "confirmed"
    calendar_id: str = "primary"
    transcript_text: str | None = None
    transcript_source: str | None = None
    raw_data: dict | None = None


class Section(BaseModel):
    title: str
    items: list[str] = Field(default_factory=list)


class DailySynthesis(BaseModel):
    date: date
    generated_at: datetime
    meeting_count: int = 0
    total_meeting_hours: float = 0.0
    transcript_count: int = 0
    all_day_events: list[NormalizedEvent] = Field(default_factory=list)
    timed_events: list[NormalizedEvent] = Field(default_factory=list)
    declined_events: list[NormalizedEvent] = Field(default_factory=list)
    cancelled_events: list[NormalizedEvent] = Field(default_factory=list)
    unmatched_transcripts: list[dict] = Field(default_factory=list)
    substance: Section = Field(default_factory=lambda: Section(title="Substance"))
    decisions: Section = Field(default_factory=lambda: Section(title="Decisions"))
    commitments: Section = Field(default_factory=lambda: Section(title="Commitments"))
