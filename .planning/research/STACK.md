# Stack Research: v1.5.1 New Capabilities

**Domain:** Work intelligence pipeline -- Notion ingestion, asyncio parallelization, structured outputs, config validation, cache management, algorithmic dedup
**Researched:** 2026-04-04
**Confidence:** HIGH

## Existing Stack (validated, not changing)

| Technology | Version (installed) | Purpose |
|------------|-------------------|---------|
| Python | 3.12+ | Runtime |
| anthropic SDK | 0.88.0 | Claude API (Sonnet daily, Opus roll-ups) |
| google-api-python-client | 2.193.0 | Calendar, Gmail, Drive, Docs |
| slack_sdk | 3.41.0 | Slack API |
| hubspot-api-client | 12.0.0 | HubSpot API |
| pydantic | 2.12.5+ | Data models |
| httpx | 0.28.1+ | HTTP client |
| pyyaml | 6.0.3+ | Config loading |
| jinja2 | 3.1.6+ | Output templates |
| pytest | 9.0.2+ | Testing |

## New Dependencies

### Core: Notion Ingestion

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| notion-client | >=3.0.0,<4.0 | Official Notion API client | The canonical Python SDK for Notion API (ramnes/notion-sdk-py). Provides both sync `Client` and async `AsyncClient`. Uses httpx under the hood -- already in our dependency tree. v3.0.0 is current stable. Supports Notion API version 2026-03-11. |

**Integration notes:**
- `notion-client` depends on `httpx`, which we already have. No transitive dependency conflicts.
- Provides `AsyncClient` out of the box -- important for our asyncio parallelization work. Use `AsyncClient` in the parallel pipeline, `Client` for any standalone scripts.
- Notion API has no "changes since date" endpoint. We must query databases/pages and filter client-side by `last_edited_time`. This is an API limitation, not a library issue.
- The Notion API uses cursor-based pagination. The library handles this via `iterate` helpers, but you must implement date-range filtering yourself.

**Authentication:** Internal Integration Token. Store as `NOTION_TOKEN` in `.env`. Create at notion.so/my-integrations, then share target pages/databases with the integration manually.

**Rate Limits (MOST RESTRICTIVE of all services):** 3 requests/second average. For daily batch reading ~5-20 pages, add 0.35s delay between calls.

### Core: Asyncio Parallelization

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| asyncio (stdlib) | -- | Concurrent ingest orchestration | Built into Python 3.12+. Use `asyncio.gather()` to run independent ingest modules concurrently. No external dependency needed. |
| aiofiles | >=25.1.0,<26.0 | Async file I/O for cache reads/writes | Prevents blocking the event loop during file operations in async ingest paths. Lightweight, well-maintained. Only needed if ingest modules do significant file I/O within async context. |

**Integration notes:**
- The pipeline currently uses synchronous `anthropic.Anthropic`. For parallel Claude calls (per-meeting extraction), use `anthropic.AsyncAnthropic` which is already included in the `anthropic` SDK -- no additional dependency.
- `slack_sdk` ships `AsyncWebClient` for async Slack calls. Already in our dependency (`slack_sdk>=3.33.0`). Requires `aiohttp` as an optional dependency -- must be installed explicitly.
- Google API client (`google-api-python-client`) is synchronous-only. Wrap in `asyncio.to_thread()` to run without blocking. Do NOT try to find an async Google client -- the official library is sync and `to_thread()` is the correct pattern.
- `httpx` (used by notion-client) is natively async. The `notion_client.AsyncClient` uses it directly.
- Pattern: `asyncio.gather(_ingest_slack_async(), _ingest_hubspot_async(), _ingest_docs_async(), _ingest_notion_async(), _ingest_calendar_async())` with each module wrapping its sync calls in `asyncio.to_thread()` where needed.

### Core: Structured Output Migration

No new dependencies needed. The existing `anthropic>=0.45.0` SDK (we have 0.88.0 installed) supports structured outputs via the GA `output_config` parameter.

