"""Google Docs ingestion module.

Detects documents the user edited on a target date, extracts content
(Docs) or metadata (Sheets/Slides), fetches comments and suggestions,
and converts everything to SourceItem objects for synthesis.
"""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from typing import Any

from dateutil.parser import parse as dateutil_parse
from google.oauth2.credentials import Credentials

from src.config import PipelineConfig
from src.ingest.drive import build_docs_service, build_drive_service, _extract_doc_text
from src.models.sources import ContentType, SourceItem, SourceType
from src.retry import retry_api_call

logger = logging.getLogger(__name__)


@retry_api_call
def _execute_with_retry(request):
    """Execute a Google API request with retry on transient errors."""
    return request.execute()


# Module-level cache for authenticated user email
_user_email_cache: str | None = None


def _get_user_email(drive_service: Any) -> str:
    """Get the authenticated user's email address.

    Uses a module-level cache to avoid repeated API calls.

    Args:
        drive_service: Authenticated Drive API v3 service.

    Returns:
        User's email address string.
    """
    global _user_email_cache
    if _user_email_cache is not None:
        return _user_email_cache

    about = _execute_with_retry(drive_service.about().get(fields="user(emailAddress)"))
    _user_email_cache = about["user"]["emailAddress"]
    return _user_email_cache


def _should_exclude(doc_meta: dict, config: PipelineConfig) -> bool:
    """Check if a document should be excluded based on config.

    Checks doc ID against exclude_ids list and doc title against
    exclude_title_patterns regex list.

    Args:
        doc_meta: Drive file metadata dict with 'id' and 'name'.
        config: Pipeline configuration dict.

    Returns:
        True if the document should be excluded.
    """
    # Check excluded IDs
    if doc_meta.get("id") in config.google_docs.exclude_ids:
        logger.debug("Excluding doc %s (ID in exclude list)", doc_meta.get("id"))
        return True

    # Check excluded title patterns
    exclude_patterns = config.google_docs.exclude_title_patterns
    doc_name = doc_meta.get("name", "")
    for pattern in exclude_patterns:
        try:
            if re.search(pattern, doc_name, re.IGNORECASE):
                logger.debug(
                    "Excluding doc '%s' (title matches pattern '%s')",
                    doc_name,
                    pattern,
                )
                return True
        except re.error:
            logger.warning("Invalid regex pattern in exclude_title_patterns: %s", pattern)

    return False


def _find_edited_docs(
    drive_service: Any, target_date: date, config: PipelineConfig
) -> list[dict]:
    """Find all docs/sheets/slides the user modified on target_date.

    Uses Drive API files.list with modifiedTime filter, then filters
    to only include docs where the authenticated user was the modifier.

    Args:
        drive_service: Authenticated Drive API v3 service.
        target_date: Date to search for modifications.
        config: Pipeline configuration dict.

    Returns:
        List of file metadata dicts.
    """
    date_str = target_date.isoformat()
    next_date_str = (target_date + timedelta(days=1)).isoformat()

    # MIME types for Google Workspace files
    mime_types = [
        "application/vnd.google-apps.document",
        "application/vnd.google-apps.spreadsheet",
        "application/vnd.google-apps.presentation",
    ]
    mime_filter = " or ".join(f"mimeType = '{m}'" for m in mime_types)

    query = (
        f"({mime_filter}) "
        f"and modifiedTime >= '{date_str}T00:00:00' "
        f"and modifiedTime < '{next_date_str}T00:00:00' "
        "and trashed = false"
    )

    results: list[dict] = []
    page_token = None
    while True:
        response = _execute_with_retry(
            drive_service.files()
            .list(
                q=query,
                fields="nextPageToken, files(id, name, mimeType, modifiedTime, owners, lastModifyingUser)",
                pageSize=100,
                pageToken=page_token,
            )
        )
        results.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    # Filter to docs modified by the authenticated user
    user_email = _get_user_email(drive_service)
    user_edited = []
    for doc in results:
        last_modifier = doc.get("lastModifyingUser", {})
        modifier_email = last_modifier.get("emailAddress", "")
        modifier_is_me = last_modifier.get("me", False)
        if modifier_email == user_email or modifier_is_me:
            user_edited.append(doc)

    logger.info(
        "Found %d/%d docs modified by user on %s",
        len(user_edited),
        len(results),
        target_date,
    )
    return user_edited


