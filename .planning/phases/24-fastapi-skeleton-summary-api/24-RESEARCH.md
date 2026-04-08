# Phase 24: FastAPI Skeleton + Summary API - Research

**Researched:** 2026-04-08
**Domain:** FastAPI backend foundation, summary read endpoints, SQLite hardening, Next.js scaffold
**Confidence:** HIGH

## Summary

Phase 24 establishes the API foundation by adding FastAPI to the existing Python project and proving the core integration pattern: the API layer imports `src.*` modules directly with zero business logic duplication. The phase delivers three working endpoints (health/status, summary detail, summary list) plus SQLite hardening (busy_timeout, connection-per-request) and a minimal Next.js scaffold for CORS validation.

The existing codebase is well-structured for this. Pydantic models (`DailySidecar`, `PipelineConfig`, `Entity`) serialize directly to JSON. `EntityRepository` already supports context manager usage. The output directory has 6 markdown summaries and 4 JSON sidecars, meaning the API must handle graceful degradation for dates with markdown but no sidecar (2 such dates exist today: 2026-04-01, 2026-04-02).

**Primary recommendation:** Build the API at `src/api/` (inside the existing src package), add `busy_timeout=5000` to `get_connection()` in `src/entity/db.py`, use sync `def` endpoints with FastAPI's automatic thread pool for SQLite access, and scaffold Next.js in `web/` with a single fetch to validate CORS end-to-end.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- API code lives at `src/api/` (inside the existing src package for clean imports of src.entity, src.config, etc.)
- Versioned URL prefix: `/api/v1/summaries`, `/api/v1/entities`, etc.
- One router per domain: `summaries.py`, `entities.py`, `pipeline.py`, `config.py` (4 files, only summaries implemented in Phase 24)
- OpenAPI docs enabled at `/docs` (Swagger UI)
- `GET /api/v1/summaries/{date}` returns combined response: structured sidecar data AND markdown body in a single JSON response
- Summary list endpoint (`GET /api/v1/summaries`) returns dates with previews: meeting count, commitment count, top themes per date
- Makefile with `make dev` starts both FastAPI and Next.js via concurrently or similar
- pnpm as the JS package manager
- Phase 24 scaffolds both: FastAPI API + empty Next.js project in `web/`
- Dates with markdown but no JSON sidecar: return markdown body with structured fields as null/empty
- Invalid dates: 422 Unprocessable Entity with Pydantic validation error
- Rich `/api/v1/status` endpoint: DB connectivity, last pipeline run date, summary count
- All API endpoints import from `src.*` modules -- grep for `sqlite3` in api/ returns nothing
- SQLite connections need `busy_timeout=5000` added to `get_connection()` in `src/entity/db.py`
- CORS middleware must be added first (before other middleware) allowing localhost:3000
- Next.js scaffold uses App Router, TypeScript, Tailwind, and shadcn/ui setup

### Claude's Discretion
- Exact fields in the curated summary response model (which sidecar fields to include/expose)
- Concurrently vs Makefile parallel targets for `make dev`
- Exact FastAPI dependency injection pattern for config and DB connections
- Test strategy (pytest with httpx TestClient)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| API-01 | FastAPI backend serves JSON API on localhost:8000 with CORS for localhost:3000 | FastAPI app factory pattern, CORSMiddleware configuration, CORS-first middleware ordering |
| API-02 | SQLite connections use busy_timeout and connection-per-request pattern for safe concurrent access | `busy_timeout=5000` pragma in `get_connection()`, FastAPI `Depends()` yield pattern for repo lifecycle |
| API-03 | API imports existing `src.*` modules directly -- zero business logic duplication in API layer | API at `src/api/` enables clean `from src.entity.repository import EntityRepository` imports; summary reader service wraps file I/O only |
| SUM-03 | Summary index endpoint returns available dates so navigation skips gaps | File system scan of `output/daily/` with date extraction from directory structure; returns preview data from sidecar JSON when available |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.135.x | ASGI web framework, JSON API | Pydantic v2 native (matches existing models), auto-generates OpenAPI, async-capable |
| uvicorn | 0.34.x | ASGI server | Standard FastAPI server, auto-reload in dev |
| httpx | (already installed) | Test client for API tests | FastAPI recommends httpx TestClient; already a project dependency |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pnpm | 9.x | JS package manager | Next.js scaffold setup |
| Next.js | 15.2.x | Frontend framework scaffold | Minimal scaffold in `web/` for CORS validation |
| concurrently | latest | Run multiple dev servers | `make dev` runs both FastAPI and Next.js |

