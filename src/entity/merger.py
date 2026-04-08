"""Entity merge proposal generation.

Generates merge proposals by comparing entities of the same type using
rapidfuzz similarity scoring. Proposals are filtered against existing
rejected/approved pairs to avoid re-proposing.
"""

from __future__ import annotations

import logging
from itertools import combinations

from rapidfuzz import fuzz

from src.entity.normalizer import normalize_for_matching
from src.entity.repository import EntityRepository

logger = logging.getLogger(__name__)

MERGE_THRESHOLD = 80  # Minimum token_sort_ratio for merge proposal


def score_pair(name_a: str, name_b: str) -> float:
    """Score name similarity using token_sort_ratio on normalized names.

    Args:
        name_a: First entity name.
        name_b: Second entity name.

    Returns:
        Similarity score 0-100.
    """
    norm_a = normalize_for_matching(name_a)
    norm_b = normalize_for_matching(name_b)
    return fuzz.token_sort_ratio(norm_a, norm_b)


def generate_proposals(
    repo: EntityRepository,
    entity_type: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """Generate merge proposals for similar entities of the same type.

    Args:
        repo: Connected EntityRepository.
        entity_type: Filter to specific type (partner/person). None = all types.
        limit: Maximum proposals to return.

    Returns:
        List of proposal dicts sorted by score descending, each containing:
        - source_entity: Entity (less-mentioned, will be merged away)
        - target_entity: Entity (more-mentioned, canonical survivor)
        - score: float
        - source_context: {mention_count: int, source_types: list[str]}
        - target_context: {mention_count: int, source_types: list[str]}
    """
    # Load active entities (exclude deleted and already-merged)
    all_entities = repo.list_entities(entity_type=entity_type)
    active = [e for e in all_entities if e.merge_target_id is None]

    # Group by type (same-type comparisons only)
    by_type: dict[str, list] = {}
    for entity in active:
        by_type.setdefault(str(entity.entity_type), []).append(entity)

    proposals: list[dict] = []

    for _etype, entities in by_type.items():
        for e_a, e_b in combinations(entities, 2):
            # Check if proposal already exists (any status, either ordering)
            existing = repo.get_existing_proposals(e_a.id, e_b.id)
            if existing:
                continue

            score = score_pair(e_a.name, e_b.name)
            if score < MERGE_THRESHOLD:
                continue

            # Determine source (less-mentioned) and target (more-mentioned)
            count_a = repo.get_mention_count(e_a.id)
            count_b = repo.get_mention_count(e_b.id)

            if count_a >= count_b:
                target, source = e_a, e_b
                target_count, source_count = count_a, count_b
            else:
                target, source = e_b, e_a
                target_count, source_count = count_b, count_a

            proposals.append({
                "source_entity": source,
                "target_entity": target,
                "score": score,
                "source_context": {
                    "mention_count": source_count,
                    "source_types": repo.get_mention_sources(source.id),
                },
                "target_context": {
                    "mention_count": target_count,
                    "source_types": repo.get_mention_sources(target.id),
                },
            })

    # Sort by score descending, cap at limit
    proposals.sort(key=lambda p: p["score"], reverse=True)
    return proposals[:limit]