def _mime_to_file_type(mime_type: str) -> str:
    """Map Google MIME type to human-readable file type label."""
    if "spreadsheet" in mime_type:
        return "Google Sheet"
    elif "presentation" in mime_type:
        return "Google Slides"
    return "Google Doc"


def _mime_to_url(mime_type: str, file_id: str) -> str:
    """Build the appropriate Google URL for a file based on MIME type."""
    if "spreadsheet" in mime_type:
        return f"https://docs.google.com/spreadsheets/d/{file_id}"
    elif "presentation" in mime_type:
        return f"https://docs.google.com/presentation/d/{file_id}"
    return f"https://docs.google.com/document/d/{file_id}"


def _build_doc_edit_items(
    drive_service: Any,
    docs_service: Any,
    edited_docs: list[dict],
    config: PipelineConfig,
) -> list[SourceItem]:
    """Convert edited doc metadata to SourceItem objects.

    For Google Docs: extracts plain text content, truncated to configured limit.
    For Sheets/Slides: metadata only (title + edit time).

    Args:
        drive_service: Authenticated Drive API v3 service.
        docs_service: Authenticated Docs API v1 service.
        edited_docs: List of file metadata dicts from _find_edited_docs.
        config: Pipeline configuration.

    Returns:
        List of SourceItem objects for doc edits.
    """
    max_content = config.google_docs.content_max_chars
    max_docs = config.google_docs.max_docs_per_day

    items: list[SourceItem] = []

    for doc in edited_docs[:max_docs]:
        if _should_exclude(doc, config):
            continue

        try:
            doc_name = doc.get("name", "Untitled")
            mime_type = doc.get("mimeType", "")
            file_type = _mime_to_file_type(mime_type)
            modified_time = doc.get("modifiedTime", "")

            # Extract content based on file type
            if "document" in mime_type:
                # Google Docs: extract full text, truncate
                raw_content = _extract_doc_text(docs_service, doc["id"])
                content = raw_content[:max_content] if len(raw_content) > max_content else raw_content
            else:
                # Sheets/Slides: metadata only per user decision
                content = f"[{file_type} edited on {modified_time}]"

            items.append(
                SourceItem(
                    id=doc["id"],
                    source_type=SourceType.GOOGLE_DOC_EDIT,
                    content_type=ContentType.EDIT,
                    title=doc_name,
                    timestamp=dateutil_parse(modified_time),
                    content=content,
                    participants=[],
                    source_url=_mime_to_url(mime_type, doc["id"]),
                    display_context=f"{file_type} {doc_name}",
                )
            )
        except Exception as e:
            logger.warning("Failed to process doc '%s' (%s): %s", doc.get("name"), doc.get("id"), e)

    if len(edited_docs) > max_docs:
        logger.warning(
            "Hit max_docs_per_day limit (%d). %d docs skipped.",
            max_docs,
            len(edited_docs) - max_docs,
        )

    return items


