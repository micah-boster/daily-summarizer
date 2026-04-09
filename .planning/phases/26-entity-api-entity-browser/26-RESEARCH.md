# Phase 26: Entity API + Entity Browser - Research

**Researched:** 2026-04-08
**Domain:** FastAPI entity endpoints + Next.js entity browser UI
**Confidence:** HIGH

## Summary

Phase 26 adds entity browsing to the existing three-column layout. The backend work is straightforward: new FastAPI router importing from the existing `src.entity.repository` and `src.entity.views` modules (which already provide `get_enriched_entity_list`, `get_entity_scoped_view`, and `score_significance`). The frontend adds a tab switcher to the left nav (Summaries/Entities), an entity list with grouped/filtered/sorted items, an entity scoped view for the center panel, and a context-aware right sidebar that swaps between summary metadata and entity details.

The existing codebase already has the data layer fully built. `EntityRepository` provides `list_entities`, `get_entity_stats`, `list_aliases`, `resolve_name`, `get_entity_mentions_in_range`. `views.py` provides `EnrichedEntity`, `EntityScopedView`, `ActivityItem`, and `get_enriched_entity_list` with filtering and sorting. The API dependency `get_entity_repo()` already exists in `deps.py`. The frontend patterns (TanStack Query hooks, Zustand store, shadcn components, DateGroup collapsible pattern) are all established from Phase 25.

**Primary recommendation:** Follow the exact patterns from Phase 24/25 -- new FastAPI router for entities, new TanStack Query hooks, new components following the existing DateGroup/card/section pattern. Zero new libraries needed.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Tab switcher at top of left nav: "Summaries" | "Entities" -- switches entire nav content between date navigation (Phase 25) and entity browser
- Entities grouped by type: Partners, People, Initiatives -- using the same expandable DateGroup pattern from Phase 25, with counts per group
- Sort dropdown (Activity | Name) and type filter chips below the tab switcher, always visible, compact
- Activity indicator: small green dot next to entity name for entities active in the last 7 days (Slack/Linear pattern)
- Header + stacked sections layout: entity name/type header at top, then Highlights, Open Commitments, Activity Timeline sections. Same scroll behavior as summary view
- Highlights section: key stats (total mentions, days active, last seen date) plus 2-3 most recent themes/topics associated with the entity
- Activity timeline: vertical timeline grouped by day, newest first. Each entry shows date, source type icon, brief description, significance score badge
- Significance scoring: subtle colored badges -- "High" (red/orange), "Medium" (yellow), "Low" (gray). Scannable without being noisy
- Context-aware swap: sidebar content changes based on what's selected -- summary metadata for daily view, entity details for entity view. Header updates to match
- Entity sidebar prioritizes identity + relationships: entity type, aliases as muted tags under name (read-only), metadata, then related entities below, then organization linkage
- Related entities displayed as clickable chips with co-mention count. Clicking navigates to that entity
- Aliases shown as small muted tag list below entity name (editing deferred to Phase 27)
- Inline expand: clicking a timeline mention expands the entry in place to reveal source evidence. Click again to collapse. No navigation away
- Expanded evidence shows: original text snippet where entity was mentioned, source type icon (Slack/Meeting/HubSpot/etc), date, confidence score badge
- Confidence score: percentage badge (e.g. "92%") with color coding -- green >80%, yellow 50-80%, red <50%
- "View in summary" link at bottom of expanded evidence navigates to the daily summary for that date (switches to Summaries tab + selects the date)

### Claude's Discretion
- API endpoint design (REST paths, response shapes)
- Entity data fetching strategy (TanStack Query patterns)
- Exact icon choices for source types
- Animation/transition for sidebar context swap
- Empty state design for entities with no activity

