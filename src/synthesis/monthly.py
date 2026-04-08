"""Monthly narrative synthesis pipeline: thematic analysis from weekly summaries.

Reads accumulated weekly summary .md files for a month, uses Claude
to identify thematic arcs and strategic patterns, and produces a
structured MonthlySynthesis with arcs, shifts, risks, and metrics.
"""

from __future__ import annotations

import calendar
import json
import logging
import re
from datetime import date, datetime, timezone
from pathlib import Path

import anthropic

from src.config import PipelineConfig
from src.schema_utils import prepare_schema_for_claude
from src.models.rollups import MonthlyMetrics, MonthlySynthesis, ThematicArc
from src.synthesis.models import MonthlySynthesisOutput
from src.synthesis.prompts import MONTHLY_NARRATIVE_PROMPT
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


def _get_weeks_in_month(year: int, month: int) -> list[int]:
    """Get ISO week numbers that fall within a given month.

    A week belongs to a month if its Monday is in that month.

    Args:
        year: Target year.
        month: Target month (1-12).

    Returns:
        Sorted list of ISO week numbers for the month.
    """
    weeks: set[int] = set()
    _, days_in_month = calendar.monthrange(year, month)

    for day in range(1, days_in_month + 1):
        d = date(year, month, day)
        # Only count the week if the Monday of that week is in this month
        monday = d - __import__("datetime").timedelta(days=d.weekday())
        if monday.month == month:
            weeks.add(d.isocalendar()[1])

    return sorted(weeks)


def read_weekly_summaries(
    output_dir: Path, year: int, month: int
) -> list[dict]:
    """Read rendered weekly .md files for a given month.

    Args:
        output_dir: Base output directory.
        year: Target year.
        month: Target month (1-12).

    Returns:
        List of dicts with keys: week_number (int), year (int),
        content (str), path (Path).
    """
    weeks = _get_weeks_in_month(year, month)
    summaries: list[dict] = []

    for week_num in weeks:
        # Weekly files may span year boundaries at edges
        for check_year in [year - 1, year, year + 1]:
            path = output_dir / "weekly" / str(check_year) / f"{check_year}-W{week_num:02d}.md"
            if path.exists():
                content = path.read_text(encoding="utf-8")
                summaries.append(
                    {
                        "week_number": week_num,
                        "year": check_year,
                        "content": content,
                        "path": path,
                    }
                )
                break  # Found the file, no need to check other years

    return summaries


def _aggregate_monthly_metrics(
    output_dir: Path, year: int, month: int, config: PipelineConfig
) -> MonthlyMetrics:
    """Aggregate meeting metrics from daily files for a month.

    Args:
        output_dir: Base output directory.
        year: Target year.
        month: Target month (1-12).
        config: Pipeline config (unused currently, reserved).

    Returns:
        MonthlyMetrics with totals computed from daily files.
    """
    _, days_in_month = calendar.monthrange(year, month)
    total_meetings = 0
    total_hours = 0.0
    total_decisions = 0
    attendee_counts: dict[str, int] = {}
    weekly_meetings: dict[int, int] = {}

    for day in range(1, days_in_month + 1):
        d = date(year, month, day)
        path = output_dir / "daily" / str(year) / f"{month:02d}" / f"{d.isoformat()}.md"

        if not path.exists():
            continue

        content = path.read_text(encoding="utf-8")

        # Parse overview line: "N meetings, X.X hours of meetings, M transcripts"
        meetings_match = re.search(r"(\d+)\s+meetings?", content)
        hours_match = re.search(r"([\d.]+)\s+hours", content)
        if meetings_match:
            day_meetings = int(meetings_match.group(1))
            total_meetings += day_meetings
            # Track weekly
            week_num = d.isocalendar()[1]
            weekly_meetings[week_num] = weekly_meetings.get(week_num, 0) + day_meetings
        if hours_match:
            total_hours += float(hours_match.group(1))

        # Count decision items
        in_decisions = False
        for line in content.split("\n"):
            if line.startswith("## Decisions"):
                in_decisions = True
                continue
            if line.startswith("## ") and in_decisions:
                in_decisions = False
            if in_decisions and line.strip().startswith("- **"):
                total_decisions += 1

        # Extract attendees from calendar section
        in_calendar = False
        for line in content.split("\n"):
            if line.startswith("## Calendar"):
                in_calendar = True
                continue
            if line.startswith("## ") and in_calendar:
                in_calendar = False
            if in_calendar and "With " in line:
                # Extract names after "With "
                with_match = re.search(r"With\s+(.+?)(?:\.|$)", line)
                if with_match:
                    names = [n.strip() for n in with_match.group(1).split(",")]
                    for name in names:
                        if name:
                            attendee_counts[name] = attendee_counts.get(name, 0) + 1

    # Get top 5 attendees by frequency
    sorted_attendees = sorted(attendee_counts.items(), key=lambda x: x[1], reverse=True)
    top_attendees = [name for name, _ in sorted_attendees[:5]]

    # Build weekly meeting counts in order
    sorted_weeks = sorted(weekly_meetings.keys())
    weekly_meeting_counts = [weekly_meetings[w] for w in sorted_weeks]

    return MonthlyMetrics(
        total_meetings=total_meetings,
        total_hours=total_hours,
        total_decisions=total_decisions,
        top_attendees=top_attendees,
        weekly_meeting_counts=weekly_meeting_counts,
    )


