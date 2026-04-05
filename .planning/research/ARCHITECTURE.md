# Architecture Research

**Domain:** Pipeline enhancement -- integrating Notion ingestion, asyncio parallelization, Claude structured outputs, algorithmic dedup, typed config, and cache management into existing daily intelligence pipeline
**Researched:** 2026-04-04
**Confidence:** HIGH (based on direct codebase analysis + official documentation)

## Current Architecture (Baseline)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Entry Point (main.py)                        │
│   CLI parsing, date range loop, Google auth, PipelineContext setup  │
├─────────────────────────────────────────────────────────────────────┤
│                     Pipeline Runner (pipeline.py)                    │
│         run_pipeline(ctx) -- sequential orchestration                │
├───────────┬───────────┬───────────┬──────────────┬──────────────────┤
│ _ingest_  │ _ingest_  │ _ingest_  │ _ingest_     │                  │
│ calendar  │ slack     │ hubspot   │ docs         │  (sequential)    │
│ +transcr  │           │           │              │                  │
├───────────┴───────────┴───────────┴──────────────┴──────────────────┤
│                    Synthesis Layer (two-stage)                       │
│  Stage 1: extract_all_meetings (sequential per-meeting Claude calls)│
│  Stage 2: synthesize_daily (single cross-source Claude call)        │
│  Stage 3: extract_commitments (single Claude call, structured out)  │
├─────────────────────────────────────────────────────────────────────┤
│                        Output Layer                                  │
│  write_daily_summary (markdown) + write_daily_sidecar (JSON)        │
│  quality tracking, Slack notification                                │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Architectural Facts from Codebase

| Aspect | Current State | Implication for v1.5.1 |
|--------|--------------|------------------------|
| Orchestration | `run_pipeline()` is synchronous, calls ingest functions sequentially | Must wrap in `asyncio.run()` or convert to async |
| Claude client | `anthropic.Anthropic` (sync), one instance in `PipelineContext` | Need `AsyncAnthropic` for parallel Claude calls |
| Ingest modules | Each returns `list[SourceItem]` or tuple, catches own errors | Clean fit for `asyncio.gather()` with `return_exceptions=True` |
| Calendar ingest | Coupled: calendar -> transcripts -> normalizer -> extraction | Cannot fully decouple; extraction depends on transcript fetch |
| Config | `load_config()` returns untyped `dict`, no validation | Clean replacement point; all consumers use `ctx.config` param |
| Module caches | `_user_cache`, `_channel_name_cache` (Slack), `_user_email_cache` (Docs) as mutable module globals | Not async-safe; must convert to instance-level or pass-through |
| Claude API calls | New `Anthropic()` fallback in each function if client not passed | Single client reuse via `PipelineContext.claude_client` already works |
| Synthesis parsing | `_parse_synthesis_response()` and `_parse_extraction_response()` use regex/string splitting of markdown | Primary targets for structured output migration |
| Commitment extraction | `commitments.py` already uses `output_config` with `json_schema` | Proven pattern to extend to extractor and synthesizer |

