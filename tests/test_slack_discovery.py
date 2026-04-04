"""Tests for Slack channel and DM discovery."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from src.ingest.slack_discovery import (
    MIN_ACTIVITY_THRESHOLD,
    check_new_channels,
    compute_channel_stats,
    discover_channels,
    run_discovery,
)


def _make_mock_client():
    """Create a mock Slack WebClient."""
    return MagicMock()


class TestComputeChannelStats:
    """Tests for compute_channel_stats."""

    def test_extracts_keywords_from_messages(self):
        client = _make_mock_client()
        client.conversations_history.return_value = {
            "messages": [
                {"text": "working on the redesign sprint", "user": "U1"},
                {"text": "redesign sprint planning figma", "user": "U2"},
                {"text": "figma mockups for redesign", "user": "U1"},
            ],
            "response_metadata": {"next_cursor": ""},
        }

        stats = compute_channel_stats(client, "C_TEST", lookback_days=7)

        assert stats["message_count"] == 3
        assert stats["participant_count"] == 2
        # "redesign" should be the top keyword (appears 3 times)
        assert "redesign" in stats["topic_keywords"]

    def test_low_activity_channel(self):
        client = _make_mock_client()
        client.conversations_history.return_value = {
            "messages": [
                {"text": "hello", "user": "U1"},
            ],
            "response_metadata": {"next_cursor": ""},
        }

        stats = compute_channel_stats(client, "C_QUIET")
        assert stats["message_count"] == 1
        assert stats["participant_count"] == 1

    def test_empty_channel(self):
        client = _make_mock_client()
        client.conversations_history.return_value = {
            "messages": [],
            "response_metadata": {"next_cursor": ""},
        }

        stats = compute_channel_stats(client, "C_EMPTY")
        assert stats["message_count"] == 0
        assert stats["participant_count"] == 0
        assert stats["topic_keywords"] == []

    def test_stopwords_excluded_from_keywords(self):
        client = _make_mock_client()
        client.conversations_history.return_value = {
            "messages": [
                {"text": "the project is for testing and validation", "user": "U1"},
                {"text": "project testing validation", "user": "U2"},
            ],
            "response_metadata": {"next_cursor": ""},
        }

        stats = compute_channel_stats(client, "C_TEST")
        # Stopwords like "the", "is", "for", "and" should not appear
        for kw in stats["topic_keywords"]:
            assert kw not in {"the", "is", "for", "and"}


class TestDiscoverChannels:
    """Tests for discover_channels with mocked client and input."""

    def test_already_configured_shown_separately(self, monkeypatch):
        client = _make_mock_client()
        client.users_conversations.return_value = {
            "channels": [
                {"id": "C_EXISTING", "name": "existing-channel", "is_private": False, "num_members": 10},
                {"id": "C_NEW", "name": "new-channel", "is_private": False, "num_members": 5},
            ],
            "response_metadata": {"next_cursor": ""},
        }
        # Stats for existing channel
        client.conversations_history.return_value = {
            "messages": [{"text": f"msg {i}", "user": "U1"} for i in range(20)],
            "response_metadata": {"next_cursor": ""},
        }

        config = {"slack": {"channels": ["C_EXISTING"]}}
        state = {"channels": {}}

        # User says 'n' to new channel
        inputs = iter(["n"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        result = discover_channels(client, state, config)
        assert "C_EXISTING" in result

    def test_user_confirms_new_channel(self, monkeypatch):
        client = _make_mock_client()
        client.users_conversations.return_value = {
            "channels": [
                {"id": "C_NEW", "name": "new-active", "is_private": False, "num_members": 8},
            ],
            "response_metadata": {"next_cursor": ""},
        }
        client.conversations_history.return_value = {
            "messages": [{"text": f"msg {i}", "user": "U1"} for i in range(20)],
            "response_metadata": {"next_cursor": ""},
        }

        config = {"slack": {"channels": []}}
        state = {"channels": {}}

        inputs = iter(["y"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        result = discover_channels(client, state, config)
        assert "C_NEW" in result

    def test_user_quits_discovery(self, monkeypatch):
        client = _make_mock_client()
        client.users_conversations.return_value = {
            "channels": [
                {"id": "C1", "name": "ch1", "is_private": False, "num_members": 5},
                {"id": "C2", "name": "ch2", "is_private": False, "num_members": 5},
            ],
            "response_metadata": {"next_cursor": ""},
        }
        client.conversations_history.return_value = {
            "messages": [{"text": f"msg {i}", "user": "U1"} for i in range(20)],
            "response_metadata": {"next_cursor": ""},
        }

        config = {"slack": {"channels": []}}
        state = {"channels": {}}

        inputs = iter(["q"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        result = discover_channels(client, state, config)
        # Quit before confirming any
        assert result == []

    def test_low_activity_channels_excluded(self, monkeypatch):
        client = _make_mock_client()
        client.users_conversations.return_value = {
            "channels": [
                {"id": "C_QUIET", "name": "quiet-channel", "is_private": False, "num_members": 3},
            ],
            "response_metadata": {"next_cursor": ""},
        }
        # Only 2 messages - below threshold
        client.conversations_history.return_value = {
            "messages": [
                {"text": "hi", "user": "U1"},
                {"text": "hello", "user": "U2"},
            ],
            "response_metadata": {"next_cursor": ""},
        }

        config = {"slack": {"channels": []}}
        state = {"channels": {}}

        # Should not be prompted at all
        monkeypatch.setattr("builtins.input", lambda _: pytest.fail("Should not prompt for low-activity channel"))

        result = discover_channels(client, state, config)
        assert result == []


class TestCheckNewChannels:
    """Tests for non-interactive check_new_channels."""

    def test_returns_active_untracked_channels(self):
        client = _make_mock_client()
        client.users_conversations.return_value = {
            "channels": [
                {"id": "C_TRACKED", "name": "tracked", "is_private": False, "num_members": 10},
                {"id": "C_NEW_ACTIVE", "name": "new-active", "is_private": False, "num_members": 8},
                {"id": "C_NEW_QUIET", "name": "new-quiet", "is_private": False, "num_members": 3},
            ],
            "response_metadata": {"next_cursor": ""},
        }

        def mock_history(**kwargs):
            channel = kwargs.get("channel", "")
            if channel == "C_NEW_ACTIVE":
                return {
                    "messages": [{"text": f"m{i}", "user": "U1"} for i in range(20)],
                    "response_metadata": {"next_cursor": ""},
                }
            elif channel == "C_NEW_QUIET":
                return {
                    "messages": [{"text": "hi", "user": "U1"}],
                    "response_metadata": {"next_cursor": ""},
                }
            return {"messages": [], "response_metadata": {"next_cursor": ""}}

        client.conversations_history.side_effect = mock_history

        config = {"slack": {"channels": ["C_TRACKED"]}}
        state = {"channels": {}}

        result = check_new_channels(client, state, config)
        assert "new-active" in result
        assert "new-quiet" not in result
        assert "tracked" not in result

    def test_returns_empty_when_all_configured(self):
        client = _make_mock_client()
        client.users_conversations.return_value = {
            "channels": [
                {"id": "C1", "name": "ch1", "is_private": False, "num_members": 10},
            ],
            "response_metadata": {"next_cursor": ""},
        }

        config = {"slack": {"channels": ["C1"]}}
        state = {"channels": {}}

        result = check_new_channels(client, state, config)
        assert result == []


class TestRunDiscovery:
    """End-to-end test for run_discovery with mocked client and tmp_path."""

    @patch("src.ingest.slack_discovery.build_slack_client")
    def test_end_to_end(self, mock_build, tmp_path, monkeypatch):
        client = _make_mock_client()
        mock_build.return_value = client

        # Setup mock responses
        client.users_conversations.return_value = {
            "channels": [
                {"id": "C_FOUND", "name": "found-channel", "is_private": False, "num_members": 5},
            ],
            "response_metadata": {"next_cursor": ""},
        }
        client.conversations_history.return_value = {
            "messages": [{"text": f"msg {i}", "user": "U1"} for i in range(20)],
            "response_metadata": {"next_cursor": ""},
        }

        # Create config file
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_yaml = config_dir / "config.yaml"
        config_yaml.write_text(yaml.dump({"slack": {"enabled": True, "channels": [], "dms": []}}))

        # Patch paths
        monkeypatch.setattr("src.ingest.slack_discovery.load_slack_state", lambda _: {"channels": {}, "dms": {}})
        saved_state = {}

        def mock_save(state, path):
            saved_state.update(state)

        monkeypatch.setattr("src.ingest.slack_discovery.save_slack_state", mock_save)

        # User confirms the channel, then no DMs to discover
        inputs = iter(["y"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs, "n"))

        # Patch config path
        monkeypatch.chdir(tmp_path)

        config = {"slack": {"enabled": True, "channels": [], "dms": []}}
        run_discovery(config)

        assert "C_FOUND" in saved_state.get("channels", {})
