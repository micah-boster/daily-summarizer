"""Slack webhook notification helper.

Sends fire-and-forget notifications via an incoming webhook URL.
The webhook URL must be set as the SLACK_WEBHOOK_URL environment variable.
"""

from __future__ import annotations

import logging
import os
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


def _split_text(text: str, max_len: int = MAX_BLOCK_TEXT) -> list[str]:
    """Split text into chunks that fit within Slack block limits."""
    if len(text) <= max_len:
        return [text]

    chunks = []
    remaining = text
    while remaining:
        if len(remaining) <= max_len:
            chunks.append(remaining)
            break

        cut_point = remaining.rfind("\n\n", 0, max_len)
        if cut_point == -1:
            cut_point = remaining.rfind("\n", 0, max_len)
        if cut_point == -1:
            cut_point = max_len

        chunks.append(remaining[:cut_point])
        remaining = remaining[cut_point:].lstrip("\n")

    return chunks


def _build_blocks(summary_content: str, target_date: date) -> list[dict]:
    """Build Slack Block Kit blocks from daily summary content."""
    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Daily Summary: {target_date.isoformat()}",
            },
        },
    ]

    chunks = _split_text(summary_content)
    for chunk in chunks:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": chunk,
            },
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
