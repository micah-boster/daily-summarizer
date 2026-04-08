# Research Summary: v3.0 Web Interface

**Domain:** FastAPI backend + Next.js frontend for work intelligence pipeline
**Researched:** 2026-04-08
**Overall confidence:** HIGH

## Executive Summary

The v3.0 web interface adds a FastAPI JSON API and a Next.js frontend to the existing Python pipeline. The architecture is straightforward because the existing codebase is well-structured for this integration: Pydantic models that serialize directly to JSON responses, an EntityRepository with clean CRUD methods, JSON sidecars alongside markdown summaries, and a config system with built-in validation.

The critical design decision is the API boundary. The FastAPI backend is a **thin translation layer** -- it imports existing `src.*` modules and exposes their data as JSON. No pipeline logic moves into the API layer. Summary reads come from the existing JSON sidecar files. Entity operations wrap `EntityRepository` methods directly. Config reads and writes use the existing `PipelineConfig` Pydantic model for validation.

The one genuinely new capability is pipeline run management with real-time status streaming. FastAPI 0.135+ has native SSE support via `EventSourceResponse`, which is the right fit for unidirectional server-to-client status updates. The pipeline itself needs a minor modification: an optional status callback parameter in `async_pipeline()` so the API can stream progress events to the browser.

The monorepo structure is deliberately simple: `api/` (Python FastAPI) and `web/` (Next.js) as sibling directories in the existing project root. No Turborepo, no workspace tooling -- this is a single-developer project with one Python backend and one JS frontend. FastAPI and Uvicorn are added to the existing `pyproject.toml`; the frontend gets its own `package.json` in `web/`.

## Key Findings

**Stack:** FastAPI (>=0.135) + Next.js 15 + Tailwind CSS + React Query. Two new Python deps (fastapi, uvicorn). No ORM, no Redis, no Docker.

**Architecture:** Thin API facade over existing modules. API imports `src.entity.repository`, `src.entity.views`, `src.config`, `src.sidecar` models directly. Pipeline runs via subprocess or thread pool to avoid blocking the API event loop. SSE for pipeline status only.

**Critical pitfall:** Running the pipeline in-process blocks the API. Must isolate pipeline execution in a subprocess or thread pool. Second critical risk: SQLite "database is locked" without `busy_timeout` pragma.

## Implications for Roadmap

Based on research, suggested phase structure:

1. **FastAPI Skeleton + Summary API** - Foundation phase
   - Addresses: API app factory, CORS, dependency injection, summary read endpoints
   - Avoids: Building too much before proving the import/integration pattern works
   - Deliverable: `GET /api/summaries/{date}` returns real sidecar + markdown data

2. **Next.js Scaffold + Summary View** - First visible UI
   - Addresses: Three-column layout shell, daily summary rendering, date navigation
   - Avoids: Building entity UI before the layout pattern is proven
   - Deliverable: Browse daily summaries in the browser

3. **Entity API + Entity Browser UI** - Entity read path
   - Addresses: Entity list, scoped views, activity indicators in nav
   - Avoids: Write operations before reads are solid
   - Deliverable: Click entity in nav, see scoped view in center panel

4. **Entity Management UI** - Entity write path
   - Addresses: CRUD, merge proposals, alias management
   - Avoids: N/A (depends on entity read path)
   - Deliverable: Full entity management from browser

5. **Pipeline Run Management** - Pipeline triggers + SSE
   - Addresses: Run trigger, SSE status streaming, run history
   - Avoids: Premature SSE complexity; built last because it is the most complex new capability
   - Deliverable: Trigger pipeline run from browser, watch progress in real time

6. **Config Management + Polish** - Config UI + activity highlights + keyboard nav
   - Addresses: Config viewer/editor, quality dashboard, keyboard shortcuts
   - Avoids: Over-polishing before core features work
   - Deliverable: Full v3.0 feature set

**Phase ordering rationale:**
- Summary API first because it validates the core integration pattern (API reads existing files) with minimal new code
- Summary UI second because it provides the daily use case immediately (browse summaries in browser)
- Entity reads before writes because the entity list/nav drives the three-column layout design
- Pipeline management last because it is the most complex (SSE, subprocess isolation, status tracking) and least frequently used
- Config management deferred because config changes are rare and the CLI works fine for now

**Research flags for phases:**
- Phase 5 (Pipeline Run): Needs deeper research on subprocess vs thread pool isolation, status communication mechanism, and error recovery for failed runs
- Phase 6 (Config): Needs validation that Pydantic error formatting translates well to a form-based UI
- Phases 1-4: Standard patterns, unlikely to need additional research

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | FastAPI + Next.js is a well-established combo; all libraries are mature |
| Features | HIGH | Feature list derived directly from PROJECT.md requirements and existing CLI capabilities |
| Architecture | HIGH | API boundary design validated by examining actual data shapes in sidecar.py, entity/views.py, config.py |
| Pitfalls | HIGH | SQLite concurrency and event loop blocking are well-documented concerns with known mitigations |

## Gaps to Address

- **Pipeline subprocess isolation:** Exact mechanism (subprocess.Popen vs asyncio.create_subprocess_exec vs thread pool) needs prototyping during Phase 5. The right choice depends on how `async_pipeline()` communicates status.
- **Run history persistence:** In-memory run tracking is fragile. Phase 5 should decide whether to add a `pipeline_runs` SQLite table or a simple JSON log file.
- **Authentication:** Out of scope for v3.0 (localhost-only), but the API router structure should make it easy to add auth middleware later (v5.0 multi-user).
- **Sidecar coverage:** Older summaries (pre-sidecar) may not have JSON files. The summary API needs a graceful fallback for markdown-only dates.

## Sources

- [FastAPI SSE documentation](https://fastapi.tiangolo.com/tutorial/server-sent-events/)
- [FastAPI + Next.js monorepo patterns (Vinta Software)](https://www.vintasoftware.com/blog/nextjs-fastapi-monorepo)
- [Full-stack type safety with FastAPI + OpenAPI](https://abhayramesh.com/blog/type-safe-fullstack)
- [SQLite WAL mode documentation](https://www.sqlite.org/wal.html)
- [SQLite concurrent writes](https://tenthousandmeters.com/blog/sqlite-concurrent-writes-and-database-is-locked-errors/)
- [FastAPI best practices](https://github.com/zhanymkanov/fastapi-best-practices)
- Direct codebase analysis: src/entity/repository.py, src/entity/views.py, src/entity/models.py, src/pipeline_async.py, src/config.py, src/sidecar.py, src/models/events.py, src/main.py, src/entity/db.py
