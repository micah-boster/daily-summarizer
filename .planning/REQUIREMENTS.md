# Requirements: Work Intelligence Daily Summarizer

## v1 Requirements

### Data Ingestion (INGEST)

- **INGEST-01**: Semi-automated daily pipeline: script pulls calendar + transcript data, processes through Claude, outputs structured summary
- **INGEST-02**: Ingest Google Calendar events (Bounce workspace) for meeting skeleton
- **INGEST-03**: Ingest meeting transcripts from Gemini (Gmail/Calendar attachments)
- **INGEST-04**: Ingest meeting transcripts from Gong (email delivery)

### Synthesis (SYNTH)

- **SYNTH-01**: Daily synthesis answering: What happened of substance today?
- **SYNTH-02**: Daily synthesis answering: What decisions were made, by whom, with what rationale?
- **SYNTH-03**: Daily synthesis answering: What tasks/commitments were created, completed, or deferred?
- **SYNTH-04**: Prompt engineering that enforces evidence-only framing (no evaluative language)

### Output (OUT)

- **OUT-01**: Structured output file per day (markdown) with source attribution
- **OUT-02**: Source linking: each summary item traces back to the specific transcript or calendar event

### Temporal (TEMP)

- **TEMP-01**: Temporal roll-ups: weekly summary from accumulated dailies
- **TEMP-02**: Temporal roll-ups: monthly narrative with progress and themes

## v2+ (Out of Scope)

- Real-time / intraday processing
- Slack ingestion
- HubSpot / Notion / Drive ingestion
- Personnel evaluation or judgment
- Team-facing dashboards or shared views
- Multi-context support (Nighthawk, advisory)
- Query interface / ad-hoc retrieval
- API-based execution

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INGEST-01 | Phase 0 | Complete |
| INGEST-02 | Phase 1 | Pending |
| INGEST-03 | Phase 2 | Pending |
| INGEST-04 | Phase 2 | Pending |
| SYNTH-01 | Phase 3 | Pending |
| SYNTH-02 | Phase 3 | Pending |
| SYNTH-03 | Phase 3 | Pending |
| SYNTH-04 | Phase 3 | Pending |
| OUT-01 | Phase 1 | Pending |
| OUT-02 | Phase 3 | Pending |
| TEMP-01 | Phase 4 | Pending |
| TEMP-02 | Phase 4 | Pending |

---
*Created: 2026-04-02*
