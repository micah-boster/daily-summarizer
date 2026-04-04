# Architecture

**Analysis Date:** 2026-04-04

## Pattern Overview

**Overall:** Pipeline-based ETL architecture with a two-stage LLM synthesis core

**Key Characteristics:**
- Multi-source ingestion (Google Calendar, Gmail/Drive transcripts, Slack, HubSpot, Google Docs) each producing normalized data models
- Two-stage Claude API synthesis: per-meeting extraction (Stage 1) then cross-source daily synthesis (Stage 2)
- Temporal roll-up hierarchy: daily -> weekly -> monthly, each reading the prior tier's output files
- Jinja2-templated Markdown output with JSON sidecar for structured data
- Config-driven: YAML config + env vars control all source toggles, API keys, and synthesis parameters

## Layers

**CLI / Entry Point:**
- Purpose: Parse arguments, dispatch to daily/weekly/monthly/discover-slack commands
- Location: `src/main.py`
- Contains: `parse_args()`, `run_daily()`, `run_weekly()`, `run_monthly()`, `run_discover_slack()`, `main()`
- Depends on: All other layers (orchestrates the full pipeline)
- Used by: Direct invocation via `python -m src.main`

**Authentication:**
- Purpose: Google OAuth2 credential management (load, refresh, save)
- Location: `src/auth/google_oauth.py`
- Contains: `load_credentials()`, `save_credentials()`, OAuth flow
- Depends on: `google-auth-oauthlib`, `.credentials/` directory
- Used by: `src/main.py` (loads creds once, passes to ingest modules)

**Configuration:**
- Purpose: Load YAML config with environment variable overrides
- Location: `src/config.py`
- Contains: `load_config()` - returns plain `dict`
- Depends on: `pyyaml`, `config/config.yaml`
- Used by: Every pipeline stage (config dict threaded through function args)

**Ingestion Layer:**
- Purpose: Fetch raw data from external APIs, normalize to Pydantic models
- Location: `src/ingest/`
- Contains:
  - `calendar.py`: Google Calendar API -> `NormalizedEvent` list
  - `gmail.py`: Gmail API search/fetch helpers
  - `drive.py`: Google Drive + Docs API for "Notes by Gemini" transcript docs
  - `transcripts.py`: Gemini + Gong email transcript parsing, filler stripping, dedup
  - `slack.py`: Slack Bot API -> `SourceItem` list (channels + DMs + thread expansion)
  - `slack_filter.py`: Noise filtering rules for Slack messages
  - `slack_discovery.py`: Auto-discovery of new Slack channels
  - `hubspot.py`: HubSpot CRM API -> `SourceItem` list (deals, contacts, tickets, engagements)
  - `google_docs.py`: Google Drive + Docs API -> `SourceItem` list (doc edits + comments)
  - `normalizer.py`: Transcript-to-event matching, deduplication, richness scoring
- Depends on: `src/models/`, external API SDKs
- Used by: `src/main.py` (daily pipeline)

**Model Layer:**
- Purpose: Pydantic data models for the entire pipeline
- Location: `src/models/`
- Contains:
  - `events.py`: `NormalizedEvent`, `Attendee`, `ResponseStatus`, `Section`, `DailySynthesis`
  - `sources.py`: `SourceItem`, `SourceType`, `ContentType`, `SynthesisSource` (Protocol)
  - `commitments.py`: `Commitment`, `CommitmentStatus`
  - `rollups.py`: `WeeklyThread`, `ThreadEntry`, `WeeklySynthesis`, `ThematicArc`, `MonthlyMetrics`, `MonthlySynthesis`
- Depends on: Pydantic
- Used by: All layers

**Synthesis Layer:**
- Purpose: LLM-powered extraction and synthesis via Claude API
- Location: `src/synthesis/`
- Contains:
  - `extractor.py`: Stage 1 - per-meeting transcript -> `MeetingExtraction` (one Claude call per meeting)
  - `synthesizer.py`: Stage 2 - all extractions + Slack + Docs + HubSpot -> daily summary (one Claude call)
  - `commitments.py`: Stage 3 - structured commitment extraction via Claude structured outputs (one Claude call)
  - `weekly.py`: Weekly thread detection from daily .md files (one Claude call)
  - `monthly.py`: Monthly narrative from weekly .md files (one Claude call)
  - `prompts.py`: All LLM prompt templates
  - `models.py`: `ExtractionItem`, `MeetingExtraction` (Stage 1 output models)
  - `validator.py`: Evidence-only language enforcement (regex-based banned pattern scanning)
- Depends on: `anthropic` SDK, `src/models/`, `src/synthesis/prompts.py`
- Used by: `src/main.py`

