# Phase 3: Two-Stage Synthesis Pipeline - Context

**Gathered:** 2026-04-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver the core daily intelligence brief via a two-stage pipeline: (1) per-meeting extraction from transcripts, (2) daily cross-meeting synthesis answering the three core questions (substance, decisions, commitments) with source attribution and no evaluative language. Calendar events without transcripts are acknowledged. The output is a single daily markdown file with synthesis sections and a per-meeting appendix.

</domain>

<decisions>
## Implementation Decisions

### Extraction depth
- Extract five categories per meeting: decisions, tasks/commitments, substance, open questions, and tensions/disagreements
- Signal-filtered granularity: capture items that would matter if missed, skip trivial scheduling decisions and low-signal chatter ("let's sync on Slack later")
- Rationale preservation depth is Claude's discretion — adapt based on how much reasoning was actually stated in the meeting

### Brief structure and voice
- Daily synthesis organized by question: three sections — Substance, Decisions, Commitments
- Structured multi-line bullets within each section: item, who, rationale/context, source
- Executive summary (3-5 sentences) auto-included only on busy days with 5+ meetings that have transcripts; omitted on lighter days
- Neutral reporter tone: "Team decided X. Rationale: Y. Owner: Z." — facts only, no editorializing or implications

### Source citation style
- Inline parenthetical attribution on every item: "(Meeting Title — Key Participants)"
- Citation includes meeting title and key participants involved in that specific item
- When an item pulls from multiple meetings, list all sources: "(Exec Sync — Sarah; Product Review — Mike)"
- Per-meeting appendix includes relative file path links to cached raw transcripts in `output/raw/`

### Meeting type handling
- 1:1s vs. group meetings: Claude adapts extraction depth based on transcript content, not meeting type
- Meetings without transcripts: listed in a separate "Meetings without transcripts" section showing title, time, attendees, duration
- Short meetings (under 10 min): full extraction treatment regardless of duration — even quick syncs can produce key decisions
- Recurring meeting handling: Claude's discretion (may become more relevant in Phase 4 temporal roll-ups)

### Claude's Discretion
- Rationale preservation depth per decision (one-line vs. full reasoning chain)
- Adapting extraction structure for 1:1s vs. group meetings based on content
- Whether to flag recurrence patterns in extraction metadata
- Loading skeleton / empty state handling for days with no meetings
- Exact prompt engineering approach for evidence-only enforcement

</decisions>

<specifics>
## Specific Ideas

- Per-meeting extractions should be visible as an appendix in the daily output — synthesis up top, per-meeting detail below for drill-down
- The three core questions from requirements must map directly to the three synthesis sections — no renaming or reframing
- Raw transcript links in the appendix enable full audit trail from synthesis → extraction → raw transcript

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-two-stage-synthesis-pipeline*
*Context gathered: 2026-04-03*
