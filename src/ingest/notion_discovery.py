"""Notion database discovery module.

Scans the Notion workspace for databases, presents them to the user,
and writes selected database IDs to config.yaml as watched databases.
Mirrors the Slack discovery CLI pattern.
"""
from __future__ import annotations

import logging
from pathlib import Path

import yaml

from src.config import load_config

logger = logging.getLogger(__name__)


def _build_headers(token: str, notion_version: str = "2022-06-28") -> dict:
    """Build Notion API request headers."""
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": notion_version,
        "Content-Type": "application/json",
    }


def _scan_databases(token: str, notion_version: str = "2022-06-28") -> list[dict]:
    """Scan workspace for all databases accessible to the integration.

    Returns list of dicts with: id, title, description, last_edited_time.
    Sorted by last_edited_time descending (most recently active first).
    """
    import time

    import httpx

    headers = _build_headers(token, notion_version)
    base = "https://api.notion.com/v1"
    results: list[dict] = []
    start_cursor: str | None = None

    while True:
        payload: dict = {
            "filter": {"property": "object", "value": "database"},
            "page_size": 100,
        }
        if start_cursor:
            payload["start_cursor"] = start_cursor

        time.sleep(0.35)  # Rate limit throttle
        resp = httpx.post(
            f"{base}/search",
            headers=headers,
            json=payload,
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()

        for db in data.get("results", []):
            db_id = db.get("id", "")
            title_parts = db.get("title", [])
            title = "".join(t.get("plain_text", "") for t in title_parts) or "Untitled"
            description_parts = db.get("description", [])
            description = "".join(
                d.get("plain_text", "") for d in description_parts
            ) if description_parts else ""
            last_edited = db.get("last_edited_time", "")

            results.append({
                "id": db_id,
                "title": title,
                "description": description,
                "last_edited_time": last_edited,
            })

        if not data.get("has_more"):
            break
        start_cursor = data.get("next_cursor")
        if not start_cursor:
            break

    # Sort by last_edited_time descending
    results.sort(key=lambda d: d.get("last_edited_time", ""), reverse=True)
    return results


def run_notion_discovery(config_path: str) -> None:
    """Interactive CLI flow for discovering and selecting Notion databases.

    Args:
        config_path: Path to config.yaml file.
    """
    config = load_config(config_path)

    if not config.notion.token:
        print(
            "\nNo Notion token configured. Add notion.token to config.yaml first.\n"
            "Get a token at: https://www.notion.so/my-integrations"
        )
        return

    print("\nScanning Notion workspace for databases...")
    databases = _scan_databases(config.notion.token, config.notion.notion_version)

    if not databases:
        print(
            "\nNo databases found. Make sure databases are shared with your integration.\n"
            "In Notion: open each database -> ... menu -> Add connections -> select your integration."
        )
        return

    # Display databases
    current_watched = set(config.notion.watched_databases)

    print(f"\nFound {len(databases)} Notion databases:\n")
    print(f"  {'#':>3}  {'':2}  {'Database':<40}  {'Last edited'}")
    print(f"  {'---':>3}  {'':2}  {'--------':<40}  {'-----------'}")

    for i, db in enumerate(databases, 1):
        marker = "*" if db["id"] in current_watched else " "
        title = db["title"][:40]
        edited = db["last_edited_time"][:10] if db["last_edited_time"] else "unknown"
        print(f"  {i:3d}  {marker:2}  {title:<40}  {edited}")

    if current_watched:
        print(f"\n  * = currently watched ({len(current_watched)} database(s))")

    # Interactive selection
    print("\nEnter numbers to watch (comma-separated), 'all' for all, or 'done' to keep current:")
    try:
        user_input = input("> ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        return

    if user_input.lower() == "done" or not user_input:
        print("Keeping current configuration.")
        return

    if user_input.lower() == "all":
        selected_ids = [db["id"] for db in databases]
    else:
        selected_ids = []
        for part in user_input.split(","):
            part = part.strip()
            try:
                idx = int(part) - 1
                if 0 <= idx < len(databases):
                    selected_ids.append(databases[idx]["id"])
                else:
                    print(f"  Skipping invalid number: {part}")
            except ValueError:
                print(f"  Skipping invalid input: {part}")

    if not selected_ids:
        print("No valid selections. Keeping current configuration.")
        return

    # Update config.yaml
    config_file = Path(config_path)
    if config_file.exists():
        raw_config = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
    else:
        raw_config = {}

    if "notion" not in raw_config:
        raw_config["notion"] = {}

    raw_config["notion"]["watched_databases"] = selected_ids

    config_file.write_text(yaml.dump(raw_config, default_flow_style=False), encoding="utf-8")

    selected_names = []
    for sid in selected_ids:
        for db in databases:
            if db["id"] == sid:
                selected_names.append(db["title"])
                break

    print(f"\nUpdated {config_path} with {len(selected_ids)} watched database(s):")
    for name in selected_names:
        print(f"  - {name}")
    print()