## Target Architecture (v1.5.1)

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Entry Point (main.py)                            │
│   CLI parsing, config load + Pydantic validate, asyncio.run()       │
├─────────────────────────────────────────────────────────────────────┤
│                  Pipeline Runner (pipeline.py)                       │
│       async run_pipeline(ctx) -- parallel orchestration              │
├────────────────────────────┬────────────────────────────────────────┤
│   Parallel Ingest Phase    │   Calendar Ingest (sequential chain)   │
│   (asyncio.gather)         │                                        │
│ ┌─────────┐ ┌──────────┐  │  calendar -> transcripts -> normalizer │
│ │  Slack   │ │ HubSpot  │  │       -> parallel extraction           │
│ └─────────┘ └──────────┘  │         (asyncio.gather)                │
│ ┌─────────┐ ┌──────────┐  │                                        │
│ │  Docs   │ │  Notion  │  │                                        │
│ └─────────┘ └──────────┘  │                                        │
├────────────────────────────┴────────────────────────────────────────┤
│                  Algorithmic Dedup Layer (NEW)                       │
│   Fingerprint-based cross-source dedup before LLM synthesis         │
├─────────────────────────────────────────────────────────────────────┤
│                    Synthesis Layer (two-stage)                       │
│  Stage 1: extract_all_meetings (parallel Claude, structured output) │
│  Stage 2: synthesize_daily (structured output -> Pydantic model)    │
│  Stage 3: extract_commitments (unchanged, already structured)       │
├─────────────────────────────────────────────────────────────────────┤
│                        Output Layer (unchanged)                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | v1.5.1 Change |
|-----------|---------------|---------------|
| `config.py` | Load and validate config | **REWRITE**: Returns Pydantic model instead of raw dict |
| `models/config.py` | Typed config model | **NEW**: Pydantic BaseModel for config.yaml structure |
| `pipeline.py` | Orchestrate daily pipeline | **MODIFY**: async, parallel ingest, parallel extraction |
| `PipelineContext` | Shared state for pipeline run | **MODIFY**: Add `async_claude_client`, `notion_client`, typed config |
| `ingest/notion.py` | Fetch Notion pages/databases | **NEW**: Follows established SourceItem pattern |
| `ingest/slack.py` | Fetch Slack messages | **MODIFY**: Batch `users.list()` resolution, no module globals |
| `ingest/google_docs.py` | Fetch Docs edits/comments | **MODIFY**: Remove `_user_email_cache` module global |
| `synthesis/extractor.py` | Per-meeting extraction | **MODIFY**: async + structured output (replace markdown parsing) |
| `synthesis/synthesizer.py` | Cross-source daily synthesis | **MODIFY**: structured output (replace `_parse_synthesis_response`) |
| `synthesis/commitments.py` | Commitment extraction | **UNCHANGED**: Already uses structured outputs |
| `models/sources.py` | SourceItem, SourceType | **MODIFY**: Add NOTION_PAGE, NOTION_DATABASE types |
| `models/outputs.py` | Structured output schemas | **NEW**: Pydantic schemas for Claude structured responses |
| `dedup/fingerprint.py` | Algorithmic cross-source dedup | **NEW**: Pre-LLM dedup using content fingerprints |
| `cache/manager.py` | Cache retention policy | **NEW**: TTL-based cleanup of raw data files |

## Recommended Project Structure Changes

```
src/
├── config.py              # REWRITE: load_config returns PipelineConfig
├── pipeline.py            # MODIFY: async run_pipeline, parallel orchestration
├── main.py                # MODIFY: asyncio.run(), PipelineConfig usage
├── models/
│   ├── config.py          # NEW: PipelineConfig, SlackConfig, NotionConfig, etc.
│   ├── sources.py         # MODIFY: Add NOTION_PAGE, NOTION_DATABASE types
│   ├── outputs.py         # NEW: structured output schemas for Claude responses
│   ├── events.py          # Unchanged
│   └── rollups.py         # Unchanged
├── ingest/
│   ├── notion.py          # NEW: Notion page/database ingestion
│   ├── slack.py           # MODIFY: batch user resolution, instance caches
│   ├── google_docs.py     # MODIFY: instance cache
│   ├── calendar.py        # Unchanged
│   ├── transcripts.py     # Unchanged
│   ├── hubspot.py         # Unchanged
│   ├── normalizer.py      # Unchanged
│   └── ...
├── dedup/
│   ├── __init__.py
│   └── fingerprint.py     # NEW: algorithmic cross-source dedup
├── cache/
│   ├── __init__.py
│   └── manager.py         # NEW: TTL-based cache file cleanup
├── synthesis/
│   ├── extractor.py       # MODIFY: async + structured output
│   ├── synthesizer.py     # MODIFY: structured output
│   ├── commitments.py     # Unchanged
│   ├── models.py          # MODIFY: Add structured output schemas (or use models/outputs.py)
│   ├── weekly.py          # Optional: structured output migration
│   └── monthly.py         # Out of scope for v1.5.1
├── output/                # Unchanged
├── notifications/         # Unchanged
└── validation/            # Unchanged
```

## Architectural Patterns

### Pattern 1: Async Facade over Sync Modules

**What:** Convert `run_pipeline()` to async while keeping existing ingest modules synchronous. Wrap them with `asyncio.to_thread()` for parallel execution. Only Claude API calls and Notion (native async SDK) use true async.

**When to use:** When most I/O is HTTP-based but you have sync-only SDKs (Google API client, Slack SDK `WebClient`).

