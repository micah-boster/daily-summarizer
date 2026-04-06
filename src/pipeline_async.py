"""Async pipeline orchestrator: runs all ingest sources concurrently.

Wraps sync ingest functions via asyncio.to_thread for concurrent execution,
and uses async extraction for the calendar chain. The public entry point
async_pipeline() is called from run_pipeline() via asyncio.run().
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

import anthropic

from src.config import PipelineConfig
from src.dedup import dedup_source_items
from src.models.events import DailySynthesis, Section
from src.models.sources import SourceType
from src.notifications.slack import send_slack_summary
from src.output.writer import write_daily_sidecar, write_daily_summary
from src.pipeline import (
    PipelineContext,
    _ingest_docs,
    _ingest_hubspot,
    _ingest_notion,
    _ingest_slack,
)
from src.quality import detect_edits, save_raw_output, update_quality_report
from src.synthesis.commitments import extract_commitments
from src.synthesis.extractor import extract_all_meetings, extract_all_meetings_async
from src.synthesis.synthesizer import synthesize_daily

# Calendar-specific imports for the async calendar chain
from src.ingest.calendar import build_calendar_service, cache_raw_response, fetch_events_for_date
from src.ingest.gmail import build_gmail_service, cache_raw_emails
from src.ingest.normalizer import build_normalized_output
from src.ingest.transcripts import fetch_all_transcripts

logger = logging.getLogger(__name__)


def _discover_and_register_entities(
    synthesis_result: dict,
    target_date,
    config: PipelineConfig,
) -> None:
    """Post-synthesis entity discovery. Fire-and-forget with graceful degradation."""
    if not config.entity.enabled:
        return

    try:
        from src.entity.db import get_connection_from_config
        from src.entity.normalizer import normalize_company_name, normalize_for_matching
        from src.entity.repository import EntityRepository

        conn = get_connection_from_config(config.entity)
        if conn is None:
            return

        # Collect entity names from synthesis items
        all_entity_names: set[str] = set()
        for section_key in ("substance", "decisions"):
            for item in synthesis_result.get(section_key, []):
                if hasattr(item, "entity_names"):
                    all_entity_names.update(item.entity_names)
                elif isinstance(item, dict) and "entity_names" in item:
                    all_entity_names.update(item["entity_names"])
        for commitment in synthesis_result.get("commitments", []):
            if hasattr(commitment, "entity_names"):
                all_entity_names.update(commitment.entity_names)
            elif isinstance(commitment, dict) and "entity_names" in commitment:
                all_entity_names.update(commitment["entity_names"])

        if not all_entity_names:
            logger.debug("No entity names in synthesis output")
            conn.close()
            return

        repo = EntityRepository(config.entity.db_path)
        with repo:
            registered = 0
            for raw_name in all_entity_names:
                if not raw_name or not raw_name.strip():
                    continue
                normalized = normalize_for_matching(raw_name)
                existing = repo.resolve_name(normalized)
                if existing is None:
                    existing = repo.resolve_name(raw_name)
                if existing is None:
                    # Determine type heuristic: names with 2+ capitalized words
                    # and short parts are likely people
                    parts = raw_name.strip().split()
                    is_person = (
                        len(parts) >= 2
                        and all(p[0].isupper() for p in parts if p)
                        and all(len(p) <= 20 for p in parts)
                        and len(parts) <= 4
                    )
                    entity_type = "person" if is_person else "partner"
                    repo.add_entity(raw_name.strip(), entity_type)
                    registered += 1
                    # Add normalized form as alias if different
                    try:
                        canonical = normalize_company_name(raw_name.strip())
                        if canonical != raw_name.strip():
                            entity = repo.get_by_name(raw_name.strip())
                            if entity:
                                repo.add_alias(entity.id, canonical)
                    except Exception:
                        pass  # Alias is best-effort

            if registered:
                logger.info("Entity discovery: registered %d new entities", registered)
        conn.close()

    except Exception as e:
        logger.warning("Entity discovery failed: %s. Daily summary unaffected.", e)


def _fetch_calendar_and_transcripts(
    ctx: PipelineContext,
) -> tuple[dict | None, list, list, list]:
    """Sync helper: fetch calendar events and transcripts (no extraction).

    Returns:
        (categorized, transcripts, unmatched, active_events_with_transcripts)
    """
    if ctx.calendar_service is None:
        return None, [], [], []

    categorized, raw_events = fetch_events_for_date(
        ctx.calendar_service, ctx.target_date, ctx.config, ctx.user_email
    )
    cache_raw_response(raw_events, ctx.target_date, ctx.output_dir)

    # Fetch and link transcripts
    transcripts: list[dict] = []
    unmatched: list[dict] = []
    try:
        if ctx.gmail_service is not None:
            transcripts = fetch_all_transcripts(
                ctx.gmail_service, ctx.target_date, ctx.config, creds=ctx.google_creds
            )
            if transcripts:
                raw_emails = [t["raw_email"] for t in transcripts]
                cache_raw_emails(raw_emails, "transcripts", ctx.target_date, ctx.output_dir)

            categorized, unmatched = build_normalized_output(
                categorized, transcripts, ctx.config
            )
    except Exception as e:
        logger.warning("Transcript ingestion failed: %s. Continuing with calendar only.", e)

    active_events = categorized["timed_events"] + categorized["all_day_events"]
    events_with_transcripts = [e for e in active_events if e.transcript_text]

    return categorized, transcripts, unmatched, events_with_transcripts


async def _ingest_calendar_async(
    ctx: PipelineContext,
    async_client: anthropic.AsyncAnthropic,
) -> tuple[dict | None, list, list, list]:
    """Async calendar chain: fetch events/transcripts in thread, then async extraction.

    Returns:
        (categorized, transcripts, unmatched, extractions)
    """
    if ctx.calendar_service is None:
        return None, [], [], []

    try:
        categorized, transcripts, unmatched, events_with_transcripts = (
            await asyncio.to_thread(_fetch_calendar_and_transcripts, ctx)
        )

        if categorized is None:
            return None, [], [], []

        # Per-meeting extraction (async)
        extractions: list = []
        try:
            if events_with_transcripts:
                extractions = await extract_all_meetings_async(
                    events_with_transcripts, ctx.config, async_client
                )
                logger.info("Extracted %d meetings (async)", len(extractions))
        except Exception as e:
            logger.warning("Async extraction failed: %s. Continuing without synthesis.", e)

        return categorized, transcripts, unmatched, extractions

    except Exception as e:
        logger.warning("Calendar ingestion failed: %s", e)
        return None, [], [], []


async def async_ingest_all(
    ctx: PipelineContext,
) -> tuple[list, list, list, list, dict | None, list, list, list]:
    """Run all ingest sources concurrently.

    Returns:
        (slack_items, hubspot_items, docs_items, notion_items,
         categorized, transcripts, unmatched, extractions)
    """
    async_client = anthropic.AsyncAnthropic()

    results = await asyncio.gather(
        asyncio.to_thread(_ingest_slack, ctx),
        asyncio.to_thread(_ingest_hubspot, ctx),
        asyncio.to_thread(_ingest_docs, ctx),
        asyncio.to_thread(_ingest_notion, ctx),
        _ingest_calendar_async(ctx, async_client),
        return_exceptions=True,
    )

    # Unpack with error handling
    slack_items: list = []
    hubspot_items: list = []
    docs_items: list = []
    notion_items: list = []
    categorized: dict | None = None
    transcripts: list = []
    unmatched: list = []
    extractions: list = []

    labels = ["Slack", "HubSpot", "Google Docs", "Notion", "Calendar"]

    for i, result in enumerate(results):
        if isinstance(result, BaseException):
            logger.warning("%s ingest failed during parallel execution: %s", labels[i], result)
            continue

        if i == 0:
            slack_items = result
        elif i == 1:
            hubspot_items = result
        elif i == 2:
            docs_items = result
        elif i == 3:
            notion_items = result
        elif i == 4:
            categorized, transcripts, unmatched, extractions = result

    return (
        slack_items,
        hubspot_items,
        docs_items,
        notion_items,
        categorized,
        transcripts,
        unmatched,
        extractions,
    )


async def async_pipeline(ctx: PipelineContext) -> None:
    """Async entry point: parallel ingest then sequential synthesis and output.

    Called from run_pipeline() via asyncio.run(). Runs all ingest sources
    concurrently, then proceeds with dedup, synthesis, and output writing
    sequentially (those depend on accumulated ingest results).
    """
    current = ctx.target_date
    pipeline_start = time.perf_counter()

    # Phase 1: Parallel ingest
    ingest_start = time.perf_counter()
    (
        slack_items,
        hubspot_items,
        docs_items,
        notion_items,
        categorized,
        transcripts,
        unmatched,
        extractions,
    ) = await async_ingest_all(ctx)
    ingest_elapsed = time.perf_counter() - ingest_start
    logger.info("Parallel ingest completed in %.1fs", ingest_elapsed)

    # Cross-source dedup pre-filter
    all_source_items = (
        (slack_items or [])
        + (hubspot_items or [])
        + (docs_items or [])
        + (notion_items or [])
    )
    if len(all_source_items) > 1:
        try:
            deduped_items = dedup_source_items(all_source_items, ctx.config, current)
            items_removed = len(all_source_items) - len(deduped_items)
            if items_removed:
                slack_types = {SourceType.SLACK_MESSAGE, SourceType.SLACK_THREAD}
                hubspot_types = {
                    SourceType.HUBSPOT_DEAL,
                    SourceType.HUBSPOT_CONTACT,
                    SourceType.HUBSPOT_TICKET,
                    SourceType.HUBSPOT_ACTIVITY,
                }
                docs_types = {SourceType.GOOGLE_DOC_EDIT, SourceType.GOOGLE_DOC_COMMENT}
                notion_types = {SourceType.NOTION_PAGE, SourceType.NOTION_DB}
                slack_items = [i for i in deduped_items if i.source_type in slack_types]
                hubspot_items = [i for i in deduped_items if i.source_type in hubspot_types]
                docs_items = [i for i in deduped_items if i.source_type in docs_types]
                notion_items = [i for i in deduped_items if i.source_type in notion_types]
                logger.info("Dedup pre-filter: consolidated %d items", items_removed)
        except Exception as e:
            logger.warning(
                "Dedup pre-filter failed: %s. Continuing with unfiltered items.", e
            )

    # Phase 2: Synthesis
    synthesis_result: dict = {
        "substance": [],
        "decisions": [],
        "commitments": [],
        "executive_summary": None,
    }

    if categorized is not None:
        active_events = categorized["timed_events"] + categorized["all_day_events"]
        meeting_count = len(active_events)
        total_meeting_hours = (
            sum((e.duration_minutes or 0) for e in categorized["timed_events"]) / 60.0
        )
        transcript_count = sum(1 for e in active_events if e.transcript_text is not None)

        try:
            if extractions or slack_items or docs_items or hubspot_items or notion_items:
                synthesis_result = synthesize_daily(
                    extractions,
                    current,
                    ctx.config,
                    slack_items=slack_items,
                    docs_items=docs_items,
                    hubspot_items=hubspot_items,
                    notion_items=notion_items,
                    client=ctx.claude_client,
                )
                logger.info("Daily synthesis complete")
        except Exception as e:
            logger.warning("Synthesis failed: %s. Continuing with empty synthesis.", e)

        meetings_without_transcripts = [
            e for e in active_events if e.transcript_text is None
        ]

        synthesis = DailySynthesis(
            date=current,
            generated_at=datetime.now(timezone.utc),
            meeting_count=meeting_count,
            total_meeting_hours=total_meeting_hours,
            transcript_count=transcript_count,
            all_day_events=categorized["all_day_events"],
            timed_events=categorized["timed_events"],
            declined_events=categorized["declined_events"],
            cancelled_events=categorized["cancelled_events"],
            unmatched_transcripts=unmatched,
            executive_summary=synthesis_result.get("executive_summary"),
            extractions=extractions,
            meetings_without_transcripts=meetings_without_transcripts,
            substance=Section(
                title="Substance",
                items=synthesis_result.get("substance", []),
            ),
            decisions=Section(
                title="Decisions",
                items=synthesis_result.get("decisions", []),
            ),
            commitments=Section(
                title="Commitments",
                items=synthesis_result.get("commitments", []),
            ),
        )
    else:
        # No Google credentials: synthesize Slack/HubSpot/Docs if available
        if slack_items or docs_items or hubspot_items or notion_items:
            try:
                synthesis_result = synthesize_daily(
                    [],
                    current,
                    ctx.config,
                    slack_items=slack_items,
                    docs_items=docs_items,
                    hubspot_items=hubspot_items,
                    notion_items=notion_items,
                    client=ctx.claude_client,
                )
                logger.info("Daily synthesis complete (no-creds path)")
            except Exception as e:
                logger.warning("Synthesis failed (no-creds path): %s", e)

        synthesis = DailySynthesis(
            date=current,
            generated_at=datetime.now(timezone.utc),
            meeting_count=0,
            total_meeting_hours=0.0,
            transcript_count=0,
            executive_summary=synthesis_result.get("executive_summary"),
            substance=Section(
                title="Substance",
                items=synthesis_result.get("substance", []),
            ),
            decisions=Section(
                title="Decisions",
                items=synthesis_result.get("decisions", []),
            ),
            commitments=Section(
                title="Commitments",
                items=synthesis_result.get("commitments", []),
            ),
        )

    # Commitment extraction (second Claude call)
    extracted_commitments: list = []
    try:
        synthesis_text_parts: list[str] = []
        if synthesis_result.get("executive_summary"):
            synthesis_text_parts.append(synthesis_result["executive_summary"])
        for section in ["substance", "decisions", "commitments"]:
            for item in synthesis_result.get(section, []):
                synthesis_text_parts.append(item)
        synthesis_text = "\n".join(synthesis_text_parts)
        if synthesis_text.strip():
            extracted_commitments = extract_commitments(
                synthesis_text, current, ctx.config, client=ctx.claude_client
            )
            logger.info("Extracted %d structured commitments", len(extracted_commitments))
    except Exception as e:
        logger.warning(
            "Commitment extraction failed: %s. Continuing without structured commitments.",
            e,
        )

    # Phase 3: Output
    # Quality tracking: detect edits
    try:
        edit_result = detect_edits(current, ctx.output_dir)
        if edit_result is not None:
            update_quality_report(edit_result, ctx.output_dir)
            if edit_result["edited"]:
                logger.info(
                    "Edit detected for %s: similarity=%.0f%%, sections=%s",
                    current,
                    edit_result["similarity"] * 100,
                    ", ".join(edit_result["sections_changed"]) or "none",
                )
            else:
                logger.info("No edits detected for %s", current)
    except Exception as e:
        logger.warning("Quality tracking (detect) failed: %s", e)

    # Write daily summary
    path = write_daily_summary(
        synthesis,
        ctx.output_dir,
        ctx.template_dir,
        slack_items=slack_items,
        docs_items=docs_items,
        hubspot_items=hubspot_items,
        notion_items=notion_items,
    )
    logger.info(
        "Wrote daily summary for %s -> %s (%d meetings, %.1fh)",
        current,
        path,
        synthesis.meeting_count,
        synthesis.total_meeting_hours,
    )

    # Quality tracking: save raw output
    try:
        raw_content = path.read_text(encoding="utf-8")
        raw_path = save_raw_output(raw_content, current, ctx.output_dir)
        logger.info("Saved raw output -> %s", raw_path)
    except Exception as e:
        logger.warning("Quality tracking (save) failed: %s", e)

    # JSON sidecar
    try:
        sidecar_path = write_daily_sidecar(
            synthesis,
            extractions,
            ctx.output_dir,
            extracted_commitments=extracted_commitments,
        )
        logger.info("Wrote JSON sidecar -> %s", sidecar_path)
    except Exception as e:
        logger.warning("Sidecar generation failed: %s. Daily summary still written.", e)

    # Entity discovery (post-synthesis, optional)
    _discover_and_register_entities(synthesis_result, current, ctx.config)

    # Slack notification
    try:
        summary_content = path.read_text(encoding="utf-8")
        send_slack_summary(summary_content, current)
    except Exception as e:
        logger.warning("Slack notification failed: %s", e)

    pipeline_elapsed = time.perf_counter() - pipeline_start
    logger.info("Total pipeline completed in %.1fs", pipeline_elapsed)