### Deferred Ideas (OUT OF SCOPE)
- Entity CRUD (create/edit/delete) -- Phase 27
- Merge proposal review UI -- Phase 27
- Alias management (add/remove) -- Phase 27
- Entity search/command palette -- Phase 27
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| NAV-02 | Left nav shows entities grouped by type with activity indicators | Tab switcher + DateGroup pattern reuse + EnrichedEntity.last_active_date for 7-day dot |
| NAV-03 | Selecting an entity in left nav opens its scoped view in center panel | get_entity_scoped_view() already returns EntityScopedView with all needed data |
| NAV-04 | Context sidebar adapts to selection: related items, source evidence, timeline | Sidebar swap pattern: lift "activeView" state to page level, pass different content to RightSidebar |
| ENT-01 | User can browse entity list with filtering by type and sorting by activity/name | get_enriched_entity_list(entity_type, sort_by) already supports this |
| ENT-02 | Entity scoped view shows highlights, open commitments, activity timeline with significance scoring | EntityScopedView model has highlights, open_commitments, activity_by_date; score_significance() built |
| ENT-05 | Source evidence drill-down -- click a mention to see original context snippet with source type and confidence | ActivityItem.context_snippet + confidence field; collapsible expand pattern |
</phase_requirements>

## Standard Stack

### Core (Already Installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.135+ | Entity API endpoints | Already used for summary endpoints in Phase 24 |
| Pydantic | v2 | Response models for entity data | Already used in src/entity/models.py and src/api/models/responses.py |
| Next.js | 16.2.3 | Frontend framework | Already installed |
| TanStack Query | 5.96+ | Entity data fetching + caching | Already used for summary hooks in use-summaries.ts |
| Zustand | 5.0+ | UI state (active tab, selected entity) | Already used for ui-store.ts |
| shadcn/ui + Tailwind 4 | Latest | UI components | Already used throughout Phase 25 components |
| lucide-react | 1.7+ | Icons for source types and nav | Already installed |
| date-fns | 4.1+ | Date formatting for activity timeline | Already installed |

### No New Dependencies Required
Everything needed is already in the project. No new npm packages or Python packages.

## Architecture Patterns

### Backend: New Router Pattern (Follow Summaries Router)
```
src/api/
├── routers/
│   ├── summaries.py       # Existing (Phase 24)
│   └── entities.py        # NEW -- entity list, scoped view, related entities
├── models/
│   └── responses.py       # ADD entity response models here
└── deps.py                # get_entity_repo() ALREADY EXISTS
```

Entity router follows the exact same pattern as summaries router:
- Import `get_entity_repo` from deps (connection-per-request, already built)
- Import from `src.entity.views` for business logic (never duplicate SQL)
- Return Pydantic response models

### Backend: Recommended Endpoints
```
GET /api/v1/entities                    → list with type filter + sort
GET /api/v1/entities/{entity_id}        → scoped view (highlights, commitments, timeline)
GET /api/v1/entities/{entity_id}/related → related entities with co-mention counts
```

Query parameters for list: `?type=partner&sort=activity` (matching get_enriched_entity_list args)

### Frontend: Tab-Based Navigation State
```
web/src/
├── components/
│   ├── nav/
│   │   ├── entity-list.tsx         # NEW -- entity nav items grouped by type
│   │   ├── entity-list-item.tsx    # NEW -- single entity nav item with activity dot
│   │   ├── entity-filter-bar.tsx   # NEW -- sort dropdown + type filter chips
│   │   └── nav-tab-switcher.tsx    # NEW -- Summaries | Entities tabs
│   ├── entity/
│   │   ├── entity-scoped-view.tsx  # NEW -- center panel for entity
│   │   ├── entity-header.tsx       # NEW -- name/type header
│   │   ├── highlights-section.tsx  # NEW -- key stats + recent themes
│   │   ├── commitments-section.tsx # NEW -- open commitments list
│   │   ├── activity-timeline.tsx   # NEW -- vertical timeline grouped by day
│   │   ├── timeline-entry.tsx      # NEW -- single timeline item, expandable
│   │   └── evidence-panel.tsx      # NEW -- expanded source evidence
│   └── layout/
│       ├── left-nav.tsx            # MODIFY -- add tab switcher, conditional rendering
│       ├── right-sidebar.tsx       # MODIFY -- context-aware swap
│       └── entity-sidebar.tsx      # NEW -- entity details sidebar content
├── hooks/
│   └── use-entities.ts             # NEW -- TanStack Query hooks for entity endpoints
├── lib/
│   └── types.ts                    # MODIFY -- add entity TypeScript types
└── stores/
    └── ui-store.ts                 # MODIFY -- add activeTab, selectedEntityId
```