**Output Layer:**
- Purpose: Render Pydantic models to Markdown and JSON via Jinja2 templates
- Location: `src/output/writer.py`
- Contains: `write_daily_summary()`, `write_daily_sidecar()`, `write_weekly_summary()`, `write_monthly_summary()`, `insert_weekly_backlinks()`
- Depends on: Jinja2, `templates/` directory
- Used by: `src/main.py`

**Sidecar Layer:**
- Purpose: Build structured JSON alongside daily Markdown for programmatic access
- Location: `src/sidecar.py`
- Contains: `DailySidecar`, `SidecarTask`, `SidecarDecision`, `SidecarMeeting`, `SidecarCommitment`, `build_daily_sidecar()`
- Depends on: `src/models/`, `src/synthesis/models.py`
- Used by: `src/output/writer.py`

**Quality Tracking:**
- Purpose: Detect user edits to pipeline output, track correction patterns
- Location: `src/quality.py`
- Contains: `save_raw_output()`, `detect_edits()`, `update_quality_report()`
- Depends on: `difflib` (stdlib)
- Used by: `src/main.py` (daily pipeline post-write)

**Priorities:**
- Purpose: User-defined priority emphasis/suppression in synthesis prompts
- Location: `src/priorities.py`
- Contains: `PriorityConfig`, `load_priorities()`, `build_priority_context()`
- Depends on: `config/priorities.yaml`, `src/synthesis/models.py`
- Used by: `src/synthesis/synthesizer.py` (injected into synthesis prompt)

**Notifications:**
- Purpose: Post daily summaries to Slack via incoming webhook
- Location: `src/notifications/slack.py`
- Contains: `notify_slack()`, `send_slack_summary()`, `_build_blocks()` (Slack Block Kit formatting)
- Depends on: `httpx`, `SLACK_WEBHOOK_URL` env var
- Used by: `src/main.py`, `src/validation/daily_check.py`

**Validation:**
- Purpose: Daily health check (credential validity, Calendar API access)
- Location: `src/validation/`
- Contains: `daily_check.py` (standalone script with retry logic), `run_log.py` (JSONL logging)
- Depends on: `src/auth/`, `src/notifications/`
- Used by: External scheduler (Cowork)

## Data Flow

**Daily Pipeline (run_daily):**

1. Load config from `config/config.yaml` with env var overrides
2. Load Google OAuth credentials from `.credentials/`; refresh if expired
3. **Ingest Phase** (per date in range):
   - Fetch Google Calendar events -> categorize into timed/all-day/declined/cancelled
   - Fetch transcripts from Drive (Gemini docs), Gmail (Gemini emails), Gmail (Gong emails)
   - Run normalizer: match transcripts to calendar events by time proximity + title similarity; deduplicate
   - Fetch Slack messages/threads (if enabled) -> `SourceItem` list
   - Fetch Google Docs edits/comments (if enabled) -> `SourceItem` list
   - Fetch HubSpot deals/contacts/tickets/engagements (if enabled) -> `SourceItem` list
4. **Stage 1 Extraction**: For each meeting with transcript, call Claude to extract decisions/commitments/substance/questions/tensions -> `MeetingExtraction` list
5. **Stage 2 Synthesis**: Single Claude call combining all extractions + Slack + Docs + HubSpot -> daily summary sections (executive summary, substance, decisions, commitments)
6. **Stage 3 Commitment Extraction**: Claude structured outputs call to extract typed commitments from synthesis text
7. **Quality Tracking**: Detect edits on previous day's output; save raw output for future comparison
8. **Output**: Render DailySynthesis to Markdown via Jinja2 template; write JSON sidecar
9. **Notification**: Post condensed digest to Slack webhook

**Weekly Pipeline (run_weekly):**

1. Read daily `.md` files for Mon-Fri of target week
2. Extract synthesis sections (substance, decisions, commitments) from each daily file
3. Single Claude call for thread detection across days
4. Parse response into `WeeklyThread` and `ThreadEntry` models
5. Render to Markdown via `weekly.md.j2`; insert backlinks into daily files

**Monthly Pipeline (run_monthly):**

1. Read weekly `.md` files for all weeks in target month
2. Aggregate metrics from daily files (meeting counts, hours, top attendees)
3. Single Claude call for thematic narrative synthesis
4. Parse response into `ThematicArc` models
5. Render to Markdown via `monthly.md.j2`

**State Management:**
- No database. All state is files on disk.
- Daily summaries: `output/daily/YYYY/MM/YYYY-MM-DD.md` + `.json`
- Weekly summaries: `output/weekly/YYYY/YYYY-WXX.md`
- Monthly summaries: `output/monthly/YYYY/YYYY-MM.md`
- Raw API responses cached: `output/raw/YYYY/MM/DD/calendar.json`
- Quality tracking: `output/quality/metrics.jsonl`, `output/raw/daily/YYYY/MM/YYYY-MM-DD.raw.md`
- Slack ingestion state: `config/slack_state.json` (last-read timestamps per channel)

## Key Abstractions

