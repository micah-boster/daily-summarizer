"""Backfill orchestrator for populating the entity registry from historical data.

Scans daily sidecar JSON and markdown files, extracts entities via Claude,
and registers them in the entity registry. Tracks progress per day in
the backfill_progress table to allow incremental re-runs.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

from src.config import PipelineConfig
from src.entity.db import get_connection
from src.entity.discovery import extract_entities
from src.entity.normalizer import normalize_for_matching
from src.entity.repository import EntityRepository

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_text_from_sidecar(sidecar_data: dict) -> str:
    """Concatenate text content from a sidecar JSON structure.

    Pulls text from tasks, decisions, and commitments sections.
    """
    parts: list[str] = []

    for task in sidecar_data.get("tasks", []):
        if isinstance(task, dict) and task.get("description"):
            parts.append(task["description"])

    for decision in sidecar_data.get("decisions", []):
        if isinstance(decision, dict):
            if decision.get("description"):
                parts.append(decision["description"])
            if decision.get("rationale"):
                parts.append(decision["rationale"])

    for commitment in sidecar_data.get("commitments", []):
        if isinstance(commitment, dict):
            if commitment.get("what"):
                parts.append(commitment["what"])

    return "\n".join(parts)


def _read_day_content(target_date: date, output_dir: str | Path) -> str | None:
    """Read content for a given date, preferring sidecar JSON over markdown.

    Args:
        target_date: The date to read content for.
        output_dir: Base output directory (e.g., "output").

    Returns:
        Extracted text content, or None if neither file exists.
    """
    output_path = Path(output_dir)
    date_str = target_date.isoformat()
    year = str(target_date.year)
    month = f"{target_date.month:02d}"

    # Try sidecar JSON first
    json_path = output_path / "daily" / year / month / f"{date_str}.json"
    if json_path.exists():
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            text = _extract_text_from_sidecar(data)
            if text.strip():
                return text
        except (json.JSONDecodeError, OSError) as e:
            logger.debug("Failed to read sidecar %s: %s", json_path, e)

    # Fall back to markdown
    md_path = output_path / "daily" / year / month / f"{date_str}.md"
    if md_path.exists():
        try:
            text = md_path.read_text(encoding="utf-8")
            if text.strip():
                return text
        except OSError as e:
            logger.debug("Failed to read markdown %s: %s", md_path, e)

    return None


def _is_day_processed(conn, date_str: str) -> bool:
    """Check if a date has already been processed in backfill_progress."""
    row = conn.execute(
        "SELECT 1 FROM backfill_progress WHERE source_date = ?",
        (date_str,),
    ).fetchone()
    return row is not None


def _record_day_processed(
    conn, date_str: str, status: str, entities_found: int
) -> None:
    """Insert a record into backfill_progress for a processed date."""
    conn.execute(
        "INSERT OR REPLACE INTO backfill_progress "
        "(id, source_date, status, entities_found) VALUES (?, ?, ?, ?)",
        (uuid4().hex, date_str, status, entities_found),
    )


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


def run_backfill(
    from_date: date,
    to_date: date,
    config: PipelineConfig,
    force: bool = False,
    client=None,
) -> dict:
    """Run entity backfill over a date range.

    Scans daily output files (sidecar JSON or markdown), extracts entities
    via Claude, and registers them in the entity registry. Processes dates
    in weekly batches with checkpointing.

    Args:
        from_date: Start date (inclusive).
        to_date: End date (inclusive).
        config: Pipeline configuration.
        force: If True, re-process already-completed days.
        client: Optional pre-configured Anthropic client.

    Returns:
        Summary dict with days_processed, days_skipped, entities_registered.
    """
    if from_date > to_date:
        return {"days_processed": 0, "days_skipped": 0, "entities_registered": 0}

    output_dir = config.pipeline.output_dir

    # Open database connection for backfill_progress tracking
    conn = get_connection(config.entity.db_path)

    # Generate list of all dates in range
    all_dates: list[date] = []
    current = from_date
    while current <= to_date:
        all_dates.append(current)
        current += timedelta(days=1)

    # Filter out already-processed dates (unless force)
    if force:
        dates_to_process = all_dates
    else:
        dates_to_process = [
            d for d in all_dates if not _is_day_processed(conn, d.isoformat())
        ]

    if not dates_to_process:
        print("Backfill complete: 0 days to process (all already done)")
        conn.close()
        return {"days_processed": 0, "days_skipped": len(all_dates), "entities_registered": 0}

    # Group into weekly batches
    batches: list[list[date]] = []
    for i in range(0, len(dates_to_process), 7):
        batches.append(dates_to_process[i : i + 7])

    total_days = len(dates_to_process)
    total_entities = 0
    days_processed = 0
    days_skipped = len(all_dates) - len(dates_to_process)

    threshold = config.entity.auto_register_threshold
    review_threshold = config.entity.review_threshold

    # Check HubSpot availability once for the entire backfill run
    hubspot_available = bool(getattr(config.hubspot, "access_token", ""))
    if not hubspot_available:
        logger.info("HubSpot cross-reference skipped: no access_token configured")

    with EntityRepository(config.entity.db_path) as repo:
        for batch_idx, batch in enumerate(batches):
            batch_entities = 0
            new_entities_in_batch: list[tuple[str, str, str]] = []  # (entity_id, name, type)

            for day in batch:
                date_str = day.isoformat()
                content = _read_day_content(day, output_dir)

                if content is None:
                    _record_day_processed(conn, date_str, "skipped", 0)
                    days_processed += 1
                    continue

                try:
                    discovered = extract_entities(content, config, client)
                except Exception as e:
                    logger.warning("Entity extraction failed for %s: %s", date_str, e)
                    _record_day_processed(conn, date_str, "failed", 0)
                    days_processed += 1
                    continue

                day_count = 0
                for entity in discovered:
                    if entity.confidence >= threshold:
                        normalized = normalize_for_matching(entity.name)
                        existing = repo.resolve_name(normalized)
                        if existing is None:
                            existing = repo.resolve_name(entity.name)
                        if existing is None:
                            new_entity = repo.add_entity(
                                entity.name.strip(), entity.entity_type
                            )
                            day_count += 1
                            new_entities_in_batch.append(
                                (new_entity.id, entity.name.strip(), entity.entity_type)
                            )
                            # Add normalized form as alias if different
                            raw = entity.name.strip()
                            from src.entity.normalizer import normalize_company_name

                            canonical = normalize_company_name(raw)
                            if canonical != raw:
                                try:
                                    found = repo.get_by_name(raw)
                                    if found:
                                        repo.add_alias(found.id, canonical)
                                except Exception:
                                    pass  # Alias is best-effort
                    elif entity.confidence >= review_threshold:
                        logger.debug(
                            "Low-confidence entity '%s' (%.2f) -- merge proposal deferred to Phase 22",
                            entity.name,
                            entity.confidence,
                        )

                _record_day_processed(conn, date_str, "completed", day_count)
                batch_entities += day_count
                days_processed += 1

                # Progress display
                progress_pct = days_processed / total_days
                bar_filled = int(progress_pct * 20)
                bar = "#" * bar_filled + "-" * (20 - bar_filled)
                sys.stdout.write(
                    f"\rProcessing {from_date} to {to_date}... "
                    f"[{bar}] {days_processed}/{total_days} days, "
                    f"{total_entities + batch_entities} entities found"
                )
                sys.stdout.flush()

            # Cross-reference new entities with HubSpot (batch level)
            if new_entities_in_batch and hubspot_available:
                try:
                    from src.entity.hubspot_xref import cross_reference_entity

                    hubspot_api_failed = False
                    for eid, ename, etype in new_entities_in_batch:
                        if hubspot_api_failed:
                            repo.update_hubspot_id(eid, "", metadata_updates={"pending_enrichment": True})
                            continue
                        try:
                            match = cross_reference_entity(ename, etype, config)
                            if match:
                                repo.update_hubspot_id(eid, match["hubspot_id"], metadata_updates={
                                    "hubspot_type": match.get("hubspot_type"),
                                    "email": match.get("email"),
                                    "deal_stage": match.get("deal_stage"),
                                    "xref_confidence": match.get("confidence"),
                                })
                        except Exception:
                            hubspot_api_failed = True
                            logger.warning("HubSpot API unavailable, flagging remaining entities as pending_enrichment")
                            repo.update_hubspot_id(eid, "", metadata_updates={"pending_enrichment": True})
                except Exception as e:
                    logger.warning("HubSpot cross-reference import failed: %s", e)

            # Commit checkpoint after each batch
            conn.commit()
            total_entities += batch_entities

            print(
                f"\nBatch {batch_idx + 1}/{len(batches)} complete: "
                f"processed {len(batch)} days, found {batch_entities} entities"
            )

    conn.close()

    print(
        f"\nBackfill complete: processed {days_processed}/{len(all_dates)} days, "
        f"{total_entities} entities registered"
    )

    return {
        "days_processed": days_processed,
        "days_skipped": days_skipped,
        "entities_registered": total_entities,
    }
