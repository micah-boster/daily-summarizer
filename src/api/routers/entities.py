"""Entity list, scoped view, and related entity endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import get_entity_repo
from src.api.models.responses import (
    ActivityDayResponse,
    ActivityItemResponse,
    EntityListItem,
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
