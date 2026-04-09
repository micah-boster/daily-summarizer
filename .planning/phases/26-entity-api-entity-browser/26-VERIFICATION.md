---
phase: 26-entity-api-entity-browser
verified: 2026-04-08T00:00:00Z
status: human_needed
score: 18/18 must-haves verified
human_verification:
  - test: "Click Entities tab in left nav -- entity list appears grouped by Partners/People/Initiatives with counts"
    expected: "Tab switcher toggles content; entity list renders with correct type grouping and entity counts"
    why_human: "Component renders correctly in code but actual rendering depends on live API data and browser layout"
  - test: "Verify green activity dots appear on recently active entities (active within 7 days)"
    expected: "Entities with last_active_date within 7 days of today show a green dot next to the name"
    why_human: "Date-comparison logic correct in code but requires live data to confirm dots render as expected"
  - test: "Use sort dropdown (Activity/Name) and type filter chips -- list updates correctly"
    expected: "Clicking sort buttons and type chips re-fetches/re-filters entity list; active state highlights correctly"
    why_human: "State updates and query params require running app to confirm correct re-render"
  - test: "Click an entity -- center panel shows entity scoped view with header, highlights, open commitments, and activity timeline"
    expected: "EntityScopedView renders all sections (header, highlights, commitments, activity timeline) for selected entity"
    why_human: "Visual rendering, loading states, and data population require live environment"
  - test: "Click a timeline entry -- it expands to show source evidence with confidence percentage badge (green/yellow/red)"
    expected: "TimelineEntry toggles expanded state; EvidencePanel shows full context with colored confidence badge"
    why_human: "Expandable interaction and badge color rendering requires browser"
  - test: "Click 'View in summary' in expanded evidence -- switches to Summaries tab and selects correct date"
    expected: "setActiveTab('summaries') called and handleSelectDaily(date) navigates to that date's summary"
    why_human: "Cross-view navigation flow requires end-to-end browser verification"
  - test: "Right sidebar shows entity details (type, aliases, related entity chips) when entity is selected"
    expected: "RightSidebar renders EntitySidebar with entity type, aliases, stats, and related entity chips"
    why_human: "Live data population and sidebar mode switching requires browser"
  - test: "Click a related entity chip in right sidebar -- navigates to that entity's scoped view"
    expected: "selectEntity(relatedEntity.entity_id) called; center panel updates to show new entity's scoped view"
    why_human: "Click handler wiring correct in code but interaction requires browser confirmation"
  - test: "Switch back to Summaries tab -- daily summary view works as before (regression)"
    expected: "Existing summary/rollup behavior fully unchanged; date navigation, weekly/monthly views still work"
    why_human: "Regression across full summary flow requires human verification"
---

# Phase 26: Entity API & Entity Browser Verification Report

