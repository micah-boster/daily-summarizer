# Codebase Concerns

**Analysis Date:** 2026-04-04

## Tech Debt

**Monolithic `run_daily()` function:**
- Issue: `src/main.py` `run_daily()` is ~330 lines with deeply nested try/except blocks, inline imports, and sequential orchestration of 6+ data sources. Every ingest module, synthesis stage, quality tracker, sidecar writer, and notification call is wired inline.
- Files: `src/main.py` lines 120-453
- Impact: Adding a new data source requires editing this function in multiple places. Hard to test the orchestration logic in isolation. A failure in quality tracking code could mask errors in the synthesis pipeline due to exception nesting.
- Fix approach: Extract an orchestrator class or pipeline runner that accepts a list of ingest modules and runs them through a standard interface. Each ingest module already returns `list[SourceItem]` -- formalize this with a protocol and loop.

**Inline/deferred imports throughout `run_daily()`:**
- Issue: Many imports happen inside `try` blocks within `run_daily()` (e.g., `from src.synthesis.extractor import extract_all_meetings` at line 289, `from src.quality import detect_edits` at line 393). This hides import errors until runtime and makes dependency tracking difficult.
- Files: `src/main.py` lines 135-143, 177-179, 219-220, 233-234, 289, 305-306, 367, 393, 422, 431, 443
- Impact: A broken import in any module silently degrades the pipeline to a partial run. Import errors look like runtime failures in logs.
- Fix approach: Move all imports to module level. Use feature flags (config `enabled` checks) to skip execution, not import gating.

**New Anthropic client instantiated per API call:**
- Issue: Every function that calls the Claude API creates a fresh `anthropic.Anthropic()` client: `src/synthesis/extractor.py` line 240, `src/synthesis/synthesizer.py` line 517, `src/synthesis/commitments.py` line 97, `src/synthesis/weekly.py` line 470, `src/synthesis/monthly.py` line 395. This means a new HTTP connection pool per call.
- Files: `src/synthesis/extractor.py`, `src/synthesis/synthesizer.py`, `src/synthesis/commitments.py`, `src/synthesis/weekly.py`, `src/synthesis/monthly.py`
- Impact: Wasted TCP connections. For a day with 8 meetings, that is at least 10 separate client instantiations (8 extraction + 1 synthesis + 1 commitment extraction). Minor overhead per call but unnecessary.
- Fix approach: Create the Anthropic client once in the pipeline runner and pass it through, or use a module-level singleton.

**Module-level mutable caches in Slack ingest:**
- Issue: `src/ingest/slack.py` uses module-level dicts `_user_cache` and `_channel_name_cache` (lines 25-28). `src/ingest/google_docs.py` uses `_user_email_cache` (line 24). These persist across calls within a process and are not cleared between runs.
- Files: `src/ingest/slack.py` lines 25-28, `src/ingest/google_docs.py` line 24
- Impact: If the module is imported in a long-running process or test suite, stale data accumulates. Not currently a problem for the batch-and-exit model, but will break if the pipeline moves to a daemon/server model.
- Fix approach: Move caches into the client/session object, or add explicit cache-clear functions called at pipeline start.

**`uv.lock` in `.gitignore`:**
- Issue: The lockfile is gitignored (`.gitignore` line 15: `uv.lock`). Dependencies in `pyproject.toml` use minimum version pins (`>=`) with no upper bounds.
- Files: `.gitignore` line 15, `pyproject.toml` lines 6-20
- Impact: Builds are not reproducible. A `uv sync` on a new machine may pull different dependency versions. The `hubspot-api-client`, `slack-sdk`, and `anthropic` packages all have breaking changes between major versions, and `>=` pins will not protect against them.
- Fix approach: Remove `uv.lock` from `.gitignore` and commit it. Optionally, add upper-bound pins on critical dependencies (e.g., `anthropic>=0.45.0,<1.0`).

## Known Bugs

