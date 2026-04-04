# Phase 10: Cross-Source Synthesis + Commitments - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Multi-source output is deduplicated and commitments are extracted with structured deadlines across all sources. When the same topic appears in multiple sources (meetings, Slack, Google Docs, HubSpot), the daily summary consolidates it into one item with all sources attributed. Commitments with deadlines are extracted as structured who/what/by-when entries in both markdown output and JSON sidecar.

</domain>

<decisions>
## Implementation Decisions

### Deduplication behavior
- Conservative merging only — merge when clearly the same topic (same project, same people, same decision). Err on showing two items rather than losing detail
- When sources have conflicting details (e.g., different dates), show both with inline attribution — let the reader resolve
- Narrative merge style — one coherent paragraph/bullet weaving both sources together with inline attribution like "(per standup)" and "(per Slack #channel)"
- Dedup logic integrated into the synthesis prompt itself (one LLM pass), not a separate post-synthesis dedup step

### Commitment extraction
- Explicit commitments only — someone clearly says they'll do something ("I'll send the deck by Friday", "John will follow up"). No implied obligations
- Extract everyone's commitments, not just the user's — full picture of what was promised across all participants
- Normalize vague deadlines to actual dates where possible: "next week" → date range, "by end of day" → specific date. Leave truly vague ones ("soon") as text
- Deduplicate commitments across sources — same commitment discussed in meeting AND Slack appears once with multi-source attribution

### Output structure — Commitments section
- Dedicated "## Commitments" section at the TOP of the daily summary, before detailed activity sections — high visibility
- Table format with columns: Who | What | By When | Source
- Inline parenthetical attribution for consolidated activity items: "...project timeline updated (per standup, per Slack #proj-alpha)"

### Output structure — JSON sidecar
- Commitments array with core fields only: `who`, `what`, `by_when` (ISO date string or text like "unspecified"), `source` (array of attribution strings)
- Final output only in sidecar — no merge lineage or consolidated_topics tracking

### Edge cases
- Low-confidence dedup matches: keep items separate. Better to have a slight repeat than merge incorrectly
- Partial commitments: include with gaps marked — who = "TBD" or by_when = "unspecified". Better to surface incomplete commitments than miss them
- Single-source days: always run the full pipeline regardless of source count. Commitments still extracted, consistent output format
- Pipeline runs the same synthesis prompt whether 1 source or 5

### Claude's Discretion
- Exact prompt engineering for dedup instructions within the synthesis prompt
- Confidence threshold tuning for what constitutes "clearly the same topic"
- Table formatting details (column widths, date formatting in table)
- How to handle commitments that reference future dates beyond the current day

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 10-cross-source-synthesis-commitments*
*Context gathered: 2026-04-04*
