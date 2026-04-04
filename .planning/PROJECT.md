# Work Intelligence System

## What This Is

A personal work intelligence system that ingests data from multiple work sources (calendar, transcripts, Slack, HubSpot, Google Docs, Notion) to produce structured daily summaries answering what happened of substance, what decisions were made, and what tasks/commitments emerged. Rolls up into weekly, monthly, and quarterly intelligence. Built for Micah Boster as a personal tool evolving toward an entity-aware platform with action capabilities and a web interface.

## Core Value

Every morning I open a structured daily summary of yesterday's work and find it accurate, useful, and worth 5 minutes of my time — without having produced it manually.

## Current Milestone: v1.5.1 Notion + Performance + Reliability

**Goal:** Complete the ingest surface with Notion, parallelize the pipeline for speed, harden configuration and caching, and migrate Claude API calls to structured outputs.

**Target features:**
- Notion page/database ingestion for daily summaries
- Parallel ingest modules via asyncio (independent sources run concurrently)
- Parallel per-meeting transcript extraction (concurrent Claude API calls)
- Slack user batch resolution (users_list instead of N individual calls)
- Algorithmic cross-source deduplication (supplement to LLM-based)
- Typed config model with Pydantic validation on config.yaml load
- Raw data cache retention policy (auto-delete after configurable TTL)
- Migrate Claude API responses from markdown parsing to structured outputs (json_schema)

## Requirements

### Validated

- ✓ Semi-automated daily pipeline (v1.0)
- ✓ Google Calendar event ingestion (v1.0)
- ✓ Meeting transcript ingestion — Gemini and Gong (v1.0)
- ✓ Daily synthesis: substance, decisions, commitments (v1.0)
- ✓ Structured markdown output with source attribution (v1.0)
- ✓ Weekly and monthly temporal roll-ups (v1.0)
- ✓ Evidence-only framing enforced (v1.0)
- ✓ Priority configuration (v1.0)
- ✓ Slack digest notifications (v1.0)
- ✓ Quality tracking and JSON sidecar (v1.0)
- ✓ Slack message ingestion from curated channels (v1.5)
- ✓ HubSpot activity ingestion (v1.5)
- ✓ Google Docs ingestion (v1.5)
- ✓ Cross-source deduplication via LLM (v1.5)
- ✓ Source attribution throughout synthesis output (v1.5)
- ✓ Multi-source synthesis prompts (v1.5)
- ✓ Commitment extraction with structured deadlines (v1.5)
- ✓ Pipeline hardening and reliability (v1.5)

### Active

- [ ] Notion page/database ingestion
- [ ] Parallel ingest modules (asyncio)
- [ ] Parallel per-meeting extraction (concurrent Claude calls)
- [ ] Slack user batch resolution
- [ ] Algorithmic cross-source deduplication
- [ ] Typed config model (Pydantic validation)
- [ ] Raw data cache retention policy
- [ ] Claude API structured output migration (json_schema)

### Out of Scope

- Entity layer (partners, people, initiatives) — v2.0
- Response drafting and send queue — v3.0
- Web interface — v4.0
- Personnel evaluation or judgment — system surfaces evidence only
- Team-facing dashboards or shared views — personal tool
- Real-time / intraday processing — end-of-day batch sufficient
- Query interface / ad-hoc retrieval — v2.0+

## Context

**User:** Micah Boster, manager/executive at Bounce.AI. Uses Gmail, Slack, HubSpot, Notion, Google Calendar, Google Drive daily.

**v1.0 learnings:**
- Calendar + transcripts provide strong meeting intelligence but miss async work entirely
- Slack is highest volume, lowest average signal — channel curation is critical
- HubSpot contains structured deal/contact activity that doesn't surface in meetings
- Cross-source dedup is essential — same topic discussed in meeting, Slack, and email
- Synthesis prompts need source-specific handling (Slack thread ≠ meeting transcript)

**v1.5 learnings:**
- Multi-source synthesis works well with single-pass LLM dedup at conservative threshold
- Structured outputs (json_schema) eliminate brittle markdown parsing — migration overdue
- Sequential pipeline acceptable at current scale but parallelization needed before adding more sources
- Notion API complexity warranted deferral — no diff endpoint, breaking changes in Sept 2025

**Platform vision:** v1.5 (expanded ingest) → v1.5.1 (Notion + perf + reliability) → v2.0 (entity layer) → v3.0 (action layer) → v4.0 (web UI). See docs/multi-version-platform-vision.md.

## Constraints

- **Language**: Python for all pipeline logic
- **LLM**: Claude API (Sonnet for daily, Opus for roll-ups)
- **Personnel framing**: Evidence only, never evaluative language
- **Storage**: Flat markdown + JSON sidecar for now; DB layer deferred to v2.0
- **Privacy**: Personal use only; data passes through Anthropic API
- **Slack channels**: Discovery-based with manual curation, not all-channels
- **HubSpot scope**: Activity logs, deal changes, notes — not full CRM dump

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Python + Claude API | Migrated from plan limits; API gives reliability and headless operation | ✓ Good |
| Evidence only, never evaluations | Legal exposure, fairness, context collapse risks | ✓ Good |
| Two-stage synthesis (per-meeting → daily) | Architecturally required for source attribution | ✓ Good |
| Flat files for storage | Avoids premature architecture; revisit at v2.0 | ✓ Good |
| Slack channel discovery + curation | Auto-find active channels, user confirms/adds; avoids noise from 50+ channels | — Pending |
| HubSpot: activity-only scope | Deal changes and notes, not full CRM; keeps ingestion focused | — Pending |
| Cross-source dedup at normalization layer | One event = one item regardless of how many sources mention it | — Pending |

---
*Last updated: 2026-04-04 after milestone v1.5.1 start*
