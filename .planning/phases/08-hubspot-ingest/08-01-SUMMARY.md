# Plan 08-01 Summary: HubSpot Ingest Module (TDD)

**Status:** Complete
**Duration:** ~8 min
**Commits:** 2 (dependency+config, module+tests)

## What Was Built

HubSpot CRM ingestion module (`src/ingest/hubspot.py`) using the official `hubspot-api-client` v12.x SDK with private app token authentication. The module fetches deals, contacts, tickets, and engagements (notes, calls, emails, meetings, tasks) for a target date and converts them to `SourceItem` objects.

### Key Features
- **Deal fetching** with stage history detection (propertiesWithHistory) and stage name resolution via pipeline API
- **Contact fetching** with company context in display_context
- **Ticket fetching** with pipeline stage name resolution
- **Engagement fetching** for 5 types: notes, calls, emails, meetings, tasks
- **Configurable ownership scope**: "mine" (default), "all", or specific owner IDs
- **Volume caps** per activity type from config
- **Owner name resolution** via owners API (not raw IDs)
- **Stage name resolution** via pipelines API (not raw stage IDs)
- **Attribution format**: "HubSpot deal {name}", "HubSpot contact {name} ({company})", etc.

### Config Section
Added `hubspot:` section to config.yaml with enabled, ownership_scope, volume caps, and portal_url.

## Self-Check: PASSED

- [x] All 15 tests pass
- [x] Module importable
- [x] SDK installed
- [x] Config section present
- [x] SourceItem types match models/sources.py enums

## Key Files

### Created
- `src/ingest/hubspot.py` — HubSpot CRM ingest module (380+ lines)
- `tests/test_hubspot_ingest.py` — 15 test cases with mocked SDK

### Modified
- `pyproject.toml` — added hubspot-api-client dependency
- `config/config.yaml` — added hubspot config section
- `src/config.py` — added hubspot defaults

## Decisions
- Single module (`hubspot.py`) rather than per-object-type split, matching Slack pattern
- Date filtering via `hs_lastmodifieddate` BETWEEN for all object types
- Engagement search per-type (notes, calls, etc.) rather than combined engagements v1 endpoint
- Calls/meetings get full detail; emails/tasks get brief content per user decision

## Issues
None.
