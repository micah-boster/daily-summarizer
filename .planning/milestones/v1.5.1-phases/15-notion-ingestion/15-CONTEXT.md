# Phase 15: Notion Ingestion - Context

**Gathered:** 2026-04-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Ingest Notion page updates and database changes into daily summaries, completing the work tool surface. Pages you edited or created, comments where you're mentioned, and database property changes all appear in the daily output with Notion attribution. Discovery CLI helps configure which databases to watch.

</domain>

<decisions>
## Implementation Decisions

### Content Scope
- Ingest pages YOU edited or created on the target date (workspace-wide, no watchlist for pages)
- Include comments where you are @mentioned
- Single workspace, single integration token
- Both creates and edits captured

### Content Extraction
- Title + first ~200 characters of page content (same pattern as Slack/Docs/HubSpot SourceItems)
- Flat list — no nesting hierarchy for sub-pages
- Extract text blocks only: paragraphs, headings, lists, toggles, callouts. Skip images, embeds, code blocks
- Notion API rate limiting: simple throttle (~350ms between requests) + existing retry decorator for 429 errors

### Database Handling
- Default mode: database items YOU modified on the target date
- Opt-in watchlist: specific databases (e.g., ticketing) where ALL changes by anyone are tracked
- Watched databases surface status/property changes (not content edits)
- Show property transitions: "In Progress → Done" not just current value
- Group database items by database name in the output template

### Discovery & Configuration
- config.yaml has a `notion` section with `token` and optional `watched_databases` list
- Discovery CLI command: scans workspace, proposes databases, user confirms which to watch (same UX as Slack channel discovery)
- Token stored in config.yaml alongside other API tokens (consistent with existing pattern)
- Page edits are workspace-wide — no pre-configuration needed for pages

### Claude's Discretion
- Notion SDK/client library choice
- Internal module structure (single file vs split)
- How to detect property transitions (Notion API doesn't provide diffs natively — may need snapshot comparison)
- SourceType enum values for Notion items
- Template section layout for Notion content

</decisions>

<specifics>
## Specific Ideas

- "We use Notion for ticketing — I care how things move there and want to be on top of what changes"
- Discovery CLI should mirror the Slack channel discovery UX (propose + confirm)
- Attribution format: "(per Notion [page/database title])"

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 15-notion-ingestion*
*Context gathered: 2026-04-05*
