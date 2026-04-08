# Architecture: v3.0 Web Interface Integration

**Domain:** FastAPI backend + Next.js frontend layered onto existing Python pipeline
**Researched:** 2026-04-08
**Overall confidence:** HIGH (existing codebase is well-structured for this; FastAPI/Next.js patterns are mature)

## Recommended Architecture

The web layer is a **read-heavy facade** over the existing pipeline. The core principle is **thin API over existing modules** -- the FastAPI backend imports and calls the same Python functions the CLI uses today. No pipeline logic moves into the API layer; the API is a JSON translation layer.

### System Diagram

```
                     Browser (Next.js)
                          |
                     localhost:3000
                          |
                    [Next.js App Router]
                     /        \
              React UI     API Route Proxy
                            (optional, for SSE)
                          |
                     localhost:8000
                          |
                    [FastAPI Backend]
                   /    |    |     \
            /summaries  |  /config  \
                   /entities  /pipeline
                  |     |      |      |
          [file reads] [SQLite] [YAML] [async_pipeline]
              output/   data/   config/   src/
```

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| **Next.js App** | UI rendering, client state, navigation | FastAPI via fetch/SSE |
| **FastAPI Backend** | JSON API, auth (future), SSE streaming | Existing Python modules directly |
| **Summary Service** | Read markdown/JSON from output dir | Filesystem (output/daily/, output/quality/) |
| **Entity Service** | CRUD wrapper over EntityRepository | SQLite via existing repository.py |
| **Config Service** | Read/write pipeline YAML config | config/config.yaml via existing config.py |
| **Pipeline Service** | Trigger runs, stream status, run history | pipeline_async.py, subprocess for isolation |

## API Boundary Design

This is the critical architectural decision. The rule: **API reads structured data (JSON sidecars, SQLite); file system reads stay server-side only.**

### What goes through the API

| Data | Source | API Pattern | Rationale |
|------|--------|------------|-----------|
| Daily summaries (structured) | JSON sidecars | `GET /api/summaries/{date}` | Sidecar has meetings, tasks, decisions as structured data |
| Daily summaries (rendered) | Markdown files | `GET /api/summaries/{date}/markdown` | Server reads and returns markdown; frontend renders |
| Summary calendar/index | File system scan | `GET /api/summaries?from=&to=` | Server scans output/daily/ for available dates |
| Entity list + stats | SQLite | `GET /api/entities?type=&sort=` | Wraps `get_enriched_entity_list()` |
| Entity scoped view | SQLite | `GET /api/entities/{id}/activity` | Wraps `get_entity_scoped_view()` |
| Entity CRUD | SQLite | `POST/PUT/DELETE /api/entities/{id}` | Wraps EntityRepository methods |
| Merge proposals | SQLite | `GET/POST /api/entities/merges` | Wraps merger.py functions |
| Alias management | SQLite | `POST/DELETE /api/entities/{id}/aliases` | Wraps repository alias methods |
| Pipeline config | YAML file | `GET/PUT /api/config` | Reads/writes config/config.yaml |
| Pipeline runs | In-memory + log | `POST /api/pipeline/run` | Triggers async pipeline, returns run ID |
| Pipeline status | In-memory | `GET /api/pipeline/runs/{id}/status` (SSE) | Streams progress events |
| Quality metrics | JSONL file | `GET /api/quality` | Reads output/quality/metrics.jsonl |

### What does NOT go through the API

- Raw cached data (output/raw/) -- internal pipeline concern
- Dedup logs -- internal debugging
- Template files -- server-side rendering only
- Credentials -- never exposed

## Data Flow Details

### Read Path: Daily Summaries

```
Browser requests GET /api/summaries/2026-04-07
  -> FastAPI handler reads output/daily/2026/04/2026-04-07.json (sidecar)
  -> Also reads output/daily/2026/04/2026-04-07.md (markdown body)
  -> Returns { sidecar: {...structured data...}, markdown: "..." }
  -> Next.js renders markdown in center panel, structured data in sidebar
```

The JSON sidecar already contains `SidecarTask`, `SidecarDecision`, `SidecarMeeting`, `SidecarCommitment`, and `SidecarEntityReference` models. These map directly to API response shapes with zero transformation.

### Read Path: Entity Views

```
Browser requests GET /api/entities/abc123/activity?from=2026-03-01
  -> FastAPI creates EntityRepository(db_path=config.entity.db_path)
  -> Calls get_entity_scoped_view(repo, entity_id, from_date, to_date)
  -> Returns EntityScopedView as JSON (already a Pydantic model)
```

