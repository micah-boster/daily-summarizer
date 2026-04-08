# Domain Pitfalls: v3.0 Web Interface

**Domain:** Adding Next.js + FastAPI web layer to existing Python CLI pipeline (SQLite + flat files + async)
**Researched:** 2026-04-08
**Overall confidence:** HIGH (verified against codebase patterns, SQLite documentation, FastAPI documentation, community issue reports)

## Critical Pitfalls

Mistakes that cause rewrites, data corruption, or major architectural problems.

### Pitfall 1: SQLite "Database Is Locked" Under Concurrent Web Requests

**What goes wrong:** The existing pipeline uses a single `sqlite3.Connection` per `EntityRepository` instance. When FastAPI serves concurrent requests -- each potentially reading/writing entities -- multiple threads hit `entities.db` simultaneously. Even with WAL mode (already enabled in `db.py`), SQLite allows only one writer at a time. Without `busy_timeout`, concurrent writes fail *instantly* with `SQLITE_BUSY` instead of retrying.

**Why it happens:** The CLI only ever has one process and one thread accessing the database. The transition to web means N concurrent request handlers all touching `entities.db`. The current `get_connection()` in `src/entity/db.py` sets WAL and foreign keys but has NO `busy_timeout` pragma. Additionally, Python's `sqlite3` module defaults to `check_same_thread=True`, which will raise `ProgrammingError` if a connection created in one thread is used in another -- a near certainty with FastAPI's thread pool.

**Consequences:** Sporadic 500 errors on entity CRUD. Worse during pipeline runs (entity discovery writes while API reads). Errors appear under light load -- just 2-3 concurrent requests is enough to trigger.

**Prevention:**
1. Add `PRAGMA busy_timeout=5000` to `get_connection()` immediately -- single highest-impact one-line fix
2. Use connection-per-request pattern: FastAPI dependency that creates a fresh connection, yields it, and closes it after the request. Do NOT share a single `EntityRepository` across threads
3. For write operations, use `BEGIN IMMEDIATE` to acquire the write lock upfront rather than upgrading mid-transaction (upgrading causes unrecoverable `SQLITE_BUSY` even WITH `busy_timeout`)
4. Keep API writes fast -- entity CRUD is simple INSERTs/UPDATEs, not multi-second transactions

**Detection:** Any "OperationalError: database is locked" in logs, or `ProgrammingError` about same thread.

