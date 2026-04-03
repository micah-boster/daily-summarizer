"""Transcript parsing: Gemini and Gong email transcript extraction with filler stripping."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime

from dateutil.parser import parse as dateutil_parse

from src.ingest.gmail import (
    build_transcript_query,
    extract_body_text,
    extract_headers,
    get_message_content,
    search_messages,
)

logger = logging.getLogger(__name__)

# Filler word patterns for transcript preprocessing
FILLER_PATTERNS: list[str] = [
    r"\b(?:um|uh|ah|er|mm|hmm|hm)\b",
    r"\b(?:like,?\s+)?you know,?\s*",
    r"\b(?:I mean,?\s*)",
    r"\b(\w+)\s+\1\b",  # repeated words: "the the" -> "the"
]

# Prefixes to strip from email subjects to extract meeting title
GEMINI_SUBJECT_PREFIXES = [
    r"^Transcript\s+for\s+",
    r"^Meeting\s+notes:\s*",
    r"^Notes\s+from\s+",
    r"^Transcript:\s*",
    r"^Re:\s*",
    r"^Fwd:\s*",
]


def strip_filler(text: str) -> str:
    """Remove filler words and repeated phrases from transcript text.

    Strips common verbal fillers (um, uh, ah, er, etc.), conversational
    padding (you know, I mean), and repeated consecutive words.

    Args:
        text: Raw transcript text.

    Returns:
        Cleaned text with fillers removed and whitespace collapsed.
    """
    for pattern in FILLER_PATTERNS:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    # Collapse multiple spaces
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text


def _extract_title_from_subject(subject: str) -> str:
    """Extract meeting title from email subject line.

    Strips common Gemini/Google prefixes like 'Transcript for', 'Meeting notes:'.

    Args:
        subject: Email subject line.

    Returns:
        Cleaned meeting title.
    """
    title = subject.strip()
    for prefix_pattern in GEMINI_SUBJECT_PREFIXES:
        title = re.sub(prefix_pattern, "", title, flags=re.IGNORECASE).strip()
    return title or subject.strip()


def parse_gemini_transcript(message: dict, config: dict) -> dict | None:
    """Parse a Gmail message into a Gemini transcript dict.

    Extracts meeting title from subject, datetime from headers, and
    body text with optional filler stripping.

    Args:
        message: Full Gmail message dict (from get_message_content).
        config: Pipeline configuration dict.

    Returns:
        Transcript dict with keys: source, title, meeting_time, transcript_text,
        raw_email, message_id. Returns None if body is empty.
    """
    headers = extract_headers(message)
    body = extract_body_text(message)

    if not body.strip():
        logger.debug("Empty body for message %s, skipping", message.get("id"))
        return None

    # Parse meeting title from subject
    title = _extract_title_from_subject(headers.get("subject", ""))

    # Parse meeting datetime from email Date header
    meeting_time: datetime | None = None
    date_str = headers.get("date", "")
    if date_str:
        try:
            meeting_time = dateutil_parse(date_str)
        except (ValueError, OverflowError):
            logger.warning("Could not parse date header: %s", date_str)

    # Apply filler stripping if configured
    preprocessing = config.get("transcripts", {}).get("preprocessing", {})
    if preprocessing.get("strip_filler", True):
        body = strip_filler(body)

    return {
        "source": "gemini",
        "title": title,
        "meeting_time": meeting_time,
        "transcript_text": body,
        "raw_email": message,
        "message_id": message.get("id", ""),
    }


def fetch_gemini_transcripts(
    service, target_date: date, config: dict
) -> list[dict]:
    """Fetch and parse all Gemini transcript emails for a target date.

    Args:
        service: Gmail API service instance.
        target_date: The date to search for transcripts.
        config: Pipeline configuration dict with transcripts.gemini settings.

    Returns:
        List of parsed transcript dicts.
    """
    gemini_config = config.get("transcripts", {}).get("gemini", {})
    sender_patterns = gemini_config.get("sender_patterns", [])
    subject_patterns = gemini_config.get("subject_patterns", [])

    if not sender_patterns or not subject_patterns:
        logger.warning("No Gemini sender/subject patterns configured, skipping")
        return []

    query = build_transcript_query(sender_patterns, subject_patterns, target_date)
    logger.info("Searching Gemini transcripts: %s", query)

    message_stubs = search_messages(service, query)
    logger.info("Found %d candidate Gemini emails for %s", len(message_stubs), target_date)

    transcripts: list[dict] = []
    for stub in message_stubs:
        try:
            full_message = get_message_content(service, stub["id"])
            parsed = parse_gemini_transcript(full_message, config)
            if parsed:
                transcripts.append(parsed)
        except Exception as e:
            logger.warning("Failed to parse Gemini email %s: %s", stub.get("id"), e)

    logger.info("Found %d Gemini transcripts for %s", len(transcripts), target_date)
    return transcripts


# --- Gong transcript parsing ---

# Prefixes to strip from Gong email subjects to extract call title
GONG_SUBJECT_PREFIXES = [
    r"^Call\s+with\s+",
    r"^Conversation:\s*",
    r"^Your\s+call\s+with\s+",
    r"^Call\s+recording:\s*",
    r"^Call\s+summary:\s*",
    r"^Re:\s*",
    r"^Fwd:\s*",
]


def _extract_gong_title_from_subject(subject: str) -> str:
    """Extract call title from Gong notification email subject.

    Strips common Gong prefixes like 'Call with', 'Conversation:'.

    Args:
        subject: Email subject line.

    Returns:
        Cleaned call/meeting title.
    """
    title = subject.strip()
    for prefix_pattern in GONG_SUBJECT_PREFIXES:
        title = re.sub(prefix_pattern, "", title, flags=re.IGNORECASE).strip()
    return title or subject.strip()


def parse_gong_transcript(message: dict, config: dict) -> dict | None:
    """Parse a Gong notification email into a transcript dict.

    Extracts call title from subject, datetime from headers, and
    summary text from body with optional filler stripping.

    Args:
        message: Full Gmail message dict (from get_message_content).
        config: Pipeline configuration dict.

    Returns:
        Transcript dict with keys: source, title, meeting_time, transcript_text,
        raw_email, message_id. Returns None if body is empty.
    """
    headers = extract_headers(message)
    body = extract_body_text(message)

    if not body.strip():
        logger.debug("Empty body for Gong message %s, skipping", message.get("id"))
        return None

    # Parse call title from subject
    title = _extract_gong_title_from_subject(headers.get("subject", ""))

    # Parse meeting datetime from email Date header
    meeting_time: datetime | None = None
    date_str = headers.get("date", "")
    if date_str:
        try:
            meeting_time = dateutil_parse(date_str)
        except (ValueError, OverflowError):
            logger.warning("Could not parse Gong date header: %s", date_str)

    # Apply filler stripping if configured
    preprocessing = config.get("transcripts", {}).get("preprocessing", {})
    if preprocessing.get("strip_filler", True):
        body = strip_filler(body)

    return {
        "source": "gong",
        "title": title,
        "meeting_time": meeting_time,
        "transcript_text": body,
        "raw_email": message,
        "message_id": message.get("id", ""),
    }


def fetch_gong_transcripts(
    service, target_date: date, config: dict
) -> list[dict]:
    """Fetch and parse all Gong transcript emails for a target date.

    Args:
        service: Gmail API service instance.
        target_date: The date to search for transcripts.
        config: Pipeline configuration dict with transcripts.gong settings.

    Returns:
        List of parsed transcript dicts.
    """
    gong_config = config.get("transcripts", {}).get("gong", {})
    sender_patterns = gong_config.get("sender_patterns", [])
    subject_patterns = gong_config.get("subject_patterns", [])

    if not sender_patterns or not subject_patterns:
        logger.warning("No Gong sender/subject patterns configured, skipping")
        return []

    query = build_transcript_query(sender_patterns, subject_patterns, target_date)
    logger.info("Searching Gong transcripts: %s", query)

    message_stubs = search_messages(service, query)
    logger.info("Found %d candidate Gong emails for %s", len(message_stubs), target_date)

    transcripts: list[dict] = []
    for stub in message_stubs:
        try:
            full_message = get_message_content(service, stub["id"])
            parsed = parse_gong_transcript(full_message, config)
            if parsed:
                transcripts.append(parsed)
        except Exception as e:
            logger.warning("Failed to parse Gong email %s: %s", stub.get("id"), e)

    logger.info("Found %d Gong transcripts for %s", len(transcripts), target_date)
    return transcripts


def fetch_all_transcripts(
    service, target_date: date, config: dict
) -> list[dict]:
    """Fetch transcripts from all configured sources (Gemini + Gong).

    Args:
        service: Gmail API service instance.
        target_date: The date to search for transcripts.
        config: Pipeline configuration dict.

    Returns:
        Combined list of transcript dicts from all sources.
    """
    gemini = fetch_gemini_transcripts(service, target_date, config)
    gong = fetch_gong_transcripts(service, target_date, config)

    combined = gemini + gong
    logger.info(
        "Total transcripts for %s: %d (%d Gemini, %d Gong)",
        target_date,
        len(combined),
        len(gemini),
        len(gong),
    )
    return combined
