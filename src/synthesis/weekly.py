"""Weekly roll-up pipeline: thread detection across daily summaries.

Reads accumulated daily summary .md files for a week, uses Claude
to detect semantic threads across days, and produces a structured
WeeklySynthesis with threads, single-day items, and still-open tracking.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import anthropic

from src.config import PipelineConfig
from src.schema_utils import prepare_schema_for_claude
from src.models.rollups import ThreadEntry, WeeklySynthesis, WeeklyThread
from src.synthesis.models import WeeklySynthesisOutput
from src.synthesis.prompts import WEEKLY_THREAD_DETECTION_PROMPT
from src.retry import retry_api_call
from src.synthesis.validator import validate_evidence_only

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_MAX_OUTPUT_TOKENS = 8192


@retry_api_call
def _call_claude_structured_with_retry(client, model, max_tokens, prompt, schema):
    """Call Claude API with structured output and retry on transient errors."""
    return client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
        tools=[{"name": "output", "description": "Structured output", "input_schema": schema}],
        tool_choice={"type": "tool", "name": "output"},
    )


def _get_week_date_range(target_date: date) -> tuple[date, date]:
    """Compute the Monday-Friday range for the ISO week containing target_date.

    If target_date is Saturday or Sunday, uses the preceding week.

    Args:
        target_date: Any date within the desired week.

    Returns:
        Tuple of (monday, friday) for the ISO week.
    """
    # If weekend, go back to the preceding Friday's week
    if target_date.weekday() == 5:  # Saturday
        target_date = target_date - timedelta(days=1)
    elif target_date.weekday() == 6:  # Sunday
        target_date = target_date - timedelta(days=2)

    # Monday of the week
    monday = target_date - timedelta(days=target_date.weekday())
    friday = monday + timedelta(days=4)
    return monday, friday


def _extract_synthesis_sections(content: str) -> dict:
    """Extract only synthesis sections from a daily .md file.

    Extracts: Executive Summary, Substance, Decisions, Commitments.
    Strips: Calendar, Per-Meeting Extractions, Declined, Cancelled,
    Meetings Without Transcripts, Overview.

    Args:
        content: Full content of a daily .md file.

    Returns:
        Dict with keys: executive_summary (str|None), substance (list[str]),
        decisions (list[str]), commitments (list[str]).
    """
    result: dict = {
        "executive_summary": None,
        "substance": [],
        "decisions": [],
        "commitments": [],
    }

    # Split by ## headers
    sections: dict[str, str] = {}
    current_section = ""
    current_content: list[str] = []

    for line in content.split("\n"):
        if line.startswith("## "):
            if current_section:
                sections[current_section] = "\n".join(current_content).strip()
            current_section = line[3:].strip().lower()
            current_content = []
        else:
            current_content.append(line)

    if current_section:
        sections[current_section] = "\n".join(current_content).strip()

    # Extract executive summary
    if "executive summary" in sections:
        summary = sections["executive summary"].strip()
        if summary and summary.lower() not in ("", "no items for this day."):
            result["executive_summary"] = summary

    # Extract bullet items from synthesis sections
    for section_key, result_key in [
        ("substance", "substance"),
        ("decisions", "decisions"),
        ("commitments", "commitments"),
    ]:
        section_text = sections.get(section_key, "")
        if not section_text or "no transcript data" in section_text.lower():
            continue

        items: list[str] = []
        current_item_lines: list[str] = []

        for line in section_text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("- "):
                if current_item_lines:
                    items.append(" ".join(current_item_lines))
                current_item_lines = [stripped[2:]]
            elif stripped and current_item_lines:
                current_item_lines.append(stripped)

        if current_item_lines:
            items.append(" ".join(current_item_lines))

        result[result_key] = items

    return result


def read_daily_summaries(output_dir: Path, start: date, end: date) -> list[dict]:
    """Read rendered daily .md files and extract synthesis sections.

    Args:
        output_dir: Base output directory (e.g., Path("output")).
        start: First date to include (typically Monday).
        end: Last date to include (typically Friday).

    Returns:
        List of dicts with keys: date, executive_summary (str|None),
        substance (list[str]), decisions (list[str]), commitments (list[str]),
        path (Path).
    """
    summaries: list[dict] = []
    current = start

    while current <= end:
        path = (
            output_dir
            / "daily"
            / str(current.year)
            / f"{current.month:02d}"
            / f"{current.isoformat()}.md"
        )
        if path.exists():
            content = path.read_text(encoding="utf-8")
            sections = _extract_synthesis_sections(content)
            summaries.append(
                {
                    "date": current,
                    "executive_summary": sections["executive_summary"],
                    "substance": sections["substance"],
                    "decisions": sections["decisions"],
                    "commitments": sections["commitments"],
                    "path": path,
                }
            )
        current += timedelta(days=1)

    return summaries


def _build_thread_detection_prompt(summaries: list[dict]) -> str:
    """Format daily synthesis content into a thread detection prompt.

    Args:
        summaries: List of daily summary dicts from read_daily_summaries.

    Returns:
        Complete prompt string for Claude thread detection.
    """
    daily_blocks: list[str] = []

    for s in summaries:
        lines: list[str] = [f"### {s['date'].strftime('%A, %B %d')}"]

        if s["executive_summary"]:
            lines.append(f"\n**Executive Summary:** {s['executive_summary']}")

        if s["decisions"]:
            lines.append("\n**Decisions:**")
            for item in s["decisions"]:
                lines.append(f"- {item}")

        if s["commitments"]:
            lines.append("\n**Commitments:**")
            for item in s["commitments"]:
                lines.append(f"- {item}")

        if s["substance"]:
            lines.append("\n**Substance:**")
            for item in s["substance"]:
                lines.append(f"- {item}")

        daily_blocks.append("\n".join(lines))

    daily_content = "\n\n---\n\n".join(daily_blocks)
    date_range = f"{summaries[0]['date'].isoformat()} to {summaries[-1]['date'].isoformat()}"

    return WEEKLY_THREAD_DETECTION_PROMPT.format(
        date_range=date_range,
        daily_count=len(summaries),
        daily_content=daily_content,
    )


def _resolve_date_from_label(day_label: str, summaries: list[dict]) -> date | None:
    """Resolve a day label (e.g. 'Monday, March 30') to a date using summaries.

    Args:
        day_label: Day label string from structured output.
        summaries: List of daily summary dicts with 'date' keys.

    Returns:
        Resolved date, or first summary date as fallback, or None.
    """
    for s in summaries:
        summary_date = s["date"]
        # Match by formatted day name with zero-padded and non-padded day
        # strftime %d is zero-padded; also check non-padded via %-d (platform-dependent)
        formatted_padded = summary_date.strftime("%A, %B %d")
        formatted_unpadded = summary_date.strftime("%A, %B ") + str(summary_date.day)
        if day_label in formatted_padded or day_label in formatted_unpadded:
            return summary_date
        # Also check if the formatted string is a substring of the label
        if formatted_padded in day_label or formatted_unpadded in day_label:
            return summary_date
        # Match by ISO date string
        if day_label == summary_date.isoformat():
            return summary_date
    # Fallback to first summary date
    if summaries:
        return summaries[0]["date"]
    return None


def _convert_weekly_output(
    output: WeeklySynthesisOutput, summaries: list[dict]
) -> tuple[list[WeeklyThread], list[ThreadEntry], list[dict]]:
    """Convert structured output to domain models.

    Args:
        output: Validated WeeklySynthesisOutput from Claude.
        summaries: Original daily summaries (for date resolution).

    Returns:
        Tuple of (threads, single_day_items, still_open).
    """
    threads: list[WeeklyThread] = []
    for t in output.threads:
        entries: list[ThreadEntry] = []
        for e in t.entries:
            entry_date = _resolve_date_from_label(e.day_label, summaries)
            if entry_date and e.content:
                entries.append(
                    ThreadEntry(date=entry_date, content=e.content, category=e.category)
                )
        threads.append(
            WeeklyThread(
                title=t.title,
                significance=t.significance,
                entries=entries,
                progression=t.progression,
                status=t.status,
                tags=t.tags,
            )
        )

    single_day_items: list[ThreadEntry] = []
    for item in output.single_day_items:
        entry_date = _resolve_date_from_label(item.day_label, summaries)
        if entry_date and item.content:
            single_day_items.append(
                ThreadEntry(date=entry_date, content=item.content, category=item.category)
            )

    still_open: list[dict] = []
    for item in output.still_open:
        d: dict = {"content": item.content}
        if item.owner is not None:
            d["owner"] = item.owner
        if item.since is not None:
            d["since"] = item.since
        still_open.append(d)

    return threads, single_day_items, still_open


def synthesize_weekly(
    target_date: date,
    config: PipelineConfig,
    output_dir: Path,
    client: anthropic.Anthropic | None = None,
) -> WeeklySynthesis:
    """Produce weekly synthesis from accumulated daily summaries.

    Main entry point for the weekly pipeline. Reads daily files,
    detects threads via Claude, and returns structured WeeklySynthesis.

    Args:
        target_date: Any date within the target week.
        config: Pipeline configuration dict.
        output_dir: Base output directory.

    Returns:
        WeeklySynthesis model populated from Claude's analysis.
    """
    monday, friday = _get_week_date_range(target_date)
    iso_cal = monday.isocalendar()
    week_number = iso_cal[1]
    year = iso_cal[0]

    logger.info("Synthesizing weekly for %d-W%02d (%s to %s)", year, week_number, monday, friday)

    # Read daily summaries
    summaries = read_daily_summaries(output_dir, monday, friday)

    if not summaries:
        logger.info("No daily summaries found for week %d-W%02d", year, week_number)
        return WeeklySynthesis(
            week_number=week_number,
            year=year,
            start_date=monday,
            end_date=friday,
            generated_at=datetime.now(timezone.utc),
            daily_count=0,
            is_partial=True,
            meeting_count=0,
            total_meeting_hours=0.0,
        )

    daily_count = len(summaries)
    is_partial = daily_count < 5

    # Aggregate meeting stats from daily files
    total_meetings = 0
    total_hours = 0.0
    for s in summaries:
        # Re-read the file to get overview stats
        if s["path"].exists():
            content = s["path"].read_text(encoding="utf-8")
            meetings_match = re.search(r"(\d+)\s+meetings?", content)
            hours_match = re.search(r"([\d.]+)\s+hours", content)
            if meetings_match:
                total_meetings += int(meetings_match.group(1))
            if hours_match:
                total_hours += float(hours_match.group(1))

    # Build prompt and call Claude
    prompt = _build_thread_detection_prompt(summaries)

    model = config.synthesis.model
    max_tokens = config.synthesis.weekly_max_output_tokens

    client = client or anthropic.Anthropic()
    schema = prepare_schema_for_claude(WeeklySynthesisOutput.model_json_schema())
    response = _call_claude_structured_with_retry(client, model, max_tokens, prompt, schema)
    data = response.content[0].input
    output = WeeklySynthesisOutput.model_validate(data)

    # Convert structured output to domain models
    threads, single_day_items, still_open = _convert_weekly_output(output, summaries)

    logger.info(
        "Weekly %d-W%02d: %d threads, %d single-day items, %d still open",
        year,
        week_number,
        len(threads),
        len(single_day_items),
        len(still_open),
    )

    return WeeklySynthesis(
        week_number=week_number,
        year=year,
        start_date=monday,
        end_date=friday,
        generated_at=datetime.now(timezone.utc),
        daily_count=daily_count,
        is_partial=is_partial,
        meeting_count=total_meetings,
        total_meeting_hours=total_hours,
        threads=threads,
        single_day_items=single_day_items,
        still_open=still_open,
        daily_dates=[s["date"] for s in summaries],
    )
