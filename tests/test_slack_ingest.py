"""Tests for Slack ingestion and filtering."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.ingest.slack import (
    build_slack_client,
    load_slack_state,
    message_to_source_item,
    save_slack_state,
    should_expand_thread,
    thread_to_source_item,
)
from src.ingest.slack_filter import (
    NOISE_SUBTYPES,
    TRIVIAL_PATTERN,
    URL_ONLY_PATTERN,
    should_keep_message,
)


class TestShouldKeepMessage:
    """Tests for the should_keep_message filter function."""

    def test_normal_message_passes(self):
        msg = {"text": "Hey team, the deploy is done.", "user": "U123"}
        assert should_keep_message(msg) is True

    def test_message_with_substance_passes(self):
        msg = {"text": "We need to discuss the new API design before Friday", "user": "U123"}
        assert should_keep_message(msg) is True

    def test_noise_subtype_channel_join_filtered(self):
        msg = {"text": "joined #general", "subtype": "channel_join"}
        assert should_keep_message(msg) is False

    def test_noise_subtype_channel_leave_filtered(self):
        msg = {"text": "left #general", "subtype": "channel_leave"}
        assert should_keep_message(msg) is False

    def test_noise_subtype_channel_topic_filtered(self):
        msg = {"text": "set the topic", "subtype": "channel_topic"}
        assert should_keep_message(msg) is False

    def test_noise_subtype_channel_purpose_filtered(self):
        msg = {"text": "set the purpose", "subtype": "channel_purpose"}
        assert should_keep_message(msg) is False

    def test_noise_subtype_channel_name_filtered(self):
        msg = {"text": "renamed channel", "subtype": "channel_name"}
        assert should_keep_message(msg) is False

    def test_noise_subtype_bot_add_filtered(self):
        msg = {"text": "added a bot", "subtype": "bot_add"}
        assert should_keep_message(msg) is False

    def test_noise_subtype_bot_remove_filtered(self):
        msg = {"text": "removed a bot", "subtype": "bot_remove"}
        assert should_keep_message(msg) is False

    def test_all_noise_subtypes_covered(self):
        expected = {"channel_join", "channel_leave", "channel_topic",
                    "channel_purpose", "channel_name", "bot_add", "bot_remove"}
        assert NOISE_SUBTYPES == expected

    def test_tombstone_message_filtered(self):
        msg = {"text": "", "subtype": "tombstone"}
        assert should_keep_message(msg) is False

    def test_bot_message_filtered_by_default(self):
        msg = {"text": "Automated build passed", "bot_id": "B123"}
        assert should_keep_message(msg) is False

    def test_bot_message_subtype_filtered(self):
        msg = {"text": "Build #42 succeeded", "subtype": "bot_message"}
        assert should_keep_message(msg) is False

    def test_bot_message_allowed_via_allowlist(self):
        msg = {"text": "Important bot update", "bot_id": "B_ALLOWED"}
        assert should_keep_message(msg, bot_allowlist=["B_ALLOWED"]) is True

    def test_bot_message_not_in_allowlist_still_filtered(self):
        msg = {"text": "Spam bot", "bot_id": "B_SPAM"}
        assert should_keep_message(msg, bot_allowlist=["B_OTHER"]) is False

    def test_trivial_ok_filtered(self):
        msg = {"text": "ok", "user": "U123"}
        assert should_keep_message(msg) is False

    def test_trivial_thanks_filtered(self):
        msg = {"text": "thanks", "user": "U123"}
        assert should_keep_message(msg) is False

    def test_trivial_lol_filtered(self):
        msg = {"text": "lol", "user": "U123"}
        assert should_keep_message(msg) is False

    def test_trivial_yes_filtered(self):
        msg = {"text": "yes", "user": "U123"}
        assert should_keep_message(msg) is False

    def test_trivial_no_filtered(self):
        msg = {"text": "no", "user": "U123"}
        assert should_keep_message(msg) is False

    def test_trivial_sure_filtered(self):
        msg = {"text": "Sure", "user": "U123"}
        assert should_keep_message(msg) is False

    def test_trivial_yep_filtered(self):
        msg = {"text": "YEP", "user": "U123"}
        assert should_keep_message(msg) is False

    def test_trivial_plus_one_filtered(self):
        msg = {"text": "+1", "user": "U123"}
        assert should_keep_message(msg) is False

    def test_trivial_emoji_only_filtered(self):
        msg = {"text": ":thumbsup:", "user": "U123"}
        assert should_keep_message(msg) is False

    def test_trivial_emoji_with_hyphen_filtered(self):
        msg = {"text": ":heavy-check-mark:", "user": "U123"}
        assert should_keep_message(msg) is False

    def test_trivial_ty_filtered(self):
        msg = {"text": "ty", "user": "U123"}
        assert should_keep_message(msg) is False

    def test_trivial_case_insensitive(self):
        msg = {"text": "OK", "user": "U123"}
        assert should_keep_message(msg) is False

    def test_multi_word_not_trivial(self):
        msg = {"text": "ok sounds good", "user": "U123"}
        assert should_keep_message(msg) is True

    def test_link_only_filtered(self):
        msg = {"text": "<https://example.com/page>", "user": "U123"}
        assert should_keep_message(msg) is False

    def test_link_with_text_passes(self):
        msg = {"text": "Check this out: <https://example.com/page>", "user": "U123"}
        assert should_keep_message(msg) is True

    def test_empty_message_no_files_filtered(self):
        msg = {"text": "", "user": "U123"}
        assert should_keep_message(msg) is False

    def test_empty_text_no_text_key_filtered(self):
        msg = {"user": "U123"}
        assert should_keep_message(msg) is False

    def test_whitespace_only_message_filtered(self):
        msg = {"text": "   ", "user": "U123"}
        assert should_keep_message(msg) is False

    def test_message_with_files_but_no_text_passes(self):
        msg = {"text": "", "user": "U123", "files": [{"id": "F123"}]}
        assert should_keep_message(msg) is True

    def test_message_with_attachments_but_no_text_passes(self):
        msg = {"text": "", "user": "U123", "attachments": [{"text": "preview"}]}
        assert should_keep_message(msg) is True

    def test_default_bot_allowlist_is_empty(self):
        # Passing None should default to empty allowlist
        msg = {"text": "bot msg", "bot_id": "B1"}
        assert should_keep_message(msg, bot_allowlist=None) is False


class TestFilterPatterns:
    """Tests for exported filter patterns."""

    def test_trivial_pattern_matches_nope(self):
        assert TRIVIAL_PATTERN.match("nope") is not None

    def test_trivial_pattern_matches_haha(self):
        assert TRIVIAL_PATTERN.match("haha") is not None

    def test_trivial_pattern_matches_nice(self):
        assert TRIVIAL_PATTERN.match("nice") is not None

    def test_trivial_pattern_does_not_match_sentence(self):
        assert TRIVIAL_PATTERN.match("that sounds nice actually") is None

    def test_url_only_pattern_matches_slack_url(self):
        assert URL_ONLY_PATTERN.match("<https://example.com/path?q=1>") is not None

    def test_url_only_pattern_does_not_match_text_with_url(self):
        assert URL_ONLY_PATTERN.match("see <https://example.com>") is None


# ============================================================
# Tests for src/ingest/slack.py (Task 2)
# ============================================================


class TestBuildSlackClient:
    """Tests for build_slack_client."""

    def test_raises_without_token(self):
        import pytest

        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="No Slack bot token"):
                build_slack_client(token=None)

    def test_builds_with_explicit_token(self):
        client = build_slack_client(token="xoxb-test-token")
        assert client is not None
        assert client.token == "xoxb-test-token"

    def test_builds_from_env(self):
        with patch.dict("os.environ", {"SLACK_BOT_TOKEN": "xoxb-env-token"}):
            client = build_slack_client()
            assert client.token == "xoxb-env-token"


class TestShouldExpandThread:
    """Tests for should_expand_thread."""

    def test_expands_when_both_thresholds_met(self):
        msg = {"reply_count": 5, "reply_users_count": 3}
        config = {"slack": {"thread_min_replies": 3, "thread_min_participants": 2}}
        assert should_expand_thread(msg, config) is True

    def test_does_not_expand_below_reply_threshold(self):
        msg = {"reply_count": 2, "reply_users_count": 3}
        config = {"slack": {"thread_min_replies": 3, "thread_min_participants": 2}}
        assert should_expand_thread(msg, config) is False

    def test_does_not_expand_below_participant_threshold(self):
        msg = {"reply_count": 5, "reply_users_count": 1}
        config = {"slack": {"thread_min_replies": 3, "thread_min_participants": 2}}
        assert should_expand_thread(msg, config) is False

    def test_does_not_expand_both_below_threshold(self):
        msg = {"reply_count": 1, "reply_users_count": 1}
        config = {"slack": {"thread_min_replies": 3, "thread_min_participants": 2}}
        assert should_expand_thread(msg, config) is False

    def test_uses_defaults_when_config_missing(self):
        msg = {"reply_count": 3, "reply_users_count": 2}
        config = {}  # No slack section
        assert should_expand_thread(msg, config) is True

    def test_exact_threshold_matches(self):
        msg = {"reply_count": 3, "reply_users_count": 2}
        config = {"slack": {"thread_min_replies": 3, "thread_min_participants": 2}}
        assert should_expand_thread(msg, config) is True

    def test_missing_reply_fields_default_to_zero(self):
        msg = {}
        config = {"slack": {"thread_min_replies": 3, "thread_min_participants": 2}}
        assert should_expand_thread(msg, config) is False


class TestMessageToSourceItem:
    """Tests for message_to_source_item."""

    def _make_msg(self, **overrides):
        base = {
            "ts": "1712000000.000100",
            "user": "U_ALICE",
            "text": "Let's discuss the API redesign",
        }
        base.update(overrides)
        return base

    def test_basic_channel_message(self):
        msg = self._make_msg()
        user_map = {"U_ALICE": "Alice"}
        item = message_to_source_item(msg, "design-team", "C_DESIGN", user_map)

        assert item.id == "slack_C_DESIGN_1712000000.000100"
        assert item.source_type == "slack_message"
        assert item.content_type == "message"
        assert item.title == "Message from Alice"
        assert item.content == "Let's discuss the API redesign"
        assert item.participants == ["Alice"]
        assert item.display_context == "Slack #design-team"
        assert "C_DESIGN" in item.source_url
        assert item.context["channel_id"] == "C_DESIGN"
        assert item.context["reply_count"] == 0

    def test_dm_message(self):
        msg = self._make_msg()
        user_map = {"U_ALICE": "Alice"}
        item = message_to_source_item(
            msg, "DM_123", "DM_123", user_map,
            is_dm=True, dm_partner="Bob"
        )

        assert item.display_context == "Slack DM with Bob"
        assert item.attribution_text() == "(per Slack DM with Bob)"

    def test_channel_attribution_text(self):
        msg = self._make_msg()
        user_map = {"U_ALICE": "Alice"}
        item = message_to_source_item(msg, "general", "C_GEN", user_map)
        assert item.attribution_text() == "(per Slack #general)"

    def test_reply_count_appended_to_content(self):
        msg = self._make_msg()
        user_map = {"U_ALICE": "Alice"}
        item = message_to_source_item(
            msg, "general", "C_GEN", user_map, reply_count=5
        )
        assert "(5 replies)" in item.content
        assert item.context["reply_count"] == 5

    def test_zero_reply_count_no_hint(self):
        msg = self._make_msg()
        user_map = {"U_ALICE": "Alice"}
        item = message_to_source_item(
            msg, "general", "C_GEN", user_map, reply_count=0
        )
        assert "(0 replies)" not in item.content
        assert "replies" not in item.content

    def test_none_reply_count_no_hint(self):
        msg = self._make_msg()
        user_map = {"U_ALICE": "Alice"}
        item = message_to_source_item(
            msg, "general", "C_GEN", user_map, reply_count=None
        )
        assert "replies" not in item.content

    def test_timestamp_conversion(self):
        msg = self._make_msg(ts="1712000000.000100")
        user_map = {"U_ALICE": "Alice"}
        item = message_to_source_item(msg, "general", "C_GEN", user_map)
        assert item.timestamp.tzinfo == timezone.utc
        assert item.timestamp.year == 2024

    def test_unknown_user_fallback(self):
        msg = self._make_msg(user="U_UNKNOWN")
        user_map = {}  # No mapping
        item = message_to_source_item(msg, "general", "C_GEN", user_map)
        assert item.title == "Message from U_UNKNOWN"

    def test_raw_data_preserved(self):
        msg = self._make_msg()
        user_map = {"U_ALICE": "Alice"}
        item = message_to_source_item(msg, "general", "C_GEN", user_map)
        assert item.raw_data == msg


class TestThreadToSourceItem:
    """Tests for thread_to_source_item."""

    def test_aggregates_participants(self):
        parent = {"ts": "1712000000.000100", "user": "U_ALICE", "text": "What do we think?"}
        replies = [
            {"ts": "1712000001.000200", "user": "U_BOB", "text": "I agree"},
            {"ts": "1712000002.000300", "user": "U_CAROL", "text": "Me too"},
            {"ts": "1712000003.000400", "user": "U_ALICE", "text": "Great"},
        ]
        user_map = {"U_ALICE": "Alice", "U_BOB": "Bob", "U_CAROL": "Carol"}

        item = thread_to_source_item(parent, replies, "design", "C_DES", user_map)

        assert item.source_type == "slack_thread"
        assert item.content_type == "thread"
        assert set(item.participants) == {"Alice", "Bob", "Carol"}
        assert item.context["reply_count"] == 3

    def test_formats_content_with_names(self):
        parent = {"ts": "1712000000.000100", "user": "U_ALICE", "text": "Discussion"}
        replies = [
            {"ts": "1712000001.000200", "user": "U_BOB", "text": "My take"},
        ]
        user_map = {"U_ALICE": "Alice", "U_BOB": "Bob"}

        item = thread_to_source_item(parent, replies, "eng", "C_ENG", user_map)

        assert "Alice: Discussion" in item.content
        assert "Bob: My take" in item.content

    def test_title_truncated(self):
        parent = {
            "ts": "1712000000.000100",
            "user": "U_ALICE",
            "text": "A" * 100,  # 100 chars
        }
        user_map = {"U_ALICE": "Alice"}

        item = thread_to_source_item(parent, [], "eng", "C_ENG", user_map)
        assert len(item.title) < 100
        assert item.title.endswith("...")

    def test_display_context(self):
        parent = {"ts": "1712000000.000100", "user": "U_ALICE", "text": "test"}
        user_map = {"U_ALICE": "Alice"}

        item = thread_to_source_item(parent, [], "design-team", "C_DT", user_map)
        assert item.display_context == "Slack #design-team"


class TestSlackStateManagement:
    """Tests for load_slack_state / save_slack_state round-trip."""

    def test_load_returns_empty_when_no_file(self, tmp_path):
        state = load_slack_state(tmp_path)
        assert state == {"channels": {}, "dms": {}}

    def test_save_and_load_round_trip(self, tmp_path):
        state = {
            "channels": {
                "C_123": {"last_ts": "1712000000.000100", "name": "general"}
            },
            "dms": {
                "D_456": {"last_ts": "1712000001.000200", "partner": "Alice"}
            },
        }
        save_slack_state(state, tmp_path)
        loaded = load_slack_state(tmp_path)
        assert loaded == state

    def test_save_creates_directory(self, tmp_path):
        nested = tmp_path / "nested" / "dir"
        state = {"channels": {}, "dms": {}}
        save_slack_state(state, nested)
        assert (nested / "slack_state.json").exists()

    def test_save_is_valid_json(self, tmp_path):
        state = {"channels": {"C1": {"last_ts": "123.456"}}, "dms": {}}
        save_slack_state(state, tmp_path)
        with open(tmp_path / "slack_state.json") as f:
            loaded = json.load(f)
        assert loaded["channels"]["C1"]["last_ts"] == "123.456"


class TestVolumeCap:
    """Test that volume capping works correctly in fetch_slack_items."""

    @patch("src.ingest.slack.build_slack_client")
    @patch("src.ingest.slack.save_slack_state")
    @patch("src.ingest.slack.load_slack_state")
    @patch("src.ingest.slack._resolve_channel_name")
    @patch("src.ingest.slack.fetch_channel_messages")
    @patch("src.ingest.slack.resolve_user_names")
    def test_volume_cap_keeps_most_recent(
        self,
        mock_resolve_users,
        mock_fetch_msgs,
        mock_resolve_name,
        mock_load_state,
        mock_save_state,
        mock_build_client,
    ):
        from src.ingest.slack import fetch_slack_items

        mock_build_client.return_value = MagicMock()
        mock_load_state.return_value = {"channels": {}, "dms": {}}
        mock_resolve_name.return_value = "test-channel"
        mock_resolve_users.return_value = {"U1": "TestUser"}

        # Create 150 messages
        messages = [
            {"ts": f"{1712000000 + i}.000100", "user": "U1", "text": f"Message {i}"}
            for i in range(150)
        ]
        mock_fetch_msgs.return_value = messages

        config = {
            "slack": {
                "enabled": True,
                "channels": ["C_TEST"],
                "dms": [],
                "max_messages_per_channel": 100,
                "bot_allowlist": [],
            }
        }

        items = fetch_slack_items(config)
        assert len(items) == 100
