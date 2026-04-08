"""Entity scoped views, enriched lists, and significance scoring.

Provides the data layer between EntityRepository (raw queries) and CLI/template
consumers. All business logic for entity views lives here.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, Field

from src.entity.repository import EntityRepository

logger = logging.getLogger(__name__)

__all__ = [
    "ActivityItem",
    "EnrichedEntity",
    "EntityScopedView",
    "score_significance",
    "get_entity_scoped_view",
    "get_enriched_entity_list",
    "generate_entity_report",
]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ActivityItem(BaseModel):
    """A single activity mention for an entity."""

    source_type: str  # substance | decision | commitment
    source_date: str
    context_snippet: str | None = None
    confidence: float = 1.0
    significance_score: float = 0.0


class EntityScopedView(BaseModel):
    """Complete scoped view of an entity's activity."""

    entity_name: str
    entity_type: str
    entity_id: str
    from_date: str | None = None
    to_date: str | None = None
    open_commitments: list[ActivityItem] = Field(default_factory=list)
    highlights: list[ActivityItem] = Field(default_factory=list)
    activity_by_date: list[dict] = Field(default_factory=list)
    total_mentions: int = 0


class EnrichedEntity(BaseModel):
    """Entity with aggregated mention statistics."""

    entity_id: str
    name: str
    entity_type: str
    mention_count: int = 0
    commitment_count: int = 0
    last_active_date: str | None = None


# ---------------------------------------------------------------------------
# Significance Scoring
# ---------------------------------------------------------------------------


def score_significance(
    source_type: str,
    source_date: str,
    confidence: float,
    today: date | None = None,
) -> float:
    """Rule-based significance scoring for entity mentions.

    Scoring:
    - Decision items: base 3.0
    - Commitment items: base 2.5
    - Substance items: base 1.0
    - Recency: +1.0 within 7 days, +0.5 within 14 days
    - Multiplied by confidence (0.0-1.0)
    """
    if today is None:
        today = date.today()

    # Base score by type
    base_scores = {
        "decision": 3.0,
        "commitment": 2.5,
        "substance": 1.0,
    }
    base = base_scores.get(source_type, 1.0)

    # Recency bonus
    try:
        item_date = date.fromisoformat(source_date[:10])
        days_ago = (today - item_date).days
        if days_ago <= 7:
            base += 1.0
        elif days_ago <= 14:
            base += 0.5
    except (ValueError, TypeError):
        pass

    return base * confidence


# ---------------------------------------------------------------------------
# Scoped View
# ---------------------------------------------------------------------------


def get_entity_scoped_view(
    repo: EntityRepository,
    entity_name: str,
    from_date: date | None = None,
    to_date: date | None = None,
) -> EntityScopedView:
    """Build a scoped activity view for an entity.

    Args:
        repo: Entity repository (must be connected).
        entity_name: Entity name or alias to look up.
        from_date: Start date filter (default: 30 days ago).
        to_date: End date filter (default: today).

    Returns:
        EntityScopedView with highlights, commitments, and activity.

    Raises:
        ValueError: If entity is not found.
    """
    entity = repo.resolve_name(entity_name)
    if entity is None:
        raise ValueError("Entity not found: %s" % entity_name)

    today = date.today()
    if from_date is None:
        from_date = today - timedelta(days=30)
    if to_date is None:
        to_date = today

    from_str = from_date.isoformat() if isinstance(from_date, date) else from_date
    to_str = to_date.isoformat() if isinstance(to_date, date) else to_date

    mentions = repo.get_entity_mentions_in_range(entity.id, from_str, to_str)

    # Build ActivityItems with significance scores
    items: list[ActivityItem] = []
    for m in mentions:
        score = score_significance(
            m["source_type"], m["source_date"], m["confidence"], today
        )
        items.append(
            ActivityItem(
                source_type=m["source_type"],
                source_date=m["source_date"],
                context_snippet=m["context_snippet"],
                confidence=m["confidence"],
                significance_score=score,
            )
        )

    # Open commitments (source_type = 'commitment')
    open_commitments = [i for i in items if i.source_type == "commitment"]

    # Highlights: top 5 by significance score
    highlights = sorted(items, key=lambda x: x.significance_score, reverse=True)[:5]

    # Activity grouped by date (descending)
    by_date: dict[str, list[ActivityItem]] = defaultdict(list)
    for item in items:
        by_date[item.source_date].append(item)

    activity_by_date = [
        {"date": d, "items": by_date[d]}
        for d in sorted(by_date.keys(), reverse=True)
    ]

    return EntityScopedView(
        entity_name=entity.name,
        entity_type=entity.entity_type.value,
        entity_id=entity.id,
        from_date=from_str,
        to_date=to_str,
        open_commitments=open_commitments,
        highlights=highlights,
        activity_by_date=activity_by_date,
        total_mentions=len(items),
    )


