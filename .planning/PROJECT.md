# Work Intelligence System

## What This Is

A personal work intelligence system that ingests data from multiple work sources (calendar, transcripts, Slack, HubSpot, Google Docs, Notion) to produce structured daily summaries answering what happened of substance, what decisions were made, and what tasks/commitments emerged. Rolls up into weekly, monthly, and quarterly intelligence. Built for Micah Boster as a personal tool evolving toward an entity-aware platform with action capabilities and a web interface.

## Core Value

Every morning I open a structured daily summary of yesterday's work and find it accurate, useful, and worth 5 minutes of my time — without having produced it manually.

## Current Milestone: v3.0 Web Interface

**Goal:** A polished, demo-quality web UI that replaces the CLI as the daily interface — browse summaries, manage entities, configure the pipeline, and trigger runs from the browser.

**Target features:**
- Three-column layout: entity/people nav (left), content panel (center), context-aware sidebar (right)
- Daily summary as default center view, entity scoped views on selection
- Activity highlights in nav showing which entities/sections had recent activity
- Context panel adapts per selection: related items, source evidence, timeline
- Entity CRUD: create, edit, merge, delete, confirm merge proposals, manage aliases
- Pipeline config management: source settings, channel curation, priorities
- Pipeline run triggers: manual runs, run history, schedule management
- FastAPI backend exposing existing Python pipeline/entity data as JSON API
- Next.js (React) frontend, localhost-first, hostable later

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
- ✓ Typed config model with Pydantic validation (v1.5.1)
- ✓ Claude API structured output migration (v1.5.1)
- ✓ Notion page/database ingestion (v1.5.1)
- ✓ Slack user batch resolution (v1.5.1)
- ✓ Algorithmic cross-source deduplication (v1.5.1)
- ✓ Raw data cache retention policy (v1.5.1)
- ✓ Async pipeline parallelization (v1.5.1)
- ✓ Entity registry in SQLite — partners, people, initiatives (v2.0)
- ✓ Semi-automated entity discovery from historical summaries (v2.0)
- ✓ Ongoing entity discovery from new pipeline runs (v2.0)
- ✓ Entity attribution during synthesis (v2.0)
- ✓ Entity merge proposals with user confirmation (v2.0)
- ✓ Scoped entity views — CLI and markdown reports (v2.0)

### Active

- [ ] FastAPI backend — JSON API exposing pipeline data, entities, config
- [ ] Next.js frontend — three-column layout, responsive, keyboard-navigable
- [ ] Daily summary view — default center panel, temporal navigation
- [ ] Entity browser — scoped views for partners, people, initiatives
- [ ] Context sidebar — related items, source evidence, timeline (adapts to selection)
- [ ] Activity highlights — nav indicators for recent entity/section activity
- [ ] Entity management UI — CRUD, merge proposals, alias management
- [ ] Config management UI — source settings, channels, priorities
- [ ] Pipeline run management — trigger runs, view history, schedule

### Out of Scope

- Response drafting and send queue — v4.0
- Multi-user / team distribution — v5.0+
- Personnel evaluation or judgment — system surfaces evidence only
- Team-facing dashboards or shared views — personal tool
- Real-time / intraday processing — end-of-day batch sufficient
- Knowledge graph / relationship mapping — over-engineered; relationships implicit via co-mentions
- Entity sentiment tracking — violates evidence-only constraint
- Auto-merge without confirmation — false merges are catastrophic

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

**v1.5.1 learnings:**
- httpx works well for Notion API — no need for official SDK
- Pydantic structured outputs are clean; entity attribution can extend existing models
- Async parallelization stable — entity discovery backfill can leverage async patterns
- SQLite will be first non-flat-file storage in the project

**v2.0 learnings:**
- SQLite entity registry works well — single file, no server, fast reads
- Entity discovery prompt needs real-summary validation; backfill with weekly batching + checkpoints is resilient
- HubSpot cross-reference enriches partner entities significantly (fuzzy match threshold 0.80)
- Merge proposals need zero auto-merge on fuzzy signals — false merges are catastrophic
- Entity-attributed synthesis adds real value to scoped views

**Platform vision:** v3.0 (web UI) → v4.0 (action layer) → v5.0 (team distribution). See docs/multi-version-platform-vision.md.

## Constraints

- **Language**: Python for all pipeline logic
- **LLM**: Claude API (Sonnet for daily, Opus for roll-ups)
- **Personnel framing**: Evidence only, never evaluative language
- **Storage**: Flat markdown + JSON sidecar + SQLite entity registry
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
| Slack channel discovery + curation | Auto-find active channels, user confirms/adds; avoids noise from 50+ channels | ✓ Good |
| HubSpot: activity-only scope | Deal changes and notes, not full CRM; keeps ingestion focused | ✓ Good |
| Cross-source dedup at normalization layer | One event = one item regardless of how many sources mention it | ✓ Good |
| httpx for Notion API (no SDK) | Pinned to Notion-Version 2022-06-28; avoids breaking changes | ✓ Good |
| Pydantic for config + Claude outputs | Reuse same model layer for validation and structured outputs | ✓ Good |
| Conservative dedup threshold (0.85) | Logs near-matches for threshold tuning; avoids false merges | ✓ Good |
| Async pipeline with sync entry point | `run_pipeline()` stays sync; `asyncio.run()` wraps internal async | ✓ Good |
| Decimal phase numbering for gap closure | Phase 18.1 inserted without renumbering — clear audit trail | ✓ Good |

---
*Last updated: 2026-04-08 after v3.0 milestone start*
