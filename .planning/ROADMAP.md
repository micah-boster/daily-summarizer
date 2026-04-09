# Roadmap: Work Intelligence Daily Summarizer

## Milestones

- ✅ **v1.0 Daily Intelligence Pipeline** - Phases 0-5 (shipped 2026-04-03)
- ✅ **v1.5 Expanded Ingest** - Phases 6-12 (shipped 2026-04-05)
- ✅ **v1.5.1 Notion + Performance + Reliability** - Phases 13-18.1 (shipped 2026-04-05)
- ✅ **v2.0 Entity Layer** - Phases 19-23.1 (shipped 2026-04-08)
- [ ] **v3.0 Web Interface** - Phases 24-29

## Phases

<details>
<summary>v1.0 Daily Intelligence Pipeline (Phases 0-5) - SHIPPED 2026-04-03</summary>

- [x] **Phase 0: Execution Model Validation** - Prove Cowork scheduling, Google OAuth, and Claude Code session reliability before building anything
- [x] **Phase 1: Foundation and Calendar Ingestion** - Data models, markdown output writer, Google Calendar ingestion, and project scaffolding
- [x] **Phase 2: Transcript Ingestion and Normalization** - Gemini and Gong transcript parsing, calendar-transcript linking, noise filtering, deduplication
- [x] **Phase 3: Two-Stage Synthesis Pipeline** - Per-meeting extraction and daily cross-meeting synthesis answering the three core questions with source attribution
- [x] **Phase 4: Temporal Roll-Ups** - Weekly summaries from accumulated dailies and monthly narrative with themes and progression arcs
- [x] **Phase 5: Feedback and Refinement** - Priority configuration, quality tracking, structured data sidecar, and prompt tuning informed by accumulated output

### Phase 0: Execution Model Validation
**Goal**: Confirm that the daily automation foundation works before building on it
**Depends on**: Nothing (first phase)
**Requirements**: INGEST-01
**Success Criteria** (what must be TRUE):
  1. A Cowork scheduled task fires reliably at a configured time for 5 consecutive weekdays
  2. Google OAuth token authenticates against both Calendar and Gmail APIs and auto-refreshes without manual intervention
  3. A documented re-auth procedure exists for when tokens inevitably expire
  4. Claude Code session within Cowork can execute a Python script that reads/writes files and returns structured output
**Plans**: 2 plans

Plans:
- [x] 00-01-PLAN.md -- Project scaffolding, OAuth module, Slack notifications, validation script with retry logic
- [x] 00-02-PLAN.md -- Operational docs (re-auth procedure, Cowork setup guide) and 5-day scheduled validation

### Phase 1: Foundation and Calendar Ingestion
**Goal**: Establish the data models, output format, and first data source so the pipeline skeleton is testable end-to-end with real calendar data
**Depends on**: Phase 0
**Requirements**: INGEST-02, OUT-01
**Success Criteria** (what must be TRUE):
  1. Running the pipeline for a given date produces a markdown file at `output/daily/YYYY/MM/YYYY-MM-DD.md` with consistent structure and sections
  2. The daily output includes all Google Calendar events for the target date with title, time, attendees, and duration
  3. The output file is scannable in under 2 minutes (calendar-only days have less content)
  4. The Pydantic data models (NormalizedEvent, DailySynthesis) validate and serialize correctly
**Plans**: 2 plans

Plans:
- [x] 01-01-PLAN.md -- Pydantic data models, Jinja2 output writer, YAML config, CLI entry point
- [x] 01-02-PLAN.md -- Google Calendar ingestion module with event normalization and end-to-end pipeline wiring

### Phase 2: Transcript Ingestion and Normalization
**Goal**: Ingest meeting transcripts from both sources and link them to calendar events so synthesis has complete, deduplicated, noise-filtered input data
**Depends on**: Phase 1
**Requirements**: INGEST-03, INGEST-04
**Success Criteria** (what must be TRUE):
  1. Gemini transcripts from Gmail are extracted, parsed, and linked to their corresponding calendar events
  2. Gong transcripts from email delivery are extracted, parsed, and linked to their corresponding calendar events
  3. Unmatched transcripts (no calendar event) and unmatched calendar events (no transcript) are surfaced explicitly in the normalized output rather than silently dropped
  4. Duplicate events from overlapping sources are merged into single normalized records
  5. Raw ingestion data is cached to `output/raw/` for debugging and reprocessing
**Plans**: 3 plans

Plans:
- [x] 02-01-PLAN.md -- Gmail API utilities, Gemini transcript parser, filler stripping
- [x] 02-02-PLAN.md -- Gong transcript parser, combined fetch function
- [x] 02-03-PLAN.md -- Normalization pipeline with calendar-transcript linking, deduplication, pipeline wiring

### Phase 3: Two-Stage Synthesis Pipeline
**Goal**: Deliver the core daily intelligence brief that answers the three synthesis questions with source-attributed evidence and no evaluative language
**Depends on**: Phase 2
**Requirements**: SYNTH-01, SYNTH-02, SYNTH-03, SYNTH-04, OUT-02
**Success Criteria** (what must be TRUE):
  1. Each meeting with a transcript produces a per-meeting extraction (decisions, commitments, substance) before daily synthesis runs
  2. The daily summary answers "What happened of substance today?" with specific, sourced items -- not vague generalities
  3. The daily summary answers "What decisions were made, by whom, with what rationale?" with participant attribution and stated reasoning
  4. The daily summary answers "What tasks/commitments were created, completed, or deferred?" with owners and deadlines where stated
  5. Every summary item traces back to a specific meeting via inline source citation (meeting title + date)
  6. The output contains zero evaluative language about individuals -- only actions, quotes, outcomes, and timestamps
**Plans**: 3 plans

