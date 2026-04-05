# Domain Pitfalls: v1.5.1 Notion + Performance + Reliability

**Domain:** Work intelligence pipeline -- adding Notion ingestion, asyncio parallelization, structured output migration, config validation, cache management, and algorithmic dedup to existing synchronous Python pipeline
**Researched:** 2026-04-04
**Overall confidence:** HIGH (based on codebase inspection, official docs, and verified community sources)

## Critical Pitfalls

Mistakes that cause rewrites, data loss, or pipeline breakage.

### Pitfall 1: Asyncio Retrofit Blocks the Event Loop with Synchronous SDK Calls

**What goes wrong:** You wrap `run_pipeline()` in `async def`, sprinkle `asyncio.gather()` around `_ingest_slack()`, `_ingest_hubspot()`, `_ingest_docs()`, and `_ingest_calendar()` -- but every one of those functions uses synchronous SDK clients (slack_sdk `WebClient`, hubspot-api-client, google-api-python-client, notion-client sync mode). The `asyncio.gather()` runs them all, but they block the event loop sequentially because the underlying HTTP calls are synchronous. Net result: zero parallelism, plus all the complexity of async code.

**Why it happens:** "Make it async" sounds like wrapping functions in `async def` and using `gather()`. But asyncio only yields control at `await` points. Synchronous HTTP libraries never yield. The code looks concurrent but runs sequentially.

**Consequences:** No performance improvement. Worse: debugging becomes harder because stack traces are async. If one SDK hangs, it blocks ALL other coroutines (no timeout works because the event loop is blocked). You get the worst of both worlds.

**Prevention:** Two viable approaches:
1. **`asyncio.to_thread()` (recommended for this codebase):** Wrap each synchronous ingest function in `asyncio.to_thread(_ingest_slack, ctx)`. This runs them in a ThreadPoolExecutor, giving true concurrency for I/O-bound SDK calls. No SDK changes needed.
2. **Native async clients:** `notion-client` has async mode (`AsyncClient`), `httpx` supports async, but `google-api-python-client` and `hubspot-api-client` are synchronous-only. You'd need to mix approaches anyway.

Use approach 1. It works with all existing synchronous code unchanged. The only async code is the orchestration layer.

**Detection:** If your `_ingest_*` functions are `async def` but contain no `await` statements (or only `await` sync SDK calls), you have this bug. Run with `PYTHONASYNCIODEBUG=1` to detect blocking calls.

**Phase:** Parallel ingest modules (asyncio)

### Pitfall 2: Structured Output Migration Breaks Existing Parsing Without Realizing It

**What goes wrong:** You migrate `synthesize_daily()` and `extract_meeting()` to use `output_config` with `json_schema`, but the downstream code that consumes their output (the template renderer, the sidecar writer, the quality tracker) still expects the old markdown-parsed format. The structured output returns a different shape than `_parse_synthesis_response()` was producing, and items silently go missing or render wrong.

**Why it happens:** The current pipeline has three Claude API call sites:
1. `extract_meeting()` in `extractor.py` -- returns `MeetingExtraction` via markdown section parsing
2. `synthesize_daily()` in `synthesizer.py` -- returns dict via `_parse_synthesis_response()` (markdown bullet parsing)
3. `extract_commitments()` in `commitments.py` -- already uses structured outputs

Each has bespoke markdown parsing (`_parse_section_items`, `_parse_legacy_blocks`, `_parse_synthesis_response`) that handles edge cases like "None." responses, pipe-delimited formats, bold-label formats, and table row parsing. The structured output migration eliminates all this parsing, but you must verify that the JSON schema produces output in exactly the same shape that downstream consumers expect.

**Consequences:** Commitments table renders empty. Substance items disappear. Sidecar JSON has wrong structure. Tests pass (they mock Claude responses) but production breaks.

**Prevention:**
- Define Pydantic models for each API call's output FIRST. The models define the contract.
- The `output_config` schema comes from `Model.model_json_schema()`.
- Write integration tests that compare structured output responses against the old parsed format for a set of real responses.
- Migrate one call site at a time: `extract_meeting()` first (simplest), then `synthesize_daily()` (most complex), keeping `extract_commitments()` as-is (already done).
- Keep the old parsing code behind a feature flag for one release cycle.

