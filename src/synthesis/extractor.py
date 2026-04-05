"""Stage 1: Per-meeting extraction via Claude API using structured outputs.

Sends each meeting transcript to Claude for structured extraction of
decisions, commitments, substance, open questions, and tensions.
Uses json_schema constrained decoding for guaranteed valid output.
"""

from __future__ import annotations

import asyncio
import json
import logging

import anthropic

from src.config import PipelineConfig
from src.models.events import NormalizedEvent
from src.synthesis.models import (
    ExtractionItem,
    ExtractionItemOutput,
    MeetingExtraction,
    MeetingExtractionOutput,
)
from src.retry import retry_api_call
from src.synthesis.prompts import EXTRACTION_PROMPT

logger = logging.getLogger(__name__)

# Default model and token settings
DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_MAX_OUTPUT_TOKENS = 4096


@retry_api_call
def _call_claude_structured_with_retry(client, model, max_tokens, prompt, schema):
    """Call Claude structured outputs API with retry on transient errors."""
    return client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": schema,
            }
        },
    )


@retry_api_call
def _call_claude_structured_fallback_with_retry(client, model, max_tokens, prompt, schema):
    """Call Claude structured outputs (beta fallback) with retry on transient errors."""
    return client.messages.create(
        model=model,
        max_tokens=max_tokens,
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


def _convert_item(item: ExtractionItemOutput) -> ExtractionItem:
    """Convert an API output item to the downstream ExtractionItem model."""
    return ExtractionItem(
        content=item.content,
        participants=item.participants,
        rationale=item.rationale,
    )


def _convert_output_to_extraction(
    output: MeetingExtractionOutput,
    meeting_title: str,
    meeting_time: str,
    participants: list[str],
) -> MeetingExtraction:
    """Convert structured API output to a MeetingExtraction for downstream use.

    Maps ExtractionItemOutput -> ExtractionItem for each category and adds
    meeting metadata from the event (not from Claude's output).

    Args:
        output: Validated MeetingExtractionOutput from API response.
        meeting_title: Title of the meeting being extracted.
        meeting_time: ISO format time string.
        participants: List of participant names.

    Returns:
        MeetingExtraction model populated from the structured output.
    """
    decisions = [_convert_item(i) for i in output.decisions]
    commitments = [_convert_item(i) for i in output.commitments]
    substance = [_convert_item(i) for i in output.substance]
    open_questions = [_convert_item(i) for i in output.open_questions]
    tensions = [_convert_item(i) for i in output.tensions]

    all_empty = not any([decisions, commitments, substance, open_questions, tensions])

    return MeetingExtraction(
        meeting_title=meeting_title,
        meeting_time=meeting_time,
        meeting_participants=participants,
        decisions=decisions,
        commitments=commitments,
        substance=substance,
        open_questions=open_questions,
        tensions=tensions,
        low_signal=all_empty,
    )


def extract_meeting(
    event: NormalizedEvent,
    config: PipelineConfig,
    client: anthropic.Anthropic | None = None,
) -> MeetingExtraction | None:
    """Extract structured information from a single meeting transcript.

    Sends the transcript to Claude using json_schema structured outputs
    for guaranteed valid JSON. Parses and validates with Pydantic.

    Args:
        event: NormalizedEvent with transcript_text attached.
        config: Pipeline configuration with synthesis settings.
        client: Optional pre-configured Anthropic client.

    Returns:
        MeetingExtraction model, or None if event has no transcript.
    """
    if not event.transcript_text:
        return None

    # Build participant list
    participants = [
        a.name or a.email for a in event.attendees if not a.is_self
    ]
    participants_str = ", ".join(participants) if participants else "Not available"

    # Get meeting time string
    meeting_time = ""
    if event.start_time:
        meeting_time = event.start_time.isoformat()

    # Build prompt
    prompt = EXTRACTION_PROMPT.format(
        meeting_title=event.title,
        meeting_time=meeting_time,
        participants=participants_str,
        transcript_text=event.transcript_text,
    )

    # Get model settings from config
    model = config.synthesis.model
    max_tokens = config.synthesis.extraction_max_output_tokens

    # Generate JSON schema from Pydantic model
    schema = MeetingExtractionOutput.model_json_schema()

    # Call Claude API with structured output
    client = client or anthropic.Anthropic()
    try:
        response = _call_claude_structured_with_retry(
            client, model, max_tokens, prompt, schema
        )
    except (TypeError, anthropic.BadRequestError):
        # Fallback: older SDK or API version may use different parameter
        logger.info("output_config not supported, falling back to beta header")
        response = _call_claude_structured_fallback_with_retry(
            client, model, max_tokens, prompt, schema
        )

    # Parse and validate structured response
    data = json.loads(response.content[0].text)
    output = MeetingExtractionOutput.model_validate(data)

    # Convert to downstream MeetingExtraction model
    extraction = _convert_output_to_extraction(
        output, event.title, meeting_time, participants
    )

    # Log stats
    total_items = (
        len(extraction.decisions)
        + len(extraction.commitments)
        + len(extraction.substance)
        + len(extraction.open_questions)
        + len(extraction.tensions)
    )
    logger.info(
        "Extracted '%s': %d decisions, %d commitments, %d substance, %d questions, %d tensions%s",
        event.title,
        len(extraction.decisions),
        len(extraction.commitments),
        len(extraction.substance),
        len(extraction.open_questions),
        len(extraction.tensions),
        " [low-signal]" if extraction.low_signal else "",
    )

    return extraction


def extract_all_meetings(
    events: list[NormalizedEvent],
    config: PipelineConfig,
    client: anthropic.Anthropic | None = None,
) -> list[MeetingExtraction]:
    """Extract structured information from all meetings with transcripts.

    Iterates over events, calling extract_meeting for each with a transcript.
    Individual extraction failures are logged and skipped.

    Args:
        events: List of NormalizedEvent objects.
        config: Pipeline configuration dict.
        client: Optional pre-configured Anthropic client.

    Returns:
        List of MeetingExtraction objects for events that had transcripts.
    """
    client = client or anthropic.Anthropic()
    extractions: list[MeetingExtraction] = []
    skipped = 0

    for event in events:
        if not event.transcript_text:
            continue

        try:
            extraction = extract_meeting(event, config, client=client)
            if extraction is not None:
                extractions.append(extraction)
        except Exception as e:
            logger.warning("Extraction failed for '%s': %s", event.title, e)
            skipped += 1

    low_signal_count = sum(1 for e in extractions if e.low_signal)
    logger.info(
        "Extracted %d meetings (%d low-signal, %d failed)",
        len(extractions),
        low_signal_count,
        skipped,
    )

    return extractions


# ---------------------------------------------------------------------------
# Async extraction functions
# ---------------------------------------------------------------------------


@retry_api_call
async def _call_claude_structured_async_with_retry(client, model, max_tokens, prompt, schema):
    """Async call to Claude structured outputs API with retry on transient errors."""
    return await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": schema,
            }
        },
    )


