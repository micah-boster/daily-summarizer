# Work Intelligence System

## What This Is

A personal work intelligence system that ingests data from multiple work sources (calendar, transcripts, Slack, HubSpot, Google Docs, Notion) to produce structured daily summaries answering what happened of substance, what decisions were made, and what tasks/commitments emerged. Rolls up into weekly, monthly, and quarterly intelligence. Built for Micah Boster as a personal tool evolving toward an entity-aware platform with action capabilities and a web interface.

## Core Value

Every morning I open a structured daily summary of yesterday's work and find it accurate, useful, and worth 5 minutes of my time — without having produced it manually.

## Current Milestone: v1.5 Expanded Ingest

**Goal:** Broaden the data surface beyond calendar and transcripts so synthesis sees the full picture of work activity.

**Target features:**
- Slack message ingestion from curated channel list (discovery-based selection)
- HubSpot activity ingestion (deal changes, contact notes, tasks)
- Google Docs ingestion (documents created/edited that day)
- Notion ingestion (page updates, database changes)
- Cross-source normalization and deduplication
- Source attribution in synthesis ("per Slack #channel", "per HubSpot deal")
- Updated synthesis prompts for multi-source input

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

### Active

- [ ] Slack message ingestion from curated channels
- [ ] HubSpot activity ingestion (deals, contacts, tasks)
- [ ] Google Docs ingestion (created/edited documents)
- [ ] Notion ingestion (page updates, database changes)
- [ ] Cross-source deduplication (same event across multiple sources = one item)
- [ ] Source attribution throughout synthesis output
- [ ] Updated synthesis prompts for multi-source context

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

**Platform vision:** v1.5 (expanded ingest) → v2.0 (entity layer) → v3.0 (action layer) → v4.0 (web UI). See docs/multi-version-platform-vision.md.

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
*Last updated: 2026-04-03 after milestone v1.5 start*