Plans:
- [x] 03-01-PLAN.md -- Per-meeting extraction models, prompts, and extractor module with Claude API integration
- [x] 03-02-PLAN.md -- Evidence-only language validator with banned pattern detection and source attribution checking
- [x] 03-03-PLAN.md -- Daily cross-meeting synthesizer, template update with appendix, and full pipeline wiring

### Phase 4: Temporal Roll-Ups
**Goal**: Users can review weekly and monthly intelligence that traces threads across days rather than just concatenating summaries
**Depends on**: Phase 3
**Requirements**: TEMP-01, TEMP-02
**Success Criteria** (what must be TRUE):
  1. A weekly roll-up is produced from 5 daily summaries that groups related items into threads
  2. The weekly roll-up identifies the 3-5 most significant threads of the week with progression from first mention to current status
  3. A monthly narrative synthesizes 4 weekly summaries into thematic arcs, emerging risks, and strategic shifts
  4. Roll-up structure is consistent with daily structure (same categories, different granularity)
**Plans**: 2 plans

Plans:
- [x] 04-01-PLAN.md -- Weekly roll-up pipeline: thread detection, weekly template, CLI subcommand, backlinks
- [x] 04-02-PLAN.md -- Monthly narrative synthesis: thematic arcs, metrics, CLI subcommand

### Phase 5: Feedback and Refinement
**Goal**: The pipeline improves over time through explicit priority configuration, quality tracking, and structured data output for downstream use
**Depends on**: Phase 4
**Requirements**: None (enhancement phase)
**Success Criteria** (what must be TRUE):
  1. User can configure explicit priorities (projects, people, topics) that visibly influence what the daily synthesis emphasizes
  2. Quality metrics are tracked over time: edit frequency, section correction rates, data volume per run
  3. A JSON sidecar file is produced alongside each daily markdown for programmatic access to decisions, tasks, and source metadata
**Plans**: 2 plans

Plans:
- [x] 05-01-PLAN.md -- Priority configuration (projects, people, topics, suppress) and diff-based quality metrics tracking
- [x] 05-02-PLAN.md -- JSON sidecar output for programmatic task extraction and decision metadata

</details>

<details>
<summary>v1.5 Expanded Ingest (Phases 6-12) - SHIPPED 2026-04-05</summary>

**Milestone Goal:** Broaden the data surface beyond calendar and transcripts so synthesis sees the full picture of work activity.

- [x] **Phase 6: Data Model Foundation** - SourceItem model and commitment structure that all new sources depend on (completed 2026-04-04)
- [x] **Phase 7: Slack Ingest + Synthesis Integration** - Slack channel/DM ingestion with end-to-end synthesis validation (completed 2026-04-04)
- [x] **Phase 8: HubSpot Ingest** - Deal changes, contact notes, and CRM activity ingestion (completed 2026-04-04)
- [x] **Phase 9: Google Docs Ingest** - Document edit detection and content extraction (completed 2026-04-04)
- [x] **Phase 10: Cross-Source Synthesis + Commitments** - Deduplication tuning and structured commitment extraction across all sources (completed 2026-04-04)
- [x] **Phase 11: Pipeline Hardening** - Bug fixes, run_daily() decomposition, commitment model consolidation, dependency pinning (completed 2026-04-04)
- [x] **Phase 12: Reliability & Test Coverage** - API retry/backoff, token counting, pre-existing test fixes, pipeline orchestrator tests (completed 2026-04-05)

### Phase 6: Data Model Foundation
**Goal**: All new source data has a well-defined structure that ingest modules and synthesis can depend on
**Depends on**: Phase 5 (v1.0 complete)
**Requirements**: MODEL-01, MODEL-02
**Success Criteria** (what must be TRUE):
  1. A SourceItem can be instantiated with source type, channel/context, timestamp, content, and participants -- and validates correctly
  2. A Commitment can be instantiated with who, what, by-when, and source attribution -- and validates correctly
  3. Existing NormalizedEvent and DailySynthesis models still work unchanged (no regressions)
**Plans**: 1 plan

Plans:
- [x] 06-01-PLAN.md -- SourceItem model, Commitment model, SynthesisSource Protocol, NormalizedEvent conformance, tests

### Phase 7: Slack Ingest + Synthesis Integration
**Goal**: Daily summaries include Slack activity from curated channels and DMs, with source attribution throughout
**Depends on**: Phase 6
**Requirements**: SLACK-01, SLACK-02, SLACK-03, SLACK-04, SYNTH-05, SYNTH-07
**Success Criteria** (what must be TRUE):
  1. Running the pipeline produces a daily summary that includes Slack channel messages alongside meeting content
  2. Thread replies above the configured threshold appear expanded in the summary, not collapsed to just the parent message
  3. DM conversations appear in the summary with appropriate context
  4. User can run discovery mode to see proposed channels and confirm/reject them before ingestion uses that list
  5. Every Slack-sourced item in the output is attributed with "(per Slack #channel-name)" or "(per Slack DM with Person)"
**Plans**: 3 plans

Plans:
- [x] 07-01-PLAN.md -- Slack API client, message filtering, thread expansion, channel/DM fetching, SourceItem conversion
- [x] 07-02-PLAN.md -- Slack discovery mode CLI for channel/DM proposal and selection
- [x] 07-03-PLAN.md -- Synthesis prompt integration, pipeline wiring, output template update

### Phase 8: HubSpot Ingest
**Goal**: Daily summaries include HubSpot CRM activity -- deal movements, contact notes, and task changes
**Depends on**: Phase 7
**Requirements**: HUBSPOT-01, HUBSPOT-02, HUBSPOT-03
**Success Criteria** (what must be TRUE):
  1. Deal stage changes from the target date appear in the daily summary with deal name and stage transition
  2. Contact notes and activity from the target date appear in the summary with contact context
  3. HubSpot tickets, calls, emails, meetings, and tasks from the target date appear in the summary
  4. Every HubSpot-sourced item is attributed with "(per HubSpot [object type])"
**Plans**: 2 plans

