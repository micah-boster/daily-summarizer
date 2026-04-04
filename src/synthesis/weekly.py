"""Weekly roll-up pipeline: thread detection across daily summaries.

Reads accumulated daily summary .md files for a week, uses Claude
to detect semantic threads across days, and produces a structured
WeeklySynthesis with threads, single-day items, and still-open tracking.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import anthropic

from src.models.rollups import ThreadEntry, WeeklySynthesis, WeeklyThread
from src.synthesis.prompts import WEEKLY_THREAD_DETECTION_PROMPT
from src.synthesis.validator import validate_evidence_only

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_MAX_OUTPUT_TOKENS = 8192


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


def _parse_weekly_response(
    response_text: str, summaries: list[dict]
) -> tuple[list[WeeklyThread], list[ThreadEntry], list[dict]]:
    """Parse Claude's thread detection response into structured models.

    Args:
        response_text: Claude's full response text.
        summaries: Original daily summaries (for date reference).

    Returns:
        Tuple of (threads, single_day_items, still_open).
    """
    threads: list[WeeklyThread] = []
    single_day_items: list[ThreadEntry] = []
    still_open: list[dict] = []

    # Split by ## headers
    sections: dict[str, str] = {}
    current_section = ""
    current_content: list[str] = []

    for line in response_text.split("\n"):
        if line.startswith("## "):
            if current_section:
                sections[current_section] = "\n".join(current_content).strip()
            current_section = line[3:].strip()
            current_content = []
        else:
            current_content.append(line)

    if current_section:
        sections[current_section] = "\n".join(current_content).strip()

    # Parse thread sections (## Thread: Title or ## Thread N: Title)
    for section_name, section_text in sections.items():
        if section_name.lower().startswith("thread"):
            thread = _parse_thread_section(section_name, section_text, summaries)
            if thread:
                threads.append(thread)

    # Parse single-day items
    for section_name, section_text in sections.items():
        if "single" in section_name.lower() and "item" in section_name.lower():
            single_day_items = _parse_single_day_items(section_text)

    # Parse still open
    for section_name, section_text in sections.items():
        if "still open" in section_name.lower() or "open" == section_name.lower():
            still_open = _parse_still_open(section_text)

    return threads, single_day_items, still_open


def _parse_thread_section(
    section_name: str, section_text: str, summaries: list[dict]
) -> WeeklyThread | None:
    """Parse a single thread section into a WeeklyThread model."""
    # Extract title from section name: "Thread 1: Title" or "Thread: Title"
    title_match = re.match(r"Thread(?:\s+\d+)?:\s*(.*)", section_name, re.IGNORECASE)
    title = title_match.group(1).strip() if title_match else section_name

    if not title or not section_text.strip():
        return None

    # Parse fields
    significance = "medium"
    status = "open"
    progression = ""
    tags: list[str] = []
    entries: list[ThreadEntry] = []

    for line in section_text.split("\n"):
        stripped = line.strip()

        if stripped.lower().startswith("**significance:**"):
            val = stripped.split(":", 1)[1].strip().strip("*").strip().lower()
            if val in ("high", "medium"):
                significance = val

        elif stripped.lower().startswith("**status:**"):
            val = stripped.split(":", 1)[1].strip().strip("*").strip().lower()
            if val in ("resolved", "open", "escalated"):
                status = val

        elif stripped.lower().startswith("**progression:**"):
            progression = stripped.split(":", 1)[1].strip().strip("*").strip()

        elif stripped.lower().startswith("**tags:**"):
            tags_str = stripped.split(":", 1)[1].strip().strip("*").strip()
            tags = [t.strip() for t in tags_str.split(",") if t.strip()]

        elif stripped.startswith("- **") and "):" in stripped:
            # Entry: "- **Monday, April 3** (decision): Content here"
            entry = _parse_thread_entry(stripped, summaries)
            if entry:
                entries.append(entry)

    return WeeklyThread(
        title=title,
        significance=significance,
        entries=entries,
        progression=progression,
        status=status,
        tags=tags,
    )


def _parse_thread_entry(line: str, summaries: list[dict]) -> ThreadEntry | None:
    """Parse a single thread entry line into a ThreadEntry model."""
    # Pattern: "- **DayName, Month Day** (category): content"
    # or: "- **YYYY-MM-DD** (category): content"
    match = re.match(
        r"-\s+\*\*([^*]+)\*\*\s*\((\w+)\)\s*:\s*(.*)", line.strip()
    )
    if not match:
        return None

    date_str = match.group(1).strip()
    category = match.group(2).strip().lower()
    content = match.group(3).strip()

    # Try to resolve date from summaries
    entry_date = None
    for s in summaries:
        # Match by formatted day name or ISO date
        if date_str in s["date"].strftime("%A, %B %d") or date_str == s["date"].isoformat():
            entry_date = s["date"]
            break

    if entry_date is None and summaries:
        entry_date = summaries[0]["date"]  # Fallback

    if entry_date and content:
        return ThreadEntry(date=entry_date, content=content, category=category)
    return None


def _parse_single_day_items(section_text: str) -> list[ThreadEntry]:
    """Parse single-day items section into ThreadEntry list."""
    items: list[ThreadEntry] = []

    for line in section_text.split("\n"):
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue

        # Pattern: "- **YYYY-MM-DD** (category): content" or "- (category): content"
        match = re.match(
            r"-\s+(?:\*\*([^*]+)\*\*\s*)?\((\w+)\)\s*:\s*(.*)", stripped
        )
        if match:
            date_str = match.group(1)
            category = match.group(2).strip().lower()
            content = match.group(3).strip()
            try:
                entry_date = date.fromisoformat(date_str) if date_str else date.today()
            except (ValueError, TypeError):
                entry_date = date.today()
            if content:
                items.append(
                    ThreadEntry(date=entry_date, content=content, category=category)
                )

    return items


def _parse_still_open(section_text: str) -> list[dict]:
    """Parse still-open section into list of dicts."""
    items: list[dict] = []

    for line in section_text.split("\n"):
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue

        # Simple parsing: each bullet is an open item
        content = stripped[2:].strip()
        if content and content.lower() != "none":
            item: dict = {"content": content}

            # Try to extract owner/date from content
            owner_match = re.search(r"\*\*Owner:\*\*\s*([^|]+)", content)
            if owner_match:
                item["owner"] = owner_match.group(1).strip()

            date_match = re.search(r"\*\*Since:\*\*\s*(\d{4}-\d{2}-\d{2})", content)
            if date_match:
                item["since"] = date_match.group(1)

            items.append(item)

    return items


def synthesize_weekly(
    target_date: date,
    config: dict,
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

    synthesis_config = config.get("synthesis", {})
    model = synthesis_config.get("model", DEFAULT_MODEL)
    max_tokens = synthesis_config.get("weekly_max_output_tokens", DEFAULT_MAX_OUTPUT_TOKENS)

    client = client or anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    response_text = response.content[0].text

    # Validate evidence-only language
    violations = validate_evidence_only(response_text)
    if violations:
        logger.warning(
            "Weekly synthesis contains %d evaluative language violation(s):",
            len(violations),
        )
        for v in violations[:5]:
            logger.warning("  [%s] '%s' in: ...%s...", v.pattern, v.text, v.context)

    # Parse response
    threads, single_day_items, still_open = _parse_weekly_response(response_text, summaries)

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
