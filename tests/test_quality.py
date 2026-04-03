"""Tests for diff-based quality metrics tracking."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from src.quality import detect_edits, save_raw_output, update_quality_report


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """Create a temporary output directory structure."""
    return tmp_path / "output"


class TestSaveRawOutput:
    def test_creates_file_at_correct_path(self, output_dir: Path):
        target = date(2026, 4, 3)
        content = "# Daily Summary\n\nSome content here."
        path = save_raw_output(content, target, output_dir)

        assert path.exists()
        assert path == output_dir / "raw" / "daily" / "2026" / "04" / "2026-04-03.raw.md"
        assert path.read_text() == content

    def test_creates_directories(self, output_dir: Path):
        target = date(2026, 1, 15)
        save_raw_output("content", target, output_dir)

        assert (output_dir / "raw" / "daily" / "2026" / "01").is_dir()

    def test_overwrites_existing(self, output_dir: Path):
        target = date(2026, 4, 3)
        save_raw_output("first version", target, output_dir)
        save_raw_output("second version", target, output_dir)

        path = output_dir / "raw" / "daily" / "2026" / "04" / "2026-04-03.raw.md"
        assert path.read_text() == "second version"


class TestDetectEdits:
    def _setup_files(self, output_dir: Path, target: date, raw: str, current: str):
        """Helper to create both raw and current files."""
        d = target
        raw_dir = output_dir / "raw" / "daily" / str(d.year) / f"{d.month:02d}"
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / f"{d.isoformat()}.raw.md").write_text(raw)

        cur_dir = output_dir / "daily" / str(d.year) / f"{d.month:02d}"
        cur_dir.mkdir(parents=True, exist_ok=True)
        (cur_dir / f"{d.isoformat()}.md").write_text(current)

    def test_identical_files_no_edit(self, output_dir: Path):
        target = date(2026, 4, 3)
        content = "# Summary\n\n## Substance\n- Item 1\n"
        self._setup_files(output_dir, target, content, content)

        result = detect_edits(target, output_dir)
        assert result is not None
        assert result["edited"] is False
        assert result["similarity"] == 1.0
        assert result["sections_changed"] == []
        assert result["additions"] == 0
        assert result["deletions"] == 0

    def test_modified_section_detected(self, output_dir: Path):
        target = date(2026, 4, 3)
        raw = "# Summary\n\n## Substance\n- Item 1\n\n## Commitments\n- Task A\n"
        current = "# Summary\n\n## Substance\n- Item 1\n\n## Commitments\n- Task A (updated)\n- Task B\n"
        self._setup_files(output_dir, target, raw, current)

        result = detect_edits(target, output_dir)
        assert result is not None
        assert result["edited"] is True
        assert result["similarity"] < 1.0
        assert "Commitments" in result["sections_changed"]

    def test_missing_raw_returns_none(self, output_dir: Path):
        target = date(2026, 4, 3)
        # Only create current file, not raw
        cur_dir = output_dir / "daily" / "2026" / "04"
        cur_dir.mkdir(parents=True, exist_ok=True)
        (cur_dir / "2026-04-03.md").write_text("content")

        result = detect_edits(target, output_dir)
        assert result is None

    def test_missing_current_returns_none(self, output_dir: Path):
        target = date(2026, 4, 3)
        # Only create raw file, not current
        raw_dir = output_dir / "raw" / "daily" / "2026" / "04"
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / "2026-04-03.raw.md").write_text("content")

        result = detect_edits(target, output_dir)
        assert result is None

    def test_date_in_result(self, output_dir: Path):
        target = date(2026, 4, 3)
        self._setup_files(output_dir, target, "a", "a")

        result = detect_edits(target, output_dir)
        assert result["date"] == "2026-04-03"

    def test_additions_and_deletions_counted(self, output_dir: Path):
        target = date(2026, 4, 3)
        raw = "line1\nline2\nline3\n"
        current = "line1\nmodified\nline3\nnewline\n"
        self._setup_files(output_dir, target, raw, current)

        result = detect_edits(target, output_dir)
        assert result["additions"] > 0
        assert result["deletions"] > 0


class TestUpdateQualityReport:
    def test_appends_to_jsonl(self, output_dir: Path):
        edit_result = {
            "date": "2026-04-03",
            "edited": True,
            "similarity": 0.95,
            "sections_changed": ["Commitments"],
            "additions": 2,
            "deletions": 1,
        }
        update_quality_report(edit_result, output_dir)

        metrics_path = output_dir / "quality" / "metrics.jsonl"
        assert metrics_path.exists()
        lines = metrics_path.read_text().strip().split("\n")
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["date"] == "2026-04-03"

    def test_appends_multiple_entries(self, output_dir: Path):
        for i in range(3):
            result = {
                "date": f"2026-04-0{i + 1}",
                "edited": i % 2 == 0,
                "similarity": 0.9 + i * 0.03,
                "sections_changed": ["Substance"] if i % 2 == 0 else [],
                "additions": i,
                "deletions": 0,
            }
            update_quality_report(result, output_dir)

        metrics_path = output_dir / "quality" / "metrics.jsonl"
        lines = metrics_path.read_text().strip().split("\n")
        assert len(lines) == 3

    def test_generates_report_markdown(self, output_dir: Path):
        edit_result = {
            "date": "2026-04-03",
            "edited": True,
            "similarity": 0.92,
            "sections_changed": ["Commitments"],
            "additions": 3,
            "deletions": 1,
        }
        report_path = update_quality_report(edit_result, output_dir)

        assert report_path.exists()
        content = report_path.read_text()
        assert "# Quality Report" in content
        assert "## Recent (Last 7 Days)" in content
        assert "## Trends" in content
        assert "2026-04-03" in content
        assert "Commitments" in content

    def test_report_trends_calculation(self, output_dir: Path):
        # Add 5 entries: 3 edited, 2 not
        for i in range(5):
            result = {
                "date": f"2026-04-0{i + 1}",
                "edited": i < 3,
                "similarity": 0.9 if i < 3 else 1.0,
                "sections_changed": ["Substance"] if i < 3 else [],
                "additions": 2 if i < 3 else 0,
                "deletions": 1 if i < 3 else 0,
            }
            update_quality_report(result, output_dir)

        report_path = output_dir / "quality" / "quality-report.md"
        content = report_path.read_text()
        assert "Edit rate (7d):" in content
        assert "Most-edited section:" in content
        assert "Average similarity:" in content
