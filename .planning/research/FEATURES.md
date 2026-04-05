# Feature Research: v1.5.1 -- Notion + Performance + Reliability

**Domain:** Work intelligence pipeline -- Notion ingestion, performance, reliability, structured outputs
**Researched:** 2026-04-04
**Confidence:** HIGH (existing codebase well-understood, API docs verified)

## Feature Landscape

### Table Stakes (Users Expect These)

Features that complete the v1.5.1 milestone promise. Without these, the milestone is incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Notion page/database ingestion | Notion is the last major daily-use tool not yet ingested; PROJECT.md lists it as primary user tool | MEDIUM | Notion API has no diff endpoint -- must query by `last_edited_time` filter and compare content. SDK: `notion-sdk-py` (ramnes) supports sync+async. |
| Typed config model (Pydantic validation) | Current `load_config()` returns raw dict, zero validation. Typos in config silently produce wrong behavior (e.g., `enbled: true`). Every ingest module does its own `.get()` with fallback defaults scattered across the codebase. | LOW-MEDIUM | Pydantic already a dependency (v2.12+). Define nested BaseModel classes mirroring config.yaml structure. Validate on startup, fail fast with field-specific errors. |
| Claude API structured output migration | PROJECT.md explicitly states "migration overdue." Current extractors parse markdown with brittle regex (`_parse_section_items`, `_parse_legacy_blocks`, `_parse_synthesis_response`). Multiple parsing formats maintained for backward compat. Any Claude response format drift breaks extraction. | MEDIUM | Use `output_config.format` with `json_schema` type (GA on Sonnet 4.5+). Anthropic SDK has `client.messages.parse()` with native Pydantic model support. Eliminates ~200 lines of regex parsing in extractor.py and synthesizer.py. |
| Raw data cache retention policy | Pipeline caches raw API responses to disk (calendar JSON, transcript emails). No cleanup mechanism exists. Over time, output/ directory grows unbounded. | LOW | Scan output dirs older than TTL, delete raw_* files. Config: `pipeline.cache_retention_days: 30`. Run at pipeline start or as separate CLI command. |

### Differentiators (Competitive Advantage)

Features that make v1.5.1 meaningfully better than v1.5, beyond just adding another source.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Parallel ingest modules (asyncio) | Current pipeline runs 4-5 ingest sources sequentially. With 5+ API sources, wall-clock time scales linearly. Parallelizing independent sources cuts total ingest time to the slowest source. | MEDIUM | Pipeline.py is synchronous. Need `asyncio.gather()` for independent sources. Calendar+transcripts have internal dependencies so stay sequential internally but run parallel with other sources. Use `asyncio.Semaphore` to cap concurrent API calls. Anthropic SDK supports async via `AsyncAnthropic`. |
| Parallel per-meeting transcript extraction | `extract_all_meetings()` iterates meetings sequentially, one Claude API call per meeting. With 5-8 meetings/day at ~3-5s each = 15-40s. Parallel calls reduce to ~5s. | LOW-MEDIUM | `asyncio.gather()` over async Claude calls. Anthropic rate limits are per-minute, so 5-8 concurrent calls are well within limits. |
| Slack user batch resolution | Current `resolve_user_names()` makes one `users.info` API call per unique user ID. With 10-20 unique users, that is 10-20 serial API calls. `users.list` returns all workspace users in one call. | LOW | Replace N `users.info` calls with one paginated `users.list` call. Build full user_id -> display_name map upfront. For typical company scale (<500 users), single call is fine. |
| Algorithmic cross-source deduplication | Current dedup is LLM-based only (prompt instructs Claude to merge duplicates). Non-deterministic and costs tokens. Pre-LLM algorithmic pass catches obvious duplicates cheaply and deterministically. | MEDIUM | TF-IDF + cosine similarity on SourceItem content/title. Scikit-learn `TfidfVectorizer`. Threshold ~0.85 for conservative matching. Supplements LLM dedup, does not replace it. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Real-time Notion webhook ingestion | "Get Notion changes as they happen" | Notion webhooks (automations API) are limited to triggers within Notion, not external consumers. No reliable webhook-to-external-URL path. Adds always-on server requirement for a batch pipeline. | Poll by `last_edited_time` filter during daily pipeline run. Batch is sufficient per PROJECT.md constraints. |
| Full Notion workspace crawl | "Ingest everything from Notion" | Workspaces contain thousands of pages. Most are stale reference material. Crawling everything wastes API quota and drowns signal in noise. | Configure specific database IDs and/or page IDs. Filter by `last_edited_time` for pages changed on target date. Mirror the Google Docs pattern: curated scope + recency filter. |
| Embedding-based dedup (sentence transformers) | "Use semantic embeddings for better duplicate detection" | Adds heavy dependency (sentence-transformers, torch) for marginal improvement over TF-IDF at this scale (~50-100 items/day). Increases install size by hundreds of MB. | TF-IDF + cosine similarity handles 70-85% of lexical duplicates. LLM-based dedup (already in place) catches semantic remainder. Two-layer approach is sufficient. |
| Full async rewrite of entire pipeline | "Make everything async for maximum performance" | Calendar/transcript pipeline has inherent sequential dependencies (fetch events, then fetch transcripts, then match, then extract). Making everything async adds complexity without meaningful speedup for serial-dependency paths. | Targeted async: parallelize independent sources and independent Claude calls. Keep sequential logic sequential. This is the 80/20 approach. |
| Config hot-reload | "Auto-detect config changes without restart" | Adds file-watching complexity and partial-state concerns for a CLI tool that runs once per day. | Validate config on startup. Fail fast with clear error. Re-run pipeline after fixing. |
| Notion content diffing via stored snapshots | "Show me what changed in each Notion page" | Requires storing full page content snapshots, running diffs, managing storage growth. Over-engineered for daily intelligence use case. | Fetch current content of pages modified today. Title + content excerpt is sufficient for daily synthesis. |

