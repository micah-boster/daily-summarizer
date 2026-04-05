"""Notion ingestion module.

Fetches pages the user edited/created on a target date and database
items modified on a target date.  Converts to SourceItem objects for
synthesis.  Uses direct httpx REST calls against the Notion API with
a simple per-request throttle for rate limiting (3 req/s).
"""
from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from typing import Any

import httpx
from dateutil.parser import parse as dateutil_parse

from src.config import PipelineConfig
from src.models.sources import ContentType, SourceItem, SourceType
from src.retry import retry_api_call

logger = logging.getLogger(__name__)

# Block types whose rich_text content we extract
SUPPORTED_BLOCKS: set[str] = {
    "paragraph",
    "heading_1",
    "heading_2",
    "heading_3",
    "bulleted_list_item",
    "numbered_list_item",
    "toggle",
    "callout",
    "quote",
}

# Module-level cache for bot user id
_bot_user_id_cache: str | None = None


# ---------------------------------------------------------------------------
# Notion API client (thin httpx wrapper with throttle)
# ---------------------------------------------------------------------------


class NotionClient:
    """Thin httpx wrapper for the Notion REST API with per-request throttle."""

    def __init__(self, token: str, notion_version: str = "2022-06-28") -> None:
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": notion_version,
            "Content-Type": "application/json",
        }
        self._base = "https://api.notion.com/v1"
        self._last_request: float = 0.0
        self._min_interval: float = 0.35  # ~3 req/s

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request = time.monotonic()

    @retry_api_call
    def _request(self, method: str, path: str, **kwargs: Any) -> dict:
        self._throttle()
        resp = httpx.request(
            method,
            f"{self._base}{path}",
            headers=self._headers,
            timeout=30.0,
            **kwargs,
        )
        resp.raise_for_status()
        return resp.json()

    def get(self, path: str, **kwargs: Any) -> dict:
        return self._request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> dict:
        return self._request("POST", path, **kwargs)

    def paginate_post(self, path: str, body: dict | None = None) -> list[dict]:
        """Paginate a POST endpoint, collecting all results."""
        results: list[dict] = []
        start_cursor: str | None = None
        payload = dict(body or {})

        while True:
            if start_cursor:
                payload["start_cursor"] = start_cursor
            resp = self.post(path, json=payload)
            results.extend(resp.get("results", []))
            if not resp.get("has_more"):
                break
            start_cursor = resp.get("next_cursor")
            if not start_cursor:
                break
        return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_bot_user_id(client: NotionClient) -> str:
    """Get the bot user id for the integration (cached)."""
    global _bot_user_id_cache
    if _bot_user_id_cache is not None:
        return _bot_user_id_cache
    resp = client.get("/users/me")
    _bot_user_id_cache = resp.get("id", "")
    return _bot_user_id_cache


def _extract_page_title(page: dict) -> str:
    """Extract the title from a Notion page's properties.

    Notion pages have a single property of type 'title'. The property
    name varies (commonly 'Name' or 'title').
    """
    properties = page.get("properties", {})
    for _prop_name, prop_value in properties.items():
        if prop_value.get("type") == "title":
            rich_texts = prop_value.get("title", [])
            return "".join(rt.get("plain_text", "") for rt in rich_texts) or "Untitled"
    return "Untitled"


def _extract_text_from_blocks(blocks: list[dict]) -> str:
    """Extract plain text from supported Notion blocks.

    Only extracts text from: paragraph, heading_1/2/3,
    bulleted/numbered list items, toggle, callout, quote.
    Skips images, embeds, code blocks, etc.
    """
    parts: list[str] = []
    for block in blocks:
        block_type = block.get("type", "")
        if block_type in SUPPORTED_BLOCKS:
            rich_texts = block.get(block_type, {}).get("rich_text", [])
            text = "".join(rt.get("plain_text", "") for rt in rich_texts)
            if text.strip():
                parts.append(text.strip())
    return "\n".join(parts)