**Slack ingestion uses stale timestamps across date ranges:**
- Symptoms: When running `daily --from 2026-03-01 --to 2026-03-31`, Slack ingestion always fetches from the last-saved cursor timestamp, not relative to the target date being processed. The date loop iterates `current`, but Slack fetch uses `datetime.now(timezone.utc)` as `now_ts` and the saved `last_ts` state.
- Files: `src/main.py` lines 171-213, `src/ingest/slack.py` lines 420-421
- Trigger: Run daily pipeline for a past date range.
- Workaround: Only run daily for today's date, or run Slack ingestion separately.

**`creds` variable referenced before assignment when Google auth unavailable:**
- Symptoms: If the initial credential loading in `run_daily()` raises (line 166 `except` catches it), `creds` is never assigned. Later code at line 219 (`if docs_config.get("enabled", False) and creds is not None`) will raise `NameError: name 'creds' is not defined`.
- Files: `src/main.py` line 219
- Trigger: Google auth fails with an exception (not just missing credentials, but an actual import or network error).
- Workaround: None automatic. The outer `try/except` on line 450 catches it, but the error message will be misleading.

**HubSpot owner resolution assumes first owner is "me":**
- Symptoms: The `_resolve_owner_id()` function (lines 127-137 in `src/ingest/hubspot.py`) with `scope="mine"` returns `owners.results[0].id` -- the first owner returned by the API, not necessarily the authenticated user. HubSpot private app tokens do not have a "current user" concept.
- Files: `src/ingest/hubspot.py` lines 127-137
- Trigger: Use `ownership_scope: "mine"` (the default) with a HubSpot account that has multiple owners.
- Workaround: Set `ownership_scope` to a specific owner ID in `config/config.yaml`.

## Security Considerations

**Credential files stored in plaintext on disk:**
- Risk: `.credentials/token.json` and `.credentials/client_secret.json` contain Google OAuth tokens and client secrets. They are gitignored but stored as plain JSON on the local filesystem with standard file permissions.
- Files: `src/auth/google_oauth.py` lines 19-21, `.credentials/` directory
- Current mitigation: `.gitignore` excludes `.credentials/` and `.env`.
- Recommendations: Set restrictive file permissions (0600) on token files. Consider using OS keychain (macOS Keychain, etc.) for token storage instead of plaintext JSON.

**API keys loaded from environment with no validation:**
- Risk: `ANTHROPIC_API_KEY`, `SLACK_BOT_TOKEN`, `HUBSPOT_ACCESS_TOKEN`, and `SLACK_WEBHOOK_URL` are read from environment variables via `os.environ.get()` with no format validation. A malformed or partial key will produce unhelpful downstream errors.
- Files: `src/ingest/slack.py` line 43, `src/ingest/hubspot.py` line 37, `src/notifications/slack.py` line 20, `.env.example`
- Current mitigation: Individual modules raise `ValueError` for missing tokens, but not for invalid ones.
- Recommendations: Add a startup preflight check that validates required env vars exist and have expected prefixes (e.g., `sk-ant-` for Anthropic, `xoxb-` for Slack).

**Webhook URL read at module import time:**
- Risk: `src/notifications/slack.py` line 20 reads `SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")` at import time. If `.env` is loaded after import, the value will be empty. The `send_slack_summary()` function has a fallback re-read at line 279, but `notify_slack()` does not.
- Files: `src/notifications/slack.py` lines 20, 35-36 vs 279
- Current mitigation: `dotenv` is loaded at the top of `src/main.py` before any other imports when run as the main entry point.
- Recommendations: Always read env vars at call time, not module import time.

**Raw API responses cached to disk include sensitive data:**
- Risk: `cache_raw_response()` and `cache_raw_emails()` write full API responses to `output/raw/` as JSON. Calendar events may include attendee emails, descriptions with sensitive content, and full email bodies. This data persists on disk indefinitely.
- Files: `src/ingest/calendar.py` lines 260-289, `src/ingest/gmail.py` lines 230-263
- Current mitigation: `output/` is gitignored.
- Recommendations: Add a retention policy that auto-deletes raw caches older than N days. Consider whether full email bodies need to be cached.

