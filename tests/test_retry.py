"""Tests for the shared retry decorator module."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.retry import (
    _is_retryable,
    is_retryable_google_error,
    is_retryable_slack_error,
    retry_api_call,
)


class TestRetryDecorator:
    """Tests for the retry_api_call decorator behavior."""

    def test_succeeds_first_try(self):
        call_count = 0

        @retry_api_call
        def good_func():
            nonlocal call_count
            call_count += 1
            return "ok"

        assert good_func() == "ok"
        assert call_count == 1

    def test_retries_on_connection_error_then_succeeds(self):
        call_count = 0

        @retry_api_call
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("connection refused")
            return "recovered"

        result = flaky_func()
        assert result == "recovered"
        assert call_count == 2

    def test_retries_on_timeout_error(self):
        call_count = 0

        @retry_api_call
        def timeout_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError("timed out")
            return "ok"

        result = timeout_func()
        assert result == "ok"
        assert call_count == 3

    def test_does_not_retry_on_value_error(self):
        call_count = 0

        @retry_api_call
        def bad_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("bad argument")

        with pytest.raises(ValueError, match="bad argument"):
            bad_func()
        assert call_count == 1  # No retry

    def test_does_not_retry_on_key_error(self):
        call_count = 0

        @retry_api_call
        def bad_func():
            nonlocal call_count
            call_count += 1
            raise KeyError("missing key")

        with pytest.raises(KeyError):
            bad_func()
        assert call_count == 1

    def test_exhausts_retries_then_raises(self):
        call_count = 0

        @retry_api_call
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("persistent failure")

        with pytest.raises(ConnectionError, match="persistent failure"):
            always_fails()
        assert call_count == 3  # 1 initial + 2 retries


class TestIsRetryableGoogleError:
    """Tests for Google API error classification."""

    def _make_google_error(self, status: int):
        """Create a real HttpError with a given status code."""
        from googleapiclient.errors import HttpError

        resp = MagicMock()
        resp.status = status
        return HttpError(resp=resp, content=b"error")

    def test_429_is_retryable(self):
        exc = self._make_google_error(429)
        assert is_retryable_google_error(exc) is True

    def test_500_is_retryable(self):
        exc = self._make_google_error(500)
        assert is_retryable_google_error(exc) is True

    def test_503_is_retryable(self):
        exc = self._make_google_error(503)
        assert is_retryable_google_error(exc) is True

    def test_502_is_retryable(self):
        exc = self._make_google_error(502)
        assert is_retryable_google_error(exc) is True

    def test_401_is_not_retryable(self):
        exc = self._make_google_error(401)
        assert is_retryable_google_error(exc) is False

    def test_403_is_not_retryable(self):
        exc = self._make_google_error(403)
        assert is_retryable_google_error(exc) is False

    def test_404_is_not_retryable(self):
        exc = self._make_google_error(404)
        assert is_retryable_google_error(exc) is False

    def test_non_google_error_is_not_retryable(self):
        assert is_retryable_google_error(ValueError("not google")) is False


class TestIsRetryableSlackError:
    """Tests for Slack API error classification."""

    def _make_slack_error(self, error_str: str, status_code: int = 200):
        """Create a real SlackApiError with a given error string."""
        from slack_sdk.errors import SlackApiError
        from slack_sdk.web.slack_response import SlackResponse

        resp = MagicMock(spec=SlackResponse)
        resp.status_code = status_code
        resp.get = MagicMock(side_effect=lambda key, default="": error_str if key == "error" else default)
        resp.__getitem__ = MagicMock(side_effect=lambda key: error_str if key == "error" else None)
        resp.data = {"ok": False, "error": error_str}
        return SlackApiError(message=f"Error: {error_str}", response=resp)

    def test_rate_limited_is_retryable(self):
        exc = self._make_slack_error("ratelimited", status_code=429)
        assert is_retryable_slack_error(exc) is True

    def test_channel_not_found_is_not_retryable(self):
        exc = self._make_slack_error("channel_not_found", status_code=400)
        assert is_retryable_slack_error(exc) is False

    def test_non_slack_error_is_not_retryable(self):
        assert is_retryable_slack_error(ValueError("not slack")) is False


class TestIsRetryable:
    """Tests for the main retryable classification function."""

    def test_connection_error(self):
        assert _is_retryable(ConnectionError("fail")) is True

    def test_timeout_error(self):
        assert _is_retryable(TimeoutError("timeout")) is True

    def test_os_error(self):
        assert _is_retryable(OSError("network unreachable")) is True

    def test_value_error_not_retryable(self):
        assert _is_retryable(ValueError("bad")) is False

    def test_runtime_error_not_retryable(self):
        assert _is_retryable(RuntimeError("fail")) is False
