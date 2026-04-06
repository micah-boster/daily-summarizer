"""Pydantic models for meeting extraction and synthesis pipeline."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


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


class ExtractionItemOutput(BaseModel):
    """A single extracted item in structured output format (API response model)."""

    model_config = ConfigDict(extra="forbid")

    content: str  # Concise factual statement (15-20 words max)
    participants: list[str] = Field(default_factory=list)  # First names only
    rationale: str | None = None  # Explicit reason if stated, or null


class MeetingExtractionOutput(BaseModel):
    """Structured output model for Claude extraction API response.

    Used with json_schema constrained decoding. The reasoning field
    is a scratchpad for Claude's thinking and is discarded downstream.
    """

    model_config = ConfigDict(extra="forbid")

    reasoning: str = ""  # Scratchpad for Claude's thinking (discarded downstream)
    decisions: list[ExtractionItemOutput] = Field(default_factory=list)
    commitments: list[ExtractionItemOutput] = Field(default_factory=list)
    substance: list[ExtractionItemOutput] = Field(default_factory=list)
    open_questions: list[ExtractionItemOutput] = Field(default_factory=list)
    tensions: list[ExtractionItemOutput] = Field(default_factory=list)


class SynthesisItem(BaseModel):
    """A single substance or decision item in synthesis output."""

    model_config = ConfigDict(extra="forbid")

    content: str  # Full text including attribution
    entity_names: list[str] = Field(default_factory=list)  # Partners/people mentioned


class CommitmentRow(BaseModel):
    """A single commitment in synthesis output."""

    model_config = ConfigDict(extra="forbid")

    who: str  # Person name or "TBD"
    what: str  # Commitment description
    by_when: str  # ISO date, "week of YYYY-MM-DD", or "unspecified"
    source: str  # Attribution text
    entity_names: list[str] = Field(default_factory=list)  # Partners/people mentioned


class DailySynthesisOutput(BaseModel):
    """Structured output model for Claude synthesis API response.

    Used with json_schema constrained decoding. The reasoning field
    is a scratchpad for cross-source analysis and is discarded downstream.
    """

    model_config = ConfigDict(extra="forbid")

    reasoning: str = ""  # Cross-source analysis scratchpad (discarded)
    executive_summary: str | None = None
    substance: list[SynthesisItem] = Field(default_factory=list)
    decisions: list[SynthesisItem] = Field(default_factory=list)
    commitments: list[CommitmentRow] = Field(default_factory=list)


# --- Weekly structured output models ---


class WeeklyThreadEntryOutput(BaseModel):
    """A single day's contribution to a thread in structured output format."""

    model_config = ConfigDict(extra="forbid")

    day_label: str  # e.g. "Monday, March 30"
    category: str  # "decision", "commitment", "substance"
    content: str


class StillOpenItemOutput(BaseModel):
    """An unresolved item in structured output format."""

    model_config = ConfigDict(extra="forbid")

    content: str
    owner: str | None = None
    since: str | None = None


class WeeklyThreadOutput(BaseModel):
    """A thread traced across multiple days in structured output format."""

    model_config = ConfigDict(extra="forbid")

    title: str
    significance: str  # "high" or "medium"
    status: str  # "resolved", "open", "escalated"
    tags: list[str] = Field(default_factory=list)
    progression: str
    entries: list[WeeklyThreadEntryOutput] = Field(default_factory=list)


class WeeklySynthesisOutput(BaseModel):
    """Structured output model for Claude weekly thread detection API response.

    Used with json_schema constrained decoding. The reasoning field
    is a scratchpad for Claude's thinking and is discarded downstream.
    """

    model_config = ConfigDict(extra="forbid")

    reasoning: str = ""  # Scratchpad for Claude's thinking (discarded downstream)
    threads: list[WeeklyThreadOutput] = Field(default_factory=list)
    single_day_items: list[WeeklyThreadEntryOutput] = Field(default_factory=list)
    still_open: list[StillOpenItemOutput] = Field(default_factory=list)


# --- Monthly structured output models ---


class ThematicArcOutput(BaseModel):
    """A thematic arc in structured output format."""

    model_config = ConfigDict(extra="forbid")

    title: str
    trajectory: str  # "growing", "declining", "stable", "emerging", "resolved"
    weeks_active: list[int] = Field(default_factory=list)
    description: str
    key_moments: list[str] = Field(default_factory=list)


class MonthlySynthesisOutput(BaseModel):
    """Structured output model for Claude monthly narrative API response.

    Used with json_schema constrained decoding. The reasoning field
    is a scratchpad for Claude's thinking and is discarded downstream.
    """

    model_config = ConfigDict(extra="forbid")

    reasoning: str = ""  # Scratchpad for Claude's thinking (discarded downstream)
    thematic_arcs: list[ThematicArcOutput] = Field(default_factory=list)
    strategic_shifts: list[str] = Field(default_factory=list)
    emerging_risks: list[str] = Field(default_factory=list)
    still_open: list[StillOpenItemOutput] = Field(default_factory=list)