**NormalizedEvent (calendar events):**
- Purpose: Unified calendar event model with optional transcript attachment
- Defined in: `src/models/events.py`
- Pattern: Pydantic BaseModel with properties implementing `SynthesisSource` protocol informally
- Key fields: `id`, `title`, `start_time`, `end_time`, `attendees`, `transcript_text`, `transcript_source`

**SourceItem (non-calendar sources):**
- Purpose: Unified model for Slack messages, HubSpot items, Google Docs activity
- Defined in: `src/models/sources.py`
- Pattern: Pydantic BaseModel implementing `SynthesisSource` protocol via properties
- Key fields: `id`, `source_type` (StrEnum), `content_type`, `title`, `content`, `display_context`

**SynthesisSource (protocol):**
- Purpose: Structural typing interface for anything that can be synthesized
- Defined in: `src/models/sources.py`
- Pattern: `typing.Protocol` with `runtime_checkable`
- Properties: `source_id`, `source_type`, `title`, `timestamp`, `participants_list`, `content_for_synthesis`, `attribution_text()`
- Note: `NormalizedEvent` has matching properties but does NOT formally inherit from `SourceItem`. The protocol is defined but not consistently enforced.

**MeetingExtraction (Stage 1 output):**
- Purpose: Structured extraction from a single meeting transcript
- Defined in: `src/synthesis/models.py`
- Pattern: Pydantic BaseModel with `ExtractionItem` list fields
- Key fields: `decisions`, `commitments`, `substance`, `open_questions`, `tensions`, `low_signal`

**DailySynthesis (pipeline output):**
- Purpose: Complete daily output model fed to Jinja2 templates
- Defined in: `src/models/events.py`
- Contains: all categorized events, synthesis sections, extractions, stats

## Entry Points

**Main CLI:**
- Location: `src/main.py` -> `main()`
- Triggers: `python -m src.main daily|weekly|monthly|discover-slack`
- Invoked via: `uv run python -m src.main daily --from 2026-04-03`
- Responsibilities: Full pipeline orchestration

**Daily Validation Script:**
- Location: `src/validation/daily_check.py` -> `main()`
- Triggers: External scheduler (Cowork)
- Responsibilities: Credential health check, Calendar API smoke test, Slack notification on failure

**Google OAuth Flow:**
- Location: `src/auth/google_oauth.py` (runnable as `python -m src.auth.google_oauth`)
- Triggers: Manual one-time setup
- Responsibilities: Interactive OAuth consent flow, credential persistence

## Error Handling

**Strategy:** Graceful degradation with per-source isolation

**Patterns:**
- Each data source is wrapped in its own try/except in `run_daily()`. A Slack failure does not prevent calendar ingestion.
- Failed individual meeting extractions are logged and skipped (`extract_all_meetings` catches per-event errors)
- Claude API failures at synthesis stage produce empty results; the pipeline still writes a summary (just with less content)
- Commitment extraction failure is non-blocking: pipeline continues without structured commitments
- Quality tracking failures are non-blocking
- Slack notification failures are non-blocking
- Validation script has explicit retry logic (15-minute delay, 2 attempts max)
- All error handling uses `logging.warning()` for non-fatal and `logging.error()` for date-level failures

**Anti-pattern:** The `run_daily()` function catches `Exception` broadly in ~15 separate try/except blocks. Errors are logged but there is no structured error aggregation or summary of what succeeded vs. failed for a given date.

## Cross-Cutting Concerns

**Logging:** Standard library `logging` module. Configured at module level in `src/main.py` with `basicConfig(level=INFO)`. Each module gets its own logger via `logging.getLogger(__name__)`.

**Validation:** Two kinds:
1. **Evidence-only validator** (`src/synthesis/validator.py`): Regex-based scanning for evaluative language in Claude's output. Applied after every Claude synthesis call (daily, weekly, monthly). Violations are logged as warnings but do not block output.
2. **Source attribution validator** (`validate_source_attribution` in same file): Checks bullet items for parenthetical citations. Defined but not called in the main pipeline.

**Authentication:** Google OAuth2 handled centrally in `src/auth/google_oauth.py`. Credentials loaded once in `run_daily()`, then passed through to ingestion functions. Slack and HubSpot use env-var bearer tokens constructed per-call.

**Configuration:** Single `dict` loaded from YAML, threaded through all functions as `config: dict`. No typed config model -- all access is via `config.get("section", {}).get("key", default)`. This is fragile but consistent across the codebase.

**Deduplication:** Applied at two levels:
1. Transcript deduplication in `src/ingest/transcripts.py` (by normalized title, source priority)
2. Calendar event deduplication in `src/ingest/normalizer.py` (by title + start time, richness scoring)
3. HubSpot cross-source dedup in `src/synthesis/synthesizer.py` (calendar time bucket matching)

---

*Architecture analysis: 2026-04-04*
