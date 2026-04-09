"""Pydantic response models for the Daily Summarizer API."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class SummaryListItem(BaseModel):
    """A single entry in the summary list endpoint."""

    date: date
    meeting_count: int | None = None
    commitment_count: int | None = None
    has_sidecar: bool = False


class SummaryResponse(BaseModel):
    """Full summary detail for a single date."""

    date: date
    markdown: str
    sidecar: dict | None = None


class StatusResponse(BaseModel):
    """API health / status check response."""

    status: str = "ok"
    db_connected: bool = False
    summary_count: int = 0
    last_summary_date: date | None = None


# --- Weekly roll-up models ---


class WeeklyListItem(BaseModel):
    """A single entry in the weekly roll-up list endpoint."""

    week_label: str
    year: int
    week_number: int
    start_date: date | None = None
    end_date: date | None = None
    daily_count: int = 0


class WeeklyResponse(BaseModel):
    """Full weekly roll-up detail."""

    week_number: int
    year: int
    start_date: date | None = None
    end_date: date | None = None
    markdown: str
    sidecar: dict | None = None


# --- Monthly roll-up models ---


class MonthlyListItem(BaseModel):
    """A single entry in the monthly roll-up list endpoint."""

    month_label: str
    year: int
    month: int


class MonthlyResponse(BaseModel):
    """Full monthly roll-up detail."""

    month: int
    year: int
    markdown: str
    sidecar: dict | None = None


# --- Entity models ---


class EntityListItem(BaseModel):
    """A single entity in the entity list endpoint."""

    entity_id: str
    name: str
    entity_type: str
    mention_count: int = 0
    commitment_count: int = 0
    last_active_date: str | None = None


class ActivityItemResponse(BaseModel):
    """A single activity mention for an entity."""

    source_type: str
    source_date: str
    context_snippet: str | None = None
    confidence: float = 1.0
    significance_score: float = 0.0


class ActivityDayResponse(BaseModel):
    """Activity items grouped by date."""

    date: str
    items: list[ActivityItemResponse] = []


class EntityScopedViewResponse(BaseModel):
    """Complete scoped view of an entity's activity."""

    entity_name: str
    entity_type: str
    entity_id: str
    from_date: str | None = None
    to_date: str | None = None
    total_mentions: int = 0
    aliases: list[str] = []
    open_commitments: list[ActivityItemResponse] = []
    highlights: list[ActivityItemResponse] = []
    activity_by_date: list[ActivityDayResponse] = []


class RelatedEntityItem(BaseModel):
    """A related entity with co-mention count."""

    entity_id: str
    name: str
    entity_type: str
    co_mention_count: int = 0


class EntityResponse(BaseModel):
    """Returned on entity create/update."""

    entity_id: str
    name: str
    entity_type: str


class AliasResponse(BaseModel):
    """Returned on alias create."""

    alias_id: str
    entity_id: str
    alias: str


class MergeProposalResponse(BaseModel):
    """A merge proposal with enriched entity details."""

    proposal_id: str
    source_entity: EntityListItem
    target_entity: EntityListItem
    score: float
    reason: str | None = None
    status: str
    created_at: str
