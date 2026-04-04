from __future__ import annotations

import calendar
import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src.models.events import Attendee, DailySynthesis


def _format_time(dt) -> str:
    """Format datetime to '2:00pm' style string."""
    if dt is None:
        return ""
    return dt.strftime("%-I:%M%p").lower()


def _format_attendees(attendees: list[Attendee]) -> str:
    """Format attendee list as comma-separated names, excluding self and resources."""
    names = []
    for a in attendees:
        if a.is_self:
            continue
        # Skip conference rooms and resources
        if a.email and "@resource.calendar.google.com" in a.email:
            continue
        # Skip entries that look like room names (contain bracketed hardware info)
        display = a.name if a.name else a.email
        if "[" in display and "]" in display:
            continue
        # Use first name only for internal team (finbounce.com)
        if a.email and "finbounce.com" in a.email:
            if a.name:
                display = a.name.split()[0]
            else:
                # Extract name from email: "colin@finbounce.com" -> "Colin"
                display = a.email.split("@")[0].capitalize()
        names.append(display)
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


def _format_date(d) -> str:
    """Format date to 'Mon, Apr 3' style string."""
    if d is None:
        return ""
    return d.strftime("%a, %b %-d")


def _format_month_name(month_num) -> str:
    """Convert month number (1-12) to full month name."""
    if month_num is None or not isinstance(month_num, int):
        return ""
    return calendar.month_name[month_num]


def _split_emdash(text: str, expected_cols: int = 3) -> list[str]:
    """Split a synthesis bullet on em-dash separators into columns.

    Returns a list padded/truncated to expected_cols length.
    e.g. "Build reporting table — Micah — Account Review" -> ["Build reporting table", "Micah", "Account Review"]
    """
    parts = [p.strip() for p in text.split("—")]
    # Pad with empty strings if fewer parts than expected
    while len(parts) < expected_cols:
        parts.append("")
    return parts[:expected_cols]


def create_jinja_env(template_dir: Path) -> Environment:
    """Create Jinja2 environment with custom filters for summary rendering."""
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    env.filters["format_time"] = _format_time
    env.filters["format_attendees"] = _format_attendees
    env.filters["format_duration"] = _format_duration
    env.filters["format_date"] = _format_date
    env.filters["format_month_name"] = _format_month_name
    env.filters["split_emdash"] = _split_emdash
    return env


