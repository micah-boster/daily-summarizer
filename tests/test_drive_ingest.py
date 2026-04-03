"""Tests for Google Drive transcript fetching."""

from datetime import datetime

import pytest

from src.ingest.drive import (
    _extract_time_from_doc_name,
    _extract_title_from_doc_name,
    parse_drive_transcript,
)
from src.ingest.transcripts import _deduplicate_transcripts


class TestExtractTitleFromDocName:
    def test_standard_format(self):
        name = "Bounce x Cardless First Party  - 2026/03/18 15:25 EDT - Notes by Gemini"
        assert _extract_title_from_doc_name(name) == "Bounce x Cardless First Party"

    def test_title_with_hyphens(self):
        name = "Micah / Colin - Account Review - 2026/03/18 10:58 EDT - Notes by Gemini"
        assert _extract_title_from_doc_name(name) == "Micah / Colin - Account Review"

    def test_no_match_fallback_strips_suffix(self):
        name = "Some Random Doc - Notes by Gemini"
        assert _extract_title_from_doc_name(name) == "Some Random Doc"

    def test_no_match_no_suffix(self):
        name = "Completely unrelated doc"
        assert _extract_title_from_doc_name(name) == "Completely unrelated doc"

    def test_case_insensitive_suffix(self):
        name = "Weekly Sync - 2026/03/18 09:00 EST - notes by gemini"
        assert _extract_title_from_doc_name(name) == "Weekly Sync"


class TestExtractTimeFromDocName:
    def test_standard_format(self):
        name = "Weekly Sync - 2026/03/18 15:25 EDT - Notes by Gemini"
        result = _extract_time_from_doc_name(name)
        assert result is not None
        assert result.year == 2026
        assert result.month == 3
        assert result.day == 18

    def test_no_match_returns_none(self):
        name = "Some Random Doc"
        assert _extract_time_from_doc_name(name) is None


class TestParseDriveTranscript:
    def test_standard_parse(self):
        meta = {
            "id": "doc123",
            "name": "Team Sync - 2026/03/18 10:00 EDT - Notes by Gemini",
            "createdTime": "2026-03-18T14:00:00.000Z",
        }
        result = parse_drive_transcript(meta, "Meeting content here", {})
        assert result is not None
        assert result["source"] == "gemini_drive"
        assert result["title"] == "Team Sync"
        assert result["message_id"] == "doc123"
        assert "Meeting content" in result["transcript_text"]

    def test_empty_text_returns_none(self):
        meta = {"id": "doc123", "name": "Empty Meeting - Notes by Gemini"}
        assert parse_drive_transcript(meta, "", {}) is None
        assert parse_drive_transcript(meta, "   ", {}) is None

    def test_filler_stripping(self):
        meta = {
            "id": "doc123",
            "name": "Test - 2026/03/18 10:00 EDT - Notes by Gemini",
        }
        config = {"transcripts": {"preprocessing": {"strip_filler": True}}}
        result = parse_drive_transcript(meta, "So um we discussed the the plan", config)
        assert result is not None
        assert "um" not in result["transcript_text"]

    def test_fallback_to_created_time(self):
        meta = {
            "id": "doc123",
            "name": "Weird Format - Notes by Gemini",
            "createdTime": "2026-03-18T14:00:00.000Z",
        }
        result = parse_drive_transcript(meta, "Some content", {})
        assert result is not None
        assert result["meeting_time"] is not None
        assert result["meeting_time"].year == 2026


class TestDeduplicateTranscripts:
    def test_drive_beats_gmail(self):
        transcripts = [
            {"source": "gemini_drive", "title": "Team Sync", "transcript_text": "drive version"},
            {"source": "gemini", "title": "Team Sync", "transcript_text": "email version"},
        ]
        result = _deduplicate_transcripts(transcripts)
        assert len(result) == 1
        assert result[0]["source"] == "gemini_drive"

    def test_gmail_beats_gong(self):
        transcripts = [
            {"source": "gemini", "title": "Team Sync", "transcript_text": "gmail version"},
            {"source": "gong", "title": "Team Sync", "transcript_text": "gong version"},
        ]
        result = _deduplicate_transcripts(transcripts)
        assert len(result) == 1
        assert result[0]["source"] == "gemini"

    def test_different_titles_kept(self):
        transcripts = [
            {"source": "gemini_drive", "title": "Meeting A", "transcript_text": "a"},
            {"source": "gemini_drive", "title": "Meeting B", "transcript_text": "b"},
        ]
        result = _deduplicate_transcripts(transcripts)
        assert len(result) == 2

    def test_case_insensitive_dedup(self):
        transcripts = [
            {"source": "gemini_drive", "title": "Team Sync", "transcript_text": "drive"},
            {"source": "gemini", "title": "team sync", "transcript_text": "email"},
        ]
        result = _deduplicate_transcripts(transcripts)
        assert len(result) == 1
        assert result[0]["source"] == "gemini_drive"

    def test_empty_list(self):
        assert _deduplicate_transcripts([]) == []
