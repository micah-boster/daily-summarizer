# Phase 1: Foundation and Calendar Ingestion - Context

**Gathered:** 2026-04-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Establish the data models, markdown output writer, and Google Calendar ingestion so the pipeline skeleton is testable end-to-end with real calendar data. Covers INGEST-02 (calendar events) and OUT-01 (structured daily markdown). No transcripts, no synthesis, no roll-ups — just calendar data flowing through models into a readable daily file.

</domain>

<decisions>
## Implementation Decisions

### Output Structure
- Full detail per event: title, time, duration, all attendees, meeting link, description snippet
- Narrative block format — short prose paragraph per event (not bullets or tables)
- Neutral log tone — third-person factual ("Meeting with Sarah Chen, 2:00-2:30pm. Discussed Q3 planning.")
- Summary header at top of daily file: meeting count, total meeting hours, transcript count (0 in Phase 1)
- Include calendar event description/agenda body when present — richer context per event
- Full skeleton with stub sections for future phases (Decisions, Commitments, Substance) — consistent structure from day one
- Raw API response cached to `output/raw/` alongside the daily markdown

### Calendar Filtering
- Include declined meetings in a separate section — useful to see what was skipped
- Include cancelled events in a separate section — useful to see what dropped off
- Include all-day events in their own section at the top — they set day context
- Include all events regardless of attendee role (organizer, required, optional, FYI)
- Tag recurring events — annotate to distinguish routine from one-off meetings
- Include Focus Time and OOO blocks — they're part of the day's structure
- Configurable calendar ID list in config file — not just primary calendar
- Configurable title-pattern exclusion list (default: empty, include everything)

### Pipeline Invocation
- Date range support built in: `--from` and `--to` flags for backfill
- Overwrite existing output on re-run — latest run wins, no force flag needed
- Configuration via YAML config file with environment variable overrides
- CLI design (defaults, flag names, module entrypoint): Claude's discretion

### Data Model
- Full attendee detail: name, email, response status (accepted/declined/tentative)
- Transcript fields (transcript_text, transcript_source) included now as Optional/None — populated in Phase 2
- Hierarchical DailySynthesis model: nested Section objects (calendar_events, substance, decisions, commitments)
- JSON-serializable from day one via Pydantic `.model_dump_json()` — Phase 5 sidecar is trivial later

### Claude's Discretion
- Organization of events within the daily markdown (chronological vs grouped — Claude picks)
- CLI design: module entrypoint, flag names, defaults-to-today behavior
- Exact section ordering within the daily markdown template
- Error handling and logging approach
- Naming conventions for raw cache files

</decisions>

<specifics>
## Specific Ideas

- Output should be scannable in under 2 minutes per the success criteria — narrative blocks keep it readable without being verbose
- Calendar-only days (Phase 1) will have less content, but the full skeleton means the file format is stable from the start
- The configurable calendar ID list and exclusion patterns give flexibility without overengineering — empty defaults mean everything works out of the box

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-foundation-and-calendar-ingestion*
*Context gathered: 2026-04-03*
