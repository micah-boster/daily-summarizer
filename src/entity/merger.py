"""Entity merge proposal generation, execution, and split reversal.

Generates merge proposals by comparing entities of the same type using
rapidfuzz similarity scoring. Proposals are filtered against existing
rejected/approved pairs to avoid re-proposing. Provides merge execution
(soft-delete source, reassign mentions, transfer aliases) and split
reversal (restore entity, re-attribute mentions).
"""

from __future__ import annotations

import logging
import sqlite3
from itertools import combinations

from rapidfuzz import fuzz

from src.entity.models import _now_utc
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


def execute_merge(
    repo: EntityRepository,
    source_entity_id: str,
    target_entity_id: str,
    score: float = 0.0,
) -> None:
    """Execute a merge: soft-delete source, reassign mentions, transfer aliases.

    Args:
        repo: Connected EntityRepository.
        source_entity_id: Entity to merge away (less-mentioned).
        target_entity_id: Entity to keep (canonical survivor).
        score: Similarity score for the proposal record.

    Raises:
        ValueError: If either entity does not exist or is already deleted.
    """
    now = _now_utc()
    conn = repo._conn

    # Verify both entities exist
    source = repo.get_by_id(source_entity_id)
    if source is None:
        raise ValueError("Source entity %s not found" % source_entity_id)
    target = repo.get_by_id(target_entity_id)
    if target is None:
        raise ValueError("Target entity %s not found" % target_entity_id)

    # 1. Record which mention IDs belong to source before reassignment
    # Store in merge proposal metadata for split reversal
    source_mention_ids = [
        row["id"] for row in conn.execute(
            "SELECT id FROM entity_mentions WHERE entity_id = ?",
            (source_entity_id,),
        ).fetchall()
    ]

    # Reassign all mentions from source to target
    conn.execute(
        "UPDATE entity_mentions SET entity_id = ? WHERE entity_id = ?",
        (target_entity_id, source_entity_id),
    )

    # 2. Transfer aliases from source to target (handle collisions individually)
    source_aliases = repo.list_aliases(source_entity_id)
    for alias in source_aliases:
        try:
            conn.execute(
                "UPDATE aliases SET entity_id = ? WHERE id = ?",
                (target_entity_id, alias.id),
            )
        except sqlite3.IntegrityError:
            # Alias already exists on another entity -- skip
            conn.execute("DELETE FROM aliases WHERE id = ?", (alias.id,))

    # 3. Add source's canonical name as alias on target
    try:
        repo.add_alias(target_entity_id, source.name)
    except ValueError:
        pass  # Alias already exists (collision)

    # 4. Soft-delete source with merge_target_id
    conn.execute(
        "UPDATE entities SET deleted_at = ?, merge_target_id = ?, updated_at = ? "
        "WHERE id = ?",
        (now, target_entity_id, now, source_entity_id),
    )
    conn.commit()

    # 5. Record approved proposal with source mention IDs for split reversal
    import json as _json
    mention_data = _json.dumps(source_mention_ids)
    repo.save_proposal(
        source_entity_id, target_entity_id,
        reason=mention_data,  # Store mention IDs in reason field for split
        status="approved",
    )

    logger.info(
        "Merged entity %s (%s) into %s (%s)",
        source_entity_id, source.name, target_entity_id, target.name,
    )


def execute_split(repo: EntityRepository, entity_id: str) -> None:
    """Reverse a merge: restore entity, re-attribute mentions, move aliases back.

    Args:
        repo: Connected EntityRepository.
        entity_id: The entity that was merged away (source_entity_id in proposal).

    Raises:
        ValueError: If entity was never merged or is not currently deleted.
    """
    conn = repo._conn

    # Find merge history
    proposals = conn.execute(
        "SELECT * FROM merge_proposals "
        "WHERE source_entity_id = ? AND status = 'approved' "
        "ORDER BY resolved_at DESC",
        (entity_id,),
    ).fetchall()

    if not proposals:
        raise ValueError("Entity %s was never merged" % entity_id)

    last_merge = proposals[0]
    target_entity_id = last_merge["target_entity_id"]

    # Verify entity is soft-deleted
    row = conn.execute(
        "SELECT * FROM entities WHERE id = ? AND deleted_at IS NOT NULL",
        (entity_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Entity %s is not merged/deleted" % entity_id)

    source_name = row["name"]
    now = _now_utc()

    # 1. Restore entity (clear deleted_at and merge_target_id)
    conn.execute(
        "UPDATE entities SET deleted_at = NULL, merge_target_id = NULL, updated_at = ? "
        "WHERE id = ?",
        (now, entity_id),
    )

    # 2. Remove source's canonical name alias from target
    conn.execute(
        "DELETE FROM aliases WHERE entity_id = ? AND LOWER(alias) = LOWER(?)",
        (target_entity_id, source_name),
    )

    # 3. Re-attribute mentions using stored mention IDs from merge proposal
    import json as _json
    reason_data = last_merge["reason"]
    source_mention_ids: list[str] = []
    try:
        source_mention_ids = _json.loads(reason_data)
    except (ValueError, TypeError):
        # Reason field doesn't contain JSON mention IDs -- fall back to name matching
        pass

    if source_mention_ids:
        # Deterministic: move back exactly the mentions that were on source before merge
        for mention_id in source_mention_ids:
            conn.execute(
                "UPDATE entity_mentions SET entity_id = ? WHERE id = ?",
                (entity_id, mention_id),
            )
    else:
        # Fallback: match by context_snippet containing source name
        restored_aliases = [a.alias.lower() for a in repo.list_aliases(entity_id)]
        source_names = {source_name.lower()} | set(restored_aliases)

        target_mentions = conn.execute(
            "SELECT id, context_snippet FROM entity_mentions WHERE entity_id = ?",
            (target_entity_id,),
        ).fetchall()

        for mention in target_mentions:
            snippet = mention["context_snippet"]
            if snippet and any(name in snippet.lower() for name in source_names):
                conn.execute(
                    "UPDATE entity_mentions SET entity_id = ? WHERE id = ?",
                    (entity_id, mention["id"]),
                )

    conn.commit()

    logger.info("Split entity %s (%s) from %s", entity_id, source_name, target_entity_id)
