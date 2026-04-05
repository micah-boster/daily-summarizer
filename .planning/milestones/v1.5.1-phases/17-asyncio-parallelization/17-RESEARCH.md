# Phase 17: Asyncio Parallelization - Research

**Researched:** 2026-04-05
**Domain:** Python asyncio, concurrent ingest orchestration, async Claude API calls
**Confidence:** HIGH

## Summary

Phase 17 converts the sequential `run_pipeline()` ingest phase to concurrent execution using Python's `asyncio`. The current pipeline in `src/pipeline.py` calls five ingest functions sequentially (`_ingest_slack`, `_ingest_hubspot`, `_ingest_docs`, `_ingest_notion`, `_ingest_calendar`), then feeds results to synthesis. Each source is already error-isolated (try/except returning empty on failure), which is the ideal precondition for concurrent execution.

The project runs Python 3.12 (via `.venv`), which provides `asyncio.TaskGroup` (added 3.11) for structured concurrency. The key insight is that most ingest sources use sync-only SDKs (Google API client, HubSpot SDK, Slack SDK), so these must be wrapped in `asyncio.to_thread()` to run concurrently without blocking the event loop. Only Notion (httpx) and Claude API calls (anthropic) have native async clients available. The `extract_all_meetings()` function in `src/synthesis/extractor.py` currently loops sequentially over meetings calling Claude -- this is the primary target for true async parallelism with a semaphore for rate limiting.

The public API (`run_pipeline()`) must remain synchronous. Internally, it calls `asyncio.run()` on an async orchestrator. This is a clean boundary -- callers (including `main.py` and tests) see no change.

**Primary recommendation:** Use `asyncio.to_thread()` for all sync SDK sources (Calendar, Slack, HubSpot, Google Docs), native `httpx.AsyncClient` for Notion, and `anthropic.AsyncAnthropic` for parallel meeting extraction with `asyncio.Semaphore` for rate limiting.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PERF-01 | Parallel ingest modules via asyncio (independent sources run concurrently, sequential dependencies preserved) | `asyncio.TaskGroup` + `asyncio.to_thread()` for sync SDKs, native async for httpx/anthropic. Calendar+transcripts+extraction remain sequential internally (dependency chain) but run concurrent with other sources. |
| PERF-02 | Parallel per-meeting transcript extraction (concurrent Claude API calls with rate-limit-aware semaphore) | `anthropic.AsyncAnthropic` provides async `messages.create()`. `asyncio.Semaphore(N)` limits concurrent Claude calls. Current `extract_all_meetings()` sequential loop becomes `asyncio.gather()` with semaphore-guarded calls. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| asyncio | stdlib (3.12) | Concurrent execution, TaskGroup, Semaphore | Built-in, no dependency. TaskGroup provides structured concurrency with automatic cancellation on failure. |
| anthropic.AsyncAnthropic | 0.88.0 (installed) | Async Claude API calls for parallel extraction | Already installed. Mirror API to sync `Anthropic` client -- `await client.messages.create()`. |
| httpx.AsyncClient | 0.28.x (installed) | Async HTTP for Notion API | Already installed. Drop-in replacement for sync `httpx.Client`. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncio.to_thread | stdlib | Run sync SDK calls in thread pool | For Google API, HubSpot, Slack -- all sync-only SDKs |
| asyncio.Semaphore | stdlib | Rate-limit concurrent Claude calls | In parallel meeting extraction to cap concurrent requests |
| time.perf_counter | stdlib | Wall-clock timing for before/after measurement | Pipeline timing instrumentation |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| asyncio.to_thread for sync SDKs | aiohttp + slack_sdk.web.async_client | Requires new dependency (aiohttp), only benefits Slack, other SDKs still sync |
| asyncio.TaskGroup | asyncio.gather | TaskGroup auto-cancels on first unhandled error; gather needs manual error handling. But we want partial results on failure, so gather with return_exceptions=True is better for ingest. |
| asyncio.Semaphore | Custom token bucket | Semaphore is simpler, sufficient for bounding concurrency. Token bucket only needed for precise rate/s control. |

**Installation:**
```bash
# No new dependencies required -- all capabilities already installed
# asyncio, anthropic.AsyncAnthropic, httpx.AsyncClient all available
```

## Architecture Patterns

### Recommended Project Structure
```
src/
  pipeline.py          # run_pipeline() stays sync, calls asyncio.run(_async_pipeline())
  pipeline_async.py    # NEW: async orchestrator, parallel ingest, parallel extraction
  synthesis/
    extractor.py       # Add async extract_meeting_async() + extract_all_meetings_async()
  ingest/
    notion.py          # Add AsyncNotionClient using httpx.AsyncClient (optional optimization)
```

