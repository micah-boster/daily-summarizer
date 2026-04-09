# Requirements: Work Intelligence System v3.0

**Defined:** 2026-04-08
**Core Value:** Every morning I open a structured daily summary of yesterday's work and find it accurate, useful, and worth 5 minutes of my time -- now in a polished web UI instead of markdown files.

## v3.0 Requirements

### API Foundation

- [ ] **API-01**: FastAPI backend serves JSON API on localhost:8000 with CORS for localhost:3000
- [ ] **API-02**: SQLite connections use busy_timeout and connection-per-request pattern for safe concurrent access
- [ ] **API-03**: API imports existing `src.*` modules directly -- zero business logic duplication in API layer

### Summary Browsing

- [ ] **SUM-01**: User can view daily summary (structured data + rendered markdown) for any available date
- [ ] **SUM-02**: User can navigate between dates (prev/next, date picker) with graceful handling of missing dates
- [ ] **SUM-03**: Summary index endpoint returns available dates so navigation skips gaps
- [ ] **SUM-04**: Weekly and monthly roll-up summaries are browsable alongside daily summaries

### Layout & Navigation

- [ ] **NAV-01**: Three-column layout: entity nav (left), content panel (center), context sidebar (right)
- [x] **NAV-02**: Left nav shows entities grouped by type (partners, people, initiatives) with activity indicators
- [x] **NAV-03**: Selecting an entity in left nav opens its scoped view in center panel
- [x] **NAV-04**: Context sidebar adapts to selection: related items, source evidence, timeline
- [x] **NAV-05**: Command palette (Cmd+K) for keyboard-first entity search, date jump, and action triggers

### Entity Management

- [x] **ENT-01**: User can browse entity list with filtering by type and sorting by activity/name
- [x] **ENT-02**: Entity scoped view shows highlights, open commitments, activity timeline with significance scoring
- [x] **ENT-03**: User can create, edit, and delete entities and their aliases from the browser
- [x] **ENT-04**: Merge proposal review UI with side-by-side comparison, similarity score, approve/reject
- [x] **ENT-05**: Source evidence drill-down -- click a mention to see original context snippet with source type and confidence

### Pipeline Operations

- [ ] **PIPE-01**: User can trigger a pipeline run from the browser and receive real-time status via SSE
- [ ] **PIPE-02**: Pipeline runs execute in isolation (subprocess/thread) -- never block the API server
- [ ] **PIPE-03**: Run history is visible with status, duration, and date processed

### Config Management

- [ ] **CFG-01**: User can view current pipeline config (sources, channels, priorities) in the browser
- [ ] **CFG-02**: User can edit config with full Pydantic validation -- invalid configs are rejected with structured errors
- [ ] **CFG-03**: Config writes are atomic (temp file + rename) with backup of previous version

### Quality & Polish

- [ ] **UX-01**: Dark mode with system preference detection and manual toggle
- [ ] **UX-02**: Keyboard navigation across all three columns (j/k list traversal, h/l column focus, Enter/Esc)
- [ ] **UX-03**: Loading skeletons per panel, error boundaries per column, toast notifications for actions
- [ ] **UX-04**: Design quality is demo-presentable -- consistent typography, spacing, and visual hierarchy

## v4.0 Requirements (Deferred)

### Action Layer

- **ACT-01**: System proposes draft responses based on commitments and follow-ups
- **ACT-02**: Draft review queue with approve/edit/reject/snooze
- **ACT-03**: Send approved drafts via Gmail API and Slack API
- **ACT-04**: Audit log of everything sent

### Commitment Tracking

- **CMIT-01**: Cross-entity commitment tracker view with owner, deadline, source
- **CMIT-02**: Overdue commitment alerts

## Out of Scope

| Feature | Reason |
|---------|--------|
| Authentication | Localhost-first personal tool; auth is v5.0+ (multi-user) |
| Real-time WebSocket | Pipeline runs once daily; SSE for run status, polling for everything else |
| Mobile-responsive layout | Desktop tool; three-column layout needs min 1024px |
| Inline summary editing | Violates evidence-only constraint; summaries are LLM-generated |
| Entity relationship graph | Over-engineered per PROJECT.md; co-mentions shown as flat list |
| Natural language chat | Known query patterns -> build views, not a chatbot |
| Run scheduling UI | Cron works; surface last/next run in status bar only |
| Auto-merge entities | False merges are catastrophic; always require explicit confirmation |
| GraphQL | Single consumer; REST + OpenAPI is simpler |
| ORM (SQLAlchemy) | Existing EntityRepository works; adding ORM adds complexity for zero benefit |
| Docker for dev | Localhost Python + Node is fine for personal tool |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| API-01 | Phase 24 | Pending |
| API-02 | Phase 24 | Pending |
| API-03 | Phase 24 | Pending |
| SUM-01 | Phase 25 | Pending |
| SUM-02 | Phase 25 | Pending |
| SUM-03 | Phase 24 | Pending |
| SUM-04 | Phase 25 | Pending |
| NAV-01 | Phase 25 | Pending |
| NAV-02 | Phase 26 | Complete |
| NAV-03 | Phase 26 | Complete |
| NAV-04 | Phase 26 | Complete |
| NAV-05 | Phase 27 | Complete |
| ENT-01 | Phase 26 | Complete |
| ENT-02 | Phase 26 | Complete |
| ENT-03 | Phase 27 | Complete |
| ENT-04 | Phase 27 | Complete |
| ENT-05 | Phase 26 | Complete |
| PIPE-01 | Phase 28 | Pending |
| PIPE-02 | Phase 28 | Pending |
| PIPE-03 | Phase 28 | Pending |
| CFG-01 | Phase 29 | Pending |
| CFG-02 | Phase 29 | Pending |
| CFG-03 | Phase 29 | Pending |
| UX-01 | Phase 29 | Pending |
| UX-02 | Phase 29 | Pending |
| UX-03 | Phase 25 | Pending |
| UX-04 | Phase 29 | Pending |

**Coverage:**
- v3.0 requirements: 27 total
- Mapped to phases: 27
- Unmapped: 0

---
*Requirements defined: 2026-04-08*
*Last updated: 2026-04-08 after roadmap creation*