### What NOT to Add
| Temptation | Why to Resist |
|------------|---------------|
| aiosqlite | Sync sqlite3 in thread pool is correct; EntityRepository is battle-tested |
| SQLAlchemy | ORM adds complexity for zero benefit with existing repository |
| nest_asyncio | Masks event loop conflicts with re-entrancy bugs |

**Installation:**
```bash
# Backend (add to pyproject.toml)
uv add fastapi uvicorn

# Frontend scaffold (new web/ directory)
pnpm create next-app@latest web --typescript --tailwind --eslint --app --src-dir
cd web && pnpm dlx shadcn@latest init

# Dev tooling (npm, for make dev)
npm install -g concurrently  # or add to web/package.json devDeps
```

## Architecture Patterns

### Project Structure (New Files)
```
src/
  api/                         # NEW: FastAPI application (inside src package)
    __init__.py
    app.py                     # App factory, CORS, router registration
    deps.py                    # Dependency injection: config, DB, summary reader
    routers/
      __init__.py
      summaries.py             # GET /api/v1/summaries, GET /api/v1/summaries/{date}
    services/
      __init__.py
      summary_reader.py        # File system scan + read logic for output/daily/
    models/
      __init__.py
      responses.py             # SummaryResponse, SummaryListItem, StatusResponse
web/                           # NEW: Next.js scaffold (minimal)
  src/app/
    layout.tsx                 # App shell
    page.tsx                   # Minimal page with fetch to /api/v1/status
Makefile                       # NEW: make dev, make test, make install
```

### Pattern 1: App Factory with CORS-First Middleware
**What:** Create FastAPI app in a factory function. CORSMiddleware MUST be the first middleware added.
**Why:** If other middleware throws errors before CORS runs, browser sees CORS error instead of actual error.
**Example:**
```python
# src/api/app.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.routers import summaries

def create_app() -> FastAPI:
    app = FastAPI(
        title="Daily Summarizer API",
        version="0.1.0",
        docs_url="/docs",
    )

    # CORS MUST be first middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
    )

    app.include_router(summaries.router, prefix="/api/v1")

    return app

app = create_app()
```

### Pattern 2: Connection-per-Request via Dependency Injection
**What:** FastAPI `Depends()` creates and closes an `EntityRepository` per request. Use sync `def` (not `async def`) so FastAPI runs it in a thread pool automatically.
**Why:** SQLite connections are not thread-safe. Connection-per-request with WAL mode allows concurrent reads.
**Example:**
```python
# src/api/deps.py
from src.config import load_config, PipelineConfig
from src.entity.repository import EntityRepository

def get_config() -> PipelineConfig:
    return load_config()

def get_entity_repo():
    config = load_config()
    repo = EntityRepository(config.entity.db_path)
    repo.connect()
    try:
        yield repo
    finally:
        repo.close()
```

### Pattern 3: Summary Reader as Service (Not Inline File I/O)
**What:** Encapsulate output directory scanning in a service class. Route handlers never construct file paths.
**Why:** Isolates filesystem logic, prevents path traversal, handles missing sidecars gracefully.
**Example:**
```python
# src/api/services/summary_reader.py
from pathlib import Path
from datetime import date
import json

class SummaryReader:
    def __init__(self, output_dir: str = "output"):
        self._base = Path(output_dir) / "daily"

    def list_available_dates(self) -> list[date]:
        """Scan output/daily/ for YYYY-MM-DD.md files, return sorted dates."""
        dates = []
        for md_file in self._base.rglob("*.md"):
            try:
                dates.append(date.fromisoformat(md_file.stem))
            except ValueError:
                continue
        return sorted(dates, reverse=True)

    def get_summary(self, target_date: date) -> dict | None:
        """Read markdown + optional sidecar for a date."""
        d = target_date
        dir_path = self._base / str(d.year) / f"{d.month:02d}"
        md_path = dir_path / f"{d.isoformat()}.md"
        json_path = dir_path / f"{d.isoformat()}.json"

        if not md_path.exists():
            return None

        result = {"date": d.isoformat(), "markdown": md_path.read_text()}

        if json_path.exists():
            result["sidecar"] = json.loads(json_path.read_text())
        else:
            result["sidecar"] = None  # Graceful degradation for pre-sidecar dates

        return result
```