**Migration details:**
- Structured outputs are GA (not beta) on Claude API for Sonnet 4.5+, Opus 4.5+, Haiku 4.5+. The claude-sonnet-4-20250514 model currently used in `extractor.py` and `synthesizer.py` supports this.
- Use `output_config={"format": {"type": "json_schema", "schema": {...}}}` in `client.messages.create()`.
- The old beta header (`structured-outputs-2025-11-13`) and `output_format` parameter still work but are deprecated. Use `output_config.format` directly.
- Response content is still in `response.content[0].text` -- parse with `json.loads()`. Alternatively, define Pydantic models and use `model_validate_json(response.content[0].text)` for automatic validation.
- Define JSON schemas matching existing `MeetingExtraction`, `DailySynthesis` section structures, and `Commitment` models. Pydantic's `.model_json_schema()` generates compatible schemas.
- The `additionalProperties: false` constraint is recommended for strict validation.
- Replace all `_parse_section_items()` regex-based markdown parsing in `extractor.py` and `synthesizer.py` with schema-constrained responses.
- For async parallel extraction: use `AsyncAnthropic` with same `output_config` parameter.

**Minimum SDK version for GA structured outputs:** Bump `anthropic>=0.82.0` in pyproject.toml to ensure `output_config` parameter support. Our installed 0.88.0 already supports it.

### Core: Algorithmic Deduplication

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| rapidfuzz | >=3.12.0,<4.0 | Fast fuzzy string matching for cross-source dedup | C-extension performance (~10-100x faster than difflib). Provides `fuzz.token_sort_ratio` and `fuzz.token_set_ratio` for comparing normalized event descriptions across sources. MIT licensed. No heavy dependencies. |

**Integration notes:**
- Use `rapidfuzz.fuzz.token_set_ratio` for comparing source items -- it handles word reordering (same topic described differently in Slack vs. meeting transcript).
- Set threshold at ~80 for "likely same topic" and ~90 for "definitely same topic". Tune based on testing.
- Supplement (not replace) existing LLM-based dedup. Algorithmic dedup runs first as a cheap pre-filter, reducing items sent to LLM dedup.
- Works on normalized `SourceItem.content` strings. Normalize before comparison: lowercase, strip punctuation, remove stop words.
- `process.cdist()` can compute pairwise similarity matrix efficiently for batch dedup across all source items.

### Supporting: Slack Batch User Resolution

No new dependencies. The existing `slack_sdk` (3.41.0) already provides `users_list()` on both `WebClient` and `AsyncWebClient`.