@retry_api_call
async def _call_claude_structured_async_fallback_with_retry(
    client, model, max_tokens, prompt, schema
):
    """Async call to Claude structured outputs (beta fallback) with retry."""
    return await client.messages.create(
        model=model,
        max_tokens=max_tokens,
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


async def extract_meeting_async(
    event: NormalizedEvent,
    config: PipelineConfig,
    client: anthropic.AsyncAnthropic,
) -> MeetingExtraction | None:
    """Async version of extract_meeting using AsyncAnthropic client.

    Sends the transcript to Claude using json_schema structured outputs
    for guaranteed valid JSON. Parses and validates with Pydantic.

    Args:
        event: NormalizedEvent with transcript_text attached.
        config: Pipeline configuration with synthesis settings.
        client: Pre-configured AsyncAnthropic client.

    Returns:
        MeetingExtraction model, or None if event has no transcript.
    """
    if not event.transcript_text:
        return None

    # Build participant list
    participants = [
        a.name or a.email for a in event.attendees if not a.is_self
    ]
    participants_str = ", ".join(participants) if participants else "Not available"

    # Get meeting time string
    meeting_time = ""
    if event.start_time:
        meeting_time = event.start_time.isoformat()

    # Build prompt
    prompt = EXTRACTION_PROMPT.format(
        meeting_title=event.title,
        meeting_time=meeting_time,
        participants=participants_str,
        transcript_text=event.transcript_text,
    )

    # Get model settings from config
    model = config.synthesis.model
    max_tokens = config.synthesis.extraction_max_output_tokens

    # Generate JSON schema from Pydantic model
    schema = MeetingExtractionOutput.model_json_schema()

    # Call Claude API with structured output (async)
    try:
        response = await _call_claude_structured_async_with_retry(
            client, model, max_tokens, prompt, schema
        )
    except (TypeError, anthropic.BadRequestError):
        # Fallback: older SDK or API version may use different parameter
        logger.info("output_config not supported, falling back to beta header")
        response = await _call_claude_structured_async_fallback_with_retry(
            client, model, max_tokens, prompt, schema
        )

    # Parse and validate structured response
    data = json.loads(response.content[0].text)
    output = MeetingExtractionOutput.model_validate(data)

    # Convert to downstream MeetingExtraction model
    extraction = _convert_output_to_extraction(
        output, event.title, meeting_time, participants
    )

    # Log stats
    total_items = (
        len(extraction.decisions)
        + len(extraction.commitments)
        + len(extraction.substance)
        + len(extraction.open_questions)
        + len(extraction.tensions)
    )
    logger.info(
        "Extracted '%s': %d decisions, %d commitments, %d substance, %d questions, %d tensions%s",
        event.title,
        len(extraction.decisions),
        len(extraction.commitments),
        len(extraction.substance),
        len(extraction.open_questions),
        len(extraction.tensions),
        " [low-signal]" if extraction.low_signal else "",
    )

    return extraction


async def extract_all_meetings_async(
    events: list[NormalizedEvent],
    config: PipelineConfig,
    client: anthropic.AsyncAnthropic,
) -> list[MeetingExtraction]:
    """Async version of extract_all_meetings with concurrent execution.

    Creates an asyncio.Semaphore to limit concurrent Claude API calls,
    then runs all extractions concurrently via asyncio.gather. Individual
    extraction failures are caught and logged, not propagated.

    Args:
        events: List of NormalizedEvent objects.
        config: Pipeline configuration with synthesis settings.
        client: Pre-configured AsyncAnthropic client.

    Returns:
        List of MeetingExtraction objects for events that had transcripts.
    """
    sem = asyncio.Semaphore(config.synthesis.max_concurrent_extractions)

    async def _guarded_extract(event: NormalizedEvent) -> MeetingExtraction | None:
        async with sem:
            return await extract_meeting_async(event, config, client)

    # Only create tasks for events with transcripts
    tasks_with_events = [
        (event, asyncio.ensure_future(_guarded_extract(event)))
        for event in events
        if event.transcript_text
    ]

    if not tasks_with_events:
        logger.info("Extracted 0 meetings (0 low-signal, 0 failed)")
        return []

    # Gather all results, capturing exceptions instead of raising
    task_futures = [t for _, t in tasks_with_events]
    results = await asyncio.gather(*task_futures, return_exceptions=True)

    extractions: list[MeetingExtraction] = []
    skipped = 0

    for (event, _), result in zip(tasks_with_events, results):
        if isinstance(result, BaseException):
            logger.warning("Extraction failed for '%s': %s", event.title, result)
            skipped += 1
        elif result is not None:
            extractions.append(result)

    low_signal_count = sum(1 for e in extractions if e.low_signal)
    logger.info(
        "Extracted %d meetings (%d low-signal, %d failed)",
        len(extractions),
        low_signal_count,
        skipped,
    )

    return extractions
