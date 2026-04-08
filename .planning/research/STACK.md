# Technology Stack

**Project:** Work Intelligence System v3.0 Web Interface
**Researched:** 2026-04-08

## Recommended Stack

### Frontend Core
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Next.js | 15.2.x (latest stable) | React framework, routing, SSR-capable | Stable LTS line; App Router mature; project specifies Next.js; avoid v16 (too new, breaking changes likely) |
| React | 19.x | UI library | Ships with Next.js 15; required for shadcn/ui compatibility |
| TypeScript | 5.x | Type safety | Non-negotiable for any non-trivial frontend; catches API contract drift early |

### Frontend UI
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| shadcn/ui | latest (CLI-installed) | Component library | Copy-paste components, no runtime dependency, Tailwind-native, excellent for dashboards. Not an npm package -- CLI copies source into your project. Beats MUI (too heavy for personal tool) and Ant Design (opinionated styling). |
| Tailwind CSS | 4.x | Utility CSS | Ships with shadcn/ui; zero-config with Next.js 15; three-column layout trivial with grid utilities |
| Radix UI | (via shadcn/ui) | Accessible primitives | shadcn/ui is built on Radix; you get keyboard nav, ARIA, focus management for free |

### Frontend Data & State
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| TanStack Query | 5.96.x | Server state / data fetching | Caching, background refetch, mutation handling, devtools. 12M+ weekly downloads. The standard for REST API consumption in React 2026. |
| Zustand | 5.0.x | Client-side UI state | Lightweight (1.2KB), hook-based, no boilerplate. Perfect for: selected entity, active panel, sidebar state. Do NOT use Redux -- massive overkill for a personal tool. |

### Backend
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| FastAPI | 0.135.x | JSON API layer | Already in the Python ecosystem; Pydantic v2 native (matches existing models); auto-generates OpenAPI spec; async-capable |
| Uvicorn | 0.34.x | ASGI server | Standard FastAPI server; auto-reload in dev |

### Backend Database Access
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| sqlite3 (stdlib) | N/A | SQLite access from API | **Keep the existing sync `sqlite3` module.** Do NOT add SQLAlchemy or aiosqlite. Rationale below. |

### Dev Tooling
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| pnpm | 9.x | JS package manager | Faster installs, strict dependency resolution, handles React 19 peer deps without --legacy-peer-deps hack |
| @tanstack/react-query-devtools | 5.x | Query debugging | Invaluable during development; tree-shaken in production |

## Key Decision: SQLite Access Strategy

The existing codebase uses raw `sqlite3` with WAL mode, `sqlite3.Row` factory, and a clean `EntityRepository` class. The API layer should **wrap the existing repository, not replace it**.

**Use sync sqlite3 in FastAPI thread pool, NOT async aiosqlite. Here is why:**

1. **Existing code works.** `EntityRepository` is battle-tested. Rewriting it for async gains nothing -- SQLite is local disk I/O, not network I/O.
2. **WAL mode already enables concurrent reads.** Multiple API requests can read simultaneously.
3. **FastAPI handles sync gracefully.** Sync `def` endpoints (not `async def`) automatically run in a thread pool. No blocking.
4. **Adding SQLAlchemy/aiosqlite is over-engineering.** This is a personal tool with one concurrent user. The abstraction cost exceeds the benefit.

**Pattern:** Import `EntityRepository` directly in FastAPI dependency injection:

```python
from fastapi import Depends
from src.entity.repository import EntityRepository

def get_entity_repo() -> EntityRepository:
    repo = EntityRepository(db_path=settings.entity_db_path)
    repo.connect()
    try:
        yield repo
    finally:
        repo.close()

@app.get("/api/entities")
def list_entities(repo: EntityRepository = Depends(get_entity_repo)):
    return repo.list_entities()
```

## Key Decision: CORS Strategy

Use FastAPI's `CORSMiddleware` for development. Next.js rewrites are an alternative but add config complexity for no gain at localhost scale.

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
    allow_credentials=False,  # No auth needed for personal tool
)
```

**Production note:** When deploying, switch to explicit origin or use Next.js rewrites to proxy API calls (same-origin, no CORS needed).

## Key Decision: Three-Column Layout

Use CSS Grid via Tailwind, not a layout library. Three columns with responsive collapse:

```tsx
<div className="grid grid-cols-[280px_1fr_320px] h-screen">
  <aside>  {/* Entity/people nav */} </aside>
  <main>   {/* Content panel */}     </main>
  <aside>  {/* Context sidebar */}   </aside>