# ---------------------------------------------------------------------------
# Enriched Entity List
# ---------------------------------------------------------------------------


def get_enriched_entity_list(
    repo: EntityRepository,
    entity_type: str | None = None,
    sort_by: str = "active",
) -> list[EnrichedEntity]:
    """Get entities with aggregated mention statistics.

    Args:
        repo: Entity repository (must be connected).
        entity_type: Filter by type (partner/person/initiative).
        sort_by: Sort order -- "active" (last-active desc), "mentions" (desc), "name" (asc).

    Returns:
        List of EnrichedEntity with mention stats.
    """
    entities = repo.list_entities(entity_type=entity_type)

    enriched: list[EnrichedEntity] = []
    for e in entities:
        stats = repo.get_entity_stats(e.id)
        enriched.append(
            EnrichedEntity(
                entity_id=e.id,
                name=e.name,
                entity_type=e.entity_type.value,
                mention_count=stats["mention_count"],
                commitment_count=stats["commitment_count"],
                last_active_date=stats["last_active_date"],
            )
        )

    # Sort
    if sort_by == "mentions":
        enriched.sort(key=lambda x: x.mention_count, reverse=True)
    elif sort_by == "name":
        enriched.sort(key=lambda x: x.name)
    else:  # "active" (default)
        enriched.sort(
            key=lambda x: (x.last_active_date or "", x.name),
            reverse=True,
        )

    return enriched


# ---------------------------------------------------------------------------
# Report Generation
# ---------------------------------------------------------------------------


def generate_entity_report(
    repo: EntityRepository,
    entity_name: str,
    from_date: date | None = None,
    to_date: date | None = None,
    output_dir: str = "output/entities",
    template_dir: str = "templates",
) -> Path:
    """Generate a per-entity markdown report using Jinja2 template.

    Args:
        repo: Entity repository (must be connected).
        entity_name: Entity name or alias.
        from_date: Start date filter.
        to_date: End date filter.
        output_dir: Directory for output files.
        template_dir: Directory containing Jinja2 templates.

    Returns:
        Path to the generated report file.

    Raises:
        ValueError: If entity is not found.
    """
    view = get_entity_scoped_view(repo, entity_name, from_date, to_date)

    # Get aliases
    aliases = [a.alias for a in repo.list_aliases(view.entity_id)]

    # Load and render template
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("entity_report.md.j2")

    rendered = template.render(
        entity_name=view.entity_name,
        entity_type=view.entity_type,
        entity_id=view.entity_id,
        from_date=view.from_date,
        to_date=view.to_date,
        total_mentions=view.total_mentions,
        generated_date=date.today().isoformat(),
        aliases=aliases,
        open_commitments=view.open_commitments,
        highlights=view.highlights,
        activity_by_date=view.activity_by_date,
    )

    # Write report
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    slug = view.entity_name.lower().replace(" ", "-")
    report_path = out_path / ("%s.md" % slug)
    report_path.write_text(rendered)

    logger.info("Generated entity report: %s", report_path)
    return report_path
