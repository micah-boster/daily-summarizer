"""Cache retention policy: auto-delete old raw data files.

Runs at pipeline startup before ingest begins. Never touches
processed output (daily summaries, quality files).
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def cleanup_raw_cache(
    output_dir: Path,
    raw_ttl_days: int = 14,
    dedup_log_ttl_days: int = 30,
) -> tuple[int, int]:
    """Delete raw cache files older than TTL.

    Walks output_dir/raw/ and output_dir/dedup_logs/ only.
    Never touches output_dir/daily/, output_dir/quality/, or
    output_dir/validation/.

    Args:
        output_dir: Root output directory.
        raw_ttl_days: Max age in days for raw cache files.
        dedup_log_ttl_days: Max age in days for dedup log files.

    Returns:
        Tuple of (files_deleted, bytes_freed).
    """
    deleted_count = 0
    bytes_freed = 0

    # Clean raw cache
    raw_dir = output_dir / "raw"
    if raw_dir.exists():
        cutoff = time.time() - (raw_ttl_days * 86400)
        for path in list(raw_dir.rglob("*")):
            if path.is_file():
                try:
                    stat = path.stat()
                    if stat.st_mtime < cutoff:
                        bytes_freed += stat.st_size
                        path.unlink()
                        deleted_count += 1
                except OSError as e:
                    logger.warning("Failed to clean %s: %s", path, e)

        # Clean up empty directories bottom-up
        for dirpath in sorted(raw_dir.rglob("*"), reverse=True):
            if dirpath.is_dir():
                try:
                    dirpath.rmdir()  # Only removes if empty
                except OSError:
                    pass

    # Clean dedup logs
    dedup_dir = output_dir / "dedup_logs"
    if dedup_dir.exists():
        cutoff = time.time() - (dedup_log_ttl_days * 86400)
        for path in list(dedup_dir.rglob("*")):
            if path.is_file():
                try:
                    stat = path.stat()
                    if stat.st_mtime < cutoff:
                        bytes_freed += stat.st_size
                        path.unlink()
                        deleted_count += 1
                except OSError as e:
                    logger.warning("Failed to clean dedup log %s: %s", path, e)

    if deleted_count:
        logger.info(
            "Cache cleanup: deleted %d files, freed %d bytes",
            deleted_count,
            bytes_freed,
        )

    return deleted_count, bytes_freed