**Trade-offs:** Simpler migration path (don't rewrite every module). `asyncio.to_thread()` uses a thread pool, so parallelism is real but not as lightweight as pure async. For 4-5 concurrent ingest sources, this is perfectly fine.

**Example:**
```python
async def run_pipeline(ctx: PipelineContext) -> None:
    # Independent ingest sources run in parallel via thread pool
    slack_task = asyncio.to_thread(_ingest_slack, ctx)
    hubspot_task = asyncio.to_thread(_ingest_hubspot, ctx)
    docs_task = asyncio.to_thread(_ingest_docs, ctx)
    notion_task = asyncio.to_thread(_ingest_notion, ctx)
    calendar_task = asyncio.to_thread(_ingest_calendar, ctx)

    results = await asyncio.gather(
        slack_task, hubspot_task, docs_task, notion_task, calendar_task,
        return_exceptions=True,
    )

    # Unpack results, treat exceptions as empty returns
    slack_items = results[0] if not isinstance(results[0], Exception) else []
    hubspot_items = results[1] if not isinstance(results[1], Exception) else []
    # ... etc
```

**Why this over pure async rewrite:** Google API Python client and `slack_sdk.web.WebClient` are synchronous. Rewriting them to use httpx async would be massive scope expansion for marginal benefit. `asyncio.to_thread()` gives real concurrency with minimal code change.

**Confidence:** HIGH -- `asyncio.to_thread()` is standard library, well-understood behavior.

### Pattern 2: Parallel Per-Meeting Extraction with AsyncAnthropic

**What:** Use `anthropic.AsyncAnthropic` for concurrent Claude API calls during per-meeting extraction. This is the single biggest performance win.

**When to use:** When you have N independent Claude API calls (per-meeting extraction currently processes 5-10 meetings sequentially).

**Trade-offs:** True async (no thread pool), but requires converting `extract_meeting` and `extract_all_meetings` to async functions. The Anthropic Python SDK natively supports `AsyncAnthropic` with identical API surface.

**Example:**
```python
from anthropic import AsyncAnthropic

async def extract_meeting_async(
    event: NormalizedEvent,
    config: dict,
    client: AsyncAnthropic,
) -> MeetingExtraction | None:
    if not event.transcript_text:
        return None

    response = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": MeetingExtractionOutput.model_json_schema(),
            }
        },
    )
    data = json.loads(response.content[0].text)
    return MeetingExtractionOutput.model_validate(data)

async def extract_all_meetings_async(
    events: list[NormalizedEvent],
    config: dict,
    client: AsyncAnthropic,
) -> list[MeetingExtraction]:
    tasks = [
        extract_meeting_async(e, config, client)
        for e in events if e.transcript_text
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if isinstance(r, MeetingExtraction)]
```

**Performance impact:** 8 meetings at 3-5s each: sequential = 24-40s, parallel = 3-5s. This is the dominant bottleneck.

**Confidence:** HIGH -- `AsyncAnthropic` is documented first-class in the Anthropic Python SDK.

### Pattern 3: Structured Output Migration (Replace Markdown Parsing)

**What:** Replace `_parse_extraction_response()` and `_parse_synthesis_response()` with Claude structured outputs (`output_config` with `json_schema`), getting guaranteed-valid Pydantic models instead of regex-parsing markdown.

**Migration targets:**

| Call Site | Current Parsing | New Schema | Priority |
|-----------|----------------|------------|----------|
| `extractor.py` `extract_meeting()` | `_parse_extraction_response()` -- regex `## ` header splitting, pipe-delimited items | `MeetingExtractionOutput` | HIGH (most fragile parser) |
| `synthesizer.py` `synthesize_daily()` | `_parse_synthesis_response()` -- regex `## ` header splitting, bullet/table extraction | `DailySynthesisOutput` | HIGH (most complex parser) |
| `commitments.py` `extract_commitments()` | Already uses `output_config` + `CommitmentsOutput` | No change | DONE |
| `weekly.py` weekly rollup | Markdown parsing of thread detection | `WeeklySynthesisOutput` | MEDIUM (lower frequency) |
| `monthly.py` monthly narrative | Markdown parsing | Out of v1.5.1 scope | LOW |

**New Pydantic schemas needed:**

```python
# models/outputs.py

class MeetingExtractionOutput(BaseModel):
    """Structured output for per-meeting extraction (replaces markdown parsing)."""
    model_config = ConfigDict(extra="forbid")

    decisions: list[ExtractionItem] = Field(default_factory=list)
    commitments: list[ExtractionItem] = Field(default_factory=list)
    substance: list[ExtractionItem] = Field(default_factory=list)
    open_questions: list[ExtractionItem] = Field(default_factory=list)
    tensions: list[ExtractionItem] = Field(default_factory=list)

class DailySynthesisOutput(BaseModel):
    """Structured output for daily synthesis (replaces markdown parsing)."""
    model_config = ConfigDict(extra="forbid")

    executive_summary: str | None = None
    substance: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    commitments: list[str] = Field(default_factory=list)
```

**API call pattern (GA, proven in commitments.py):**
```python
response = client.messages.create(
    model=model,
    max_tokens=max_tokens,
    messages=[{"role": "user", "content": prompt}],
    output_config={
        "format": {
            "type": "json_schema",
            "schema": MeetingExtractionOutput.model_json_schema(),
        }
    },
)
data = json.loads(response.content[0].text)
result = MeetingExtractionOutput.model_validate(data)
```

**What this eliminates:** All of `_parse_extraction_response()` (67 lines), `_parse_section_items()` (40 lines), `_parse_legacy_blocks()` (43 lines), and `_parse_synthesis_response()` (84 lines). That is ~234 lines of fragile parsing code replaced by schema definitions.

**Confidence:** HIGH -- `commitments.py` already proves the `output_config` pattern works in this codebase with fallback to beta header.

### Pattern 4: Pydantic Config Model (Replace Untyped Dict)

**What:** Replace `load_config() -> dict` with a typed Pydantic model. All downstream code accesses typed fields instead of `.get()` chains with default fallbacks.

**Example:**
```python
# models/config.py
from pydantic import BaseModel, Field

class SlackConfig(BaseModel):
    enabled: bool = False
    channels: list[dict] = Field(default_factory=list)
    dms: list[dict] = Field(default_factory=list)
    thread_min_replies: int = 3
    thread_min_participants: int = 2
    max_messages_per_channel: int = 100
    bot_allowlist: list[str] = Field(default_factory=list)
    discovery_check_days: int = 7

class NotionConfig(BaseModel):
    enabled: bool = False
    databases: list[dict] = Field(default_factory=list)
    pages: list[str] = Field(default_factory=list)

class CacheConfig(BaseModel):
    retention_days: int = 30

class PipelineConfig(BaseModel):
    pipeline: PipelineSettings
    calendars: CalendarSettings
    transcripts: TranscriptSettings
    synthesis: SynthesisSettings
    slack: SlackConfig = SlackConfig()
    google_docs: GoogleDocsConfig = GoogleDocsConfig()
    hubspot: HubSpotConfig = HubSpotConfig()
    notion: NotionConfig = NotionConfig()
    cache: CacheConfig = CacheConfig()
```

**Migration strategy:** Change `PipelineContext.config` type from `dict` to `PipelineConfig`. Update all `config.get("x", {}).get("y", default)` to `config.x.y`. This is mechanical but touches many files -- do it as the first step before adding new features.

**Why Pydantic BaseModel over pydantic-settings BaseSettings:** The existing config loading is file-based YAML with a few env var overrides. BaseSettings is designed for env-var-first configuration. Use plain BaseModel with manual YAML loading and env var override logic (which already exists in `load_config()`).

**Confidence:** HIGH -- Pydantic is already used for all models in the codebase.

### Pattern 5: Content Fingerprint Dedup

**What:** Pre-LLM algorithmic deduplication using content fingerprinting. Catches obvious duplicates before they reach the synthesis prompt, supplementing (not replacing) the LLM-based dedup.

**How it works:** Combine normalized title + timestamp bucket + sorted participants into a fingerprint. Items with matching fingerprints are duplicates. This generalizes the existing `_dedup_hubspot_items()` logic in `synthesizer.py` (which already does time-bucket matching for HubSpot meetings vs calendar events).

**Example:**
```python
import hashlib

def fingerprint_item(item: SourceItem) -> str:
    normalized_title = item.title.lower().strip()
    time_bucket = int(item.timestamp.timestamp()) // 300  # 5-min buckets
    participants = ",".join(sorted(p.lower() for p in item.participants))
    raw = f"{normalized_title}|{time_bucket}|{participants}"
    return hashlib.md5(raw.encode()).hexdigest()

def dedup_source_items(items: list[SourceItem]) -> list[SourceItem]:
    seen: dict[str, SourceItem] = {}
    for item in items:
        fp = fingerprint_item(item)
        if fp not in seen:
            seen[fp] = item
        else:
            # Keep the one with more content
            if len(item.content) > len(seen[fp].content):
                seen[fp] = item
    return list(seen.values())
```

**Placement in pipeline:** After all ingest modules return, before synthesis. Replaces the current `_dedup_hubspot_items()` with a generalized version.

## Data Flow

### Current Flow
```
config.yaml (unvalidated dict)
    |
PipelineContext(config=dict, claude_client=Anthropic)
    |
_ingest_slack(ctx)     -> list[SourceItem]     --+
_ingest_hubspot(ctx)   -> list[SourceItem]       |  (sequential)
_ingest_docs(ctx)      -> list[SourceItem]       |
_ingest_calendar(ctx)  -> (categorized, ...)   --+
    |
_dedup_hubspot_items() -> filtered list
    |
extract_all_meetings() -> list[MeetingExtraction]  (sequential Claude calls)
    |
synthesize_daily()     -> dict (parsed from markdown)
    |
extract_commitments()  -> list[ExtractedCommitment] (structured output)
    |
write_daily_summary() + write_daily_sidecar()
```

### Target Flow (v1.5.1)
```
config.yaml -> PipelineConfig (Pydantic validated at load time)
    |
PipelineContext(config=PipelineConfig, claude_client=Anthropic,
                async_claude=AsyncAnthropic)
    |
asyncio.gather(                                    --+
    to_thread(_ingest_slack),    -> list[SourceItem]  |
    to_thread(_ingest_hubspot),  -> list[SourceItem]  |  PARALLEL
    to_thread(_ingest_docs),     -> list[SourceItem]  |
    _ingest_notion(async native),-> list[SourceItem]  |  (NEW)
    to_thread(_ingest_calendar), -> (categorized,...) |
)                                                  --+
    |
dedup_source_items(all_items)   -> deduplicated list  (NEW: algorithmic)
    |
extract_all_meetings_async()    -> list[MeetingExtraction]  (PARALLEL Claude)
    |                                                        (structured output)
synthesize_daily()              -> DailySynthesisOutput      (structured output)
    |
extract_commitments()           -> list[ExtractedCommitment] (unchanged)
    |
write_daily_summary() + write_daily_sidecar()
cache_manager.cleanup()         (NEW: TTL-based cache purge)
```

## Integration Points

### New External Services

| Service | SDK | Auth | Notes |
|---------|-----|------|-------|
| Notion API | `notion-client` (ramnes/notion-sdk-py) | Bearer token via `NOTION_TOKEN` env var | `AsyncClient` for native async; query databases by ID list from config |
| Anthropic (async) | `anthropic` (same package, `AsyncAnthropic` class) | Same `ANTHROPIC_API_KEY` | Alongside existing sync `Anthropic` for backward compat |

### Internal Boundary Changes

| Boundary | Current | v1.5.1 | Notes |
|----------|---------|--------|-------|
| pipeline -> ingest | Sync function calls in sequence | `asyncio.to_thread()` wrappers; native async for Notion | Ingest functions stay sync except Notion |
| pipeline -> synthesis | Sync `extract_all_meetings()` | Async `extract_all_meetings_async()` with `AsyncAnthropic` | Biggest performance improvement |
| config -> everything | `config.get()` chains with defaults | Typed attribute access on Pydantic model | Mechanical refactor, many files |
| ingest -> cache (module globals) | `_user_cache`, `_channel_name_cache`, `_user_email_cache` as mutable module-level dicts | Instance-level or passed through context | Required for async safety |

### Notion Integration Specifics

**What Notion provides for daily summaries:**
- Pages the user edited today (via database query with `last_edited_time` filter)
- Database items modified today (same filter)
- Page content extraction (block children API, recursive)

**Notion API constraints (from official docs):**
- No "diff" endpoint -- full current page only, not what changed
- Rate limit: 3 requests/second per integration
- Block children are paginated (100 per page), nested blocks require recursive fetch
- Rich text is block-based -- requires traversal to extract plain text
- Integration must be explicitly shared with each page/database in Notion UI

**Recommended approach:**
1. Config lists database IDs to monitor
2. Query each database with `last_edited_time` filter for target date
3. For returned pages: fetch title + top-level block children only (one API call per page)
4. Convert to `SourceItem` with `source_type=NOTION_PAGE` or `NOTION_DATABASE`
5. Do NOT recursively fetch nested blocks -- title + first-level content is sufficient for synthesis context

### Cache Retention

**Current cache locations:**
- `output/{date}/raw_events.json` -- raw calendar API response
- `output/{date}/raw_emails_transcripts.json` -- raw email data
- In-memory module globals (Slack users, channel names, Docs user email)

**Recommended cache manager:**
- Walk `output/` directory for date-stamped subdirectories
- Delete `raw_*.json` files older than configurable TTL (default 30 days)
- Run at pipeline end (post-output, non-blocking)
- Config: `cache.retention_days: 30`

## Recommended Build Order

Dependency graph:
```
Typed Config (foundation) ------> every other feature reads config
    |
    +-- Structured Outputs ------> independent of async, schema-only change
    |       |
    |       +-- Extractor migration (drop _parse_extraction_response)
    |       +-- Synthesizer migration (drop _parse_synthesis_response)
    |
    +-- Notion Ingest -----------> needs config for database IDs
    |
    +-- Algorithmic Dedup -------> needs all SourceItems from all sources
    |
    +-- Slack Batch Resolution --> prerequisite for async safety (no module globals)
    |
    +-- Asyncio Parallelization -> capstone, benefits from all prior changes
    |
    +-- Cache Retention ---------> independent, lowest risk
```

**Recommended order:**

1. **Typed Config** (`models/config.py` + rewrite `config.py`) -- Foundation. All other features reference config. Pure refactor, no new behavior, easy to validate. Touch this first because later features add new config sections.

2. **Structured Output Migration** (`models/outputs.py` + modify `extractor.py` + modify `synthesizer.py`) -- Independent of async work. Migrate to `output_config` + Pydantic schemas. Delete ~234 lines of markdown parsing code. Test with existing sequential pipeline to isolate correctness from concurrency.

3. **Notion Ingest** (`ingest/notion.py` + modify `models/sources.py` + modify `pipeline.py`) -- New module following established `SourceItem` pattern. Wire into `pipeline.py` sequentially first. Test independently before parallelization.

4. **Algorithmic Dedup** (`dedup/fingerprint.py` + modify `pipeline.py`) -- Insert between ingest and synthesis. Replaces `_dedup_hubspot_items()` with generalized fingerprint-based dedup. Test with existing sources to verify no false positives before adding Notion data.

5. **Slack Batch Resolution + Cache Cleanup** (modify `ingest/slack.py` + modify `ingest/google_docs.py`) -- Use `users.list()` instead of per-user `users.info()` calls. Move caches from module globals to function-local dicts. Required prerequisite for async safety.

6. **Asyncio Parallelization** (modify `pipeline.py` + modify `main.py` + modify `extractor.py`) -- The capstone. Convert `run_pipeline()` to async, wrap sync ingest with `asyncio.to_thread()`, convert `extract_all_meetings()` to async with `AsyncAnthropic`. Benefits from all prior changes being stable.

7. **Cache Retention** (`cache/manager.py`) -- Lowest risk, lowest dependency. Can be done at any point. TTL-based cleanup of raw data files.

**Rationale for this order:** Each step can be tested independently. Typed config is pure refactor (no behavior change). Structured outputs are testable with the existing sequential pipeline. Notion adds a new module without changing existing ones. Dedup is an insert, not a rewrite. Async is the riskiest change and goes last so all other features are stable.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Converting All Ingest Modules to Native Async

**What people do:** Rewrite every ingest module (calendar, slack, hubspot, docs) to use async HTTP clients.
**Why it's wrong:** Google API Python client and `slack_sdk.web.WebClient` are synchronous. Replacing them with raw httpx/aiohttp means losing SDK pagination, error handling, and OAuth token refresh logic.
**Do this instead:** Use `asyncio.to_thread()` for sync ingest modules. True async only for Notion (native `AsyncClient`) and Claude API calls (`AsyncAnthropic`).

### Anti-Pattern 2: Module-Level Mutable State with Async

**What people do:** Keep `_user_cache` and `_channel_name_cache` as module globals while running ingest functions in parallel threads.
**Why it's wrong:** Concurrent writes to unsynchronized dicts corrupt data. Even with CPython's GIL, dict operations are not atomic at the application level.
**Do this instead:** For Slack, the batch `users.list()` call eliminates per-user caching entirely. For remaining caches, pass through function parameters or store on `PipelineContext`.

### Anti-Pattern 3: Combining Structured Output and Async Migration

**What people do:** Convert to structured outputs AND async at the same time.
**Why it's wrong:** Two variables changing simultaneously makes debugging impossible. Is the failure in the new schema, the prompt adjustment, or the async behavior?
**Do this instead:** Migrate to structured outputs first with the sequential pipeline. Verify correctness. Then convert to async as a separate step.

### Anti-Pattern 4: Deep Recursive Notion Block Fetching

**What people do:** Recursively fetch all nested blocks for every Notion page to get full document content.
**Why it's wrong:** Notion blocks can be deeply nested, each level requiring a separate API call. A page with 10 nested sections means 10+ calls at 3 req/sec rate limit = 3+ seconds per page. For a daily summary, you need context, not the full document.
**Do this instead:** Fetch title + top-level blocks only (one API call per page). Properties from database items are already structured -- use them directly.

### Anti-Pattern 5: TaskGroup Instead of gather for Ingest

**What people do:** Use `asyncio.TaskGroup` (Python 3.11+) instead of `asyncio.gather()` for ingest parallelization.
**Why it's wrong for this use case:** TaskGroup cancels remaining tasks when one fails. The entire design of the pipeline is that one source failing should NOT block others.
**Do this instead:** Use `asyncio.gather(return_exceptions=True)` which lets all tasks complete and returns exceptions as values you can check individually.

## Scaling Considerations

| Concern | Current (5 sources) | With Notion (6 sources) | Future (10+ sources) |
|---------|---------------------|------------------------|---------------------|
| Wall-clock ingest time | ~30-45s (sequential) | ~35-50s (sequential) | Would grow linearly |
| Wall-clock with async | ~10-15s (parallel) | ~10-15s (parallel) | ~10-15s (parallel, bottleneck = slowest source) |
| Per-meeting extraction | ~25-40s (8 meetings sequential) | Same | Same |
| Per-meeting with async | ~3-5s (8 meetings parallel) | Same | Add semaphore if >20 meetings |

### First Bottleneck: Sequential Per-Meeting Claude Calls
8 meetings x 3-5s each = 24-40s. Parallelizing drops this to ~5s total. This is the single largest improvement.

### Second Bottleneck: Sequential Ingest
Slack + HubSpot + Docs + Calendar each take 3-10s. Parallelizing overlaps them, saving ~15-25s.

### Future Concern: Notion Rate Limit
At 3 req/sec, monitoring 10 databases with 5 changed pages each = 60 API calls = 20 seconds minimum. Add `asyncio.Semaphore(3)` to cap concurrent Notion requests.

## Sources

- Anthropic Claude API Structured Outputs documentation: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
- Anthropic Python SDK (AsyncAnthropic): https://github.com/anthropics/anthropic-sdk-python
- notion-sdk-py (sync + async client): https://github.com/ramnes/notion-sdk-py
- Notion API Reference (database query, pagination): https://developers.notion.com/reference/post-database-query
- Python asyncio documentation (gather, to_thread): https://docs.python.org/3/library/asyncio-task.html
- Pydantic documentation (BaseModel, Settings): https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- Direct codebase analysis: `src/pipeline.py`, `src/synthesis/extractor.py`, `src/synthesis/synthesizer.py`, `src/synthesis/commitments.py`, `src/ingest/slack.py`, `src/ingest/google_docs.py`, `src/config.py`, `src/models/sources.py`, `src/models/events.py`

---
*Architecture research for: Work Intelligence System v1.5.1 pipeline enhancement*
*Researched: 2026-04-04*
