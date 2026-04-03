"""Tests for priority configuration and prompt injection."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.priorities import PriorityConfig, build_priority_context, load_priorities
from src.synthesis.models import ExtractionItem, MeetingExtraction


@pytest.fixture
def sample_extractions() -> list[MeetingExtraction]:
    """Create sample extractions for testing priority matching."""
    return [
        MeetingExtraction(
            meeting_title="Project Alpha Weekly Sync",
            meeting_time="2026-04-03T10:00:00",
            meeting_participants=["Sarah Chen", "Bob Smith"],
            decisions=[
                ExtractionItem(
                    content="Decided to move hiring timeline up by two weeks",
                    participants=["Sarah Chen"],
                    rationale="Budget approved early",
                )
            ],
            commitments=[
                ExtractionItem(
                    content="Sarah to draft job descriptions by Friday",
                    participants=["Sarah Chen"],
                )
            ],
            substance=[
                ExtractionItem(
                    content="Reviewed Q2 budget allocation for Project Alpha",
                    participants=["Sarah Chen", "Bob Smith"],
                )
            ],
        ),
        MeetingExtraction(
            meeting_title="Daily Standup",
            meeting_time="2026-04-03T09:00:00",
            meeting_participants=["Team"],
            substance=[
                ExtractionItem(
                    content="Sprint progress update, no blockers",
                    participants=["Team"],
                )
            ],
        ),
        MeetingExtraction(
            meeting_title="Recruiting Update",
            meeting_time="2026-04-03T14:00:00",
            meeting_participants=["Mike Johnson", "HR Team"],
            substance=[
                ExtractionItem(
                    content="Hiring pipeline review: 5 candidates in final round",
                    participants=["Mike Johnson"],
                )
            ],
        ),
    ]


@pytest.fixture
def low_signal_extraction() -> MeetingExtraction:
    """Create a low-signal extraction."""
    return MeetingExtraction(
        meeting_title="Quick Chat",
        meeting_time="2026-04-03T16:00:00",
        meeting_participants=["Alice"],
        low_signal=True,
    )


class TestPriorityConfig:
    def test_empty_config(self):
        config = PriorityConfig()
        assert config.projects == []
        assert config.people == []
        assert config.topics == []
        assert config.suppress == []
        assert config.is_empty is True

    def test_non_empty_config(self):
        config = PriorityConfig(projects=["Alpha"])
        assert config.is_empty is False

    def test_all_fields(self):
        config = PriorityConfig(
            projects=["Alpha"],
            people=["Sarah"],
            topics=["hiring"],
            suppress=["Standup"],
        )
        assert len(config.projects) == 1
        assert len(config.people) == 1
        assert len(config.topics) == 1
        assert len(config.suppress) == 1


class TestLoadPriorities:
    def test_load_valid_file(self, tmp_path: Path):
        config_file = tmp_path / "priorities.yaml"
        config_file.write_text(
            "projects:\n  - Alpha\npeople:\n  - Sarah\ntopics:\n  - hiring\nsuppress:\n  - Standup\n"
        )
        config = load_priorities(config_file)
        assert config.projects == ["Alpha"]
        assert config.people == ["Sarah"]
        assert config.topics == ["hiring"]
        assert config.suppress == ["Standup"]

    def test_load_missing_file(self, tmp_path: Path):
        config = load_priorities(tmp_path / "nonexistent.yaml")
        assert config.is_empty is True

    def test_load_empty_file(self, tmp_path: Path):
        config_file = tmp_path / "priorities.yaml"
        config_file.write_text("")
        config = load_priorities(config_file)
        assert config.is_empty is True

    def test_load_partial_file(self, tmp_path: Path):
        config_file = tmp_path / "priorities.yaml"
        config_file.write_text("projects:\n  - Alpha\n")
        config = load_priorities(config_file)
        assert config.projects == ["Alpha"]
        assert config.people == []
        assert config.topics == []
        assert config.suppress == []


class TestBuildPriorityContext:
    def test_empty_priorities_returns_empty(self, sample_extractions):
        config = PriorityConfig()
        result = build_priority_context(config, sample_extractions)
        assert result == ""

    def test_no_matches_returns_empty(self):
        config = PriorityConfig(projects=["Nonexistent Project"])
        extractions = [
            MeetingExtraction(
                meeting_title="Unrelated Meeting",
                meeting_time="2026-04-03T10:00:00",
                meeting_participants=["Nobody"],
                substance=[
                    ExtractionItem(content="Nothing relevant", participants=["Nobody"])
                ],
            )
        ]
        result = build_priority_context(config, extractions)
        assert result == ""

    def test_project_match(self, sample_extractions):
        config = PriorityConfig(projects=["Project Alpha"])
        result = build_priority_context(config, sample_extractions)
        assert "PRIORITY CONTEXT:" in result
        assert "Project Alpha" in result
        assert "PRIORITY INSTRUCTIONS:" in result

    def test_people_match(self, sample_extractions):
        config = PriorityConfig(people=["Sarah Chen"])
        result = build_priority_context(config, sample_extractions)
        assert "Sarah Chen" in result
        assert "High-priority people detected:" in result

    def test_topic_match(self, sample_extractions):
        config = PriorityConfig(topics=["hiring"])
        result = build_priority_context(config, sample_extractions)
        assert "hiring" in result
        assert "High-priority topics detected:" in result

    def test_suppress_match(self, sample_extractions):
        config = PriorityConfig(suppress=["Daily Standup"])
        result = build_priority_context(config, sample_extractions)
        assert "Suppress:" in result
        assert "Daily Standup" in result

    def test_case_insensitive_matching(self, sample_extractions):
        config = PriorityConfig(people=["sarah chen"])  # lowercase
        result = build_priority_context(config, sample_extractions)
        assert "sarah chen" in result
        assert "High-priority people detected:" in result

    def test_low_signal_extractions_skipped(self, low_signal_extraction):
        config = PriorityConfig(projects=["Quick Chat"])
        result = build_priority_context(config, [low_signal_extraction])
        assert result == ""

    def test_combined_priorities(self, sample_extractions):
        config = PriorityConfig(
            projects=["Project Alpha"],
            people=["Mike Johnson"],
            topics=["hiring"],
            suppress=["Daily Standup"],
        )
        result = build_priority_context(config, sample_extractions)
        assert "High-priority projects detected:" in result
        assert "High-priority people detected:" in result
        assert "High-priority topics detected:" in result
        assert "Suppress:" in result
        assert "PRIORITY INSTRUCTIONS:" in result

    def test_no_priority_markers_instruction(self, sample_extractions):
        config = PriorityConfig(projects=["Project Alpha"])
        result = build_priority_context(config, sample_extractions)
        assert "Do NOT add [priority] tags" in result
        assert "shape output naturally" in result
