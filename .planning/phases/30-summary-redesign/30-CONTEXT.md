# Phase 30: Summary Redesign - Context

**Gathered:** 2026-04-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Transform the center column from a raw markdown dump into a structured, scannable daily intelligence view. Executive brief at top with key decisions and actions, collapsible per-meeting sections below, and integrated Slack content. The pipeline extraction and synthesis stages must output structured JSON to support the new UI. Busy days (10+ meetings) must be usable, not overwhelming.

</domain>

<decisions>
## Implementation Decisions

### Executive brief
- Content: key decisions + action items (not narrative). Decisions tagged as Decision, actions tagged as Action — visually distinct (e.g., colored pills/icons).
- Size: 5-8 items max. Forces prioritization on busy days.
- Each item links to the meeting section it came from — clicking scrolls and expands that section.
- Slack decisions/actions also appear in the brief alongside meeting ones.
- Pipeline generates the brief (Claude cross-meeting synthesis), not computed client-side.

### Per-meeting section design
- Collapsed card shows: meeting title + colored tag pills (e.g., "2 decisions, 1 action") indicating what's inside.
- Chronological ordering.
- All collapsed by default — user clicks to expand.
- Expanded section contains structured sub-sections: summary, decisions, actions, context. Not raw notes.

### Synthesis prompt changes
- Pipeline outputs structured JSON sidecar alongside markdown (backward compatible).
- Per-meeting extraction becomes structured: each meeting outputs summary, decisions[], actions[], context, attendees — not free-form prose.
- Daily synthesis generates the executive brief as a cross-meeting product (Claude sees all meetings, identifies themes, prioritizes).
- All existing days will be re-run with the new synthesis when backfilling March 1–today.

### Slack integration
- Slack threads that relate to a meeting topic merge into that meeting's section, with channel attribution badge (e.g., "Also in #bounce-leadership").
- Unmatched Slack threads get their own collapsible section: "Async Discussions" at the bottom.
- Slack cards use a lighter format than meetings: summary + key points (no formal decisions/actions/context structure).
- Slack decisions/actions still bubble up to the executive brief.

### Claude's Discretion
- Exact JSON schema for the structured sidecar
- How to match Slack threads to meetings (topic similarity, time window, entity overlap)
- Tag pill colors and icons for decisions vs actions vs info
- Scroll/expand animation behavior
- How to handle days with no meetings (Slack-only days)

</decisions>

<specifics>
## Specific Ideas

- "On busy days (like March 18th) the system is almost impossible to use — it feels like a terrible info dump that isn't organized or easy to process"
- The morning use case: open the summary, scan the brief to see what matters, expand 2-3 meetings that need attention, ignore the rest
- Tags on collapsed cards serve as a triage mechanism — "2 decisions" means I need to look, "info only" means I can skip
- Brief items linking to their source meeting is the key navigation pattern — click a decision, see the full context

</specifics>

<deferred>
## Deferred Ideas

- Backfill March 1–today — separate execution step after this phase is built
- Weekly/monthly roll-ups may need similar structured treatment — future phase

</deferred>

---

*Phase: 30-summary-redesign*
*Context gathered: 2026-04-10*
