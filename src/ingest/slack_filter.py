"""Slack message noise filtering.

Filters out bot messages, system notifications, trivial replies,
link-only messages, and empty messages before synthesis.
"""

from __future__ import annotations

import re

NOISE_SUBTYPES: set[str] = {
    "channel_join",
    "channel_leave",
    "channel_topic",
    "channel_purpose",
    "channel_name",
    "bot_add",
    "bot_remove",
}

TRIVIAL_PATTERN: re.Pattern[str] = re.compile(
    r"^(ok|thanks|lol|yes|no|sure|yep|nope|haha|nice|ty|\+1|:[\w+-]+:)$",
    re.IGNORECASE,
)

URL_ONLY_PATTERN: re.Pattern[str] = re.compile(r"^<https?://[^>]+>$")


def should_keep_message(msg: dict, bot_allowlist: list[str] | None = None) -> bool:
    """Return True if the message should be kept for synthesis.

    Filters out:
    - System/notification subtypes (joins, leaves, topic changes, etc.)
    - Bot messages unless the bot_id is in the allowlist
    - Tombstone messages (edited-away)
    - Trivial single-word responses (ok, thanks, lol, emoji-only, etc.)
    - Link-only messages
    - Empty messages (no text, no files, no attachments)
    """
    if bot_allowlist is None:
        bot_allowlist = []

    subtype = msg.get("subtype")

    # Filter noise subtypes
    if subtype in NOISE_SUBTYPES:
        return False

    # Filter tombstone messages
    if subtype == "tombstone":
        return False

    # Filter bot messages unless allowlisted
    if msg.get("bot_id") or subtype == "bot_message":
        bot_id = msg.get("bot_id", "")
        if bot_id not in bot_allowlist:
            return False

    text = msg.get("text", "").strip()

    # Empty messages with no files or attachments are noise (reactions-only)
    if not text and not msg.get("files") and not msg.get("attachments"):
        return False

    # Messages with files but no text are substantive (file uploads)
    if not text and (msg.get("files") or msg.get("attachments")):
        return True

    # Filter trivial single-word responses
    if TRIVIAL_PATTERN.match(text):
        return False

    # Filter link-only messages
    if URL_ONLY_PATTERN.match(text):
        return False

    return True
