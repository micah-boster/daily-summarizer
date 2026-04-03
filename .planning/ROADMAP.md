# Roadmap: Work Intelligence Daily Summarizer

## Overview

This roadmap delivers a personal daily intelligence pipeline in six phases, built from the ground up. Phase 0 validates that the execution model (Cowork + Claude Code + Google OAuth) actually works before any real code is written. Phases 1-2 build the data pipeline bottom-up: models and output first (so everything is testable with mock data), then calendar ingestion, then transcript ingestion with normalization. Phase 3 delivers the core value -- two-stage LLM synthesis that answers the three daily questions (substance, decisions, commitments) with source attribution. Phase 4 adds temporal roll-ups (weekly and monthly). Phase 5 adds feedback mechanisms and refinement once the base pipeline proves useful.

## Phases

**Phase Numbering:**
- Integer phases (0, 1, 2, 3, 4, 5): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 0: Execution Model Validation** - Prove Cowork scheduling, Google OAuth, and Claude Code session reliability before building anything
- [ ] **Phase 1: Foundation and Calendar Ingestion** - Data models, markdown output writer, Google Calendar ingestion, and project scaffolding
- [ ] **Phase 2: Transcript Ingestion and Normalization** - Gemini and Gong transcript parsing, calendar-transcript linking, noise filtering, deduplication
- [ ] **Phase 3: Two-Stage Synthesis Pipeline** - Per-meeting extraction and daily cross-meeting synthesis answering the three core questions with source attribution
- [ ] **Phase 4: Temporal Roll-Ups** - Weekly summaries from accumulated dailies and monthly narrative with themes and progression arcs
- [ ] **Phase 5: Feedback and Refinement** - Priority configuration, quality tracking, structured data sidecar, and prompt tuning informed by accumulated output

## Phase Details

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
- [ ] 00-01-PLAN.md -- Project scaffolding, OAuth module, Slack notifications, validation script with retry logic
- [ ] 00-02-PLAN.md -- Operational docs (re-auth procedure, Cowork setup guide) and 5-day scheduled validation

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
- [ ] 01-01-PLAN.md — Pydantic data models, Jinja2 output writer, YAML config, CLI entry point
- [ ] 01-02-PLAN.md — Google Calendar ingestion module with event normalization and end-to-end pipeline wiring

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
- [ ] 02-01-PLAN.md — Gmail API utilities, Gemini transcript parser, filler stripping
- [ ] 02-02-PLAN.md — Gong transcript parser, combined fetch function
- [ ] 02-03-PLAN.md — Normalization pipeline with calendar-transcript linking, deduplication, pipeline wiring

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
- [ ] 03-01-PLAN.md — Per-meeting extraction models, prompts, and extractor module with Claude API integration
- [ ] 03-02-PLAN.md — Evidence-only language validator with banned pattern detection and source attribution checking
- [ ] 03-03-PLAN.md — Daily cross-meeting synthesizer, template update with appendix, and full pipeline wiring

### Phase 4: Temporal Roll-Ups
**Goal**: Users can review weekly and monthly intelligence that traces threads across days rather than just concatenating summaries
**Depends on**: Phase 3 (requires several weeks of accumulated daily summaries)
**Requirements**: TEMP-01, TEMP-02
**Success Criteria** (what must be TRUE):
  1. A weekly roll-up is produced from 5 daily summaries that groups related items into threads (e.g., a decision discussed Monday and revised Wednesday appears as one thread, not two disconnected items)
  2. The weekly roll-up identifies the 3-5 most significant threads of the week with progression from first mention to current status
  3. A monthly narrative synthesizes 4 weekly summaries into thematic arcs, emerging risks, and strategic shifts -- not a longer list of everything
  4. Roll-up structure is consistent with daily structure (same categories, different granularity)
**Plans**: 2 plans

Plans:
- [ ] 04-01-PLAN.md -- Weekly roll-up pipeline: thread detection, weekly template, CLI subcommand, backlinks
- [ ] 04-02-PLAN.md -- Monthly narrative synthesis: thematic arcs, metrics, CLI subcommand

### Phase 5: Feedback and Refinement
**Goal**: The pipeline improves over time through explicit priority configuration, quality tracking, and structured data output for downstream use
**Depends on**: Phase 4 (requires proven base synthesis quality)
**Requirements**: None (enhancement phase -- no v1 requirements; delivers differentiator features from research)
**Success Criteria** (what must be TRUE):
  1. User can configure explicit priorities (projects, people, topics) that visibly influence what the daily synthesis emphasizes
  2. Quality metrics are tracked over time: edit frequency, section correction rates, data volume per run
  3. A JSON sidecar file is produced alongside each daily markdown for programmatic access to decisions, tasks, and source metadata
**Plans**: 2 plans

Plans:
- [ ] 05-01-PLAN.md — Priority configuration (projects, people, topics, suppress) and diff-based quality metrics tracking
- [ ] 05-02-PLAN.md — JSON sidecar output for programmatic task extraction and decision metadata

## Progress

**Execution Order:**
Phases execute in numeric order: 0 -> 1 -> 2 -> 3 -> 4 -> 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 0. Execution Model Validation | 0/2 | Not started | - |
| 1. Foundation and Calendar Ingestion | 0/2 | Not started | - |
| 2. Transcript Ingestion and Normalization | 0/3 | Not started | - |
| 3. Two-Stage Synthesis Pipeline | 0/3 | Not started | - |
| 4. Temporal Roll-Ups | 0/2 | Not started | - |
| 5. Feedback and Refinement | 0/2 | Not started | - |
