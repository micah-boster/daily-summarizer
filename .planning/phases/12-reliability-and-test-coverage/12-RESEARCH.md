# Phase 12: Reliability & Test Coverage - Research

**Researched:** 2026-04-04
**Domain:** API retry/backoff, token budget management, test infrastructure
**Confidence:** HIGH

## Summary

Phase 12 addresses three concerns: (1) transient API failure resilience via retry with exponential backoff, (2) input token budget enforcement for the synthesis Claude call, and (3) fixing broken tests + adding coverage for pipeline orchestration and response parsers.

The codebase currently has ZERO retry logic on any API call. Google API calls (calendar, gmail, drive, docs) use `.execute()`, Claude calls use `client.messages.create()`, HubSpot uses the SDK, and Slack uses the `slack_sdk`. All fail immediately on transient errors. Two test files fail to collect due to stale imports (`test_notifications.py` imports a removed `_split_text` function; `test_source_models.py` imports from a removed `src.models.commitments` module). The pipeline runner (`pipeline.py`) has no test coverage.

**Primary recommendation:** Add a shared retry decorator using `tenacity` library, apply it to all external API call sites, implement token budget estimation in the synthesizer, fix the two broken test files, and add pipeline orchestration tests.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Conservative approach: 2 retries with exponential backoff starting at 1s (1s, 2s, 4s)
- Retryable errors: timeouts, connection errors, HTTP 429 (rate limit), 500/502/503
- Immediate failure on: 401 (auth), 403 (forbidden), 404 (not found)
- Shared retry decorator/wrapper used by all API clients (Google, Claude, HubSpot) — DRY, consistent
- Log each retry attempt at warn level with error details
- ~100K token max budget for synthesis input
- Use rough character estimate (~4 chars per token) — no tokenizer dependency needed
- When over budget, truncate lowest-priority sources first: Docs edits -> HubSpot -> Slack -> Transcripts (meetings are highest signal)
- Note truncated sources in output header so user knows synthesis was based on incomplete data
- Continue with partial data when a source fails (better partial brief than nothing)
- Add header warning in daily summary listing unavailable sources
- If Claude synthesis call itself fails after retries, fall back to structured raw data summary
- Track failed sources and backfill their data on the next successful pipeline run
- Lightweight mocks using unittest.mock / pytest fixtures — no VCR or recorded fixtures
- Claude response parser tests focus on empty responses and missing sections
- Add GitHub Actions CI workflow to run tests automatically on push

### Claude's Discretion
- Test coverage depth and prioritization
- Exact retry decorator implementation (tenacity vs custom)
- Backfill state tracking mechanism
- Raw data fallback format when synthesis fails
- GitHub Actions workflow configuration details

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| tenacity | 9.x | Retry with exponential backoff | Industry standard Python retry library, far simpler than hand-rolling |
| pytest | 9.x | Test framework | Already in project |
| unittest.mock | stdlib | Mock external API calls | Already used throughout test suite |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-cov | latest | Coverage reporting | Optional — for measuring coverage % |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| tenacity | Custom decorator | tenacity handles edge cases (jitter, max delay, exception filtering) that custom code inevitably misses |
| tenacity | backoff library | backoff is simpler but less flexible; tenacity is more widely used |

**Installation:**
```bash
uv add tenacity
```

## Architecture Patterns

### Pattern 1: Shared Retry Decorator
**What:** A single `@retry_api_call` decorator in a new `src/retry.py` module that wraps all external API calls.
**When to use:** Every function that makes HTTP/API calls to external services.
**Example:**
```python
# src/retry.py
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log

logger = logging.getLogger(__name__)

def retry_api_call(func):
    """Shared retry decorator for all external API calls."""
    return retry(
        stop=stop_after_attempt(3),  # initial + 2 retries
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, ...)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )(func)
```

### Pattern 2: Token Budget Estimation
**What:** Before sending the synthesis prompt, estimate total input tokens via character count / 4, and truncate lowest-priority sources if over ~100K tokens.
**When to use:** In `synthesize_daily()` before the Claude API call.

### Pattern 3: Graceful Degradation with Source Tracking
**What:** Pipeline already catches per-source errors. Enhancement: track which sources failed and include a header warning in the output.
**When to use:** In pipeline runner when any source ingest function returns empty due to error.