**Phase Goal:** Entity API & Entity Browser -- entity list API, scoped entity view API, entity browser UI with tab switcher, grouping, filtering, evidence drill-down, and context-aware sidebar
**Verified:** 2026-04-08
**Status:** human_needed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | GET /api/v1/entities returns entity list with mention stats, filterable by type and sortable by activity or name | VERIFIED | `entities.py` lines 21-39: full implementation with `type` and `sort` query params; delegates to `get_enriched_entity_list` |
| 2  | GET /api/v1/entities/{entity_id} returns scoped view with highlights, open commitments, and activity timeline with significance scores | VERIFIED | `entities.py` lines 42-103: full mapping of all EntityScopedView fields including aliases |
| 3  | GET /api/v1/entities/{entity_id}/related returns co-mentioned entities with counts | VERIFIED | `entities.py` lines 106-125: validates entity, calls `repo.get_related_entities`, returns typed list |
| 4  | Activity indicator data is available -- each entity includes last_active_date for 7-day dot calculation | VERIFIED | `responses.py` line 92: `last_active_date: str \| None`; `entity-list-item.tsx` lines 19-21: `differenceInDays` check |
| 5  | Confidence scores and context snippets are included in activity timeline items | VERIFIED | `responses.py` lines 95-103: `ActivityItemResponse` has `confidence`, `significance_score`, `context_snippet` |
| 6  | 404 returned for non-existent entity IDs | VERIFIED | `entities.py` lines 49-50, 54-55: `get_by_id` null check + ValueError catch both raise `HTTPException(404)` |
| 7  | TypeScript types exist for entity list items, scoped view, activity items, and related entities | VERIFIED | `types.ts` lines 124-165: `EntityListItem`, `ActivityItemResponse`, `ActivityDay`, `EntityScopedViewResponse`, `RelatedEntityItem` all exported |
| 8  | TanStack Query hooks fetch entity list (with type/sort params), entity scoped view, and related entities | VERIFIED | `use-entities.ts`: three hooks with correct query keys, `enabled` guards, 5-min staleTime, typed generics |
| 9  | Zustand store tracks activeTab (summaries/entities) and selectedEntityId | VERIFIED | `ui-store.ts` lines 11-14: `activeTab`, `selectedEntityId`, `entityTypeFilter`, `entitySort` in interface; setters at lines 71-77 |
| 10 | Tab switching and entity selection state persists in sessionStorage | VERIFIED | `ui-store.ts` line 80: `name: "ui-state"` with zustand/persist (consistent with existing pattern) |
| 11 | Left nav shows Summaries/Entities tab switcher, and switching tabs swaps nav content | VERIFIED | `left-nav.tsx` lines 64, 67-165: `NavTabSwitcher` rendered; conditional blocks for `activeTab === "summaries"` and `activeTab === "entities"` |
| 12 | Entities tab shows entities grouped by type (Partners, People, Initiatives) with counts and expandable groups | VERIFIED | `entity-list.tsx`: `TYPE_GROUPS` with `DateGroup` reuse; grouping + count + `groupId` for expand state |
| 13 | Activity indicator green dot appears next to entities active in the last 7 days | VERIFIED | `entity-list-item.tsx` lines 19-38: `differenceInDays(new Date(), parseISO(...)) <= 7` + `bg-green-500` dot |
| 14 | Sort dropdown and type filter chips filter/sort the entity list | VERIFIED | `entity-filter-bar.tsx`: sort buttons bound to `setEntitySort`; type chips bound to `setEntityTypeFilter`; both from store |
| 15 | Clicking an entity in left nav loads its scoped view in the center panel | VERIFIED | `entity-list-item.tsx` line 25-27: `selectEntity(entity.entity_id)` + `setActiveTab("entities")`; `page.tsx` line 93: `showEntityView = activeTab === "entities" && selectedEntityId` routes to `EntityScopedView` |
| 16 | Entity scoped view shows header, highlights, open commitments, and activity timeline with significance badges | VERIFIED | `entity-scoped-view.tsx`: orchestrates `EntityHeader`, `HighlightsSection`, `CommitmentsSection`, `ActivityTimeline`; `timeline-entry.tsx` lines 59-72: `SignificanceBadge` with High/Medium/Low thresholds |
| 17 | Right sidebar shows entity details (aliases, metadata, related entities) when entity is selected | VERIFIED | `right-sidebar.tsx` lines 27-47: `showEntity` branch renders `EntitySidebar`; `entity-sidebar.tsx`: type, aliases, stats, related entity chips |
| 18 | Clicking a timeline entry expands to show source evidence with confidence badge; evidence panel has View in summary link | VERIFIED | `timeline-entry.tsx` line 22: `useState(false)` toggle; `evidence-panel.tsx` lines 44-51: `onViewInSummary` button; callback chain: `evidence-panel` → `timeline-entry` → `activity-timeline` → `entity-scoped-view` → `page.tsx` `handleViewInSummary` which calls `setActiveTab("summaries")` + `handleSelectDaily(date)` |

