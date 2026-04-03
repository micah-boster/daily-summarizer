"""JSON sidecar generation for daily synthesis pipeline.

Produces a structured JSON file alongside each daily markdown
for programmatic task extraction and decision metadata access.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.models.events import DailySynthesis
from src.synthesis.models import MeetingExtraction


class SidecarTask(BaseModel):
    """A task/commitment extracted from a meeting, structured for downstream tools."""

    description: str
    owner: str | None = None
    source_meeting: str
    date_captured: str  # ISO date
    due_date: str | None = None
    status: str = "new"  # new, in-progress, completed


class SidecarDecision(BaseModel):
    """A decision extracted from a meeting with attribution."""

    description: str
    decision_makers: list[str] = Field(default_factory=list)
    rationale: str | None = None
    source_meeting: str


class SidecarMeeting(BaseModel):
    """Metadata about a meeting that contributed to the daily summary."""

    title: str
    time: str  # ISO datetime
    participants: list[str] = Field(default_factory=list)
    has_transcript: bool = False


class DailySidecar(BaseModel):
    """Complete JSON sidecar for a daily summary."""

    date: str  # ISO date
    generated_at: str  # ISO datetime
    meeting_count: int
    transcript_count: int
    tasks: list[SidecarTask] = Field(default_factory=list)
    decisions: list[SidecarDecision] = Field(default_factory=list)
    source_meetings: list[SidecarMeeting] = Field(default_factory=list)


def build_daily_sidecar(
    synthesis: DailySynthesis,
    extractions: list[MeetingExtraction],
) -> DailySidecar:
    """Build a DailySidecar from synthesis data and meeting extractions.

    Maps commitments to tasks and decisions to structured records,
    both with source meeting attribution. Also includes meeting metadata.

    Args:
        synthesis: The DailySynthesis for the day.
        extractions: List of MeetingExtraction objects from Stage 1.

    Returns:
        DailySidecar ready for JSON serialization.
    """
    tasks: list[SidecarTask] = []
    decisions: list[SidecarDecision] = []
    source_meetings: list[SidecarMeeting] = []
    date_str = synthesis.date.isoformat()

    for ext in extractions:
        if ext.low_signal:
            continue

        # Map commitments to tasks
        for item in ext.commitments:
            tasks.append(
                SidecarTask(
                    description=item.content,
                    owner=item.participants[0] if item.participants else None,
                    source_meeting=ext.meeting_title,
                    date_captured=date_str,
                    due_date=None,
                    status="new",
                )
            )

        # Map decisions
        for item in ext.decisions:
            decisions.append(
                SidecarDecision(
                    description=item.content,
                    decision_makers=item.participants,
                    rationale=item.rationale,
                    source_meeting=ext.meeting_title,
                )
            )

        # Add meeting with transcript
        source_meetings.append(
            SidecarMeeting(
                title=ext.meeting_title,
                time=ext.meeting_time,
                participants=ext.meeting_participants,
                has_transcript=True,
            )
        )

    # Add meetings without transcripts
    for event in synthesis.meetings_without_transcripts:
        time_str = event.start_time.isoformat() if event.start_time else ""
        participants = [
            a.name or a.email for a in event.attendees if not a.is_self
        ]
        source_meetings.append(
            SidecarMeeting(
                title=event.title,
                time=time_str,
                participants=participants,
                has_transcript=False,
            )
        )

    return DailySidecar(
        date=date_str,
        generated_at=synthesis.generated_at.isoformat(),
        meeting_count=synthesis.meeting_count,
        transcript_count=synthesis.transcript_count,
        tasks=tasks,
        decisions=decisions,
        source_meetings=source_meetings,
    )
