"""Entity attribution for synthesis output.

Matches entity names from synthesis items against the entity registry,
produces per-item entity references with confidence scores, persists
mentions to SQLite, and provides data for sidecar enrichment.
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
from collections import Counter
from uuid import uuid4

from pydantic import BaseModel, Field

from src.entity.models import Entity, EntityMention, _now_utc
from src.entity.normalizer import normalize_for_matching
from src.entity.repository import EntityRepository
from src.synthesis.models import CommitmentRow, DailySynthesisOutput, SynthesisItem

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class EntityReference(BaseModel):
    """A reference to a matched entity for a synthesis item."""

    entity_id: str
    name: str
    confidence: float


class EntitySummaryEntry(BaseModel):
    """Summary of an entity's mentions across the daily output."""

    entity_id: str
    name: str
    entity_type: str
    mention_count: int


class AttributionResult(BaseModel):
    """Complete attribution result for a daily synthesis output."""

    substance_refs: list[list[EntityReference]] = Field(default_factory=list)
    decision_refs: list[list[EntityReference]] = Field(default_factory=list)
    commitment_refs: list[list[EntityReference]] = Field(default_factory=list)
    mentions: list[EntityMention] = Field(default_factory=list)
    entity_summary: list[EntitySummaryEntry] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


def content_hash(text: str) -> str:
    """Produce a deterministic 16-char hex hash of text content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def commitment_content_hash(who: str, what: str, by_when: str) -> str:
    """Hash a commitment using the who|what|by_when format."""
    return content_hash(f"{who}|{what}|{by_when}")


# ---------------------------------------------------------------------------
# Name matching
# ---------------------------------------------------------------------------


def match_name_to_entity(
    raw_name: str, repo: EntityRepository
) -> tuple[Entity, float] | None:
    """Match a raw name against the entity registry.

    Two-step matching:
    1. Canonical name lookup (normalized then raw) -- confidence 1.0
    2. Alias lookup -- confidence 0.7
    Follows merge_target_id if present.

    Returns (entity, confidence) or None if no match.
    """
    if not raw_name or not raw_name.strip():
        return None

    # Step 1: direct canonical name match
    normalized = normalize_for_matching(raw_name)
    entity = repo.get_by_name(normalized)
    if entity is None:
        entity = repo.get_by_name(raw_name)

    if entity is not None:
        # Follow merge target
        if entity.merge_target_id:
            merged = repo.get_by_id(entity.merge_target_id)
            if merged:
                entity = merged
        return (entity, 1.0)

    # Step 2: alias lookup
    row = repo._conn.execute(
        "SELECT a.entity_id FROM aliases a "
        "JOIN entities e ON a.entity_id = e.id "
        "WHERE LOWER(a.alias) = LOWER(?) AND e.deleted_at IS NULL",
        (raw_name,),
    ).fetchone()
    if row:
        entity = repo.get_by_id(row["entity_id"])
        if entity:
            # Follow merge target
            if entity.merge_target_id:
                merged = repo.get_by_id(entity.merge_target_id)
                if merged:
                    entity = merged
            return (entity, 0.7)

    return None


# ---------------------------------------------------------------------------
# Attribution
# ---------------------------------------------------------------------------


def attribute_synthesis_items(
    synthesis_output: DailySynthesisOutput,
    repo: EntityRepository,
    target_date: str,
) -> AttributionResult:
    """Attribute entity names in synthesis items to registered entities.

    For each item, builds a candidate name set from entity_names.
    For CommitmentRow, also adds the who field (excluding empty/TBD).
    Returns per-item EntityReference lists and EntityMention records.
    """
    all_mentions: list[EntityMention] = []
    entity_counter: Counter = Counter()
    entity_info: dict[str, tuple[str, str]] = {}  # entity_id -> (name, type)

    def _process_items(
        items: list[SynthesisItem] | list[CommitmentRow],
        source_type: str,
    ) -> list[list[EntityReference]]:
        all_refs: list[list[EntityReference]] = []

        for item in items:
            item_refs: list[EntityReference] = []
            seen_ids: set[str] = set()

            # Build candidate names
            candidates: list[str] = list(getattr(item, "entity_names", []))
            if isinstance(item, CommitmentRow) and item.who:
                who = item.who.strip()
                if who and who.lower() not in ("tbd", ""):
                    candidates.append(who)

            for name in candidates:
                if not name or not name.strip():
                    continue

                result = match_name_to_entity(name, repo)
                if result is None:
                    continue

                entity, confidence = result
                if entity.id in seen_ids:
                    continue
                seen_ids.add(entity.id)

                item_refs.append(
                    EntityReference(
                        entity_id=entity.id,
                        name=entity.name,
                        confidence=confidence,
                    )
                )

                # Build content hash for source_id
                if isinstance(item, CommitmentRow):
                    source_id = commitment_content_hash(
                        item.who, item.what, item.by_when
                    )
                else:
                    source_id = content_hash(item.content)

                all_mentions.append(
                    EntityMention(
                        id=uuid4().hex,
                        entity_id=entity.id,
                        source_type=source_type,
                        source_id=source_id,
                        source_date=target_date,
                        confidence=confidence,
                        context_snippet=(
                            item.content[:100] if hasattr(item, "content") else None
                        ),
                        created_at=_now_utc(),
                    )
                )

                entity_counter[entity.id] += 1
                entity_info[entity.id] = (entity.name, entity.entity_type.value)

            all_refs.append(item_refs)

        return all_refs

    substance_refs = _process_items(synthesis_output.substance, "substance")
    decision_refs = _process_items(synthesis_output.decisions, "decision")
    commitment_refs = _process_items(synthesis_output.commitments, "commitment")

    # Build entity summary
    entity_summary = [
        EntitySummaryEntry(
            entity_id=eid,
            name=entity_info[eid][0],
            entity_type=entity_info[eid][1],
            mention_count=count,
        )
        for eid, count in entity_counter.most_common()
    ]

    return AttributionResult(
        substance_refs=substance_refs,
        decision_refs=decision_refs,
        commitment_refs=commitment_refs,
        mentions=all_mentions,
        entity_summary=entity_summary,
    )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def persist_mentions(
    conn: sqlite3.Connection,
    mentions: list[EntityMention],
    target_date: str,
) -> int:
    """Persist entity mentions to SQLite, replacing existing for the date.

    Idempotent: DELETE then INSERT for the target date.
    Returns number of mentions persisted.
    """
    conn.execute(
        "DELETE FROM entity_mentions WHERE source_date = ?", (target_date,)
    )
    for m in mentions:
        conn.execute(
            "INSERT INTO entity_mentions "
            "(id, entity_id, source_type, source_id, source_date, confidence, "
            "context_snippet, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (m.id, m.entity_id, m.source_type, m.source_id, m.source_date,
             m.confidence, m.context_snippet, m.created_at),
        )
    conn.commit()
    return len(mentions)