Plans:
- [x] 08-01-PLAN.md -- HubSpot ingest module: SDK setup, deal/contact/ticket/engagement fetching, ownership scoping, TDD
- [x] 08-02-PLAN.md -- Pipeline integration: wire into synthesizer, writer, template with cross-source dedup

### Phase 9: Google Docs Ingest
**Goal**: Daily summaries include documents the user created or edited that day
**Depends on**: Phase 7
**Requirements**: DOCS-01, DOCS-02
**Success Criteria** (what must be TRUE):
  1. Documents the user edited on the target date appear in the daily summary with title and content extract
  2. Comments and suggestions on docs the user owns or is mentioned in appear in the summary
  3. Every Docs-sourced item is attributed with "(per Google Doc [title])"
**Plans**: 2 plans

Plans:
- [x] 09-01-PLAN.md -- Google Docs ingest module: edit detection, content extraction, comment fetching, SourceItem conversion
- [x] 09-02-PLAN.md -- Synthesis pipeline integration: wire docs into synthesizer, pipeline, writer, and daily template

### Phase 10: Cross-Source Synthesis + Commitments
**Goal**: Multi-source output is deduplicated and commitments are extracted with structured deadlines across all sources
**Depends on**: Phase 8, Phase 9
**Requirements**: SYNTH-06, SYNTH-08
**Success Criteria** (what must be TRUE):
  1. When the same topic appears in both a meeting transcript and a Slack thread, the daily summary consolidates it into one item with both sources attributed
  2. Commitments with deadlines are extracted from all sources (meetings, Slack, HubSpot) and appear as structured who/what/by-when entries in both the markdown output and JSON sidecar
  3. The JSON sidecar contains a commitments array with machine-readable who, what, by_when, and source fields
**Plans**: 2 plans

Plans:
- [x] 10-01-PLAN.md -- Enhanced synthesis prompt with cross-source dedup rules, Commitments table reordering
- [x] 10-02-PLAN.md -- Structured commitment extraction via Claude structured outputs, sidecar integration

### Phase 11: Pipeline Hardening
**Goal**: Fix known bugs, decompose the monolithic pipeline orchestrator, consolidate dead code, and lock dependencies for reproducible builds
**Depends on**: Phase 10
**Requirements**: None (quality/reliability phase)
**Gap Closure**: Closes integration gap MODEL-02-DEAD-CODE and flow gap COMMITMENT-NOCREDS from v1.5 audit
**Success Criteria** (what must be TRUE):
  1. Pipeline runs correctly when Google credentials are unavailable (Slack/HubSpot-only mode) -- commitment extraction still works
  2. `run_daily()` is decomposed into a pipeline runner; adding a new source requires editing only 1-2 locations, not 4
  3. All imports are at module level; a broken optional dependency produces a clear error at startup, not a silent partial run
  4. One shared Anthropic client is created per pipeline run and passed through
  5. Only one Commitment model exists in the codebase (dead Phase 6 model removed)
  6. `uv.lock` is committed and critical deps have upper-bound pins
  7. Slack backfill for past dates uses the target date, not stale cursors
  8. HubSpot owner resolution uses configured owner ID, not first-result assumption
  9. REQUIREMENTS.md traceability and SUMMARY frontmatter are accurate
**Plans**: 2 plans

Plans:
- [x] 11-01-PLAN.md -- Bug fixes (no-creds commitment, Slack backfill, HubSpot owner), dead code removal, dependency pinning
- [x] 11-02-PLAN.md -- Pipeline decomposition, shared Anthropic client, module-level imports, bookkeeping

### Phase 12: Reliability & Test Coverage
**Goal**: Pipeline gracefully handles transient API failures and has test coverage for orchestration logic and edge cases
**Depends on**: Phase 11
**Requirements**: None (quality/reliability phase)
**Success Criteria** (what must be TRUE):
  1. Google, Claude, and HubSpot API calls retry with exponential backoff (at least 2 retries) before failing
  2. Synthesis call estimates input tokens and truncates if over budget before sending to Claude
  3. All pre-existing test failures are fixed (test_notifications, test_extractor, test_writer)
  4. `main.py` pipeline orchestration has test coverage (at least happy path + single-source-failure path)
  5. Claude response parsers have tests for malformed/empty/unexpected responses
  6. All tests pass: `uv run pytest` exits 0
**Plans**: 3 plans

Plans:
- [x] 12-01-PLAN.md -- Shared retry decorator with tenacity, API call site wrapping, token budget estimation and truncation
- [x] 12-02-PLAN.md -- Fix broken test imports and assertions, add parser edge case tests
- [x] 12-03-PLAN.md -- Pipeline orchestration tests and GitHub Actions CI workflow

</details>

<details>
<summary>v1.5.1 Notion + Performance + Reliability (Phases 13-18) - SHIPPED 2026-04-05</summary>

**Milestone Goal:** Complete the ingest surface with Notion, parallelize the pipeline for speed, harden configuration and caching, and migrate Claude API calls to structured outputs.

- [x] **Phase 13: Typed Config Foundation** - Pydantic config model replacing raw dict access with validated, typed configuration (completed 2026-04-05)
- [x] **Phase 14: Structured Output Migration** - Claude API calls migrated from markdown parsing to json_schema structured outputs (completed 2026-04-05)
- [x] **Phase 15: Notion Ingestion** - Notion page and database ingestion completing the work source surface (completed 2026-04-05)
- [x] **Phase 16: Reliability Quick Wins** - Slack batch resolution, cache retention policy, and algorithmic dedup pre-filter (completed 2026-04-05)
- [x] **Phase 17: Asyncio Parallelization** - Concurrent ingest modules and parallel per-meeting extraction via asyncio (completed 2026-04-05)
- [x] **Phase 18: Structured Output Completion** - Gap closure: weekly/monthly structured outputs, deprecated beta header removal (completed 2026-04-05)
- [x] **Phase 18.1: Milestone Audit Gap Closure** - Verify Phase 16, fix notion_discovery.py bug, remove dead sync pipeline code (completed 2026-04-05)

