---
phase: 12-reliability-and-test-coverage
plan: 01
subsystem: infra
tags: [tenacity, retry, backoff, token-budget, truncation]

requires:
  - phase: 11-pipeline-hardening
    provides: stable pipeline with all ingest sources
provides:
  - retry_api_call decorator with exponential backoff (3 attempts, 1s/2s/4s)
  - All external API calls wrapped with retry
  - Token budget estimation with source truncation (Docs > HubSpot > Slack priority)
affects: [all-ingest-sources, synthesis, pipeline-reliability]

tech-stack:
  added: [tenacity]
  patterns: [shared retry decorator, token budget truncation]

key-files:
  created: [src/retry.py, tests/test_retry.py]
  modified: [src/synthesis/extractor.py, src/synthesis/synthesizer.py, src/synthesis/commitments.py, src/synthesis/weekly.py, src/synthesis/monthly.py, src/ingest/calendar.py, src/ingest/gmail.py, src/ingest/google_docs.py, src/ingest/drive.py, src/ingest/slack.py, src/ingest/hubspot.py, src/notifications/slack.py, pyproject.toml]

key-decisions:
  - "tenacity for retry — declarative, well-tested, already in ecosystem"
  - "3 attempts (1 initial + 2 retries) with 1s/2s/4s exponential backoff"
  - "Auth errors (401/403/404) fail immediately without retry"
  - "Token budget: 100K tokens (~400K chars) with 80% safety margin"
  - "Truncation priority: Docs first, HubSpot second, Slack third, transcripts never"

patterns-established:
  - "Retry pattern: @retry_api_call on lowest-level API call functions only"
  - "Token budget pattern: _estimate_and_truncate before Claude API calls"
---

# Plan 12-01: Retry/Backoff and Token Budget Estimation

**One-liner:** Shared tenacity retry decorator on all API calls (3 attempts, exponential backoff) plus token budget truncation prioritizing transcripts over docs/hubspot/slack

## What Was Built
- `src/retry.py` — retry_api_call decorator using tenacity with retryable error classification for Claude, Google, Slack, HubSpot, and httpx
- All ingest + synthesis modules wrapped with retry at lowest-level API call points
- Token budget estimation in synthesizer with source truncation (320K effective char budget)

## Key Files
- `src/retry.py` — Shared retry decorator with error classification helpers
- `src/synthesis/synthesizer.py` — _estimate_and_truncate for token budget
- `tests/test_retry.py` — Retry behavior tests

## Decisions Made
- tenacity for retry library — declarative config, well-tested
- 3 attempts with exponential backoff (1s, 2s, 4s waits)
- Auth errors fail immediately without retry
- 80% safety margin on token budget

## Deviations from Plan
None — followed plan as specified.

## Issues Encountered
None.

## Next Phase Readiness
- All API calls now retry-resilient
- Token budget prevents oversized synthesis prompts

---
*Phase: 12-reliability-and-test-coverage*
*Completed: 2026-04-08 (retroactive)*
