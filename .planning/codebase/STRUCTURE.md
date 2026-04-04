# Codebase Structure

**Analysis Date:** 2026-04-04

## Directory Layout

```
daily-summarizer/
├── config/                    # YAML configuration files
│   ├── config.yaml            # Main pipeline config (calendars, sources, synthesis)
│   ├── priorities.yaml        # User priority emphasis/suppression config
│   └── slack_state.json       # Slack ingestion cursor state (auto-managed)
├── src/                       # All Python source code
│   ├── __init__.py
│   ├── main.py                # CLI entry point and pipeline orchestration
│   ├── config.py              # Config loading (YAML + env overrides)
│   ├── priorities.py          # Priority config model + prompt builder
│   ├── quality.py             # Diff-based quality metrics tracking
│   ├── sidecar.py             # JSON sidecar generation models + builder
│   ├── auth/                  # Authentication
│   │   ├── __init__.py
│   │   └── google_oauth.py    # Google OAuth2 credential management
│   ├── ingest/                # Data source ingestion modules
│   │   ├── __init__.py
│   │   ├── calendar.py        # Google Calendar API ingestion
│   │   ├── gmail.py           # Gmail API search/fetch helpers
│   │   ├── drive.py           # Google Drive/Docs API for Gemini transcripts
│   │   ├── transcripts.py     # Transcript parsing (Gemini + Gong) with dedup
│   │   ├── normalizer.py      # Transcript-event matching and deduplication
│   │   ├── slack.py           # Slack Bot API ingestion (channels + DMs)
│   │   ├── slack_filter.py    # Slack message noise filtering
│   │   ├── slack_discovery.py # Auto-discovery of new Slack channels
│   │   ├── hubspot.py         # HubSpot CRM API ingestion
│   │   └── google_docs.py     # Google Docs edits + comments ingestion
│   ├── models/                # Pydantic data models
│   │   ├── __init__.py
│   │   ├── events.py          # NormalizedEvent, DailySynthesis, Section
│   │   ├── sources.py         # SourceItem, SourceType, SynthesisSource protocol
│   │   ├── commitments.py     # Commitment model
│   │   └── rollups.py         # Weekly/Monthly synthesis models
│   ├── synthesis/             # LLM-powered extraction and synthesis
│   │   ├── __init__.py
│   │   ├── extractor.py       # Stage 1: per-meeting extraction
│   │   ├── synthesizer.py     # Stage 2: cross-source daily synthesis
│   │   ├── commitments.py     # Stage 3: structured commitment extraction
│   │   ├── weekly.py          # Weekly thread detection
│   │   ├── monthly.py         # Monthly narrative synthesis
│   │   ├── prompts.py         # All LLM prompt templates
│   │   ├── models.py          # ExtractionItem, MeetingExtraction
│   │   └── validator.py       # Evidence-only language enforcement
│   ├── output/                # File output rendering
│   │   ├── __init__.py
│   │   └── writer.py          # Jinja2 template rendering + file writing
│   ├── notifications/         # External notifications
│   │   ├── __init__.py
│   │   └── slack.py           # Slack webhook posting (Block Kit digest)
│   └── validation/            # Health checks
│       ├── __init__.py
│       ├── daily_check.py     # Daily credential/API validation script
│       └── run_log.py         # JSONL run log helpers
├── templates/                 # Jinja2 Markdown templates
│   ├── daily.md.j2            # Daily summary template
│   ├── weekly.md.j2           # Weekly roll-up template
│   └── monthly.md.j2          # Monthly narrative template
├── tests/                     # Pytest test files (flat directory)
│   ├── __init__.py
│   ├── test_calendar_ingest.py
│   ├── test_drive_ingest.py
│   ├── test_extractor.py
│   ├── test_gmail_ingest.py
│   ├── test_gong_ingest.py
│   ├── test_google_docs.py
│   ├── test_hubspot_ingest.py
│   ├── test_models.py
│   ├── test_monthly.py
│   ├── test_normalizer.py
│   ├── test_notifications.py
│   ├── test_priorities.py
│   ├── test_quality.py
│   ├── test_sidecar.py
│   ├── test_slack_discovery.py
│   ├── test_slack_ingest.py
│   ├── test_source_models.py
│   ├── test_synthesizer.py
│   ├── test_validator.py
│   ├── test_weekly.py
│   └── test_writer.py
├── output/                    # Generated output (gitignored except structure)
│   ├── daily/YYYY/MM/         # Daily summaries: YYYY-MM-DD.md + .json
│   ├── weekly/YYYY/           # Weekly summaries: YYYY-WXX.md
│   ├── monthly/YYYY/          # Monthly summaries: YYYY-MM.md
│   ├── raw/YYYY/MM/DD/        # Raw API response cache (calendar.json, etc.)
│   ├── raw/daily/YYYY/MM/     # Raw pipeline output for quality diffing
│   ├── quality/               # Quality metrics (metrics.jsonl, quality-report.md)
│   └── validation/            # Daily validation check results
├── docs/                      # Design documents and decision records
├── .planning/                 # GSD planning artifacts
├── .credentials/              # Google OAuth credentials (gitignored)
├── .env                       # Environment variables (gitignored)
├── .env.example               # Template for required env vars
├── pyproject.toml             # Project metadata and dependencies (uv)
├── uv.lock                    # Dependency lockfile
└── .python-version            # Python 3.12+
```