### Pattern 4: Sync Endpoints for SQLite Access
**What:** Use `def` (not `async def`) for any endpoint that touches SQLite. FastAPI automatically runs sync handlers in a thread pool.
**Why:** Sync sqlite3 in thread pool is the correct pattern. `async def` with sync I/O would block the event loop.
**Example:**
```python
# Correct: sync def -- FastAPI runs in thread pool
@router.get("/summaries")
def list_summaries(reader: SummaryReader = Depends(get_summary_reader)):
    return reader.list_available_dates()

# WRONG: async def with sync I/O blocks the event loop
@router.get("/summaries")
async def list_summaries(...):  # DON'T DO THIS with sync file/DB I/O
    ...
```

### Anti-Patterns to Avoid
- **Direct `Path()` construction in route handlers:** Always go through SummaryReader service. Never concatenate user input into file paths.
- **`async def` with sync sqlite3:** Blocks the uvicorn event loop. Use plain `def` so FastAPI runs it in a thread pool.
- **Importing sqlite3 in api/ code:** All DB access goes through `src.entity.repository` and `src.entity.db`.
- **Shared mutable state across requests:** No module-level `EntityRepository` instances. Create per-request via `Depends()`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CORS handling | Custom headers on responses | `CORSMiddleware` | Handles preflight OPTIONS, error responses, header injection correctly |
| Request validation | Manual date parsing in handlers | Pydantic `date` type in path params | FastAPI auto-returns 422 with structured error |
| OpenAPI docs | Manual API documentation | FastAPI auto-generated `/docs` | Free Swagger UI from Pydantic models |
| Connection lifecycle | Manual try/finally in every handler | `Depends()` with generator | Centralized, testable, never leaks connections |
| Date validation | Regex matching in route handlers | `datetime.date` path parameter type | Pydantic handles format validation, FastAPI returns 422 automatically |

## Common Pitfalls

### Pitfall 1: Missing busy_timeout Causes Sporadic 500s
**What goes wrong:** Concurrent API requests hit SQLite simultaneously. Without `busy_timeout`, writes fail instantly with `SQLITE_BUSY` instead of retrying.
**Why it happens:** CLI only ever had one thread. Web means N concurrent handlers.
**How to avoid:** Add `conn.execute("PRAGMA busy_timeout=5000")` in `src/entity/db.py:get_connection()` right after WAL and foreign_keys pragmas. Single highest-impact one-line fix.
**Warning signs:** `OperationalError: database is locked` in logs.

### Pitfall 2: CORS Headers Missing on Error Responses
**What goes wrong:** CORSMiddleware added after other middleware. When an error occurs, the error response has no CORS headers and the browser shows a CORS error instead of the actual error.
**Why it happens:** Starlette middleware executes in LIFO order for responses (last-added runs first on the way out). CORS must be added first to wrap everything.
**How to avoid:** `app.add_middleware(CORSMiddleware, ...)` MUST be the first `add_middleware` call.
**Warning signs:** Browser console shows CORS error but server logs show a different error (404, 500, etc.).

### Pitfall 3: async def With Sync I/O Blocks Event Loop
**What goes wrong:** Using `async def` for endpoints that do file reads or sqlite3 queries. This runs on the main event loop thread, blocking all other requests.
**Why it happens:** Developer assumes `async def` is always better. It is only better for actual async I/O (httpx, aiofiles).
**How to avoid:** Use plain `def` for all endpoints in Phase 24. FastAPI runs sync handlers in a thread pool automatically.
**Warning signs:** API becomes unresponsive under even light concurrent load.

### Pitfall 4: Sidecar Field Mismatch on Older Summaries
**What goes wrong:** The API response model expects all `DailySidecar` fields but older sidecar JSON files (e.g., 2026-03-18) may lack fields added later (commitments, entity_summary, entity refs).
**Why it happens:** The sidecar schema evolved over time. Older JSON was written before new fields existed.
**How to avoid:** Use `DailySidecar.model_validate()` with the JSON data -- Pydantic fills missing fields with defaults (empty lists). For dates with no JSON at all (2026-04-01, 2026-04-02), return sidecar as null.
**Warning signs:** KeyError or validation errors when loading older sidecars.