def _build_comment_items(
    drive_service: Any,
    edited_docs: list[dict],
    target_date: date,
    config: PipelineConfig,
) -> list[SourceItem]:
    """Fetch comments and suggestions on edited docs for the target date.

    Includes resolved comments (they represent decisions made that day).
    Treats suggestions (proposed edits) the same as regular comments,
    but includes the quoted content for context.

    Args:
        drive_service: Authenticated Drive API v3 service.
        edited_docs: List of file metadata dicts.
        target_date: Date to filter comments by.
        config: Pipeline configuration.

    Returns:
        List of SourceItem objects for comments.
    """
    comment_max_chars = config.google_docs.comment_max_chars

    date_str = target_date.isoformat()
    next_date_str = (target_date + timedelta(days=1)).isoformat()
    date_min = f"{date_str}T00:00:00"
    date_max = f"{next_date_str}T00:00:00"

    items: list[SourceItem] = []

    for doc in edited_docs:
        file_id = doc.get("id", "")
        doc_name = doc.get("name", "Untitled")
        mime_type = doc.get("mimeType", "")

        try:
            page_token = None
            while True:
                response = _execute_with_retry(
                    drive_service.comments()
                    .list(
                        fileId=file_id,
                        fields="nextPageToken, comments(id, content, author, createdTime, modifiedTime, resolved, quotedFileContent, replies)",
                        pageSize=100,
                        pageToken=page_token,
                        includeDeleted=False,
                    )
                )

                for comment in response.get("comments", []):
                    created = comment.get("createdTime", "")
                    modified = comment.get("modifiedTime", "")

                    # Include if created or modified on target date
                    in_range = (
                        (created >= date_min and created < date_max)
                        or (modified >= date_min and modified < date_max)
                    )
                    if not in_range:
                        continue

                    author_name = comment.get("author", {}).get("displayName", "Unknown")
                    comment_text = comment.get("content", "")
                    quoted = comment.get("quotedFileContent", {})
                    quoted_text = quoted.get("value", "") if quoted else ""

                    # Build rich content: quoted text + comment
                    if quoted_text:
                        full_content = f'Suggested: "{quoted_text}" \u2014 {comment_text}'
                    else:
                        full_content = comment_text

                    full_content = full_content[:comment_max_chars]

                    items.append(
                        SourceItem(
                            id=f"{file_id}_comment_{comment['id']}",
                            source_type=SourceType.GOOGLE_DOC_COMMENT,
                            content_type=ContentType.COMMENT,
                            title=f"Comment by {author_name} on {doc_name}",
                            timestamp=dateutil_parse(created or modified),
                            content=full_content,
                            participants=[author_name],
                            source_url=_mime_to_url(mime_type, file_id),
                            display_context=f"Google Doc {doc_name}",
                        )
                    )

                    # Also include replies that fall within target date
                    for reply in comment.get("replies", []):
                        reply_created = reply.get("createdTime", "")
                        if reply_created >= date_min and reply_created < date_max:
                            reply_author = reply.get("author", {}).get("displayName", "Unknown")
                            reply_content = reply.get("content", "")[:comment_max_chars]

                            items.append(
                                SourceItem(
                                    id=f"{file_id}_reply_{reply.get('id', '')}",
                                    source_type=SourceType.GOOGLE_DOC_COMMENT,
                                    content_type=ContentType.COMMENT,
                                    title=f"Reply by {reply_author} on {doc_name}",
                                    timestamp=dateutil_parse(reply_created),
                                    content=reply_content,
                                    participants=[reply_author],
                                    source_url=_mime_to_url(mime_type, file_id),
                                    display_context=f"Google Doc {doc_name}",
                                )
                            )

                page_token = response.get("nextPageToken")
                if not page_token:
                    break

        except Exception as e:
            logger.warning(
                "Failed to fetch comments for doc '%s' (%s): %s",
                doc_name,
                file_id,
                e,
            )

    return items


def fetch_google_docs_items(
    config: PipelineConfig, creds: Credentials, target_date: date
) -> list[SourceItem]:
    """Fetch edited docs and comments for a target date.

    Main entry point for Google Docs ingestion. Returns empty list if
    google_docs.enabled is False in config.

    Args:
        config: Pipeline configuration.
        creds: Authenticated Google OAuth credentials.
        target_date: Date to fetch activity for.

    Returns:
        List of SourceItem objects for doc edits and comments.
    """
    if not config.google_docs.enabled:
        logger.debug("Google Docs ingestion disabled in config")
        return []

    drive_service = build_drive_service(creds)
    docs_service = build_docs_service(creds)

    # Find docs modified on target_date by the authenticated user
    edited_docs = _find_edited_docs(drive_service, target_date, config)

    # Filter excluded docs
    filtered_docs = [d for d in edited_docs if not _should_exclude(d, config)]

    # Build edit items (content for Docs, metadata for Sheets/Slides)
    doc_items = _build_doc_edit_items(drive_service, docs_service, filtered_docs, config)

    # Build comment items
    comment_items = _build_comment_items(drive_service, filtered_docs, target_date, config)

    logger.info(
        "Google Docs ingest for %s: %d edits, %d comments",
        target_date,
        len(doc_items),
        len(comment_items),
    )

    return doc_items + comment_items
