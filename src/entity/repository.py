"""Data access layer for the entity registry.

All sqlite3 interactions for entity CRUD, alias management, and name
resolution are confined to this module and ``db.py``.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from uuid import uuid4

from src.entity.db import get_connection
from src.entity.models import Alias, Entity, EntityType, MergeProposal, _now_utc

logger = logging.getLogger(__name__)


class EntityRepository:
    """Repository providing CRUD, alias management, and name resolution."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        """Open the database connection (with migrations)."""
        self._conn = get_connection(self._db_path)

    def close(self) -> None:
        """Close the connection if open."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> EntityRepository:
        self.connect()
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Entity CRUD
    # ------------------------------------------------------------------

    def add_entity(
        self,
        name: str,
        entity_type: str,
        organization_id: str | None = None,
        hubspot_id: str | None = None,
        slack_channel: str | None = None,
        metadata: dict | None = None,
    ) -> Entity:
        """Create a new entity and return it."""
        if not name or not name.strip():
            raise ValueError("Entity name must not be empty")

        entity_id = uuid4().hex
        now = _now_utc()
        meta_json = json.dumps(metadata or {})

        self._conn.execute(
            "INSERT INTO entities "
            "(id, name, entity_type, organization_id, hubspot_id, slack_channel, "
            "metadata, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (entity_id, name.strip(), entity_type, organization_id,
             hubspot_id, slack_channel, meta_json, now, now),
        )
        self._conn.commit()
        logger.info("Created entity %s: %s (%s)", entity_id, name, entity_type)

        return Entity(
            id=entity_id,
            name=name.strip(),
            entity_type=EntityType(entity_type),
            organization_id=organization_id,
            hubspot_id=hubspot_id,
            slack_channel=slack_channel,
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
        )

    def get_by_id(self, entity_id: str) -> Entity | None:
        """Fetch an entity by ID (excludes soft-deleted)."""
        row = self._conn.execute(
            "SELECT * FROM entities WHERE id = ? AND deleted_at IS NULL",
            (entity_id,),
        ).fetchone()
        return self._row_to_entity(row) if row else None

    def get_by_name(self, name: str) -> Entity | None:
        """Case-insensitive lookup by canonical name (excludes soft-deleted)."""
        row = self._conn.execute(
            "SELECT * FROM entities WHERE LOWER(name) = LOWER(?) AND deleted_at IS NULL",
            (name,),
        ).fetchone()
        return self._row_to_entity(row) if row else None

    def get_by_name_including_deleted(self, name: str) -> Entity | None:
        """Case-insensitive lookup by canonical name (includes soft-deleted)."""
        row = self._conn.execute(
            "SELECT * FROM entities WHERE LOWER(name) = LOWER(?)",
            (name,),
        ).fetchone()
        return self._row_to_entity(row) if row else None

    def list_entities(
        self,
        entity_type: str | None = None,
        include_deleted: bool = False,
    ) -> list[Entity]:
        """List entities with optional type filter."""
        query = "SELECT * FROM entities"
        params: list[str] = []
        conditions: list[str] = []

        if not include_deleted:
            conditions.append("deleted_at IS NULL")
        if entity_type is not None:
            conditions.append("entity_type = ?")
            params.append(entity_type)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY name"

        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_entity(row) for row in rows]

    def update_entity(
        self,
        entity_id: str,
        name: str | None = None,
        entity_type: str | None = None,
    ) -> "Entity | None":
        """Update an entity's name and/or type. Returns updated entity or None."""
        entity = self.get_by_id(entity_id)
        if entity is None:
            return None

        new_name = name.strip() if name else entity.name
        new_type = entity_type if entity_type else str(entity.entity_type)
        now = _now_utc()

        self._conn.execute(
            "BEGIN IMMEDIATE",
        )
        try:
            self._conn.execute(
                "UPDATE entities SET name = ?, entity_type = ?, updated_at = ? "
                "WHERE id = ? AND deleted_at IS NULL",
                (new_name, new_type, now, entity_id),
            )
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

        return self.get_by_id(entity_id)

    def remove_entity(self, entity_id: str) -> bool:
        """Soft-delete an entity by setting deleted_at."""
        now = _now_utc()
        cursor = self._conn.execute(
            "UPDATE entities SET deleted_at = ?, updated_at = ? "
            "WHERE id = ? AND deleted_at IS NULL",
            (now, now, entity_id),
        )
        self._conn.commit()
        if cursor.rowcount > 0:
            logger.info("Soft-deleted entity %s", entity_id)
            return True
        return False

    def _row_to_entity(self, row: sqlite3.Row) -> Entity:
        """Convert a database row to an Entity model."""
        return Entity(
            id=row["id"],
            name=row["name"],
            entity_type=row["entity_type"],
            organization_id=row["organization_id"],
            hubspot_id=row["hubspot_id"],
            slack_channel=row["slack_channel"],
            metadata=row["metadata"],
            merge_target_id=row["merge_target_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            deleted_at=row["deleted_at"],
        )

    def update_hubspot_id(self, entity_id: str, hubspot_id: str, metadata_updates: dict | None = None) -> bool:
        """Update HubSpot ID and optional metadata for an entity."""
        if metadata_updates:
            row = self._conn.execute(
                "SELECT metadata FROM entities WHERE id = ? AND deleted_at IS NULL",
                (entity_id,),
            ).fetchone()
            if row is None:
                return False
            current_meta = json.loads(row["metadata"]) if row["metadata"] else {}
            current_meta.update(metadata_updates)
            meta_json = json.dumps(current_meta)
            self._conn.execute(
                "UPDATE entities SET hubspot_id = ?, metadata = ?, updated_at = ? WHERE id = ?",
                (hubspot_id, meta_json, _now_utc(), entity_id),
            )
        else:
            self._conn.execute(
                "UPDATE entities SET hubspot_id = ?, updated_at = ? WHERE id = ?",
                (hubspot_id, _now_utc(), entity_id),
            )
        self._conn.commit()
        return True

    # ------------------------------------------------------------------
    # Alias management
    # ------------------------------------------------------------------

    def add_alias(self, entity_id: str, alias: str) -> Alias:
        """Add an alias for an entity."""
        # Verify entity exists
        entity = self.get_by_id(entity_id)
        if entity is None:
            raise ValueError("Entity %s not found" % entity_id)

        alias_id = uuid4().hex
        now = _now_utc()

        try:
            self._conn.execute(
                "INSERT INTO aliases (id, entity_id, alias, created_at) "
                "VALUES (?, ?, ?, ?)",
                (alias_id, entity_id, alias, now),
            )
            self._conn.commit()
        except sqlite3.IntegrityError:
            raise ValueError("Alias '%s' already exists" % alias)

        logger.info("Added alias '%s' for entity %s", alias, entity_id)
        return Alias(id=alias_id, entity_id=entity_id, alias=alias, created_at=now)

    def remove_alias(self, alias: str) -> bool:
        """Remove an alias (case-insensitive)."""
        cursor = self._conn.execute(
            "DELETE FROM aliases WHERE LOWER(alias) = LOWER(?)",
            (alias,),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def list_aliases(self, entity_id: str) -> list[Alias]:
        """List all aliases for an entity."""
        rows = self._conn.execute(
            "SELECT * FROM aliases WHERE entity_id = ? ORDER BY alias",
            (entity_id,),
        ).fetchall()
        return [
            Alias(
                id=row["id"],
                entity_id=row["entity_id"],
                alias=row["alias"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Name resolution
    # ------------------------------------------------------------------

    def resolve_name(self, name: str) -> Entity | None:
        """Resolve a name to an entity via canonical name or alias.

        Two-step resolution:
        1. Try canonical name (case-insensitive)
        2. Try alias lookup (case-insensitive)

        If the resolved entity has a ``merge_target_id``, follow the pointer
        (one level only).
        """
        # Step 1: canonical name
        entity = self.get_by_name(name)

        # Step 2: alias lookup
        if entity is None:
            row = self._conn.execute(
                "SELECT a.entity_id FROM aliases a "
                "JOIN entities e ON a.entity_id = e.id "
                "WHERE LOWER(a.alias) = LOWER(?) AND e.deleted_at IS NULL",
                (name,),
            ).fetchone()
            if row:
                entity = self.get_by_id(row["entity_id"])

        # Follow merge target (one level)
        if entity and entity.merge_target_id:
            merged = self.get_by_id(entity.merge_target_id)
            if merged:
                return merged

        return entity

    # ------------------------------------------------------------------
    # Mention queries
    # ------------------------------------------------------------------

    def get_entity_mentions_in_range(
        self,
        entity_id: str,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[dict]:
        """Fetch mentions for an entity within a date range.

        Includes mentions from entities whose merge_target_id equals this
        entity (aggregating pre-merge mentions).
        """
        query = """
            SELECT em.source_type, em.source_date, em.confidence,
                   em.context_snippet, em.source_id
            FROM entity_mentions em
            WHERE (em.entity_id = ?
                   OR em.entity_id IN (
                       SELECT id FROM entities WHERE merge_target_id = ?
                   ))
        """
        params: list[str] = [entity_id, entity_id]
        if from_date:
            query += " AND em.source_date >= ?"
            params.append(from_date)
        if to_date:
            query += " AND em.source_date <= ?"
            params.append(to_date)
        query += " ORDER BY em.source_date DESC, em.source_type"
        return [dict(row) for row in self._conn.execute(query, params).fetchall()]

    def get_entity_stats(self, entity_id: str) -> dict:
        """Return aggregate mention statistics for an entity.

        Returns dict with mention_count, commitment_count, last_active_date.
        Includes mentions from merged entities.
        """
        row = self._conn.execute(
            """
            SELECT
                COUNT(*) AS mention_count,
                SUM(CASE WHEN em.source_type = 'commitment' THEN 1 ELSE 0 END) AS commitment_count,
                MAX(em.source_date) AS last_active_date
            FROM entity_mentions em
            WHERE em.entity_id = ?
               OR em.entity_id IN (
                   SELECT id FROM entities WHERE merge_target_id = ?
               )
            """,
            (entity_id, entity_id),
        ).fetchone()
        return {
            "mention_count": row["mention_count"],
            "commitment_count": row["commitment_count"] or 0,
            "last_active_date": row["last_active_date"],
        }

    def get_mention_count(self, entity_id: str) -> int:
        """Count total mentions for an entity."""
        row = self._conn.execute(
            "SELECT COUNT(*) AS cnt FROM entity_mentions WHERE entity_id = ?",
            (entity_id,),
        ).fetchone()
        return row["cnt"]

    def get_mention_sources(self, entity_id: str) -> list[str]:
        """Return distinct source types that mention this entity."""
        rows = self._conn.execute(
            "SELECT DISTINCT source_type FROM entity_mentions WHERE entity_id = ? ORDER BY source_type",
            (entity_id,),
        ).fetchall()
        return [row["source_type"] for row in rows]

    def get_related_entities(self, entity_id: str, limit: int = 10) -> list[dict]:
        """Find entities that co-occur with the given entity.

        Co-occurrence is defined as sharing the same (source_date, source_id)
        in entity_mentions.  Includes mentions from merged entities (where
        merge_target_id equals this entity).

        Returns a list of dicts with keys: entity_id, name, entity_type,
        co_mention_count.  Sorted by co_mention_count descending.
        """
        rows = self._conn.execute(
            """
            SELECT e.id AS entity_id, e.name, e.entity_type,
                   COUNT(*) AS co_mention_count
            FROM entity_mentions em1
            JOIN entity_mentions em2
                ON em1.source_date = em2.source_date
               AND em1.source_id = em2.source_id
               AND em1.entity_id != em2.entity_id
            JOIN entities e
                ON em2.entity_id = e.id
               AND e.deleted_at IS NULL
            WHERE (em1.entity_id = ?
                   OR em1.entity_id IN (
                       SELECT id FROM entities WHERE merge_target_id = ?
                   ))
            GROUP BY e.id, e.name, e.entity_type
            ORDER BY co_mention_count DESC
            LIMIT ?
            """,
            (entity_id, entity_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Merge proposal management
    # ------------------------------------------------------------------

    def save_proposal(
        self,
        source_id: str,
        target_id: str,
        reason: str,
        status: str = "pending",
    ) -> MergeProposal:
        """Create a merge proposal record."""
        proposal_id = uuid4().hex
        now = _now_utc()
        resolved_at = now if status != "pending" else None

        self._conn.execute(
            "INSERT INTO merge_proposals "
            "(id, source_entity_id, target_entity_id, proposed_by, reason, status, created_at, resolved_at) "
            "VALUES (?, ?, ?, 'system', ?, ?, ?, ?)",
            (proposal_id, source_id, target_id, reason, status, now, resolved_at),
        )
        self._conn.commit()

        return MergeProposal(
            id=proposal_id,
            source_entity_id=source_id,
            target_entity_id=target_id,
            proposed_by="system",
            reason=reason,
            status=status,
            created_at=now,
            resolved_at=resolved_at,
        )

    def get_existing_proposals(self, source_id: str, target_id: str) -> list[MergeProposal]:
        """Find existing proposals for a pair (checks both orderings)."""
        rows = self._conn.execute(
            "SELECT * FROM merge_proposals "
            "WHERE (source_entity_id = ? AND target_entity_id = ?) "
            "   OR (source_entity_id = ? AND target_entity_id = ?)",
            (source_id, target_id, target_id, source_id),
        ).fetchall()
        return [
            MergeProposal(
                id=row["id"],
                source_entity_id=row["source_entity_id"],
                target_entity_id=row["target_entity_id"],
                proposed_by=row["proposed_by"],
                reason=row["reason"],
                status=row["status"],
                created_at=row["created_at"],
                resolved_at=row["resolved_at"],
            )
            for row in rows
        ]

    def update_proposal_status(self, proposal_id: str, status: str) -> bool:
        """Update a proposal's status and set resolved_at timestamp."""
        now = _now_utc()
        cursor = self._conn.execute(
            "UPDATE merge_proposals SET status = ?, resolved_at = ? WHERE id = ?",
            (status, now, proposal_id),
        )
        self._conn.commit()
        return cursor.rowcount > 0