### Pitfall 5: check_same_thread Default Breaks FastAPI Thread Pool
**What goes wrong:** Python's `sqlite3.connect()` defaults to `check_same_thread=True`. FastAPI's thread pool may run the dependency generator and the route handler on different threads, causing `ProgrammingError`.
**Why it happens:** Connection-per-request pattern creates the connection in the generator, but FastAPI may execute the actual query on a different thread pool worker.
**How to avoid:** This is actually NOT an issue with the current pattern because the generator and the sync handler run on the SAME thread pool worker. However, if refactoring to async patterns later, this becomes relevant. Keep the sync `def` pattern and this is safe.
**Warning signs:** `ProgrammingError: SQLite objects created in a thread can only be used in that same thread`.

## Code Examples

### Summary Response Model
```python
# src/api/models/responses.py
from pydantic import BaseModel
from datetime import date

class SummaryListItem(BaseModel):
    """One entry in the summary list endpoint."""
    date: date
    meeting_count: int | None = None
    commitment_count: int | None = None
    has_sidecar: bool = False

class SummaryResponse(BaseModel):
    """Full summary for a single date."""
    date: date
    markdown: str
    sidecar: dict | None = None  # Raw sidecar data; None for pre-sidecar dates

class StatusResponse(BaseModel):
    """API status and health information."""
    status: str = "ok"
    db_connected: bool
    summary_count: int
    last_summary_date: date | None = None
```

### Summary Router
```python
# src/api/routers/summaries.py
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from src.api.deps import get_summary_reader
from src.api.services.summary_reader import SummaryReader

router = APIRouter(tags=["summaries"])

@router.get("/summaries")
def list_summaries(reader: SummaryReader = Depends(get_summary_reader)):
    """List available summary dates with preview data."""
    return reader.list_available_dates_with_previews()

@router.get("/summaries/{target_date}")
def get_summary(target_date: date, reader: SummaryReader = Depends(get_summary_reader)):
    """Get full summary (markdown + sidecar) for a specific date."""
    result = reader.get_summary(target_date)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No summary found for {target_date}")
    return result
```

### busy_timeout Addition to Existing db.py
```python
# In src/entity/db.py:get_connection() -- add after foreign_keys pragma
conn.execute("PRAGMA busy_timeout=5000")
```

### Status Endpoint
```python
# src/api/routers/summaries.py (or a separate status.py)
@router.get("/status")
def get_status(
    reader: SummaryReader = Depends(get_summary_reader),
    config: PipelineConfig = Depends(get_config),
):
    """API health check with system info."""
    dates = reader.list_available_dates()
    db_ok = False
    try:
        repo = EntityRepository(config.entity.db_path)
        repo.connect()
        repo.close()
        db_ok = True
    except Exception:
        pass

    return StatusResponse(
        db_connected=db_ok,
        summary_count=len(dates),
        last_summary_date=dates[0] if dates else None,
    )
```

