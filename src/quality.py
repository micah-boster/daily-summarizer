"""Diff-based quality metrics tracking for daily synthesis pipeline.

Compares raw pipeline output against user-edited versions to detect edits,
track correction patterns, and generate a rolling quality report.
"""

from __future__ import annotations

import difflib
import json
from datetime import date, datetime, timezone
from pathlib import Path


def save_raw_output(content: str, target_date: date, output_dir: Path) -> Path:
    """Save raw pipeline output for future diff-based comparison.

    Args:
        content: The raw markdown content from the pipeline.
        target_date: The date of the daily summary.
        output_dir: Base output directory.

    Returns:
        Path to the saved raw file.
    """
    d = target_date
    raw_dir = output_dir / "raw" / "daily" / str(d.year) / f"{d.month:02d}"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{d.isoformat()}.raw.md"
    raw_path.write_text(content, encoding="utf-8")
    return raw_path


def detect_edits(target_date: date, output_dir: Path) -> dict | None:
    """Compare raw pipeline output against current file to detect user edits.

    Args:
        target_date: The date to check for edits.
        output_dir: Base output directory.

    Returns:
        Dict with edit metrics, or None if either file is missing.
        Keys: date, edited, similarity, sections_changed, additions, deletions.
    """
    d = target_date
    raw_path = (
        output_dir / "raw" / "daily" / str(d.year) / f"{d.month:02d}" / f"{d.isoformat()}.raw.md"
    )
    current_path = output_dir / "daily" / str(d.year) / f"{d.month:02d}" / f"{d.isoformat()}.md"

    if not raw_path.exists() or not current_path.exists():
        return None

    raw_text = raw_path.read_text(encoding="utf-8")
    current_text = current_path.read_text(encoding="utf-8")

    # Overall similarity
    matcher = difflib.SequenceMatcher(None, raw_text, current_text)
    similarity = round(matcher.ratio(), 4)

    # Line-level diff
    raw_lines = raw_text.splitlines(keepends=True)
    current_lines = current_text.splitlines(keepends=True)
    diff = list(difflib.unified_diff(raw_lines, current_lines, lineterm=""))

    additions = 0
    deletions = 0
    for line in diff:
        if line.startswith("+") and not line.startswith("+++"):
            additions += 1
        elif line.startswith("-") and not line.startswith("---"):
            deletions += 1

    edited = additions > 0 or deletions > 0

    # Detect which sections were changed
    sections_changed = _detect_changed_sections(raw_lines, current_lines)

    return {
        "date": d.isoformat(),
        "edited": edited,
        "similarity": similarity,
        "sections_changed": sections_changed,
        "additions": additions,
        "deletions": deletions,
    }


def _detect_changed_sections(raw_lines: list[str], current_lines: list[str]) -> list[str]:
    """Identify which markdown sections were changed between raw and current.

    Looks for ## headers and checks if content under them differs.

    Returns:
        List of section names that were modified.
    """
    raw_sections = _split_into_sections(raw_lines)
    current_sections = _split_into_sections(current_lines)

    changed: list[str] = []

    # Check sections present in both
    all_section_names = set(raw_sections.keys()) | set(current_sections.keys())
    for name in all_section_names:
        raw_content = raw_sections.get(name, "")
        current_content = current_sections.get(name, "")
        if raw_content != current_content:
            changed.append(name)

    return sorted(changed)


def _split_into_sections(lines: list[str]) -> dict[str, str]:
    """Split markdown lines into sections keyed by ## header names."""
    sections: dict[str, str] = {}
    current_section = "_preamble"
    current_content: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            if current_content:
                sections[current_section] = "".join(current_content)
            current_section = stripped[3:].strip()
            current_content = []
        else:
            current_content.append(line)

    if current_content:
        sections[current_section] = "".join(current_content)

    return sections


def update_quality_report(edit_result: dict, output_dir: Path) -> Path:
    """Append edit result to metrics log and regenerate quality report.

    Args:
        edit_result: Dict from detect_edits().
        output_dir: Base output directory.

    Returns:
        Path to the generated quality-report.md.
    """
    quality_dir = output_dir / "quality"
    quality_dir.mkdir(parents=True, exist_ok=True)

    # Append to JSONL log
    metrics_path = quality_dir / "metrics.jsonl"
    with open(metrics_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(edit_result) + "\n")

    # Read all metrics
    all_metrics: list[dict] = []
    with open(metrics_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                all_metrics.append(json.loads(line))

    # Generate report
    report_path = quality_dir / "quality-report.md"
    report = _generate_report(all_metrics)
    report_path.write_text(report, encoding="utf-8")

    return report_path


def _generate_report(metrics: list[dict]) -> str:
    """Generate human-readable quality report from metrics data."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines: list[str] = [
        "# Quality Report",
        f"\nLast updated: {now}",
        "",
    ]

    # Recent (last 7 entries)
    recent = metrics[-7:]
    lines.append("## Recent (Last 7 Days)")
    lines.append("")
    lines.append("| Date | Edit Detected | Similarity | Sections Changed |")
    lines.append("|------|--------------|------------|------------------|")
    for m in recent:
        edited = "Yes" if m["edited"] else "No"
        similarity = f"{m['similarity'] * 100:.0f}%"
        sections = ", ".join(m["sections_changed"]) if m["sections_changed"] else "-"
        lines.append(f"| {m['date']} | {edited} | {similarity} | {sections} |")

    lines.append("")

    # Trends
    lines.append("## Trends")
    lines.append("")

    if metrics:
        # 7-day edit rate
        last_7 = metrics[-7:]
        edit_rate_7d = sum(1 for m in last_7 if m["edited"]) / len(last_7) * 100

        # 30-day edit rate
        last_30 = metrics[-30:]
        edit_rate_30d = sum(1 for m in last_30 if m["edited"]) / len(last_30) * 100

        # Most-edited section
        section_counts: dict[str, int] = {}
        for m in metrics:
            for section in m.get("sections_changed", []):
                section_counts[section] = section_counts.get(section, 0) + 1
        most_edited = max(section_counts, key=section_counts.get) if section_counts else "None"
        most_edited_pct = (
            f"{section_counts[most_edited] / len(metrics) * 100:.0f}%"
            if section_counts
            else "0%"
        )

        # Average similarity
        avg_similarity = sum(m["similarity"] for m in metrics) / len(metrics) * 100

        lines.append(f"- Edit rate (7d): {edit_rate_7d:.0f}%")
        lines.append(f"- Edit rate (30d): {edit_rate_30d:.0f}%")
        lines.append(f"- Most-edited section: {most_edited} ({most_edited_pct})")
        lines.append(f"- Average similarity: {avg_similarity:.0f}%")
    else:
        lines.append("No data yet.")

    lines.append("")
    return "\n".join(lines)