def _extract_db_properties(properties: dict, max_chars: int = 200) -> str:
    """Extract human-readable property values from a Notion database item.

    Handles common property types; skips noisy ones (relation, rollup, etc.).
    """
    parts: list[str] = []
    skip_types = {
        "relation",
        "rollup",
        "formula",
        "files",
        "created_by",
        "last_edited_by",
        "created_time",
        "last_edited_time",
    }

    for prop_name, prop_value in properties.items():
        prop_type = prop_value.get("type", "")
        if prop_type in skip_types:
            continue

        value: str | None = None

        if prop_type == "title":
            rich_texts = prop_value.get("title", [])
            value = "".join(rt.get("plain_text", "") for rt in rich_texts)
        elif prop_type == "rich_text":
            rich_texts = prop_value.get("rich_text", [])
            value = "".join(rt.get("plain_text", "") for rt in rich_texts)
        elif prop_type == "select":
            select = prop_value.get("select")
            if select:
                value = select.get("name", "")
        elif prop_type == "multi_select":
            options = prop_value.get("multi_select", [])
            value = ", ".join(o.get("name", "") for o in options)
        elif prop_type == "status":
            status = prop_value.get("status")
            if status:
                value = status.get("name", "")
        elif prop_type == "number":
            num = prop_value.get("number")
            if num is not None:
                value = str(num)
        elif prop_type == "date":
            date_obj = prop_value.get("date")
            if date_obj:
                value = date_obj.get("start", "")
        elif prop_type == "checkbox":
            value = "Yes" if prop_value.get("checkbox") else "No"
        elif prop_type == "people":
            people = prop_value.get("people", [])
            value = ", ".join(p.get("name", p.get("id", "")) for p in people)
        elif prop_type == "url":
            value = prop_value.get("url", "")
        elif prop_type == "email":
            value = prop_value.get("email", "")
        elif prop_type == "phone_number":
            value = prop_value.get("phone_number", "")

        if value and value.strip():
            parts.append(f"{prop_name}: {value.strip()}")

    result = ", ".join(parts)
    return result[:max_chars] if len(result) > max_chars else result


# ---------------------------------------------------------------------------
# Page ingestion
# ---------------------------------------------------------------------------


def _fetch_edited_pages(
    client: NotionClient, target_date: date, config: PipelineConfig
) -> list[SourceItem]:
    """Fetch Notion pages edited on the target date and convert to SourceItems."""
    date_str = target_date.isoformat()
    next_date_str = (target_date + timedelta(days=1)).isoformat()

    # Search for all pages, sorted by last_edited_time
    all_pages = client.paginate_post(
        "/search",
        {
            "filter": {"property": "object", "value": "page"},
            "sort": {"direction": "descending", "timestamp": "last_edited_time"},
            "page_size": 100,
        },
    )

    # Filter to pages edited on the target date
    edited_pages: list[dict] = []
    for page in all_pages:
        last_edited = page.get("last_edited_time", "")
        if last_edited >= f"{date_str}T00:00:00" and last_edited < f"{next_date_str}T00:00:00":
            edited_pages.append(page)
        # Since results are sorted descending by last_edited_time,
        # we can break early once we pass the target date
        elif last_edited < f"{date_str}T00:00:00":
            break

    max_pages = config.notion.max_pages_per_day
    if len(edited_pages) > max_pages:
        logger.warning(
            "Hit max_pages_per_day limit (%d). %d pages skipped.",
            max_pages,
            len(edited_pages) - max_pages,
        )
        edited_pages = edited_pages[:max_pages]

    logger.info("Found %d Notion pages edited on %s", len(edited_pages), target_date)

    items: list[SourceItem] = []
    max_content = config.notion.content_max_chars

    for page in edited_pages:
        try:
            page_id = page.get("id", "")
            page_title = _extract_page_title(page)
            last_edited = page.get("last_edited_time", "")
            page_url = page.get("url", f"https://notion.so/{page_id.replace('-', '')}")

            # Fetch first page of block children for content extraction
            try:
                blocks_resp = client.get(
                    f"/blocks/{page_id}/children",
                    params={"page_size": 50},
                )
                blocks = blocks_resp.get("results", [])
            except Exception as e:
                logger.debug("Could not fetch blocks for page %s: %s", page_id, e)
                blocks = []

            content = _extract_text_from_blocks(blocks)
            if len(content) > max_content:
                content = content[:max_content]

            items.append(
                SourceItem(
                    id=page_id,
                    source_type=SourceType.NOTION_PAGE,
                    content_type=ContentType.EDIT,
                    title=page_title,
                    timestamp=dateutil_parse(last_edited),
                    content=content or f"[Page edited on {last_edited}]",
                    participants=[],
                    source_url=page_url,
                    display_context=f"Notion {page_title}",
                )
            )
        except Exception as e:
            logger.warning("Failed to process Notion page %s: %s", page.get("id"), e)

    return items