### Makefile
```makefile
.PHONY: dev dev-api dev-web install test

install:
	uv sync
	cd web && pnpm install

dev-api:
	uvicorn src.api.app:app --reload --port 8000

dev-web:
	cd web && pnpm dev

dev:
	@command -v concurrently >/dev/null 2>&1 || npx concurrently --version >/dev/null 2>&1
	npx concurrently --names "api,web" --prefix-colors "blue,green" \
		"uvicorn src.api.app:app --reload --port 8000" \
		"cd web && pnpm dev"

test:
	python -m pytest tests/ -x -q

test-api:
	python -m pytest tests/api/ -x -q
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| FastAPI `BackgroundTasks` for long ops | Subprocess isolation for pipeline | 2024+ community consensus | Phase 28 concern, not Phase 24 |
| `async def` everywhere | Sync `def` for sync I/O, FastAPI thread pool | Always been correct, often misunderstood | Phase 24 uses sync `def` for all endpoints |
| OpenAPI codegen for TS client | Manual fetch wrappers first, codegen later | Pragmatic for early-stage APIs | Phase 24 scaffolds minimal Next.js, no codegen |

## Existing Codebase Facts (Verified)

| Fact | Details | Impact |
|------|---------|--------|
| Output file layout | `output/daily/YYYY/MM/YYYY-MM-DD.{md,json}` | Summary reader must match this glob pattern |
| Markdown count | 6 files (2026-03-18, 2026-04-01 through 2026-04-08) | Enough for testing; some have no sidecar |
| Sidecar count | 4 files (2026-03-18, 2026-04-03, 2026-04-05, 2026-04-08) | 2 dates have markdown but no sidecar -- must handle gracefully |
| Older sidecar schema | 2026-04-03 has 7 keys (no commitments, no entity refs) | `DailySidecar.model_validate()` fills defaults for missing fields |
| EntityRepository | Context manager support (`__enter__`/`__exit__`), `connect()`/`close()` | Clean fit for FastAPI `Depends()` yield pattern |
| `get_connection()` | WAL mode + foreign_keys, NO busy_timeout | Must add `PRAGMA busy_timeout=5000` |
| `load_config()` | Calls `sys.exit(1)` on validation error | Must refactor or wrap for API use (sys.exit kills uvicorn) |
| Python version | 3.12+ (pyproject.toml) | Compatible with FastAPI 0.135.x |
| Existing deps | pydantic 2.12.5+, httpx 0.28+ | httpx already available for TestClient |
| No Makefile | Does not exist yet | Must create from scratch |
| No `src/api/` | Does not exist yet | Must create entire directory structure |

## Open Questions

1. **`load_config()` calls `sys.exit(1)` on validation error**
   - What we know: Current config loading exits the process on bad config. In a web server, this kills uvicorn.
   - What's unclear: Whether to refactor `load_config()` or wrap it in a try/except in the API layer.
   - Recommendation: Create a `load_config_safe()` variant in deps.py that catches `SystemExit` and raises `HTTPException(500)` instead. Do not modify `load_config()` (CLI still needs it). Alternatively, call `_load_yaml()` + `_apply_env_overrides()` + `PipelineConfig(**raw)` directly, catching `ValidationError`.

2. **Summary list preview data: "top themes per date"**
   - What we know: CONTEXT.md specifies the list endpoint returns "meeting count, commitment count, top themes per date". Meeting count and commitment count are in the sidecar. Themes are not.
   - What's unclear: Where themes come from. The DailySidecar has no `themes` field.
   - Recommendation: For Phase 24, return meeting_count and commitment_count from sidecar data. Omit themes (or derive from entity_summary names if present). Flag as future enhancement.

3. **Concurrently vs Makefile parallel**
   - What we know: Both work. `concurrently` (npm package) provides colored output, process naming, and graceful shutdown. Makefile parallel (`make -j2`) is simpler but output interleaves.
   - Recommendation: Use `npx concurrently` in the Makefile `dev` target. Provides better DX without a global install.

## Sources

### Primary (HIGH confidence)
- Direct codebase analysis: `src/entity/db.py`, `src/entity/repository.py`, `src/sidecar.py`, `src/config.py`, `pyproject.toml`, `output/daily/` directory structure
- [FastAPI CORS documentation](https://fastapi.tiangolo.com/tutorial/cors/) -- CORS middleware ordering
- [FastAPI PyPI](https://pypi.org/project/fastapi/) -- v0.135.x confirmed current

### Secondary (MEDIUM confidence)
- [CORSMiddleware ordering discussion](https://github.com/fastapi/fastapi/discussions/7319) -- middleware order matters
- [SQLite concurrent writes](https://tenthousandmeters.com/blog/sqlite-concurrent-writes-and-database-is-locked-errors/) -- busy_timeout behavior
- [FastAPI best practices](https://github.com/zhanymkanov/fastapi-best-practices) -- project structure patterns
- Architecture research (`.planning/research/ARCHITECTURE.md`) -- verified against codebase
- Stack research (`.planning/research/STACK.md`) -- verified against codebase
- Pitfall research (`.planning/research/PITFALLS.md`) -- verified against codebase

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - FastAPI 0.135.x verified on PyPI, existing deps confirmed in pyproject.toml
- Architecture: HIGH - Pattern verified against actual codebase structure and existing Pydantic models
- Pitfalls: HIGH - Verified busy_timeout missing in db.py, sys.exit in load_config(), sidecar field mismatches confirmed

**Research date:** 2026-04-08
**Valid until:** 2026-05-08 (stable domain, no fast-moving dependencies)