### State Management Pattern
The key architectural decision is lifting the "active view" concept to the page level:

```typescript
// ui-store.ts additions
activeTab: "summaries" | "entities"   // which left-nav tab is active
selectedEntityId: string | null       // currently selected entity
setActiveTab: (tab) => void
selectEntity: (id) => void
```

`page.tsx` conditionally renders center panel content and passes different data to the right sidebar based on `activeTab`. This follows the existing pattern where `selectedType` already switches between daily/weekly/monthly views.

### Anti-Patterns to Avoid
- **Direct SQL in API router:** Entity endpoints MUST import from `src.entity.repository` and `src.entity.views` -- the pitfall warnings in the roadmap are explicit about this
- **Duplicating entity models:** Use existing `Entity`, `EnrichedEntity`, `EntityScopedView` from `src.entity` -- create thin Pydantic response models that serialize them
- **N+1 queries for related entities:** The `get_entity_stats` call inside `get_enriched_entity_list` is already N+1 for the list endpoint but acceptable for <100 entities. For related entities endpoint, batch if possible
- **Over-engineering the tab switcher:** This is a simple conditional render in LeftNav, not a router change. Both tabs share the same page route

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Significance scoring | Custom algorithm | `views.score_significance()` | Already built with decision/commitment/recency weights |
| Entity list enrichment | Manual SQL aggregation | `views.get_enriched_entity_list()` | Already handles type filter, sort, mention stats |
| Entity scoped view | Custom query + assembly | `views.get_entity_scoped_view()` | Returns highlights, commitments, activity_by_date |
| Collapsible sections | Custom disclosure component | shadcn Collapsible (already installed) | Used for DateGroup in Phase 25 |
| Activity dot logic | Custom component | Compare `last_active_date` to 7-day threshold | Simple date comparison, not a component |
| Confidence color coding | Complex logic | Simple threshold: green >80%, yellow 50-80%, red <50% | Three CSS classes, no library needed |

## Common Pitfalls

### Pitfall 1: Entity Not Found Handling
**What goes wrong:** API returns 500 instead of 404 when entity doesn't exist
**Why it happens:** `get_entity_scoped_view` raises `ValueError`, not caught by FastAPI
**How to avoid:** Wrap `ValueError` from views.py in HTTPException(404) in the router
**Warning signs:** Stack traces in browser console for deleted/merged entities

### Pitfall 2: Related Entities Query Missing
**What goes wrong:** CONTEXT.md specifies related entities with co-mention counts, but `src.entity.repository` doesn't have a `get_related_entities` method
**Why it happens:** Related entities (co-mentions) require a SQL query joining entity_mentions on source_date + source_id
**How to avoid:** Add a `get_related_entities(entity_id)` method to EntityRepository that queries co-mentions, then expose via API endpoint
**Warning signs:** Empty related entities section in sidebar

### Pitfall 3: Tab Switcher Breaking Date Navigation
**What goes wrong:** Switching tabs loses the selected date or entity selection
**Why it happens:** State reset when toggling between Summaries and Entities
**How to avoid:** Keep both `selectedDate` and `selectedEntityId` in store independently; only clear on explicit user action
**Warning signs:** Losing place when switching tabs

### Pitfall 4: Sidebar Flash on View Switch
**What goes wrong:** Right sidebar briefly shows empty state when switching between summary and entity views
**Why it happens:** New query starts loading while old content is unmounted
**How to avoid:** Use `keepPreviousData: true` in TanStack Query options, or hold previous sidebar content during transition
**Warning signs:** Flash of empty sidebar when clicking between entity and summary

### Pitfall 5: Large Entity Lists Without Pagination
**What goes wrong:** Slow load for entity list endpoint
**Why it happens:** `get_enriched_entity_list` calls `get_entity_stats` per entity (N+1)
**How to avoid:** For Phase 26, acceptable if entity count is <500. Add a `limit` parameter as escape hatch. Optimize in future if needed
**Warning signs:** >500ms response time on entity list endpoint