**Migration details:**
- Current code in `slack.py:resolve_user_names()` (line 54-90) calls `users_info(user=uid)` per user (N API calls).
- Replace with single `users_list()` call that returns all workspace users, then build lookup dict.
- `users_list()` is paginated (default limit 200). For workspaces with <1000 users, 1-5 API calls vs. N individual calls.
- Cache the full user list in memory for the pipeline run (users don't change mid-run).
- For async pipeline: use `AsyncWebClient.users_list()`.

### Supporting: Typed Config Validation

No new dependencies. Pydantic (already >=2.12.5) handles this.

**Implementation details:**
- Define a `PipelineConfig` Pydantic model mirroring `config/config.yaml` structure.
- Use `pydantic.BaseModel` with nested models for each section (`SlackConfig`, `HubSpotConfig`, `SynthesisConfig`, `NotionConfig`, etc.).
- Replace `load_config() -> dict` in `src/config.py` with `load_config() -> PipelineConfig` that calls `PipelineConfig.model_validate(yaml_data)`.
- Pydantic provides: type coercion, default values, validation errors with field paths, and IDE autocompletion on `ctx.config.slack.enabled` instead of `ctx.config.get("slack", {}).get("enabled", False)`.
- Environment variable overrides: handle in the loading function before validation, or use `model_validator(mode='after')`.
- `PipelineContext.config` type changes from `dict` to `PipelineConfig` -- update all consumers.

### Supporting: Cache Retention Policy

No new dependencies. Use `pathlib` (stdlib) and `os.stat()` for file age checks.

**Implementation details:**
- Add `cache_retention_days: int = 30` to the new config model.
- On pipeline start, scan cache directories (`output/raw/`, `output/cache/`) for files older than TTL.
- Use `Path.stat().st_mtime` for age calculation, `Path.unlink()` for deletion.
- Log deletions at INFO level. Never delete current day's data.

### Supporting: Async HTTP for Slack

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| aiohttp | >=3.11.0,<4.0 | Required by slack_sdk AsyncWebClient | slack_sdk's AsyncWebClient requires aiohttp as its HTTP transport. Not installed by default with slack_sdk -- must be added explicitly. Without it, async Slack calls raise `ImportError`. |

## Installation

```bash
# New dependencies for v1.5.1
uv add "notion-client>=3.0.0,<4.0"
uv add "rapidfuzz>=3.12.0,<4.0"
uv add "aiohttp>=3.11.0,<4.0"
uv add "aiofiles>=25.1.0,<26.0"

# Update anthropic minimum to ensure output_config support
# In pyproject.toml, change: "anthropic>=0.45.0,<1.0" -> "anthropic>=0.82.0,<1.0"
```

## Updated pyproject.toml Dependencies

```toml
dependencies = [
    "google-api-python-client>=2.193.0,<3.0",
    "google-auth>=2.49.1,<3.0",
    "google-auth-httplib2>=0.3.1,<1.0",
    "google-auth-oauthlib>=1.3.1,<2.0",
    "httpx>=0.28.1,<1.0",
    "jinja2>=3.1.6,<4.0",
    "pydantic>=2.12.5,<3.0",
    "python-dateutil>=2.9.0.post0,<3.0",
    "pyyaml>=6.0.3,<7.0",
    "anthropic>=0.82.0,<1.0",         # bumped for GA structured outputs
    "python-dotenv>=1.0.0,<2.0",
    "slack-sdk>=3.33.0,<4.0",
    "hubspot-api-client>=12.0.0,<13.0",
    "notion-client>=3.0.0,<4.0",      # NEW: Notion API
    "rapidfuzz>=3.12.0,<4.0",         # NEW: algorithmic dedup
    "aiohttp>=3.11.0,<4.0",           # NEW: required by slack_sdk AsyncWebClient
    "aiofiles>=25.1.0,<26.0",         # NEW: async file I/O
]
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| notion-client (official) | ultimate-notion | Never for this project. Adds ORM-like abstraction we don't need. |
| notion-client (official) | notion-sdk (getsyncr) | Never. Less maintained, smaller community. |
| rapidfuzz | thefuzz (fuzzywuzzy) | Never. thefuzz is slower (pure Python fallback), less maintained. rapidfuzz is a strict superset. |
| rapidfuzz | difflib (stdlib) | Only if you want zero deps and don't care about perf. difflib SequenceMatcher is ~50-100x slower. |
| asyncio.to_thread() | aiogoogle | Never. aiogoogle is unmaintained. `to_thread()` is the stdlib solution for wrapping sync Google API calls. |
| aiohttp (for slack_sdk) | httpx (for slack_sdk) | Not possible. slack_sdk AsyncWebClient specifically requires aiohttp. Not configurable. |
| Pydantic config model | pydantic-settings | Not worth the extra dep. pydantic-settings adds env var binding but we only have 3 env overrides -- handle manually. |

## What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| instructor | Wraps anthropic SDK for structured outputs. Unnecessary -- anthropic SDK now has native GA structured outputs via `output_config`. Another abstraction layer and dependency. | Native `output_config` + `json.loads()` + Pydantic `model_validate()` |
| celery / dramatiq | Overkill. We need concurrent I/O within a single pipeline run, not distributed task queues. | `asyncio.gather()` |
| motor / asyncpg | No database in this project (flat file storage until v2.0). | pathlib + aiofiles |
| notion-py (jamalex) | Uses unofficial/undocumented Notion API. Fragile, breaks with Notion updates. | notion-client (official API) |
| langchain | Massive dependency tree for simple Claude API calls. Direct SDK calls are simpler and more maintainable. | Direct anthropic SDK |
| tenacity | Slack SDK has built-in retry. For Notion, simple `time.sleep(0.35)` between calls suffices. For Claude, structured outputs eliminate retry-on-parse-failure. | Built-in retry + simple sleep |
| requests | Already have httpx which is strictly better (async support, HTTP/2). Note: hubspot-api-client uses requests internally but that's its own transitive dep. | httpx |

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| notion-client 3.0.0 | httpx >=0.23.0 | Our httpx 0.28.1+ satisfies this. No conflict. |
| notion-client 3.0.0 | Python >=3.9 | Our Python 3.12+ satisfies this. |
| aiohttp >=3.11.0 | Python >=3.9 | Coexists with httpx -- different use cases (aiohttp for slack_sdk, httpx for notion-client/anthropic). |
| rapidfuzz >=3.12.0 | Python >=3.9 | C extension wheels available for macOS arm64, Linux x86_64. |
| anthropic >=0.82.0 | httpx >=0.20.0 | No conflict with our httpx pin. |
| aiofiles 25.1.0 | Python >=3.9 | No dependency conflicts. |

## Capability-to-Library Mapping

Quick reference for plan authors -- which library addresses which v1.5.1 feature.

| Feature | Library | Key API / Pattern |
|---------|---------|-------------------|
| Notion ingestion | notion-client | `Client.databases.query()`, `Client.blocks.children.list()`, `Client.search()` |
| Parallel ingest | asyncio (stdlib) | `asyncio.gather()`, `asyncio.to_thread()` |
| Parallel Claude calls | anthropic (existing) | `AsyncAnthropic.messages.create()` with `output_config` |
| Structured outputs | anthropic (existing) | `messages.create(output_config={"format": {"type": "json_schema", "schema": ...}})` |
| Slack batch users | slack_sdk (existing) | `WebClient.users_list()` or `AsyncWebClient.users_list()` |
| Async Slack | slack_sdk + aiohttp | `AsyncWebClient` (requires aiohttp at runtime) |
| Algorithmic dedup | rapidfuzz | `fuzz.token_set_ratio()`, `process.cdist()` |
| Config validation | pydantic (existing) | `BaseModel`, `model_validate()`, `model_json_schema()` |
| Cache retention | pathlib (stdlib) | `Path.stat()`, `Path.unlink()`, `Path.glob()` |
| Async file I/O | aiofiles | `aiofiles.open()` |

## Environment Variables (New)

```bash
# .env addition for Notion
NOTION_TOKEN=ntn_...               # Notion internal integration secret
```

Note: `SLACK_BOT_TOKEN` and `HUBSPOT_ACCESS_TOKEN` already exist from v1.5.

## Sources

- [Anthropic structured outputs docs (GA)](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) -- verified output_config API shape, GA status, supported models (HIGH confidence)
- [notion-client PyPI](https://pypi.org/project/notion-client/) -- verified v3.0.0 latest via `pip index versions` (HIGH confidence)
- [ramnes/notion-sdk-py GitHub](https://github.com/ramnes/notion-sdk-py) -- verified async support, httpx dependency (HIGH confidence)
- [RapidFuzz GitHub](https://github.com/rapidfuzz/RapidFuzz) -- verified version 3.12+, C extension performance (HIGH confidence)
- [slack_sdk AsyncWebClient docs](https://docs.slack.dev/tools/python-slack-sdk/reference/web/async_client.html) -- verified aiohttp requirement, users_list pagination (HIGH confidence)
- [aiofiles PyPI](https://pypi.org/project/aiofiles/) -- verified v25.1.0 latest (MEDIUM confidence, version from web search)
- Installed package versions verified directly from local .venv (HIGH confidence)
- [Notion API versioning](https://developers.notion.com/reference/versioning) -- API version 2026-03-11 (MEDIUM confidence, from web search)

---
*Stack research for: Work Intelligence System v1.5.1*
*Researched: 2026-04-04*
