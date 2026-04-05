"""Comprehensive tests for the Pydantic config system.

Covers: happy path loading, validation errors, env var overrides,
error formatting with fuzzy suggestions, and the make_test_config factory.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from src.config import (
    GoogleDocsConfig,
    PipelineConfig,
    PipelineSettings,
    SlackConfig,
    SynthesisConfig,
    _format_validation_error,
    load_config,
    make_test_config,
)


# ---------------------------------------------------------------------------
# Happy path tests
# ---------------------------------------------------------------------------


class TestLoadDefaultConfig:
    """Tests for loading config from the actual config.yaml file."""

    def test_load_default_config(self):
        """load_config() with existing config/config.yaml returns PipelineConfig."""
        config = load_config()
        assert isinstance(config, PipelineConfig)
        assert config.pipeline.timezone == "America/New_York"
        assert config.calendars.ids == ["primary"]
        assert config.synthesis.model == "claude-sonnet-4-20250514"

    def test_load_missing_file(self, tmp_path: Path):
        """load_config() with non-existent path returns PipelineConfig with all defaults."""
        config = load_config(tmp_path / "nonexistent.yaml")
        assert isinstance(config, PipelineConfig)
        assert config.pipeline.timezone == "America/New_York"
        assert config.pipeline.output_dir == "output"
        assert config.slack.enabled is False

    def test_all_sections_optional(self):
        """PipelineConfig(**{}) succeeds with all defaults."""
        config = PipelineConfig()
        assert config.pipeline.timezone == "America/New_York"
        assert config.slack.enabled is False
        assert config.hubspot.enabled is False
        assert config.google_docs.enabled is False

    def test_partial_config(self):
        """PipelineConfig with only pipeline section succeeds, others default."""
        config = PipelineConfig(pipeline={"timezone": "US/Pacific"})
        assert config.pipeline.timezone == "US/Pacific"
        assert config.slack.enabled is False
        assert config.synthesis.model == "claude-sonnet-4-20250514"

    def test_full_config_roundtrip(self):
        """Load config.yaml via load_config(), verify key values match YAML."""
        config = load_config()
        # Pipeline
        assert config.pipeline.timezone == "America/New_York"
        assert config.pipeline.output_dir == "output"
        # Calendars
        assert config.calendars.ids == ["primary"]
        assert config.calendars.exclude_patterns == []
        # Transcripts
        assert config.transcripts.gemini_drive.enabled is True
        assert "calendar-notification@google.com" in config.transcripts.gemini.sender_patterns
        assert config.transcripts.matching.time_window_minutes == 30
        assert config.transcripts.matching.include_unmatched_events is True
        assert config.transcripts.preprocessing.strip_filler is True
        # Synthesis
        assert config.synthesis.extraction_max_output_tokens == 4096
        assert config.synthesis.synthesis_max_output_tokens == 8192
        assert config.synthesis.weekly_max_output_tokens == 8192
        assert config.synthesis.monthly_max_output_tokens == 8192
        # Slack
        assert config.slack.enabled is False
        assert config.slack.thread_min_replies == 3
        assert config.slack.thread_min_participants == 2
        assert config.slack.max_messages_per_channel == 100
        assert config.slack.discovery_check_days == 7
        assert "channel_join" in config.slack.filter.skip_subtypes
        # Google Docs
        assert config.google_docs.enabled is False
        assert config.google_docs.content_max_chars == 2500
        assert config.google_docs.comment_max_chars == 500
        assert config.google_docs.max_docs_per_day == 50
        # HubSpot
        assert config.hubspot.enabled is False
        assert config.hubspot.ownership_scope == "mine"
        assert config.hubspot.max_deals == 50
        assert config.hubspot.max_contacts == 50
        assert config.hubspot.max_tickets == 25
        assert config.hubspot.max_activities_per_type == 25
        assert config.hubspot.portal_url == ""


# ---------------------------------------------------------------------------
# Validation error tests
# ---------------------------------------------------------------------------


class TestValidationErrors:
    """Tests for config validation catching invalid values and unknown keys."""

    def test_unknown_top_level_key(self):
        """PipelineConfig(slakc={}) raises ValidationError with extra_forbidden."""
        with pytest.raises(ValidationError) as exc_info:
            PipelineConfig(slakc={})
        assert "extra_forbidden" in str(exc_info.value)

    def test_unknown_nested_key(self):
        """PipelineConfig(slack={"chnnels": []}) raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            PipelineConfig(slack={"chnnels": []})
        assert "extra_forbidden" in str(exc_info.value)

    def test_negative_thread_min_replies(self):
        """SlackConfig(thread_min_replies=-1) raises ValidationError."""
        with pytest.raises(ValidationError):
            SlackConfig(thread_min_replies=-1)

    def test_empty_timezone(self):
        """PipelineSettings(timezone='') raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            PipelineSettings(timezone="")
        assert "must not be empty" in str(exc_info.value)

    def test_empty_synthesis_model(self):
        """SynthesisConfig(model='') raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SynthesisConfig(model="")
        assert "must not be empty" in str(exc_info.value)

    def test_zero_thread_min_replies(self):
        """SlackConfig(thread_min_replies=0) raises ValidationError (ge=1)."""
        with pytest.raises(ValidationError):
            SlackConfig(thread_min_replies=0)

    def test_whitespace_only_timezone(self):
        """PipelineSettings(timezone='   ') raises ValidationError."""
        with pytest.raises(ValidationError):
            PipelineSettings(timezone="   ")

    def test_empty_output_dir(self):
        """PipelineSettings(output_dir='') raises ValidationError."""
        with pytest.raises(ValidationError):
            PipelineSettings(output_dir="")


