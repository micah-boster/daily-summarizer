"""Priority configuration for daily synthesis pipeline.

Loads user-defined priorities (projects, people, topics, suppress) from YAML
and builds prompt context that shapes synthesis output emphasis.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from src.synthesis.models import MeetingExtraction


class PriorityConfig(BaseModel):
    """User-defined priority configuration for synthesis emphasis."""

    projects: list[str] = Field(default_factory=list)
    people: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    suppress: list[str] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        """Return True if no priorities are configured."""
        return not (self.projects or self.people or self.topics or self.suppress)


def load_priorities(config_path: Path | None = None) -> PriorityConfig:
    """Load priority configuration from YAML file.

    Args:
        config_path: Path to priorities YAML file. Defaults to config/priorities.yaml.

    Returns:
        PriorityConfig with loaded priorities, or empty config if file missing.
    """
    if config_path is None:
        config_path = Path("config/priorities.yaml")

    if not config_path.exists():
        return PriorityConfig()

    with open(config_path) as f:
        data = yaml.safe_load(f) or {}

    return PriorityConfig(
        projects=data.get("projects", []) or [],
        people=data.get("people", []) or [],
        topics=data.get("topics", []) or [],
        suppress=data.get("suppress", []) or [],
    )


def _find_matches(
    items: list[str],
    extractions: list[MeetingExtraction],
    match_field: str,
) -> dict[str, list[str]]:
    """Find which priority items match which meetings.

    Args:
        items: Priority items to search for.
        extractions: Meeting extractions to search within.
        match_field: "content" to search extraction text, "participants" for people,
                     "title" for meeting titles.

    Returns:
        Dict mapping matched item -> list of meeting titles where it appears.
    """
    matches: dict[str, list[str]] = {}

    for item in items:
        item_lower = item.lower()
        matched_meetings: list[str] = []

        for ext in extractions:
            if ext.low_signal:
                continue

            found = False

            if match_field == "title":
                if item_lower in ext.meeting_title.lower():
                    found = True
            elif match_field == "participants":
                for participant in ext.meeting_participants:
                    if item_lower in participant.lower():
                        found = True
                        break
            elif match_field == "content":
                # Search across all extraction content
                all_content = []
                for category in [
                    ext.decisions,
                    ext.commitments,
                    ext.substance,
                    ext.open_questions,
                    ext.tensions,
                ]:
                    for extraction_item in category:
                        all_content.append(extraction_item.content.lower())

                # Also search meeting title
                all_content.append(ext.meeting_title.lower())

                if any(item_lower in text for text in all_content):
                    found = True

            if found and ext.meeting_title not in matched_meetings:
                matched_meetings.append(ext.meeting_title)

        if matched_meetings:
            matches[item] = matched_meetings

    return matches


def build_priority_context(
    priorities: PriorityConfig,
    extractions: list[MeetingExtraction],
) -> str:
    """Build priority context string for injection into synthesis prompt.

    Scans extractions for priority matches and builds a formatted context
    block that tells the synthesizer how to emphasize or suppress content.

    Args:
        priorities: Loaded priority configuration.
        extractions: Meeting extractions from Stage 1.

    Returns:
        Formatted priority context string, or empty string if no priorities
        or no matches found.
    """
    if priorities.is_empty:
        return ""

    sections: list[str] = []

    # Match projects against content and titles
    project_matches = _find_matches(priorities.projects, extractions, "content")
    if project_matches:
        lines = []
        for project, meetings in project_matches.items():
            lines.append(f"  - {project} (in {', '.join(repr(m) for m in meetings)})")
        sections.append("High-priority projects detected:\n" + "\n".join(lines))

    # Match people against participants
    people_matches = _find_matches(priorities.people, extractions, "participants")
    if people_matches:
        lines = []
        for person, meetings in people_matches.items():
            lines.append(f"  - {person} (in {', '.join(repr(m) for m in meetings)})")
        sections.append("High-priority people detected:\n" + "\n".join(lines))

    # Match topics against content
    topic_matches = _find_matches(priorities.topics, extractions, "content")
    if topic_matches:
        lines = []
        for topic, meetings in topic_matches.items():
            lines.append(f"  - {topic} (in {', '.join(repr(m) for m in meetings)})")
        sections.append("High-priority topics detected:\n" + "\n".join(lines))

    # Match suppress against meeting titles
    suppress_matches = _find_matches(priorities.suppress, extractions, "title")
    if suppress_matches:
        titles = list(suppress_matches.keys())
        sections.append(f"Suppress: {', '.join(titles)} (minimize to one-liner each)")

    if not sections:
        return ""

    context_block = "PRIORITY CONTEXT:\n" + "\n".join(sections)
    instructions = """

PRIORITY INSTRUCTIONS:
- Give priority-matched items dedicated subsections with expanded detail
- Give suppress-matched meetings one-liner treatment: "Also: [title] — [one-sentence summary]"
- Do NOT add [priority] tags or markers — shape output naturally
- Non-priority items still appear with standard treatment"""

    return context_block + instructions
