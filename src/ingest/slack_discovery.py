"""Slack channel and DM discovery module.

Proposes active channels and DMs for the user to opt into,
with interactive CLI flow and periodic auto-suggest checks.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
from slack_sdk.errors import SlackApiError
from slack_sdk.web import WebClient

from src.config import PipelineConfig
from src.ingest.slack import (
    build_slack_client,
    load_slack_state,
    resolve_user_names,
    save_slack_state,
)

logger = logging.getLogger(__name__)

STOPWORDS: set[str] = {
    "the", "a", "an", "is", "are", "was", "were", "it", "to", "in", "for",
    "on", "with", "at", "by", "from", "of", "and", "or", "but", "not",
    "this", "that", "i", "we", "you", "they", "he", "she", "have", "has",
    "had", "do", "does", "did", "will", "would", "can", "could", "should",
    "be", "been", "being",
}

MIN_ACTIVITY_THRESHOLD = 5  # messages in lookback window


def get_user_channels(client: WebClient) -> list[dict]:
    """Get all channels the authenticated user is a member of.

    Returns list of dicts with: id, name, is_private, num_members.
    """
    channels: list[dict] = []
    cursor = None
    while True:
        kwargs: dict = {
            "types": "public_channel,private_channel",
            "limit": 200,
        }
        if cursor:
            kwargs["cursor"] = cursor
        try:
            resp = client.users_conversations(**kwargs)
            for ch in resp.get("channels", []):
                channels.append({
                    "id": ch["id"],
                    "name": ch.get("name", ch["id"]),
                    "is_private": ch.get("is_private", False),
                    "num_members": ch.get("num_members", 0),
                })
            cursor = resp.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        except SlackApiError as e:
            logger.warning("Failed to list user channels: %s", e)
            break
    return channels


def get_user_dms(client: WebClient) -> list[dict]:
    """Get all DMs and group DMs the authenticated user is in.

    Returns list of dicts with: id, is_im, is_mpim, partner_name(s).
    """
    dms: list[dict] = []
    cursor = None
    while True:
        kwargs: dict = {
            "types": "im,mpim",
            "limit": 200,
        }
        if cursor:
            kwargs["cursor"] = cursor
        try:
            resp = client.users_conversations(**kwargs)
            for ch in resp.get("channels", []):
                dm_info: dict = {
                    "id": ch["id"],
                    "is_im": ch.get("is_im", False),
                    "is_mpim": ch.get("is_mpim", False),
                }
                # Resolve partner name for 1:1 DMs
                if ch.get("is_im") and ch.get("user"):
                    names = resolve_user_names(client, {ch["user"]})
                    dm_info["partner_name"] = names.get(ch["user"], ch["user"])
                elif ch.get("is_mpim"):
                    # Group DM - resolve members
                    try:
                        members_resp = client.conversations_members(channel=ch["id"])
                        member_ids = set(members_resp.get("members", []))
                        names = resolve_user_names(client, member_ids)
                        name_list = sorted(names.values())
                        if len(name_list) > 3:
                            dm_info["partner_name"] = "group DM"
                        else:
                            dm_info["partner_name"] = ", ".join(name_list)
                    except SlackApiError:
                        dm_info["partner_name"] = "group DM"
                else:
                    dm_info["partner_name"] = ch["id"]

                dms.append(dm_info)
            cursor = resp.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        except SlackApiError as e:
            logger.warning("Failed to list user DMs: %s", e)
            break
    return dms


def compute_channel_stats(
    client: WebClient, channel_id: str, lookback_days: int = 7
) -> dict:
    """Compute activity stats for a channel over the lookback period.

    Returns dict with: message_count, participant_count, topic_keywords.
    """
    oldest = str(
        (datetime.now(timezone.utc) - timedelta(days=lookback_days)).timestamp()
    )
    latest = str(datetime.now(timezone.utc).timestamp())

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
            resp = client.conversations_history(**kwargs)
            messages.extend(resp.get("messages", []))
            cursor = resp.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        except SlackApiError as e:
            logger.warning("Failed to fetch stats for %s: %s", channel_id, e)
            break

    # Compute stats
    user_ids = {m.get("user", "") for m in messages if m.get("user")}

    # Extract topic keywords from message text
    word_counts: Counter[str] = Counter()
    for msg in messages:
        text = msg.get("text", "")
        words = text.lower().split()
        for word in words:
            # Strip punctuation
            clean = word.strip(".,!?:;'\"()[]<>")
            if len(clean) > 2 and clean not in STOPWORDS and clean.isalpha():
                word_counts[clean] += 1

    # Top 3 keywords
    top_keywords = [word for word, _ in word_counts.most_common(3)]

    return {
        "message_count": len(messages),
        "participant_count": len(user_ids),
        "topic_keywords": top_keywords,
    }


def discover_channels(
    client: WebClient, state: dict, config: PipelineConfig
) -> list[str]:
    """Interactive channel discovery flow.

    Shows already-configured channels, then proposes active unconfigured ones.
    Returns list of all confirmed channel IDs (existing + newly added).
    """
    configured_ids = set(config.slack.channels)
    state_channel_ids = set(state.get("channels", {}).keys())
    all_configured = configured_ids | state_channel_ids

    user_channels = get_user_channels(client)
    already_configured = [ch for ch in user_channels if ch["id"] in all_configured]
    unconfigured = [ch for ch in user_channels if ch["id"] not in all_configured]

    confirmed: list[str] = list(configured_ids)

    print("\n=== Slack Channel Discovery ===\n")

    # Show currently tracking
    if already_configured:
        print("Currently tracking:")
        for ch in already_configured:
            stats = compute_channel_stats(client, ch["id"])
            print(
                f"  #{ch['name']} ({stats['message_count']} messages, "
                f"{stats['participant_count']} participants last 7d)"
            )
        print()

    # Propose new channels
    new_count = 0
    for ch in unconfigured:
        stats = compute_channel_stats(client, ch["id"])
        if stats["message_count"] <= MIN_ACTIVITY_THRESHOLD:
            continue  # Skip low-activity channels

        keywords_str = ", ".join(stats["topic_keywords"]) if stats["topic_keywords"] else "general"
        prompt = (
            f"  Add #{ch['name']}? ({stats['message_count']} messages, "
            f"{stats['participant_count']} participants, "
            f"topics: {keywords_str}) [y/n/q]: "
        )

        if new_count == 0:
            print("New suggestions:")

        response = input(prompt).strip().lower()
        if response == "q":
            break
        if response == "y":
            confirmed.append(ch["id"])
            new_count += 1
        # 'n' or anything else = skip

    return confirmed


def discover_dms(
    client: WebClient, state: dict, config: PipelineConfig
) -> list[str]:
    """Interactive DM discovery flow.

    Proposes active DMs for user to opt into.
    Returns list of confirmed DM channel IDs.
    """
    configured_dm_ids = set(config.slack.dms)
    confirmed: list[str] = list(configured_dm_ids)

    user_dms = get_user_dms(client)

    print("\n=== Slack DM Discovery ===\n")

    for dm in user_dms:
        if dm["id"] in configured_dm_ids:
            continue  # Already configured

        stats = compute_channel_stats(client, dm["id"])
        if stats["message_count"] <= MIN_ACTIVITY_THRESHOLD:
            continue

        partner = dm.get("partner_name", dm["id"])
        if dm.get("is_mpim"):
            prompt = f"  Add group DM with {partner}? ({stats['message_count']} messages last 7d) [y/n/q]: "
        else:
            prompt = f"  Add DM with {partner}? ({stats['message_count']} messages last 7d) [y/n/q]: "

        response = input(prompt).strip().lower()
        if response == "q":
            break
        if response == "y":
            confirmed.append(dm["id"])

    return confirmed


def check_new_channels(
    client: WebClient, state: dict, config: PipelineConfig
) -> list[str]:
    """Non-interactive check for active untracked channels.

    Returns list of channel NAMES that are active but not configured.
    Does not prompt -- used by pipeline for periodic auto-suggest logging.
    """
    configured_ids = set(config.slack.channels)
    user_channels = get_user_channels(client)

    new_active: list[str] = []
    for ch in user_channels:
        if ch["id"] in configured_ids:
            continue
        stats = compute_channel_stats(client, ch["id"])
        if stats["message_count"] > MIN_ACTIVITY_THRESHOLD:
            new_active.append(ch["name"])

    return new_active


def _update_config_yaml(config_path: Path, channels: list[str], dms: list[str]) -> None:
    """Update config.yaml with confirmed channel and DM IDs."""
    with open(config_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if "slack" not in raw:
        raw["slack"] = {}

    raw["slack"]["channels"] = channels
    raw["slack"]["dms"] = dms

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(raw, f, default_flow_style=False, sort_keys=False)


def run_discovery(config: PipelineConfig) -> None:
    """Full discovery orchestrator.

    Builds client, runs channel and DM discovery, persists results.
    """
    client = build_slack_client()
    config_dir = Path("config")
    state = load_slack_state(config_dir)

    channels = discover_channels(client, state, config)
    dms = discover_dms(client, state, config)

    # Update config.yaml
    config_path = config_dir / "config.yaml"
    if config_path.exists():
        _update_config_yaml(config_path, channels, dms)

    # Update state with discovery metadata
    for ch_id in channels:
        state.setdefault("channels", {})[ch_id] = state.get("channels", {}).get(
            ch_id, {"name": ch_id}
        )

    for dm_id in dms:
        state.setdefault("dms", {})[dm_id] = state.get("dms", {}).get(
            dm_id, {"partner": dm_id}
        )

    save_slack_state(state, config_dir)

    print(f"\nDiscovery complete. Tracking {len(channels)} channels and {len(dms)} DMs.")
