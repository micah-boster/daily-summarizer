# Project Research Summary

**Project:** Work Intelligence Pipeline v1.5.1
**Domain:** Python data pipeline — Notion ingestion, asyncio parallelization, structured outputs, config validation, algorithmic dedup
**Researched:** 2026-04-04
**Confidence:** HIGH

## Executive Summary

The v1.5.1 milestone is a well-scoped enhancement to an existing, working daily intelligence pipeline. The research task was not "how to build something new" but "how to extend something known" — the codebase is thoroughly understood, all target libraries are verified against installed versions, and all API docs are confirmed. The recommended approach follows three principles: (1) foundation before features (Pydantic config model first, since every subsequent feature adds config), (2) sequential correctness before parallel complexity (structured outputs in sync mode before asyncio), and (3) new source before performance work (Notion ingestor built synchronously, then wrapped in parallel execution).

The core technical choices are clear and validated. Four new dependencies are required: `notion-client` (official Notion SDK with native async), `rapidfuzz` (algorithmic dedup, C-extension speed), `aiohttp` (required by slack_sdk's AsyncWebClient), and `aiofiles` (async file I/O in cache layer). The asyncio parallelization strategy uses `asyncio.to_thread()` to wrap synchronous SDK clients (Google, HubSpot) rather than rewriting them, while leveraging native async for Notion and Claude (AsyncAnthropic). Structured outputs are GA on the current claude-sonnet model and will replace approximately 234 lines of brittle regex parsing across extractor.py and synthesizer.py.

The biggest risks are the two cross-cutting changes: asyncio refactor (which can silently deliver zero parallelism if sync SDKs are not wrapped in `to_thread()`) and structured output migration (which can silently break downstream consumers if the output schema shape diverges from what parsers currently produce). Both risks are mitigated by strict phase ordering: structured outputs first with the sequential pipeline, asyncio last after all other features are stable. The Pydantic config migration carries the highest startup-failure risk but is low-complexity to execute if every field is Optional with sensible defaults and the model is tested against the actual production config.yaml.

## Key Findings

### Recommended Stack

The existing stack requires only four additions for v1.5.1. All other features (structured outputs, config validation, cache management, Slack batch resolution, async per-meeting extraction) use already-installed packages. The `anthropic>=0.82.0` minimum pin should be bumped to ensure GA `output_config` support, though the installed 0.88.0 already satisfies this.

**Core technologies:**
- `notion-client>=3.0.0` (NEW): Official Notion SDK, both sync `Client` and async `AsyncClient` built on httpx — already in the dependency tree. No conflicts. Rate limit is 3 req/s, most restrictive of all services.
- `rapidfuzz>=3.12.0` (NEW): Algorithmic dedup via `fuzz.token_set_ratio` and `process.cdist`. C-extension, ~100x faster than difflib. Strict superset of the deprecated thefuzz library.
- `aiohttp>=3.11.0` (NEW): Required transport for `slack_sdk.AsyncWebClient`. Not installed by default with slack_sdk — will raise `ImportError` if omitted.
- `aiofiles>=25.1.0` (NEW): Async file I/O to avoid blocking the event loop during cache reads/writes in async ingest paths.
- `asyncio` (stdlib): `asyncio.gather()` with `return_exceptions=True` for ingest parallelization; `asyncio.to_thread()` for sync SDK wrappers.
- `anthropic` (existing, bumped to >=0.82.0): `AsyncAnthropic` for parallel per-meeting extraction; `output_config` parameter for structured outputs.
- `pydantic>=2.12.5` (existing): Config model validation, JSON schema generation for Claude structured outputs.

**What NOT to add:** instructor (native SDK handles structured outputs), celery (asyncio.gather suffices), scikit-learn (rapidfuzz covers the dedup use case at this scale), langchain (direct SDK is simpler), tenacity (built-in retry handles most cases).

### Expected Features

See `.planning/research/FEATURES.md` for full specifications.

**Must have (table stakes):**
- Notion page/database ingestion — last major daily-use tool not yet ingested; PROJECT.md identifies this as the primary gap
- Typed config model (Pydantic validation) — current raw-dict config silently accepts typos; failures are runtime KeyErrors deep in the pipeline
- Structured output migration — PROJECT.md explicitly notes this as "overdue"; eliminates two fragile parsers covering 234 lines of regex
- Cache retention policy — output/ directory grows unbounded; no cleanup mechanism exists

**Should have (differentiators):**
- Parallel ingest via asyncio — cuts wall-clock ingest time from ~30-45s (sequential) to ~10-15s (parallel), bottlenecked by slowest source
- Parallel per-meeting extraction — single largest performance win: 8 meetings at 3-5s each drops from 24-40s to ~5s with AsyncAnthropic
- Slack user batch resolution — replaces 10-20 serial `users.info` calls with one paginated `users.list` call
- Algorithmic cross-source dedup — deterministic pre-filter using content fingerprints + time-bucket matching reduces tokens sent to LLM synthesis

**Defer (v2+):**
- Real-time Notion webhook ingestion — Notion's automation API does not expose external webhooks reliably; batch polling on `last_edited_time` is sufficient
- Full Notion workspace crawl — workspaces contain thousands of stale pages; curated database IDs + recency filter is the correct scope
- Embedding-based dedup — sentence-transformers adds hundreds of MB for marginal improvement over rapidfuzz at ~50-100 items/day
- Full async rewrite of all ingest modules — calendar/transcript pipeline has inherent sequential dependencies; targeted async is the 80/20 approach
- Config hot-reload — file-watching complexity for a CLI tool that runs once per day

### Architecture Approach

The architecture follows a straightforward enhancement pattern: the pipeline runner becomes the async orchestration layer while individual ingest modules remain synchronous and are wrapped in `asyncio.to_thread()`. Only two components use native async: `ingest/notion.py` (uses `AsyncClient`) and `synthesis/extractor.py` (uses `AsyncAnthropic` for parallel Claude calls). The existing three-layer structure (ingest → synthesis → output) is preserved with one new layer inserted between ingest and synthesis: algorithmic dedup via `dedup/fingerprint.py`. The config layer moves from `load_config() -> dict` to `load_config() -> PipelineConfig` with full Pydantic validation at startup. The public API of `run_pipeline()` stays synchronous; asyncio is an internal implementation detail bridged via `asyncio.run(_run_pipeline_async(ctx))`.

**Major components:**
1. `models/config.py` (NEW) — Pydantic BaseModel hierarchy matching config.yaml structure; replaces all `.get()` chains with typed attribute access across every ingest module
2. `ingest/notion.py` (NEW) — Follows established SourceItem pattern (mirrors google_docs.py); queries database IDs from config, filters by `last_edited_time`, fetches top-level block children only
3. `models/outputs.py` (NEW) — Pydantic schemas for Claude structured responses: `MeetingExtractionOutput`, `DailySynthesisOutput`; replaces ~234 lines of markdown parsing in extractor.py and synthesizer.py
4. `dedup/fingerprint.py` (NEW) — Content fingerprint + time-bucket matching; runs after all ingest, before synthesis; replaces and generalizes the existing `_dedup_hubspot_items()` in synthesizer.py
5. `pipeline.py` (MODIFIED) — Converts `_run_pipeline_async()` private function using `asyncio.gather(return_exceptions=True)` over `asyncio.to_thread()` wrappers for each ingest source
6. `cache/manager.py` (NEW) — TTL-based cleanup of `output/raw/` files only; never touches `output/daily/` or `output/quality/`

### Critical Pitfalls

See `.planning/research/PITFALLS.md` for full analysis with 15 documented pitfalls.

1. **Sync SDKs blocking the event loop** — wrapping sync ingest functions in `async def` without `asyncio.to_thread()` produces code that looks concurrent but runs sequentially and blocks all other coroutines. Use `asyncio.to_thread(_ingest_slack, ctx)` for every sync SDK. Detect with `PYTHONASYNCIODEBUG=1`.

2. **Structured output migration breaking downstream consumers** — schemas that produce different shapes than the old markdown parsers cause silent data loss (items missing, commitments table empty). Migrate one call site at a time, regression-test output by running both code paths on a known date, keep old parsing behind a flag for one release cycle.

3. **Pydantic config model rejecting existing valid configs** — a strict model will fail on production configs that have grown organically. Use `extra="ignore"` initially, make every field Optional with defaults, and test the actual production config.yaml through the model before shipping.

4. **Parallel Claude calls hitting rate limits** — 8 concurrent extraction calls can exhaust RPM limits, causing thundering-herd retries that make parallelization slower than sequential. Use `asyncio.Semaphore(3)` on Claude calls; tune based on API tier limits observed in `x-ratelimit-remaining-requests` headers.

5. **Notion API version 2025-09-03 breaking changes** — the September 2025 API update introduced `data_source_id` for multi-source databases. Queries using `database_id` alone may fail silently. Pin `notion_version="2025-09-03"` in the client constructor and build an integration health check before the first real run.

## Implications for Roadmap

Based on the combined research, the feature dependency graph and pitfall analysis both converge on the same phase order. The ordering is not preference — each phase creates the stable foundation the next requires.

### Phase 1: Typed Config Foundation

**Rationale:** Every subsequent feature adds new config fields (Notion needs `notion.databases`, cache retention needs `cache.retention_days`, async may need concurrency limits). Building the Pydantic model first means all new config sections are validated from day one rather than retroactively added. This is a pure refactor with no behavior change — correctness is verified by confirming pipeline output is identical before and after.

**Delivers:** `models/config.py` with full Pydantic hierarchy; `load_config()` returns `PipelineConfig`; all consumers migrated from `.get()` chains to typed access.

**Addresses:** Table stakes — typed config model (FEATURES.md)

**Avoids:** Pitfall 5 (Pydantic rejects existing configs), Integration Pitfall 2 (Notion config vs. config model chicken-and-egg)

### Phase 2: Structured Output Migration

**Rationale:** Structured outputs are independent of all other v1.5.1 work — they touch only the Claude API call sites in extractor.py and synthesizer.py, not ingest modules or async infrastructure. Doing this in sequential mode makes correctness easy to verify: run on a known date, diff the output. Once stable, the async phase only needs to swap sync for async clients without simultaneously changing response shapes.

**Delivers:** `models/outputs.py` with `MeetingExtractionOutput` and `DailySynthesisOutput`; deletion of ~234 lines of regex parsing; per-meeting extraction and daily synthesis return typed Pydantic models instead of parsed markdown dicts.

**Addresses:** Table stakes — structured output migration (FEATURES.md)

**Avoids:** Pitfall 2 (downstream parsing mismatch), Pitfall 10 (schema rejects edge cases on empty days), Integration Pitfall 1 (async + structured outputs = double migration risk)

### Phase 3: Notion Ingestion

**Rationale:** A new ingest module is best built and debugged in synchronous code. It follows the established SourceItem pattern (mirrors google_docs.py) and can be wired into pipeline.py sequentially first, tested in isolation, then parallelized in Phase 5. Building Notion after config validation means the `NotionConfig` model is already in place.

**Delivers:** `ingest/notion.py`; `NOTION_PAGE` and `NOTION_DATABASE` source types; Notion databases/pages ingested as SourceItems filtered by `last_edited_time`; `NOTION_TOKEN` in .env.

**Addresses:** Table stakes — Notion ingestion (FEATURES.md)

**Avoids:** Pitfall 3 (Notion API version breaking changes), Pitfall 8 (block pagination drops content), Pitfall 11 (rate limit timeout on large workspaces)

### Phase 4: Reliability Quick Wins

**Rationale:** Three low-risk, low-dependency improvements that deliver independent value before the riskiest phase. Slack batch user resolution and module global elimination are also prerequisites for async safety — module-level mutable caches must be removed before ingest functions run concurrently in threads.

**Delivers:** Slack `users.list()` batch resolution; `cache/manager.py` with TTL cleanup of `output/raw/` only (never processed output); `dedup/fingerprint.py` with content-fingerprint + time-bucket matching replacing `_dedup_hubspot_items()`.

**Addresses:** Table stakes — cache retention; Differentiators — Slack batch resolution, algorithmic dedup (FEATURES.md)

**Avoids:** Pitfall 6 (cache deletes roll-up data — only raw, TTL >= 35 days), Pitfall 7 (false positives on short text — require multiple matching signals, threshold >= 0.85), Pitfall 12 (Slack paginated user list), Integration Pitfall 3 (cache retention unaware of Notion raw data)

### Phase 5: Asyncio Parallelization

**Rationale:** The async refactor touches pipeline orchestration and changes execution semantics — it is the riskiest change and goes last so all other features are stable. At this point: config is typed, structured outputs are verified, Notion exists as a synchronous module, module globals are eliminated, dedup is in place. The async layer wraps all of this in `asyncio.to_thread()` without touching ingest module internals. Parallel per-meeting extraction with `AsyncAnthropic` is added in the same phase since the async infrastructure is already present.

**Delivers:** `run_pipeline()` bridges to `_run_pipeline_async()`; all ingest sources run concurrently via `asyncio.gather(return_exceptions=True)` over `asyncio.to_thread()` wrappers; `extract_all_meetings_async()` with `AsyncAnthropic` and `asyncio.Semaphore(3)`; `aiohttp` installed for slack_sdk async; wall-clock reduction from ~45-80s to ~15-20s.

**Addresses:** Differentiators — parallel ingest, parallel per-meeting extraction (FEATURES.md)

**Avoids:** Pitfall 1 (sync SDKs block event loop — use to_thread, not async def wrappers), Pitfall 4 (Claude rate limits — Semaphore), Pitfall 9 (asyncio.run from existing loop — keep public API sync), Pitfall 14 (error isolation — return_exceptions=True always)

### Phase Ordering Rationale

- **Config first** because it is a pure refactor (zero behavior change, verifiable by output diff) and every subsequent feature adds config fields. Retroactive migration is harder than building on a typed foundation.
- **Structured outputs before async** because changing response format and execution model simultaneously makes debugging impossible. Each must be independently testable.
- **Notion before async** because new ingest modules are easier to build and verify in synchronous code. Test correctness first, then parallelize.
- **Reliability wins before async** because they reduce the complexity surface of the riskiest phase, and two of them (module global elimination, Slack batch resolution) are prerequisites for async safety.
- **Async last** because it is the capstone that benefits from all prior work being stable. It is also the only phase that changes execution semantics — keeping it last isolates failure modes.

### Research Flags

Phases with well-documented patterns (safe to plan without additional research):
- **Phase 1 (Config):** Pydantic v2 config validation is thoroughly documented. Pattern is mechanical: define models, validate YAML, update call sites. `commitments.py` proves the Pydantic + structured output pattern already works in this codebase.
- **Phase 2 (Structured Outputs):** `commitments.py` already proves the `output_config` pattern in this codebase. Migration is schema definition + deletion of existing parsers. One-at-a-time per call site.
- **Phase 4 (Quick Wins):** Slack `users.list()` and cache TTL are standard operations. Fingerprint dedup approach is fully specified in ARCHITECTURE.md with example code.

Phases needing careful planning attention:
- **Phase 3 (Notion):** The Notion API 2025-09-03 breaking changes (data_source_id for multi-source databases) require explicit API version pinning and a health check. Block pagination handling for nested pages needs explicit test coverage. The integration must be manually shared with each configured page/database in the Notion UI — this must be documented as a setup prerequisite. Plan should be explicit about the API version constraint and the health check pattern.
- **Phase 5 (Async):** The asyncio refactor of pipeline.py has the most concurrent-state risk. The `asyncio.Semaphore` value for Claude calls requires empirical tuning against actual API tier limits — this cannot be determined until execution. Plan should call out both the module-global elimination prerequisite and the semaphore tuning step explicitly.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All packages verified via pip, installed versions confirmed in .venv, Notion API version confirmed via official changelog, no transitive dependency conflicts |
| Features | HIGH | Existing codebase analyzed directly, all API endpoints verified against official docs, feature dependencies mapped from actual code |
| Architecture | HIGH | Based on direct codebase inspection of pipeline.py, extractor.py, synthesizer.py, commitments.py, config.py; `asyncio.to_thread()` pattern verified against Python 3.12 docs; target flow fully specified with example code |
| Pitfalls | HIGH | All critical pitfalls grounded in codebase-specific analysis (actual parsing functions named, actual module globals identified); Notion API version pitfall confirmed via official upgrade guide; 15 pitfalls documented across 4 severity levels |

**Overall confidence:** HIGH

### Gaps to Address

- **Algorithmic dedup threshold tuning:** The rapidfuzz threshold (~80-85 for token_set_ratio) requires testing against real SourceItem data to avoid false positives on short work intelligence items. PITFALLS.md flags this as the feature with most uncertainty. Build with conservative threshold, log near-matches for the first week, tune before enabling auto-merge.
- **Claude API rate limit tier:** The `asyncio.Semaphore` value for parallel extraction depends on actual API tier limits, which vary by account. Research recommends starting at `Semaphore(3)` and tuning based on `x-ratelimit-remaining-requests` response headers. Cannot be determined until Phase 5 execution.
- **Notion integration sharing:** Each Notion database and page must be manually shared with the integration in the Notion UI before the pipeline can access it. This is a one-time setup step, not a code concern, but it must be documented as a required pre-step in the Phase 3 plan.
- **aiofiles version confidence:** aiofiles 25.1.0 version was confirmed via web search (MEDIUM confidence) rather than direct pip verification. Confirm with `pip index versions aiofiles` during Phase 5 dependency installation.

## Sources

### Primary (HIGH confidence)
- Anthropic Structured Outputs docs (GA) — `output_config` parameter shape, supported models, GA status
- notion-sdk-py GitHub (ramnes) — async client support, httpx dependency, pagination helpers, `collect_paginated_api` helper
- Notion API Reference — database query filter, block children endpoint, rate limits (3 req/s)
- Notion API Upgrade Guide 2025-09-03 — data_source_id breaking changes, filter value changes for multi-source databases
- Python 3.12 asyncio docs — `asyncio.gather()`, `asyncio.to_thread()`, event loop constraints
- Pydantic v2 docs — BaseModel, ConfigDict, `model_json_schema()`, ValidationError behavior
- RapidFuzz GitHub — token_set_ratio algorithm, process.cdist for batch comparison, version 3.12+
- slack_sdk AsyncWebClient docs — aiohttp requirement, users_list pagination
- Direct codebase inspection — `src/pipeline.py`, `src/synthesis/extractor.py`, `src/synthesis/synthesizer.py`, `src/synthesis/commitments.py`, `src/ingest/slack.py`, `src/ingest/google_docs.py`, `src/config.py`, `src/models/sources.py`
- Installed package versions — verified from .venv directly

### Secondary (MEDIUM confidence)
- asyncio.gather() best practices (community blog, verified against Python docs) — `return_exceptions=True` pattern and error isolation
- Notion API version date (2026-03-11) — confirmed via web search
- aiofiles 25.1.0 version — confirmed via web search, not direct pip verification

---
*Research completed: 2026-04-04*
*Ready for roadmap: yes*
