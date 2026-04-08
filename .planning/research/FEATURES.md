# Feature Research

**Domain:** Personal work intelligence web dashboard (v3.0 UI layer for existing Python pipeline)
**Researched:** 2026-04-08
**Confidence:** HIGH -- Features derived from existing backend capabilities + established dashboard UX patterns

## Feature Landscape

### Table Stakes (Users Expect These)

Features the dashboard must have to justify replacing the CLI + markdown workflow. Missing any of these makes the web UI feel like a downgrade.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Daily summary as default view | Core value prop -- "what happened yesterday" must be the first thing visible on load | LOW | Reads existing `.md` + `.json` sidecar from `output/daily/YYYY/MM/`. Parse and render commitments table, substance bullets, decisions table, per-meeting extractions. Backend: file read endpoint. |
| Temporal navigation (day/week/month) | Without browsing backwards the dashboard shows one day and is useless | LOW | Date picker + prev/next arrows. Files already organized as `YYYY/MM/YYYY-MM-DD.{md,json}`. Weekly/monthly roll-ups exist in separate output dirs. Backend: date index endpoint listing available dates. |
| Entity nav sidebar (left column) | Three-column layout requires a navigable entity list as primary navigation | MEDIUM | `get_enriched_entity_list()` already returns entities with `mention_count`, `commitment_count`, `last_active_date`. Group by `EntityType` (partners, people, initiatives). Default sort by last-active. |
| Entity scoped view (center panel) | Clicking an entity must show its activity -- the whole point of entity-aware intelligence | MEDIUM | `get_entity_scoped_view()` returns `EntityScopedView` with highlights (top 5 by significance), open_commitments, activity_by_date. Direct API exposure of existing Pydantic model. |
| Context sidebar (right column) | Three-column layout demands adaptive contextual detail per selection | MEDIUM | Content varies: for entities show aliases, metadata, org linkage, HubSpot/Slack refs. For summaries show meeting list, source counts. All data exists in SQLite + JSON sidecar. |
| Activity indicators in nav | Users need to see which entities had recent activity without clicking through each one | LOW | `EnrichedEntity.last_active_date` already computed. Badge/dot on entities active in last 7 days. Color or size weight by `mention_count`. |
| Entity type filtering | 3 types (partner, person, initiative) -- users need to scope the nav list | LOW | `list_entities(entity_type=)` already supports filtering. Tab bar or filter chips at top of left sidebar. |
| Responsive content rendering | Summaries contain markdown tables, lists, bold text -- must render cleanly as HTML | LOW | Use a markdown renderer (react-markdown or similar). Commitments table, decisions table, substance bullets all have consistent heading hierarchy. |
| Loading states and error handling | SPA without loading feedback feels broken; API errors need graceful display | LOW | Skeleton loaders per panel. Error boundaries per column. Toast notifications for action results. |

### Differentiators (Competitive Advantage)