### Phase 13: Typed Config Foundation
**Goal**: Pipeline configuration is validated at startup with typed access, catching misconfigurations immediately instead of failing deep in a run
**Depends on**: Phase 12
**Requirements**: CONFIG-01
**Success Criteria** (what must be TRUE):
  1. Running the pipeline with a valid config.yaml loads successfully and produces identical output to the current raw-dict approach
  2. Running the pipeline with a misspelled or invalid config key produces a clear Pydantic ValidationError at startup -- not a KeyError mid-run
  3. All existing config.yaml files (including those with missing optional sections) load without error due to backward-compatible defaults
  4. Every ingest module and synthesis function accesses config via typed attributes (e.g., `config.slack.channels`) instead of `.get()` chains
**Plans**: 2 plans

Plans:
- [x] 13-01-PLAN.md -- Pydantic config model tree, load_config() returning PipelineConfig, error formatter with fuzzy matching, validation tests
- [x] 13-02-PLAN.md -- Migrate all 15 consumer files from .get() chains to typed attribute access, update PipelineContext and test fixtures

### Phase 14: Structured Output Migration
**Goal**: Claude API responses are typed Pydantic models instead of parsed markdown, eliminating brittle regex extraction and enabling downstream schema validation
**Depends on**: Phase 13
**Requirements**: STRUCT-01
**Success Criteria** (what must be TRUE):
  1. Per-meeting extraction returns a typed `MeetingExtractionOutput` Pydantic model with decisions, commitments, and substance fields
  2. Daily synthesis returns a typed `DailySynthesisOutput` Pydantic model with all section content structured
  3. Running the pipeline on a known date produces equivalent content to the old markdown-parsing path (no silent data loss)
  4. The ~234 lines of regex/markdown parsing in extractor.py and synthesizer.py are deleted and replaced by Pydantic model access
**Plans**: 2 plans

Plans:
- [x] 14-01-PLAN.md -- Migrate per-meeting extraction to structured outputs (TDD)
- [x] 14-02-PLAN.md -- Migrate daily synthesis to structured outputs (TDD)

### Phase 15: Notion Ingestion
**Goal**: Daily summaries include Notion page updates and database changes, completing the set of work tools ingested by the pipeline
**Depends on**: Phase 14
**Requirements**: NOTION-01
**Success Criteria** (what must be TRUE):
  1. Notion pages edited on the target date appear in the daily summary with title and content extract
  2. Notion database items modified on the target date appear in the daily summary with property values and context
  3. Every Notion-sourced item is attributed with "(per Notion [page/database title])"
  4. The Notion integration handles API rate limits (3 req/s) without failing or dropping content
**Plans**: 3 plans

Plans:
- [x] 15-01-PLAN.md -- Notion ingest module: API client, page/DB fetching, SourceItem conversion, config model, tests
- [x] 15-02-PLAN.md -- Notion database discovery CLI and main.py subcommand wiring
- [x] 15-03-PLAN.md -- Pipeline integration: wire into synthesizer, writer, template, retry error handling

### Phase 16: Reliability Quick Wins
**Goal**: Three independent improvements that reduce API call volume, manage disk growth, and add a deterministic dedup layer before LLM synthesis
**Depends on**: Phase 15
**Requirements**: PERF-03, OPS-01, DEDUP-01
**Success Criteria** (what must be TRUE):
  1. Slack user resolution uses a single batch `users.list` call instead of N individual `users.info` calls per run
  2. Raw data cache files older than the configured TTL are automatically deleted on each pipeline run, while processed output (daily summaries, quality files) is never touched
  3. Algorithmically duplicate items across sources (same content, overlapping time window) are consolidated before reaching LLM synthesis, reducing token usage
  4. Near-match dedup decisions are logged so false positives can be identified and the threshold tuned
**Plans**: 3 plans

Plans:
- [x] 16-01-PLAN.md -- Batch Slack user resolution via users.list with disk cache and fallback (TDD)
- [x] 16-02-PLAN.md -- Cache retention policy with configurable TTL for raw data cleanup (TDD)
- [x] 16-03-PLAN.md -- Cross-source algorithmic dedup pre-filter with decision logging (TDD)

### Phase 17: Asyncio Parallelization
**Goal**: Independent ingest sources run concurrently and per-meeting Claude calls run in parallel, cutting pipeline wall-clock time roughly in half
**Depends on**: Phase 16
**Requirements**: PERF-01, PERF-02
**Success Criteria** (what must be TRUE):
  1. All ingest sources (Calendar, Transcripts, Slack, HubSpot, Google Docs, Notion) run concurrently via asyncio, with total ingest time bounded by the slowest source rather than the sum of all sources
  2. Per-meeting transcript extraction calls Claude concurrently with a rate-limit-aware semaphore, processing N meetings in parallel instead of sequentially
  3. A single source failure during parallel ingest does not crash the entire pipeline -- other sources complete and partial results are synthesized
  4. The public API (`run_pipeline()`) remains synchronous; asyncio is an internal implementation detail
  5. Pipeline wall-clock time for a typical day (5-8 meetings, 4-6 sources) is measurably faster than sequential execution
**Plans**: 2 plans

Plans:
- [x] 17-01-PLAN.md -- Async extraction functions with AsyncAnthropic, semaphore rate limiting, config field
- [x] 17-02-PLAN.md -- Async pipeline orchestrator with parallel ingest via asyncio.gather, timing instrumentation

