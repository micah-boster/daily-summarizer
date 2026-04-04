"""Tests for JSON sidecar generation."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest

from src.models.events import Attendee, DailySynthesis, NormalizedEvent, Section
from src.sidecar import (
    DailySidecar,
    SidecarCommitment,
    SidecarDecision,
    SidecarTask,
    build_daily_sidecar,
)
from src.synthesis.models import ExtractionItem, MeetingExtraction


@pytest.fixture
def sample_synthesis() -> DailySynthesis:
    """Create a sample DailySynthesis for testing."""
    return DailySynthesis(
        date=date(2026, 4, 3),
        generated_at=datetime(2026, 4, 3, 8, 0, 0, tzinfo=timezone.utc),
        meeting_count=3,
        total_meeting_hours=2.5,
        transcript_count=2,
        substance=Section(title="Substance"),
        decisions=Section(title="Decisions"),
        commitments=Section(title="Commitments"),
        meetings_without_transcripts=[
            NormalizedEvent(
                id="evt-no-transcript",
                title="Quick 1:1",
                start_time=datetime(2026, 4, 3, 15, 0, 0, tzinfo=timezone.utc),
                attendees=[
                    Attendee(name="Alice", email="alice@example.com"),
                    Attendee(name="Me", email="me@example.com", is_self=True),
                ],
            )
        ],
    )


@pytest.fixture
def sample_extractions() -> list[MeetingExtraction]:
    """Create sample extractions for testing."""
    return [
        MeetingExtraction(
            meeting_title="Project Alpha Sync",
            meeting_time="2026-04-03T10:00:00",
            meeting_participants=["Sarah Chen", "Bob Smith"],
            decisions=[
                ExtractionItem(
                    content="Move launch to Q3 due to API dependency",
                    participants=["Sarah Chen"],
                    rationale="API partner delayed by 4 weeks",
                )
            ],
            commitments=[
                ExtractionItem(
                    content="Draft revised timeline by Friday",
                    participants=["Sarah Chen"],
                ),
                ExtractionItem(
                    content="Update stakeholder communication",
                    participants=["Bob Smith"],
                ),
            ],
            substance=[
                ExtractionItem(
                    content="Reviewed API integration blockers",
                    participants=["Sarah Chen", "Bob Smith"],
                )
            ],
        ),
        MeetingExtraction(
            meeting_title="Hiring Review",
            meeting_time="2026-04-03T14:00:00",
            meeting_participants=["Mike Johnson", "HR Team"],
            decisions=[],
            commitments=[
                ExtractionItem(
                    content="Schedule final round interviews next week",
                    participants=["Mike Johnson"],
                )
            ],
            substance=[
                ExtractionItem(
                    content="5 candidates passed technical screen",
                    participants=["Mike Johnson"],
                )
            ],
        ),
    ]


class TestSidecarModels:
    def test_sidecar_task_model(self):
        task = SidecarTask(
            description="Draft timeline",
            owner="Sarah Chen",
            source_meeting="Alpha Sync",
            date_captured="2026-04-03",
            status="new",
        )
        assert task.description == "Draft timeline"
        assert task.owner == "Sarah Chen"
        assert task.status == "new"
        assert task.due_date is None

    def test_sidecar_decision_model(self):
        decision = SidecarDecision(
            description="Move to Q3",
            decision_makers=["Sarah"],
            rationale="API delay",
            source_meeting="Alpha Sync",
        )
        assert decision.description == "Move to Q3"
        assert len(decision.decision_makers) == 1

    def test_daily_sidecar_serialization(self):
        sidecar = DailySidecar(
            date="2026-04-03",
            generated_at="2026-04-03T08:00:00+00:00",
            meeting_count=2,
            transcript_count=1,
            tasks=[
                SidecarTask(
                    description="Test task",
                    source_meeting="Test Meeting",
                    date_captured="2026-04-03",
                )
            ],
        )
        json_str = sidecar.model_dump_json(indent=2)
        parsed = json.loads(json_str)
        assert parsed["date"] == "2026-04-03"
        assert len(parsed["tasks"]) == 1
        assert parsed["tasks"][0]["status"] == "new"


class TestBuildDailySidecar:
    def test_maps_commitments_to_tasks(self, sample_synthesis, sample_extractions):
        sidecar = build_daily_sidecar(sample_synthesis, sample_extractions)

        assert len(sidecar.tasks) == 3  # 2 from Alpha + 1 from Hiring
        assert sidecar.tasks[0].description == "Draft revised timeline by Friday"
        assert sidecar.tasks[0].owner == "Sarah Chen"
        assert sidecar.tasks[0].source_meeting == "Project Alpha Sync"
        assert sidecar.tasks[0].date_captured == "2026-04-03"
        assert sidecar.tasks[0].status == "new"

    def test_maps_decisions(self, sample_synthesis, sample_extractions):
        sidecar = build_daily_sidecar(sample_synthesis, sample_extractions)

        assert len(sidecar.decisions) == 1
        assert sidecar.decisions[0].description == "Move launch to Q3 due to API dependency"
        assert sidecar.decisions[0].decision_makers == ["Sarah Chen"]
        assert sidecar.decisions[0].rationale == "API partner delayed by 4 weeks"
        assert sidecar.decisions[0].source_meeting == "Project Alpha Sync"

    def test_empty_extractions(self, sample_synthesis):
        sidecar = build_daily_sidecar(sample_synthesis, [])

        assert sidecar.tasks == []
        assert sidecar.decisions == []
        assert sidecar.meeting_count == 3
        # Still includes meetings_without_transcripts
        assert len(sidecar.source_meetings) == 1

    def test_low_signal_skipped(self, sample_synthesis):
        low_signal = MeetingExtraction(
            meeting_title="Quick Chat",
            meeting_time="2026-04-03T16:00:00",
            meeting_participants=["Alice"],
            commitments=[
                ExtractionItem(content="Should not appear", participants=["Alice"])
            ],
            low_signal=True,
        )
        sidecar = build_daily_sidecar(sample_synthesis, [low_signal])

        assert sidecar.tasks == []
        assert sidecar.decisions == []

    def test_source_meetings_includes_both(self, sample_synthesis, sample_extractions):
        sidecar = build_daily_sidecar(sample_synthesis, sample_extractions)

        # 2 meetings with transcripts + 1 without
        assert len(sidecar.source_meetings) == 3

        transcript_meetings = [m for m in sidecar.source_meetings if m.has_transcript]
        no_transcript = [m for m in sidecar.source_meetings if not m.has_transcript]
        assert len(transcript_meetings) == 2
        assert len(no_transcript) == 1
        assert no_transcript[0].title == "Quick 1:1"

    def test_metadata_fields(self, sample_synthesis, sample_extractions):
        sidecar = build_daily_sidecar(sample_synthesis, sample_extractions)

        assert sidecar.date == "2026-04-03"
        assert sidecar.generated_at == "2026-04-03T08:00:00+00:00"
        assert sidecar.meeting_count == 3
        assert sidecar.transcript_count == 2

    def test_task_owner_none_when_no_participants(self, sample_synthesis):
        extraction = MeetingExtraction(
            meeting_title="Solo Meeting",
            meeting_time="2026-04-03T11:00:00",
            meeting_participants=["Me"],
            commitments=[
                ExtractionItem(content="Do something", participants=[])
            ],
        )
        sidecar = build_daily_sidecar(sample_synthesis, [extraction])

        assert sidecar.tasks[0].owner is None


class TestSidecarCommitment:
    """Tests for SidecarCommitment model and commitments integration."""

    def test_sidecar_commitment_model(self):
        c = SidecarCommitment(
            who="John",
            what="Send deck to partners",
            by_when="2026-04-10",
            source=["standup", "Slack #proj-alpha"],
        )
        assert c.who == "John"
        assert c.what == "Send deck to partners"
        assert c.by_when == "2026-04-10"
        assert c.source == ["standup", "Slack #proj-alpha"]

    def test_sidecar_commitment_json_serialization(self):
        c = SidecarCommitment(
            who="Sarah",
            what="Schedule vendor call",
            by_when="unspecified",
            source=["standup"],
        )
        data = json.loads(c.model_dump_json())
        assert data["who"] == "Sarah"
        assert data["source"] == ["standup"]

    def test_daily_sidecar_backward_compat_no_commitments(self):
        """Existing JSON without commitments key still deserializes."""
        old_json = json.dumps({
            "date": "2026-04-03",
            "generated_at": "2026-04-03T08:00:00+00:00",
            "meeting_count": 2,
            "transcript_count": 1,
            "tasks": [],
            "decisions": [],
            "source_meetings": [],
        })
        ds = DailySidecar.model_validate_json(old_json)
        assert ds.commitments == []
        assert ds.date == "2026-04-03"

    def test_build_sidecar_with_extracted_commitments(self, sample_synthesis, sample_extractions):
        """Extracted commitments are mapped to SidecarCommitment in sidecar."""
        # Create mock extracted commitments with the right attributes
        class MockCommitment:
            def __init__(self, who, what, by_when, source):
                self.who = who
                self.what = what
                self.by_when = by_when
                self.source = source

        commitments = [
            MockCommitment("Sarah", "Send timeline", "2026-04-10", ["standup"]),
            MockCommitment("Bob", "Review proposal", "unspecified", ["Slack #proj-alpha"]),
        ]

        sidecar = build_daily_sidecar(sample_synthesis, sample_extractions, extracted_commitments=commitments)
        assert len(sidecar.commitments) == 2
        assert sidecar.commitments[0].who == "Sarah"
        assert sidecar.commitments[0].what == "Send timeline"
        assert sidecar.commitments[0].by_when == "2026-04-10"
        assert sidecar.commitments[0].source == ["standup"]
        assert sidecar.commitments[1].who == "Bob"

    def test_build_sidecar_without_extracted_commitments(self, sample_synthesis, sample_extractions):
        """None extracted_commitments returns empty commitments list."""
        sidecar = build_daily_sidecar(sample_synthesis, sample_extractions, extracted_commitments=None)
        assert sidecar.commitments == []

    def test_daily_sidecar_with_commitments_json_roundtrip(self):
        """Full JSON round-trip with commitments populated."""
        sidecar = DailySidecar(
            date="2026-04-03",
            generated_at="2026-04-03T08:00:00+00:00",
            meeting_count=2,
            transcript_count=1,
            commitments=[
                SidecarCommitment(
                    who="John",
                    what="Send deck",
                    by_when="2026-04-10",
                    source=["standup"],
                ),
            ],
        )
        json_str = sidecar.model_dump_json(indent=2)
        parsed = json.loads(json_str)
        assert "commitments" in parsed
        assert len(parsed["commitments"]) == 1
        assert parsed["commitments"][0]["who"] == "John"
        assert parsed["commitments"][0]["source"] == ["standup"]

        # Deserialize back
        ds = DailySidecar.model_validate_json(json_str)
        assert len(ds.commitments) == 1
        assert ds.commitments[0].who == "John"