**Detection:** Regression test: run the pipeline on a known date with both old and new code paths, diff the output markdown files. Any missing sections = migration bug.

**Phase:** Structured output migration

### Pitfall 3: Notion API Version 2025-09-03 Breaking Changes Silently Ignored

**What goes wrong:** You build Notion ingestion against the pre-September-2025 API shape, using `database_id` directly in queries. It works initially. Then a user adds a second data source to a Notion database (a feature Notion shipped Sept 2025), and your `databases.query()` call starts returning validation errors because `database_id` is no longer sufficient -- you need `data_source_id`.

**Why it happens:** The Notion API version 2025-09-03 introduced multi-source databases. The Python SDK (`notion-client>=3.0.0`) supports the new `data_sources` endpoints, but if you're not explicitly using the 2025-09-03 API version header, you might be hitting the older API version. The breaking change: `database_id` alone is ambiguous when a database has multiple data sources.

**Consequences:** Ingestion silently fails or returns partial data. The pipeline's error handling (try/except in `_ingest_notion`) catches the error and logs a warning, so the pipeline "succeeds" but Notion data is missing. You don't notice until you realize Notion items never appear in summaries.

**Prevention:**
- Pin the Notion API version to `2025-09-03` explicitly in the client constructor: `Client(auth=token, notion_version="2025-09-03")`
- For simple page reading (your use case: recently edited pages via `search()` and block content via `blocks.children.list()`), the `data_source_id` change is LESS impactful -- it mainly affects `databases.query()`. But if you query databases for changed items, you need the discovery step.
- Use `notion.search()` with `filter={"property": "object", "value": "page"}` for page discovery (note: the 2025-09-03 version changed the filter value from `"database"` to `"data_source"` for database objects).
- Build a health check that verifies the integration can access expected pages/databases before the first real run.

**Detection:** Notion ingest returns 0 items on a day you know had Notion activity. Check API response error codes -- `validation_error` with message about `data_source_id` is the telltale sign.

**Phase:** Notion ingestion

### Pitfall 4: Asyncio Parallel Claude API Calls Hit Rate Limits

**What goes wrong:** After successfully parallelizing ingest with `asyncio.to_thread()`, you also parallelize `extract_all_meetings()` to run per-meeting extractions concurrently. With 8 meetings, 8 Claude API calls fire simultaneously. You hit Anthropic's rate limit (requests per minute or tokens per minute), get 429 errors, and extractions fail.

**Why it happens:** The current sequential `for event in events` loop in `extract_all_meetings()` naturally throttles to ~1 request at a time. Parallelizing removes this natural throttle. The Anthropic API has rate limits that depend on your tier.

**Consequences:** 429 errors. The `anthropic` SDK has built-in retry with exponential backoff, but when multiple tasks retry simultaneously, you get a thundering herd. Total wall-clock time may actually increase due to backoff stacking.

**Prevention:**
- Use `asyncio.Semaphore` to limit concurrent Claude API calls: `sem = asyncio.Semaphore(3)` (start conservative).
- Better: use the existing `anthropic.Anthropic()` client, which has built-in rate limit handling. Run extractions through `asyncio.to_thread()` with a semaphore, not raw `gather()`.
- Measure actual rate limits for your API tier before choosing concurrency. For Sonnet, typical limits are 50 RPM on the base tier, 1000 RPM on higher tiers.
- Log rate limit headers from responses (`x-ratelimit-limit-requests`, `x-ratelimit-remaining-requests`) to tune the semaphore value.

**Detection:** Multiple `429` errors in logs during extraction phase. Extraction phase takes longer than sequential despite being "parallel".

**Phase:** Parallel per-meeting extraction

### Pitfall 5: Pydantic Config Validation Rejects Existing Valid Configs

**What goes wrong:** You create a Pydantic `ConfigModel` that validates `config.yaml`. The model is stricter than the YAML has ever been -- missing optional sections become required fields, `enabled: false` sources still need all sub-fields present, and snake_case field names don't match YAML's conventions. Existing configs that worked fine now fail validation on startup.

**Why it happens:** Pydantic v2's default behavior is strict: `extra="forbid"` rejects unknown fields, required fields must be present, and type coercion is limited. Your existing `config.yaml` has grown organically and has inconsistencies (some sections present but empty, some absent entirely). The current `load_config()` handles this with `.get("key", {})` and `.setdefault()` calls. A Pydantic model doesn't tolerate this looseness.

