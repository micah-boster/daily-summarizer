from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src.models.events import Attendee, DailySynthesis


def _format_time(dt) -> str:
    """Format datetime to '2:00pm' style string."""
    if dt is None:
        return ""
    return dt.strftime("%-I:%M%p").lower()


def _format_attendees(attendees: list[Attendee]) -> str:
    """Format attendee list as comma-separated names, excluding self."""
    names = []
    for a in attendees:
        if a.is_self:
            continue
        names.append(a.name if a.name else a.email)
    return ", ".join(names)


def _format_duration(minutes: int | None) -> str:
    """Format duration in minutes to human-readable string."""
    if minutes is None:
        return ""
    if minutes >= 60:
        hours = minutes // 60
        remaining = minutes % 60
        if remaining:
            return f"{hours}h {remaining}min"
        return f"{hours}h"
    return f"{minutes} min"


def create_jinja_env(template_dir: Path) -> Environment:
    """Create Jinja2 environment with custom filters for daily summary rendering."""
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    env.filters["format_time"] = _format_time
    env.filters["format_attendees"] = _format_attendees
    env.filters["format_duration"] = _format_duration
    return env


def write_daily_summary(
    synthesis: DailySynthesis,
    output_dir: Path,
    template_dir: Path,
) -> Path:
    """Render a DailySynthesis to markdown and write to the output directory.

    Creates directory structure: output_dir/daily/YYYY/MM/YYYY-MM-DD.md
    Overwrites if file exists (latest run wins).

    Args:
        synthesis: The daily synthesis data to render.
        output_dir: Base output directory.
        template_dir: Directory containing Jinja2 templates.

    Returns:
        Path to the written markdown file.
    """
    env = create_jinja_env(template_dir)
    template = env.get_template("daily.md.j2")

    rendered = template.render(
        date=synthesis.date,
        generated_at=synthesis.generated_at,
        meeting_count=synthesis.meeting_count,
        total_meeting_hours=synthesis.total_meeting_hours,
        transcript_count=synthesis.transcript_count,
        all_day_events=synthesis.all_day_events,
        timed_events=synthesis.timed_events,
        declined_events=synthesis.declined_events,
        cancelled_events=synthesis.cancelled_events,
        substance=synthesis.substance,
        decisions=synthesis.decisions,
        commitments=synthesis.commitments,
    )

    # Build output path: output_dir/daily/YYYY/MM/YYYY-MM-DD.md
    d = synthesis.date
    file_dir = output_dir / "daily" / str(d.year) / f"{d.month:02d}"
    file_dir.mkdir(parents=True, exist_ok=True)
    file_path = file_dir / f"{d.isoformat()}.md"

    file_path.write_text(rendered, encoding="utf-8")
    return file_path
