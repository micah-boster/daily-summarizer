---
phase: 26-entity-api-entity-browser
plan: 01
status: complete
started: 2026-04-08
completed: 2026-04-08
---

# Plan 26-01 Summary: Entity API Endpoints

## What Was Built

FastAPI entity router with three read-only endpoints, backed by existing `src.entity.repository` and `src.entity.views` modules. Zero business logic in the API layer.

## Key Files

### Created
- `src/api/routers/entities.py` -- Entity list, scoped view, and related entities endpoints

### Modified
- `src/api/models/responses.py` -- Added EntityListItem, EntityScopedViewResponse, RelatedEntityItem, ActivityItemResponse, ActivityDayResponse
- `src/api/app.py` -- Registered entities router at /api/v1
- `src/entity/repository.py` -- Added get_related_entities() method for co-mention queries

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | /api/v1/entities | List entities with ?type and ?sort params |
| GET | /api/v1/entities/{id} | Scoped view with highlights, commitments, timeline, aliases |
| GET | /api/v1/entities/{id}/related | Co-mentioned entities with counts |

## Decisions Made

- Response models are thin wrappers over existing Pydantic models from src.entity
- get_related_entities uses source_date + source_id join for co-occurrence detection
- 404 returned for non-existent entities (ValueError from views wrapped in HTTPException)

## Requirements Addressed

- ENT-01: Entity list with filtering and sorting
- ENT-02: Entity scoped view with significance scoring
- ENT-05: Source evidence data (context_snippet + confidence)
- NAV-02: Activity indicator data (last_active_date in list response)
