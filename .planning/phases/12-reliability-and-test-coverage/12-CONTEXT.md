# Phase 12: Reliability & Test Coverage - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Pipeline gracefully handles transient API failures with retry/backoff, estimates and enforces token budgets for synthesis, and has test coverage for orchestration logic and edge cases. All pre-existing test failures are fixed and `uv run pytest` exits 0.

</domain>

<decisions>
## Implementation Decisions

### Retry & Backoff Strategy
- Conservative approach: 2 retries with exponential backoff starting at 1s (1s, 2s, 4s)
- Retryable errors: timeouts, connection errors, HTTP 429 (rate limit), 500/502/503
- Immediate failure on: 401 (auth), 403 (forbidden), 404 (not found)
- Shared retry decorator/wrapper used by all API clients (Google, Claude, HubSpot) — DRY, consistent
- Log each retry attempt at warn level with error details

### Token Budget & Truncation
- ~100K token max budget for synthesis input
- Use rough character estimate (~4 chars per token) — no tokenizer dependency needed
- When over budget, truncate lowest-priority sources first: Docs edits → HubSpot → Slack → Transcripts (meetings are highest signal)
- Note truncated sources in output header so user knows synthesis was based on incomplete data

### Failure Degradation
- Continue with partial data when a source fails (better partial brief than nothing)
- Add header warning in daily summary listing unavailable sources (e.g., "⚠️ HubSpot data unavailable")
- If Claude synthesis call itself fails after retries, fall back to structured raw data summary
- Track failed sources and backfill their data on the next successful pipeline run

### Test Scope & Approach
- Lightweight mocks using unittest.mock / pytest fixtures — no VCR or recorded fixtures
- Claude response parser tests focus on empty responses and missing sections (most likely real failures)
- Add GitHub Actions CI workflow to run tests automatically on push

### Claude's Discretion
- Test coverage depth and prioritization (fix broken tests + orchestration at minimum, expand as risk warrants)
- Exact retry decorator implementation (tenacity vs custom)
- Backfill state tracking mechanism
- Raw data fallback format when synthesis fails
- GitHub Actions workflow configuration details

</decisions>

<specifics>
## Specific Ideas

- Retry logging should use existing pipeline logging patterns
- Token budget note in output should be visible but not intrusive (header-level, not per-section)
- Backfill ensures data completeness even when APIs have transient outages

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 12-reliability-and-test-coverage*
*Context gathered: 2026-04-04*