## Directory Purposes

**`config/`:**
- Purpose: Runtime configuration files
- Contains: `config.yaml` (main pipeline config), `priorities.yaml` (synthesis emphasis), `slack_state.json` (auto-managed cursor state)
- Key files: `config/config.yaml` is the primary config; `config/priorities.yaml` is optional

**`src/ingest/`:**
- Purpose: All external data source fetching and normalization
- Contains: One module per data source, plus normalizer for cross-source linking
- Key files: `calendar.py` (core source), `transcripts.py` (Gemini/Gong parsing), `slack.py` (Slack ingestion), `normalizer.py` (transcript-event matching)
- Pattern: Each module exports a `fetch_*_items()` or `fetch_*()` top-level function that takes `config` dict and returns Pydantic model lists

**`src/models/`:**
- Purpose: All Pydantic data models shared across the pipeline
- Contains: Event models, source item models, commitment models, roll-up models
- Key files: `events.py` (NormalizedEvent + DailySynthesis), `sources.py` (SourceItem + Protocol)

**`src/synthesis/`:**
- Purpose: All Claude API interactions and LLM prompt management
- Contains: Extraction, synthesis, commitment extraction, weekly/monthly pipelines, prompts, validation
- Key files: `extractor.py` (Stage 1), `synthesizer.py` (Stage 2), `prompts.py` (all prompts), `validator.py` (output quality)

**`src/output/`:**
- Purpose: Jinja2 template rendering and file I/O
- Contains: Single `writer.py` with functions for daily/weekly/monthly output
- Key files: `writer.py`

**`templates/`:**
- Purpose: Jinja2 Markdown templates for all output formats
- Contains: `daily.md.j2`, `weekly.md.j2`, `monthly.md.j2`
- Generated: No (hand-authored)
- Committed: Yes

**`output/`:**
- Purpose: All pipeline output (generated, mostly gitignored)
- Contains: Daily/weekly/monthly summaries, raw API caches, quality metrics
- Generated: Yes
- Committed: No (except possibly quality reports)

## Key File Locations

**Entry Points:**
- `src/main.py`: CLI entry point (`python -m src.main`)
- `src/auth/google_oauth.py`: OAuth setup script (`python -m src.auth.google_oauth`)
- `src/validation/daily_check.py`: Health check script (`python -m src.validation.daily_check`)

**Configuration:**
- `config/config.yaml`: Main pipeline config (calendars, sources, synthesis model, output dir)
- `config/priorities.yaml`: User priority emphasis/suppression
- `.env`: Environment variables (API keys, tokens)
- `pyproject.toml`: Project dependencies and metadata