## Performance Bottlenecks

**Sequential API calls for per-meeting extraction:**
- Problem: `extract_all_meetings()` in `src/synthesis/extractor.py` calls the Claude API sequentially for each meeting with a transcript. A day with 8 meetings means 8 sequential API calls (plus 1 synthesis + 1 commitment extraction = 10 total Claude calls).
- Files: `src/synthesis/extractor.py` lines 275-314
- Cause: Simple `for` loop with no parallelism. Each call waits for the previous to complete.
- Improvement path: Use `asyncio` with `anthropic.AsyncAnthropic` to parallelize extraction calls. Meetings are independent -- all can be extracted concurrently. Expected speedup: 3-5x for busy days.

**Sequential ingest modules with no parallelism:**
- Problem: In `run_daily()`, Calendar, Slack, Google Docs, and HubSpot ingestion run sequentially. Each involves network I/O to different APIs.
- Files: `src/main.py` lines 170-241
- Cause: Straightforward sequential code.
- Improvement path: Use `concurrent.futures.ThreadPoolExecutor` or `asyncio` to run independent ingest modules in parallel. Calendar+transcripts are dependent (transcripts match to events), but Slack, Docs, and HubSpot are fully independent.

**Slack user name resolution is one-at-a-time:**
- Problem: `resolve_user_names()` makes one API call per unique user ID (`client.users_info(user=uid)` at line 74). For a busy channel with 20 unique users, that is 20 sequential HTTP calls.
- Files: `src/ingest/slack.py` lines 54-90
- Cause: Slack API `users_info` only accepts a single user ID. No batch endpoint available for individual lookups.
- Improvement path: Use `client.users_list()` to fetch all workspace users in one call and build the cache from that. This trades one large response for N small ones.

**HubSpot fetches pipeline stages and owner list on every run:**
- Problem: `fetch_hubspot_items()` calls `_build_stage_map()`, `_build_ticket_stage_map()`, and `_build_owner_map()` every time. These are reference data that rarely change.
- Files: `src/ingest/hubspot.py` lines 546-549
- Cause: No caching of lookup data.
- Improvement path: Cache pipeline stage maps and owner maps to a local file with a TTL (e.g., 24 hours). Refresh only when stale.

**Transcript matching is O(T*E) with SequenceMatcher:**
- Problem: `match_transcript_to_event()` in `src/ingest/normalizer.py` uses `difflib.SequenceMatcher` to compute title similarity for every (transcript, event) pair. SequenceMatcher is O(n*m) for string length. For T transcripts and E events, total work is O(T * E * title_length^2).
- Files: `src/ingest/normalizer.py` lines 32-80
- Cause: Brute-force matching approach.
- Improvement path: Not a real problem at current scale (typically <20 events and <10 transcripts per day). Only optimize if data volumes grow significantly.

## Fragile Areas

**Markdown response parsing in synthesis modules:**
- Files: `src/synthesis/extractor.py` lines 25-129, `src/synthesis/synthesizer.py` lines 338-421, `src/synthesis/weekly.py` lines 210-401, `src/synthesis/monthly.py` lines 211-345
- Why fragile: All Claude API responses are parsed by regex/string-splitting on markdown headers (`## `, `### `, `- `, `|`). If Claude changes its output format even slightly (extra newline, different header casing, missing section), parsing silently returns empty results.
- Safe modification: Add unit tests with varied response formats. Consider switching to Claude's structured output (JSON schema) for extraction and synthesis, as is already done for commitment extraction in `src/synthesis/commitments.py`.
- Test coverage: Basic happy-path tests exist in `tests/test_extractor.py`, `tests/test_synthesizer.py`. No tests for malformed/unexpected Claude responses.

