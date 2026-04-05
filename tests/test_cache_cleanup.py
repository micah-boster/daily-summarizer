"""Tests for cache retention policy."""
from __future__ import annotations

import os
import time
from pathlib import Path

from src.cache_cleanup import cleanup_raw_cache


class TestCacheCleanup:
    """Tests for cleanup_raw_cache."""

    def _create_file(self, path: Path, content: str = "data", age_days: int = 0) -> None:
        """Create a file and optionally set its mtime to simulate age."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        if age_days > 0:
            old_time = time.time() - (age_days * 86400)
            os.utime(path, (old_time, old_time))

    def test_cleanup_deletes_old_raw_files(self, tmp_path):
        self._create_file(tmp_path / "raw" / "2026" / "01" / "01" / "calendar.json", age_days=20)

        deleted, freed = cleanup_raw_cache(tmp_path, raw_ttl_days=14)

        assert deleted == 1
        assert freed > 0
        assert not (tmp_path / "raw" / "2026" / "01" / "01" / "calendar.json").exists()

    def test_cleanup_preserves_recent_raw_files(self, tmp_path):
        self._create_file(tmp_path / "raw" / "2026" / "04" / "04" / "calendar.json", age_days=1)

        deleted, freed = cleanup_raw_cache(tmp_path, raw_ttl_days=14)

        assert deleted == 0
        assert freed == 0
        assert (tmp_path / "raw" / "2026" / "04" / "04" / "calendar.json").exists()

    def test_cleanup_never_touches_daily_output(self, tmp_path):
        self._create_file(tmp_path / "daily" / "2026" / "01" / "summary.md", age_days=60)

        cleanup_raw_cache(tmp_path, raw_ttl_days=14)

        assert (tmp_path / "daily" / "2026" / "01" / "summary.md").exists()

    def test_cleanup_never_touches_quality(self, tmp_path):
        self._create_file(tmp_path / "quality" / "report.json", age_days=60)

        cleanup_raw_cache(tmp_path, raw_ttl_days=14)

        assert (tmp_path / "quality" / "report.json").exists()

    def test_cleanup_returns_count_and_bytes(self, tmp_path):
        for i in range(3):
            self._create_file(
                tmp_path / "raw" / "old" / f"file{i}.json",
                content=f"data_{i}" * 10,
                age_days=20,
            )

        deleted, freed = cleanup_raw_cache(tmp_path, raw_ttl_days=14)

        assert deleted == 3
        assert freed > 0

    def test_cleanup_handles_empty_raw_dir(self, tmp_path):
        deleted, freed = cleanup_raw_cache(tmp_path, raw_ttl_days=14)

        assert deleted == 0
        assert freed == 0

    def test_cleanup_dedup_logs_separate_ttl(self, tmp_path):
        # 25-day-old dedup log (within 30-day TTL)
        self._create_file(tmp_path / "dedup_logs" / "dedup_2026-03-10.log", age_days=25)
        # 35-day-old dedup log (outside 30-day TTL)
        self._create_file(tmp_path / "dedup_logs" / "dedup_2026-02-28.log", age_days=35)

        deleted, freed = cleanup_raw_cache(tmp_path, raw_ttl_days=14, dedup_log_ttl_days=30)

        assert (tmp_path / "dedup_logs" / "dedup_2026-03-10.log").exists()
        assert not (tmp_path / "dedup_logs" / "dedup_2026-02-28.log").exists()
        assert deleted == 1