### Pattern 1: Sync Wrapper over Async Core
**What:** `run_pipeline()` remains synchronous but internally delegates to an async function via `asyncio.run()`.
**When to use:** When the public API must stay sync but internal operations benefit from concurrency.
**Example:**
```python
# Source: Python 3.12 asyncio docs
import asyncio

def run_pipeline(ctx: PipelineContext) -> None:
    """Public sync API -- unchanged signature."""
    asyncio.run(_async_pipeline(ctx))

async def _async_pipeline(ctx: PipelineContext) -> None:
    """Internal async orchestrator."""
    ingest_result = await _async_ingest_all(ctx)
    # Synthesis and output remain sequential (they depend on ingest results)
    _synthesize_and_output(ctx, ingest_result)
```

### Pattern 2: Parallel Ingest with asyncio.gather + return_exceptions
**What:** Run all ingest sources concurrently. Use `return_exceptions=True` so one failure does not cancel others.
**When to use:** For independent I/O-bound operations where partial results are acceptable.
**Example:**
```python
async def _async_ingest_all(ctx: PipelineContext) -> IngestResult:
    """Run all ingest sources concurrently."""
    results = await asyncio.gather(
        asyncio.to_thread(_ingest_slack, ctx),
        asyncio.to_thread(_ingest_hubspot, ctx),
        asyncio.to_thread(_ingest_docs, ctx),
        asyncio.to_thread(_ingest_notion, ctx),
        asyncio.to_thread(_ingest_calendar, ctx),
        return_exceptions=True,
    )
    # Each _ingest_* already catches its own errors and returns [],
    # but return_exceptions guards against uncaught exceptions too.
    slack_items = results[0] if not isinstance(results[0], BaseException) else []
    hubspot_items = results[1] if not isinstance(results[1], BaseException) else []
    # ... etc
    return IngestResult(...)
```

### Pattern 3: Semaphore-Guarded Parallel Extraction
**What:** Process N meeting transcripts concurrently with a semaphore to respect Claude API rate limits.
**When to use:** When making many API calls that share a rate limit.
**Example:**
```python
async def extract_all_meetings_async(
    events: list[NormalizedEvent],
    config: PipelineConfig,
    client: anthropic.AsyncAnthropic,
    max_concurrent: int = 3,
) -> list[MeetingExtraction]:
    """Extract all meetings concurrently with rate limiting."""
    sem = asyncio.Semaphore(max_concurrent)

    async def _extract_one(event: NormalizedEvent) -> MeetingExtraction | None:
        async with sem:
            return await extract_meeting_async(event, config, client)

    tasks = [_extract_one(e) for e in events if e.transcript_text]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    extractions = []
    for r in results:
        if isinstance(r, BaseException):
            logger.warning("Extraction failed: %s", r)
        elif r is not None:
            extractions.append(r)
    return extractions
```

### Pattern 4: Calendar Chain Stays Sequential
**What:** Calendar -> Transcripts -> Extraction is a dependency chain. It runs as one async task internally but can use parallel extraction at the end.
**When to use:** When steps have data dependencies.
**Example:**
```python
async def _ingest_calendar_with_extraction(ctx, sem) -> tuple:
    """Calendar chain: sequential fetch, parallel extraction."""
    # These are sequential (dependencies)
    categorized, transcripts, unmatched = await asyncio.to_thread(
        _fetch_calendar_and_transcripts, ctx
    )
    # Extraction is parallel across meetings
    events_with_transcripts = [e for e in active_events if e.transcript_text]
    extractions = await extract_all_meetings_async(
        events_with_transcripts, ctx.config, ctx.async_claude_client
    )
    return categorized, transcripts, unmatched, extractions
```