**Core Logic:**
- `src/ingest/calendar.py`: Calendar event ingestion and categorization
- `src/ingest/normalizer.py`: Transcript-to-event matching
- `src/synthesis/extractor.py`: Per-meeting Claude extraction (Stage 1)
- `src/synthesis/synthesizer.py`: Cross-source Claude synthesis (Stage 2)
- `src/synthesis/prompts.py`: All LLM prompt templates

**Models:**
- `src/models/events.py`: `NormalizedEvent`, `DailySynthesis`
- `src/models/sources.py`: `SourceItem`, `SynthesisSource` protocol
- `src/synthesis/models.py`: `MeetingExtraction`, `ExtractionItem`
- `src/sidecar.py`: `DailySidecar`, `SidecarTask`, `SidecarDecision`, `SidecarCommitment`

**Testing:**
- `tests/test_*.py`: All test files in flat directory, one per source module

## Naming Conventions

**Files:**
- Snake_case for all Python files: `calendar.py`, `google_docs.py`, `daily_check.py`
- Jinja2 templates: `{scope}.md.j2` (e.g., `daily.md.j2`)
- Output files: `YYYY-MM-DD.md`, `YYYY-WXX.md`, `YYYY-MM.md`

**Directories:**
- Lowercase, no underscores for packages: `ingest/`, `models/`, `synthesis/`, `output/`
- Output hierarchy mirrors temporal scope: `daily/YYYY/MM/`, `weekly/YYYY/`, `monthly/YYYY/`

**Test Files:**
- `test_{module_name}.py` (e.g., `test_calendar_ingest.py` for `ingest/calendar.py`)
- Some test files use different naming than source: `test_gong_ingest.py` tests `transcripts.py`

## Where to Add New Code

**New Data Source (e.g., Linear, Jira):**
1. Create `src/ingest/{source}.py` with a `fetch_{source}_items(config, target_date) -> list[SourceItem]` function
2. Add `SourceType.{SOURCE}_*` variants to `src/models/sources.py`
3. Add enable/config section in `config/config.yaml` under the source name
4. Wire into `src/main.py:run_daily()` following the pattern of Slack/HubSpot/Docs blocks (guarded by `config.get("{source}", {}).get("enabled", False)`)
5. Add `_format_{source}_items_for_prompt()` in `src/synthesis/synthesizer.py`
6. Add tests: `tests/test_{source}_ingest.py`

**New Synthesis Stage:**
1. Add module in `src/synthesis/` (e.g., `action_items.py`)
2. Add prompt template in `src/synthesis/prompts.py`
3. Add Pydantic output models (either in `src/synthesis/models.py` or the new module)
4. Wire into `src/main.py:run_daily()` after existing synthesis stages

**New Output Format:**
1. Add Jinja2 template in `templates/`
2. Add `write_{format}_summary()` function in `src/output/writer.py`
3. Add any new Pydantic models needed for the template context

**New CLI Command:**
1. Add subparser in `src/main.py:parse_args()`
2. Add `run_{command}()` function in `src/main.py`
3. Wire into `main()` dispatch

**Utility / Helper:**
- Shared helpers: add to the relevant module (no separate `utils/` directory exists)
- Pydantic models: add to `src/models/` for pipeline-wide models, or `src/synthesis/models.py` for synthesis-specific models, or `src/sidecar.py` for sidecar-specific models

## Special Directories

**`.credentials/`:**
- Purpose: Google OAuth2 token storage
- Generated: Yes (by `src/auth/google_oauth.py`)
- Committed: No (gitignored)

**`output/`:**
- Purpose: All pipeline-generated content
- Generated: Yes
- Committed: No (gitignored, except the directory structure)

**`config/`:**
- Purpose: User-managed configuration
- Generated: `slack_state.json` is auto-managed; `config.yaml` and `priorities.yaml` are hand-edited
- Committed: Partially (config.yaml template yes, state files no)

**`.planning/`:**
- Purpose: GSD planning artifacts (phases, research, codebase analysis)
- Generated: By planning process
- Committed: Yes

---

*Structure analysis: 2026-04-04*
