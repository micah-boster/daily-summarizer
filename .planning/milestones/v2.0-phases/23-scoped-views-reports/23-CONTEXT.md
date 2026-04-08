# Phase 23: Scoped Views + Reports - Context

**Gathered:** 2026-04-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can ask "what's happening with Affirm?" or "what does Colin owe me?" and get a sourced, time-filtered answer. Three CLI commands: `entity show` (terminal view), `entity report` (markdown file), and an enriched `entity list` with mention frequency and open commitments. This is the payoff of the entire entity layer.

</domain>

<decisions>
## Implementation Decisions

### View content & depth (`entity show`)
- Each item shows: date + section type (substance/decision/commitment) + text + source attribution
- Items grouped by date (date headers, items listed under each)
- Default time range: last 30 days. Override with --from/--to or --all
- Open commitments shown in a separate highlighted section at the top, before the chronological activity view

### Report structure (`entity report`)
- Three sections: 1) Entity summary (type, aliases, mention count), 2) Open commitments, 3) Activity by date
- Generated using Jinja2 templates (in templates/ dir, customizable)
- Default time range: last 30 days (consistent with `entity show`). Override with --from/--to
- Single entity per invocation only — no --all batch mode
- Output to `output/entities/` as markdown file

### Entity list enrichment (`entity list`)
- Enhanced columns: mention frequency (all-time), open commitments count, last-active date
- Default sort: last-active date descending (most recently mentioned first)
- --sort flag supports: `active` (default), `mentions`, `name`
- --json flag supported (consistent with Phase 19 pattern)
- --type filter still works as before

### Temporal summary logic
- Significance weighting: Decisions + Commitments rank higher than Substance items
- Rule-based extraction (no Claude API call) — deterministic, fast, no cost
- Top 5 most significant items shown as a highlights section
- Highlights appear in BOTH `entity show` (terminal) and `entity report` (markdown file)
- Full chronological activity follows below the highlights

### Claude's Discretion
- Exact significance scoring algorithm (how to weight decisions vs commitments vs recency)
- Terminal formatting (colors, spacing, table widths)
- Jinja2 template design for the markdown report
- How to handle entities with zero mentions in the time range
- Edge case handling (deleted entities, merged entities in views)

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

*Phase: 23-scoped-views-reports*
*Context gathered: 2026-04-08*