**Weekly/monthly file reading relies on strict directory/naming conventions:**
- Files: `src/synthesis/weekly.py` lines 124-163, `src/synthesis/monthly.py` lines 53-86
- Why fragile: Weekly synthesis reads daily `.md` files at exact paths (`output/daily/YYYY/MM/YYYY-MM-DD.md`). Monthly reads weekly files at `output/weekly/YYYY/YYYY-WXX.md`. If the writer changes its path structure, the readers silently find no files.
- Safe modification: Extract path computation into a shared utility. Never change path patterns without updating both writer and reader.
- Test coverage: No integration tests that verify writer output can be read by reader.

**Slack state cursor management:**
- Files: `src/ingest/slack.py` lines 93-121, 496-501
- Why fragile: Slack ingestion uses `last_ts` cursors stored in `config/slack_state.json` to avoid re-fetching messages. If this file is deleted, corrupted, or the format changes, the module falls back to a 24-hour lookback. If the cursor advances past messages that were never successfully processed (e.g., due to a crash mid-run), those messages are permanently skipped.
- Safe modification: Always update the cursor only after all messages for a channel have been successfully processed. Consider adding a "high-water mark" with replay capability.
- Test coverage: `tests/test_slack_ingest.py` exists but cursor edge cases are not covered.

## Scaling Limits

**Claude API token limits for synthesis:**
- Current capacity: The synthesis prompt includes all meeting extractions, Slack items, docs items, and HubSpot items in a single prompt. With `synthesis_max_output_tokens: 8192` and the full extraction text for 10+ meetings plus 100 Slack messages, the input can exceed context window limits.
- Limit: No explicit input token counting or truncation. If the combined prompt exceeds the model's context window, the API call will fail.
- Scaling path: Add input token estimation (using `anthropic.count_tokens()` or character heuristics). If over budget, truncate older/lower-priority items, or split into multiple synthesis calls with a final merge step.

**Raw data cache grows unbounded:**
- Current capacity: Every daily run caches raw calendar JSON, email JSON, and transcript data to `output/raw/YYYY/MM/DD/`. No cleanup mechanism.
- Limit: Over months, this can grow to gigabytes (especially with full email bodies cached).
- Scaling path: Add a retention policy (configurable, e.g., 30 days). Run cleanup as part of the pipeline, or as a separate maintenance command.

**Quality metrics JSONL grows forever:**
- Current capacity: `output/quality/metrics.jsonl` appends one entry per daily run, read in full on every run to regenerate the report.
- Limit: After years of daily runs, the file read becomes slow and the report includes ancient data.
- Scaling path: Rotate or truncate the JSONL file. Limit report generation to last N entries.

## Dependencies at Risk

**`hubspot-api-client` (12.0.0):**
- Risk: HubSpot's Python SDK has a history of breaking changes between major versions. The code uses internal APIs like `client.crm.objects.notes.search_api.do_search()` which are not part of a stable public interface.
- Impact: A minor version bump could break all HubSpot ingestion.
- Migration plan: Pin to `hubspot-api-client>=12.0.0,<13.0.0`. Add integration tests that verify the SDK calls work against a mock.

**`anthropic` (0.45.0+):**
- Risk: The structured output API used in `src/synthesis/commitments.py` already has a fallback for SDK version differences (lines 109-137). The SDK is evolving rapidly; `output_config` parameter names may change.
- Impact: Claude API calls are the core of the pipeline. A breaking SDK change halts all synthesis.
- Migration plan: Pin to `anthropic>=0.45.0,<1.0.0`. The fallback pattern in commitments.py is good -- apply the same pattern to other Claude calls if needed.

**Google API client libraries (multiple):**
- Risk: `google-api-python-client`, `google-auth`, `google-auth-oauthlib`, and `google-auth-httplib2` are all pinned with `>=` only. These libraries occasionally deprecate features across versions.
- Impact: Calendar, Gmail, Drive, and Docs ingestion all depend on these.
- Migration plan: Commit `uv.lock` and add upper-bound pins.

## Missing Critical Features

