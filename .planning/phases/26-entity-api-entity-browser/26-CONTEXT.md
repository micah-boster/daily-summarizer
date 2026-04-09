# Phase 26: Entity API + Entity Browser - Context

**Gathered:** 2026-04-08
**Status:** Ready for planning

<domain>
## Phase Boundary

User sees entities in the left nav, clicks one, and sees its scoped view in the center panel with contextual details in the right sidebar. Entity CRUD, merge proposals, and alias management are Phase 27. This phase is read-only browsing + API endpoints.

</domain>

<decisions>
## Implementation Decisions

### Entity list presentation
- Tab switcher at top of left nav: "Summaries" | "Entities" — switches entire nav content between date navigation (Phase 25) and entity browser
- Entities grouped by type: Partners, People, Initiatives — using the same expandable DateGroup pattern from Phase 25, with counts per group
- Sort dropdown (Activity | Name) and type filter chips below the tab switcher, always visible, compact
- Activity indicator: small green dot next to entity name for entities active in the last 7 days (Slack/Linear pattern)

### Entity scoped view (center panel)
- Header + stacked sections layout: entity name/type header at top, then Highlights, Open Commitments, Activity Timeline sections. Same scroll behavior as summary view
- Highlights section: key stats (total mentions, days active, last seen date) plus 2-3 most recent themes/topics associated with the entity
- Activity timeline: vertical timeline grouped by day, newest first. Each entry shows date, source type icon, brief description, significance score badge
- Significance scoring: subtle colored badges — "High" (red/orange), "Medium" (yellow), "Low" (gray). Scannable without being noisy

### Right sidebar adaptation
- Context-aware swap: sidebar content changes based on what's selected — summary metadata for daily view, entity details for entity view. Header updates to match
- Entity sidebar prioritizes identity + relationships: entity type, aliases as muted tags under name (read-only), metadata, then related entities below, then organization linkage
- Related entities displayed as clickable chips with co-mention count. Clicking navigates to that entity
- Aliases shown as small muted tag list below entity name (editing deferred to Phase 27)

### Evidence drill-down
- Inline expand: clicking a timeline mention expands the entry in place to reveal source evidence. Click again to collapse. No navigation away
- Expanded evidence shows: original text snippet where entity was mentioned, source type icon (Slack/Meeting/HubSpot/etc), date, confidence score badge
- Confidence score: percentage badge (e.g. "92%") with color coding — green >80%, yellow 50-80%, red <50%
- "View in summary" link at bottom of expanded evidence navigates to the daily summary for that date (switches to Summaries tab + selects the date)

### Claude's Discretion
- API endpoint design (REST paths, response shapes)
- Entity data fetching strategy (TanStack Query patterns)
- Exact icon choices for source types
- Animation/transition for sidebar context swap
- Empty state design for entities with no activity

</decisions>

<specifics>
## Specific Ideas

- The tab switcher should feel native to the nav — not jarring. Segmented control or underlined tabs, consistent with the overall tool aesthetic
- The "View in summary" cross-link from evidence to daily summary is a key UX connection — makes the entity browser feel integrated, not siloed
- Related entity chips should feel like a mini knowledge graph — showing co-occurrence patterns at a glance
- Activity timeline should feel like a changelog/audit log — clear, chronological, scannable

</specifics>

<deferred>
## Deferred Ideas

- Entity CRUD (create/edit/delete) — Phase 27
- Merge proposal review UI — Phase 27
- Alias management (add/remove) — Phase 27
- Entity search/command palette — Phase 27

</deferred>

---

*Phase: 26-entity-api-entity-browser*
*Context gathered: 2026-04-08*