## Feature Dependencies

```
[Typed Config Model]
    +--enables--> [Notion Ingestion] (new config section validated at startup)
    +--enables--> [Cache Retention Policy] (retention_days from typed config)
    +--enables--> [All Ingest Modules] (typed access replaces .get() fallbacks)

[Parallel Ingest (asyncio)]
    +--requires--> [Notion Ingestion exists] (to parallelize it with other sources)
    +--enables--> [Parallel Per-Meeting Extraction] (same async infrastructure)

[Structured Output Migration]
    +--independent-- (no dependency on other v1.5.1 features)
    +--enables--> [Notion extraction quality] (Notion items parsed via structured outputs)

[Algorithmic Dedup]
    +--requires--> [Notion Ingestion] (so Notion items are included in dedup)
    +--enhances--> [Existing LLM Dedup] (pre-filter before synthesis prompt)

[Slack Batch User Resolution]
    +--independent-- (pure optimization, can be done anytime)

[Cache Retention]
    +--independent-- (pure maintenance, can be done anytime)
```

### Dependency Notes

- **Typed Config Model first:** Every other feature touches config. Notion needs a new config section; parallelization may need concurrency settings; cache retention needs TTL. Building typed config first means new features use it from day one rather than the raw dict pattern.
- **Notion before parallelization:** Build and test the Notion ingestor in the simpler synchronous world first, then wrap all ingestors in async. Parallelizing without Notion means retouching the code when Notion is added.
- **Structured outputs are independent:** The extraction/synthesis migration touches different code paths (Claude API call sites) than ingestion. No ordering constraint with other features. Good candidate for early work.
- **Algorithmic dedup after Notion:** Dedup logic should account for all source types. Building it before Notion exists means retrofitting later.

## MVP Definition

### Phase 1: Foundation (Config + Structured Outputs)

- [ ] **Typed config model with Pydantic validation** -- catches config errors on startup, provides typed access throughout pipeline, establishes pattern for new config sections
- [ ] **Structured output migration for extraction + synthesis** -- eliminates brittle regex parsing in extractor.py (~130 lines) and synthesizer.py (~80 lines), highest reliability improvement per effort

### Phase 2: Notion + Quick Wins

- [ ] **Notion page/database ingestion** -- completes the ingest surface with the last major daily-use tool
- [ ] **Slack user batch resolution** -- quick API optimization, reduces Slack API calls by 10-20x
- [ ] **Cache retention policy** -- maintenance hygiene, prevents unbounded disk growth

