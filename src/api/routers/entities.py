"""Entity list, scoped view, related entity, and CRUD endpoints."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import get_entity_repo
from src.api.models.requests import AddAliasRequest, CreateEntityRequest, UpdateEntityRequest
from src.api.models.responses import (
    ActivityDayResponse,
    ActivityItemResponse,
    AliasResponse,
    EntityListItem,
    EntityResponse,
    EntityScopedViewResponse,
    RelatedEntityItem,
)
from src.entity.repository import EntityRepository
from src.entity.views import get_enriched_entity_list, get_entity_scoped_view

router = APIRouter(prefix="/entities", tags=["entities"])


@router.get("", response_model=list[EntityListItem])
def list_entities(
    type: str | None = Query(None, description="Filter by entity type (partner, person, initiative)"),
    sort: str = Query("activity", description="Sort order: activity (default) or name"),
    repo: EntityRepository = Depends(get_entity_repo),
) -> list[EntityListItem]:
    """Return enriched entity list with mention statistics."""
    enriched = get_enriched_entity_list(repo, entity_type=type, sort_by=sort)
    return [
        EntityListItem(
            entity_id=e.entity_id,
            name=e.name,
            entity_type=e.entity_type,
            mention_count=e.mention_count,
            commitment_count=e.commitment_count,
            last_active_date=e.last_active_date,
        )
        for e in enriched
    ]


@router.post("", response_model=EntityResponse, status_code=201)
def create_entity(
    body: CreateEntityRequest,
    repo: EntityRepository = Depends(get_entity_repo),
) -> EntityResponse:
    """Create a new entity."""
    try:
        entity = repo.add_entity(name=body.name, entity_type=body.entity_type)
    except sqlite3.OperationalError:
        raise HTTPException(status_code=503, detail="Database busy")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return EntityResponse(
        entity_id=entity.id,
        name=entity.name,
        entity_type=str(entity.entity_type),
    )


@router.put("/{entity_id}", response_model=EntityResponse)
def update_entity(
    entity_id: str,
    body: UpdateEntityRequest,
    repo: EntityRepository = Depends(get_entity_repo),
) -> EntityResponse:
    """Update an entity's name and/or type."""
    try:
        entity = repo.update_entity(
            entity_id=entity_id,
            name=body.name,
            entity_type=body.entity_type,
        )
    except sqlite3.OperationalError:
        raise HTTPException(status_code=503, detail="Database busy")
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    return EntityResponse(
        entity_id=entity.id,
        name=entity.name,
        entity_type=str(entity.entity_type),
    )


@router.delete("/{entity_id}", status_code=204)
def delete_entity(
    entity_id: str,
    repo: EntityRepository = Depends(get_entity_repo),
) -> None:
    """Soft-delete an entity."""
    try:
        deleted = repo.remove_entity(entity_id)
    except sqlite3.OperationalError:
        raise HTTPException(status_code=503, detail="Database busy")
    if not deleted:
        raise HTTPException(status_code=404, detail="Entity not found")


@router.post("/{entity_id}/aliases", response_model=AliasResponse, status_code=201)
def add_alias(
    entity_id: str,
    body: AddAliasRequest,
    repo: EntityRepository = Depends(get_entity_repo),
) -> AliasResponse:
    """Add an alias to an entity."""
    try:
        alias = repo.add_alias(entity_id=entity_id, alias=body.alias)
    except sqlite3.OperationalError:
        raise HTTPException(status_code=503, detail="Database busy")
    except ValueError as exc:
        detail = str(exc)
        if "already exists" in detail.lower():
            raise HTTPException(status_code=409, detail=detail)
        raise HTTPException(status_code=404, detail=detail)
    return AliasResponse(
        alias_id=alias.id,
        entity_id=alias.entity_id,
        alias=alias.alias,
    )


@router.delete("/{entity_id}/aliases/{alias}", status_code=204)
def remove_alias(
    entity_id: str,
    alias: str,
    repo: EntityRepository = Depends(get_entity_repo),
) -> None:
    """Remove an alias from an entity."""
    try:
        removed = repo.remove_alias(alias)
    except sqlite3.OperationalError:
        raise HTTPException(status_code=503, detail="Database busy")
    if not removed:
        raise HTTPException(status_code=404, detail="Alias not found")


@router.get("/unmatched-mentions", response_model=list[str])
def get_unmatched_mentions(
    repo: EntityRepository = Depends(get_entity_repo),
) -> list[str]:
    """Return mention source names not matching any entity or alias.

    TODO: Implement full SQL join query against entity_mentions, entities,
    and aliases to find truly unmatched names. For now returns empty list.
    """
    return []


@router.get("/{entity_id}", response_model=EntityScopedViewResponse)
def get_entity_view(
    entity_id: str,
    repo: EntityRepository = Depends(get_entity_repo),
) -> EntityScopedViewResponse:
    """Return scoped view for an entity with highlights, commitments, and timeline."""
    entity = repo.get_by_id(entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")

    try:
        view = get_entity_scoped_view(repo, entity.name)
    except ValueError:
        raise HTTPException(status_code=404, detail="Entity not found")

    aliases = [a.alias for a in repo.list_aliases(entity_id)]

    return EntityScopedViewResponse(
        entity_name=view.entity_name,
        entity_type=view.entity_type,
        entity_id=view.entity_id,
        from_date=view.from_date,
        to_date=view.to_date,
        total_mentions=view.total_mentions,
        aliases=aliases,
        open_commitments=[
            ActivityItemResponse(
                source_type=item.source_type,
                source_date=item.source_date,
                context_snippet=item.context_snippet,
                confidence=item.confidence,
                significance_score=item.significance_score,
            )
            for item in view.open_commitments
        ],
        highlights=[
            ActivityItemResponse(
                source_type=item.source_type,
                source_date=item.source_date,
                context_snippet=item.context_snippet,
                confidence=item.confidence,
                significance_score=item.significance_score,
            )
            for item in view.highlights
        ],
        activity_by_date=[
            ActivityDayResponse(
                date=day["date"],
                items=[
                    ActivityItemResponse(
                        source_type=item.source_type,
                        source_date=item.source_date,
                        context_snippet=item.context_snippet,
                        confidence=item.confidence,
                        significance_score=item.significance_score,
                    )
                    for item in day["items"]
                ],
            )
            for day in view.activity_by_date
        ],
    )


@router.get("/{entity_id}/related", response_model=list[RelatedEntityItem])
def get_related_entities(
    entity_id: str,
    repo: EntityRepository = Depends(get_entity_repo),
) -> list[RelatedEntityItem]:
    """Return entities that co-occur with the given entity."""
    entity = repo.get_by_id(entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")

    related = repo.get_related_entities(entity_id)
    return [
        RelatedEntityItem(
            entity_id=r["entity_id"],
            name=r["name"],
            entity_type=r["entity_type"],
            co_mention_count=r["co_mention_count"],
        )
        for r in related
    ]