The existing `EntityScopedView`, `EnrichedEntity`, and `ActivityItem` Pydantic models serialize directly to JSON. No new models needed for reads.

### Write Path: Entity CRUD

```
Browser POSTs to /api/entities with { name, entity_type, organization_id, ... }
  -> FastAPI validates via Pydantic request model
  -> Creates EntityRepository, calls repo.add_entity(...)
  -> Returns created Entity as JSON
```

### Write Path: Config Updates

```
Browser PUTs to /api/config with partial config JSON
  -> FastAPI validates against PipelineConfig model
  -> Writes updated YAML to config/config.yaml
  -> Returns validated config
```

Config writes use Pydantic validation (already built) to reject invalid configs before writing. The `PipelineConfig` model with `extra="forbid"` prevents unknown keys.

### Pipeline Trigger + SSE Status

```
Browser POSTs to /api/pipeline/run with { date, sources? }
  -> FastAPI spawns pipeline in background task
  -> Returns { run_id: "uuid" }
  -> Browser opens SSE connection: GET /api/pipeline/runs/{run_id}/status
  -> Server yields ServerSentEvent for each stage:
     { event: "stage", data: { name: "calendar_ingest", status: "running" } }
     { event: "stage", data: { name: "calendar_ingest", status: "complete", duration_ms: 1234 } }
     { event: "stage", data: { name: "synthesis", status: "running" } }
     ...
     { event: "complete", data: { summary_path: "output/daily/2026/04/2026-04-08.md" } }
```

**Implementation:** FastAPI 0.135+ has native SSE via `EventSourceResponse` and `ServerSentEvent`. Use an async generator that reads from an `asyncio.Queue`. The pipeline run pushes status updates to the queue; the SSE endpoint yields from it.

```python
# Conceptual pattern -- not final implementation
from fastapi.sse import EventSourceResponse, ServerSentEvent

@app.post("/api/pipeline/run")
async def trigger_run(request: RunRequest) -> RunResponse:
    run_id = uuid4().hex
    queue = asyncio.Queue()
    active_runs[run_id] = queue
    asyncio.create_task(_run_pipeline(run_id, request, queue))
    return RunResponse(run_id=run_id)

@app.get("/api/pipeline/runs/{run_id}/status", response_class=EventSourceResponse)
async def stream_status(run_id: str) -> AsyncIterable[ServerSentEvent]:
    queue = active_runs.get(run_id)
    if not queue:
        raise HTTPException(404)
    while True:
        event = await queue.get()
        yield ServerSentEvent(data=event, event=event["type"])
        if event["type"] in ("complete", "error"):
            break
```

**Why SSE over WebSocket:** SSE is simpler (unidirectional server-to-client), auto-reconnects, works through proxies, and FastAPI has first-class support. The pipeline status stream is inherently one-way. WebSocket adds complexity with no benefit here.

## Monorepo Structure

```
daily-summarizer/                    # Existing project root
  pyproject.toml                     # Python deps (add fastapi, uvicorn)
  uv.lock
  config/
  data/
  output/
  src/                               # Existing pipeline code (UNCHANGED)
    pipeline_async.py
    config.py
    entity/
    ...
  api/                               # NEW: FastAPI application
    __init__.py
    app.py                           # FastAPI app factory
    deps.py                          # Dependency injection (repo, config)
    routers/
      __init__.py
      summaries.py                   # GET summaries, markdown
      entities.py                    # Entity CRUD, views, merges
      config.py                      # Config read/write
      pipeline.py                    # Run triggers, SSE status
    models/                          # API-specific request/response models
      __init__.py
      requests.py                    # RunRequest, EntityCreateRequest, etc.
      responses.py                   # Thin wrappers if needed
    services/
      __init__.py
      summary_reader.py              # File-based summary reading logic
      pipeline_runner.py             # Background task + queue management
  web/                               # NEW: Next.js frontend
    package.json
    next.config.ts
    tsconfig.json
    src/
      app/                           # App Router
        layout.tsx                   # Three-column layout shell
        page.tsx                     # Daily summary (default view)
        entities/
          page.tsx                   # Entity browser
          [id]/page.tsx              # Entity detail/scoped view
        config/
          page.tsx                   # Pipeline config editor
        pipeline/
          page.tsx                   # Run management
      components/
        layout/
          Sidebar.tsx                # Left nav: entities, sections
          ContentPanel.tsx           # Center: summary/entity content
          ContextPanel.tsx           # Right: related items, evidence
        summaries/
        entities/
        pipeline/
      lib/
        api.ts                       # Fetch wrapper for FastAPI
        sse.ts                       # SSE client for pipeline status
        types.ts                     # TypeScript types (from OpenAPI)
      hooks/
        useSummary.ts
        useEntities.ts
        usePipelineRun.ts
  tests/                             # Existing tests (UNCHANGED)
  tests/api/                         # NEW: API integration tests
```