Features that elevate the dashboard from "markdown viewer" to "intelligence tool." These create genuine daily-use value beyond what the CLI provides.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Command palette (Cmd+K) | Keyboard-first navigation without mouse; Linear-style UX transforms daily speed. Search entities by name/alias, jump to any date, trigger pipeline actions -- all from keyboard. | MEDIUM | Needs a search/lookup API endpoint. Libraries like cmdk (pacocoursey/cmdk) provide the React component. |
| Merge proposal review UI | Merge proposals accumulate and currently require CLI to resolve. Side-by-side entity comparison with similarity score, one-click approve/reject is the highest-value CRUD operation. | MEDIUM | `MergeProposal` model, `generate_proposals()`, `execute_merge()`, and `reverse_merge()` all exist. Backend: expose as REST endpoints. |
| Source evidence drill-down | `EntityMention.context_snippet` stores the exact text that attributed an entity. Surfacing the original quote with source_type and confidence level builds trust in the system. | MEDIUM | Click a mention in the activity timeline to expand the snippet. Shows source_type (substance/decision/commitment), source_date, confidence float. |
| Pipeline run trigger + status | Manual pipeline runs from the browser instead of terminal. Shows the system is alive and controllable. | MEDIUM | `pipeline_async.py` has async pipeline. Needs FastAPI background task wrapper + status polling (no WebSocket needed -- poll every 5s during active run). Basic run history from output directory timestamps. |
| Commitment tracker view | Cross-entity view of all open commitments with owner, deadline, source meeting. Currently these are scattered across per-entity views. | MEDIUM | Commitments are `source_type="commitment"` mentions in entity_mentions table. Dedicated view: filter by person, sort by deadline, flag overdue items. High daily value for a manager. |
| Keyboard navigation | Arrow keys to traverse entity list, Enter to select, Esc to deselect. No mouse required for the daily review workflow. | MEDIUM | Focus management across three columns. j/k for list traversal, h/l for column focus. Requires deliberate focus trap design. |
| Dark mode | Personal tool used first thing in the morning. Dark mode is expected for developer-adjacent tools. | LOW | CSS custom properties + system preference detection + manual toggle. Trivial with Tailwind or CSS variables. |
| Config viewer/editor | View and edit pipeline YAML config from the browser. Currently requires local file editing. | HIGH | Pydantic config model (`config.py`) provides schema + validation. Needs: read endpoint, form generation from schema, write-back to YAML, validation error display, change diff. Most complex single feature. |
| Significance scoring visualization | Mentions already have significance scores (recency + type weighting + confidence). Visualize as heat/weight on activity items. | LOW | `score_significance()` returns float. `ActivityItem.significance_score` exists. Apply as font weight, color saturation, or size in the activity timeline. Subtle but useful signal. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Real-time WebSocket updates | Modern dashboards are "real-time" | Pipeline runs once daily as a batch. WebSocket adds connection management, reconnection logic, and state sync complexity for zero value on a batch system. | Poll run status every 5s only during active pipeline run. All other data is static until next run. |
| Multi-user authentication | "What if someone else wants to use it?" | Personal tool through v3.0 (PROJECT.md). Auth adds sessions, RBAC, password management, token refresh for exactly one user. | Localhost-first with no auth. Optional single API key env var for hosted deployment. |
| Drag-and-drop layout customization | "Let users arrange their dashboard" | Three-column layout IS the right layout for entity nav + content + context. Customization engineering (grid system, persistence, resize handles) is enormous for marginal value. | Fixed three-column with collapsible side panels. |
| Inline editing of summaries | "Let me fix mistakes in summaries" | Summaries are LLM-generated evidence. Editing breaks the evidence chain and violates the evidence-only constraint. Edited summaries become unreliable. | Read-only display. Fix issues at the source (config, pipeline prompts) or annotate. |
| Entity relationship graph | "Show how entities connect" | Out of scope per PROJECT.md: "over-engineered; relationships implicit via co-mentions." Graph viz libraries (d3-force, cytoscape) are heavy and the visualization rarely actionable. | Show co-mentioned entities as a flat list in the context sidebar with co-mention counts. |
| Sentiment analysis on entities | "How does the team feel about X?" | Explicitly violates PROJECT.md evidence-only constraint. Sentiment is evaluative, not evidentiary. | Surface raw mentions with confidence scores. Let the user interpret tone from context snippets. |
| Auto-merge entities | "Just merge obvious duplicates" | PROJECT.md: "false merges are catastrophic." Auto-merge on fuzzy signals (even at high thresholds) will eventually merge two distinct entities. | Always require explicit user confirmation via merge proposal review UI. |
| Mobile-responsive layout | "I want to check on my phone" | Localhost-first desktop tool. Three-column layout on a phone screen is a fundamentally different product requiring different navigation patterns. | Set min-width constraint (~1024px). Tablet landscape is fine. Phone layout is v5.0+ if ever. |
| Natural language chat interface | "Ask questions about my data" | Conversational BI is trendy but wrong for structured entity data with known query patterns. LLM latency on every interaction degrades the snappy dashboard feel. | Command palette for fast structured navigation. The data shapes are known -- build views, not a chatbot. |
| Run scheduling UI | "Schedule pipeline runs from the browser" | Cron works. Building a scheduler UI (cron expression builder, timezone handling, failure notifications) is a mini-product for something that runs once daily. | Keep scheduling in cron/launchd. Surface last-run time and next-scheduled-run in the dashboard status bar. |

## Feature Dependencies

```
Daily summary view
    +-- Temporal navigation (date picker drives summary loading)
    +-- Responsive content rendering (summaries contain markdown)

Entity nav sidebar
    +-- Entity type filtering (filter controls in sidebar)
    +-- Activity indicators (overlay on nav items)
    +-- Entity scoped view (selecting entity loads center panel)
        +-- Context sidebar (selection drives sidebar content)
        +-- Source evidence drill-down (expand mention in timeline)
        +-- Commitment tracker view (cross-entity variant)

Command palette
    +-- Entity nav sidebar (search results reference entities)
    +-- Temporal navigation (jump-to-date action)
    +-- Pipeline run trigger (action from palette)

Merge proposal review UI
    +-- Entity nav sidebar (proposals reference listed entities)
    +-- Entity scoped view (review needs entity detail)

Config editor
    +-- Pipeline run trigger (config changes affect runs)

Pipeline run trigger
    +-- Loading states (run progress needs indication)
```

