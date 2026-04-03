---
phase: 02-transcript-ingestion-and-normalization
plan: 03
subsystem: ingest, normalization, pipeline
tags: [transcript-matching, deduplication, pipeline-wiring, normalization]

requires:
  - phase: 02-transcript-ingestion-and-normalization
    provides: Gmail utilities, Gemini parser, Gong parser, fetch_all_transcripts
  - phase: 01-foundation-and-calendar-ingestion
    provides: Calendar ingestion, NormalizedEvent models, DailySynthesis, output writer
provides:
  - Transcript-to-calendar matching using time window + title similarity
  - Event deduplication across overlapping calendar sources
  - End-to-end pipeline: calendar + transcripts -> normalized -> rendered -> markdown
  - Unmatched transcript surfacing in DailySynthesis model
affects: [03-synthesis, 04-rollups]

tech-stack:
  added: []
  patterns: [difflib-sequence-matcher, time-window-matching, data-richness-scoring, graceful-fallback]

key-files:
  created:
    - src/ingest/normalizer.py
    - tests/test_normalizer.py
  modified:
    - src/main.py
    - src/models/events.py

key-decisions:
  - "Gemini takes priority over Gong when both match same event (per user decision)"
  - "Dedup key is (title.lower + start_time) for timed events, (title.lower + date) for all-day"
  - "Data richness scoring for dedup: transcript > attendees > description > meeting_link"
  - "Pipeline wraps transcript ingestion in try/except for graceful calendar-only fallback"
  - "unmatched_transcripts field added to DailySynthesis model for orphan visibility"

patterns-established:
  - "Time-window + title similarity matching with configurable window"
  - "Timezone normalization before datetime comparison (naive -> aware)"
  - "Graceful degradation: transcript failure doesn't block calendar output"
  - "transcript_count computed from events with attached transcripts"

requirements-completed: [INGEST-03, INGEST-04]

duration: 5min
completed: 2026-04-03
---

# Phase 02 Plan 03: Normalization Pipeline and Pipeline Wiring Summary

**Transcript-calendar linking using time window + title similarity, event deduplication, and end-to-end pipeline producing daily summaries with integrated transcript data**

## Performance

- **Duration:** 5 min
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Normalizer module with transcript-to-event matching (30-min configurable window + SequenceMatcher title similarity)
- Gemini priority enforcement: Gemini transcripts always win over Gong for same event
- Event deduplication merging duplicates from overlapping calendars (keeps richer data)
- Unmatched transcripts surfaced via DailySynthesis.unmatched_transcripts (not silently dropped)
- Pipeline wiring in main.py: calendar_service + gmail_service -> fetch + normalize -> render -> write
- Graceful fallback to calendar-only output when Gmail/transcript ingestion fails
- Raw transcript email caching alongside calendar data
- 9 normalizer tests passing including full integration test
- Full test suite: 60 tests passing across all modules
