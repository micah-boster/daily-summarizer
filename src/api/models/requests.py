"""Pydantic request models for entity write operations."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateEntityRequest(BaseModel):
    """Request body for creating a new entity."""

    name: str = Field(..., min_length=1, description="Entity display name")
    entity_type: str = Field(
        ...,
        pattern=r"^(partner|person|initiative)$",
        description="Entity type: partner, person, or initiative",
    )


class UpdateEntityRequest(BaseModel):
    """Request body for updating an entity (partial update)."""

    name: str | None = Field(None, min_length=1, description="New display name")
    entity_type: str | None = Field(
        None,
        pattern=r"^(partner|person|initiative)$",
        description="New entity type",
    )


class AddAliasRequest(BaseModel):
    """Request body for adding an alias to an entity."""

    alias: str = Field(..., min_length=1, description="Alternative name for the entity")
