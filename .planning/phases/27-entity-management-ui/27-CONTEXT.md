# Phase 27: Entity Management UI - Context

**Gathered:** 2026-04-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can manage the entity registry entirely from the browser -- create, edit, delete entities, review merge proposals, manage aliases, and navigate anywhere via keyboard. Entity browsing/viewing (Phase 26) is complete; this phase adds write operations and the command palette.

</domain>

<decisions>
## Implementation Decisions

### CRUD form design
- Slide-over panel from the right for create/edit forms -- keeps entity list visible for context
- Required fields: name and type only (person/partner/initiative). All other metadata optional at creation time
- Inline validation errors beneath each field (red text, standard form pattern)
- Delete confirmation requires typing entity name to confirm -- GitHub-style destructive action guard

### Merge proposal review
- Side-by-side card layout showing both entities being considered for merge
- Each card displays: name, type, aliases, mention count, similarity score
- One-at-a-time review with auto-advance queue -- focus on careful review, not batch speed
- When approving a merge, user explicitly picks which entity name becomes primary; the other becomes an alias

### Alias management
- Chip/tag list below entity name with removable chips and type-to-add input at the end (Notion-style)
- Duplicate alias prevention: warn and block if alias already belongs to another entity, showing which entity owns it
- Alias removal is instant (click X) with temporary undo toast -- no confirmation dialog
- Alias input autocompletes from unmatched mentions (names that appeared in summaries but aren't linked to any entity)

### Command palette (Cmd+K)
- Search scope: entities by name/alias, dates, and actions (create entity, run pipeline, etc.)
- Results grouped by type under headers: Entities, Dates, Actions -- with recency boost within each group
- On open (before typing): show recently visited entities and dates
- Prefix filters: `/` for actions, `@` for entities, `#` for dates -- power-user keyboard shortcuts (Linear/Slack-style)

### Claude's Discretion
- Slide-over panel width and animation
- Exact form field ordering and spacing
- Merge review queue sorting (by similarity score, date, etc.)
- Command palette fuzzy matching algorithm
- Toast duration and positioning
- Loading states during entity writes

</decisions>

<specifics>
## Specific Ideas

- Delete confirmation should feel like GitHub's repo delete -- serious, not just a click-through
- Command palette should feel like Linear's Cmd+K -- fast, keyboard-first, grouped results
- Alias chips should resemble Notion's tag system -- clean, colorful by type
- Merge review should be a calm, focused flow -- not overwhelming even with many proposals

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 27-entity-management-ui*
*Context gathered: 2026-04-08*