**Consequences:** Pipeline won't start. User has to manually fix their config. If you ship this to yourself running on a cron job, it fails silently at 1am and you wake up with no daily summary.

**Prevention:**
- Make every field `Optional` with sensible defaults. The model should accept the MINIMALLY configured `config.yaml` (just `pipeline.timezone` and `calendars.ids`).
- Use `model_config = ConfigDict(extra="ignore")` initially, not `extra="forbid"`. Tighten later.
- Write the model to match EXACTLY what `load_config()` currently returns, including all the `.setdefault()` additions. Test by loading the actual production `config.yaml` through the new model.
- Apply env var overrides AFTER Pydantic validation, not before (so validation sees the YAML shape, not the merged shape).
- Add a `validate-config` CLI command that reports errors without crashing the pipeline.

**Detection:** The pipeline crashes on startup with `ValidationError` for a config that worked yesterday. Or worse: you test with a fresh config but your production config has fields the test config doesn't.

**Phase:** Typed config model (Pydantic validation)

## Moderate Pitfalls

### Pitfall 6: Cache Retention Policy Deletes Data Still Needed by Roll-ups

**What goes wrong:** You implement a TTL-based cache cleanup that deletes raw API response files older than N days. Then monthly roll-up synthesis fails because it reads daily sidecar JSONs (stored alongside raw data in `output/`) and some are gone.

**Why it happens:** The `output/` directory contains: `daily/` (final summaries), `raw/` (raw API responses and pre-edit snapshots), and `quality/` (quality tracking). The raw data and the processed output live in related but separate paths. A naive "delete anything in `output/raw/` older than 7 days" destroys data that monthly synthesis needs.

**Prevention:**
- Separate concerns: raw API cache (ephemeral, safe to delete) vs. processed output (permanent until explicitly archived).
- The TTL should ONLY apply to `output/raw/` subdirectories (calendar JSON responses, email HTML caches). Never to `output/daily/` (the summaries) or `output/quality/`.
- Set TTL >= 35 days minimum (monthly roll-ups need a full month of daily summaries). Better: only auto-delete raw cache, never auto-delete processed output.
- Implement as a separate `cleanup` CLI command, not an automatic step in the pipeline. Avoids accidental deletion during normal runs.

**Detection:** Monthly synthesis produces empty or partial results. `FileNotFoundError` in synthesis logs for daily files that should exist.

**Phase:** Cache retention policy

### Pitfall 7: Algorithmic Dedup Produces False Positives on Short Text

**What goes wrong:** You build algorithmic dedup using text similarity (cosine similarity, Jaccard, or fuzzy string matching) to supplement the LLM-based dedup in synthesis prompts. Two Slack messages "Launch pushed to Q3" and "Launch readiness review" get similarity score 0.7 and are merged. They were about different launches.

**Why it happens:** Work intelligence items are SHORT (1-3 sentences). Short texts have high similarity scores by accident because a few shared words dominate the similarity calculation. "Launch" and "Q3" appear in many unrelated items. Traditional text similarity works well on documents (hundreds of words) but poorly on bullets.

**Consequences:** Distinct items merged, losing information. Worse than no dedup -- the user sees a merged item and doesn't realize a separate event was dropped.

**Prevention:**
- Algorithmic dedup should be CONSERVATIVE. Only merge items that match on multiple signals:
  1. Source overlap (same event referenced from two sources)
  2. Time proximity (within 2 hours)
  3. Entity overlap (same people mentioned)
  4. High text similarity threshold (>= 0.85 for short text)
- Use it as a PRE-FILTER for the LLM dedup, not a replacement. Flag likely duplicates for the synthesis prompt to confirm: "These items may be duplicates: [A] and [B]. Merge if they refer to the same event."
- Never auto-merge without at least two matching signals. The existing LLM-based dedup in synthesis prompts is the safety net.

**Detection:** Output contains items that clearly reference different events but were merged. Or: items that were separate in v1.5 start appearing merged in v1.5.1.

**Phase:** Algorithmic cross-source deduplication

### Pitfall 8: Notion Block Pagination Drops Content from Long Pages

