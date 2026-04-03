"""Stage 1: Per-meeting extraction via Claude API.

Sends each meeting transcript to Claude for structured extraction of
decisions, commitments, substance, open questions, and tensions.
"""

from __future__ import annotations

import logging
import re

import anthropic

from src.models.events import NormalizedEvent
from src.synthesis.models import ExtractionItem, MeetingExtraction
from src.synthesis.prompts import EXTRACTION_PROMPT

logger = logging.getLogger(__name__)

# Default model and token settings
DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_MAX_OUTPUT_TOKENS = 4096


def _parse_section_items(section_text: str, section_type: str) -> list[ExtractionItem]:
    """Parse items from a single extraction section.

    Handles the structured format:
    - **Decision:** content
    - **Participants:** names
    - **Rationale:** reasoning

    Args:
        section_text: Text content of one section (e.g., everything under ## Decisions).
        section_type: One of 'decisions', 'commitments', 'substance', 'open_questions', 'tensions'.

    Returns:
        List of ExtractionItem objects parsed from the section.
    """
    if not section_text.strip() or section_text.strip().lower() == "none":
        return []

    items: list[ExtractionItem] = []

    # Map section types to their primary field label
    primary_labels = {
        "decisions": "Decision",
        "commitments": "Commitment",
        "substance": "Item",
        "open_questions": "Question",
        "tensions": "Tension",
    }
    primary_label = primary_labels.get(section_type, "Item")

    # Split into item blocks by looking for the primary label pattern
    pattern = rf"-\s+\*\*{primary_label}:\*\*"
    blocks = re.split(pattern, section_text)

    for block in blocks[1:]:  # Skip text before first item
        block = block.strip()
        if not block:
            continue

        # Extract content (first line or until next field)
        lines = block.split("\n")
        content = lines[0].strip()

        # Extract participants from various field patterns
        participants: list[str] = []
        rationale: str | None = None

        for line in lines[1:]:
            line = line.strip()
            if not line.startswith("- **"):
                continue

            # Extract field value
            field_match = re.match(r"-\s+\*\*(\w[\w\s]*):\*\*\s*(.*)", line)
            if not field_match:
                continue

            field_name = field_match.group(1).strip().lower()
            field_value = field_match.group(2).strip()

            if field_name in ("participants", "owner", "raised by", "who"):
                participants = [p.strip() for p in field_value.split(",") if p.strip()]
            elif field_name in ("rationale", "context", "status", "deadline"):
                if field_value.lower() != "not stated":
                    rationale = field_value

        if content:
            items.append(
                ExtractionItem(
                    content=content,
                    participants=participants,
                    rationale=rationale,
                )
            )

    return items


def _parse_extraction_response(
    response_text: str,
    meeting_title: str,
    meeting_time: str,
    participants: list[str],
) -> MeetingExtraction:
    """Parse Claude's markdown extraction response into a MeetingExtraction model.

    Args:
        response_text: Claude's full response text in the expected markdown format.
        meeting_title: Title of the meeting being extracted.
        meeting_time: ISO format time string.
        participants: List of participant names.

    Returns:
        MeetingExtraction model populated from the response.
    """
    # Split response by ## headers
    sections: dict[str, str] = {}
    current_section = ""
    current_content: list[str] = []

    for line in response_text.split("\n"):
        if line.startswith("## "):
            if current_section:
                sections[current_section] = "\n".join(current_content)
            current_section = line[3:].strip().lower()
            current_content = []
        else:
            current_content.append(line)

    if current_section:
        sections[current_section] = "\n".join(current_content)

    # Map section names to extraction fields
    section_map = {
        "decisions": "decisions",
        "commitments": "commitments",
        "substance": "substance",
        "open questions": "open_questions",
        "tensions": "tensions",
    }

    parsed: dict[str, list[ExtractionItem]] = {}
    for section_name, field_name in section_map.items():
        section_text = sections.get(section_name, "")
        parsed[field_name] = _parse_section_items(section_text, field_name)

    # Determine if low-signal (all categories empty)
    all_empty = all(len(items) == 0 for items in parsed.values())

    return MeetingExtraction(
        meeting_title=meeting_title,
        meeting_time=meeting_time,
        meeting_participants=participants,
        decisions=parsed.get("decisions", []),
        commitments=parsed.get("commitments", []),
        substance=parsed.get("substance", []),
        open_questions=parsed.get("open_questions", []),
        tensions=parsed.get("tensions", []),
        low_signal=all_empty,
    )


def extract_meeting(
    event: NormalizedEvent,
    config: dict,
) -> MeetingExtraction | None:
    """Extract structured information from a single meeting transcript.

    Sends the transcript to Claude for extraction of decisions, commitments,
    substance, open questions, and tensions.

    Args:
        event: NormalizedEvent with transcript_text attached.
        config: Pipeline configuration dict with synthesis settings.

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
    synthesis_config = config.get("synthesis", {})
    model = synthesis_config.get("model", DEFAULT_MODEL)
    max_tokens = synthesis_config.get("extraction_max_output_tokens", DEFAULT_MAX_OUTPUT_TOKENS)

    # Call Claude API
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    response_text = response.content[0].text

    # Parse response into model
    extraction = _parse_extraction_response(
        response_text, event.title, meeting_time, participants
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
    config: dict,
) -> list[MeetingExtraction]:
    """Extract structured information from all meetings with transcripts.

    Iterates over events, calling extract_meeting for each with a transcript.
    Individual extraction failures are logged and skipped.

    Args:
        events: List of NormalizedEvent objects.
        config: Pipeline configuration dict.

    Returns:
        List of MeetingExtraction objects for events that had transcripts.
    """
    extractions: list[MeetingExtraction] = []
    skipped = 0

    for event in events:
        if not event.transcript_text:
            continue

        try:
            extraction = extract_meeting(event, config)
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
