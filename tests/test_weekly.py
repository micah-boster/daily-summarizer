"""Tests for weekly roll-up pipeline."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from src.models.rollups import ThreadEntry, WeeklySynthesis, WeeklyThread
from src.synthesis.weekly import (
    _extract_synthesis_sections,
    _get_week_date_range,
    _parse_weekly_response,
    read_daily_summaries,
)


class TestGetWeekDateRange:
    """Tests for ISO week date range computation."""

    def test_weekday_returns_mon_fri(self):
        # Wednesday 2026-04-01
        monday, friday = _get_week_date_range(date(2026, 4, 1))
        assert monday == date(2026, 3, 30)  # Monday
        assert friday == date(2026, 4, 3)  # Friday

    def test_monday_returns_same_week(self):
        monday, friday = _get_week_date_range(date(2026, 3, 30))
        assert monday == date(2026, 3, 30)
        assert friday == date(2026, 4, 3)

    def test_friday_returns_same_week(self):
        monday, friday = _get_week_date_range(date(2026, 4, 3))
        assert monday == date(2026, 3, 30)
        assert friday == date(2026, 4, 3)

    def test_saturday_uses_preceding_week(self):
        monday, friday = _get_week_date_range(date(2026, 4, 4))  # Saturday
        assert monday == date(2026, 3, 30)
        assert friday == date(2026, 4, 3)

    def test_sunday_uses_preceding_week(self):
        monday, friday = _get_week_date_range(date(2026, 4, 5))  # Sunday
        assert monday == date(2026, 3, 30)
        assert friday == date(2026, 4, 3)

    def test_year_boundary(self):
        # Thursday Jan 1, 2026 is in ISO week 1
        monday, friday = _get_week_date_range(date(2026, 1, 1))
        assert monday == date(2025, 12, 29)  # Monday of ISO week 1, 2026
        assert friday == date(2026, 1, 2)


class TestExtractSynthesisSections:
    """Tests for daily file section extraction."""

    def test_extracts_substance_decisions_commitments(self):
        content = """# Daily Summary: 2026-04-01

## Overview

3 meetings, 2.5 hours of meetings, 2 transcripts available.

## Substance

- **Item:** Team discussed Q2 roadmap (Team Sync -- Sarah, Mike)

## Decisions

- **Decision:** Delay launch to Q3 | **Who:** Sarah | **Rationale:** API dependency (Product Review -- Sarah)

## Commitments

- **Commitment:** Draft spec by Friday | **Owner:** Mike | **Deadline:** 2026-04-03 | **Status:** created (Team Sync -- Mike)

## Calendar

**Team Sync**, 10:00am-11:00am (1h).
"""
        result = _extract_synthesis_sections(content)
        assert len(result["substance"]) == 1
        assert len(result["decisions"]) == 1
        assert len(result["commitments"]) == 1
        assert "Q2 roadmap" in result["substance"][0]
        assert result["executive_summary"] is None

    def test_extracts_executive_summary(self):
        content = """# Daily Summary: 2026-04-01

## Overview

5 meetings, 4.0 hours.

## Executive Summary

Busy day with major decisions on product direction.

## Substance

- **Item:** Team discussed Q2 roadmap (Sync -- Sarah)

## Decisions

No transcript data available yet.

## Commitments

No transcript data available yet.
"""
        result = _extract_synthesis_sections(content)
        assert result["executive_summary"] == "Busy day with major decisions on product direction."
        assert len(result["substance"]) == 1
        assert result["decisions"] == []
        assert result["commitments"] == []

    def test_empty_sections(self):
        content = """# Daily Summary: 2026-04-01

## Overview

0 meetings, 0.0 hours.

## Substance

No transcript data available yet.

## Decisions

No transcript data available yet.

## Commitments

