# Phase 16: Reliability Quick Wins - Research

**Researched:** 2026-04-05
**Domain:** Slack API batch resolution, file system cache management, fuzzy string matching for dedup
**Confidence:** HIGH

## Summary

Phase 16 delivers three independent improvements: (1) replacing N individual `users.info` Slack API calls with a single paginated `users.list` call, (2) automatic cleanup of raw cache files older than a configurable TTL, and (3) an algorithmic cross-source dedup pre-filter that consolidates near-identical items before LLM synthesis. All three are well-understood patterns with no novel technical risk.

The current `resolve_user_names()` in `src/ingest/slack.py` (line 68-104) iterates over user IDs one-by-one calling `_slack_users_info_with_retry()` per user. Replacing this with `users.list` (which returns all workspace members in paginated batches of up to 1000) eliminates the N-call bottleneck entirely. The resolved map should be cached to disk with a 7-day TTL per CONTEXT.md decisions.

Cache cleanup targets `output/raw/` subdirectories (calendar JSON, email JSON) which grow unbounded. The `output/daily/` and `output/quality/` directories are processed output and must never be touched. The cleanup is a simple file-age check at pipeline startup.

The dedup pre-filter operates on `SourceItem` objects after all ingest completes but before synthesis. Items sharing the same calendar day and near-identical titles (above a conservative threshold) are merged. This supplements the existing `_dedup_hubspot_items()` pattern in `src/synthesis/synthesizer.py` and the LLM-level dedup instructions in the synthesis prompt.

**Primary recommendation:** Implement as three independent plans (one per improvement) that can be developed and tested in isolation, all in wave 1 since they have no mutual dependencies.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Cache Retention Policy: 14-day TTL for raw cache files, configurable in config.yaml, cleanup at pipeline start, processed output never touched, single summary log line, dedup logs have separate 30-day retention
- Dedup Matching Criteria: time window + title/subject similarity, same calendar day, conservative threshold, merge into consolidated item, deterministic pre-filter before LLM synthesis
- Slack Batch Resolution: single `users.list` call, fallback to individual calls on failure, disk-cached user map with 7-day TTL, TTL configurable in config.yaml
- Logging & Observability: dedup decisions logged with titles/sources/score, separate dedup log file, pipeline run summary with reliability stats, dedup logs retained 30 days

### Claude's Discretion
- Exact similarity algorithm for title matching (fuzzy string matching, token overlap, etc.)
- Merge strategy for combining duplicate items (how to blend content from multiple sources)
- Cache file discovery logic (which directories/patterns constitute "raw cache")
- Slack users.list pagination handling
- Dedup log file naming convention and format

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PERF-03 | Slack user batch resolution (users_list instead of N individual users_info calls) | Slack SDK `users_list()` supports cursor pagination, returns up to 1000 members per page. Current `resolve_user_names()` is the replacement target. |
| OPS-01 | Raw data cache retention policy (auto-delete after configurable TTL) | `output/raw/` contains dated subdirectories with JSON cache files. `output/daily/` and `output/quality/` are processed output -- excluded from cleanup. |
| DEDUP-01 | Algorithmic cross-source deduplication as conservative pre-filter | Existing `_dedup_hubspot_items()` in synthesizer.py provides a partial pattern. New dedup operates on all SourceItems across all sources, using title similarity + same-day check. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| slack_sdk | (existing) | Slack API client with `users_list` method | Already in project deps, provides `WebClient.users_list()` with cursor pagination |
| difflib | stdlib | SequenceMatcher for fuzzy title similarity | Built-in, no new dependency, proven string matching algorithm |
| pathlib | stdlib | File system operations for cache cleanup | Already used throughout project |
| pydantic | (existing) | Config model extensions for new TTL settings | Phase 13 established typed config pattern |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| json | stdlib | Disk cache serialization for user map | Persist resolved Slack user map |
| logging | stdlib | Dedup decision logging | Separate dedup log file |
| os/stat | stdlib | File age detection for cache cleanup | Check mtime vs TTL threshold |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| difflib.SequenceMatcher | thefuzz (fuzzywuzzy) | External dep for marginal improvement; difflib sufficient for conservative threshold |
| File mtime for age | Embedded timestamp in filename | Mtime is simpler and works with existing cache structure |