### Anti-Patterns to Avoid
- **Retry on auth errors (401/403):** These will never succeed on retry and waste time.
- **Retry without backoff:** Hammering a rate-limited API makes things worse.
- **Retry at both caller and callee level:** Only retry at the lowest level (the actual API call), not in the pipeline runner too.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Retry with backoff | Custom while loop | tenacity | Edge cases: jitter, max attempts, exception filtering, logging hooks |

## Common Pitfalls

### Pitfall 1: Double-Retry
**What goes wrong:** Retries at both the API call level AND the pipeline orchestrator level, causing 9+ retries.
**How to avoid:** Only apply retry decorator at the lowest level (the API call function). Pipeline catch blocks should NOT retry.

### Pitfall 2: Retrying Non-Retryable Errors
**What goes wrong:** Retrying 401/403 wastes 6+ seconds and never succeeds.
**How to avoid:** Explicitly filter retryable exceptions. For Google API: `HttpError` with status 429/500/502/503. For Claude: `APIConnectionError`, `RateLimitError`, `InternalServerError`. For HubSpot: connection and rate limit errors.

### Pitfall 3: Token Count Accuracy
**What goes wrong:** The 4-chars-per-token estimate can be off by 20-30%.
**How to avoid:** Use a conservative budget (e.g., target 80K chars for 100K token budget) to leave safety margin.

### Pitfall 4: Stale Test Imports
**What goes wrong:** Tests import symbols that were renamed or removed in prior phases.
**How to avoid:** Run `uv run pytest --co` to catch import errors before running tests.

## Code Examples

### Current API Call Sites (No Retries)

**Google APIs** (`src/ingest/calendar.py`, `gmail.py`, `google_docs.py`, `drive.py`):
```python
response = request.execute()  # Google API execute
```

**Claude APIs** (`src/synthesis/extractor.py`, `synthesizer.py`, `commitments.py`, `monthly.py`, `weekly.py`):
```python
response = client.messages.create(...)  # Anthropic SDK
```

**Slack API** (`src/ingest/slack.py`):
```python
resp = client.conversations_history(**kwargs)  # slack_sdk
resp = client.users_info(user=uid)
```

**HubSpot API** (`src/ingest/hubspot.py`):
```python
# Uses hubspot SDK methods
```

### Broken Test Files

1. `tests/test_notifications.py:8` — imports `_split_text` which no longer exists in `src/notifications/slack.py`
2. `tests/test_source_models.py:5` — imports from `src.models.commitments` which was removed in Phase 11 (commitment model consolidated into `src/synthesis/commitments.py`)

### Test Status
- 318 tests collected, 2 collection errors
- Pipeline module (`src/pipeline.py`) has 0 test coverage
- Response parsers (`_parse_extraction_response`, `_parse_synthesis_response`) have some coverage in `test_extractor.py` and `test_synthesizer.py` but no edge case tests for empty/malformed responses

## Open Questions

1. **HubSpot SDK retry behavior**
   - What we know: The HubSpot Python SDK may have built-in retry behavior
   - What's unclear: Whether it handles all the error types we care about
   - Recommendation: Wrap HubSpot calls in our retry decorator regardless for consistency; built-in retries are additive

2. **Backfill mechanism**
   - What we know: CONTEXT.md mentions tracking failed sources for backfill
   - What's unclear: Exact persistence mechanism (file? config?)
   - Recommendation: Simple JSON state file in output/raw/ tracking last-failed sources; keep it simple

## Sources

### Primary (HIGH confidence)
- Codebase analysis: All API call sites identified via grep
- Test suite: `uv run pytest` output showing 318 tests, 2 errors
- Module inspection: `src/pipeline.py`, `src/synthesis/extractor.py`, `src/synthesis/synthesizer.py`

### Secondary (MEDIUM confidence)
- tenacity library: Well-established, 5K+ GitHub stars, actively maintained

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - tenacity is the standard Python retry library
- Architecture: HIGH - patterns follow established project conventions
- Pitfalls: HIGH - based on direct codebase analysis

**Research date:** 2026-04-04
**Valid until:** 2026-05-04 (stable domain, 30-day validity)
