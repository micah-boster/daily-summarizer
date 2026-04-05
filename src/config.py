from __future__ import annotations

import difflib
import logging
import os
import sys
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sub-models (bottom-up order)
# ---------------------------------------------------------------------------


class PipelineSettings(BaseModel):
    """Pipeline-level settings: timezone, output directory."""

    model_config = ConfigDict(extra="forbid")

    timezone: str = "America/New_York"
    output_dir: str = "output"

    @field_validator("timezone", mode="after")
    @classmethod
    def _non_empty_timezone(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("timezone must not be empty")
        return v

    @field_validator("output_dir", mode="after")
    @classmethod
    def _non_empty_output_dir(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("output_dir must not be empty")
        return v


class CalendarsConfig(BaseModel):
    """Calendar ingestion settings."""

    model_config = ConfigDict(extra="forbid")

    ids: list[str] = Field(default_factory=lambda: ["primary"])
    exclude_patterns: list[str] = Field(default_factory=list)

    @field_validator("ids", mode="after")
    @classmethod
    def _non_empty_ids(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("calendars.ids must contain at least one calendar ID")
        return v


class GeminiDriveConfig(BaseModel):
    """Gemini Drive transcript settings."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True


class GeminiTranscriptConfig(BaseModel):
    """Gemini email transcript matching patterns."""

    model_config = ConfigDict(extra="forbid")

    sender_patterns: list[str] = Field(default_factory=list)
    subject_patterns: list[str] = Field(default_factory=list)


class GongTranscriptConfig(BaseModel):
    """Gong email transcript matching patterns."""

    model_config = ConfigDict(extra="forbid")

    sender_patterns: list[str] = Field(default_factory=list)
    subject_patterns: list[str] = Field(default_factory=list)


class TranscriptMatchingConfig(BaseModel):
    """Transcript-to-calendar matching settings."""

    model_config = ConfigDict(extra="forbid")

    time_window_minutes: int = Field(default=30, ge=1)
    include_unmatched_events: bool = True


class TranscriptPreprocessingConfig(BaseModel):
    """Transcript preprocessing settings."""

    model_config = ConfigDict(extra="forbid")

    strip_filler: bool = True


class TranscriptsConfig(BaseModel):
    """Transcript ingestion settings (all sub-sections)."""

    model_config = ConfigDict(extra="forbid")

    gemini_drive: GeminiDriveConfig = Field(default_factory=GeminiDriveConfig)
    gemini: GeminiTranscriptConfig = Field(default_factory=GeminiTranscriptConfig)
    gong: GongTranscriptConfig = Field(default_factory=GongTranscriptConfig)
    matching: TranscriptMatchingConfig = Field(default_factory=TranscriptMatchingConfig)
    preprocessing: TranscriptPreprocessingConfig = Field(
        default_factory=TranscriptPreprocessingConfig
    )


class SynthesisConfig(BaseModel):
    """Claude synthesis settings."""

    model_config = ConfigDict(extra="forbid")

    model: str = "claude-sonnet-4-20250514"
    extraction_max_output_tokens: int = Field(default=4096, ge=1)
    synthesis_max_output_tokens: int = Field(default=8192, ge=1)
    weekly_max_output_tokens: int = Field(default=8192, ge=1)
    monthly_max_output_tokens: int = Field(default=8192, ge=1)
    max_concurrent_extractions: int = Field(default=3, ge=1, le=10)

    @field_validator("model", mode="after")
    @classmethod
    def _non_empty_model(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("synthesis.model must not be empty")
        return v


class SlackFilterConfig(BaseModel):
    """Slack message filtering rules."""

    model_config = ConfigDict(extra="forbid")

    skip_subtypes: list[str] = Field(
        default_factory=lambda: [
            "channel_join",
            "channel_leave",
            "channel_topic",
            "channel_purpose",
            "channel_name",
        ]
    )
    skip_patterns: list[str] = Field(
        default_factory=lambda: [
            r"^(ok|thanks|lol|yes|no|sure|yep|nope|haha|nice)$"
        ]
    )


class SlackConfig(BaseModel):
    """Slack ingestion settings."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    channels: list[str] = Field(default_factory=list)
    dms: list[str] = Field(default_factory=list)
    thread_min_replies: int = Field(default=3, ge=1)
    thread_min_participants: int = Field(default=2, ge=1)
    max_messages_per_channel: int = Field(default=100, ge=1)
    bot_allowlist: list[str] = Field(default_factory=list)
    discovery_check_days: int = Field(default=7, ge=1)
    user_cache_ttl_days: int = Field(default=7, ge=1)
    filter: SlackFilterConfig = Field(default_factory=SlackFilterConfig)


class GoogleDocsConfig(BaseModel):
    """Google Docs ingestion settings."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    content_max_chars: int = Field(default=2500, ge=1)
    comment_max_chars: int = Field(default=500, ge=1)
    max_docs_per_day: int = Field(default=50, ge=1)
    exclude_ids: list[str] = Field(default_factory=list)
    exclude_title_patterns: list[str] = Field(default_factory=list)


class HubSpotConfig(BaseModel):
    """HubSpot CRM ingestion settings."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    ownership_scope: str = "mine"
    owner_id: str | None = None
    max_deals: int = Field(default=50, ge=0)
    max_contacts: int = Field(default=50, ge=0)
    max_tickets: int = Field(default=25, ge=0)
    max_activities_per_type: int = Field(default=25, ge=0)
    portal_url: str = ""


class NotionConfig(BaseModel):
    """Notion ingestion settings."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    token: str = ""
    content_max_chars: int = Field(default=200, ge=50)
    max_pages_per_day: int = Field(default=100, ge=1)
    max_db_items_per_day: int = Field(default=200, ge=1)
    watched_databases: list[str] = Field(default_factory=list)
    notion_version: str = "2022-06-28"


class CacheConfig(BaseModel):
    """Cache retention policy settings."""

    model_config = ConfigDict(extra="forbid")

    raw_ttl_days: int = Field(default=14, ge=1)
    dedup_log_ttl_days: int = Field(default=30, ge=1)


class DedupConfig(BaseModel):
    """Cross-source deduplication pre-filter settings."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    similarity_threshold: float = Field(default=0.85, ge=0.5, le=1.0)
    log_dir: str = "output/dedup_logs"


class EntityConfig(BaseModel):
    """Entity registry settings."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    db_path: str = "data/entities.db"
    auto_create: bool = True


class PipelineConfig(BaseModel):
    """Root configuration model for the daily summarizer pipeline.

    All sections are optional with sensible defaults. Unknown keys are
    rejected at every nesting level (``extra='forbid'``).
    """

    model_config = ConfigDict(extra="forbid")

    pipeline: PipelineSettings = Field(default_factory=PipelineSettings)
    calendars: CalendarsConfig = Field(default_factory=CalendarsConfig)
    transcripts: TranscriptsConfig = Field(default_factory=TranscriptsConfig)
    synthesis: SynthesisConfig = Field(default_factory=SynthesisConfig)
    slack: SlackConfig = Field(default_factory=SlackConfig)
    google_docs: GoogleDocsConfig = Field(default_factory=GoogleDocsConfig)
    hubspot: HubSpotConfig = Field(default_factory=HubSpotConfig)
    notion: NotionConfig = Field(default_factory=NotionConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    dedup: DedupConfig = Field(default_factory=DedupConfig)
    entity: EntityConfig = Field(default_factory=EntityConfig)


# ---------------------------------------------------------------------------
# Section examples for error messages
# ---------------------------------------------------------------------------

SECTION_EXAMPLES: dict[str, str] = {
    "pipeline": 'pipeline:\n  timezone: "America/New_York"\n  output_dir: "output"',
    "calendars": 'calendars:\n  ids:\n    - "primary"\n  exclude_patterns: []',
    "transcripts": "transcripts:\n  gemini_drive:\n    enabled: true\n  matching:\n    time_window_minutes: 30",
    "synthesis": 'synthesis:\n  model: "claude-sonnet-4-20250514"\n  extraction_max_output_tokens: 4096',
    "slack": "slack:\n  enabled: false\n  channels: []\n  thread_min_replies: 3\n  user_cache_ttl_days: 7",
    "google_docs": "google_docs:\n  enabled: false\n  content_max_chars: 2500",
    "hubspot": 'hubspot:\n  enabled: false\n  ownership_scope: "mine"\n  max_deals: 50',
    "notion": 'notion:\n  enabled: false\n  token: ""\n  watched_databases: []',
    "cache": 'cache:\n  raw_ttl_days: 14\n  dedup_log_ttl_days: 30',
    "dedup": 'dedup:\n  enabled: true\n  similarity_threshold: 0.85\n  log_dir: "output/dedup_logs"',
    "entity": 'entity:\n  enabled: true\n  db_path: "data/entities.db"\n  auto_create: true',
}


# ---------------------------------------------------------------------------
# Validation error formatting
# ---------------------------------------------------------------------------


def _get_valid_fields_at(loc: tuple[str | int, ...]) -> list[str]:
    """Walk the model tree to find valid field names at the given location."""
    current_model: type[BaseModel] = PipelineConfig
    for part in loc:
        if isinstance(part, int):
            continue
        if part in current_model.model_fields:
            field_info = current_model.model_fields[part]
            annotation = field_info.annotation
            # Unwrap Optional / Union types
            origin = getattr(annotation, "__origin__", None)
            if origin is not None:
                args = getattr(annotation, "__args__", ())
                for arg in args:
                    if isinstance(arg, type) and issubclass(arg, BaseModel):
                        current_model = arg
                        break
            elif isinstance(annotation, type) and issubclass(annotation, BaseModel):
                current_model = annotation
            else:
                return []
        else:
            # The part itself may be the unknown key -- return valid fields at this level
            return list(current_model.model_fields.keys())
    return list(current_model.model_fields.keys())


def _format_validation_error(exc: ValidationError) -> str:
    """Format a Pydantic ValidationError into a human-readable message.

    - One-line count header
    - Per-error: field path + message
    - For extra_forbidden: fuzzy "Did you mean?" suggestion
    - Section example after each error (if available)
    - All errors reported at once
    """
    errors = exc.errors()
    lines: list[str] = [f"Config invalid: {len(errors)} error(s)\n"]

    for err in errors:
        loc_parts = [str(p) for p in err["loc"]]
        field_path = ".".join(loc_parts)
        msg = err["msg"]
        error_type = err["type"]

        line = f"  - {field_path}: {msg}"

        # Fuzzy suggestion for extra_forbidden errors
        if error_type == "extra_forbidden" and err["loc"]:
            unknown_key = str(err["loc"][-1])
            parent_loc = err["loc"][:-1]
            valid_fields = _get_valid_fields_at(parent_loc)
            matches = difflib.get_close_matches(unknown_key, valid_fields, n=1, cutoff=0.6)
            if matches:
                line += f"  (Did you mean '{matches[0]}'?)"

        lines.append(line)

        # Section example
        top_level = loc_parts[0] if loc_parts else None
        if top_level and top_level in SECTION_EXAMPLES:
            example = SECTION_EXAMPLES[top_level]
            lines.append(f"    Valid example:\n      {example.replace(chr(10), chr(10) + '      ')}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def _load_yaml(config_path: Path) -> dict:
    """Read YAML config file, returning raw dict (empty dict if file missing)."""
    if not config_path.exists():
        return {}
    with open(config_path) as f:
        return yaml.safe_load(f) or {}


def _apply_env_overrides(raw: dict) -> None:
    """Merge environment variable overrides into the raw config dict in place.

    Only the three supported env vars are checked:
    - SUMMARIZER_TIMEZONE -> pipeline.timezone
    - SUMMARIZER_CALENDAR_IDS -> calendars.ids (comma-separated)
    - SUMMARIZER_OUTPUT_DIR -> pipeline.output_dir
    """
    if tz := os.environ.get("SUMMARIZER_TIMEZONE"):
        raw.setdefault("pipeline", {})
        raw["pipeline"]["timezone"] = tz
        logger.debug("Env override: SUMMARIZER_TIMEZONE = %s", tz)

    if cal_ids := os.environ.get("SUMMARIZER_CALENDAR_IDS"):
        raw.setdefault("calendars", {})
        raw["calendars"]["ids"] = [cid.strip() for cid in cal_ids.split(",")]
        logger.debug("Env override: SUMMARIZER_CALENDAR_IDS = %s", cal_ids)

    if output_dir := os.environ.get("SUMMARIZER_OUTPUT_DIR"):
        raw.setdefault("pipeline", {})
        raw["pipeline"]["output_dir"] = output_dir
        logger.debug("Env override: SUMMARIZER_OUTPUT_DIR = %s", output_dir)


def _validate_config(raw: dict) -> PipelineConfig:
    """Validate raw config dict through PipelineConfig, exiting on error."""
    try:
        return PipelineConfig(**raw)
    except ValidationError as exc:
        error_msg = _format_validation_error(exc)
        print(error_msg, file=sys.stderr)
        sys.exit(1)


def load_config(config_path: Path | None = None) -> PipelineConfig:
    """Load pipeline configuration from YAML with environment variable overrides.

    Three-step flow: load YAML -> merge env vars -> validate via Pydantic.

    Args:
        config_path: Path to YAML config file. Defaults to config/config.yaml.

    Returns:
        Validated PipelineConfig model.
    """
    if config_path is None:
        config_path = Path("config/config.yaml")

    raw = _load_yaml(config_path)
    _apply_env_overrides(raw)
    return _validate_config(raw)


# ---------------------------------------------------------------------------
# Test factory
# ---------------------------------------------------------------------------


def make_test_config(**overrides: dict) -> PipelineConfig:
    """Create a PipelineConfig with sensible test defaults.

    Accepts keyword arguments matching top-level section names and merges
    them into defaults.

    Example::

        config = make_test_config(slack={"enabled": True, "channels": ["C123"]})
    """
    defaults: dict = {}
    for key, value in overrides.items():
        if isinstance(value, dict):
            defaults[key] = value
        else:
            defaults[key] = value
    return PipelineConfig(**defaults)
