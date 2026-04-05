"""Tests for entity Pydantic models and EntityConfig.

Covers: Entity creation, metadata JSON deserialization, EntityType enum,
Alias model, EntityMention confidence bounds, ConfidenceLevel constants,
EntityConfig defaults, PipelineConfig integration.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from src.config import EntityConfig, PipelineConfig, make_test_config
from src.entity.models import (
    Alias,
    ConfidenceLevel,
    Entity,
    EntityMention,
    EntityType,
    MergeProposal,
    _now_utc,
)


# ---------------------------------------------------------------------------
# Entity model tests
# ---------------------------------------------------------------------------


class TestEntity:
    """Tests for the Entity model."""

    def test_create_entity_with_valid_fields(self):
        """Entity with all required fields creates successfully."""
        now = _now_utc()
        entity = Entity(
            id="abc123",
            name="Affirm",
            entity_type=EntityType.PARTNER,
            created_at=now,
            updated_at=now,
        )
        assert entity.id == "abc123"
        assert entity.name == "Affirm"
        assert entity.entity_type == EntityType.PARTNER
        assert entity.metadata == {}
        assert entity.is_deleted is False

    def test_entity_metadata_dict_roundtrip(self):
        """Entity with metadata dict preserves it correctly."""
        now = _now_utc()
        meta = {"industry": "fintech", "tier": 1}
        entity = Entity(
            id="abc123",
            name="Affirm",
            entity_type=EntityType.PARTNER,
            metadata=meta,
            created_at=now,
            updated_at=now,
        )
        assert entity.metadata == meta
        assert isinstance(entity.metadata, dict)

    def test_entity_metadata_json_string_deserialized(self):
        """Entity with metadata as JSON string (from SQLite) deserializes to dict."""
        now = _now_utc()
        meta_str = '{"industry": "fintech", "tier": 1}'
        entity = Entity(
            id="abc123",
            name="Affirm",
            entity_type=EntityType.PARTNER,
            metadata=meta_str,
            created_at=now,
            updated_at=now,
        )
        assert entity.metadata == {"industry": "fintech", "tier": 1}
        assert isinstance(entity.metadata, dict)

    def test_entity_metadata_none_becomes_empty_dict(self):
        """Entity with metadata=None gets empty dict."""
        now = _now_utc()
        entity = Entity(
            id="abc123",
            name="Affirm",
            entity_type=EntityType.PARTNER,
            metadata=None,
            created_at=now,
            updated_at=now,
        )
        assert entity.metadata == {}

    def test_entity_is_deleted_property(self):
        """is_deleted returns True when deleted_at is set."""
        now = _now_utc()
        entity = Entity(
            id="abc123",
            name="Affirm",
            entity_type=EntityType.PARTNER,
            deleted_at=now,
            created_at=now,
            updated_at=now,
        )
        assert entity.is_deleted is True


# ---------------------------------------------------------------------------
# EntityType enum tests
# ---------------------------------------------------------------------------


class TestEntityType:
    """Tests for the EntityType enum."""

    def test_has_expected_values(self):
        """EntityType has partner, person, initiative."""
        assert EntityType.PARTNER == "partner"
        assert EntityType.PERSON == "person"
        assert EntityType.INITIATIVE == "initiative"

    def test_all_values(self):
        """EntityType has exactly three values."""
        assert set(EntityType) == {"partner", "person", "initiative"}


# ---------------------------------------------------------------------------
# Alias model tests
# ---------------------------------------------------------------------------


class TestAlias:
    """Tests for the Alias model."""

    def test_create_alias(self):
        """Alias with valid fields creates successfully."""
        now = _now_utc()
        alias = Alias(id="a1", entity_id="e1", alias="CR", created_at=now)
        assert alias.alias == "CR"
        assert alias.entity_id == "e1"


# ---------------------------------------------------------------------------
# EntityMention tests
# ---------------------------------------------------------------------------


class TestEntityMention:
    """Tests for EntityMention confidence bounds."""

    def test_default_confidence(self):
        """EntityMention defaults to confidence 1.0."""
        now = _now_utc()
        mention = EntityMention(
            id="m1",
            entity_id="e1",
            source_type="calendar",
            source_id="cal-123",
            source_date="2026-04-05",
            created_at=now,
        )
        assert mention.confidence == 1.0

    def test_confidence_at_bounds(self):
        """EntityMention accepts confidence at 0.0 and 1.0."""
        now = _now_utc()
        low = EntityMention(
            id="m1",
            entity_id="e1",
            source_type="calendar",
            source_id="cal-123",
            source_date="2026-04-05",
            confidence=0.0,
            created_at=now,
        )
        assert low.confidence == 0.0

        high = EntityMention(
            id="m2",
            entity_id="e1",
            source_type="calendar",
            source_id="cal-456",
            source_date="2026-04-05",
            confidence=1.0,
            created_at=now,
        )
        assert high.confidence == 1.0

    def test_confidence_out_of_range_rejected(self):
        """EntityMention rejects confidence outside [0.0, 1.0]."""
        now = _now_utc()
        with pytest.raises(ValidationError):
            EntityMention(
                id="m1",
                entity_id="e1",
                source_type="calendar",
                source_id="cal-123",
                source_date="2026-04-05",
                confidence=1.5,
                created_at=now,
            )
        with pytest.raises(ValidationError):
            EntityMention(
                id="m2",
                entity_id="e1",
                source_type="calendar",
                source_id="cal-456",
                source_date="2026-04-05",
                confidence=-0.1,
                created_at=now,
            )


# ---------------------------------------------------------------------------
# ConfidenceLevel tests
# ---------------------------------------------------------------------------


class TestConfidenceLevel:
    """Tests for ConfidenceLevel constants."""

    def test_constants_are_correct_floats(self):
        """ConfidenceLevel has expected float values."""
        assert ConfidenceLevel.HIGH == 1.0
        assert ConfidenceLevel.MEDIUM == 0.7
        assert ConfidenceLevel.LOW == 0.4
        assert ConfidenceLevel.FUZZY == 0.2


# ---------------------------------------------------------------------------
# EntityConfig / PipelineConfig integration tests
# ---------------------------------------------------------------------------


class TestEntityConfig:
    """Tests for EntityConfig defaults and PipelineConfig integration."""

    def test_defaults(self):
        """EntityConfig has expected defaults."""
        cfg = EntityConfig()
        assert cfg.enabled is True
        assert cfg.db_path == "data/entities.db"
        assert cfg.auto_create is True

    def test_pipeline_config_with_entity_section(self):
        """PipelineConfig includes entity section with defaults."""
        cfg = PipelineConfig()
        assert hasattr(cfg, "entity")
        assert cfg.entity.enabled is True
        assert cfg.entity.db_path == "data/entities.db"

    def test_pipeline_config_rejects_unknown_entity_subfields(self):
        """PipelineConfig rejects unknown fields in entity section."""
        with pytest.raises(ValidationError):
            PipelineConfig(entity={"enabled": True, "unknown_field": "bad"})

    def test_make_test_config_with_entity(self):
        """make_test_config accepts entity overrides."""
        cfg = make_test_config(entity={"db_path": "/tmp/test.db"})
        assert cfg.entity.db_path == "/tmp/test.db"
        assert cfg.entity.enabled is True  # default preserved

    def test_existing_config_no_regression(self):
        """PipelineConfig still validates all existing sections."""
        cfg = PipelineConfig()
        assert cfg.pipeline.timezone == "America/New_York"
        assert cfg.calendars.ids == ["primary"]
        assert cfg.slack.enabled is False
        assert cfg.dedup.enabled is True