### Anti-Patterns to Avoid
- **Running asyncio.run() inside an existing event loop:** If tests or callers already have a loop, `asyncio.run()` will raise RuntimeError. Guard with `try: loop = asyncio.get_running_loop()` or use a conditional.
- **Making sync ingest functions async when the SDK is sync:** Don't rewrite `_ingest_slack` to be `async def` -- it still calls sync `WebClient`. Use `to_thread` instead.
- **Shared mutable state across threads:** The `PipelineContext` is read-only during ingest, so this is safe. Do NOT share write-state between concurrent tasks.
- **Forgetting to handle exceptions from gather:** With `return_exceptions=True`, exceptions are returned as values. MUST check `isinstance(result, BaseException)`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Rate limiting for Claude API | Custom sleep/retry logic | `asyncio.Semaphore(N)` | Semaphore bounds concurrency cleanly; existing `retry_api_call` (tenacity) already handles retries and backoff |
| Thread pool management | Manual `threading.Thread` | `asyncio.to_thread()` | Uses default executor, handles lifecycle automatically |
| Async HTTP client | Custom aiohttp wrapper | `httpx.AsyncClient` | Already in deps, same API as sync httpx used by Notion |
| Async Claude client | Custom async wrapper | `anthropic.AsyncAnthropic` | Official SDK, same API as sync client |
| Structured concurrency | Manual task tracking | `asyncio.gather()` with `return_exceptions=True` | Handles partial failures gracefully |

**Key insight:** The existing sync ingest functions already have proper error isolation (try/except returning empty lists). The async layer is purely an orchestration concern -- it does not need to change any ingest logic, only how they are scheduled.

## Common Pitfalls

### Pitfall 1: Event Loop Already Running
**What goes wrong:** `asyncio.run()` raises `RuntimeError: This event loop is already running` in Jupyter notebooks, some test frameworks, or nested async calls.
**Why it happens:** `asyncio.run()` creates a new loop and cannot be called from within an existing one.
**How to avoid:** In production code, `run_pipeline()` is always called from `main.py` (no event loop). For tests, mock at the async level or use `pytest-asyncio`.
**Warning signs:** Tests that worked with sync pipeline start failing with RuntimeError.

### Pitfall 2: Semaphore Value Too High
**What goes wrong:** Claude API returns 429 (rate limited) frequently, causing retries and actually being slower than sequential.
**Why it happens:** Semaphore set too high for the API tier's rate limit.
**How to avoid:** Start conservative (3 concurrent calls), make configurable. The existing `retry_api_call` decorator handles 429s with exponential backoff, so some rate limiting is tolerable.
**Warning signs:** Log shows frequent "rate limit" retry warnings during extraction.

### Pitfall 3: Thread Safety with Google Credentials
**What goes wrong:** Google OAuth credentials object (`google.oauth2.credentials.Credentials`) may not be thread-safe if token refresh happens concurrently.
**Why it happens:** Multiple threads using the same `creds` object where one thread triggers a token refresh.
**How to avoid:** Calendar and Gmail use `creds` in the same sequential chain (calendar task). Google Docs uses `creds` in a separate thread. Since token refresh happens once at startup in `main.py`, this is safe during ingest. But if a token expires mid-pipeline, concurrent refresh could race. Mitigation: refresh token before starting async ingest.
**Warning signs:** Sporadic 401 errors from Google APIs during concurrent execution.

### Pitfall 4: to_thread and CPU-bound Work
**What goes wrong:** If any ingest function is CPU-bound (not just I/O-bound), `to_thread` still uses the GIL, and concurrency provides no speedup for CPU work.
**Why it happens:** GIL prevents true parallel CPU execution in threads.
**How to avoid:** All ingest functions are I/O-bound (network requests), so this is not a concern. Claude extraction is network-bound (waiting for API response). Verify no CPU-heavy processing crept into ingest functions.
**Warning signs:** No wallclock improvement despite concurrent execution.

### Pitfall 5: Lost Error Context in gather
**What goes wrong:** When `return_exceptions=True`, exceptions are silently swallowed if not explicitly checked.
**Why it happens:** Developer forgets to inspect results for `BaseException` instances.
**How to avoid:** Always log exceptions from gather results. The existing `_ingest_*` functions already catch and log their own errors, so this is defense-in-depth.
**Warning signs:** Sources fail silently with no log output.

## Code Examples

### Async Meeting Extraction with AsyncAnthropic
```python
# Source: anthropic SDK 0.88.0 (installed)
import anthropic

async def extract_meeting_async(
    event: NormalizedEvent,
    config: PipelineConfig,
    client: anthropic.AsyncAnthropic,
) -> MeetingExtraction | None:
    """Async version of extract_meeting using AsyncAnthropic."""
    if not event.transcript_text:
        return None

    prompt = EXTRACTION_PROMPT.format(
        meeting_title=event.title,
        meeting_time=event.start_time.isoformat() if event.start_time else "",
        participants=", ".join(a.name or a.email for a in event.attendees if not a.is_self),
        transcript_text=event.transcript_text,
    )

    schema = MeetingExtractionOutput.model_json_schema()

    # AsyncAnthropic has identical API to sync Anthropic
    response = await client.messages.create(
        model=config.synthesis.model,
        max_tokens=config.synthesis.extraction_max_output_tokens,
        messages=[{"role": "user", "content": prompt}],
        output_config={
            "format": {"type": "json_schema", "schema": schema}
        },
    )

    data = json.loads(response.content[0].text)
    output = MeetingExtractionOutput.model_validate(data)
    return _convert_output_to_extraction(output, event.title, ...)
```

