"""Shared retry decorator for all external API calls.

Provides a single retry_api_call decorator using tenacity that wraps
all external API calls with exponential backoff. Retries on transient
errors (timeouts, rate limits, server errors) and fails fast on
auth errors (401/403/404).
"""
from __future__ import annotations

import logging

from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

# Optional dependency guards — module works even if these aren't installed
try:
    from googleapiclient.errors import HttpError as GoogleHttpError
except ImportError:
    GoogleHttpError = None  # type: ignore[misc, assignment]

try:
    from slack_sdk.errors import SlackApiError
except ImportError:
    SlackApiError = None  # type: ignore[misc, assignment]

try:
    import anthropic as _anthropic

    AnthropicRetryableErrors = (
        _anthropic.APIConnectionError,
        _anthropic.RateLimitError,
        _anthropic.InternalServerError,
    )
except ImportError:
    AnthropicRetryableErrors = ()  # type: ignore[assignment]

try:
    import httpx as _httpx

    HttpxRetryableErrors = (
        _httpx.ConnectError,
        _httpx.TimeoutException,
    )
except ImportError:
    HttpxRetryableErrors = ()  # type: ignore[assignment]

# Standard library transient errors
STDLIB_RETRYABLE = (ConnectionError, TimeoutError, OSError)


def is_retryable_google_error(exc: BaseException) -> bool:
    """Check if a Google API HttpError is retryable (429/500/502/503)."""
    if GoogleHttpError is None:
        return False
    if not isinstance(exc, GoogleHttpError):
        return False
    status = exc.resp.status if hasattr(exc, "resp") and exc.resp else 0
    return status in (429, 500, 502, 503)


def is_retryable_slack_error(exc: BaseException) -> bool:
    """Check if a Slack API error is retryable (rate limited)."""
    if SlackApiError is None:
        return False
    if not isinstance(exc, SlackApiError):
        return False
    resp = exc.response if hasattr(exc, "response") else None
    if resp is None:
        return False
    status_code = getattr(resp, "status_code", 0)
    error_str = resp.get("error", "") if hasattr(resp, "get") else ""
    return status_code == 429 or error_str == "ratelimited"


def _is_retryable(exc: BaseException) -> bool:
    """Determine if an exception is retryable."""
    # Standard library transient errors
    if isinstance(exc, STDLIB_RETRYABLE):
        return True

    # httpx transport errors
    if HttpxRetryableErrors and isinstance(exc, HttpxRetryableErrors):
        return True

    # httpx HTTP status errors (429, 5xx)
    if _httpx is not None and isinstance(exc, _httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 429 or status >= 500:
            return True

    # Anthropic API errors
    if AnthropicRetryableErrors and isinstance(exc, AnthropicRetryableErrors):
        return True

    # Google API errors (only specific status codes)
    if is_retryable_google_error(exc):
        return True

    # Slack API errors (only rate limited)
    if is_retryable_slack_error(exc):
        return True

    return False


retry_api_call = retry(
    stop=stop_after_attempt(3),  # initial attempt + 2 retries
    wait=wait_exponential(multiplier=1, min=1, max=4),  # 1s, 2s, 4s
    retry=retry_if_exception(_is_retryable),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
"""Decorator: retry transient API errors with exponential backoff.

Usage::

    @retry_api_call
    def call_external_api():
        ...

Retries on: ConnectionError, TimeoutError, httpx transport errors,
Anthropic rate-limit/connection/server errors, Google 429/5xx,
Slack rate-limit errors.

Fails immediately on: ValueError, KeyError, auth errors (401/403/404),
and all other non-transient exceptions.
"""
