from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from src.models.events import (
    Attendee,
    DailySynthesis,
    NormalizedEvent,
    ResponseStatus,
    Section,
)
from src.output.writer import write_daily_summary


def _make_synthesis(**kwargs) -> DailySynthesis:
    defaults = {
        "date": date(2026, 4, 1),
        "generated_at": datetime(2026, 4, 1, 8, 0, 0, tzinfo=timezone.utc),
        "substance": Section(title="Substance"),
        "decisions": Section(title="Decisions"),
        "commitments": Section(title="Commitments"),
    }
    defaults.update(kwargs)
    return DailySynthesis(**defaults)


def _sample_timed_events() -> list[NormalizedEvent]:
    return [
        NormalizedEvent(
            id="evt1",
            title="Team Standup",
            start_time=datetime(2026, 4, 1, 9, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 4, 1, 9, 30, 0, tzinfo=timezone.utc),
            duration_minutes=30,
            is_recurring=True,
            attendees=[
                Attendee(
                    name="You",
                    email="me@example.com",
                    response_status=ResponseStatus.ACCEPTED,
                    is_self=True,
                ),
                Attendee(
                    name="Sarah Chen",
                    email="sarah@example.com",
                    response_status=ResponseStatus.ACCEPTED,
                ),
            ],
        ),
        NormalizedEvent(
            id="evt2",
            title="Q3 Planning",
            start_time=datetime(2026, 4, 1, 14, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 4, 1, 15, 0, 0, tzinfo=timezone.utc),
            duration_minutes=60,
            meeting_link="https://meet.google.com/abc-def",
            description="Discuss Q3 priorities and roadmap.",
            attendees=[
                Attendee(
                    name="You",
                    email="me@example.com",
                    response_status=ResponseStatus.ACCEPTED,
                    is_self=True,
                ),
                Attendee(
                    name="Alex Kim",
                    email="alex@example.com",
                    response_status=ResponseStatus.TENTATIVE,
                ),
            ],
        ),
    ]


TEMPLATE_DIR = Path("templates")


class TestWriteDailySummary:
    def test_creates_file_at_correct_path(self, tmp_path: Path):
        synthesis = _make_synthesis()
        path = write_daily_summary(synthesis, tmp_path, TEMPLATE_DIR)
        assert path.exists()
        assert path == tmp_path / "daily" / "2026" / "04" / "2026-04-01.md"

    def test_output_contains_daily_summary_header(self, tmp_path: Path):
        synthesis = _make_synthesis()
        path = write_daily_summary(synthesis, tmp_path, TEMPLATE_DIR)
        content = path.read_text()
        assert "# Daily Summary: 2026-04-01" in content

    def test_output_contains_overview_with_meeting_count(self, tmp_path: Path):
        synthesis = _make_synthesis(meeting_count=5, total_meeting_hours=3.5)
        path = write_daily_summary(synthesis, tmp_path, TEMPLATE_DIR)
        content = path.read_text()
        assert "## Overview" in content
        assert "5 meetings" in content
        assert "3.5 hours" in content

    def test_template_renders_timed_events_in_table(self, tmp_path: Path):
        events = _sample_timed_events()
        synthesis = _make_synthesis(
            timed_events=events,
            meeting_count=2,
            total_meeting_hours=1.5,
        )
        path = write_daily_summary(synthesis, tmp_path, TEMPLATE_DIR)
        content = path.read_text()
        assert "## Calendar" in content
        assert "Team Standup" in content
        assert "↻" in content  # Recurring marker
        assert "Sarah Chen" in content
        assert "Q3 Planning" in content

    def test_template_renders_calendar_section(self, tmp_path: Path):
        """Calendar section always renders with table header, even without events."""
        synthesis = _make_synthesis()
        path = write_daily_summary(synthesis, tmp_path, TEMPLATE_DIR)
        content = path.read_text()
        assert "## Calendar" in content
        assert "| Time | Meeting | With |" in content

    def test_template_omits_declined_section_when_empty(self, tmp_path: Path):
        synthesis = _make_synthesis()
        path = write_daily_summary(synthesis, tmp_path, TEMPLATE_DIR)
        content = path.read_text()
        assert "## Declined" not in content

    def test_empty_sections_omitted(self, tmp_path: Path):
        """Sections with no data are omitted, not shown with placeholders."""
        synthesis = _make_synthesis()
        path = write_daily_summary(synthesis, tmp_path, TEMPLATE_DIR)
        content = path.read_text()
        # Empty sections should NOT appear (template conditionals)
        assert "## Substance" not in content
        assert "## Decisions" not in content
        # Commitments only appears if there are items
        assert content.count("## Commitments") == 0

    def test_generated_timestamp_in_footer(self, tmp_path: Path):
        synthesis = _make_synthesis()
        path = write_daily_summary(synthesis, tmp_path, TEMPLATE_DIR)
        content = path.read_text()
        assert "*Generated:" in content
