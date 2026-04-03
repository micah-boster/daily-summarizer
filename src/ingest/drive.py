"""Google Drive transcript fetching: search for 'Notes by Gemini' docs and extract content."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta

from dateutil.parser import parse as dateutil_parse
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

# Pattern: "Meeting Title - 2026/03/18 15:25 EDT - Notes by Gemini"
DOC_NAME_PATTERN = re.compile(
    r"^(.+?)\s*-\s*(\d{4}/\d{2}/\d{2}\s+\S+\s+\S+)\s*-\s*Notes by Gemini$",
    re.IGNORECASE,
)


def build_drive_service(creds: Credentials):
    """Create a Google Drive API v3 service instance."""
    return build("drive", "v3", credentials=creds)


def build_docs_service(creds: Credentials):
    """Create a Google Docs API v1 service instance."""
    return build("docs", "v1", credentials=creds)


def _extract_title_from_doc_name(doc_name: str) -> str:
    """Extract meeting title from Drive doc name.

    Strips the date/time suffix and 'Notes by Gemini' suffix.
    E.g. 'Weekly Sync - 2026/03/18 15:25 EDT - Notes by Gemini' -> 'Weekly Sync'
    """
    match = DOC_NAME_PATTERN.match(doc_name)
    if match:
        return match.group(1).strip()
    # Fallback: strip ' - Notes by Gemini' suffix if present
    fallback = re.sub(r"\s*-\s*Notes by Gemini\s*$", "", doc_name, flags=re.IGNORECASE)
    return fallback.strip()


def _extract_time_from_doc_name(doc_name: str) -> datetime | None:
    """Extract meeting datetime from Drive doc name.

    Parses the date/time portion between the title and 'Notes by Gemini'.
    """
    match = DOC_NAME_PATTERN.match(doc_name)
    if match:
        date_str = match.group(2).strip()
        try:
            return dateutil_parse(date_str)
        except (ValueError, OverflowError):
            logger.warning("Could not parse date from doc name: %s", date_str)
    return None


def _extract_doc_text(docs_service, doc_id: str) -> str:
    """Fetch full plain text content from a Google Doc.

    Uses the Docs API to read structural elements and concatenate text runs.
    """
    doc = docs_service.documents().get(documentId=doc_id).execute()
    text_parts = []
    for element in doc.get("body", {}).get("content", []):
        paragraph = element.get("paragraph")
        if paragraph:
            for elem in paragraph.get("elements", []):
                text_run = elem.get("textRun")
                if text_run:
                    text_parts.append(text_run.get("content", ""))
    return "".join(text_parts)


def search_gemini_drive_docs(
    drive_service, target_date: date
) -> list[dict]:
    """Search Google Drive for 'Notes by Gemini' docs created on target_date.

    Returns list of file metadata dicts with 'id', 'name', 'createdTime'.
    """
    date_str = target_date.isoformat()
    next_date_str = (target_date + timedelta(days=1)).isoformat()

    query = (
        "name contains 'Notes by Gemini' "
        "and mimeType = 'application/vnd.google-apps.document' "
        f"and createdTime >= '{date_str}T00:00:00' "
        f"and createdTime < '{next_date_str}T00:00:00'"
    )

    results = []
    page_token = None
    while True:
        response = drive_service.files().list(
            q=query,
            fields="nextPageToken, files(id, name, createdTime)",
            pageSize=100,
            pageToken=page_token,
        ).execute()

        results.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return results


def parse_drive_transcript(
    doc_meta: dict, doc_text: str, config: dict
) -> dict | None:
    """Parse a Drive doc into a transcript dict matching the pipeline format.

    Returns transcript dict with same keys as Gmail-based parsers:
    source, title, meeting_time, transcript_text, raw_email, message_id.
    """
    doc_name = doc_meta.get("name", "")
    title = _extract_title_from_doc_name(doc_name)
    meeting_time = _extract_time_from_doc_name(doc_name)

    # Fallback: use createdTime from Drive metadata
    if meeting_time is None:
        created_str = doc_meta.get("createdTime", "")
        if created_str:
            try:
                meeting_time = dateutil_parse(created_str)
            except (ValueError, OverflowError):
                pass

    if not doc_text.strip():
        logger.debug("Empty content for Drive doc %s, skipping", doc_meta.get("id"))
        return None

    # Apply filler stripping if configured (reuse existing function)
    from src.ingest.transcripts import strip_filler

    preprocessing = config.get("transcripts", {}).get("preprocessing", {})
    if preprocessing.get("strip_filler", True):
        doc_text = strip_filler(doc_text)

    return {
        "source": "gemini_drive",
        "title": title,
        "meeting_time": meeting_time,
        "transcript_text": doc_text,
        "raw_email": doc_meta,
        "message_id": doc_meta.get("id", ""),
    }


def fetch_gemini_drive_transcripts(
    creds: Credentials, target_date: date, config: dict
) -> list[dict]:
    """Fetch and parse all 'Notes by Gemini' docs from Drive for a target date."""
    drive_config = config.get("transcripts", {}).get("gemini_drive", {})
    if drive_config.get("enabled") is False:
        logger.info("Drive transcript fetching disabled in config")
        return []

    drive_service = build_drive_service(creds)
    docs_service = build_docs_service(creds)

    doc_metas = search_gemini_drive_docs(drive_service, target_date)
    logger.info("Found %d 'Notes by Gemini' docs in Drive for %s", len(doc_metas), target_date)

    transcripts = []
    for meta in doc_metas:
        try:
            doc_text = _extract_doc_text(docs_service, meta["id"])
            parsed = parse_drive_transcript(meta, doc_text, config)
            if parsed:
                transcripts.append(parsed)
        except Exception as e:
            logger.warning("Failed to parse Drive doc %s: %s", meta.get("id"), e)

    logger.info("Parsed %d Drive transcripts for %s", len(transcripts), target_date)
    return transcripts