### Phase 3: Performance + Intelligence

- [ ] **Parallel ingest via asyncio** -- requires async refactor of pipeline runner, wraps all ingest modules
- [ ] **Parallel per-meeting extraction** -- piggybacks on async infrastructure from ingest parallelization
- [ ] **Algorithmic cross-source dedup** -- TF-IDF pre-filter supplements existing LLM dedup

### Ordering Rationale

1. **Config model first** because every subsequent feature adds config. Retroactive validation is harder.
2. **Structured outputs early** because they are independent, high-ROI, and reduce the surface area for parsing bugs before Notion adds a new source type.
3. **Notion before async** because building and debugging a new ingestor is easier in synchronous code. Test it works, then parallelize.
4. **Async after all ingestors exist** because the async refactor wraps all ingest modules. Doing it earlier means touching the same code twice when Notion is added.
5. **Algorithmic dedup last** because it operates on the output of all ingestors, so all should be stable first. Also the feature with most uncertainty (threshold tuning needed).

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Typed config model (Pydantic) | MEDIUM | LOW | P1 |
| Structured output migration | HIGH | MEDIUM | P1 |
| Notion ingestion | HIGH | MEDIUM | P1 |
| Slack user batch resolution | LOW | LOW | P2 |
| Cache retention policy | LOW | LOW | P2 |
| Parallel ingest (asyncio) | MEDIUM | MEDIUM | P2 |
| Parallel extraction | MEDIUM | LOW | P2 |
| Algorithmic dedup | MEDIUM | MEDIUM | P3 |

**Priority key:**
- P1: Must have -- core milestone deliverables
- P2: Should have -- meaningful improvements, add when core is stable
- P3: Nice to have -- valuable but lowest risk of deferral

## Detailed Feature Specifications

### Notion Ingestion

**What it does:** Query configured Notion databases and pages for content modified on the target date. Convert to SourceItem objects matching the existing pattern (Google Docs, Slack, HubSpot).

**Expected behavior:**
- Config section: `notion.enabled`, `notion.databases` (list of database IDs), `notion.pages` (list of page IDs), `notion.content_max_chars`, `notion.max_pages_per_day`
- Filter: `last_edited_time` timestamp filter on database queries (after start_of_day, before end_of_day)
- For databases: query with filter, iterate results, extract page content via blocks API
- For standalone pages: retrieve page, check `last_edited_time`, extract content if modified
- Content extraction: recursively fetch page blocks, convert to plain text (paragraph, heading, bulleted_list_item, numbered_list_item, toggle, callout, quote, code, table blocks)
- New SourceTypes: `NOTION_PAGE_EDIT`, `NOTION_DATABASE_ITEM`
- Attribution: `(per Notion "Page Title")`

**Key API details (verified):**
- Database query filter: `{"filter": {"timestamp": "last_edited_time", "last_edited_time": {"on_or_after": "2026-04-04T00:00:00-04:00"}}}`
- Pagination: max 100 items per request, use `start_cursor` for next page
- Block children: `GET /v1/blocks/{block_id}/children` -- paginated, recursive for nested blocks
- Rich text: each block has `rich_text` array, concatenate `plain_text` fields
- SDK: `notion-sdk-py` (ramnes/notion-sdk-py) -- sync and async clients available
- Auth: integration token via `NOTION_API_KEY` env var

**Follows existing pattern from:** `src/ingest/google_docs.py` -- curated list of sources, date-based filtering, content extraction with max_chars truncation, conversion to SourceItem

**Confidence:** HIGH -- API endpoints verified via official Notion docs.

### Structured Output Migration

**What it does:** Replace markdown-response-then-regex-parse pattern with Claude structured outputs (json_schema). Define Pydantic response models, use `client.messages.parse()` or `output_config.format`.

**Where it applies (3 call sites):**
1. **`extractor.py` -- `extract_meeting()`**: Per-meeting extraction. Currently returns markdown parsed by `_parse_extraction_response()` with `_parse_section_items()` and `_parse_legacy_blocks()` (~130 lines of regex/string parsing). Handles two response formats plus a legacy fallback.
2. **`synthesizer.py` -- `synthesize_daily()`**: Daily synthesis. Currently returns markdown parsed by `_parse_synthesis_response()` (~80 lines of section-splitting and bullet/table-row parsing).
3. **`commitments.py` -- `extract_commitments()`**: Commitment extraction from synthesis text.

