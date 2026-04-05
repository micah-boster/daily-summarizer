"""Pydantic models for the entity registry.

Defines Entity, Alias, EntityMention, MergeProposal, and ConfidenceLevel
used throughout the entity subsystem. All timestamp fields use ISO-8601
strings generated in Python via ``_now_utc()``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_utc() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EntityType(StrEnum):
    """Supported entity types."""

    PARTNER = "partner"
    PERSON = "person"
    INITIATIVE = "initiative"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class Entity(BaseModel):
    """A canonical entity (partner, person, or initiative)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    entity_type: EntityType
    organization_id: str | None = None
    hubspot_id: str | None = None
    slack_channel: str | None = None
    metadata: dict = Field(default_factory=dict)
    merge_target_id: str | None = None
    created_at: str
    updated_at: str
    deleted_at: str | None = None

    @field_validator("metadata", mode="before")
    @classmethod
    def _deserialize_metadata(cls, v: object) -> dict:
        """Accept a JSON string (from SQLite TEXT column) and parse to dict."""
        if isinstance(v, str):
            return json.loads(v)
        if v is None:
            return {}
        return v

    @property
    def is_deleted(self) -> bool:
        """Return ``True`` when the entity has been soft-deleted."""
        return self.deleted_at is not None


class Alias(BaseModel):
    """An alternative name that resolves to a canonical entity."""

    model_config = ConfigDict(extra="forbid")

    id: str
    entity_id: str
    alias: str
    created_at: str


class EntityMention(BaseModel):
    """A recorded mention of an entity in a source document."""

    model_config = ConfigDict(extra="forbid")

    id: str
    entity_id: str
    source_type: str
    source_id: str
    source_date: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    context_snippet: str | None = None
    created_at: str


class MergeProposal(BaseModel):
    """A proposal to merge two entities."""

    model_config = ConfigDict(extra="forbid")

    id: str
    source_entity_id: str
    target_entity_id: str
    proposed_by: str = "system"
    reason: str | None = None
    status: str = "pending"
    created_at: str
    resolved_at: str | None = None


class ConfidenceLevel:
    """Confidence level constants for entity mentions.

    * HIGH (1.0)   -- Direct attribution: "Colin said..."
    * MEDIUM (0.7)  -- Contextual: mentioned in meeting with known attendees
    * LOW (0.4)    -- Ambient: name appears in text without clear attribution
    * FUZZY (0.2)  -- Alias match or partial name match
    """

    HIGH: float = 1.0
    MEDIUM: float = 0.7
    LOW: float = 0.4
    FUZZY: float = 0.2