### Phase 18: Structured Output Completion
**Goal**: Close STRUCT-01 gap -- migrate weekly.py and monthly.py to structured outputs, fix deprecated beta header causing production 400 errors, clean up dead imports
**Depends on**: Phase 14, Phase 17
**Requirements**: STRUCT-01
**Gap Closure**: Closes gaps from v1.5.1 milestone audit
**Success Criteria** (what must be TRUE):
  1. weekly.py uses json_schema structured outputs with a Pydantic model instead of free-text markdown + regex parsing
  2. monthly.py uses json_schema structured outputs with a Pydantic model instead of free-text markdown + regex parsing
  3. Deprecated output-format-2025-01-24 beta header removed from all API call sites -- no 400 errors on extraction
  4. Dead import of dedup_source_items removed from pipeline.py
  5. All existing tests pass; new tests cover structured output paths for weekly and monthly
**Plans**: 2 plans

Plans:
- [x] 18-01-PLAN.md -- Migrate weekly.py and monthly.py to structured outputs with Pydantic output models and converter functions (TDD)
- [x] 18-02-PLAN.md -- Remove deprecated beta header fallback from extractor/synthesizer/commitments, remove dead dedup import from pipeline.py

### Phase 18.1: Milestone Audit Gap Closure
**Goal**: Close remaining v1.5.1 audit gaps -- verify Phase 16 requirements (PERF-03, OPS-01, DEDUP-01), fix notion_discovery.py str->Path crash, remove dead sync pipeline code
**Depends on**: Phase 18
**Requirements**: PERF-03, OPS-01, DEDUP-01, NOTION-01
**Gap Closure**: Closes gaps from v1.5.1 re-audit
**Success Criteria** (what must be TRUE):
  1. Phase 16 has a VERIFICATION.md confirming PERF-03, OPS-01, DEDUP-01 are satisfied
  2. `python -m src.main discover-notion --config config.yaml` reaches the Notion token check without crashing
  3. No dead `_ingest_calendar` function or `extract_all_meetings` import remains in pipeline.py
  4. All existing tests pass
**Plans**: 2 plans

Plans:
- [x] 18.1-01-PLAN.md -- Verify Phase 16 and fix notion_discovery.py str->Path bug
- [x] 18.1-02-PLAN.md -- Remove dead sync pipeline code from pipeline.py

</details>

<details>
<summary>v2.0 Entity Layer (Phases 19-23.1) - SHIPPED 2026-04-08</summary>

**Milestone Goal:** Make every synthesis item traceable to partners, people, and initiatives -- so you can ask "what's happening with Affirm?" or "what does Colin owe me?" and get a sourced answer.

- [x] **Phase 19: Entity Registry Foundation** - SQLite entity storage with schema migrations, alias management, and confidence scoring models
- [x] **Phase 20: Entity Discovery + Backfill** - Populate the registry from historical summaries and wire ongoing discovery into the pipeline (completed 2026-04-06)
- [x] **Phase 21: Entity Attribution** - Tag synthesis items with entity references and persist mentions to SQLite and JSON sidecar (completed 2026-04-08)
- [x] **Phase 22: Merge + Split Review** - Entity merge proposals with CLI confirmation and split/undo capability (completed 2026-04-08)
- [x] **Phase 23: Scoped Views + Reports** - CLI entity queries and generated per-entity markdown reports (completed 2026-04-08)
- [x] **Phase 23.1: Milestone Audit Gap Closure** - Pipeline ordering fix, template path fix, verifications, summary backfill (completed 2026-04-08)

### Phase 19: Entity Registry Foundation
**Goal**: Named entities (partners and people) have persistent storage with alias support and confidence scoring, forming the foundation every other entity feature depends on
**Depends on**: Phase 18 (v1.5.1 complete)
**Requirements**: ENTY-01, ENTY-02, ENTY-03
**Success Criteria** (what must be TRUE):
  1. User can run a CLI command to create a partner or person entity, and it persists in SQLite across pipeline runs
  2. User can add, list, and remove aliases for an entity via CLI (e.g., `entity alias add "Colin Roberts" "CR"`) and alias resolution returns the canonical entity
  3. The SQLite schema includes all tables needed for the full entity layer (entities, aliases, mentions, merge_proposals, relationships) with soft-delete and merge_target_id fields baked in from day one
  4. Schema migrations run automatically on startup via PRAGMA user_version, so future phases can evolve the schema safely
  5. Entity config section in config.yaml is validated by Pydantic at startup with sensible defaults
**Plans**: 2 plans

Plans:
- [x] 19-01-PLAN.md -- SQLite schema, Pydantic entity models, migration infrastructure, EntityConfig, db connection management
- [x] 19-02-PLAN.md -- EntityRepository CRUD, alias management, CLI commands (entity add/list/show/remove/alias), .gitignore update

### Phase 20: Entity Discovery + Backfill
**Goal**: The entity registry is populated -- both from 6+ months of historical summaries and automatically on each new pipeline run -- with HubSpot cross-referencing for enrichment
**Depends on**: Phase 19
**Requirements**: DISC-01, DISC-02, DISC-05
**Success Criteria** (what must be TRUE):
  1. Running `entity backfill --from 2025-10-01 --to 2026-04-05` scans existing daily sidecar JSONs and populates the registry with discovered partners and people
  2. A normal daily pipeline run automatically discovers and registers new entities as a post-synthesis step without manual intervention
  3. Discovered entities are cross-referenced with HubSpot contacts and deals by name match, enriching the registry with external identifiers
  4. Entity extraction from synthesis output uses structured output fields (extending existing Pydantic models with optional entity_names) and does not break the pipeline if entity processing fails
  5. Name normalization handles common variants (stripping Inc/LLC, standardizing casing) so "Affirm Inc" and "Affirm" resolve to the same entity
**Plans**: 3 plans

Plans:
- [x] 20-01-PLAN.md -- Name normalization module (TDD), entity extraction via Claude structured outputs, SynthesisItem/CommitmentRow model extension with entity_names
- [x] 20-02-PLAN.md -- Backfill CLI with weekly batching and checkpoint/resume, schema v2 migration, ongoing discovery wired into async_pipeline post-synthesis
- [x] 20-03-PLAN.md -- HubSpot contact/deal cross-reference with rapidfuzz fuzzy matching, entity enrichment in both backfill and pipeline paths