## Architecture Patterns

### Pattern 1: Batch-then-Cache for Slack Users
**What:** Call `users.list` once at Slack ingest start, build complete ID-to-name map, cache to disk, use in-memory for the run.
**When to use:** Any time the pipeline needs user resolution.
**Implementation:**
1. Check disk cache (`config/slack_user_cache.json`) -- if fresh (< 7 days), load and use
2. If stale or missing, call `users.list` with cursor pagination
3. Build `{user_id: display_name}` map from all pages
4. Write map + timestamp to disk cache
5. Fallback: if `users.list` fails, fall back to existing per-user `users.info` calls

### Pattern 2: Startup Cleanup Hook
**What:** Run cache cleanup as the first step in `run_pipeline()`, before any ingest begins.
**When to use:** Every pipeline run.
**Implementation:**
1. Walk `output/raw/` directory tree
2. For each file, check `stat().st_mtime` against TTL threshold
3. Delete files older than TTL, track count and bytes freed
4. Walk dedup log directory, apply separate 30-day TTL
5. Log single summary line
6. Never touch `output/daily/`, `output/quality/`, `output/validation/`

### Pattern 3: Pre-Synthesis Dedup Filter
**What:** After all ingest modules return SourceItems, run a deterministic dedup pass before feeding to LLM.
**When to use:** Between ingest completion and synthesis invocation in `run_pipeline()`.
**Implementation:**
1. Group all SourceItems by target date (same calendar day)
2. Within each day group, compare titles pairwise using `SequenceMatcher.ratio()`
3. If ratio >= threshold (recommend 0.85 for conservative matching), merge items
4. Merge strategy: keep item with most content, append source attributions from all duplicates
5. Log each merge decision with titles, sources, and similarity score
6. Return deduplicated list to synthesis

### Anti-Patterns to Avoid
- **Eager cache deletion:** Never delete files in `output/daily/` or `output/quality/` -- these are user-facing summaries
- **Aggressive dedup threshold:** A threshold too low (< 0.8) will merge distinct items. Start conservative (0.85+)
- **Blocking on users.list failure:** Must fall back gracefully to per-user calls if batch fails

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| String similarity | Custom edit distance | `difflib.SequenceMatcher` | Handles Unicode, well-tested, no deps |
| Slack pagination | Manual cursor loop | `users.list` with cursor pagination pattern from existing `fetch_channel_messages` | Consistent with codebase patterns |
| Config validation | Manual TTL range checks | Pydantic Field with `ge=1` constraints | Phase 13 established this pattern |

## Common Pitfalls

### Pitfall 1: Slack users.list Returns Deactivated Users
**What goes wrong:** `users.list` includes deactivated/deleted users, inflating the map unnecessarily.
**Why it happens:** Slack API returns all members including `deleted: true`.
**How to avoid:** Filter out `user["deleted"] == True` when building the map.
**Warning signs:** Map size is much larger than expected active user count.

### Pitfall 2: Cache Cleanup Races with Active Pipeline
**What goes wrong:** Cleanup deletes a cache file that another part of the pipeline is about to read.
**Why it happens:** If cleanup runs mid-pipeline or a file is from today's run.
**How to avoid:** Run cleanup at the very start of `run_pipeline()`, before any ingest begins. Only delete files older than TTL (14 days), which are never from the current run.
**Warning signs:** FileNotFoundError during ingest after cleanup.

### Pitfall 3: Dedup Merges Items from Different Days
**What goes wrong:** Items from adjacent days with similar titles get merged.
**Why it happens:** Target date boundary not enforced in comparison.
**How to avoid:** Group items by their target date (calendar day) before comparing. Only compare within the same day.
**Warning signs:** Merged items have timestamps from different dates.

### Pitfall 4: SequenceMatcher Performance on Large Sets
**What goes wrong:** O(n^2) pairwise comparison becomes slow with many items.
**Why it happens:** Comparing every item against every other item.
**How to avoid:** For typical daily volumes (< 100 items), O(n^2) is negligible. If needed, pre-group by source_type or first-word of title to reduce comparisons.
**Warning signs:** Pipeline noticeably slower on high-volume days.