**No retry/backoff on external API calls:**
- Problem: Calendar, Gmail, Drive, Docs, and HubSpot API calls have no retry logic. Only the Slack SDK has built-in rate-limit retries (`RateLimitErrorRetryHandler` in `src/ingest/slack.py` line 50). Claude API calls have no retries at all.
- Blocks: Any transient network error or rate limit from Google/Anthropic/HubSpot APIs causes that data source to be skipped for the day with only a warning log.
- Files: `src/ingest/calendar.py`, `src/ingest/gmail.py`, `src/ingest/drive.py`, `src/ingest/google_docs.py`, `src/ingest/hubspot.py`, `src/synthesis/extractor.py`, `src/synthesis/synthesizer.py`

**No input token counting before Claude API calls:**
- Problem: The pipeline builds arbitrarily large prompts (all extractions + Slack + Docs + HubSpot text) and sends them to Claude without checking if they fit within the model's context window.
- Blocks: Days with heavy activity (many meetings, busy Slack channels, many doc edits) can produce prompts that exceed context limits, causing the synthesis call to fail.
- Files: `src/synthesis/synthesizer.py` lines 424-548

**No idempotency guarantee for daily pipeline:**
- Problem: Re-running the daily pipeline for the same date overwrites output files and double-appends to the quality metrics JSONL. Slack state cursors advance on each run, so re-running may miss messages fetched in the first run but not processed.
- Blocks: Cannot safely re-run the pipeline to fix issues without side effects.
- Files: `src/main.py`, `src/quality.py` lines 148-151, `src/ingest/slack.py` lines 496-501

## Test Coverage Gaps

**No integration tests for end-to-end pipeline:**
- What's not tested: The `run_daily()`, `run_weekly()`, and `run_monthly()` functions in `src/main.py` have no test coverage. The complex orchestration logic, exception handling paths, and data flow between modules are untested.
- Files: `src/main.py`
- Risk: Regressions in the wiring between modules go undetected. The deeply nested try/except blocks mean partial failures are invisible.
- Priority: High

**Claude API response parsing not tested with edge cases:**
- What's not tested: Parsers in `src/synthesis/extractor.py`, `src/synthesis/synthesizer.py`, `src/synthesis/weekly.py`, and `src/synthesis/monthly.py` are tested only with well-formed mock responses. No tests for empty responses, malformed markdown, missing sections, or unexpected section names.
- Files: `tests/test_extractor.py`, `tests/test_synthesizer.py`, `tests/test_weekly.py`, `tests/test_monthly.py`
- Risk: Production Claude responses are nondeterministic. A slightly different format could silently produce empty synthesis.
- Priority: High

**No tests for multi-day date range execution:**
- What's not tested: The `while current <= to_date` loop in `run_daily()` with date ranges spanning multiple days, including error recovery when one day fails mid-pipeline.
- Files: `src/main.py` lines 169-453
- Risk: A failure on day 3 of a 30-day backfill could corrupt state (e.g., Slack cursors) for subsequent days.
- Priority: Medium

**HubSpot deduplication logic untested in real scenarios:**
- What's not tested: `_dedup_hubspot_items()` in `src/synthesis/synthesizer.py` uses fuzzy time-bucket matching to skip HubSpot meetings/emails that overlap with calendar events. No tests verify this works with real-world data shapes.
- Files: `src/synthesis/synthesizer.py` lines 279-335
- Risk: Either too aggressive (removes valid HubSpot items) or too passive (lets duplicates through).
- Priority: Medium

**Google Docs ingestion comment pagination untested:**
- What's not tested: The nested pagination loop in `_build_comment_items()` (`src/ingest/google_docs.py` lines 283-358) that fetches comments, filters by date, and expands replies.
- Files: `tests/test_google_docs.py`, `src/ingest/google_docs.py`
- Risk: A doc with hundreds of comments could trigger unexpected behavior.
- Priority: Low

---

*Concerns audit: 2026-04-04*