### Dependency Notes

- **Entity scoped view requires Entity nav sidebar:** The center panel content is driven by left sidebar selection. Nav must exist first.
- **Context sidebar requires Entity scoped view:** Sidebar adapts to the current selection. Without a selection model, sidebar has nothing to show.
- **Command palette enhances all views:** It is a navigation accelerator, not a dependency. Build after core views work.
- **Config editor is independent but expensive:** Can be built in isolation but is the highest-complexity single feature. Defer unless pipeline config changes are frequent.

## MVP Definition

### Launch With (v1 -- Read-Only Intelligence)

Minimum viable dashboard that replaces the daily CLI workflow.

- [ ] Daily summary as default view -- the core value; render existing markdown/JSON output
- [ ] Temporal navigation -- prev/next day, date picker; browsing history is essential
- [ ] Entity nav sidebar -- left column with grouped, filterable entity list
- [ ] Entity scoped view -- click entity, see activity/commitments/highlights in center
- [ ] Context sidebar -- right column with metadata, aliases, related entities per selection
- [ ] Activity indicators -- dots/badges on entities with recent mentions

This is the "replaces CLI" threshold. Everything above is read-only against existing data.

### Add After Validation (v1.x -- Entity Management + Interactivity)

Features to add once the read-only shell is working and daily-driveable.

- [ ] Merge proposal review UI -- highest-value write operation; proposals pile up without UI
- [ ] Entity CRUD -- create, edit, delete entities and aliases from browser
- [ ] Command palette (Cmd+K) -- keyboard-first navigation; transforms daily speed
- [ ] Keyboard navigation -- j/k/h/l + Enter/Esc across columns
- [ ] Dark mode -- low effort, high daily comfort impact

### Future Consideration (v2+)

Features to defer until the core dashboard proves its value.

- [ ] Pipeline run trigger + status -- convenient but CLI works; add when config editor is ready
- [ ] Commitment tracker view -- valuable cross-entity view; depends on entity views being solid
- [ ] Config editor -- highest complexity feature; defer unless config changes become frequent
- [ ] Source evidence drill-down -- trust-building polish; add after activity timelines are stable
- [ ] Significance scoring visualization -- subtle enhancement; add as CSS polish pass

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Daily summary view | HIGH | LOW | P1 |
| Temporal navigation | HIGH | LOW | P1 |
| Entity nav sidebar | HIGH | MEDIUM | P1 |
| Entity scoped view | HIGH | MEDIUM | P1 |
| Context sidebar | HIGH | MEDIUM | P1 |
| Activity indicators | MEDIUM | LOW | P1 |
| Entity type filtering | MEDIUM | LOW | P1 |
| Loading states | MEDIUM | LOW | P1 |
| Responsive rendering | MEDIUM | LOW | P1 |
| Merge proposal review | HIGH | MEDIUM | P2 |
| Entity CRUD | HIGH | MEDIUM | P2 |
| Command palette | HIGH | MEDIUM | P2 |
| Keyboard navigation | MEDIUM | MEDIUM | P2 |
| Dark mode | MEDIUM | LOW | P2 |
| Pipeline run trigger | MEDIUM | MEDIUM | P3 |
| Commitment tracker | MEDIUM | MEDIUM | P3 |
| Config editor | MEDIUM | HIGH | P3 |
| Source evidence drill-down | LOW | MEDIUM | P3 |
| Significance visualization | LOW | LOW | P3 |

**Priority key:**
- P1: Must have for launch -- replaces CLI daily workflow
- P2: Should have -- adds write operations and power-user speed
- P3: Nice to have -- pipeline operations and polish

## Backend API Surface Required

The existing Python codebase provides all data access. The FastAPI layer wraps existing functions.

