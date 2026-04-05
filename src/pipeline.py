"""Pipeline runner: orchestrates a single day's ingest-synthesize-output cycle.

Provides PipelineContext (shared state for a pipeline run) and run_pipeline
(the main orchestrator). Each source has its own private ingest function that
catches errors independently so one source failure doesn't block others.

All imports are at module level for fail-fast on missing dependencies.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import anthropic

from src.cache_cleanup import cleanup_raw_cache
from src.config import PipelineConfig, load_config
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

    Delegates to the async pipeline orchestrator which runs all ingest sources
    concurrently. Cache cleanup runs synchronously first (quick operation).

    Args:
        ctx: PipelineContext with config, dates, services, and shared client.
    """
    # Cache retention: cleanup old raw data (quick sync operation)
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

    # Run the async pipeline (parallel ingest -> sequential synthesis -> output)
    from src.pipeline_async import async_pipeline

    asyncio.run(async_pipeline(ctx))
