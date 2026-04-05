"""Slack ingestion module.

Fetches messages from configured Slack channels and DMs, expands active
threads, applies noise filtering, and converts to SourceItem objects.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from slack_sdk.errors import SlackApiError
from slack_sdk.http_retry.builtin_handlers import RateLimitErrorRetryHandler
from slack_sdk.web import WebClient

from src.ingest.slack_filter import should_keep_message
from src.models.sources import ContentType, SourceItem, SourceType
from src.retry import retry_api_call

logger = logging.getLogger(__name__)

@retry_api_call
def _slack_users_info_with_retry(client, uid):
    """Call Slack users_info with retry on transient errors."""
    return client.users_info(user=uid)


@retry_api_call
def _slack_conversations_history_with_retry(client, **kwargs):
    """Call Slack conversations_history with retry on transient errors."""
    return client.conversations_history(**kwargs)


# Module-level cache for user ID -> display name resolution
_user_cache: dict[str, str] = {}

# Module-level cache for channel ID -> channel name
_channel_name_cache: dict[str, str] = {}


def build_slack_client(token: str | None = None) -> WebClient:
    """Initialize a Slack WebClient with rate-limit retry handling.

    Args:
        token: Bot token. Falls back to SLACK_BOT_TOKEN env var.

    Returns:
        Configured WebClient.

    Raises:
        ValueError: If no token is available.
    """
    token = token or os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        raise ValueError(
            "No Slack bot token found. Set SLACK_BOT_TOKEN env var "
            "or pass token directly."
        )
    client = WebClient(token=token)
    client.retry_handlers.append(RateLimitErrorRetryHandler(max_retry_count=2))
    return client


def resolve_user_names(
    client: WebClient, user_ids: set[str]
) -> dict[str, str]:
    """Batch resolve Slack user IDs to display names.

    Uses a module-level cache to avoid repeated API calls across channels.

    Args:
        client: Authenticated Slack WebClient.
        user_ids: Set of user IDs to resolve.

    Returns:
        Dict mapping user_id -> display name.
    """
    result: dict[str, str] = {}
    for uid in user_ids:
        if uid in _user_cache:
            result[uid] = _user_cache[uid]
            continue
        try:
            resp = _slack_users_info_with_retry(client, uid)
            profile = resp["user"].get("profile", {})
            name = (
                profile.get("display_name")
                or resp["user"].get("real_name")
                or uid
            )
            # Strip empty strings
            if not name.strip():
                name = uid
            _user_cache[uid] = name
            result[uid] = name
        except SlackApiError as e:
            logger.warning("Failed to resolve user %s: %s", uid, e)
            _user_cache[uid] = uid
            result[uid] = uid
    return result


def load_slack_state(config_dir: Path) -> dict:
    """Load Slack ingestion state from disk.

    Args:
        config_dir: Directory containing slack_state.json.

    Returns:
        State dict with 'channels' and 'dms' keys.
    """
    state_path = config_dir / "slack_state.json"
    if state_path.exists():
        with open(state_path, encoding="utf-8") as f:
            return json.load(f)
    return {"channels": {}, "dms": {}}


def save_slack_state(state: dict, config_dir: Path) -> None:
    """Write Slack ingestion state atomically.

    Args:
        state: State dict to persist.
        config_dir: Directory for slack_state.json.
    """
    state_path = config_dir / "slack_state.json"
    config_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = state_path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    tmp_path.replace(state_path)


def fetch_channel_messages(
    client: WebClient, channel_id: str, oldest: str, latest: str
) -> list[dict]:
    """Fetch all messages from a channel in a time window.

    Uses cursor pagination with limit=200.

    Args:
        client: Authenticated Slack WebClient.
        channel_id: Channel to fetch from.
        oldest: Start timestamp (string).
        latest: End timestamp (string).

    Returns:
        List of raw message dicts.
    """
    messages: list[dict] = []
    cursor = None
    while True:
        kwargs: dict = {
            "channel": channel_id,
            "oldest": oldest,
            "latest": latest,
            "limit": 200,
        }
        if cursor:
            kwargs["cursor"] = cursor
        try:
            resp = _slack_conversations_history_with_retry(client, **kwargs)
            messages.extend(resp.get("messages", []))
            cursor = resp.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        except SlackApiError as e:
            logger.warning(
                "Failed to fetch messages from %s: %s", channel_id, e
            )
            break
    return messages


def fetch_thread_replies(
    client: WebClient, channel_id: str, thread_ts: str
) -> list[dict]:
    """Fetch all reply messages in a thread.

    Skips the first message on the first page (it's the parent,
    already present in channel history).

    Args:
        client: Authenticated Slack WebClient.
        channel_id: Channel containing the thread.
        thread_ts: Thread parent timestamp.

    Returns:
        List of reply message dicts (excluding parent).
    """
    replies: list[dict] = []
    cursor = None
    first_page = True
    while True:
        kwargs: dict = {
            "channel": channel_id,
            "ts": thread_ts,
            "limit": 200,
        }
        if cursor:
            kwargs["cursor"] = cursor
        try:
            resp = client.conversations_replies(**kwargs)
            page_messages = resp.get("messages", [])
            if first_page and page_messages:
                # Skip parent message (first item on first page)
                page_messages = page_messages[1:]
                first_page = False
            replies.extend(page_messages)
            cursor = resp.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        except SlackApiError as e:
            logger.warning(
                "Failed to fetch thread replies for %s in %s: %s",
                thread_ts,
                channel_id,
                e,
            )
            break
    return replies


def should_expand_thread(msg: dict, config: dict) -> bool:
    """Check if a thread should be fully expanded based on activity thresholds.

    Both conditions must be met (AND logic per user decision):
    - reply_count >= thread_min_replies (default 3)
    - reply_users_count >= thread_min_participants (default 2)

    Args:
        msg: Raw Slack message dict (must have reply_count, reply_users_count).
        config: Full config dict with slack section.

    Returns:
        True if thread should be expanded.
    """
    slack_config = config.get("slack", {})
    min_replies = slack_config.get("thread_min_replies", 3)
    min_participants = slack_config.get("thread_min_participants", 2)

    reply_count = msg.get("reply_count", 0)
    reply_users_count = msg.get("reply_users_count", 0)

    return reply_count >= min_replies and reply_users_count >= min_participants


def message_to_source_item(
    msg: dict,
    channel_name: str,
    channel_id: str,
    user_map: dict[str, str],
    is_dm: bool = False,
    dm_partner: str | None = None,
    reply_count: int | None = None,
) -> SourceItem:
    """Convert a raw Slack message dict to a SourceItem.

    Args:
        msg: Raw Slack message dict.
        channel_name: Human-readable channel name.
        channel_id: Slack channel ID.
        user_map: Mapping of user_id -> display name.
        is_dm: Whether this is from a DM conversation.
        dm_partner: Display name of DM partner (for attribution).
        reply_count: Number of thread replies (for hint in content).

    Returns:
        SourceItem representing this message.
    """
    user_id = msg.get("user", "unknown")
    user_name = user_map.get(user_id, user_id)

    text = msg.get("text", "")
    if reply_count and reply_count > 0:
        text = f"{text} ({reply_count} replies)"

    ts = msg.get("ts", "0")
    timestamp = datetime.fromtimestamp(float(ts), tz=timezone.utc)

    if is_dm:
        display_ctx = f"Slack DM with {dm_partner}" if dm_partner else "Slack DM"
    else:
        display_ctx = f"Slack #{channel_name}"

    return SourceItem(
        id=f"slack_{channel_id}_{ts}",
        source_type=SourceType.SLACK_MESSAGE,
        content_type=ContentType.MESSAGE,
        title=f"Message from {user_name}",
        timestamp=timestamp,
        content=text,
        participants=[user_name],
        source_url=f"https://slack.com/archives/{channel_id}/p{ts.replace('.', '')}",
        display_context=display_ctx,
        context={
            "channel_id": channel_id,
            "thread_ts": msg.get("thread_ts"),
            "reply_count": reply_count or 0,
        },
        raw_data=msg,
    )


def thread_to_source_item(
    parent_msg: dict,
    replies: list[dict],
    channel_name: str,
    channel_id: str,
    user_map: dict[str, str],
) -> SourceItem:
    """Convert an expanded thread to a single SourceItem.

    Args:
        parent_msg: The thread parent message dict.
        replies: List of reply message dicts.
        channel_name: Human-readable channel name.
        channel_id: Slack channel ID.
        user_map: Mapping of user_id -> display name.

    Returns:
        SourceItem representing the full thread.
    """
    parent_user = user_map.get(parent_msg.get("user", "unknown"), "unknown")
    parent_text = parent_msg.get("text", "")

    # Build thread content: parent + all replies
    lines = [f"{parent_user}: {parent_text}"]
    all_participants = {parent_user}

    for reply in replies:
        reply_user = user_map.get(reply.get("user", "unknown"), "unknown")
        reply_text = reply.get("text", "")
        lines.append(f"{reply_user}: {reply_text}")
        all_participants.add(reply_user)

    ts = parent_msg.get("ts", "0")
    timestamp = datetime.fromtimestamp(float(ts), tz=timezone.utc)

    # Truncate title
    title_text = parent_text[:80]
    if len(parent_text) > 80:
        title_text += "..."

    return SourceItem(
        id=f"slack_{channel_id}_{ts}_thread",
        source_type=SourceType.SLACK_THREAD,
        content_type=ContentType.THREAD,
        title=f"Thread: {title_text}",
        timestamp=timestamp,
        content="\n".join(lines),
        participants=sorted(all_participants),
        source_url=f"https://slack.com/archives/{channel_id}/p{ts.replace('.', '')}",
        display_context=f"Slack #{channel_name}",
        context={
            "reply_count": len(replies),
            "channel_id": channel_id,
        },
        raw_data=parent_msg,
    )


def _resolve_channel_name(client: WebClient, channel_id: str) -> str:
    """Resolve a channel ID to its name, with caching."""
    if channel_id in _channel_name_cache:
        return _channel_name_cache[channel_id]
    try:
        resp = client.conversations_info(channel=channel_id)
        name = resp["channel"].get("name", channel_id)
        _channel_name_cache[channel_id] = name
        return name
    except SlackApiError:
        _channel_name_cache[channel_id] = channel_id
        return channel_id


def _resolve_dm_partner(
    client: WebClient, channel_id: str, user_map: dict[str, str]
) -> str:
    """Resolve the partner name(s) for a DM or group DM."""
    try:
        resp = client.conversations_info(channel=channel_id)
        channel_info = resp.get("channel", {})

        # For 1:1 DMs
        if channel_info.get("is_im"):
            partner_id = channel_info.get("user", "")
            if partner_id:
                names = resolve_user_names(client, {partner_id})
                return names.get(partner_id, partner_id)
            return "unknown"

        # For group DMs (mpim)
        if channel_info.get("is_mpim"):
            members_resp = client.conversations_members(channel=channel_id)
            member_ids = set(members_resp.get("members", []))
            names = resolve_user_names(client, member_ids)
            name_list = sorted(names.values())
            if len(name_list) > 3:
                return "group DM"
            return ", ".join(name_list)

        return channel_id
    except SlackApiError:
        return channel_id


def fetch_slack_items(
    config: dict, target_date: date | None = None
) -> list[SourceItem]:
    """Main orchestrator: fetch all Slack items and return as SourceItems.

    Fetches messages from configured channels and DMs, applies filtering,
    expands active threads, and converts to SourceItem objects.

    When target_date is provided, fetches messages from that date's boundaries
    in the configured timezone (for backfill). Otherwise defaults to today.

    Args:
        config: Full config dict with 'slack' section.
        target_date: Date to fetch messages for. Defaults to today.

    Returns:
        List of SourceItems sorted by timestamp.
    """
    from datetime import date as date_type
    from zoneinfo import ZoneInfo

    slack_config = config.get("slack", {})
    if not slack_config.get("enabled", False):
        return []

    if target_date is None:
        target_date = date_type.today()

    client = build_slack_client()
    config_dir = Path("config")
    state = load_slack_state(config_dir)
    bot_allowlist = slack_config.get("bot_allowlist", [])
    max_per_channel = slack_config.get("max_messages_per_channel", 100)

    all_items: list[SourceItem] = []

    # Compute time window from target_date boundaries in configured timezone
    tz_name = config.get("pipeline", {}).get("timezone", "America/New_York")
    tz = ZoneInfo(tz_name)
    day_start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=tz)
    day_end = day_start + timedelta(days=1)
    date_oldest_ts = str(day_start.timestamp())
    date_latest_ts = str(day_end.timestamp())

    # --- Channels ---
    for channel_id in slack_config.get("channels", []):
        try:
            # Use target_date boundaries for the time window
            oldest = date_oldest_ts
            latest = date_latest_ts

            channel_name = _resolve_channel_name(client, channel_id)
            messages = fetch_channel_messages(client, channel_id, oldest, latest)

            if not messages:
                logger.info("No new messages in #%s", channel_name)
                continue

            logger.info(
                "Fetched %d messages from #%s", len(messages), channel_name
            )

            # Resolve user names
            user_ids = {m.get("user", "") for m in messages if m.get("user")}
            user_map = resolve_user_names(client, user_ids)

            # Filter noise
            filtered = [m for m in messages if should_keep_message(m, bot_allowlist)]

            # Volume cap: keep most recent N
            if len(filtered) > max_per_channel:
                # Messages come in reverse chronological, sort by ts ascending
                filtered.sort(key=lambda m: m.get("ts", "0"))
                filtered = filtered[-max_per_channel:]

            # Process messages
            channel_items: list[SourceItem] = []
            expanded_thread_ts: set[str] = set()

            for msg in filtered:
                # Check for thread expansion
                if msg.get("reply_count", 0) > 0 and should_expand_thread(
                    msg, config
                ):
                    # Expand thread
                    thread_ts = msg.get("ts", "")
                    replies = fetch_thread_replies(client, channel_id, thread_ts)
                    item = thread_to_source_item(
                        msg, replies, channel_name, channel_id, user_map
                    )
                    channel_items.append(item)
                    expanded_thread_ts.add(thread_ts)
                elif msg.get("reply_count", 0) > 0:
                    # Thread below threshold: show as message with reply count hint
                    item = message_to_source_item(
                        msg,
                        channel_name,
                        channel_id,
                        user_map,
                        reply_count=msg.get("reply_count", 0),
                    )
                    channel_items.append(item)
                else:
                    # Regular message (no thread)
                    item = message_to_source_item(
                        msg, channel_name, channel_id, user_map
                    )
                    channel_items.append(item)

            all_items.extend(channel_items)

            # Update state with latest timestamp
            if messages:
                latest_ts = max(m.get("ts", "0") for m in messages)
                state.setdefault("channels", {})[channel_id] = {
                    "last_ts": latest_ts,
                    "name": channel_name,
                }

        except SlackApiError as e:
            logger.warning("Failed to process channel %s: %s", channel_id, e)
        except Exception as e:
            logger.warning("Unexpected error processing channel %s: %s", channel_id, e)

    # --- DMs ---
    for dm_id in slack_config.get("dms", []):
        try:
            # Use target_date boundaries for the time window
            oldest = date_oldest_ts
            latest = date_latest_ts

            messages = fetch_channel_messages(client, dm_id, oldest, latest)

            if not messages:
                continue

            # Resolve DM partner name
            user_ids = {m.get("user", "") for m in messages if m.get("user")}
            user_map = resolve_user_names(client, user_ids)
            dm_partner = _resolve_dm_partner(client, dm_id, user_map)

            logger.info(
                "Fetched %d messages from DM with %s", len(messages), dm_partner
            )

            # Filter noise
            filtered = [m for m in messages if should_keep_message(m, bot_allowlist)]

            # Volume cap
            if len(filtered) > max_per_channel:
                filtered.sort(key=lambda m: m.get("ts", "0"))
                filtered = filtered[-max_per_channel:]

            for msg in filtered:
                item = message_to_source_item(
                    msg,
                    dm_id,
                    dm_id,
                    user_map,
                    is_dm=True,
                    dm_partner=dm_partner,
                )
                all_items.append(item)

            # Update state
            if messages:
                latest_ts = max(m.get("ts", "0") for m in messages)
                state.setdefault("dms", {})[dm_id] = {
                    "last_ts": latest_ts,
                    "partner": dm_partner,
                }

        except SlackApiError as e:
            logger.warning("Failed to process DM %s: %s", dm_id, e)
        except Exception as e:
            logger.warning("Unexpected error processing DM %s: %s", dm_id, e)

    # Save updated state
    save_slack_state(state, config_dir)

    # Sort all items by timestamp
    all_items.sort(key=lambda item: item.timestamp)
    return all_items
