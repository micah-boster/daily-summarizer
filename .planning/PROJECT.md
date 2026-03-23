# Work Intelligence System

## What This Is

A personal work intelligence system that ingests calendar events and meeting transcripts from Bounce.AI work to produce structured daily summaries. It answers three core synthesis questions — what happened of substance, what decisions were made, and what tasks/commitments emerged — then rolls those up into weekly, monthly, and quarterly intelligence over time. Built for Micah Boster as a personal tool with the potential to share select outputs (e.g., team roll-ups) later.

## Core Value

Every morning I open a structured daily summary of yesterday's work and find it accurate, useful, and worth 5 minutes of my time — without having produced it manually.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Semi-automated daily pipeline: script pulls calendar + transcript data, processes through Claude, outputs structured summary
- [ ] Ingest Google Calendar events (Bounce workspace) for meeting skeleton
- [ ] Ingest meeting transcripts from Gemini (Gmail/Calendar attachments)
- [ ] Ingest meeting transcripts from Gong (email delivery)
- [ ] Daily synthesis answering: What happened of substance today?
- [ ] Daily synthesis answering: What decisions were made, by whom, with what rationale?
- [ ] Daily synthesis answering: What tasks/commitments were created, completed, or deferred?
- [ ] Structured output file per day (markdown) with source attribution
- [ ] Temporal roll-ups: weekly summary from accumulated dailies
- [ ] Temporal roll-ups: monthly narrative with progress and themes
- [ ] Prompt engineering that enforces evidence-only framing (no evaluative language)
- [ ] Source linking: each summary item traces back to the specific transcript or calendar event

### Out of Scope

- Real-time / intraday processing — end-of-day batch is sufficient for v1
- Slack ingestion — defer until calendar + transcripts prove value
- HubSpot / Notion / Drive ingestion — defer to later phases
- Personnel evaluation or judgment — system surfaces evidence only, never "performed well" / "underperformed"
- Team-facing dashboards or shared views — personal tool first
- Multi-context support (Nighthawk, advisory) — Bounce only
- Query interface / ad-hoc retrieval — defer until storage model is decided
- API-based execution — run on Claude plan limits for v1

## Context

**User:** Micah Boster, manager/executive at Bounce.AI. Has direct reports, does performance reviews, manages cross-functional work. Uses Gmail, Slack, HubSpot, Notion, Google Calendar, Google Drive daily.

**Transcript sources:**
- Gemini: auto-transcriptions that arrive via Gmail or attached to Google Calendar invites
- Gong: call recordings/transcripts delivered via email
- Eventually both will consolidate in Notion, but for v1 we pull from Gmail/Calendar

**Prior thinking:** Three planning documents in `docs/` contain extensive conceptual framing, a 10-question daily synthesis framework, data source mapping, architecture options, and ~50 architecture decision questions. The 10 questions are: Task Management, Substance, Decisions, People & Team, Themes & Questions, Resonance, Commitments & Follow-ups, Risks & Flags, External Signals, Energy & Focus. V1 focuses on questions 2, 3, and 7 (Substance, Decisions, Tasks/Commitments).

**Validation approach:** Start with a semi-automated manual POC (Phase 0 from planning docs). Script pulls data + processes through Claude + outputs structured file. Micah reviews and tweaks daily. Goal: learn which data is highest-signal, refine prompts, prove the daily habit before investing in full automation.

**Confidentiality boundaries:** TBD — will be informed by the POC. Some categories (HR, legal, board) may be excluded from processing. For now, process everything since output is private.

## Constraints

- **Execution model**: Runs within Claude Code / Cowork on Claude Pro/Max plan limits — not API-based. Cannot be fully headless in v1.
- **Language**: Python for all pipeline logic
- **Personnel framing**: System must never output evaluative language about individuals. Enforced in prompt design. Surfaces timestamped evidence, quotes, and contributions only.
- **Storage**: Flat markdown files for v1. Storage architecture (Obsidian, SQLite, vector DB) to be decided after POC validates the concept.
- **Cost**: Zero incremental cost target — runs against existing Claude plan allocation.
- **Privacy**: Data passes through Anthropic's infrastructure via Claude plan usage. Acceptable for personal use. Check with Bounce legal/IT before processing team-wide data.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Python + Claude Code + Cowork | Keeps everything in Claude ecosystem, avoids API costs, Cowork handles scheduling | — Pending |
| Run on plan limits, not API | Validate value before committing to ongoing API spend. Graduating to API later is straightforward | — Pending |
| Evidence only, never evaluations | Legal exposure, fairness problems, context collapse risks with automated assessment. Human makes judgment calls | — Pending |
| Start with calendar + transcripts | Highest signal-to-noise ratio. Calendar is the skeleton, transcripts are the substance | — Pending |
| Semi-automated POC before full automation | Learn which data matters, refine prompts, prove the daily habit before investing in infrastructure | — Pending |
| Flat files for v1 storage | Avoids premature architecture decisions. Storage model informed by what queries prove useful during POC | — Pending |
| Bounce-only scope | Simplifies data governance, API access, and confidentiality boundaries | — Pending |

---
*Last updated: 2026-03-23 after initialization*
