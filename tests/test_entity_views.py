"""Tests for entity views module -- scoped views, enriched lists, significance scoring."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from uuid import uuid4

import pytest

from src.entity.db import get_connection
from src.entity.models import _now_utc
from src.entity.repository import EntityRepository
from src.entity.views import (
    ActivityItem,
    EnrichedEntity,
    EntityScopedView,
    get_enriched_entity_list,
    get_entity_scoped_view,
    score_significance,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_entities.db")


@pytest.fixture
def repo(db_path):
    r = EntityRepository(db_path)
    r.connect()
    yield r
    r.close()


def _add_mention(conn, entity_id, source_type, source_date, snippet=None, confidence=1.0):
    """Helper to insert a mention directly."""
    conn.execute(
        "INSERT INTO entity_mentions "
        "(id, entity_id, source_type, source_id, source_date, confidence, context_snippet, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (uuid4().hex, entity_id, source_type, uuid4().hex, source_date, confidence, snippet, _now_utc()),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# score_significance tests
# ---------------------------------------------------------------------------


class TestScoreSignificance:
    def test_decision_base_score(self):
        today = date(2026, 4, 8)
        score = score_significance("decision", "2026-01-01", 1.0, today)
        # Base 3.0, no recency bonus (> 14 days), confidence 1.0
        assert score == 3.0

    def test_commitment_base_score(self):
        today = date(2026, 4, 8)
        score = score_significance("commitment", "2026-01-01", 1.0, today)
        assert score == 2.5

    def test_substance_base_score(self):
        today = date(2026, 4, 8)
        score = score_significance("substance", "2026-01-01", 1.0, today)
        assert score == 1.0

    def test_recency_within_7_days(self):
        today = date(2026, 4, 8)
        recent = (today - timedelta(days=3)).isoformat()
        score = score_significance("substance", recent, 1.0, today)
        # Base 1.0 + recency 1.0 = 2.0
        assert score == 2.0

    def test_recency_within_14_days(self):
        today = date(2026, 4, 8)
        recent = (today - timedelta(days=10)).isoformat()
        score = score_significance("substance", recent, 1.0, today)
        # Base 1.0 + recency 0.5 = 1.5
        assert score == 1.5

    def test_confidence_multiplier(self):
        today = date(2026, 4, 8)
        score = score_significance("decision", "2026-01-01", 0.5, today)
        # Base 3.0 * confidence 0.5 = 1.5
        assert score == 1.5

    def test_recency_and_confidence_combined(self):
        today = date(2026, 4, 8)
        recent = (today - timedelta(days=2)).isoformat()
        score = score_significance("decision", recent, 0.7, today)
        # (Base 3.0 + recency 1.0) * confidence 0.7 = 2.8
        assert score == pytest.approx(2.8)


# ---------------------------------------------------------------------------
# Repository query tests
# ---------------------------------------------------------------------------


class TestRepositoryMentionQueries:
    def test_get_entity_mentions_in_range(self, repo):
        entity = repo.add_entity("Affirm", "partner")
        _add_mention(repo._conn, entity.id, "substance", "2026-03-15", "Affirm discussed")
        _add_mention(repo._conn, entity.id, "decision", "2026-04-01", "Affirm decided X")
        _add_mention(repo._conn, entity.id, "substance", "2026-04-10", "Affirm update")

        results = repo.get_entity_mentions_in_range(entity.id, "2026-04-01", "2026-04-30")
        assert len(results) == 2
        assert results[0]["source_date"] == "2026-04-10"  # DESC order

    def test_mentions_no_date_filter(self, repo):
        entity = repo.add_entity("Affirm", "partner")
        _add_mention(repo._conn, entity.id, "substance", "2025-01-01", "Old mention")
        _add_mention(repo._conn, entity.id, "decision", "2026-04-01", "New mention")

        results = repo.get_entity_mentions_in_range(entity.id)
        assert len(results) == 2

    def test_mentions_include_merged_entities(self, repo):
        target = repo.add_entity("Affirm Inc", "partner")
        source = repo.add_entity("Affirm", "partner")
        # Simulate merge: set merge_target_id on source
        repo._conn.execute(
            "UPDATE entities SET merge_target_id = ? WHERE id = ?",
            (target.id, source.id),
        )
        repo._conn.commit()

        _add_mention(repo._conn, source.id, "substance", "2026-04-01", "Pre-merge mention")
        _add_mention(repo._conn, target.id, "decision", "2026-04-02", "Post-merge mention")

        results = repo.get_entity_mentions_in_range(target.id)
        assert len(results) == 2

    def test_get_entity_stats(self, repo):
        entity = repo.add_entity("Colin", "person")
        _add_mention(repo._conn, entity.id, "substance", "2026-03-01", "Colin substance")
        _add_mention(repo._conn, entity.id, "commitment", "2026-04-01", "Colin owes X")
        _add_mention(repo._conn, entity.id, "commitment", "2026-04-05", "Colin owes Y")
        _add_mention(repo._conn, entity.id, "decision", "2026-04-08", "Colin decided")

        stats = repo.get_entity_stats(entity.id)
        assert stats["mention_count"] == 4
        assert stats["commitment_count"] == 2
        assert stats["last_active_date"] == "2026-04-08"

    def test_get_entity_stats_no_mentions(self, repo):
        entity = repo.add_entity("NewEntity", "partner")
        stats = repo.get_entity_stats(entity.id)
        assert stats["mention_count"] == 0
        assert stats["commitment_count"] == 0
        assert stats["last_active_date"] is None


# ---------------------------------------------------------------------------
# get_entity_scoped_view tests
# ---------------------------------------------------------------------------


class TestGetEntityScopedView:
    def test_basic_scoped_view(self, repo):
        entity = repo.add_entity("Affirm", "partner")
        _add_mention(repo._conn, entity.id, "substance", "2026-04-01", "Affirm sync")
        _add_mention(repo._conn, entity.id, "decision", "2026-04-02", "Affirm strategy shift")
        _add_mention(repo._conn, entity.id, "commitment", "2026-04-03", "Affirm owes report")

        view = get_entity_scoped_view(repo, "Affirm", date(2026, 4, 1), date(2026, 4, 30))

        assert view.entity_name == "Affirm"
        assert view.entity_type == "partner"
        assert view.total_mentions == 3
        assert len(view.open_commitments) == 1
        assert len(view.highlights) <= 5
        assert len(view.activity_by_date) > 0

    def test_default_30_day_range(self, repo):
        entity = repo.add_entity("Affirm", "partner")
        old_date = (date.today() - timedelta(days=60)).isoformat()
        recent_date = (date.today() - timedelta(days=5)).isoformat()
        _add_mention(repo._conn, entity.id, "substance", old_date, "Old mention")
        _add_mention(repo._conn, entity.id, "substance", recent_date, "Recent mention")

        view = get_entity_scoped_view(repo, "Affirm")

        # Should only show the recent one (within 30 days)
        assert view.total_mentions == 1

    def test_entity_not_found(self, repo):
        with pytest.raises(ValueError, match="Entity not found"):
            get_entity_scoped_view(repo, "NonExistent")

    def test_activity_grouped_by_date(self, repo):
        entity = repo.add_entity("Affirm", "partner")
        _add_mention(repo._conn, entity.id, "substance", "2026-04-01", "Item A")
        _add_mention(repo._conn, entity.id, "decision", "2026-04-01", "Item B")
        _add_mention(repo._conn, entity.id, "substance", "2026-04-02", "Item C")

        view = get_entity_scoped_view(repo, "Affirm", date(2026, 4, 1), date(2026, 4, 30))

        # Should have 2 date groups
        assert len(view.activity_by_date) == 2
        # First group (most recent) should be April 2
        assert view.activity_by_date[0]["date"] == "2026-04-02"

    def test_highlights_limited_to_5(self, repo):
        entity = repo.add_entity("Affirm", "partner")
        for i in range(10):
            d = (date(2026, 4, 1) + timedelta(days=i)).isoformat()
            _add_mention(repo._conn, entity.id, "decision", d, "Decision %d" % i)

        view = get_entity_scoped_view(repo, "Affirm", date(2026, 4, 1), date(2026, 4, 30))
        assert len(view.highlights) == 5

    def test_zero_mentions_in_range(self, repo):
        entity = repo.add_entity("Affirm", "partner")
        _add_mention(repo._conn, entity.id, "substance", "2025-01-01", "Old mention")

        view = get_entity_scoped_view(repo, "Affirm", date(2026, 4, 1), date(2026, 4, 30))
        assert view.total_mentions == 0
        assert view.activity_by_date == []


# ---------------------------------------------------------------------------
# get_enriched_entity_list tests
# ---------------------------------------------------------------------------


class TestGetEnrichedEntityList:
    def test_enriched_list_with_stats(self, repo):
        e1 = repo.add_entity("Affirm", "partner")
        e2 = repo.add_entity("Colin", "person")
        _add_mention(repo._conn, e1.id, "substance", "2026-04-05", "Affirm thing")
        _add_mention(repo._conn, e1.id, "commitment", "2026-04-06", "Affirm commitment")
        _add_mention(repo._conn, e2.id, "decision", "2026-04-08", "Colin decided")

        entities = get_enriched_entity_list(repo)

        assert len(entities) == 2
        # Default sort by last-active desc: Colin (04-08) first, Affirm (04-06) second
        assert entities[0].name == "Colin"
        assert entities[0].mention_count == 1
        assert entities[1].name == "Affirm"
        assert entities[1].mention_count == 2
        assert entities[1].commitment_count == 1

    def test_sort_by_mentions(self, repo):
        e1 = repo.add_entity("Affirm", "partner")
        e2 = repo.add_entity("Colin", "person")
        _add_mention(repo._conn, e1.id, "substance", "2026-04-01")
        _add_mention(repo._conn, e1.id, "substance", "2026-04-02")
        _add_mention(repo._conn, e2.id, "substance", "2026-04-03")

        entities = get_enriched_entity_list(repo, sort_by="mentions")
        assert entities[0].name == "Affirm"  # 2 mentions
        assert entities[1].name == "Colin"  # 1 mention

    def test_sort_by_name(self, repo):
        repo.add_entity("Zebra Corp", "partner")
        repo.add_entity("Alpha Inc", "partner")

        entities = get_enriched_entity_list(repo, sort_by="name")
        assert entities[0].name == "Alpha Inc"
        assert entities[1].name == "Zebra Corp"

    def test_filter_by_type(self, repo):
        repo.add_entity("Affirm", "partner")
        repo.add_entity("Colin", "person")

        partners = get_enriched_entity_list(repo, entity_type="partner")
        assert len(partners) == 1
        assert partners[0].name == "Affirm"

    def test_entity_with_no_mentions(self, repo):
        repo.add_entity("NewEntity", "partner")

        entities = get_enriched_entity_list(repo)
        assert len(entities) == 1
        assert entities[0].mention_count == 0
        assert entities[0].commitment_count == 0
        assert entities[0].last_active_date is None