No transcript data available yet.
"""
        result = _extract_synthesis_sections(content)
        assert result["substance"] == []
        assert result["decisions"] == []
        assert result["commitments"] == []


class TestReadDailySummaries:
    """Tests for reading daily .md files from output directory."""

    def test_reads_existing_files(self, tmp_path):
        # Create mock daily files
        daily_dir = tmp_path / "daily" / "2026" / "04"
        daily_dir.mkdir(parents=True)

        (daily_dir / "2026-04-01.md").write_text(
            "# Daily Summary: 2026-04-01\n\n## Overview\n\n2 meetings.\n\n"
            "## Substance\n\n- Item one\n\n## Decisions\n\nNo transcript data available yet.\n\n"
            "## Commitments\n\nNo transcript data available yet.\n"
        )
        (daily_dir / "2026-04-02.md").write_text(
            "# Daily Summary: 2026-04-02\n\n## Overview\n\n1 meeting.\n\n"
            "## Substance\n\n- Item two\n\n## Decisions\n\n- Decision A\n\n"
            "## Commitments\n\nNo transcript data available yet.\n"
        )

        result = read_daily_summaries(tmp_path, date(2026, 4, 1), date(2026, 4, 3))
        assert len(result) == 2
        assert result[0]["date"] == date(2026, 4, 1)
        assert result[1]["date"] == date(2026, 4, 2)
        assert "Item one" in result[0]["substance"][0]

    def test_skips_missing_dates(self, tmp_path):
        daily_dir = tmp_path / "daily" / "2026" / "04"
        daily_dir.mkdir(parents=True)

        (daily_dir / "2026-04-01.md").write_text(
            "# Daily Summary\n\n## Substance\n\n- Item\n\n"
            "## Decisions\n\nNone.\n\n## Commitments\n\nNone.\n"
        )
        # No file for April 2 or 3

        result = read_daily_summaries(tmp_path, date(2026, 4, 1), date(2026, 4, 3))
        assert len(result) == 1


class TestParseWeeklyResponse:
    """Tests for parsing Claude's thread detection response."""

    def test_parses_threads_and_single_items(self):
        response = """## Thread 1: Q2 Roadmap Planning

**Significance:** high
**Status:** open
**Tags:** decision, substance
**Progression:** Monday: initial discussion -> Wednesday: options narrowed -> Thursday: direction set

- **Monday, March 30** (substance): Team reviewed Q2 priorities
- **Wednesday, April 1** (decision): Narrowed to three key initiatives
- **Thursday, April 2** (decision): Locked in Q2 direction

## Single-Day Items

- **2026-04-01** (commitment): Draft budget proposal by next week

## Still Open

- Budget proposal draft | **Owner:** Mike | **Since:** 2026-04-01 | **Status:** in progress
"""
        summaries = [
            {"date": date(2026, 3, 30), "substance": [], "decisions": [], "commitments": [], "executive_summary": None, "path": Path("/tmp/fake")},
            {"date": date(2026, 4, 1), "substance": [], "decisions": [], "commitments": [], "executive_summary": None, "path": Path("/tmp/fake")},
            {"date": date(2026, 4, 2), "substance": [], "decisions": [], "commitments": [], "executive_summary": None, "path": Path("/tmp/fake")},
        ]

        threads, single_items, still_open = _parse_weekly_response(response, summaries)

        assert len(threads) == 1
        assert threads[0].title == "Q2 Roadmap Planning"
        assert threads[0].significance == "high"
        assert threads[0].status == "open"
        assert len(threads[0].entries) == 3
        assert "decision" in threads[0].tags

        assert len(single_items) == 1
        assert "budget" in single_items[0].content.lower()

        assert len(still_open) == 1
        assert "Budget" in still_open[0]["content"]