def write_daily_summary(
    synthesis: DailySynthesis,
    output_dir: Path,
    template_dir: Path,
    slack_items: list | None = None,
) -> Path:
    """Render a DailySynthesis to markdown and write to the output directory.

    Creates directory structure: output_dir/daily/YYYY/MM/YYYY-MM-DD.md
    Overwrites if file exists (latest run wins).

    Args:
        synthesis: The daily synthesis data to render.
        output_dir: Base output directory.
        template_dir: Directory containing Jinja2 templates.
        slack_items: Optional list of Slack SourceItems for the activity section.

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
        executive_summary=synthesis.executive_summary,
        substance=synthesis.substance,
        decisions=synthesis.decisions,
        commitments=synthesis.commitments,
        meetings_without_transcripts=synthesis.meetings_without_transcripts,
        extractions=synthesis.extractions,
        slack_items=slack_items or [],
        slack_item_count=len(slack_items) if slack_items else 0,
    )

    # Build output path: output_dir/daily/YYYY/MM/YYYY-MM-DD.md
    d = synthesis.date
    file_dir = output_dir / "daily" / str(d.year) / f"{d.month:02d}"
    file_dir.mkdir(parents=True, exist_ok=True)
    file_path = file_dir / f"{d.isoformat()}.md"

    file_path.write_text(rendered, encoding="utf-8")
    return file_path


def write_daily_sidecar(
    synthesis: DailySynthesis,
    extractions: list,
    output_dir: Path,
) -> Path:
    """Write a JSON sidecar file alongside the daily markdown summary.

    Produces YYYY-MM-DD.json in the same directory as YYYY-MM-DD.md,
    containing structured tasks, decisions, and source meeting metadata.

    Args:
        synthesis: The DailySynthesis data.
        extractions: List of MeetingExtraction objects from Stage 1.
        output_dir: Base output directory.

    Returns:
        Path to the written JSON sidecar file.
    """
    from src.sidecar import build_daily_sidecar

    sidecar = build_daily_sidecar(synthesis, extractions)

    d = synthesis.date
    file_dir = output_dir / "daily" / str(d.year) / f"{d.month:02d}"
    file_dir.mkdir(parents=True, exist_ok=True)
    file_path = file_dir / f"{d.isoformat()}.json"

    file_path.write_text(sidecar.model_dump_json(indent=2), encoding="utf-8")
    return file_path


def write_weekly_summary(
    synthesis,
    output_dir: Path,
    template_dir: Path,
) -> Path:
    """Render a WeeklySynthesis to markdown and write to the output directory.

    Creates directory structure: output_dir/weekly/YYYY/YYYY-WXX.md
    Overwrites if file exists (latest run wins).

    Args:
        synthesis: The WeeklySynthesis data to render.
        output_dir: Base output directory.
        template_dir: Directory containing Jinja2 templates.

    Returns:
        Path to the written markdown file.
    """
    env = create_jinja_env(template_dir)
    template = env.get_template("weekly.md.j2")

    rendered = template.render(
        week_number=synthesis.week_number,
        year=synthesis.year,
        start_date=synthesis.start_date,
        end_date=synthesis.end_date,
        generated_at=synthesis.generated_at,
        daily_count=synthesis.daily_count,
        is_partial=synthesis.is_partial,
        meeting_count=synthesis.meeting_count,
        total_meeting_hours=synthesis.total_meeting_hours,
        threads=synthesis.threads,
        single_day_items=synthesis.single_day_items,
        still_open=synthesis.still_open,
    )

    file_dir = output_dir / "weekly" / str(synthesis.year)
    file_dir.mkdir(parents=True, exist_ok=True)
    file_path = file_dir / f"{synthesis.year}-W{synthesis.week_number:02d}.md"

    file_path.write_text(rendered, encoding="utf-8")
    return file_path


def write_monthly_summary(
    synthesis,
    output_dir: Path,
    template_dir: Path,
) -> Path:
    """Render a MonthlySynthesis to markdown and write to the output directory.

    Creates directory structure: output_dir/monthly/YYYY/YYYY-MM.md
    Overwrites if file exists (latest run wins).

    Args:
        synthesis: The MonthlySynthesis data to render.
        output_dir: Base output directory.
        template_dir: Directory containing Jinja2 templates.

    Returns:
        Path to the written markdown file.
    """
    env = create_jinja_env(template_dir)
    template = env.get_template("monthly.md.j2")

    rendered = template.render(
        month=synthesis.month,
        month_name=calendar.month_name[synthesis.month],
        year=synthesis.year,
        generated_at=synthesis.generated_at,
        weekly_count=synthesis.weekly_count,
        thematic_arcs=synthesis.thematic_arcs,
        strategic_shifts=synthesis.strategic_shifts,
        emerging_risks=synthesis.emerging_risks,
        metrics=synthesis.metrics,
        still_open=synthesis.still_open,
    )

    file_dir = output_dir / "monthly" / str(synthesis.year)
    file_dir.mkdir(parents=True, exist_ok=True)
    file_path = file_dir / f"{synthesis.year}-{synthesis.month:02d}.md"

    file_path.write_text(rendered, encoding="utf-8")
    return file_path


def insert_weekly_backlinks(weekly_path: Path, daily_paths: list[Path]) -> int:
    """Insert backlinks from daily files to their parent weekly summary.

    Idempotent: checks if backlink already exists before inserting.

    Args:
        weekly_path: Path to the weekly summary file.
        daily_paths: List of paths to daily summary files.

    Returns:
        Count of backlinks inserted (0 if all already present).
    """
    inserted = 0

    for daily_path in daily_paths:
        if not daily_path.exists():
            continue

        content = daily_path.read_text(encoding="utf-8")

        # Check if backlink already exists
        if "Part of [Weekly" in content:
            continue

        # Compute relative path from daily file to weekly file
        rel_path = os.path.relpath(weekly_path, daily_path.parent)

        # Get week identifier from weekly filename
        week_name = weekly_path.stem  # e.g., "2026-W14"

        backlink = f"> Part of [Weekly {week_name}]({rel_path})\n\n"
        content = backlink + content
        daily_path.write_text(content, encoding="utf-8")
        inserted += 1

    return inserted