**Migration pattern per call site:**
1. Define Pydantic response model (e.g., `MeetingExtractionResponse` with `decisions: list[ExtractionItem]`, etc.)
2. Use `client.messages.parse(output_format=MeetingExtractionResponse, ...)` -- SDK transforms Pydantic schema, validates response, returns `response.parsed_output` as typed model
3. Remove all `_parse_*` functions and regex logic

**Key technical details (verified from Anthropic docs):**
- GA on Claude Sonnet 4.5, Opus 4.5, Sonnet 4.6, Opus 4.6, Haiku 4.5
- API parameter: `output_config={"format": {"type": "json_schema", "schema": {...}}}`
- SDK helper: `client.messages.parse()` auto-transforms Pydantic models
- Response in `response.content[0].text` as valid JSON (or `response.parsed_output` with `.parse()`)
- Pydantic field constraints (e.g., `minimum`) are converted to descriptions; SDK validates post-response
- Already available in `anthropic>=0.45.0` (project dependency)

**Confidence:** HIGH -- verified against official Anthropic structured outputs docs (GA, not beta).

### Asyncio Pipeline Parallelization

**What it does:** Run independent ingest modules concurrently using `asyncio.gather()`.

**Current state:** `run_pipeline()` in pipeline.py calls `_ingest_slack()`, `_ingest_hubspot()`, `_ingest_docs()`, `_ingest_calendar()` sequentially at lines 207-210. Each makes network calls. Total ingest time = sum of all source times.

**Target state:**
```python
async def run_pipeline_async(ctx):
    # Independent sources run in parallel
    results = await asyncio.gather(
        _ingest_slack_async(ctx),
        _ingest_hubspot_async(ctx),
        _ingest_docs_async(ctx),
        _ingest_notion_async(ctx),
        _ingest_calendar_async(ctx),
        return_exceptions=True,
    )
    # Unpack results, handle any exceptions
```

**Library async support:**
- `httpx` (dependency): async via `httpx.AsyncClient` -- native
- `slack-sdk`: `slack_sdk.web.async_client.AsyncWebClient` available
- `google-api-python-client`: sync only. Wrap in `asyncio.to_thread()` -- pragmatic, avoids risky library swap
- `anthropic`: `AsyncAnthropic` for parallel Claude calls -- native
- `notion-sdk-py`: async client built in -- native
- `hubspot-api-client`: sync only. Wrap in `asyncio.to_thread()`

**Error isolation:** `return_exceptions=True` in `asyncio.gather()` so one source failure does not cancel others. Matches current pattern where each `_ingest_*` function catches its own errors.

**Confidence:** HIGH -- asyncio.gather() is well-established, key libraries support async or can be thread-wrapped.

### Algorithmic Cross-Source Dedup

**What it does:** Pre-filter obvious duplicates before the synthesis LLM call, reducing token usage and improving dedup determinism.

**Approach:**
1. After all sources are ingested, collect all SourceItems
2. Compute TF-IDF vectors on `title + " " + content` fields using sklearn `TfidfVectorizer`
3. Compute pairwise cosine similarity within same-day items
4. Flag pairs above threshold (0.80-0.85) as potential duplicates
5. For flagged pairs: keep item from higher-priority source, annotate with cross-references
6. Pass deduplicated items to synthesis, with annotations so LLM knows about merged sources

**Why TF-IDF over embeddings:** At 50-100 items/day, TF-IDF is instantaneous (<100ms), requires no GPU/model download, and catches lexical duplicates well. LLM dedup (already in synthesis prompt) catches semantic duplicates. Two layers is the right architecture.

**What it does NOT replace:** The synthesis prompt's cross-source dedup instructions. Algorithmic dedup is a pre-filter. The LLM still handles nuanced semantic merging ("Q3 timeline slipped" in meeting vs "we're pushing to Q3" in Slack).