class TestWeeklySynthesisModel:
    """Tests for WeeklySynthesis Pydantic model."""

    def test_construction_with_all_fields(self):
        synthesis = WeeklySynthesis(
            week_number=14,
            year=2026,
            start_date=date(2026, 3, 30),
            end_date=date(2026, 4, 3),
            generated_at=datetime.now(timezone.utc),
            daily_count=5,
            is_partial=False,
            meeting_count=15,
            total_meeting_hours=12.5,
            threads=[
                WeeklyThread(
                    title="Test Thread",
                    significance="high",
                    entries=[
                        ThreadEntry(
                            date=date(2026, 3, 30),
                            content="Test entry",
                            category="decision",
                        )
                    ],
                    progression="start -> end",
                    status="resolved",
                    tags=["decision"],
                )
            ],
            single_day_items=[],
            still_open=[],
            daily_dates=[date(2026, 3, 30)],
        )
        assert synthesis.week_number == 14
        assert synthesis.is_partial is False
        assert len(synthesis.threads) == 1

    def test_partial_week(self):
        synthesis = WeeklySynthesis(
            week_number=14,
            year=2026,
            start_date=date(2026, 3, 30),
            end_date=date(2026, 4, 3),
            generated_at=datetime.now(timezone.utc),
            daily_count=3,
            is_partial=True,
            meeting_count=8,
            total_meeting_hours=6.0,
        )
        assert synthesis.is_partial is True
        assert synthesis.daily_count == 3


class TestWriteWeeklySummary:
    """Tests for weekly summary file writing."""

    def test_writes_to_correct_path(self, tmp_path):
        from src.output.writer import write_weekly_summary

        synthesis = WeeklySynthesis(
            week_number=14,
            year=2026,
            start_date=date(2026, 3, 30),
            end_date=date(2026, 4, 3),
            generated_at=datetime.now(timezone.utc),
            daily_count=5,
            is_partial=False,
            meeting_count=10,
            total_meeting_hours=8.0,
            threads=[],
            single_day_items=[],
            still_open=[],
        )

        template_dir = Path(__file__).parent.parent / "templates"
        path = write_weekly_summary(synthesis, tmp_path, template_dir)

        assert path.exists()
        assert path == tmp_path / "weekly" / "2026" / "2026-W14.md"

        content = path.read_text()
        assert "Week 14" in content
        assert "2026" in content

    def test_partial_week_annotation(self, tmp_path):
        from src.output.writer import write_weekly_summary

        synthesis = WeeklySynthesis(
            week_number=14,
            year=2026,
            start_date=date(2026, 3, 30),
            end_date=date(2026, 4, 3),
            generated_at=datetime.now(timezone.utc),
            daily_count=3,
            is_partial=True,
            meeting_count=5,
            total_meeting_hours=4.0,
        )

        template_dir = Path(__file__).parent.parent / "templates"
        path = write_weekly_summary(synthesis, tmp_path, template_dir)

        content = path.read_text()
        assert "Partial week" in content
        assert "3 of 5" in content


class TestInsertWeeklyBacklinks:
    """Tests for idempotent backlink insertion."""

    def test_inserts_backlinks(self, tmp_path):
        from src.output.writer import insert_weekly_backlinks

        weekly_path = tmp_path / "weekly" / "2026" / "2026-W14.md"
        weekly_path.parent.mkdir(parents=True)
        weekly_path.write_text("# Weekly Summary")

        daily_dir = tmp_path / "daily" / "2026" / "03"
        daily_dir.mkdir(parents=True)
        daily_path = daily_dir / "2026-03-30.md"
        daily_path.write_text("# Daily Summary: 2026-03-30\n\nContent here.")

        count = insert_weekly_backlinks(weekly_path, [daily_path])
        assert count == 1

        content = daily_path.read_text()
        assert "Part of [Weekly 2026-W14]" in content

    def test_idempotent(self, tmp_path):
        from src.output.writer import insert_weekly_backlinks

        weekly_path = tmp_path / "weekly" / "2026" / "2026-W14.md"
        weekly_path.parent.mkdir(parents=True)
        weekly_path.write_text("# Weekly Summary")

        daily_dir = tmp_path / "daily" / "2026" / "03"
        daily_dir.mkdir(parents=True)
        daily_path = daily_dir / "2026-03-30.md"
        daily_path.write_text("# Daily Summary: 2026-03-30\n\nContent here.")

        insert_weekly_backlinks(weekly_path, [daily_path])
        count2 = insert_weekly_backlinks(weekly_path, [daily_path])
        assert count2 == 0  # No new insertions

        content = daily_path.read_text()
        assert content.count("Part of [Weekly") == 1