### Why NOT a separate repo or Turborepo

1. **Python-first project.** The frontend is a thin layer over a Python pipeline. Turborepo adds JS-ecosystem complexity (workspaces, hoisting) that does not serve a project with one Python backend and one JS frontend.
2. **Shared filesystem.** The API reads files from `output/` and `data/` -- same filesystem as the pipeline. Separate repos would require mounting or syncing.
3. **Single developer.** No team coordination overhead justifying workspace isolation.
4. **Simple structure.** `api/` (Python) and `web/` (Node) as sibling directories in the existing repo. Each has its own dependency management (`pyproject.toml` for Python, `package.json` for JS). No monorepo tooling needed.

### Development Workflow

```bash
# Terminal 1: FastAPI backend
uvicorn api.app:app --reload --port 8000

# Terminal 2: Next.js frontend
cd web && npm run dev    # port 3000, proxies /api to 8000
```

Next.js `next.config.ts` uses `rewrites` to proxy `/api/*` to `http://localhost:8000/api/*` during development. In production (if ever hosted), reverse proxy handles this.

## SQLite Concurrency Strategy

The existing entity DB uses WAL mode (already configured in `db.py`). For FastAPI:

1. **Add `busy_timeout`:** Set `PRAGMA busy_timeout=5000` after connection. Prevents "database is locked" on concurrent reads during a pipeline write.
2. **Connection per request:** Use FastAPI dependency injection to create/close connections per request. SQLite WAL allows concurrent readers.
3. **Single writer enforcement:** Pipeline writes are rare (once per run). API writes (entity CRUD) are low-frequency. No write contention expected at single-user scale.
4. **No ORM:** Keep using raw `sqlite3` via `EntityRepository`. Adding SQLAlchemy for a single-user app with an existing working data layer adds complexity without benefit.

## Integration Points with Existing Code

### Direct imports (no changes to existing modules)

| API Router | Imports From | Functions Used |
|------------|-------------|----------------|
| `routers/entities.py` | `src.entity.repository` | `EntityRepository` (all CRUD methods) |
| `routers/entities.py` | `src.entity.views` | `get_entity_scoped_view()`, `get_enriched_entity_list()` |
| `routers/entities.py` | `src.entity.merger` | `generate_proposals()`, `execute_merge()` |
| `routers/config.py` | `src.config` | `load_config()`, `PipelineConfig` |
| `routers/summaries.py` | `src.sidecar` | Sidecar Pydantic models for type hints |
| `routers/pipeline.py` | `src.pipeline_async` | `async_pipeline()` (wrapped) |

### New code needed

| Module | Purpose | Complexity |
|--------|---------|------------|
| `api/app.py` | FastAPI app factory, CORS, router registration | Low |
| `api/deps.py` | Dependency injection: config loader, DB connection | Low |
| `api/services/summary_reader.py` | Scan output dir, read markdown + JSON sidecars | Medium |
| `api/services/pipeline_runner.py` | Background task wrapper, status queue, run history | Medium |
| `api/routers/summaries.py` | Summary list, detail, markdown endpoints | Low |
| `api/routers/entities.py` | Entity CRUD, views, merges, aliases | Medium |
| `api/routers/config.py` | Config read/write with validation | Low |
| `api/routers/pipeline.py` | Run trigger, SSE status stream | Medium |

### Modifications to existing code

Minimal. The only change needed is making `pipeline_async.py` emit status callbacks so the API can stream progress. This means adding an optional callback parameter to `async_pipeline()`:

```python
# In pipeline_async.py -- add optional status_callback
async def async_pipeline(
    config: PipelineConfig,
    target_date: date,
    status_callback: Callable[[str, str], None] | None = None,
) -> dict:
    ...
    if status_callback:
        status_callback("calendar_ingest", "running")
    # existing logic
    if status_callback:
        status_callback("calendar_ingest", "complete")
```

This is additive -- existing CLI callers pass no callback and behavior is unchanged.

## Patterns to Follow

