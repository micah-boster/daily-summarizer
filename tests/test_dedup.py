"""Tests for cross-source dedup pre-filter."""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from src.config import make_test_config
from src.dedup import dedup_source_items
from src.models.sources import ContentType, SourceItem, SourceType


def _make_item(
    title: str,
    source_type: SourceType = SourceType.SLACK_MESSAGE,
    content: str = "Some content",
    ts: datetime | None = None,
    participants: list[str] | None = None,
    display_context: str = "",
    item_id: str | None = None,
) -> SourceItem:
    if ts is None:
        ts = datetime(2026, 4, 5, 10, 0, 0, tzinfo=timezone.utc)
    return SourceItem(
        id=item_id or f"item_{title[:10]}_{source_type.value}",
        source_type=source_type,
        content_type=ContentType.MESSAGE,
        title=title,
        timestamp=ts,
        content=content,
        participants=participants or [],
        source_url="https://example.com",
        display_context=display_context or source_type.value,
    )


class TestDedup:
    """Tests for dedup_source_items."""

    def test_dedup_merges_identical_titles_same_day(self, tmp_path):
        items = [
            _make_item("Q2 Planning", SourceType.SLACK_MESSAGE, display_context="Slack #general"),
            _make_item("Q2 Planning", SourceType.NOTION_PAGE, display_context="Notion Q2"),
        ]
        config = make_test_config(dedup={"enabled": True, "log_dir": str(tmp_path)})
        result = dedup_source_items(items, config, date(2026, 4, 5))

        assert len(result) == 1
        assert "Slack #general" in result[0].display_context
        assert "Notion Q2" in result[0].display_context

    def test_dedup_merges_near_identical_titles(self, tmp_path):
        items = [
            _make_item("Q2 Planning Review Discussion", SourceType.SLACK_MESSAGE),
            _make_item("Q2 Planning Review Discussions", SourceType.NOTION_PAGE),
        ]
        config = make_test_config(dedup={"enabled": True, "log_dir": str(tmp_path)})
        result = dedup_source_items(items, config, date(2026, 4, 5))

        assert len(result) == 1

    def test_dedup_preserves_distinct_items(self, tmp_path):
        items = [
            _make_item("Q2 Planning", SourceType.SLACK_MESSAGE),
            _make_item("Budget Review", SourceType.NOTION_PAGE),
        ]
        config = make_test_config(dedup={"enabled": True, "log_dir": str(tmp_path)})
        result = dedup_source_items(items, config, date(2026, 4, 5))

        assert len(result) == 2

    def test_dedup_does_not_merge_different_days(self, tmp_path):
        items = [
            _make_item(
                "Q2 Planning",
                ts=datetime(2026, 4, 5, 10, 0, 0, tzinfo=timezone.utc),
            ),
            _make_item(
                "Q2 Planning",
                ts=datetime(2026, 4, 7, 10, 0, 0, tzinfo=timezone.utc),
                source_type=SourceType.NOTION_PAGE,
            ),
        ]
        config = make_test_config(dedup={"enabled": True, "log_dir": str(tmp_path)})
        result = dedup_source_items(items, config, date(2026, 4, 5))

        # Only the target_date item + the other_items (different day)
        assert len(result) == 2

    def test_dedup_merge_keeps_longer_content(self, tmp_path):
        short = _make_item("Q2 Planning", content="Short", item_id="short")
        long = _make_item(
            "Q2 Planning",
            content="This is much longer content with details about the planning session",
            source_type=SourceType.NOTION_PAGE,
            item_id="long",
        )
        config = make_test_config(dedup={"enabled": True, "log_dir": str(tmp_path)})
        result = dedup_source_items([short, long], config, date(2026, 4, 5))

        assert len(result) == 1
        assert "longer content" in result[0].content

    def test_dedup_merge_combines_participants(self, tmp_path):
        items = [
            _make_item("Q2 Planning", participants=["Alice"], item_id="a"),
            _make_item(
                "Q2 Planning",
                participants=["Bob"],
                source_type=SourceType.NOTION_PAGE,
                item_id="b",
            ),
        ]
        config = make_test_config(dedup={"enabled": True, "log_dir": str(tmp_path)})
        result = dedup_source_items(items, config, date(2026, 4, 5))

        assert len(result) == 1
        assert "Alice" in result[0].participants
        assert "Bob" in result[0].participants

    def test_dedup_logs_decisions(self, tmp_path):
        items = [
            _make_item("Q2 Planning", display_context="Slack #general", item_id="a"),
            _make_item(
                "Q2 Planning",
                source_type=SourceType.NOTION_PAGE,
                display_context="Notion",
                item_id="b",
            ),
        ]
        config = make_test_config(dedup={"enabled": True, "log_dir": str(tmp_path)})
        dedup_source_items(items, config, date(2026, 4, 5))

        log_file = tmp_path / "dedup_2026-04-05.log"
        assert log_file.exists()
        content = log_file.read_text()
        assert "Merged" in content
        assert "Q2 Planning" in content

    def test_dedup_disabled_config(self, tmp_path):
        items = [
            _make_item("Q2 Planning", item_id="a"),
            _make_item("Q2 Planning", source_type=SourceType.NOTION_PAGE, item_id="b"),
        ]
        config = make_test_config(dedup={"enabled": False, "log_dir": str(tmp_path)})
        result = dedup_source_items(items, config, date(2026, 4, 5))

        assert len(result) == 2
        assert not (tmp_path / "dedup_2026-04-05.log").exists()

    def test_dedup_empty_input(self, tmp_path):
        config = make_test_config(dedup={"enabled": True, "log_dir": str(tmp_path)})
        result = dedup_source_items([], config, date(2026, 4, 5))

        assert result == []
