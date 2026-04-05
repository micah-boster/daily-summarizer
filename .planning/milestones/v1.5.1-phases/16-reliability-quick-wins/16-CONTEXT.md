# Phase 16: Reliability Quick Wins - Context

**Gathered:** 2026-04-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Three independent improvements that reduce API call volume, manage disk growth, and add a deterministic dedup layer before LLM synthesis. Specifically: Slack batch user resolution, cache retention policy with automatic cleanup, and algorithmic cross-source dedup pre-filter.

</domain>

<decisions>
## Implementation Decisions

### Cache Retention Policy
- TTL of 14 days for raw cache files (Slack JSON, calendar data, email cache, Notion cache)
- TTL is configurable in config.yaml (fits the typed config pattern from Phase 13)
- Cleanup runs at the start of each pipeline run, before ingestion begins
- Processed output (daily summaries, quality files) is never touched by cleanup
- Cleanup logs a single summary line: count of files deleted + space freed
- Dedup log files have a separate 30-day retention (longer than raw cache, since they're small and useful for threshold tuning)

### Dedup Matching Criteria
- Matching signal: time window + title/subject similarity
- Time window: same calendar day (items on the same target date with similar titles are candidates)
- Conservative threshold — only merge near-identical items to minimize false positives
- When duplicates are found: merge into one consolidated item combining info from all duplicate sources
- This is a deterministic pre-filter before LLM synthesis, not a replacement for LLM-level dedup

### Slack Batch Resolution
- Replace N individual `users.info` calls with a single batch `users.list` call
- Fallback: if batch call fails (rate limit, network error), fall back to individual calls so the run still completes
- Resolved user map (ID → display name) cached to disk with 7-day TTL
- User cache TTL is configurable in config.yaml, consistent with cache retention TTL pattern

### Logging & Observability
- Dedup decisions logged with merged item titles, source labels, and similarity score (e.g., "Merged 'Q2 Planning' (Slack) + 'Q2 Planning' (Calendar) — score: 0.92")
- Dedup decisions written to a separate log file (not just the main pipeline log) for easy threshold tuning review
- Pipeline run summary includes a "reliability stats" section showing: API calls saved, cache space freed, and items deduped
- Dedup log files retained for 30 days (separate from the 14-day raw cache TTL)

### Claude's Discretion
- Exact similarity algorithm for title matching (fuzzy string matching, token overlap, etc.)
- Merge strategy for combining duplicate items (how to blend content from multiple sources)
- Cache file discovery logic (which directories/patterns constitute "raw cache")
- Slack users.list pagination handling
- Dedup log file naming convention and format

</decisions>

<specifics>
## Specific Ideas

- All three improvements are independent and can be implemented/tested in isolation
- Config pattern should mirror Phase 13's typed config approach (Pydantic models for new settings)
- Dedup log should be human-readable enough to review false positives and tune thresholds

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 16-reliability-quick-wins*
*Context gathered: 2026-04-05*