### Pitfall 5: Slack User Cache File Corruption
**What goes wrong:** Cache file is partially written (crash/interrupt), subsequent load fails.
**Why it happens:** Non-atomic write to JSON file.
**How to avoid:** Use write-to-temp-then-rename pattern (already used by `save_slack_state()`).
**Warning signs:** JSONDecodeError when loading cache.

## Code Examples

### Slack users.list with Cursor Pagination
```python
def _fetch_all_users(client: WebClient) -> dict[str, str]:
    """Fetch all workspace users via users.list with pagination."""
    user_map: dict[str, str] = {}
    cursor = None
    while True:
        kwargs: dict = {"limit": 1000}
        if cursor:
            kwargs["cursor"] = cursor
        resp = client.users_list(**kwargs)
        for member in resp.get("members", []):
            if member.get("deleted"):
                continue
            if member.get("is_bot"):
                continue
            uid = member["id"]
            profile = member.get("profile", {})
            name = (
                profile.get("display_name")
                or member.get("real_name")
                or uid
            )
            if not name.strip():
                name = uid
            user_map[uid] = name
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return user_map
```

### Cache Cleanup Logic
```python
def cleanup_raw_cache(output_dir: Path, ttl_days: int = 14) -> tuple[int, int]:
    """Delete raw cache files older than TTL. Returns (files_deleted, bytes_freed)."""
    raw_dir = output_dir / "raw"
    if not raw_dir.exists():
        return 0, 0
    cutoff = time.time() - (ttl_days * 86400)
    deleted_count = 0
    bytes_freed = 0
    for path in raw_dir.rglob("*"):
        if path.is_file() and path.stat().st_mtime < cutoff:
            bytes_freed += path.stat().st_size
            path.unlink()
            deleted_count += 1
    return deleted_count, bytes_freed
```

### Title Similarity Check
```python
from difflib import SequenceMatcher

def titles_match(title_a: str, title_b: str, threshold: float = 0.85) -> float:
    """Return similarity ratio between two titles. >= threshold means match."""
    ratio = SequenceMatcher(None, title_a.lower().strip(), title_b.lower().strip()).ratio()
    return ratio
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Per-user `users.info` calls | Batch `users.list` + disk cache | This phase | Reduces API calls from N to 1-2 per run |
| Unbounded raw cache growth | TTL-based auto-cleanup | This phase | Prevents disk filling over weeks/months |
| LLM-only dedup | Algorithmic pre-filter + LLM dedup | This phase | Reduces token usage, catches obvious duplicates deterministically |

## Open Questions

1. **Optimal dedup threshold**
   - What we know: 0.85 is a conservative starting point for SequenceMatcher
   - What's unclear: Real-world false positive rate needs empirical tuning
   - Recommendation: Start at 0.85, log all decisions, adjust based on dedup log review

2. **Slack workspace size impact**
   - What we know: `users.list` returns up to 1000 per page with pagination
   - What's unclear: Very large workspaces (10K+ users) may need multiple pages
   - Recommendation: Pagination loop handles this. Cache 7-day TTL keeps map fresh without daily re-fetch.

## Sources

### Primary (HIGH confidence)
- Codebase analysis: `src/ingest/slack.py` lines 27-104 (current user resolution implementation)
- Codebase analysis: `src/synthesis/synthesizer.py` `_dedup_hubspot_items()` (existing dedup pattern)
- Codebase analysis: `src/pipeline.py` `run_pipeline()` (pipeline orchestration, ingest ordering)
- Codebase analysis: `src/config.py` (Pydantic config model pattern from Phase 13)
- Codebase analysis: `output/raw/` directory structure (cache file locations)
- Python stdlib docs: `difflib.SequenceMatcher` for string similarity

### Secondary (MEDIUM confidence)
- Slack SDK: `WebClient.users_list()` method with cursor pagination (consistent with existing `conversations_history` pattern in codebase)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already in project or stdlib
- Architecture: HIGH - patterns follow existing codebase conventions
- Pitfalls: HIGH - well-understood failure modes with clear mitigations

**Research date:** 2026-04-05
**Valid until:** 2026-05-05 (stable domain, no fast-moving dependencies)