### Phase 21: Entity Attribution
**Goal**: Every synthesis item carries entity references that are persisted to both SQLite (for querying) and JSON sidecar (for portability), making entity-scoped filtering possible
**Depends on**: Phase 20
**Requirements**: ATTR-01, ATTR-02
**Success Criteria** (what must be TRUE):
  1. Running the daily pipeline produces a sidecar JSON where each synthesis item includes an `entity_references` field linking to registered entities with confidence scores
  2. Entity mentions are stored in the SQLite `entity_mentions` table with source, date, confidence, and the synthesis item they reference
  3. The entity attribution stage in the pipeline is wrapped in try/except -- if it fails, the daily summary still generates normally with no entity fields
  4. Running the pipeline with the entity database deleted or missing still produces a valid daily summary (graceful degradation)
**Plans**: 2 plans

Plans:
- [x] 21-01-PLAN.md -- TDD attributor module (name matching, confidence scoring, content hashing), sidecar entity models, synthesizer entity_names preservation
- [x] 21-02-PLAN.md -- Pipeline integration as optional post-synthesis stage in async_pipeline with graceful degradation, sidecar wiring, integration tests

### Phase 22: Merge + Split Review
**Goal**: Users can consolidate fragmented entity references ("Colin" / "Colin R." / "colin@partner.com") via merge proposals and undo incorrect merges via split -- so scoped views return clean, consolidated results
**Depends on**: Phase 21
**Requirements**: DISC-03, DISC-04
**Success Criteria** (what must be TRUE):
  1. The system generates merge proposals when name similarity exceeds the configured threshold, ranked by confidence with full context (which sources, which synthesis items mention each variant)
  2. User can review merge proposals via CLI (`entity review`) and accept or reject each one, with rejections persisted so the same pair is never proposed again
  3. User can split an incorrectly merged entity (`entity split`) and mentions are re-attributed to the restored entities
  4. Merge proposals are capped per review session (configurable, default 10) to prevent proposal fatigue
**Plans**: 2 plans

Plans:
- [x] 22-01: Merge proposal generation (rapidfuzz similarity), proposal storage, CLI review workflow (accept/reject/skip with persistent rejection)
- [x] 22-02: Merge execution (soft pointer via merge_target_id), split/undo capability with mention re-attribution, batch proposal presentation

### Phase 23: Scoped Views + Reports
**Goal**: Users can ask "what's happening with Affirm?" or "what does Colin owe me?" and get a sourced, time-filtered answer -- the payoff of the entire entity layer
**Depends on**: Phase 22
**Requirements**: VIEW-01, VIEW-02, VIEW-03
**Success Criteria** (what must be TRUE):
  1. User can run `entity show "Affirm"` and see a scoped report of all synthesis items referencing that entity, ordered by date, with source attribution
  2. User can run `entity show "Affirm" --from 2026-03-01 --to 2026-04-01` to filter the scoped view by time range
  3. Running `entity report "Affirm"` generates a per-entity markdown file in `output/entities/` covering the configured time range
  4. Entity list command (`entity list --type partner`) shows all entities with mention frequency, open commitments count, and last-active date
  5. Temporal entity summaries surface the most significant recent activity, not just a raw chronological dump
**Plans**: 2 plans

Plans:
- [x] 23-01-PLAN.md -- SQL query layer + significance scoring (TDD), CLI entity show with scoped views and enriched entity list
- [x] 23-02-PLAN.md -- Jinja2 entity report template, entity report CLI command, output/entities/ generation

### Phase 23.1: Milestone Audit Gap Closure
**Goal**: Close v2.0 audit gaps -- fix pipeline attribution/discovery ordering, fix relative template path, write missing VERIFICATION.md for phases 19 and 23
**Depends on**: Phase 23
**Requirements**: ENTY-01, ENTY-02, ENTY-03, VIEW-01, VIEW-02, VIEW-03, ATTR-01
**Gap Closure**: Closes gaps from v2.0 audit
**Success Criteria** (what must be TRUE):
  1. Pipeline runs discovery before attribution so first-mention entities are attributed same day
  2. `entity report` works from any working directory (absolute template path resolution)
  3. Phase 19 VERIFICATION.md exists and confirms all success criteria met
  4. Phase 23 VERIFICATION.md exists and confirms all success criteria met
  5. All SUMMARY.md files for phases 19-23 have `requirements` frontmatter populated
**Plans**: 1 plan

Plans:
- [x] 23.1-01: Fix pipeline ordering, fix template path, write VERIFICATION.md for phases 19 and 23, backfill requirements in summary frontmatter

</details>

## v3.0 Web Interface (Phases 24-29)

**Milestone Goal:** A polished, demo-quality web UI that replaces the CLI as the daily interface -- browse summaries, manage entities, configure the pipeline, and trigger runs from the browser.

- [x] **Phase 24: FastAPI Skeleton + Summary API** - App factory, CORS, dependency injection, summary read endpoints, SQLite busy_timeout hardening (completed 2026-04-08)
- [x] **Phase 25: Next.js Scaffold + Summary View** - Three-column layout shell, daily summary rendering, date navigation, roll-up browsing
- [x] **Phase 26: Entity API + Entity Browser** - Entity list/scoped view endpoints, nav sidebar with activity indicators, context sidebar (completed 2026-04-09)
- [ ] **Phase 27: Entity Management UI** - Entity CRUD forms, merge proposal review, alias management, command palette
- [ ] **Phase 28: Pipeline Run Management** - Pipeline trigger endpoint, SSE status streaming, subprocess isolation, run history
- [ ] **Phase 29: Config Management + Polish** - Config viewer/editor, dark mode, keyboard navigation, design polish

## Phase Details