### Pipeline Timing Instrumentation
```python
import time

async def _async_pipeline(ctx: PipelineContext) -> None:
    t0 = time.perf_counter()
    ingest_result = await _async_ingest_all(ctx)
    t_ingest = time.perf_counter() - t0
    logger.info("Parallel ingest completed in %.1fs", t_ingest)

    # Synthesis and output (sequential)
    t1 = time.perf_counter()
    _synthesize_and_output(ctx, ingest_result)
    t_total = time.perf_counter() - t0
    logger.info("Pipeline total: %.1fs (ingest: %.1fs)", t_total, t_ingest)
```

### Retry Decorator for Async Functions
```python
# tenacity supports async natively
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

retry_api_call_async = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception(_is_retryable),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
# Works identically on async def functions -- tenacity detects coroutines
```

### Configurable Semaphore from Config
```python
# In config.py - add to SynthesisConfig or PipelineSettings
class SynthesisConfig(BaseModel):
    max_concurrent_extractions: int = Field(default=3, ge=1, le=10)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| asyncio.ensure_future + manual loop | asyncio.TaskGroup (3.11+) | Python 3.11 (Oct 2022) | Structured concurrency, auto-cancellation |
| asyncio.get_event_loop().run_until_complete | asyncio.run() | Python 3.7 (June 2018) | Simpler top-level entry point |
| aiohttp for async HTTP | httpx.AsyncClient | httpx 0.20+ (2021) | Same library for sync/async, already in project |
| Custom async Anthropic wrapper | anthropic.AsyncAnthropic | anthropic SDK ~0.20+ | Official SDK support |

**Deprecated/outdated:**
- `asyncio.ensure_future()`: Prefer `asyncio.create_task()` or `TaskGroup.create_task()`
- `loop.run_until_complete()`: Use `asyncio.run()` at top level
- Manual event loop management: Let `asyncio.run()` handle it

## Open Questions

1. **Optimal semaphore value for Claude API rate limit**
   - What we know: The project uses Claude Sonnet 4, rate limits depend on API tier (noted in STATE.md as "unknown")
   - What's unclear: Exact requests-per-minute limit for the user's Anthropic account
   - Recommendation: Default to 3 concurrent, make configurable via `config.yaml`. The existing tenacity retry handles 429s gracefully.

2. **Whether to make Notion ingest natively async**
   - What we know: Notion uses httpx (which has AsyncClient). Currently uses sync httpx with a sleep-based throttle.
   - What's unclear: Whether the performance gain of native async Notion vs `to_thread(sync_notion)` justifies the code change.
   - Recommendation: Start with `to_thread()` for all sources (simplest, uniform). Optimize Notion to native async only if profiling shows it's a bottleneck. The current throttle (0.35s between requests) means Notion is rarely the slowest source anyway.

3. **Retry decorator compatibility with async**
   - What we know: tenacity's `@retry` decorator works on both sync and async functions transparently.
   - What's unclear: Whether the existing `retry_api_call` decorator works correctly when wrapping async functions.
   - Recommendation: Verify with a quick test. If the existing decorator works, reuse it. If not, create a parallel `retry_api_call_async` using the same config.

## Sources

### Primary (HIGH confidence)
- Python 3.12 asyncio documentation - TaskGroup, to_thread, gather, Semaphore
- anthropic SDK 0.88.0 (installed) - AsyncAnthropic verified available with `messages.create()`
- httpx 0.28.x (installed) - AsyncClient verified available
- Project source code - `src/pipeline.py`, `src/synthesis/extractor.py`, `src/retry.py`

### Secondary (MEDIUM confidence)
- tenacity async support - documented in tenacity README, compatible with async functions

### Tertiary (LOW confidence)
- Claude API rate limits - tier-dependent, exact values unknown for this project's account

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already installed and verified in project venv
- Architecture: HIGH - pattern is well-established (sync wrapper over async core, gather for parallel I/O)
- Pitfalls: HIGH - all pitfalls are well-documented in Python asyncio ecosystem

**Research date:** 2026-04-05
**Valid until:** 2026-05-05 (stable domain, asyncio API frozen since 3.11)
