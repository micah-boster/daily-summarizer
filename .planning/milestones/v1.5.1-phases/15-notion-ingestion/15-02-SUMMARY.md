---
phase: 15-notion-ingestion
plan: 02
subsystem: ingest
tags: [notion, discovery, cli, yaml]

requires:
  - phase: 15-notion-ingestion
    provides: "NotionClient for API calls"
provides:
  - "Notion database discovery CLI for watchlist configuration"
  - "discover-notion CLI subcommand in main.py"
affects: [notion-config, user-setup]

tech-stack:
  added: []
  patterns: ["Interactive discovery CLI with config.yaml persistence"]

key-files:
  created:
    - src/ingest/notion_discovery.py
    - tests/test_notion_discovery.py
  modified:
    - src/main.py

key-decisions:
  - "Self-contained httpx headers in discovery module to avoid cross-dependency with Plan 01 in parallel wave"
  - "Sorted databases by last_edited_time descending for most-active-first presentation"

patterns-established:
  - "Discovery CLI pattern matching Slack channel discovery UX"

requirements-completed:
  - NOTION-01

duration: 3min
completed: 2026-04-05
---

# Phase 15 Plan 02: Notion Discovery CLI Summary

**Interactive Notion database discovery CLI with workspace scanning, user selection, and config.yaml persistence**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-05T10:25:00Z
- **Completed:** 2026-04-05T10:30:00Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- Database scanning via Notion Search API with pagination support
- Interactive CLI presenting databases sorted by activity with watched-database markers
- Config.yaml persistence for selected database IDs
- discover-notion CLI subcommand wired into main.py

## Task Commits

1. **Task 1: Build discovery module** - `fd18956` (feat)
2. **Task 2: Wire CLI subcommand** - `fd18956` (feat)
3. **Task 3: Add unit tests** - `fd18956` (feat)

## Files Created/Modified
- `src/ingest/notion_discovery.py` - Database scanning, interactive selection, config writing
- `src/main.py` - discover-notion subcommand registration
- `tests/test_notion_discovery.py` - 5 tests covering scanning, pagination, title extraction, no-token guard

## Decisions Made
- Used inline headers instead of importing NotionClient to keep module self-contained
- Databases sorted by last_edited_time for most-active-first presentation

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - discovery CLI guides user through database selection.

## Next Phase Readiness
- Discovery CLI ready for use after Notion token is configured
- Feeds into Plan 01's watched_databases config for database change tracking

---
*Phase: 15-notion-ingestion*
*Completed: 2026-04-05*