**Score:** 18/18 truths verified

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `src/api/routers/entities.py` | VERIFIED | 126 lines; full implementation; exports `router`; imports from `src.entity.views` and `src.entity.repository` |
| `src/api/models/responses.py` | VERIFIED | Contains `EntityListItem`, `ActivityItemResponse`, `ActivityDayResponse`, `EntityScopedViewResponse`, `RelatedEntityItem` |
| `src/entity/repository.py` | VERIFIED | `get_related_entities` method present at line 353 with co-mention SQL query |
| `web/src/lib/types.ts` | VERIFIED | All five entity types exported: `EntityListItem`, `ActivityItemResponse`, `ActivityDay`, `EntityScopedViewResponse`, `RelatedEntityItem` |
| `web/src/hooks/use-entities.ts` | VERIFIED | Exports `useEntityList`, `useEntityScopedView`, `useRelatedEntities`; correct patterns, staleTime, enabled guards |
| `web/src/stores/ui-store.ts` | VERIFIED | Contains `activeTab`, `selectedEntityId`, `entityTypeFilter`, `entitySort` with setters |
| `web/src/components/nav/nav-tab-switcher.tsx` | VERIFIED | 35 lines; reads `activeTab` from store, calls `setActiveTab` on click |
| `web/src/components/nav/entity-filter-bar.tsx` | VERIFIED | 66 lines; sort toggle + type filter chips bound to store setters |
| `web/src/components/nav/entity-list.tsx` | VERIFIED | 86 lines; groups by type using `DateGroup`, respects `entityTypeFilter`, loading skeleton |
| `web/src/components/nav/entity-list-item.tsx` | VERIFIED | 50 lines; activity dot calculation, selected state, `selectEntity` on click |
| `web/src/components/entity/entity-scoped-view.tsx` | VERIFIED | 87 lines; uses `useEntityScopedView`; loading/error states; orchestrates all sub-components |
| `web/src/components/entity/activity-timeline.tsx` | VERIFIED | 56 lines; groups by day with `border-l-2` vertical line; passes `onViewInSummary` through |
| `web/src/components/entity/timeline-entry.tsx` | VERIFIED | 77 lines; `useState` expand toggle; `SignificanceBadge` with correct thresholds (3.0/1.5); renders `EvidencePanel` |
| `web/src/components/entity/evidence-panel.tsx` | VERIFIED | 71 lines; `ConfidenceBadge` with 80%/50% thresholds; "View in summary" button calling `onViewInSummary` |
| `web/src/components/layout/entity-sidebar.tsx` | VERIFIED | 153 lines; entity type, aliases, stats, related entities via `useRelatedEntities`; chips call `selectEntity` |
| `web/src/components/layout/left-nav.tsx` | VERIFIED | Updated with `NavTabSwitcher` + conditional `EntityFilterBar`/`EntityList` for entities tab |
| `web/src/components/layout/right-sidebar.tsx` | VERIFIED | Updated with `activeTab`/`entityId` props; renders `EntitySidebar` or `SummaryMetadata` conditionally |
| `web/src/app/page.tsx` | VERIFIED | Reads `activeTab`, `selectedEntityId`; routes center panel to `EntityScopedView`; passes `activeTab`/`entityId` to `RightSidebar`; `handleViewInSummary` wires cross-link |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/api/routers/entities.py` | `src/entity/views` | `from src.entity.views import get_enriched_entity_list, get_entity_scoped_view` | WIRED | Line 16 of entities.py confirms exact import |
| `src/api/routers/entities.py` | `src/api/deps` | `Depends(get_entity_repo)` | WIRED | All three route functions use `repo: EntityRepository = Depends(get_entity_repo)` |
| `src/api/app.py` | `src/api/routers/entities` | `include_router.*entities_router` | WIRED | `app.py` line 8 imports router; line 30 `include_router(entities_router, prefix="/api/v1")` |
| `web/src/hooks/use-entities.ts` | `web/src/lib/api.ts` | `import.*apiFetch.*from.*@/lib/api` | WIRED | Line 2: `import { apiFetch } from "@/lib/api"` |
| `web/src/hooks/use-entities.ts` | `web/src/lib/types.ts` | `import.*EntityListItem.*from.*@/lib/types` | WIRED | Lines 3-7: named type imports from `@/lib/types` |
| `web/src/components/layout/left-nav.tsx` | `web/src/stores/ui-store.ts` | `useUIStore.*activeTab` | WIRED | Line 41: `const activeTab = useUIStore((s) => s.activeTab)` |
| `web/src/app/page.tsx` | `web/src/hooks/use-entities.ts` | `useEntityScopedView\|useRelatedEntities` | WIRED (via EntityScopedView/EntitySidebar) | `page.tsx` does not call hooks directly -- hooks are consumed inside `EntityScopedView` and `EntitySidebar` components, which is architecturally correct |
| `web/src/components/entity/evidence-panel.tsx` | `web/src/stores/ui-store.ts` | `setActiveTab.*summaries` (callback chain) | WIRED | `evidence-panel` passes `onViewInSummary` up through `timeline-entry` → `activity-timeline` → `entity-scoped-view` → `page.tsx` where `handleViewInSummary` calls `setActiveTab("summaries")` + `handleSelectDaily(date)` |

**Note on Plan 03 key link for page.tsx → use-entities.ts:** The plan expected `useEntityScopedView|useRelatedEntities` to appear directly in `page.tsx`. The implementation correctly delegates this to child components (`EntityScopedView` and `EntitySidebar`), which is cleaner architecture. The wiring is functionally complete.

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| ENT-01 | User can browse entity list with filtering by type and sorting by activity/name | SATISFIED | `entities.py` GET /entities with `type` and `sort` params; `entity-filter-bar.tsx` + `entity-list.tsx` on frontend |
| ENT-02 | Entity scoped view shows highlights, open commitments, activity timeline with significance scoring | SATISFIED | `entities.py` GET /entities/{id} returns full `EntityScopedViewResponse`; `entity-scoped-view.tsx` renders all sections; `timeline-entry.tsx` significance badges |
| ENT-05 | Source evidence drill-down -- click mention to see context snippet with source type and confidence | SATISFIED | `evidence-panel.tsx` shows full `context_snippet`, source type icon, `ConfidenceBadge` (>80% green, 50-80% yellow, <50% red) |
| NAV-02 | Left nav shows entities grouped by type (partners, people, initiatives) with activity indicators | SATISFIED | `entity-list.tsx` uses `DateGroup` with Partners/People/Initiatives; `entity-list-item.tsx` green dot logic |
| NAV-03 | Selecting an entity in left nav opens its scoped view in center panel | SATISFIED | `entity-list-item.tsx` calls `selectEntity`; `page.tsx` routes `selectedEntityId` to `EntityScopedView` |
| NAV-04 | Context sidebar adapts to selection: related items, source evidence, timeline | SATISFIED | `right-sidebar.tsx` switches between `EntitySidebar` and `SummaryMetadata` based on `activeTab`/`entityId` |

All 6 required requirement IDs (ENT-01, ENT-02, ENT-05, NAV-02, NAV-03, NAV-04) are satisfied. No orphaned requirements.

### Anti-Patterns Found

No anti-patterns found across any phase 26 files. Zero TODO/FIXME/placeholder comments. No stub implementations (empty returns, console-only handlers). All components render substantive content.

### Human Verification Required

The automated code checks pass completely -- all 18 truths are verified at the implementation level. The following require human testing with a running application because they involve visual rendering, live API data, and browser interactions.

#### 1. Tab switcher and entity list rendering

**Test:** Open http://localhost:3000, click "Entities" tab in the left nav.
**Expected:** Tab active state highlights; entity list appears grouped into Partners, People, Initiatives sections with entity counts and expand/collapse behavior.
**Why human:** Live API data required; visual rendering cannot be checked statically.

#### 2. Activity dots on recently active entities

**Test:** Observe the entity list -- check if entities active within 7 days have a green dot.
**Expected:** Green dot (2x2 rounded, bg-green-500) visible next to recently active entity names.
**Why human:** Requires real `last_active_date` values from the database to verify dot logic fires.

#### 3. Filter and sort controls

**Test:** Click "Partners" type chip and observe list; then click "Name" sort and observe order.
**Expected:** List filters to partners only; sort reorders alphabetically. Active chip/button has bg-accent highlight.
**Why human:** State mutations and query param passing require live network requests.

#### 4. Entity scoped view completeness

**Test:** Click any entity in the list.
**Expected:** Center panel shows entity name (h1), type badge, aliases, stat boxes (total mentions), highlight cards, open commitments list, activity timeline grouped by day with significance badges.
**Why human:** Data population and section layout require browser rendering.

#### 5. Timeline entry expand/collapse and evidence panel

**Test:** Click a timeline entry.
**Expected:** Entry expands inline to show full context snippet, source type icon, date, confidence badge (colored), and "View in summary" button.
**Why human:** useState toggle and inline expand behavior require browser interaction.

#### 6. "View in summary" cross-link

**Test:** Expand a timeline entry, click "View in summary".
**Expected:** App switches to Summaries tab, left nav shows summaries list, center panel loads the daily summary for that date.
**Why human:** Cross-view navigation callback chain requires end-to-end browser verification.

#### 7. Right sidebar entity/summary mode switching

**Test:** With entity selected: verify right sidebar shows "Entity Details" header with type, aliases, related entity chips. Then switch to Summaries tab: verify sidebar shows "Summary Info" with summary metadata.
**Expected:** Sidebar header text and content switch correctly between modes.
**Why human:** Conditional rendering with live data requires browser.

#### 8. Related entity chip navigation

**Test:** In entity right sidebar, click a related entity chip.
**Expected:** Center panel updates to show the clicked entity's scoped view; right sidebar updates to show that entity's details.
**Why human:** selectEntity side-effect chain requires browser interaction.

#### 9. Summaries tab regression

**Test:** Switch back to Summaries tab; navigate between daily/weekly/monthly views.
**Expected:** All existing summary functionality unchanged -- date navigation, summary rendering, right sidebar summary metadata all work as before phase 26.
**Why human:** Full regression of existing functionality requires human confirmation.

### Gaps Summary

None. All automated checks pass. Phase goal is substantively implemented with no stubs, missing files, or broken wiring. The 9 human verification items are behavioral/visual in nature and cannot be confirmed without a running application.

---

_Verified: 2026-04-08_
_Verifier: Claude (gsd-verifier)_
