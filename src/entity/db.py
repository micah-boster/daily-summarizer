"""Database connection factory for the entity registry.

Provides ``get_connection`` (low-level) and ``get_connection_from_config``
(config-driven with graceful degradation). All sqlite3 imports are confined
to this module and ``migrations.py``.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from src.entity.migrations import run_migrations

logger = logging.getLogger(__name__)


def get_connection(db_path: str, auto_create: bool = True) -> sqlite3.Connection:
    """Open an SQLite connection with WAL mode, foreign keys, and auto-migration.

    Args:
        db_path: Path to the SQLite database file.
        auto_create: If ``True``, create the parent directory when missing.
            If ``False`` and the file does not exist, raise ``FileNotFoundError``.

    Returns:
        A configured ``sqlite3.Connection`` ready for use.
    """
    path = Path(db_path)

    if not path.exists() and not auto_create:
        raise FileNotFoundError(f"Database file not found: {db_path}")

    if auto_create:
        path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row

    # Enable WAL mode for concurrent reads
    result = conn.execute("PRAGMA journal_mode=WAL").fetchone()[0]
    if result.lower() != "wal":
        logger.warning("WAL mode not enabled (got %s)", result)

    # Enable foreign key enforcement
    conn.execute("PRAGMA foreign_keys=ON")

    # Set busy timeout for concurrent web access
    conn.execute("PRAGMA busy_timeout=5000")

    # Apply any pending migrations
    run_migrations(conn)

    return conn


def get_connection_from_config(config: object) -> sqlite3.Connection | None:
    """Open a connection using an ``EntityConfig`` instance.

    Returns ``None`` when the entity subsystem is disabled or when any error
    prevents opening the database (graceful degradation — the pipeline
    continues without entity features).

    Args:
        config: An ``EntityConfig`` with ``enabled``, ``db_path``, and
            ``auto_create`` attributes.
    """
    if not getattr(config, "enabled", False):
        return None

    try:
        return get_connection(
            db_path=config.db_path,
            auto_create=getattr(config, "auto_create", True),
        )
    except Exception:
        logger.warning("Entity DB unavailable, continuing without entities", exc_info=True)
        return None
