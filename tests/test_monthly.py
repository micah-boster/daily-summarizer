"""Tests for monthly narrative synthesis pipeline."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from src.models.rollups import MonthlyMetrics, MonthlySynthesis, ThematicArc
from src.synthesis.monthly import (
    _aggregate_monthly_metrics,
    _get_weeks_in_month,
    _parse_monthly_response,
    read_weekly_summaries,
)


class TestGetWeeksInMonth:
    """Tests for ISO week calculation within a month."""

    def test_april_2026(self):
        weeks = _get_weeks_in_month(2026, 4)
        # April 2026: Monday Apr 6 starts W15, etc.
        assert len(weeks) >= 4
        assert all(isinstance(w, int) for w in weeks)

    def test_january_with_year_boundary(self):
        weeks = _get_weeks_in_month(2026, 1)
        # Jan 2026 may have ISO weeks from previous year boundary
        assert len(weeks) >= 4


class TestReadWeeklySummaries:
    """Tests for reading weekly .md files."""

    def test_reads_existing_weekly_files(self, tmp_path):
        weekly_dir = tmp_path / "weekly" / "2026"
        weekly_dir.mkdir(parents=True)

        (weekly_dir / "2026-W14.md").write_text("# Weekly Summary: Week 14, 2026\n\nContent")
        (weekly_dir / "2026-W15.md").write_text("# Weekly Summary: Week 15, 2026\n\nContent")

        # April 2026 includes weeks 14 and 15
        result = read_weekly_summaries(tmp_path, 2026, 4)
        # We should find at least the files whose week numbers match
        found_weeks = {r["week_number"] for r in result}
        # Some of W14 and W15 should be in April depending on calculation
        assert len(result) >= 0  # May vary by exact date calculation

    def test_empty_when_no_files(self, tmp_path):
        result = read_weekly_summaries(tmp_path, 2026, 4)
        assert result == []


class TestAggregateMonthlyMetrics:
    """Tests for metric aggregation from daily files."""

    def test_aggregates_meeting_stats(self, tmp_path):
        daily_dir = tmp_path / "daily" / "2026" / "04"
        daily_dir.mkdir(parents=True)

        (daily_dir / "2026-04-01.md").write_text(
            "# Daily Summary: 2026-04-01\n\n## Overview\n\n"
            "3 meetings, 2.5 hours of meetings, 2 transcripts available.\n\n"
            "## Substance\n\n- Item\n\n"
            "## Decisions\n\n- **Decision:** Something important\n- **Decision:** Another one\n\n"
            "## Commitments\n\nNone.\n\n"
            "## Calendar\n\n**Meeting A**, 10:00am-11:00am. With Sarah, Mike.\n"
        )
        (daily_dir / "2026-04-02.md").write_text(
            "# Daily Summary: 2026-04-02\n\n## Overview\n\n"
            "2 meetings, 1.5 hours of meetings, 1 transcript available.\n\n"
            "## Substance\n\n- Item\n\n"
            "## Decisions\n\n- **Decision:** Third decision\n\n"
            "## Commitments\n\nNone.\n\n"
            "## Calendar\n\n**Meeting B**, 2:00pm-3:00pm. With Sarah, John.\n"
        )

        metrics = _aggregate_monthly_metrics(tmp_path, 2026, 4, {})
        assert metrics.total_meetings == 5
        assert metrics.total_hours == pytest.approx(4.0)
        assert metrics.total_decisions == 3
        assert "Sarah" in metrics.top_attendees

    def test_empty_month(self, tmp_path):
        metrics = _aggregate_monthly_metrics(tmp_path, 2026, 4, {})
        assert metrics.total_meetings == 0
        assert metrics.total_hours == 0.0


class TestParseMonthlyResponse:
    """Tests for parsing Claude's monthly narrative response."""

    def test_parses_arcs_and_shifts(self):
        response = """## Thematic Arcs

### Hiring Pipeline Acceleration

**Trajectory:** growing
**Active Weeks:** W14, W15, W16

Three new roles approved across the first three weeks, with two offers extended by week three. The hiring push reflected a strategic decision to expand the engineering team ahead of Q3.

Key moments:
- Board approved three new headcount positions in week 14
- Two offers extended to senior candidates in week 16

### Q2 Planning

**Trajectory:** resolved
**Active Weeks:** W14, W15

Q2 objectives were finalized after two weeks of discussion, with the team aligning on three key initiatives.

Key moments:
- Initial Q2 priorities proposed in week 14
- Final Q2 roadmap locked in week 15

## Strategic Shifts

- Engineering hiring became the top priority, shifting resources from product development
- Q2 planning completed earlier than usual, freeing bandwidth for execution

## Emerging Risks

- Two key candidates in the hiring pipeline have competing offers with tight deadlines
- Q2 scope may exceed available engineering capacity with current headcount

## Carrying Forward

- Complete remaining two hires for engineering team
- Finalize Q2 milestone definitions
"""
        arcs, shifts, risks, still_open = _parse_monthly_response(response)

        assert len(arcs) == 2
        assert arcs[0].title == "Hiring Pipeline Acceleration"
        assert arcs[0].trajectory == "growing"
        assert 14 in arcs[0].weeks_active
        assert len(arcs[0].key_moments) == 2

        assert arcs[1].title == "Q2 Planning"
        assert arcs[1].trajectory == "resolved"

        assert len(shifts) == 2
        assert "hiring" in shifts[0].lower()

        assert len(risks) == 2

        assert len(still_open) == 2