### Pattern 1: Pydantic Models as API Contract

**What:** Reuse existing Pydantic models (`Entity`, `EntityScopedView`, `EnrichedEntity`, sidecar models) as FastAPI response models directly.
**When:** All entity and sidecar read endpoints.
**Why:** These models already serialize to JSON correctly. FastAPI generates OpenAPI schemas from them automatically. Zero duplication.

```python
@router.get("/entities", response_model=list[EnrichedEntity])
async def list_entities(
    entity_type: str | None = None,
    sort: str = "active",
    repo: EntityRepository = Depends(get_repo),
) -> list[EnrichedEntity]:
    return get_enriched_entity_list(repo, entity_type=entity_type, sort_by=sort)
```

### Pattern 2: Repository-per-Request via Dependency Injection

**What:** FastAPI `Depends()` creates and closes an `EntityRepository` per request.
**When:** All entity endpoints.

```python
# api/deps.py
def get_repo():
    config = load_config()
    repo = EntityRepository(config.entity.db_path)
    repo.connect()
    try:
        yield repo
    finally:
        repo.close()
```

### Pattern 3: File System Reader as Service

**What:** Encapsulate output directory scanning in a service class rather than inline in route handlers.
**When:** Summary list and detail endpoints.
**Why:** Isolates filesystem logic, makes it testable, handles missing dates gracefully.

### Pattern 4: SSE for Long Operations Only

**What:** Use SSE exclusively for pipeline run status. All other endpoints are standard request/response.
**When:** Pipeline runs (30s-3min duration).
**Why:** SSE adds client complexity. Only justified when the operation is long-running and the user needs real-time feedback.

## Anti-Patterns to Avoid

### Anti-Pattern 1: GraphQL
**What:** Building a GraphQL API for the entity graph.
**Why bad:** Single consumer (the Next.js app), low query variety, adds resolver complexity. REST with a few well-shaped endpoints is simpler and sufficient.
**Instead:** REST endpoints that return the exact shapes the UI needs.

### Anti-Pattern 2: ORM for SQLite
**What:** Adding SQLAlchemy or Tortoise ORM.
**Why bad:** The EntityRepository already handles all queries. ORM adds migration tooling, session management, and async driver complexity for a single-file database with 6 tables.
**Instead:** Keep raw sqlite3 in EntityRepository. Add `busy_timeout` pragma.

### Anti-Pattern 3: WebSocket for Everything
**What:** Using WebSocket connections for all real-time updates.
**Why bad:** Only pipeline runs need streaming. Entity/summary data changes infrequently (once per pipeline run). Polling or manual refresh is sufficient for data freshness.
**Instead:** SSE for pipeline status. Standard fetch for everything else. Optional: SWR/React Query with stale-while-revalidate for the summary view.

### Anti-Pattern 4: Backend-for-Frontend in Next.js API Routes
**What:** Proxying all FastAPI calls through Next.js API routes.
**Why bad:** Adds a hop, duplicates routing, makes debugging harder. Next.js API routes are for server-side logic that needs Node.js -- not for proxying to another backend.
**Instead:** Frontend fetches FastAPI directly. Next.js rewrites handle the port mapping in dev.

## Scalability Considerations

| Concern | Current (1 user) | If hosted (5 users) | Notes |
|---------|------------------|---------------------|-------|
| SQLite concurrency | WAL mode sufficient | Still fine with WAL + busy_timeout | Migrate to PostgreSQL only if write contention appears |
| File reads | Direct filesystem | Direct filesystem | Output dir is small (365 files/year max) |
| Pipeline runs | One at a time | Lock to prevent concurrent runs | Queue if multi-user needed |
| API process | Single uvicorn | Gunicorn + 2 workers | Overkill until hosted |

## Sources

- [FastAPI SSE documentation](https://fastapi.tiangolo.com/tutorial/server-sent-events/)
- [FastAPI + Next.js monorepo patterns (Vinta Software)](https://www.vintasoftware.com/blog/nextjs-fastapi-monorepo)
- [SQLite WAL mode documentation](https://www.sqlite.org/wal.html)
- [FastAPI project structure best practices](https://github.com/zhanymkanov/fastapi-best-practices)
- [Full-stack type safety with FastAPI + Next.js + OpenAPI](https://abhayramesh.com/blog/type-safe-fullstack)
- Direct codebase analysis of src/entity/repository.py, src/entity/views.py, src/pipeline_async.py, src/config.py, src/sidecar.py, src/models/events.py