**What goes wrong:** `blocks.children.list()` returns paginated results (max 100 blocks per call). You fetch the first page and forget to follow `next_cursor`. A long Notion page (100+ blocks) has its bottom half silently truncated.

**Why it happens:** The Notion API paginates block children at 100 items. Unlike the `search()` endpoint (where you're likely to notice missing results), block pagination silently returns partial content that LOOKS complete -- you get the top of the page, which often has enough context to seem like the full page.

**Consequences:** Content from the bottom of Notion pages is missing from synthesis. Items discussed at the bottom of meeting notes or project pages are never surfaced.

**Prevention:**
- Use `notion_client.helpers.collect_paginated_api(notion.blocks.children.list, block_id=page_id)` which handles cursor following automatically.
- Or implement a pagination loop: `while has_more: results = notion.blocks.children.list(block_id=page_id, start_cursor=next_cursor)`.
- Also handle NESTED blocks (e.g., toggle blocks with children, column blocks). Each child block with `has_children=True` requires a separate `blocks.children.list()` call. Budget API calls accordingly against the 3 req/s rate limit.
- Set a depth limit (2-3 levels) to avoid recursive descent into deeply nested Notion pages.

**Detection:** Compare Notion page word count in the app vs. extracted text length. If extracted is <50% of visible content, pagination is broken.

**Phase:** Notion ingestion

### Pitfall 9: Mixing `asyncio.run()` with Existing Synchronous Entry Points

**What goes wrong:** The pipeline's entry point in `src/main.py` is synchronous. You add `asyncio.run(run_pipeline_async(ctx))` inside it. This works. Then someone (or a test) calls `run_pipeline` from within an already-running event loop (e.g., from a Jupyter notebook, or from a test framework that uses `pytest-asyncio`). `asyncio.run()` raises `RuntimeError: This event loop is already running`.

**Why it happens:** `asyncio.run()` creates a new event loop and runs until complete. It cannot be called from within an existing event loop. This is a fundamental constraint of Python's asyncio.

**Consequences:** Tests break. Interactive debugging breaks. Any future integration that embeds the pipeline in a larger async application breaks.

**Prevention:**
- Keep the public API synchronous. `run_pipeline(ctx)` stays `def`, not `async def`.
- Inside `run_pipeline()`, use `asyncio.run(_run_pipeline_async(ctx))` as the bridge.
- The `_run_pipeline_async()` function is private and handles the gather/thread orchestration.
- For tests: mock at the ingest function level, not the asyncio level. Tests should not need to know the pipeline uses asyncio internally.
- If you need to support already-running loops in the future, use `loop.run_in_executor()` or `nest_asyncio` as an escape hatch (but don't add it preemptively).

**Detection:** `RuntimeError: This event loop is already running` in tests or interactive sessions.

**Phase:** Parallel ingest modules (asyncio)

### Pitfall 10: Structured Output Schemas Reject Valid Claude Responses Due to Schema Strictness

**What goes wrong:** You define a JSON schema with `"additionalProperties": false` and required fields. Claude's constrained decoding guarantees schema compliance, BUT your schema doesn't account for edge cases: empty days (no items), partial data (one source failed), or the "No items for this day" case. The schema requires `items` to be a non-empty array, but the model wants to return an empty array and can't.

**Why it happens:** Schema design optimized for the happy path. The current markdown parsing handles "None." and empty sections gracefully via special-case string checks. When you convert to JSON schema, you need to explicitly allow empty arrays, null fields, and optional sections.

**Consequences:** Claude API returns an error or the model produces malformed output trying to satisfy an impossible schema constraint. Pipeline fails on quiet days with few meetings.

**Prevention:**
- All array fields should allow empty: `"items": {"type": "array", "items": {...}}` (arrays are empty by default in JSON Schema).
- Use `Optional` / nullable for fields that may not exist: executive_summary is null on days with <5 meetings.
- Generate schemas from Pydantic models with `Optional` types and `default_factory=list` -- these naturally produce permissive schemas.
- Test with edge cases: zero meetings, zero Slack items, all sources failed, only one source has data.
- The existing `commitments.py` already does this correctly -- use it as the template for the other migrations.

**Detection:** `BadRequestError` from Claude API with schema validation details. Or: Claude returns minimum-viable JSON that technically satisfies the schema but has wrong data (model was "forced" into an output shape that didn't fit the content).

**Phase:** Structured output migration

## Minor Pitfalls

### Pitfall 11: Notion Rate Limit Causes Timeout on Large Workspaces

**What goes wrong:** With 50+ recently edited pages, fetching block content for each at 3 req/s (plus nested block fetches) takes 30+ seconds. If the pipeline has a timeout, Notion ingestion gets killed.

**Prevention:** Limit pages processed per run (e.g., `max_pages_per_day: 20` in config). Sort by `last_edited_time` descending and take the most recent. Log skipped pages so the user knows.

**Phase:** Notion ingestion

### Pitfall 12: Slack Batch User Resolution Returns Paginated Results

**What goes wrong:** `users.list()` for batch user ID resolution returns paginated results. Large workspaces (1000+ members) require multiple pages. You fetch page 1 and build a name cache, then user IDs from later pages resolve to "Unknown User".

**Prevention:** Use the SDK's built-in pagination or cursor following: `slack_client.users_list(limit=200)` in a loop following `response_metadata.next_cursor`. Or: use `users.info()` for the small set of user IDs actually seen in today's messages (likely <50 unique users) rather than downloading the entire roster.

**Phase:** Slack user batch resolution

### Pitfall 13: Config Validation Model Diverges from Actual Config Over Time

**What goes wrong:** The Pydantic config model is created once and never updated when new config fields are added (e.g., Notion-specific settings). New fields get silently ignored (`extra="ignore"`) or cause validation errors (`extra="forbid"`).

**Prevention:** Add a CI check: load the actual `config/config.yaml` through the Pydantic model in tests. Any field present in YAML but not in the model triggers a test failure. This forces the model and the YAML to stay in sync.

**Phase:** Typed config model

### Pitfall 14: Parallel Ingest Error Isolation Is Harder Than Sequential

**What goes wrong:** In the current sequential code, if Slack ingestion fails, the except clause logs a warning and continues to HubSpot. With `asyncio.gather()`, if you use `return_exceptions=False` (the default), ONE source failure cancels all pending tasks. You lose all data, not just the failing source.

**Prevention:** Always use `asyncio.gather(*tasks, return_exceptions=True)`. Then check each result: if it's an Exception, log it and use empty data. This preserves the current "one source failure doesn't block others" behavior.

**Detection:** All sources return empty when only one source has an API issue.

**Phase:** Parallel ingest modules (asyncio)

### Pitfall 15: Notion Search API Returns Stale Results

**What goes wrong:** The `notion.search()` endpoint has eventual consistency -- recently edited pages may not appear in search results for several minutes. If the pipeline runs at 11:59 PM for "today's" data, edits from 11:55 PM may be missed.

**Prevention:** This is a known Notion API limitation. Accept it. For a daily batch running after end-of-day, the lag is negligible. If you need guaranteed freshness, query specific known page IDs directly via `pages.retrieve()` and check `last_edited_time` rather than relying on `search()`.

**Phase:** Notion ingestion

## Integration Pitfalls

These pitfalls arise from the interaction between multiple features being added simultaneously.

### Integration Pitfall 1: Asyncio + Structured Outputs = Double Migration Risk

**What goes wrong:** You change the pipeline from sequential-sync to parallel-async AND simultaneously change API responses from markdown to JSON. When something breaks, you can't tell which change caused it.

**Prevention:** Migrate in strict order:
1. First: structured output migration (change API response format, keep sequential execution)
2. Then: asyncio parallelization (change execution model, keep new API response format)

Never change the execution model and the data format in the same phase. Each is independently testable.

### Integration Pitfall 2: Config Validation + New Notion Config = Chicken-and-Egg

**What goes wrong:** You add Pydantic config validation. Then you add Notion ingestion, which needs new config fields (`notion.enabled`, `notion.page_ids`, `notion.databases`). The Pydantic model doesn't know about Notion fields yet, so either (a) Notion config is rejected, or (b) you have to update the model and the Notion code simultaneously.

**Prevention:** Add Notion config fields to the Pydantic model BEFORE implementing Notion ingestion. The model can define the schema with defaults (`enabled: false`) before any code reads from it. Order: config model -> notion config schema -> notion ingestion code.

### Integration Pitfall 3: Cache Retention + Notion Raw Data = New Cache Category

**What goes wrong:** Cache retention policy is designed for Google Calendar JSON and email HTML. Notion raw data (block content) has a different shape, different size profile, and different retention needs. The cache cleanup doesn't know about Notion data and either skips it (leak) or deletes it wrongly.

**Prevention:** Design the cache retention system to be source-aware from day one. Each source registers its cache directory and its retention policy. Don't hardcode paths.

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Severity | Mitigation |
|-------------|---------------|----------|------------|
| Notion ingestion | API version 2025-09-03 breaking changes (#3) | Critical | Pin API version, handle data_source_id for database queries |
| Notion ingestion | Block pagination drops content (#8) | Moderate | Use `collect_paginated_api` helper, handle nested blocks |
| Notion ingestion | Search eventual consistency (#15) | Minor | Accept for daily batch; query known pages directly if needed |
| Notion ingestion | Rate limit timeout (#11) | Minor | Cap pages per run, budget API calls |
| Asyncio parallelization | Sync SDKs block event loop (#1) | Critical | Use `asyncio.to_thread()`, not `async def` wrappers |
| Asyncio parallelization | Claude rate limits under concurrency (#4) | Critical | Semaphore on concurrent API calls |
| Asyncio parallelization | `asyncio.run()` from existing loop (#9) | Moderate | Keep public API synchronous, async is internal |
| Asyncio parallelization | Error isolation in gather (#14) | Moderate | `return_exceptions=True` always |
| Structured output migration | Downstream parsing mismatch (#2) | Critical | Migrate one call site at a time, regression test output |
| Structured output migration | Schema rejects edge cases (#10) | Moderate | Allow empty arrays, Optional fields, test empty-day cases |
| Config validation | Rejects existing configs (#5) | Critical | All Optional with defaults, `extra="ignore"`, test production config |
| Config validation | Model diverges over time (#13) | Minor | CI test loading actual config through model |
| Cache retention | Deletes data needed by roll-ups (#6) | Moderate | Only delete raw cache, never processed output, TTL >= 35 days |
| Algorithmic dedup | False positives on short text (#7) | Moderate | Require multiple matching signals, high threshold, use as pre-filter not replacement |
| Slack batch resolution | Paginated user list (#12) | Minor | Follow cursor or resolve only seen user IDs |

## Recommended Phase Order (Based on Pitfall Dependencies)

1. **Typed config model** -- Foundation. Do first so all subsequent features add config fields to a validated model.
2. **Structured output migration** -- Changes data format. Do before asyncio so you only change one thing at a time (Integration Pitfall 1).
3. **Notion ingestion** -- New source. Adds config, adds cache, adds to pipeline. Depends on config model existing.
4. **Asyncio parallelization** -- Changes execution model. Do after all sources exist and structured outputs are stable.
5. **Algorithmic dedup** -- Supplements existing LLM dedup. Can be done any time but benefits from all sources being present.
6. **Cache retention + Slack batch resolution** -- Cleanup and optimization. Low-risk, do last.

## Sources

- [Python asyncio official docs -- Developing with asyncio](https://docs.python.org/3/library/asyncio-dev.html)
- [BBC -- Mixing Synchronous and Asynchronous Code](https://bbc.github.io/cloudfit-public-docs/asyncio/asyncio-part-5.html)
- [Anthropic -- Structured Outputs docs (GA)](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) -- Confirms `output_config.format` is GA, `output_format` is deprecated transition
- [Notion API -- Upgrade Guide 2025-09-03](https://developers.notion.com/docs/upgrade-guide-2025-09-03) -- Breaking changes for data_source_id
- [Notion API -- Upgrade FAQs 2025-09-03](https://developers.notion.com/docs/upgrade-faqs-2025-09-03)
- [notion-sdk-py GitHub](https://github.com/ramnes/notion-sdk-py) -- Python SDK with data_sources support
- [Notion API -- Request Limits](https://developers.notion.com/reference/request-limits) -- 3 req/s rate limit
- [Pydantic -- Settings Management](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) -- Config validation patterns
- [Pydantic -- Validation Errors](https://docs.pydantic.dev/latest/errors/validation_errors/)
- Codebase inspection: `src/pipeline.py`, `src/config.py`, `src/synthesis/extractor.py`, `src/synthesis/synthesizer.py`, `src/synthesis/commitments.py`, `config/config.yaml`