def _build_monthly_narrative_prompt(
    weeklies: list[dict], metrics: MonthlyMetrics, year: int, month: int
) -> str:
    """Format weekly content and metrics into a monthly narrative prompt.

    Args:
        weeklies: List of weekly summary dicts.
        metrics: Aggregated monthly metrics.
        year: Target year.
        month: Target month.

    Returns:
        Complete prompt string for Claude narrative synthesis.
    """
    weekly_blocks: list[str] = []
    for w in weeklies:
        weekly_blocks.append(
            f"### Week {w['week_number']}\n\n{w['content']}"
        )

    weekly_content = "\n\n---\n\n".join(weekly_blocks)
    month_name = calendar.month_name[month]

    return MONTHLY_NARRATIVE_PROMPT.format(
        month_name=month_name,
        year=year,
        weekly_count=len(weeklies),
        total_meetings=metrics.total_meetings,
        total_hours=metrics.total_hours,
        total_decisions=metrics.total_decisions,
        top_attendees=", ".join(metrics.top_attendees) if metrics.top_attendees else "N/A",
        weekly_content=weekly_content,
    )


def _convert_monthly_output(
    output: MonthlySynthesisOutput,
) -> tuple[list[ThematicArc], list[str], list[str], list[dict]]:
    """Convert structured output to domain models.

    Args:
        output: Validated MonthlySynthesisOutput from Claude.

    Returns:
        Tuple of (thematic_arcs, strategic_shifts, emerging_risks, still_open).
    """
    arcs: list[ThematicArc] = []
    for a in output.thematic_arcs:
        arcs.append(
            ThematicArc(
                title=a.title,
                trajectory=a.trajectory,
                weeks_active=a.weeks_active,
                description=a.description,
                key_moments=a.key_moments,
            )
        )

    strategic_shifts = list(output.strategic_shifts)
    emerging_risks = list(output.emerging_risks)

    still_open: list[dict] = []
    for item in output.still_open:
        d: dict = {"content": item.content}
        if item.owner is not None:
            d["owner"] = item.owner
        if item.since is not None:
            d["since"] = item.since
        still_open.append(d)

    return arcs, strategic_shifts, emerging_risks, still_open


def synthesize_monthly(
    year: int,
    month: int,
    config: PipelineConfig,
    output_dir: Path,
    client: anthropic.Anthropic | None = None,
) -> MonthlySynthesis:
    """Produce monthly synthesis from accumulated weekly summaries.

    Main entry point for the monthly pipeline. Reads weekly files,
    aggregates metrics, synthesizes narrative via Claude, and returns
    structured MonthlySynthesis.

    Args:
        year: Target year.
        month: Target month (1-12).
        config: Pipeline configuration dict.
        output_dir: Base output directory.

    Returns:
        MonthlySynthesis model populated from Claude's analysis.
    """
    month_name = calendar.month_name[month]
    logger.info("Synthesizing monthly for %s %d", month_name, year)

    # Read weekly summaries
    weeklies = read_weekly_summaries(output_dir, year, month)

    # Aggregate metrics from daily files
    metrics = _aggregate_monthly_metrics(output_dir, year, month, config)

    if not weeklies:
        logger.info("No weekly summaries found for %s %d", month_name, year)
        return MonthlySynthesis(
            month=month,
            year=year,
            generated_at=datetime.now(timezone.utc),
            weekly_count=0,
            metrics=metrics,
        )

    # Build prompt and call Claude
    prompt = _build_monthly_narrative_prompt(weeklies, metrics, year, month)

    model = config.synthesis.model
    max_tokens = config.synthesis.monthly_max_output_tokens

    client = client or anthropic.Anthropic()
    schema = prepare_schema_for_claude(MonthlySynthesisOutput.model_json_schema())
    response = _call_claude_structured_with_retry(client, model, max_tokens, prompt, schema)
    data = response.content[0].input
    output = MonthlySynthesisOutput.model_validate(data)

    # Convert structured output to domain models
    arcs, strategic_shifts, emerging_risks, still_open = _convert_monthly_output(output)

    logger.info(
        "Monthly %s %d: %d arcs, %d shifts, %d risks",
        month_name,
        year,
        len(arcs),
        len(strategic_shifts),
        len(emerging_risks),
    )

    return MonthlySynthesis(
        month=month,
        year=year,
        generated_at=datetime.now(timezone.utc),
        weekly_count=len(weeklies),
        thematic_arcs=arcs,
        strategic_shifts=strategic_shifts,
        emerging_risks=emerging_risks,
        metrics=metrics,
        still_open=still_open,
    )
