"""Structured commitment extraction via Claude structured outputs.

Second-stage extraction: takes the already-synthesized daily summary text
and extracts commitments as guaranteed-valid JSON using constrained decoding.
"""
from __future__ import annotations

import json
import logging
from datetime import date

import anthropic
from pydantic import BaseModel, ConfigDict, Field

from src.config import PipelineConfig
from src.retry import retry_api_call

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-20250514"


@retry_api_call
def _call_claude_structured_with_retry(client, model, prompt, schema):
    """Call Claude structured outputs API with retry on transient errors."""
    return client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": schema,
            }
        },
    )


@retry_api_call
def _call_claude_structured_fallback_with_retry(client, model, prompt, schema):
    """Call Claude structured outputs (beta fallback) with retry on transient errors."""
    return client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
        extra_headers={
            "anthropic-beta": "output-format-2025-01-24",
        },
        extra_body={
            "output_format": {
                "type": "json_schema",
                "schema": schema,
            }
        },
    )


class ExtractedCommitment(BaseModel):
    """A single commitment extracted from synthesis output."""

    model_config = ConfigDict(extra="forbid")

    who: str  # Person name, or "TBD" if unclear
    what: str  # Commitment description
    by_when: str  # ISO date, "week of YYYY-MM-DD", or "unspecified"
    source: list[str]  # e.g. ["standup", "Slack #proj-alpha"]


class CommitmentsOutput(BaseModel):
    """Container for extracted commitments, used with Claude structured outputs."""

    model_config = ConfigDict(extra="forbid")

    commitments: list[ExtractedCommitment] = Field(default_factory=list)


COMMITMENT_EXTRACTION_PROMPT = """Extract ALL explicit commitments from this daily summary.

Date context: {target_date}

A commitment is when someone EXPLICITLY says they will do something:
- "I'll send the deck by Friday" -> YES
- "John will follow up with the vendor" -> YES
- "John agreed to review the proposal" -> YES
- "We should probably look into that" -> NO (suggestion, not commitment)
- "The report needs updating" -> NO (observation, no owner committed)
- "It would be good to schedule a review" -> NO (suggestion)

For each commitment:
- who: The person who committed. Use first name. If unclear, use "TBD".
- what: What they committed to do. Be concise.
- by_when: Normalize deadlines relative to {target_date}:
  - "by Friday" -> the next Friday's ISO date
  - "next week" -> "week of YYYY-MM-DD" (Monday of next week)
  - "end of day" -> "{target_date}"
  - "soon" or no deadline stated -> "unspecified"
- source: Array of source attributions exactly as they appear in the text (e.g., "standup", "Slack #proj-alpha", "HubSpot deal Acme Renewal")

RULES:
- Extract EVERYONE's commitments, not just the user's
- If the SAME commitment appears attributed to multiple sources, list it ONCE with all sources
- Include partial commitments with gaps marked (who="TBD", by_when="unspecified")
- Do NOT invent commitments that aren't explicitly stated
- Do NOT extract suggestions, observations, or implied obligations

Summary to extract from:
{synthesis_text}
"""


def extract_commitments(
    synthesis_text: str,
    target_date: date,
    config: PipelineConfig,
    client: anthropic.Anthropic | None = None,
) -> list[ExtractedCommitment]:
    """Extract structured commitments from synthesized daily summary text.

    Makes a second Claude API call using structured outputs to guarantee
    valid JSON schema conformance. Operates on already-synthesized text
    (small input), so the call is lightweight.

    Args:
        synthesis_text: The full synthesized daily summary text.
        target_date: The date being synthesized (anchor for relative dates).
        config: Pipeline configuration dict.

    Returns:
        List of ExtractedCommitment objects. Empty list on any error
        (graceful degradation -- extraction failure should NOT block pipeline).
    """
    if not synthesis_text or not synthesis_text.strip():
        return []

    try:
        client = client or anthropic.Anthropic()
        model = config.synthesis.model

        prompt = COMMITMENT_EXTRACTION_PROMPT.format(
            target_date=target_date.isoformat(),
            synthesis_text=synthesis_text,
        )

        schema = CommitmentsOutput.model_json_schema()

        # Use output_config for structured outputs (GA)
        try:
            response = _call_claude_structured_with_retry(
                client, model, prompt, schema
            )
        except (TypeError, anthropic.BadRequestError):
            # Fallback: older SDK or API version may use different parameter
            logger.info("output_config not supported, falling back to betas header")
            response = _call_claude_structured_fallback_with_retry(
                client, model, prompt, schema
            )

        data = json.loads(response.content[0].text)
        result = CommitmentsOutput.model_validate(data)

        logger.info("Extracted %d structured commitments", len(result.commitments))
        return result.commitments

    except Exception as e:
        logger.warning(
            "Commitment extraction failed: %s. Continuing without structured commitments.",
            e,
        )
        return []