</div>
```

shadcn/ui provides `ScrollArea`, `ResizablePanelGroup` (via `react-resizable-panels`), `Sidebar` components that slot directly into this layout. No additional layout library needed.

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Component lib | shadcn/ui | MUI | MUI ships 300KB+ runtime; opinionated Material theme; overkill for personal tool |
| Component lib | shadcn/ui | Ant Design | Heavy bundle, CJK-first docs, enterprise-grade complexity unnecessary |
| Component lib | shadcn/ui | Tremor | Good for charts but too narrow; shadcn/ui covers full component needs |
| State (server) | TanStack Query | SWR | SWR is simpler but lacks mutation handling, devtools, and cache control needed for entity CRUD |
| State (client) | Zustand | Redux Toolkit | Redux ceremony (slices, reducers, dispatch) is absurd for UI state in a personal tool |
| State (client) | Zustand | Jotai | Jotai's atomic model is elegant but Zustand's single-store is simpler for the handful of UI states needed |
| DB access | Raw sqlite3 | SQLAlchemy + aiosqlite | Existing repo works; SQLAlchemy adds ORM complexity with no benefit for a 5-table SQLite DB |
| DB access | Raw sqlite3 | SQLModel | Tiangolo's SQLModel is FastAPI-native but requires model rewrite; existing Pydantic models + raw SQL is fine |
| Package manager | pnpm | npm | npm requires --legacy-peer-deps for React 19; pnpm handles it cleanly |
| CSS | Tailwind | CSS Modules | shadcn/ui requires Tailwind; fighting it adds friction |

## What NOT to Add (Over-Engineering Warnings)

| Temptation | Why to Resist |
|------------|---------------|
| **PostgreSQL** | SQLite is perfect for single-user. WAL mode handles concurrent API reads. Do not migrate. |
| **Redis / caching layer** | One user, local SQLite. Browser-side TanStack Query cache is sufficient. |
| **GraphQL** | REST is simpler for this use case. Entity relationships are shallow (no deep nesting). FastAPI auto-generates OpenAPI docs. |
| **Docker for dev** | Python + Node on localhost is fine. Docker adds startup time and debugging friction for a personal tool. |
| **Authentication** | Localhost-first personal tool. Add auth only if/when hosting remotely (v5.0+). |
| **WebSockets for real-time** | Pipeline runs are infrequent batch jobs. Polling or SSE for run status is sufficient. |
| **Prisma / Drizzle** | Frontend should not talk to the database. FastAPI is the data layer. |
| **tRPC** | Requires full-stack TypeScript. Backend is Python. Use REST + OpenAPI. |
| **Monorepo tooling (Turborepo, Nx)** | Two packages (frontend + existing Python). A simple directory structure suffices. |

## Project Structure (New Additions)

```
daily-summarizer/
  src/                    # Existing Python pipeline
    entity/               # Existing entity module
    api/                  # NEW: FastAPI application
      __init__.py
      main.py             # FastAPI app, CORS, lifespan
      routers/
        summaries.py      # Daily/weekly/monthly summary endpoints
        entities.py       # Entity CRUD, merge proposals
        pipeline.py       # Run triggers, history, config
      dependencies.py     # Shared deps (DB connection, config)
  web/                    # NEW: Next.js frontend
    src/
      app/                # App Router pages
      components/
        layout/           # Three-column shell
        entities/         # Entity browser, CRUD forms
        summaries/        # Summary viewer, temporal nav
        sidebar/          # Context panel
      lib/
        api.ts            # TanStack Query hooks + fetch wrappers
        store.ts          # Zustand store(s)
    package.json
    next.config.ts
    tailwind.config.ts
```

## Installation

```bash
# Backend (add to existing pyproject.toml dependencies)
pip install fastapi uvicorn

# Frontend (new web/ directory)
pnpm create next-app@latest web --typescript --tailwind --eslint --app --src-dir
cd web
pnpm dlx shadcn@latest init
pnpm add @tanstack/react-query zustand
pnpm add -D @tanstack/react-query-devtools
```

## Confidence Assessment

| Decision | Confidence | Basis |
|----------|------------|-------|
| Next.js 15.2.x | HIGH | Official docs, stable release, LTS |
| shadcn/ui + Tailwind | HIGH | Ecosystem consensus, official Next.js integration |
| TanStack Query v5 | HIGH | npm downloads, community standard |
| Zustand v5 | HIGH | npm data, appropriate for scope |
| FastAPI 0.135.x | HIGH | PyPI, Pydantic v2 compatibility confirmed |
| Raw sqlite3 over aiosqlite | HIGH | Based on reading actual codebase; WAL + thread pool is correct pattern |
| CORS over Next.js rewrites | MEDIUM | Both work; CORS is more explicit and debuggable |

## Sources

- [Next.js 15 stable](https://nextjs.org/blog/next-15) -- official blog
- [Next.js releases](https://github.com/vercel/next.js/releases) -- GitHub
- [FastAPI on PyPI](https://pypi.org/project/fastapi/) -- v0.135.x confirmed
- [FastAPI CORS docs](https://fastapi.tiangolo.com/tutorial/cors/) -- official tutorial
- [shadcn/ui Next.js installation](https://ui.shadcn.com/docs/installation/next) -- official docs
- [TanStack Query releases](https://github.com/tanstack/query/releases) -- v5.96.x confirmed
- [Zustand on npm](https://www.npmjs.com/package/zustand) -- v5.0.12 confirmed
- [React component libraries 2026](https://www.builder.io/blog/react-component-libraries-2026) -- ecosystem survey
- [TanStack Query vs SWR comparison](https://www.pkgpulse.com/blog/tanstack-query-vs-swr-vs-apollo-2026) -- feature comparison
- [React state management 2026](https://www.c-sharpcorner.com/article/state-management-in-react-2026-best-practices-tools-real-world-patterns/) -- patterns overview