## Code Examples

### FastAPI Entity Router Pattern
```python
# src/api/routers/entities.py
from fastapi import APIRouter, Depends, HTTPException, Query
from src.api.deps import get_entity_repo
from src.entity.repository import EntityRepository
from src.entity.views import get_enriched_entity_list, get_entity_scoped_view

router = APIRouter(prefix="/entities", tags=["entities"])

@router.get("")
def list_entities(
    type: str | None = Query(None),
    sort: str = Query("activity"),
    repo: EntityRepository = Depends(get_entity_repo),
):
    return get_enriched_entity_list(repo, entity_type=type, sort_by=sort)

@router.get("/{entity_id}")
def get_entity_view(
    entity_id: str,
    repo: EntityRepository = Depends(get_entity_repo),
):
    entity = repo.get_by_id(entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    try:
        return get_entity_scoped_view(repo, entity.name)
    except ValueError:
        raise HTTPException(status_code=404, detail="Entity not found")
```

### TanStack Query Hook Pattern
```typescript
// web/src/hooks/use-entities.ts
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export function useEntityList(type?: string, sort?: string) {
  const params = new URLSearchParams();
  if (type) params.set("type", type);
  if (sort) params.set("sort", sort);
  const qs = params.toString();
  return useQuery({
    queryKey: ["entities", type, sort],
    queryFn: () => apiFetch(`/entities${qs ? `?${qs}` : ""}`),
    staleTime: 5 * 60 * 1000,
  });
}
```

### Activity Indicator Dot Pattern
```typescript
// 7-day activity check
const isRecentlyActive = (lastActiveDate: string | null): boolean => {
  if (!lastActiveDate) return false;
  const daysSince = differenceInDays(new Date(), parseISO(lastActiveDate));
  return daysSince <= 7;
};

// Render: small green dot
{isRecentlyActive(entity.last_active_date) && (
  <span className="h-2 w-2 rounded-full bg-green-500" />
)}
```

### Confidence Badge Pattern
```typescript
function ConfidenceBadge({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100);
  const color = pct > 80 ? "bg-green-100 text-green-700"
    : pct > 50 ? "bg-yellow-100 text-yellow-700"
    : "bg-red-100 text-red-700";
  return (
    <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${color}`}>
      {pct}%
    </span>
  );
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| CLI entity reports | Web entity browser | Phase 26 (now) | Visual, interactive entity browsing replaces markdown reports |
| Static sidebar | Context-aware sidebar | Phase 26 (now) | Sidebar adapts to show entity details or summary metadata |

## Open Questions

1. **Related entities co-mention query**
   - What we know: CONTEXT.md specifies "related entities with co-mention count" as clickable chips
   - What's unclear: `EntityRepository` doesn't have a `get_related_entities` method; need to add one
   - Recommendation: Add a new method to repository that joins entity_mentions to find entities that share the same source_date/source_id. Keep it simple -- top 10 by co-mention count.

2. **"Themes/topics" for highlights section**
   - What we know: CONTEXT.md mentions "2-3 most recent themes/topics associated with the entity"
   - What's unclear: Entity mentions don't have a "theme" or "topic" field; the closest is `source_type` (substance/decision/commitment)
   - Recommendation: For Phase 26, show top source types as "themes" (e.g., "Decisions", "Commitments") with counts. True topic extraction can be a future enhancement.

## Sources

### Primary (HIGH confidence)
- Existing codebase: `src/entity/repository.py`, `src/entity/views.py`, `src/entity/models.py` -- direct code review
- Existing codebase: `src/api/deps.py`, `src/api/routers/summaries.py`, `src/api/app.py` -- established patterns
- Existing codebase: `web/src/` -- all Phase 25 components, hooks, stores, types

### Secondary (MEDIUM confidence)
- Phase 25 CONTEXT.md and plans -- established UI patterns and component conventions

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- everything is already installed, zero new deps
- Architecture: HIGH -- following established Phase 24/25 patterns exactly
- Pitfalls: HIGH -- identified from code review of existing modules

**Research date:** 2026-04-08
**Valid until:** 2026-05-08 (stable -- internal project, no external API changes)