| Endpoint | Existing Backend Support | Gap |
|----------|------------------------|-----|
| `GET /summaries/{date}` | Files at `output/daily/YYYY/MM/YYYY-MM-DD.{md,json}` | File-reading API endpoint needed |
| `GET /summaries/dates` | Directory listing of `output/daily/` | Date index endpoint needed |
| `GET /entities` | `get_enriched_entity_list()` in `views.py` | Direct exposure |
| `GET /entities/{id}` | `repo.get_entity()` + `list_aliases()` + `get_entity_stats()` | Compose from existing methods |
| `GET /entities/{id}/view` | `get_entity_scoped_view()` in `views.py` | Direct exposure |
| `POST /entities` | `repo.add_entity()` in `repository.py` | Direct exposure |
| `PUT /entities/{id}` | `repo.update_entity()` in `repository.py` | Direct exposure |
| `DELETE /entities/{id}` | `repo.soft_delete_entity()` in `repository.py` | Direct exposure |
| `GET /merge-proposals` | `generate_proposals()` + `repo.list_merge_proposals()` | Direct exposure |
| `POST /merge-proposals/{id}/approve` | `execute_merge()` in `merger.py` | Direct exposure |
| `POST /merge-proposals/{id}/reject` | `repo.update_merge_proposal()` | Direct exposure |
| `POST /pipeline/run` | `pipeline_async.py` | Async task wrapper + status needed |
| `GET /pipeline/status` | N/A | New: track running pipeline state |
| `GET /config` | Pydantic config model loads from YAML | Read endpoint needed |
| `PUT /config` | Config model validates | Write-back to YAML (small gap) |
| `GET /search` | `repo.resolve_name()` does fuzzy lookup | Extend for command palette search |

Most API work is wrapping existing functions in FastAPI routes. The only meaningful gaps are: (1) pipeline run task management (async run + status polling), and (2) config write-back to YAML.

## Competitor Feature Analysis

| Feature | Linear | Notion | HubSpot CRM | Our Approach |
|---------|--------|--------|-------------|--------------|
| Navigation | Cmd+K command palette, keyboard-first | Sidebar tree nav, Cmd+K search | Left nav with entity types, search bar | Three-column with Cmd+K palette + keyboard nav |
| Detail views | Issue detail in center panel | Page view with blocks | Record detail with timeline sidebar | Entity scoped view with activity timeline |
| Context panel | Issue metadata sidebar (status, assignee, labels) | Page properties sidebar | Related records, activity timeline | Adaptive sidebar: aliases, metadata, co-mentions, source evidence |
| Activity tracking | Issue history, comments | Page history, comments | Contact/deal activity timeline | Entity mentions with source_type, confidence, significance score |
| Merge/dedup | N/A | N/A | Merge contacts with side-by-side | Merge proposal review with similarity score, approve/reject |
| Data entry | Minimal forms, keyboard shortcuts | Rich block editor | Full CRM forms | Read-mostly; entity CRUD and merge review only |

Our approach is closest to HubSpot's CRM entity detail pattern (entity list + detail + activity timeline) but stripped to essentials for a single-user intelligence tool. Linear's keyboard-first philosophy is the UX model to follow for interaction speed.

## Sources

- Dashboard design patterns: [UXPin Dashboard Design Principles](https://www.uxpin.com/studio/blog/dashboard-design-principles/), [Pencil & Paper Dashboard UX Patterns](https://www.pencilandpaper.io/articles/ux-pattern-analysis-data-dashboards), [5of10 Dashboard Design Best Practices](https://5of10.com/articles/dashboard-design-best-practices/)
- Command palette UX: [Command Palette UX Patterns (Medium/Bootcamp)](https://medium.com/design-bootcamp/command-palette-ux-patterns-1-d6b6e68f30c1), [Linear keyboard shortcuts](https://shortcuts.design/tools/toolspage-linear/)
- Master-detail pattern: [Oracle Alta UI Master-Detail Pattern](https://www.oracle.com/webfolder/ux/middleware/alta/patterns/masterdetail.html)
- CRM timeline patterns: [Dynamics 365 Timeline](https://stoneridgesoftware.com/configuring-the-timeline-in-the-unified-interface-crm/), [Zoho CRM Timeline](https://help.zoho.com/portal/en/kb/crm/manage-crm-data/timeline/articles/timeline-in-record-detail-page)
- Sidebar UX: [UX Planet Sidebar Best Practices](https://uxplanet.org/best-ux-practices-for-designing-a-sidebar-9174ee0ecaa2)
- Backend capabilities: Verified against existing codebase (`src/entity/views.py`, `src/entity/models.py`, `src/entity/repository.py`, `src/entity/merger.py`, `src/config.py`)

---
*Feature research for: Work Intelligence System v3.0 Web Interface*
*Researched: 2026-04-08*