### Phase 24: FastAPI Skeleton + Summary API
**Goal**: The API foundation is proven -- FastAPI serves real summary data from existing files with safe SQLite access, validating the core integration pattern before any UI is built
**Depends on**: Phase 23.1 (v2.0 complete)
**Requirements**: API-01, API-02, API-03, SUM-03
**Success Criteria** (what must be TRUE):
  1. `uvicorn api.app:app` starts on localhost:8000 and responds to health check with CORS headers allowing localhost:3000
  2. `GET /api/summaries/{date}` returns structured JSON (from sidecar) plus rendered markdown for a real historical date
  3. `GET /api/summaries` returns a list of available dates so the frontend can build navigation without guessing
  4. All API endpoints import from `src.*` modules -- zero business logic in the `api/` directory (grep for `sqlite3` in api/ returns nothing)
  5. SQLite connections use `busy_timeout=5000` and connection-per-request via FastAPI dependency injection
**Pitfall Warnings**: Event loop conflict (#3) -- refactor async_pipeline entry point before building endpoints. CORS (#6) -- CORSMiddleware must be first middleware. SQLite busy_timeout (#1) -- add pragma to connection factory.
**Plans**: 2 plans

Plans:
- [ ] 24-01-PLAN.md -- FastAPI skeleton with summary endpoints, SQLite hardening, API tests
- [ ] 24-02-PLAN.md -- Next.js scaffold, Makefile, end-to-end CORS validation

### Phase 25: Next.js Scaffold + Summary View
**Goal**: The daily use case works in the browser -- user opens localhost:3000 and sees yesterday's summary in a three-column layout, can navigate between dates, and sees roll-ups
**Depends on**: Phase 24
**Requirements**: NAV-01, SUM-01, SUM-02, SUM-04, UX-03
**Success Criteria** (what must be TRUE):
  1. Opening localhost:3000 shows a three-column layout with left nav, center content panel, and right context sidebar
  2. The center panel renders the daily summary for the most recent available date with structured data (decisions, commitments, substance) and markdown content
  3. User can navigate between dates via prev/next arrows and a date picker, with graceful "no summary" messaging for missing dates
  4. Weekly and monthly roll-up summaries are browsable from the same navigation as daily summaries
  5. Each panel has loading skeletons, error boundaries prevent one panel's failure from crashing the entire page, and action results show toast notifications
**Pitfall Warnings**: RSC misuse (#9) -- use client components for all interactive panels, server components only for layout shell. Two build systems (#15) -- create unified Makefile with `make dev` running both servers.
**Plans**: 4 plans

Plans:
- [x] 25-01-PLAN.md -- Install frontend deps, create data layer (API client, types, hooks, Zustand store, providers), add roll-up API endpoints
- [x] 25-02-PLAN.md -- Three-column layout shell with collapsible sidebars and icon rails
- [x] 25-03-PLAN.md -- Summary view with structured cards, markdown renderer, error boundaries, loading skeletons, metadata sidebar
- [x] 25-04-PLAN.md -- Date navigation: grouped date list (Daily/Weekly/Monthly), prev/next arrows, calendar date picker

### Phase 26: Entity API + Entity Browser
**Goal**: The entity navigation experience works end-to-end -- user sees entities in the left nav, clicks one, and sees its scoped view in the center panel with contextual details in the right sidebar
**Depends on**: Phase 25
**Requirements**: NAV-02, NAV-03, NAV-04, ENT-01, ENT-02, ENT-05
**Success Criteria** (what must be TRUE):
  1. Left nav shows entities grouped by type (partners, people, initiatives) with activity indicator dots on entities active in the last 7 days
  2. User can filter the entity list by type and sort by activity or name
  3. Clicking an entity in the left nav loads its scoped view in the center panel showing highlights, open commitments, and activity timeline with significance scoring
  4. The right sidebar adapts to the current selection -- for entities it shows aliases, metadata, organization linkage, and related entities
  5. Clicking a mention in the activity timeline expands the source evidence snippet showing source type, date, and confidence score
**Pitfall Warnings**: Logic duplication (#4) -- entity endpoints must import from `src.entity.repository` and `src.entity.views`, no direct SQL. Concurrent reads (#1) -- connection-per-request pattern from Phase 24 handles this.
**Plans**: 3 plans

Plans:
- [ ] 26-01-PLAN.md -- Entity API endpoints (list, scoped view, related entities) + related entities repository method
- [ ] 26-02-PLAN.md -- Frontend data layer: entity TypeScript types, TanStack Query hooks, Zustand store additions
- [ ] 26-03-PLAN.md -- Entity browser UI: tab switcher, grouped entity list, scoped view, evidence drill-down, sidebar adaptation

### Phase 27: Entity Management UI
**Goal**: Users can manage the entity registry entirely from the browser -- create, edit, delete entities, review merge proposals, manage aliases, and navigate anywhere via keyboard
**Depends on**: Phase 26
**Requirements**: ENT-03, ENT-04, NAV-05
**Success Criteria** (what must be TRUE):
  1. User can create a new entity (partner, person, or initiative) from a form in the browser with immediate feedback on success or validation errors
  2. User can edit an entity's name, type, and metadata, and delete entities with a confirmation step
  3. Merge proposal review UI shows side-by-side entity comparison with similarity score, mention counts, and one-click approve/reject
  4. User can add and remove aliases for any entity from the entity detail view
  5. Command palette (Cmd+K) enables keyboard-first search for entities by name/alias, jump to any date, and trigger actions without touching the mouse
**Pitfall Warnings**: Concurrent write locks (#1) -- use `BEGIN IMMEDIATE` for entity writes. Thread safety (#8) -- never share PipelineContext or mutable state across requests.
**Plans**: 4 plans
- [x] 27-01-PLAN.md — API endpoints for entity CRUD, aliases, merge proposals + shadcn-ui components + apiMutate helper
- [x] 27-02-PLAN.md — Entity CRUD forms (slide-over panel), delete confirmation, alias chip management
- [ ] 27-03-PLAN.md — Merge proposal review UI (side-by-side comparison, approve/reject queue)
- [ ] 27-04-PLAN.md — Command palette (Cmd+K) with entity/date/action search and keyboard navigation

### Phase 28: Pipeline Run Management
**Goal**: Users can trigger and monitor pipeline runs from the browser -- fire-and-forget with real-time status updates, never blocking the API server
**Depends on**: Phase 27
**Requirements**: PIPE-01, PIPE-02, PIPE-03
**Success Criteria** (what must be TRUE):
  1. User can trigger a pipeline run from the browser and see real-time stage-by-stage progress via SSE (calendar_ingest running... complete... synthesis running...)
  2. Pipeline runs execute in a subprocess or thread pool -- triggering a run does not degrade API responsiveness for other requests
  3. Run history page shows past runs with status (success/failed/running), duration, target date, and error details for failed runs
  4. If the SSE connection drops mid-run, reconnecting shows current status (not lost state)
**Pitfall Warnings**: Server blocking (#2) -- pipeline MUST run in subprocess, never in-process. Event loop conflict (#3) -- use `await async_pipeline()` directly or subprocess, never nested `asyncio.run()`. Lost state (#12) -- persist run status to survive server restarts.
**Plans**: TBD

### Phase 29: Config Management + Polish
**Goal**: The v3.0 feature set is complete and demo-quality -- config is manageable from the browser, the UI is dark-mode ready, keyboard-navigable, and visually polished
**Depends on**: Phase 28
**Requirements**: CFG-01, CFG-02, CFG-03, UX-01, UX-02, UX-04
**Success Criteria** (what must be TRUE):
  1. User can view the current pipeline config (sources, channels, priorities) in a structured, readable format in the browser
  2. User can edit config fields with Pydantic validation -- invalid values show structured error messages, valid changes are saved atomically (temp file + rename) with backup of previous version
  3. Dark mode works with system preference detection and a manual toggle, persisted across sessions
  4. Keyboard navigation works across all three columns: j/k for list traversal, h/l for column focus, Enter to select, Esc to deselect
  5. The overall design is demo-presentable with consistent typography, spacing, color palette, and visual hierarchy across all views
**Pitfall Warnings**: Write safety (#7) -- build config read-only view first, validate all writes through PipelineConfig before disk write. Config mutation (#7) -- atomic write with backup, reject writes during active pipeline runs.
**Plans**: TBD

## Progress

**Execution Order:**
Phases 24-29 execute sequentially: 24 -> 25 -> 26 -> 27 -> 28 -> 29.

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 0. Execution Model Validation | v1.0 | 2/2 | Complete | 2026-04-02 |
| 1. Foundation and Calendar Ingestion | v1.0 | 2/2 | Complete | 2026-04-02 |
| 2. Transcript Ingestion and Normalization | v1.0 | 3/3 | Complete | 2026-04-02 |
| 3. Two-Stage Synthesis Pipeline | v1.0 | 3/3 | Complete | 2026-04-02 |
| 4. Temporal Roll-Ups | v1.0 | 2/2 | Complete | 2026-04-03 |
| 5. Feedback and Refinement | v1.0 | 2/2 | Complete | 2026-04-03 |
| 6. Data Model Foundation | v1.5 | 1/1 | Complete | 2026-04-04 |
| 7. Slack Ingest + Synthesis Integration | v1.5 | 3/3 | Complete | 2026-04-04 |
| 8. HubSpot Ingest | v1.5 | 2/2 | Complete | 2026-04-04 |
| 9. Google Docs Ingest | v1.5 | 2/2 | Complete | 2026-04-04 |
| 10. Cross-Source Synthesis + Commitments | v1.5 | 2/2 | Complete | 2026-04-04 |
| 11. Pipeline Hardening | v1.5 | 2/2 | Complete | 2026-04-04 |
| 12. Reliability & Test Coverage | v1.5 | 3/3 | Complete | 2026-04-05 |
| 13. Typed Config Foundation | v1.5.1 | 2/2 | Complete | 2026-04-05 |
| 14. Structured Output Migration | v1.5.1 | 2/2 | Complete | 2026-04-05 |
| 15. Notion Ingestion | v1.5.1 | 3/3 | Complete | 2026-04-05 |
| 16. Reliability Quick Wins | v1.5.1 | 3/3 | Complete | 2026-04-05 |
| 17. Asyncio Parallelization | v1.5.1 | 2/2 | Complete | 2026-04-05 |
| 18. Structured Output Completion | v1.5.1 | 2/2 | Complete | 2026-04-05 |
| 18.1. Milestone Audit Gap Closure | v1.5.1 | 2/2 | Complete | 2026-04-05 |
| 19. Entity Registry Foundation | v2.0 | 2/2 | Complete | 2026-04-06 |
| 20. Entity Discovery + Backfill | v2.0 | 3/3 | Complete | 2026-04-06 |
| 21. Entity Attribution | v2.0 | 2/2 | Complete | 2026-04-08 |
| 22. Merge + Split Review | v2.0 | 2/2 | Complete | 2026-04-08 |
| 23. Scoped Views + Reports | v2.0 | 2/2 | Complete | 2026-04-08 |
| 23.1. Milestone Audit Gap Closure | v2.0 | 1/1 | Complete | 2026-04-08 |
| 24. FastAPI Skeleton + Summary API | 2/2 | Complete    | 2026-04-08 | - |
| 25. Next.js Scaffold + Summary View | v3.0 | 0/TBD | Not started | - |
| 26. Entity API + Entity Browser | 3/3 | Complete   | 2026-04-09 | - |
| 27. Entity Management UI | 1/4 | In Progress|  | - |
| 28. Pipeline Run Management | v3.0 | 0/TBD | Not started | - |
| 29. Config Management + Polish | v3.0 | 0/TBD | Not started | - |
