"""Pydantic models for meeting extraction and synthesis pipeline."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractionItem(BaseModel):
    """A single extracted item (decision, commitment, substance item, etc.)."""

    content: str  # The factual statement
    participants: list[str] = Field(default_factory=list)  # People involved
    rationale: str | None = None  # Reasoning if stated in transcript


class MeetingExtraction(BaseModel):
    """Structured extraction from a single meeting transcript."""

    meeting_title: str
    meeting_time: str  # ISO format string
    meeting_participants: list[str] = Field(default_factory=list)
    decisions: list[ExtractionItem] = Field(default_factory=list)
    commitments: list[ExtractionItem] = Field(default_factory=list)
    substance: list[ExtractionItem] = Field(default_factory=list)
    open_questions: list[ExtractionItem] = Field(default_factory=list)
    tensions: list[ExtractionItem] = Field(default_factory=list)
    low_signal: bool = False  # True if transcript had no substantive content
