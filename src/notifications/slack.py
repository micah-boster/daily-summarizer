"""Slack webhook notification helper.

Sends fire-and-forget notifications via an incoming webhook URL.
The webhook URL must be set as the SLACK_WEBHOOK_URL environment variable.
"""

import os
import sys

import httpx

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")


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