# ---------------------------------------------------------------------------
# Env var override tests
# ---------------------------------------------------------------------------


class TestEnvVarOverrides:
    """Tests for environment variable override merging."""

    def test_env_timezone_override(self, monkeypatch, tmp_path: Path):
        """Set SUMMARIZER_TIMEZONE, verify config.pipeline.timezone reflects it."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("pipeline:\n  timezone: 'America/New_York'\n")
        monkeypatch.setenv("SUMMARIZER_TIMEZONE", "US/Pacific")
        config = load_config(config_file)
        assert config.pipeline.timezone == "US/Pacific"

    def test_env_calendar_ids_override(self, monkeypatch, tmp_path: Path):
        """Set SUMMARIZER_CALENDAR_IDS='cal1,cal2', verify split correctly."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        monkeypatch.setenv("SUMMARIZER_CALENDAR_IDS", "cal1,cal2")
        config = load_config(config_file)
        assert config.calendars.ids == ["cal1", "cal2"]

    def test_env_output_dir_override(self, monkeypatch, tmp_path: Path):
        """Set SUMMARIZER_OUTPUT_DIR, verify config.pipeline.output_dir reflects it."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        monkeypatch.setenv("SUMMARIZER_OUTPUT_DIR", "/custom/output")
        config = load_config(config_file)
        assert config.pipeline.output_dir == "/custom/output"

    def test_invalid_env_var_fails_validation(self, monkeypatch, tmp_path: Path):
        """Set SUMMARIZER_TIMEZONE='  ' (whitespace), verify it fails validation."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        monkeypatch.setenv("SUMMARIZER_TIMEZONE", "   ")
        with pytest.raises(SystemExit) as exc_info:
            load_config(config_file)
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Error formatting tests
# ---------------------------------------------------------------------------


class TestErrorFormatting:
    """Tests for _format_validation_error producing helpful messages."""

    def test_format_validation_error_fuzzy_suggestion(self):
        """Verify _format_validation_error produces 'Did you mean' for a close typo."""
        try:
            PipelineConfig(slakc={})
        except ValidationError as exc:
            formatted = _format_validation_error(exc)
            assert "Did you mean 'slack'" in formatted

    def test_format_validation_error_multiple_errors(self):
        """Verify multiple errors are all reported (not just the first)."""
        try:
            PipelineConfig(slakc={}, hubspot={"enbled": True})
        except ValidationError as exc:
            formatted = _format_validation_error(exc)
            assert "2 error(s)" in formatted
            assert "slakc" in formatted
            assert "enbled" in formatted

    def test_format_shows_section_example(self):
        """Verify section examples are included in error output."""
        try:
            PipelineConfig(slack={"chnnels": []})
        except ValidationError as exc:
            formatted = _format_validation_error(exc)
            assert "Valid example" in formatted
            assert "slack:" in formatted


# ---------------------------------------------------------------------------
# Test factory tests
# ---------------------------------------------------------------------------


class TestMakeTestConfig:
    """Tests for the make_test_config() convenience factory."""

    def test_make_test_config_defaults(self):
        """make_test_config() returns valid PipelineConfig with all defaults."""
        config = make_test_config()
        assert isinstance(config, PipelineConfig)
        assert config.pipeline.timezone == "America/New_York"

    def test_make_test_config_overrides(self):
        """make_test_config(slack={'enabled': True}) returns config with slack.enabled=True."""
        config = make_test_config(slack={"enabled": True, "channels": ["C123"]})
        assert config.slack.enabled is True
        assert config.slack.channels == ["C123"]
        # Other sections remain default
        assert config.hubspot.enabled is False

    def test_make_test_config_multiple_overrides(self):
        """make_test_config with multiple section overrides."""
        config = make_test_config(
            slack={"enabled": True},
            hubspot={"enabled": True, "max_deals": 10},
            google_docs={"enabled": True},
        )
        assert config.slack.enabled is True
        assert config.hubspot.enabled is True
        assert config.hubspot.max_deals == 10
        assert config.google_docs.enabled is True

    def test_make_test_config_invalid_raises(self):
        """make_test_config with invalid data raises ValidationError."""
        with pytest.raises(ValidationError):
            make_test_config(slack={"thread_min_replies": -1})
