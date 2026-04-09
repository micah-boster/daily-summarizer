"""Entity extraction from synthesis text via Claude structured outputs.

Extracts companies/organizations (type "partner") and individual people
(type "person") from daily synthesis output using constrained JSON decoding.
"""

from __future__ import annotations

import json
import logging

import anthropic
from pydantic import BaseModel, ConfigDict, Field

from src.config import PipelineConfig
from src.retry import retry_api_call
from src.schema_utils import prepare_schema_for_claude

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class DiscoveredEntity(BaseModel):
    """An entity discovered in synthesis text."""

    model_config = ConfigDict(extra="forbid")

    name: str
    entity_type: str  # "partner" or "person"
    confidence: float  # 0.0-1.0


class EntityExtractionOutput(BaseModel):
    """Structured output model for Claude entity extraction."""

    model_config = ConfigDict(extra="forbid")

    reasoning: str = ""
    entities: list[DiscoveredEntity] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

ENTITY_EXTRACTION_PROMPT = """Extract all companies, organizations, and individual people mentioned in the following synthesis text.

For each entity:
- name: The FULL name including last name whenever possible. If the text says "Colin" but context makes clear this is "Colin Roberts", use "Colin Roberts". Always prefer "FirstName LastName" over just "FirstName". Look at meeting titles, attendee lists, and context clues to infer last names. If only a first name is available, use just the first name.
- entity_type: MUST be one of "partner" or "person"
  - "person": ANY individual human being (e.g., "Colin Roberts", "Ohad Levy", "Shannon"). If it's a person's name, it is ALWAYS type "person" — even if they work at a partner company.
  - "partner": ONLY companies, organizations, or products being discussed as business partners (e.g., "HubSpot", "Corecard")
- confidence: 1.0 for explicitly named, 0.7 for contextually inferred, 0.4 for ambiguous

CRITICAL: Individual people are NEVER type "partner". "Colin Roberts" is a person. "HubSpot" is a partner. Do not confuse a person who works at a partner with the partner company itself.

EXCLUDE:
- Internal team names (e.g., "engineering team", "product team")
- Software tools and vendors you USE but don't do business WITH (e.g., "Slack", "Notion", "Jira", "Metabase", "HubSpot" unless HubSpot is an actual business partner being discussed). If it's a tool in your tech stack, exclude it.
- Product features or modules within tools (e.g., "ServiceHub", "MarketingHub", "Partner Hub")
- Geographic locations, cities, states, event venues (e.g., "Delaware", "Wilmington", "New York")
- Generic groups (e.g., "the board", "investors", "stakeholders")
- Meeting room names
- Your own organization's name

Use the reasoning field to think through which names are entities before listing them.

Text to extract from:
{text}
"""


# ---------------------------------------------------------------------------
# API call with retry
# ---------------------------------------------------------------------------


@retry_api_call
def _call_claude_entity_extraction(client, model, max_tokens, prompt, schema):
    """Call Claude structured outputs API for entity extraction with retry."""
    return client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
        tools=[{"name": "output", "description": "Structured output", "input_schema": schema}],
        tool_choice={"type": "tool", "name": "output"},
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_entities(
    text: str,
    config: PipelineConfig,
    client: anthropic.Anthropic | None = None,
) -> list[DiscoveredEntity]:
    """Extract entities from synthesis text using Claude structured outputs.

    Args:
        text: Synthesis text to extract entities from.
        config: Pipeline configuration (uses synthesis.model).
        client: Optional pre-configured Anthropic client.

    Returns:
        List of DiscoveredEntity objects. Empty list on any failure
        (graceful degradation -- extraction failure should NOT block pipeline).
    """
    if not text or not text.strip():
        return []

    try:
        client = client or anthropic.Anthropic()
        model = config.synthesis.model

        prompt = ENTITY_EXTRACTION_PROMPT.format(text=text)
        schema = prepare_schema_for_claude(EntityExtractionOutput.model_json_schema())

        response = _call_claude_entity_extraction(
            client, model, 1024, prompt, schema
        )

        # Tool-based structured output returns input dict directly
        data = response.content[0].input
        output = EntityExtractionOutput.model_validate(data)

        logger.info("Extracted %d entities from text", len(output.entities))
        return output.entities

    except Exception as e:
        logger.warning("Entity extraction failed: %s. Returning empty list.", e)
        return []
