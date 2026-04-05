# Requirements: Work Intelligence System

**Defined:** 2026-04-03
**Core Value:** Every morning I open a structured daily summary of yesterday's work and find it accurate, useful, and worth 5 minutes of my time — without having produced it manually.

## v1.0 Requirements (Complete)

### Data Ingestion (INGEST)

- ✓ **INGEST-01**: Semi-automated daily pipeline: script pulls calendar + transcript data, processes through Claude, outputs structured summary
- ✓ **INGEST-02**: Ingest Google Calendar events (Bounce workspace) for meeting skeleton
- ✓ **INGEST-03**: Ingest meeting transcripts from Gemini (Gmail/Calendar attachments)
- ✓ **INGEST-04**: Ingest meeting transcripts from Gong (email delivery)

### Synthesis (SYNTH)

- ✓ **SYNTH-01**: Daily synthesis answering: What happened of substance today?
- ✓ **SYNTH-02**: Daily synthesis answering: What decisions were made, by whom, with what rationale?
- ✓ **SYNTH-03**: Daily synthesis answering: What tasks/commitments were created, completed, or deferred?
- ✓ **SYNTH-04**: Prompt engineering that enforces evidence-only framing (no evaluative language)

### Output (OUT)

- ✓ **OUT-01**: Structured output file per day (markdown) with source attribution
- ✓ **OUT-02**: Source linking: each summary item traces back to the specific transcript or calendar event

### Temporal (TEMP)

- ✓ **TEMP-01**: Temporal roll-ups: weekly summary from accumulated dailies
- ✓ **TEMP-02**: Temporal roll-ups: monthly narrative with progress and themes

## v1.5 Requirements

### Data Model (MODEL)

- [x] **MODEL-01**: New `SourceItem` Pydantic model for non-meeting sources (Slack messages, HubSpot activities, Doc edits) parallel to existing `NormalizedEvent`
- [x] **MODEL-02**: Commitment data structure captures who, what, by-when with source attribution

### Slack Ingestion (SLACK)

- [x] **SLACK-01**: Ingest messages from a curated list of Slack channels (user-configurable)
- [x] **SLACK-02**: Expand active threads (replies) for discussions above a configurable threshold
- [x] **SLACK-03**: Ingest direct messages (DMs and group DMs)
- [x] **SLACK-04**: Discovery mode proposes active channels based on user's history; user confirms/rejects

### HubSpot Ingestion (HUBSPOT)

- [x] **HUBSPOT-01**: Ingest deal stage changes and deal activity for the target date
- [x] **HUBSPOT-02**: Ingest contact activity and notes
- [x] **HUBSPOT-03**: Ingest tickets, calls, emails, meetings, and task activity

### Google Docs Ingestion (DOCS)

- [x] **DOCS-01**: Ingest list of documents the user edited on the target date with title and content extract
- [x] **DOCS-02**: Ingest comments and suggestions on docs the user owns or is mentioned in

### Synthesis Updates (SYNTH)

- [x] **SYNTH-05**: Source-aware synthesis prompts handle Slack, HubSpot, and Docs input alongside meetings
- [x] **SYNTH-06**: Cross-source deduplication handled at synthesis time via LLM (same topic across sources = one consolidated item)
- [x] **SYNTH-07**: Source attribution in all output ("per Slack #channel", "per HubSpot deal", "per Google Doc")
- [x] **SYNTH-08**: Commitment deadlines extracted and structured (who/what/by-when) in synthesis output and JSON sidecar

## v1.5.1 Requirements

### Foundation (CONFIG)

- [ ] **CONFIG-01**: Typed config model (Pydantic validation on config.yaml load) with backward-compatible defaults for all existing optional sections

### Structured Outputs (STRUCT)

- [ ] **STRUCT-01**: All Claude API call sites migrated from markdown response parsing to structured outputs (json_schema) with Pydantic model validation

### Notion Ingestion (NOTION)

- [ ] **NOTION-01**: Ingest Notion page updates and database changes for the target date, with content extraction and SourceItem conversion

### Performance (PERF)

- [ ] **PERF-01**: Parallel ingest modules via asyncio (independent sources run concurrently, sequential dependencies preserved)
- [ ] **PERF-02**: Parallel per-meeting transcript extraction (concurrent Claude API calls with rate-limit-aware semaphore)
- [ ] **PERF-03**: Slack user batch resolution (users_list instead of N individual users_info calls)

### Intelligence (DEDUP)

- [ ] **DEDUP-01**: Algorithmic cross-source deduplication as conservative pre-filter to supplement LLM-based dedup

### Operations (OPS)

- [ ] **OPS-01**: Raw data cache retention policy (auto-delete after configurable TTL)

## v2+ Requirements (Future)

- Entity layer (partners, people, initiatives) with discovery and attribution
- Commitment reminders and deadline alerts
- Response drafting and send queue
- Web interface
- Personnel evidence collection (not evaluation)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Entity layer | v2.0 — requires attributed data from v1.5 first |
| Commitment reminders/alerts | v2.0 — v1.5 extracts and structures only |
| Response drafting | v3.0 scope |
| Web interface | v4.0 scope |
| Personnel evaluation | Never — system surfaces evidence only |
| Real-time processing | End-of-day batch sufficient |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| MODEL-01 | Phase 6 | Complete |
| MODEL-02 | Phase 6 | Complete |
| SLACK-01 | Phase 7 | Complete |
| SLACK-02 | Phase 7 | Complete |
| SLACK-03 | Phase 7 | Complete |
| SLACK-04 | Phase 7 | Complete |
| SYNTH-05 | Phase 7 | Complete |
| SYNTH-07 | Phase 7 | Complete |
| HUBSPOT-01 | Phase 8 | Complete |
| HUBSPOT-02 | Phase 8 | Complete |
| HUBSPOT-03 | Phase 8 | Complete |
| DOCS-01 | Phase 9 | Complete |
| DOCS-02 | Phase 9 | Complete |
| SYNTH-06 | Phase 10 | Complete |
| SYNTH-08 | Phase 10 | Complete |
| CONFIG-01 | Phase 13 | Pending |
| STRUCT-01 | Phase 14 | Pending |
| NOTION-01 | Phase 15 | Pending |
| PERF-03 | Phase 16 | Pending |
| OPS-01 | Phase 16 | Pending |
| DEDUP-01 | Phase 16 | Pending |
| PERF-01 | Phase 17 | Pending |
| PERF-02 | Phase 17 | Pending |

**Coverage:**
- v1.5 requirements: 15 total, 15 mapped, 0 unmapped
- v1.5.1 requirements: 8 total, 8 mapped, 0 unmapped

---
*Requirements defined: 2026-04-03*
*Last updated: 2026-04-04 after v1.5.1 roadmap creation*
