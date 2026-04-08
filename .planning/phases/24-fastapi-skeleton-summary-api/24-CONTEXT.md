# Phase 24: FastAPI Skeleton + Summary API - Context

**Gathered:** 2026-04-08
**Status:** Ready for planning

<domain>
## Phase Boundary

API foundation phase: FastAPI app factory with CORS, dependency injection, summary read endpoints, and SQLite hardening. Proves the integration pattern (API imports `src.*` modules directly) before any UI is built. Also scaffolds an empty Next.js project so the Makefile and CORS can be validated end-to-end.

</domain>

<decisions>
## Implementation Decisions

### API Structure
- API code lives at `src/api/` (inside the existing src package for clean imports of src.entity, src.config, etc.)
- Versioned URL prefix: `/api/v1/summaries`, `/api/v1/entities`, etc.
- One router per domain: `summaries.py`, `entities.py`, `pipeline.py`, `config.py` (4 files, only summaries implemented in Phase 24)
- OpenAPI docs enabled at `/docs` (Swagger UI) for debugging and testing

### Summary Response Shape
- `GET /api/v1/summaries/{date}` returns a combined response: structured sidecar data AND markdown body in a single JSON response
- Summary list endpoint (`GET /api/v1/summaries`) returns dates with previews: meeting count, commitment count, top themes per date
- Sidecar scope: Claude's discretion on how much of SidecarOutput to expose vs curate

### Project Bootstrapping
- Makefile with `make dev` starts both FastAPI (uvicorn) and Next.js (pnpm dev) via concurrently or similar
- pnpm as the JS package manager (faster installs, strict deps, handles React 19 peer deps)
- Phase 24 scaffolds both: FastAPI API + empty Next.js project in `web/` so CORS integration is testable end-to-end
- Next.js scaffold is minimal (layout shell only) — real UI is Phase 25

### Error & Fallback Behavior
- Dates with markdown but no JSON sidecar: return markdown body with structured fields as null/empty (graceful degradation for pre-sidecar dates)
- Invalid dates: 422 Unprocessable Entity with Pydantic validation error message
- Rich `/api/v1/status` endpoint: returns DB connectivity, last pipeline run date, summary count — useful for debugging and future dashboard status bar

### Claude's Discretion
- Exact fields in the curated summary response model (which sidecar fields to include/exclude)
- Concurrently vs Makefile parallel targets for `make dev`
- Exact FastAPI dependency injection pattern for config and DB connections
- Test strategy (pytest with httpx TestClient)

</decisions>

<specifics>
## Specific Ideas

- All API endpoints must import from `src.*` modules — grep for `sqlite3` in api/ should return nothing
- SQLite connections need `busy_timeout=5000` added to the existing `get_connection()` in `src/entity/db.py`
- CORS middleware must be added first (before other middleware) allowing localhost:3000
- The Next.js scaffold in web/ should use App Router, TypeScript, Tailwind, and shadcn/ui setup

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 24-fastapi-skeleton-summary-api*
*Context gathered: 2026-04-08*