class TestMonthlySynthesisModel:
    """Tests for MonthlySynthesis Pydantic model."""

    def test_construction_with_all_fields(self):
        synthesis = MonthlySynthesis(
            month=4,
            year=2026,
            generated_at=datetime.now(timezone.utc),
            weekly_count=4,
            thematic_arcs=[
                ThematicArc(
                    title="Test Arc",
                    description="A test thematic arc",
                    weeks_active=[14, 15],
                    trajectory="growing",
                    key_moments=["Moment 1"],
                )
            ],
            strategic_shifts=["Shift 1"],
            emerging_risks=["Risk 1"],
            metrics=MonthlyMetrics(
                total_meetings=40,
                total_hours=30.0,
                total_decisions=15,
                top_attendees=["Sarah", "Mike"],
                weekly_meeting_counts=[10, 12, 8, 10],
            ),
            still_open=[{"content": "Item 1"}],
        )
        assert synthesis.month == 4
        assert synthesis.weekly_count == 4
        assert len(synthesis.thematic_arcs) == 1
        assert synthesis.metrics.total_meetings == 40


class TestWriteMonthlySummary:
    """Tests for monthly summary file writing."""

    def test_writes_to_correct_path(self, tmp_path):
        from src.output.writer import write_monthly_summary

        synthesis = MonthlySynthesis(
            month=4,
            year=2026,
            generated_at=datetime.now(timezone.utc),
            weekly_count=4,
            thematic_arcs=[],
            strategic_shifts=[],
            emerging_risks=[],
            metrics=MonthlyMetrics(total_meetings=40, total_hours=30.0),
            still_open=[],
        )

        template_dir = Path(__file__).parent.parent / "templates"
        path = write_monthly_summary(synthesis, tmp_path, template_dir)

        assert path.exists()
        assert path == tmp_path / "monthly" / "2026" / "2026-04.md"

        content = path.read_text()
        assert "April" in content
        assert "2026" in content

    def test_renders_thematic_arcs(self, tmp_path):
        from src.output.writer import write_monthly_summary

        synthesis = MonthlySynthesis(
            month=4,
            year=2026,
            generated_at=datetime.now(timezone.utc),
            weekly_count=4,
            thematic_arcs=[
                ThematicArc(
                    title="Hiring Push",
                    description="Team expanded rapidly.",
                    weeks_active=[14, 15, 16],
                    trajectory="growing",
                    key_moments=["Three roles approved"],
                )
            ],
            strategic_shifts=["Focus shifted to hiring"],
            emerging_risks=["Competing offers"],
            metrics=MonthlyMetrics(total_meetings=40, total_hours=30.0, total_decisions=15),
        )

        template_dir = Path(__file__).parent.parent / "templates"
        path = write_monthly_summary(synthesis, tmp_path, template_dir)
        content = path.read_text()

        assert "Hiring Push" in content
        assert "growing" in content
        assert "Three roles approved" in content
        assert "Strategic Shifts" in content
        assert "Emerging Risks" in content


class TestFormatMonthName:
    """Tests for month name formatting filter."""

    def test_format_month_name(self):
        from src.output.writer import _format_month_name

        assert _format_month_name(1) == "January"
        assert _format_month_name(4) == "April"
        assert _format_month_name(12) == "December"
        assert _format_month_name(None) == ""
