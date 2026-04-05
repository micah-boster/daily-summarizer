# Roadmap: Work Intelligence Daily Summarizer

## Milestones

- ✅ **v1.0 Daily Intelligence Pipeline** - Phases 0-5 (shipped 2026-04-03)
- ✅ **v1.5 Expanded Ingest** - Phases 6-12 (shipped 2026-04-05)
- 📋 **v1.5.1 Notion + Performance + Reliability** - Phases 13-17 (planned)

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

### v1.5.1 Notion + Performance + Reliability

**Milestone Goal:** Complete the ingest surface with Notion, parallelize the pipeline for speed, harden configuration and caching, and migrate Claude API calls to structured outputs.

- [ ] **Phase 13: Typed Config Foundation** - Pydantic config model replacing raw dict access with validated, typed configuration
- [ ] **Phase 14: Structured Output Migration** - Claude API calls migrated from markdown parsing to json_schema structured outputs
- [ ] **Phase 15: Notion Ingestion** - Notion page and database ingestion completing the work source surface
- [ ] **Phase 16: Reliability Quick Wins** - Slack batch resolution, cache retention policy, and algorithmic dedup pre-filter
- [ ] **Phase 17: Asyncio Parallelization** - Concurrent ingest modules and parallel per-meeting extraction via asyncio

## Phase Details

### Phase 13: Typed Config Foundation
**Goal**: Pipeline configuration is validated at startup with typed access, catching misconfigurations immediately instead of failing deep in a run
**Depends on**: Phase 12
**Requirements**: CONFIG-01
**Success Criteria** (what must be TRUE):
  1. Running the pipeline with a valid config.yaml loads successfully and produces identical output to the current raw-dict approach
  2. Running the pipeline with a misspelled or invalid config key produces a clear Pydantic ValidationError at startup -- not a KeyError mid-run
  3. All existing config.yaml files (including those with missing optional sections) load without error due to backward-compatible defaults
  4. Every ingest module and synthesis function accesses config via typed attributes (e.g., `config.slack.channels`) instead of `.get()` chains
**Plans**: TBD

### Phase 14: Structured Output Migration
**Goal**: Claude API responses are typed Pydantic models instead of parsed markdown, eliminating brittle regex extraction and enabling downstream schema validation
**Depends on**: Phase 13
**Requirements**: STRUCT-01
**Success Criteria** (what must be TRUE):
  1. Per-meeting extraction returns a typed `MeetingExtractionOutput` Pydantic model with decisions, commitments, and substance fields
  2. Daily synthesis returns a typed `DailySynthesisOutput` Pydantic model with all section content structured
  3. Running the pipeline on a known date produces equivalent content to the old markdown-parsing path (no silent data loss)
  4. The ~234 lines of regex/markdown parsing in extractor.py and synthesizer.py are deleted and replaced by Pydantic model access
**Plans**: TBD

### Phase 15: Notion Ingestion
**Goal**: Daily summaries include Notion page updates and database changes, completing the set of work tools ingested by the pipeline
**Depends on**: Phase 14
**Requirements**: NOTION-01
**Success Criteria** (what must be TRUE):
  1. Notion pages edited on the target date appear in the daily summary with title and content extract
  2. Notion database items modified on the target date appear in the daily summary with property values and context
  3. Every Notion-sourced item is attributed with "(per Notion [page/database title])"
  4. The Notion integration handles API rate limits (3 req/s) without failing or dropping content
**Plans**: TBD

### Phase 16: Reliability Quick Wins
**Goal**: Three independent improvements that reduce API call volume, manage disk growth, and add a deterministic dedup layer before LLM synthesis
**Depends on**: Phase 15
**Requirements**: PERF-03, OPS-01, DEDUP-01
**Success Criteria** (what must be TRUE):
  1. Slack user resolution uses a single batch `users.list` call instead of N individual `users.info` calls per run
  2. Raw data cache files older than the configured TTL are automatically deleted on each pipeline run, while processed output (daily summaries, quality files) is never touched
  3. Algorithmically duplicate items across sources (same content, overlapping time window) are consolidated before reaching LLM synthesis, reducing token usage
  4. Near-match dedup decisions are logged so false positives can be identified and the threshold tuned
**Plans**: TBD

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
**Plans**: TBD

## Progress

**Execution Order:**
Phases 13-17 execute sequentially: 13 -> 14 -> 15 -> 16 -> 17.
Each phase builds on the stability of the prior phase. Phase 17 (async) goes last because it changes execution semantics and benefits from all other features being stable.

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
| 13. Typed Config Foundation | v1.5.1 | 0/0 | Not started | - |
| 14. Structured Output Migration | v1.5.1 | 0/0 | Not started | - |
| 15. Notion Ingestion | v1.5.1 | 0/0 | Not started | - |
| 16. Reliability Quick Wins | v1.5.1 | 0/0 | Not started | - |
| 17. Asyncio Parallelization | v1.5.1 | 0/0 | Not started | - |
