"""Slack webhook notification helper.

Sends fire-and-forget notifications via an incoming webhook URL.
The webhook URL must be set as the SLACK_WEBHOOK_URL environment variable.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from datetime import date

import httpx

from src.retry import retry_api_call

logger = logging.getLogger(__name__)

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")


@retry_api_call
def _post_with_retry(url: str, payload: dict):
    """Post to a webhook URL with retry on transient errors."""
    return httpx.post(url, json=payload, timeout=10.0)

# Slack block text limit
MAX_BLOCK_TEXT = 3000


def notify_slack(message: str) -> bool:
    """Send a notification to Slack via incoming webhook.

    Args:
        message: Plain text message to send.

    Returns:
        True if the notification was sent successfully, False otherwise.
        Logs to stderr if the webhook URL is not configured.
    """
    if not SLACK_WEBHOOK_URL:
        print(
            "SLACK_WEBHOOK_URL not set, skipping notification",
            file=sys.stderr,
        )
        return False

    try:
        response = _post_with_retry(SLACK_WEBHOOK_URL, {"text": message})
        return response.status_code == 200
    except httpx.HTTPError as exc:
        print(f"Slack notification failed: {exc}", file=sys.stderr)
        return False


def _extract_overview(content: str) -> str:
    """Pull the overview stats line (e.g. '10 meetings, 5.0 hours...')."""
    m = re.search(r"^## Overview\n+(.*?)(?=\n#|\Z)", content, re.MULTILINE | re.DOTALL)
    if m:
        return m.group(1).strip().split("\n")[0]
    return ""


def _extract_table_rows(content: str, section_name: str) -> list[list[str]]:
    """Extract rows from a markdown table under a ## heading.

    Returns list of rows, where each row is a list of cell values.
    Skips the header and separator rows.
    """
    rows: list[list[str]] = []

    pattern = rf"^## {section_name}\s*\n(.*?)(?=\n## |\n---|\Z)"
    m = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    if not m:
        return rows

    section_text = m.group(1).strip()
    header_seen = False
    separator_seen = False

    for line in section_text.split("\n"):
        line = line.strip()
        if not line.startswith("|"):
            continue
        # Skip header row
        if not header_seen:
            header_seen = True
            continue
        # Skip separator row (|---|---|)
        if not separator_seen:
            separator_seen = True
            continue
        # Data row
        cells = [c.strip() for c in line.split("|")]
        # Split produces empty strings at start/end from leading/trailing |
        cells = [c for c in cells if c]
        if cells:
            rows.append(cells)

    return rows


def _extract_bullet_items(content: str, section_name: str) -> list[str]:
    """Extract items from top-level synthesis sections.

    Handles both markdown tables and bullet lists.
    Falls back to per-meeting extraction blocks if top-level is empty.
    """
    # Try table format first
    rows = _extract_table_rows(content, section_name)
    if rows:
        # Return rows as pipe-joined strings for downstream parsing
        return [" — ".join(cells) for cells in rows]

    # Try bullet format
    items: list[str] = []
    pattern = rf"^## {section_name}\s*\n(.*?)(?=\n## |\n---|\Z)"
    m = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    if m:
        section_text = m.group(1).strip()
        for line in section_text.split("\n"):
            line = line.strip()
            if line.startswith("- "):
                bullet = line[2:].strip()
                if bullet and bullet.lower() not in ("no items for this day.", "no transcript data available yet."):
                    if len(bullet) > 150:
                        bullet = bullet[:147] + "..."
                    items.append(bullet)

    # Fall back to per-meeting extraction blocks
    if not items:
        pattern = rf"\*\*{section_name}:\*\*\n?(.*?)(?=\n\*\*[A-Z]|\n###|\n---|\Z)"
        for match in re.finditer(pattern, content, re.DOTALL):
            raw = match.group(1).strip()
            if not raw:
                continue
            for line in raw.split("\n"):
                line = line.strip()
                if line.startswith("- "):
                    bullet = line[2:].strip()
                    if bullet and len(bullet) > 150:
                        bullet = bullet[:147] + "..."
                    if bullet:
                        items.append(bullet)

    return items


def _extract_meeting_names(content: str) -> list[str]:
    """Get meeting names from per-meeting extraction headings."""
    names = []
    for m in re.finditer(r"^### (.+?)\s*\(", content, re.MULTILINE):
        names.append(m.group(1).strip())
    return names


def _build_blocks(summary_content: str, target_date: date) -> list[dict]:
    """Build a condensed Slack digest from the full daily summary.

    This is NOT a dump of the MD file. It's a tight executive overview:
    stats → decisions → action items → open questions.
    """
    blocks: list[dict] = []

    # Header
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": f":memo: {target_date.strftime('%A, %B %-d')}",
        },
    })

    # Overview stats
    overview = _extract_overview(summary_content)
    meetings = _extract_meeting_names(summary_content)
    stats_parts = []
    if overview:
        stats_parts.append(overview)
    if meetings:
        stats_parts.append("Transcripts: " + ", ".join(meetings))
    if stats_parts:
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": "\n".join(stats_parts)}],
        })

    # Decisions — each as a labeled block
    decisions = _extract_bullet_items(summary_content, "Decisions")
    if decisions:
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*:white_check_mark: Decisions*"},
        })
        for item in decisions[:8]:
            parts = [p.strip() for p in item.split("—")]
            what = parts[0] if parts else item
            who = parts[1] if len(parts) > 1 else ""
            source = parts[2] if len(parts) > 2 else ""
            line = f"• *{what}*"
            if who:
                line += f"\n   _By {who}_"
            if source:
                line += f" · _{source}_"
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": line},
            })

    # Commitments / Action Items — each with labeled owner/deadline
    commitments = _extract_bullet_items(summary_content, "Commitments")
    if commitments:
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*:point_right: Action Items*"},
        })
        for item in commitments[:10]:
            parts = [p.strip() for p in item.split("—")]
            what = parts[0] if parts else item
            owner = parts[1] if len(parts) > 1 else ""
            deadline = parts[2] if len(parts) > 2 else ""
            source = parts[3] if len(parts) > 3 else ""
            line = f"• *{what}*"
            meta = []
            if owner:
                meta.append(owner)
            if deadline and deadline.lower() != "no deadline":
                meta.append(f"by {deadline}")
            if source:
                meta.append(source)
            if meta:
                line += f"\n   _" + " · ".join(meta) + "_"
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": line},
            })

    # Open Questions
    questions = _extract_bullet_items(summary_content, "Open Questions")
    if questions:
        blocks.append({"type": "divider"})
        bullet_text = "\n".join(f"• {d}" for d in questions[:5])
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*:grey_question: Open Questions*\n{bullet_text}"},
        })

    # No transcript data case
    if not decisions and not commitments and not questions:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "_No transcript data extracted for this day._"},
        })

    # Footer
    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": "_Full details in daily summary file._"}],
    })

    return blocks


def send_slack_summary(
    summary_content: str,
    target_date: date,
    webhook_url: str | None = None,
) -> bool:
    """Post the full daily summary to Slack via incoming webhook.

    Args:
        summary_content: The markdown content of the daily summary.
        target_date: The date the summary covers.
        webhook_url: Slack webhook URL. Falls back to SLACK_WEBHOOK_URL env var.

    Returns:
        True if sent successfully, False otherwise.
    """
    url = webhook_url or SLACK_WEBHOOK_URL or os.environ.get("SLACK_WEBHOOK_URL")
    if not url:
        logger.debug("No SLACK_WEBHOOK_URL configured, skipping notification")
        return False

    blocks = _build_blocks(summary_content, target_date)
    payload = {
        "text": f"Daily Summary: {target_date.isoformat()}",
        "blocks": blocks,
    }

    try:
        response = _post_with_retry(url, payload)
        if response.status_code == 200:
            logger.info("Slack notification sent for %s", target_date)
            return True
        else:
            logger.warning(
                "Slack webhook returned %s: %s", response.status_code, response.text
            )
            return False
    except Exception as e:
        logger.warning("Failed to send Slack notification: %s", e)
        return False
