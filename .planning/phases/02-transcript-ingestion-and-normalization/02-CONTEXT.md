# Phase 2: Transcript Ingestion and Normalization - Context

**Gathered:** 2026-04-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Ingest meeting transcripts from Gemini (via Gmail) and Gong (via email summaries), link them to calendar events from Phase 1, filter noise, deduplicate overlapping sources, and cache raw data for debugging. Synthesis and interpretation are Phase 3.

</domain>

<decisions>
## Implementation Decisions

### Transcript Discovery
- Gemini transcripts arrive as Gmail emails (not calendar attachments)
- Gong transcripts arrive as emails containing a summary plus a link back to Gong
- For Gong: use the email summary content for now; full Gong transcript pull is a future enhancement
- Email identification patterns (sender addresses, subject line formats) for both sources: Claude to investigate actual patterns during research

### Calendar-Transcript Linking
- Unmatched transcripts (no calendar event): include as standalone entries in the normalized output, not dropped
- When both Gemini and Gong produce transcripts for the same meeting: Gemini is the primary source
- Time-window and matching strategy for linking: Claude's discretion during implementation
- When multiple calendar events overlap and a transcript arrives: pick the single best-matching event (title + time + attendees), no confidence scoring

### Noise Filtering
- Include all meetings regardless of duration (even very short ones may contain decisions)
- Exclude personal calendar blocks (focus time, lunch, commute, OOO) from ingestion
- Strip filler text (ums, ahs, repeated phrases) at ingestion time before passing to synthesis — reduces token cost
- Calendar events with no transcript: configurable toggle for whether they appear in normalized output (default behavior at Claude's discretion)

### Unmatched Handling
- Orphan transcript presentation strategy (separate section vs inline): Claude's discretion based on what serves synthesis best
- Best-match-only linking — no confidence scores or ranked candidates

### Claude's Discretion
- Email sender/subject identification patterns for Gemini and Gong emails
- Time window for transcript-to-calendar matching
- Raw cache strategy (full email vs extracted content only)
- Orphan transcript display approach
- Pipeline logging verbosity and summary stats
- Default for transcript-less event visibility toggle

</decisions>

<specifics>
## Specific Ideas

- Gong full transcript integration is explicitly deferred — email summary is the v1 approach
- Personal blocks should be excluded at ingestion, not just hidden — don't waste processing on them
- Filler stripping happens at ingestion time as a preprocessing step, not deferred to LLM

</specifics>

<deferred>
## Deferred Ideas

- Full Gong transcript pull via API or link scraping — future enhancement beyond email summary
- Confidence scoring for transcript-calendar matches — v1 uses best-match-only

</deferred>

---

*Phase: 02-transcript-ingestion-and-normalization*
*Context gathered: 2026-04-03*
