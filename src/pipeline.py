"""Pipeline runner: orchestrates a single day's ingest-synthesize-output cycle.

Provides PipelineContext (shared state for a pipeline run) and run_pipeline
(the main orchestrator). Each source has its own private ingest function that
catches errors independently so one source failure doesn't block others.

All imports are at module level for fail-fast on missing dependencies.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import anthropic

from src.cache_cleanup import cleanup_raw_cache
from src.config import PipelineConfig, load_config
from src.dedup import dedup_source_items
from src.ingest.calendar import build_calendar_service, cache_raw_response, fetch_events_for_date
from src.ingest.gmail import build_gmail_service, cache_raw_emails
from src.ingest.google_docs import fetch_google_docs_items
from src.ingest.hubspot import fetch_hubspot_items
from src.ingest.notion import fetch_notion_items
from src.ingest.normalizer import build_normalized_output
from src.ingest.slack import build_slack_client, fetch_slack_items, load_slack_state, save_slack_state
from src.ingest.slack_discovery import check_new_channels
from src.ingest.transcripts import fetch_all_transcripts
from src.models.events import DailySynthesis, Section
from src.models.sources import SourceItem, SourceType
from src.notifications.slack import send_slack_summary
from src.output.writer import write_daily_sidecar, write_daily_summary
from src.quality import detect_edits, save_raw_output, update_quality_report
from src.synthesis.commitments import extract_commitments
from src.synthesis.extractor import extract_all_meetings
from src.synthesis.synthesizer import synthesize_daily

logger = logging.getLogger(__name__)


@dataclass
class PipelineContext:
    """Shared state for a single pipeline run."""

    config: PipelineConfig
    target_date: date
    output_dir: Path
    template_dir: Path
    claude_client: anthropic.Anthropic
    google_creds: object | None = None
    calendar_service: object | None = None
    gmail_service: object | None = None
    user_email: str | None = None


@dataclass
class IngestResult:
    """Aggregated ingest data for a single day."""

    events: list = field(default_factory=list)
    source_items: list = field(default_factory=list)
    extractions: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Private ingest functions -- each catches its own errors
# ---------------------------------------------------------------------------


def _ingest_slack(ctx: PipelineContext) -> list[SourceItem]:
    """Fetch Slack items for the target date."""
    if not ctx.config.slack.enabled:
        return []

    try:
        items = fetch_slack_items(ctx.config, target_date=ctx.target_date)
        logger.info("Fetched %d Slack items", len(items))

        # Periodic new-channel auto-suggest
        try:
            state = load_slack_state(Path("config"))
            last_check = state.get("last_discovery_check")
            check_interval = ctx.config.slack.discovery_check_days
            should_check = (
                last_check is None
                or datetime.fromisoformat(last_check)
                < datetime.now() - timedelta(days=check_interval)
            )
            if should_check:
                client = build_slack_client()
                new_channels = check_new_channels(client, state, ctx.config)
                if new_channels:
                    logger.info(
                        "New active Slack channels detected: %s -- run discover-slack to add them.",
                        ", ".join(f"#{name}" for name in new_channels),
                    )
                state["last_discovery_check"] = datetime.now().isoformat()
                save_slack_state(state, Path("config"))
        except Exception as e:
            logger.debug("Periodic channel check skipped: %s", e)

        return items
    except Exception as e:
        logger.warning("Slack ingestion failed: %s. Continuing without Slack data.", e)
        return []


def _ingest_hubspot(ctx: PipelineContext) -> list[SourceItem]:
    """Fetch HubSpot CRM items for the target date."""
    if not ctx.config.hubspot.enabled:
        return []

    try:
        items = fetch_hubspot_items(ctx.config, ctx.target_date)
        logger.info("Fetched %d HubSpot items", len(items))
        return items
    except Exception as e:
        logger.warning("HubSpot ingestion failed: %s. Continuing without HubSpot data.", e)
        return []


def _ingest_docs(ctx: PipelineContext) -> list[SourceItem]:
    """Fetch Google Docs items for the target date."""
    if not ctx.config.google_docs.enabled or ctx.google_creds is None:
        return []

    try:
        items = fetch_google_docs_items(ctx.config, ctx.google_creds, ctx.target_date)
        logger.info("Fetched %d Google Docs items", len(items))
        return items
    except Exception as e:
        logger.warning("Google Docs ingestion failed: %s. Continuing without Docs data.", e)
        return []


def _ingest_notion(ctx: PipelineContext) -> list[SourceItem]:
    """Fetch Notion page and database items for the target date."""
    if not ctx.config.notion.enabled:
        return []

    try:
        items = fetch_notion_items(ctx.config, ctx.target_date)
        logger.info("Fetched %d Notion items", len(items))
        return items
    except Exception as e:
        logger.warning("Notion ingestion failed: %s. Continuing without Notion data.", e)
        return []


def _ingest_calendar(
    ctx: PipelineContext,
) -> tuple[dict | None, list, list, list]:
    """Fetch calendar events and transcripts, run per-meeting extraction.

    Returns:
        (categorized, transcripts, unmatched, extractions)
        categorized is None if calendar_service is unavailable.
    """
    if ctx.calendar_service is None:
        return None, [], [], []

    try:
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

        # Per-meeting extraction
        active_events = categorized["timed_events"] + categorized["all_day_events"]
        extractions: list = []
        try:
            events_with_transcripts = [e for e in active_events if e.transcript_text]
            if events_with_transcripts:
                extractions = extract_all_meetings(
                    events_with_transcripts, ctx.config, client=ctx.claude_client
                )
                logger.info("Extracted %d meetings", len(extractions))
        except Exception as e:
            logger.warning("Extraction failed: %s. Continuing without synthesis.", e)

        return categorized, transcripts, unmatched, extractions

    except Exception as e:
        logger.warning("Calendar ingestion failed: %s", e)
        return None, [], [], []


# ---------------------------------------------------------------------------
# Main pipeline runner
# ---------------------------------------------------------------------------


def run_pipeline(ctx: PipelineContext) -> None:
    """Orchestrate a single day's pipeline: ingest -> synthesize -> output.

    Args:
        ctx: PipelineContext with config, dates, services, and shared client.
    """
    current = ctx.target_date

    # Cache retention: cleanup old raw data
    try:
        deleted, freed = cleanup_raw_cache(
            ctx.output_dir,
            raw_ttl_days=ctx.config.cache.raw_ttl_days,
            dedup_log_ttl_days=ctx.config.cache.dedup_log_ttl_days,
        )
        if deleted:
            logger.info("Cache cleanup: deleted %d files, freed %d bytes", deleted, freed)
    except Exception as e:
        logger.warning("Cache cleanup failed: %s. Continuing.", e)

    # Phase 1: Ingest from all sources
    slack_items = _ingest_slack(ctx)
    hubspot_items = _ingest_hubspot(ctx)
    docs_items = _ingest_docs(ctx)
    notion_items = _ingest_notion(ctx)
    categorized, transcripts, unmatched, extractions = _ingest_calendar(ctx)

    # Cross-source dedup pre-filter
    all_source_items = (slack_items or []) + (hubspot_items or []) + (docs_items or []) + (notion_items or [])
    if len(all_source_items) > 1:
        try:
            deduped_items = dedup_source_items(all_source_items, ctx.config, current)
            items_removed = len(all_source_items) - len(deduped_items)
            if items_removed:
                # Redistribute back to per-source lists for synthesis compatibility
                slack_types = {SourceType.SLACK_MESSAGE, SourceType.SLACK_THREAD}
                hubspot_types = {SourceType.HUBSPOT_DEAL, SourceType.HUBSPOT_CONTACT, SourceType.HUBSPOT_TICKET, SourceType.HUBSPOT_ACTIVITY}
                docs_types = {SourceType.GOOGLE_DOC_EDIT, SourceType.GOOGLE_DOC_COMMENT}
                notion_types = {SourceType.NOTION_PAGE, SourceType.NOTION_DB}
                slack_items = [i for i in deduped_items if i.source_type in slack_types]
                hubspot_items = [i for i in deduped_items if i.source_type in hubspot_types]
                docs_items = [i for i in deduped_items if i.source_type in docs_types]
                notion_items = [i for i in deduped_items if i.source_type in notion_types]
                logger.info("Dedup pre-filter: consolidated %d items", items_removed)
        except Exception as e:
            logger.warning("Dedup pre-filter failed: %s. Continuing with unfiltered items.", e)

    # Phase 2: Synthesis
    synthesis_result: dict = {
        "substance": [],
        "decisions": [],
        "commitments": [],
        "executive_summary": None,
    }

    if categorized is not None:
        # Full pipeline with calendar data
        active_events = categorized["timed_events"] + categorized["all_day_events"]
        meeting_count = len(active_events)
        total_meeting_hours = sum(
            (e.duration_minutes or 0) for e in categorized["timed_events"]
        ) / 60.0
        transcript_count = sum(1 for e in active_events if e.transcript_text is not None)

        try:
            if extractions or slack_items or docs_items or hubspot_items or notion_items:
                synthesis_result = synthesize_daily(
                    extractions, current, ctx.config,
                    slack_items=slack_items, docs_items=docs_items,
                    hubspot_items=hubspot_items, notion_items=notion_items,
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
                    [], current, ctx.config,
                    slack_items=slack_items, docs_items=docs_items,
                    hubspot_items=hubspot_items, notion_items=notion_items,
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
            "Commitment extraction failed: %s. Continuing without structured commitments.", e
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
        synthesis, ctx.output_dir, ctx.template_dir,
        slack_items=slack_items, docs_items=docs_items,
        hubspot_items=hubspot_items, notion_items=notion_items,
    )
    logger.info(
        "Wrote daily summary for %s -> %s (%d meetings, %.1fh)",
        current, path, synthesis.meeting_count, synthesis.total_meeting_hours,
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
            synthesis, extractions, ctx.output_dir,
            extracted_commitments=extracted_commitments,
        )
        logger.info("Wrote JSON sidecar -> %s", sidecar_path)
    except Exception as e:
        logger.warning("Sidecar generation failed: %s. Daily summary still written.", e)

    # Slack notification
    try:
        summary_content = path.read_text(encoding="utf-8")
        send_slack_summary(summary_content, current)
    except Exception as e:
        logger.warning("Slack notification failed: %s", e)
