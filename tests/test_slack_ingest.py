"""Tests for Slack ingestion and filtering."""

from __future__ import annotations

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
