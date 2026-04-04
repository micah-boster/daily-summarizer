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

logger = logging.getLogger(__name__)

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")

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
        response = httpx.post(
            SLACK_WEBHOOK_URL,
            json={"text": message},
            timeout=10.0,
        )
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


def _extract_bullet_items(content: str, section_name: str) -> list[str]:
    """Extract decision/commitment/question bullet items across all per-meeting sections.

    Returns condensed one-liners stripped of attribution and context.
    """
    items: list[str] = []

    # Find per-meeting extraction blocks
    pattern = rf"\*\*{section_name}:\*\*\n?(.*?)(?=\n\*\*[A-Z]|\n###|\n---|\Z)"
    for match in re.finditer(pattern, content, re.DOTALL):
        raw = match.group(1).strip()
        if not raw:
            continue
        # Split on "- " at start of line
        for bullet in re.split(r"(?:^|\n)-\s+", raw):
            bullet = bullet.strip()
            if not bullet:
                continue
            # Strip attribution in parens and " — reason" suffixes
            bullet = re.sub(r"\s*\([^)]*\)", "", bullet)
            bullet = re.sub(r"\s*—\s*.*$", "", bullet)
            # Truncate long items
            if len(bullet) > 120:
                bullet = bullet[:117] + "..."
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

    # Decisions
    decisions = _extract_bullet_items(summary_content, "Decisions")
    if decisions:
        blocks.append({"type": "divider"})
        bullet_text = "\n".join(f"• {d}" for d in decisions[:8])
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*:white_check_mark: Decisions*\n{bullet_text}"},
        })

    # Commitments / Action Items
    commitments = _extract_bullet_items(summary_content, "Commitments")
    if commitments:
        blocks.append({"type": "divider"})
        bullet_text = "\n".join(f"• {d}" for d in commitments[:8])
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*:point_right: Action Items*\n{bullet_text}"},
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
        response = httpx.post(url, json=payload, timeout=10)
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
