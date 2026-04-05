"""Gmail API utilities: service builder, message search, body extraction, caching."""

from __future__ import annotations

import base64
import html
import json
import logging
import re
from datetime import date, timedelta
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from src.retry import retry_api_call

logger = logging.getLogger(__name__)


@retry_api_call
def _execute_with_retry(request):
    """Execute a Google API request with retry on transient errors."""
    return request.execute()


def build_gmail_service(creds: Credentials):
    """Create a Gmail API v1 service instance.

    Args:
        creds: Google OAuth2 credentials with gmail.readonly scope.

    Returns:
        Gmail API service instance.
    """
    return build("gmail", "v1", credentials=creds)


def search_messages(service, query: str, max_results: int = 100) -> list[dict]:
    """Search Gmail messages matching a query string.

    Uses Gmail search operators (from:, subject:, after:, before:, etc.).
    Handles pagination automatically.

    Args:
        service: Gmail API service instance.
        query: Gmail search query string.
        max_results: Maximum number of messages to return.

    Returns:
        List of message stubs, each with 'id' and 'threadId'.
    """
    messages: list[dict] = []
    page_token = None

    while len(messages) < max_results:
        batch_size = min(max_results - len(messages), 500)
        request = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=batch_size,
            pageToken=page_token,
        )
        response = _execute_with_retry(request)

        batch = response.get("messages", [])
        messages.extend(batch)

        page_token = response.get("nextPageToken")
        if not page_token or not batch:
            break

    return messages[:max_results]


def get_message_content(service, msg_id: str) -> dict:
    """Retrieve the full content of a Gmail message.

    Args:
        service: Gmail API service instance.
        msg_id: The message ID to retrieve.

    Returns:
        Full message dict including payload with headers and body.
    """
    request = (
        service.users()
        .messages()
        .get(userId="me", id=msg_id, format="full")
    )
    return _execute_with_retry(request)


def extract_headers(message: dict) -> dict[str, str]:
    """Extract common headers from a Gmail message payload.

    Args:
        message: Full Gmail message dict (from get_message_content).

    Returns:
        Dict with keys: subject, from, to, date. Values are empty string if
        header not found.
    """
    headers: dict[str, str] = {"subject": "", "from": "", "to": "", "date": ""}
    target_names = {"subject", "from", "to", "date"}

    for header in message.get("payload", {}).get("headers", []):
        name = header.get("name", "").lower()
        if name in target_names:
            headers[name] = header.get("value", "")

    return headers


def _strip_html_tags(text: str) -> str:
    """Remove HTML tags and decode entities from text.

    Args:
        text: HTML content string.

    Returns:
        Plain text with tags removed and entities decoded.
    """
    # Remove HTML tags
    clean = re.sub(r"<[^>]+>", " ", text)
    # Decode HTML entities
    clean = html.unescape(clean)
    # Collapse whitespace
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def _extract_body_from_parts(parts: list[dict]) -> str:
    """Recursively extract text body from MIME parts.

    Prefers text/plain over text/html. Recurses into nested multipart.

    Args:
        parts: List of MIME part dicts from Gmail payload.

    Returns:
        Decoded text content, or empty string if none found.
    """
    plain_text = ""
    html_text = ""

    for part in parts:
        mime_type = part.get("mimeType", "")

        # Recurse into nested multipart
        if mime_type.startswith("multipart/") and "parts" in part:
            nested = _extract_body_from_parts(part["parts"])
            if nested:
                return nested

        body_data = part.get("body", {}).get("data")
        if not body_data:
            continue

        try:
            decoded = base64.urlsafe_b64decode(body_data).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            continue

        if mime_type == "text/plain" and not plain_text:
            plain_text = decoded
        elif mime_type == "text/html" and not html_text:
            html_text = decoded

    if plain_text:
        return plain_text
    if html_text:
        return _strip_html_tags(html_text)
    return ""


def extract_body_text(message: dict) -> str:
    """Extract plain text body from a Gmail message.

    Handles single-part and multipart MIME messages. Prefers text/plain,
    falls back to text/html with tag stripping.

    Args:
        message: Full Gmail message dict (from get_message_content).

    Returns:
        Decoded plain text content, or empty string if no body found.
    """
    payload = message.get("payload", {})

    # Check for parts (multipart message)
    parts = payload.get("parts")
    if parts:
        return _extract_body_from_parts(parts)

    # Single-part message: body data directly on payload
    body_data = payload.get("body", {}).get("data")
    if body_data:
        try:
            decoded = base64.urlsafe_b64decode(body_data).decode("utf-8")
            mime_type = payload.get("mimeType", "text/plain")
            if mime_type == "text/html":
                return _strip_html_tags(decoded)
            return decoded
        except (ValueError, UnicodeDecodeError):
            logger.warning("Failed to decode message body for message %s", message.get("id"))
            return ""

    return ""


def build_transcript_query(
    sender_patterns: list[str],
    subject_patterns: list[str],
    target_date: date,
) -> str:
    """Build a Gmail search query for transcript emails on a specific date.

    Args:
        sender_patterns: List of sender email addresses to match.
        subject_patterns: List of subject keywords to match.
        target_date: The date to search for transcripts.

    Returns:
        Gmail search query string using from:, subject:, after:, before: operators.
    """
    senders = " OR ".join(f"from:{s}" for s in sender_patterns)
    subjects = " OR ".join(f"subject:{s}" for s in subject_patterns)

    # Gmail date format uses slashes: YYYY/MM/DD
    after_str = target_date.strftime("%Y/%m/%d")
    before_date = target_date + timedelta(days=1)
    before_str = before_date.strftime("%Y/%m/%d")

    return f"({senders}) ({subjects}) after:{after_str} before:{before_str}"


def cache_raw_emails(
    emails: list[dict],
    source_name: str,
    target_date: date,
    output_dir: Path,
) -> Path:
    """Write raw email data to JSON cache file.

    Creates: output_dir/raw/YYYY/MM/DD/{source_name}_emails.json

    Args:
        emails: List of raw email message dicts.
        source_name: Name of the transcript source (e.g., 'gemini', 'gong', 'transcripts').
        target_date: The date these emails are for.
        output_dir: Base output directory.

    Returns:
        Path to the written JSON file.
    """
    cache_dir = (
        output_dir
        / "raw"
        / str(target_date.year)
        / f"{target_date.month:02d}"
        / f"{target_date.day:02d}"
    )
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{source_name}_emails.json"

    cache_path.write_text(
        json.dumps(emails, indent=2, default=str), encoding="utf-8"
    )
    logger.info("Cached %d raw emails to %s", len(emails), cache_path)
    return cache_path