**New dependency:** `scikit-learn` (for `TfidfVectorizer` and `cosine_similarity`). Lightweight, well-maintained, no GPU requirement.

**Confidence:** MEDIUM -- approach is sound, but threshold tuning requires experimentation with real data. May need adjustment after observing false positives/negatives.

### Typed Config Model

**What it does:** Replace `dict` config with validated Pydantic models. Fail on startup if config is invalid.

**Current state:** `load_config()` in config.py returns raw `dict` (line 9-41). Every module does `config.get("slack", {}).get("enabled", False)` with scattered defaults. Typos are silent. Missing sections cause runtime KeyError deep in the pipeline.

**Target state:**
```python
class SlackConfig(BaseModel):
    enabled: bool = False
    channels: list[str] = Field(default_factory=list)
    dms: list[str] = Field(default_factory=list)
    thread_min_replies: int = 3
    thread_min_participants: int = 2
    max_messages_per_channel: int = 100
    bot_allowlist: list[str] = Field(default_factory=list)
    # ... etc

class PipelineConfig(BaseModel):
    pipeline: PipelineSettings
    calendars: CalendarSettings
    transcripts: TranscriptSettings
    synthesis: SynthesisSettings
    slack: SlackConfig = SlackConfig()
    google_docs: GoogleDocsConfig = GoogleDocsConfig()
    hubspot: HubSpotConfig = HubSpotConfig()
    notion: NotionConfig = NotionConfig()
```

**Migration path:** Define models matching current config.yaml structure. Update `load_config()` to return `PipelineConfig` via `PipelineConfig.model_validate(yaml_data)`. Update all call sites from `config.get("slack", {})` to `config.slack`. This touches many files but is mechanical -- each module gains typed access.

**Environment variable overrides:** Keep existing pattern (lines 32-39 of config.py) by applying overrides to the dict before Pydantic validation, or use pydantic-settings for env var integration.

**Confidence:** HIGH -- Pydantic v2 already a dependency, pattern is well-documented and widely used.

### Slack User Batch Resolution

**What it does:** Replace per-user `users.info` API calls with a single `users.list` call.

**Current state:** `resolve_user_names()` in slack.py (lines 54-90) iterates user_ids, calling `client.users_info(user=uid)` for each. Module-level `_user_cache` prevents repeat calls within a run, but first run still makes N calls (10-20 for a typical day).

**Target state:** At start of Slack ingestion, call `client.users_list()` once, build complete `user_id -> display_name` map, cache for session. For large workspaces, paginate (200 users per page).

**Confidence:** HIGH -- standard Slack API pattern, trivial change.

### Cache Retention Policy

**What it does:** Auto-delete raw cached data (API responses, raw emails) older than a configurable TTL.

**Current state:** `cache_raw_response()` and `cache_raw_emails()` write to `output/raw/` with date-stamped filenames. No cleanup.

**Target config:** `pipeline.cache_retention_days: 30` (default). On pipeline start, scan `output/raw/`, delete directories/files older than TTL.

**Confidence:** HIGH -- pure file system operation, no API or library concerns.

## Sources

- [Notion API Database Query Filter](https://developers.notion.com/reference/post-database-query-filter) -- HIGH confidence, official docs
- [Notion API Timestamp Filter Changelog](https://developers.notion.com/changelog/filter-databases-by-timestamp-even-if-they-dont-have-a-timestamp-property) -- HIGH confidence, official changelog
- [notion-sdk-py (GitHub)](https://github.com/ramnes/notion-sdk-py) -- HIGH confidence, primary Python SDK
- [Anthropic Structured Outputs Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) -- HIGH confidence, official GA docs
- [Pydantic Settings Management](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) -- HIGH confidence, official docs
- [asyncio.gather() Best Practices](https://blog.poespas.me/posts/2024/05/24/python-asyncio-gather-examples/) -- MEDIUM confidence, community source verified against Python docs
- [TF-IDF + Cosine Similarity for Text Matching](https://bergvca.github.io/2017/10/14/super-fast-string-matching.html) -- MEDIUM confidence, well-established technique

---
*Feature research for: Work Intelligence Pipeline v1.5.1 -- Notion + Performance + Reliability*
*Researched: 2026-04-04*
