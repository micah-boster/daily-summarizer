"""Tests for entity discovery: extraction models, Claude-based extraction."""

from __future__ import annotations

import json
import logging
from unittest.mock import MagicMock, patch

import pytest

from src.config import make_test_config
from src.entity.discovery import (
    ENTITY_EXTRACTION_PROMPT,
    DiscoveredEntity,
    EntityExtractionOutput,
    extract_entities,
)


# --- Model validation tests ---


def test_discovered_entity_validates():
    """DiscoveredEntity accepts valid data."""
    entity = DiscoveredEntity(name="Affirm Inc", entity_type="partner", confidence=1.0)
    assert entity.name == "Affirm Inc"
    assert entity.entity_type == "partner"
    assert entity.confidence == 1.0


def test_discovered_entity_person():
    """DiscoveredEntity works with person type."""
    entity = DiscoveredEntity(name="Colin Roberts", entity_type="person", confidence=0.7)
    assert entity.entity_type == "person"


def test_entity_extraction_output_validates():
    """EntityExtractionOutput validates with reasoning + entities."""
    output = EntityExtractionOutput(
        reasoning="Found two entities",
        entities=[
            DiscoveredEntity(name="Affirm Inc", entity_type="partner", confidence=1.0),
            DiscoveredEntity(name="Colin Roberts", entity_type="person", confidence=0.7),
        ],
    )
    assert len(output.entities) == 2
    assert output.reasoning == "Found two entities"


def test_entity_extraction_output_empty():
    """EntityExtractionOutput works with no entities."""
    output = EntityExtractionOutput(reasoning="No entities found", entities=[])
    assert len(output.entities) == 0


# --- extract_entities tests ---


def test_extract_entities_empty_text():
    """Empty text returns empty list without API call."""
    config = make_test_config()
    result = extract_entities("", config)
    assert result == []


def test_extract_entities_whitespace_only():
    """Whitespace-only text returns empty list."""
    config = make_test_config()
    result = extract_entities("   ", config)
    assert result == []


def test_extract_entities_with_mock_response():
    """Mocked Claude response returns parsed entities."""
    config = make_test_config()

    mock_response_data = {
        "reasoning": "Found Affirm and Colin",
        "entities": [
            {"name": "Affirm Inc", "entity_type": "partner", "confidence": 1.0},
            {"name": "Colin Roberts", "entity_type": "person", "confidence": 0.7},
        ],
    }

    mock_response = MagicMock()
    mock_response.content = [MagicMock(input=mock_response_data)]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    result = extract_entities("Discussed Affirm Inc deal with Colin Roberts", config, client=mock_client)

    assert len(result) == 2
    assert result[0].name == "Affirm Inc"
    assert result[0].entity_type == "partner"
    assert result[1].name == "Colin Roberts"
    assert result[1].entity_type == "person"


def test_extract_entities_api_failure_returns_empty(caplog):
    """API failure returns empty list and logs warning."""
    config = make_test_config()

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception("API error")

    with caplog.at_level(logging.WARNING):
        result = extract_entities("Some text about entities", config, client=mock_client)

    assert result == []
    assert any("Entity extraction failed" in record.message for record in caplog.records)


def test_extraction_prompt_has_placeholder():
    """The extraction prompt contains the {text} placeholder."""
    assert "{text}" in ENTITY_EXTRACTION_PROMPT


def test_extract_entities_no_entities_response():
    """Claude response with no entities returns empty list."""
    config = make_test_config()

    mock_response_data = {
        "reasoning": "No entities found in this text",
        "entities": [],
    }

    mock_response = MagicMock()
    mock_response.content = [MagicMock(input=mock_response_data)]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    result = extract_entities("Just a general discussion about strategy", config, client=mock_client)
    assert result == []