# ---------------------------------------------------------------------------
# Database ingestion
# ---------------------------------------------------------------------------


def _fetch_database_changes(
    client: NotionClient, target_date: date, config: PipelineConfig
) -> list[SourceItem]:
    """Fetch items modified in watched databases on the target date."""
    watched = config.notion.watched_databases
    if not watched:
        return []

    date_str = target_date.isoformat()
    next_date_str = (target_date + timedelta(days=1)).isoformat()
    max_items = config.notion.max_db_items_per_day
    max_content = config.notion.content_max_chars

    all_items: list[SourceItem] = []

    for db_id in watched:
        try:
            # Get database metadata for title
            try:
                db_meta = client.get(f"/databases/{db_id}")
                db_title_parts = db_meta.get("title", [])
                db_title = "".join(t.get("plain_text", "") for t in db_title_parts) or "Database"
            except Exception:
                db_title = "Database"

            # Query for items modified on target date
            results = client.paginate_post(
                f"/databases/{db_id}/query",
                {
                    "filter": {
                        "timestamp": "last_edited_time",
                        "last_edited_time": {
                            "on_or_after": f"{date_str}T00:00:00",
                            "before": f"{next_date_str}T00:00:00",
                        },
                    },
                    "page_size": 100,
                },
            )

            if len(results) > max_items:
                logger.warning(
                    "Hit max_db_items_per_day limit (%d) for database '%s'. %d items skipped.",
                    max_items,
                    db_title,
                    len(results) - max_items,
                )
                results = results[:max_items]

            for item in results:
                try:
                    item_id = item.get("id", "")
                    item_title = _extract_page_title(item)
                    last_edited = item.get("last_edited_time", "")
                    item_url = item.get("url", f"https://notion.so/{item_id.replace('-', '')}")

                    properties = item.get("properties", {})
                    content = _extract_db_properties(properties, max_content)

                    all_items.append(
                        SourceItem(
                            id=item_id,
                            source_type=SourceType.NOTION_DB,
                            content_type=ContentType.STAGE_CHANGE,
                            title=item_title,
                            timestamp=dateutil_parse(last_edited),
                            content=content or f"[Modified on {last_edited}]",
                            participants=[],
                            source_url=item_url,
                            display_context=f"Notion {db_title}",
                        )
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to process DB item %s in '%s': %s",
                        item.get("id"),
                        db_title,
                        e,
                    )

            logger.info(
                "Fetched %d items from Notion database '%s' for %s",
                len(results),
                db_title,
                target_date,
            )

        except Exception as e:
            logger.warning("Failed to query Notion database %s: %s", db_id, e)

    return all_items


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def fetch_notion_items(
    config: PipelineConfig, target_date: date
) -> list[SourceItem]:
    """Fetch Notion page edits and database changes for a target date.

    Main entry point for Notion ingestion. Returns empty list if
    notion.enabled is False or no token configured.

    Args:
        config: Pipeline configuration.
        target_date: Date to fetch activity for.

    Returns:
        List of SourceItem objects for page edits and database changes.
    """
    if not config.notion.enabled:
        logger.debug("Notion ingestion disabled in config")
        return []

    if not config.notion.token:
        logger.warning("Notion enabled but no token configured. Skipping Notion ingestion.")
        return []

    client = NotionClient(
        token=config.notion.token,
        notion_version=config.notion.notion_version,
    )

    page_items = _fetch_edited_pages(client, target_date, config)
    db_items = _fetch_database_changes(client, target_date, config)

    logger.info(
        "Notion ingest for %s: %d page edits, %d database items",
        target_date,
        len(page_items),
        len(db_items),
    )

    return page_items + db_items