**Sources:**
- [SQLite concurrent writes and "database is locked" errors](https://tenthousandmeters.com/blog/sqlite-concurrent-writes-and-database-is-locked-errors/)
- [SQLite WAL documentation](https://www.sqlite.org/wal.html)
- [Is check_same_thread=False Safe?](https://github.com/fastapi/fastapi/discussions/5199)
- Current codebase: `src/entity/db.py` lines 38-42 (WAL enabled, no busy_timeout)

---

### Pitfall 2: Pipeline Run Blocks the Entire FastAPI Server

**What goes wrong:** The existing `run_pipeline()` is synchronous and calls `asyncio.run()` internally to wrap `async_pipeline()`. A pipeline run takes 30-120+ seconds (API calls to Gmail, Slack, HubSpot, Claude). If triggered from a FastAPI endpoint, it either: (a) crashes with `RuntimeError: This event loop is already running` if called from an async handler, or (b) occupies a thread pool worker for minutes if wrapped in `to_thread()`, starving other sync endpoints.

**Why it happens:** FastAPI runs on uvicorn's asyncio event loop. `asyncio.run()` tries to create a NEW event loop -- calling it inside an already-running loop is a hard error, not a performance issue. Even running in a thread pool only masks the problem: a 2-minute pipeline run consumes one of the limited workers.

**Consequences:** All API requests hang while the pipeline runs. The browser shows the app as frozen. If the HTTP client times out (typically 30-60s), the user sees an error while the pipeline continues running silently.

**Prevention:**
1. Pipeline runs MUST be fire-and-forget background jobs with status tracking
2. Create a `pipeline_runs` table: `(run_id, status, started_at, completed_at, error, target_date)`
3. API pattern: `POST /api/pipeline/run` returns `202 Accepted` with a `run_id`. Frontend polls `GET /api/pipeline/runs/{run_id}` for status
4. Run the pipeline in a subprocess (`subprocess.Popen` or `asyncio.create_subprocess_exec`) for true isolation -- pipeline crash cannot take down the web server
5. Alternative: refactor `async_pipeline()` to be a standalone coroutine (remove internal `asyncio.run()`), then dispatch via `asyncio.create_task()` -- simpler but shares the event loop

**Detection:** Trigger a pipeline run and immediately try to browse summaries. If browsing hangs, this pitfall is active.

**Sources:**
- [Managing Background Tasks and Long-Running Operations in FastAPI](https://leapcell.io/blog/managing-background-tasks-and-long-running-operations-in-fastapi)
- [FastAPI Background Tasks docs](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- Current codebase: `src/pipeline_async.py` uses `asyncio.run()` wrapper pattern

---

### Pitfall 3: asyncio Event Loop Conflict (FastAPI vs Existing Pipeline)

**What goes wrong:** FastAPI/uvicorn owns the asyncio event loop. The existing `pipeline.py` calls `asyncio.run(async_pipeline(...))` which tries to create a NEW event loop. This is a hard crash: `RuntimeError: This event loop is already running`.

**Why it happens:** The architecture was designed for CLI use where `asyncio.run()` is correct. Two event loop owners cannot coexist. The temptation is `nest_asyncio` which patches the loop -- this masks the problem and introduces subtle re-entrancy bugs.

**Consequences:** Any attempt to trigger pipeline runs from the web UI crashes immediately.

**Prevention:**
1. Refactor `async_pipeline()` to be a standalone coroutine callable with `await` -- remove its dependency on being the top-level entry point
2. Keep `run_pipeline()` as the sync CLI entry point that calls `asyncio.run(async_pipeline(...))`
3. FastAPI code uses `await async_pipeline()` or dispatches to subprocess
4. Do NOT use `nest_asyncio`
5. This refactoring MUST happen before building pipeline management endpoints

**Detection:** Loud and obvious: `RuntimeError` on first pipeline trigger from web.

---

### Pitfall 4: Duplicating Pipeline Logic in the API Layer

**What goes wrong:** Building new query functions, data models, or business logic in the API layer instead of importing existing modules. Results in two code paths that drift apart.

**Why it happens:** Developer writes API endpoints and thinks "I'll just query the DB directly" instead of importing `EntityRepository`, or writes a new file reader instead of using sidecar JSON.

**Consequences:** Bugs in one layer but not the other. Entity CRUD in API behaves differently from CLI. Maintenance doubles.

**Prevention:** Hard rule: API routers import from `src.*` modules. The API layer contains only HTTP concerns (request parsing, response formatting, error translation). Zero business logic in `api/`.

**Detection:** Any `sqlite3` import in `api/` code. Any file reading logic that duplicates `output/writer.py` patterns.

---

### Pitfall 5: Exposing Flat File Paths Directly as API Routes

**What goes wrong:** Summaries live as flat markdown in `output/` with date-based directories. Developers map these directly to routes (`GET /api/summaries/2026-04-07` reads `output/2026-04-07/daily.md`). This creates tight coupling between filesystem layout and API contract, and path traversal vulnerabilities.

**Why it happens:** Mirroring file layout as REST resources feels natural. The CLI already uses this structure.

**Consequences:** Path traversal attacks if date parameters are not strictly validated. Breaking API changes when file layout evolves. No metadata, pagination, or filtering without re-reading files.

**Prevention:**
1. Build a data access layer: `SummaryRepository.get_by_date()`, never `Path("output") / date / "daily.md"` in route handlers
2. Serve JSON from sidecar files as the primary API response, not raw markdown
3. Validate all date parameters strictly (`YYYY-MM-DD` regex, date range bounds, no path separators)
4. Never expose filesystem paths in API responses or error messages

**Detection:** Any `Path()` concatenation with user input in route handlers.

---

## Moderate Pitfalls

### Pitfall 6: CORS Misconfiguration Between Dev Servers

**What goes wrong:** Next.js dev server (port 3000) makes requests to FastAPI (port 8000). Browser blocks the request. Developers add `allow_origins=["*"]` with `allow_credentials=True`, which browsers reject per CORS spec. Or CORSMiddleware is added after other middleware, so error responses lack CORS headers.

**Prevention:** Use both approaches (belt and suspenders):
1. Next.js `rewrites` in `next.config.ts` proxies `/api/*` to `localhost:8000` -- frontend never sees cross-origin
2. FastAPI `CORSMiddleware` (MUST be first middleware added) allows `localhost:3000`
3. Never combine `allow_origins=["*"]` with `allow_credentials=True`
4. Test with browser fetch, not curl (curl ignores CORS)

**Sources:**
- [FastAPI CORS documentation](https://fastapi.tiangolo.com/tutorial/cors/)
- [CORSMiddleware ordering discussion](https://github.com/fastapi/fastapi/discussions/7319)

---

### Pitfall 7: Config File Mutation From Web UI Without Safety

**What goes wrong:** Config editing implemented as "read YAML, modify dict, write YAML back." Race conditions between running pipeline and user editing config. Invalid config breaks next pipeline run. No rollback.

**Why it happens:** The existing config has env var overrides, `extra="forbid"` validation, fuzzy "did you mean?" errors, and section-level examples. The editor must handle all of this.

**Prevention:**
1. Build config read-only view FIRST. Validate all writes through `PipelineConfig(**raw)` before writing to disk
2. Atomic write: write to temp file, validate, then `os.rename()` (atomic on POSIX)
3. Config history: copy current YAML to timestamped backup before overwriting
4. Config changes during active pipeline run should be rejected or queued
5. Show env var overrides as read-only indicators in the UI
6. Return Pydantic validation errors as structured JSON

**Detection:** Config write endpoint that bypasses Pydantic validation.

---

### Pitfall 8: Thread Safety of Existing Singleton Patterns

**What goes wrong:** `PipelineContext` is a mutable dataclass holding google_creds, calendar_service, gmail_service. Safe in single-threaded CLI, dangerous when shared across concurrent web requests.

**Prevention:**
1. `PipelineConfig` is Pydantic -- safe to share as read-only. Config RELOAD must be atomic (replace whole object)
2. `PipelineContext` must NEVER be shared between requests. Create per-pipeline-run only
3. `anthropic.Anthropic()` uses httpx, is thread-safe -- safe as singleton
4. Google API service objects: treat as NOT thread-safe. Create per-pipeline-run
5. Use FastAPI `Depends()` to scope lifetimes correctly

**Detection:** Module-level mutable globals holding connections or service objects.

---

### Pitfall 9: Next.js Server Components Fetching from FastAPI

**What goes wrong:** Using React Server Components to fetch from FastAPI backend. RSC runs on the Node server, which fetches from the Python server, which returns JSON, which RSC renders to HTML. Extra network hop, confusing data flow, harder debugging.

**Prevention:** Use Client Components (`"use client"`) for all data-fetching interactive panels. Server Components for static layout shells only. The browser should talk to FastAPI directly. For a localhost-first single-user tool, SSR provides zero benefit for the three-column interactive UI.

**Detection:** `fetch()` calls inside `page.tsx` files without `"use client"` directive.

---

### Pitfall 10: Over-Engineering the TypeScript API Client

**What goes wrong:** Spending days setting up OpenAPI codegen, watchers, pre-commit hooks before the API endpoints are stable.

**Prevention:** Start with manual `fetch()` wrappers in a single `api.ts` file. Add codegen when the API has 10+ stable endpoints. The API will change rapidly in early phases -- generated clients amplify churn.

---

### Pitfall 11: SQLite WAL Checkpoint Stall Under Persistent Readers

**What goes wrong:** WAL appends writes to `.db-wal` that periodically checkpoints back to the main database. Checkpointing requires NO active readers holding old snapshots. Web dashboards with keep-alive connections or long polling prevent checkpoints. WAL file grows unbounded, performance degrades.

**Prevention:**
1. Connection-per-request pattern naturally closes connections quickly
2. Verify `PRAGMA wal_autocheckpoint=1000` is not disabled
3. Monitor `.db-wal` file size -- if it exceeds 10MB for this use case, investigate
4. Do NOT keep SQLite connections in pools with long idle timeouts

---

### Pitfall 12: Losing Pipeline Run Status on Server Restart

**What goes wrong:** Pipeline run status stored in in-memory dict. Uvicorn restart (--reload in dev) loses all tracking. SSE clients disconnect with no recovery.

**Prevention:** Accept this limitation initially for single-user dev. For resilience, write run status to SQLite `pipeline_runs` table. SSE endpoint reads from persistent storage on reconnect.

---

## Minor Pitfalls

### Pitfall 13: Markdown Rendering Inconsistencies

**What goes wrong:** Pipeline markdown uses source attribution tags, structured headers, commitment blocks. `react-markdown` renders these differently than VS Code or GitHub.

**Prevention:** Serve structured JSON from sidecar files as PRIMARY source. If markdown must be displayed, use `remark-gfm` and test against 10+ real production summaries, not synthetic data.

---

### Pitfall 14: Date/Timezone Mismatch Between Frontend and Backend

**What goes wrong:** Browser local timezone differs from pipeline timezone (`America/New_York`). "Today's summary" shows wrong date.

**Prevention:**
1. All API dates use ISO 8601 date strings (`YYYY-MM-DD`), not datetime with timezone
2. "Current date" comes from backend config timezone, not browser
3. Frontend asks backend for latest available summary date, does not compute "today"

---

### Pitfall 15: Two Build Systems Confusion

**What goes wrong:** Python (pip/poetry) AND Node.js (npm/pnpm) dependencies. Developers forget one set. Starting dev requires two terminals.

**Prevention:** Single `Makefile` with unified targets: `make install`, `make dev` (both servers), `make test`. Use `concurrently` to run both dev servers from one command.

---

### Pitfall 16: Date Navigation Edge Cases

**What goes wrong:** User navigates to a date with no summary (weekend, holiday, pipeline failure). UI shows blank or errors.

**Prevention:** Summary list endpoint returns available dates. Navigation skips to nearest available date. Empty state shows "No summary for this date" with links to adjacent dates.

---

### Pitfall 17: Auth Scope Creep

**What goes wrong:** Adding JWT/OAuth for a localhost single-user tool. Wastes 1-2 weeks on zero-value infrastructure.

**Prevention:** No auth for localhost. Multi-user is explicitly v5.0+ scope. When hosting becomes real, add simple API key middleware.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Severity | Mitigation |
|-------------|---------------|----------|------------|
| FastAPI skeleton | Event loop conflict (#3) | Critical | Refactor `async_pipeline()` entry point before building ANY endpoints |
| FastAPI skeleton | CORS issues (#6) | Moderate | CORSMiddleware first + Next.js rewrites from day one |
| SQLite data access | Database locked (#1) | Critical | `busy_timeout=5000`, connection-per-request via `Depends()` |
| SQLite data access | Thread safety (#8) | Moderate | Request-scoped connections, no shared mutable state |
| Summary endpoints | File path coupling (#5) | Critical | Data access layer, serve JSON from sidecar files |
| Summary endpoints | Missing sidecars for old dates | Moderate | Graceful fallback: markdown-only when no JSON sidecar exists |
| Summary endpoints | Markdown rendering (#13) | Minor | JSON-first; test with real summaries if markdown needed |
| Entity endpoints | Logic duplication (#4) | Critical | Import from `src.entity.repository`, no direct SQL in routes |
| Entity endpoints | Concurrent write locks (#1) | Critical | `busy_timeout`, `BEGIN IMMEDIATE`, fast transactions |
| Config endpoints | Write safety (#7) | Moderate | Read-only first; writes use full PipelineConfig validation |
| Pipeline management | Server blocking (#2) | Critical | Subprocess isolation, 202 Accepted + status polling |
| Pipeline management | Event loop conflict (#3) | Critical | `await async_pipeline()` directly, no nested `asyncio.run()` |
| Pipeline management | Lost state on restart (#12) | Moderate | Persist run status to SQLite table |
| Next.js frontend | RSC misuse (#9) | Moderate | Client components for interactive panels |
| Next.js frontend | TypeScript client overengineering (#10) | Moderate | Manual fetch wrappers first |
| Next.js frontend | Two build systems (#15) | Minor | Unified Makefile |
| Date navigation | Timezone mismatch (#14) | Minor | Backend-authoritative dates |
| Date navigation | Missing dates (#16) | Minor | Available-dates endpoint |
| Production readiness | Auth scope creep (#17) | Minor | No auth for localhost |
| Production readiness | WAL checkpoint stall (#11) | Moderate | Short-lived connections, monitor WAL size |

## Recommended Phase Order Based on Pitfall Severity

1. **Foundation: API layer + SQLite hardening** -- Resolve event loop conflict (#3), add `busy_timeout` (#1), build connection-per-request pattern, data access layer for summaries (#5). These are architectural decisions that are expensive to change after endpoints are built on top.

2. **Read-only endpoints** -- Summary browsing and entity listing. Fewer concurrency risks. Validates the DAL pattern and CORS setup (#6) without write-path complexity.

3. **Write endpoints** -- Entity CRUD and config management. Introduces concurrent write pitfalls (#1, #7). Build on proven connection patterns from step 2.

4. **Pipeline management** -- Highest complexity: background jobs (#2), status tracking (#12), long-running operations (#3). Needs the most infrastructure. Benefits from all prior patterns being stable.

## Sources

- [SQLite concurrent writes and "database is locked" errors](https://tenthousandmeters.com/blog/sqlite-concurrent-writes-and-database-is-locked-errors/) -- HIGH confidence
- [SQLite WAL documentation](https://www.sqlite.org/wal.html) -- HIGH confidence
- [FastAPI CORS documentation](https://fastapi.tiangolo.com/tutorial/cors/) -- HIGH confidence
- [FastAPI Background Tasks documentation](https://fastapi.tiangolo.com/tutorial/background-tasks/) -- HIGH confidence
- [Managing Background Tasks in FastAPI](https://leapcell.io/blog/managing-background-tasks-and-long-running-operations-in-fastapi) -- HIGH confidence
- [Is check_same_thread=False Safe?](https://github.com/fastapi/fastapi/discussions/5199) -- HIGH confidence
- [Python sqlite3 thread safety](https://ricardoanderegg.com/posts/python-sqlite-thread-safety/) -- HIGH confidence
- [CORSMiddleware ordering discussion](https://github.com/fastapi/fastapi/discussions/7319) -- HIGH confidence
- Direct codebase analysis: `src/entity/db.py`, `src/pipeline.py`, `src/pipeline_async.py`, `src/entity/repository.py`, `src/config.py` -- HIGH confidence
