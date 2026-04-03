# Phase 4: Temporal Roll-Ups - Context

**Gathered:** 2026-04-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Synthesize accumulated daily summaries into weekly thread-based summaries and monthly thematic narratives. Weekly roll-ups trace threads across days (not concatenate). Monthly roll-ups surface strategic patterns and emerging themes. Both are new output types alongside existing dailies.

</domain>

<decisions>
## Implementation Decisions

### Thread Detection
- LLM-based semantic linking — Claude reads all dailies for a period and identifies connections across days
- Source material: synthesis sections only (executive summary, substance, decisions, commitments) — not per-meeting extractions
- Threads show timeline narrative progression: "Mon: raised concern → Wed: explored options → Thu: locked in decision"
- Threads ranked by significance, not frequency — a one-time board decision outranks a recurring standup topic
- Categories (decisions, commitments, substance) become tags on threads, not organizing sections

### Weekly Structure
- 1-2 page executive brief — scannable in 3-5 minutes
- Top threads get narrative treatment; single-day items elevated by significance, not just filtered out
- Significance-based prioritization: important single-day items are elevated alongside multi-day threads
- Open commitments and unresolved questions carry forward in a "Still open" section with status tracking
- Standalone file: `output/weekly/YYYY/YYYY-WXX.md`
- Daily files get backlinks to their parent weekly once generated

### Monthly Narrative
- Focus on strategic patterns: emerging themes, time allocation shifts, priority arcs over 4 weeks
- Analytical briefing tone (third-person): "Three themes dominated April: hiring pipeline acceleration, Q2 planning, and partner onboarding"
- Light metrics section: total meetings, hours, top recurring attendees, decision count — context for narrative, not a dashboard
- 2-3 pages, ~10 minute read
- Standalone file: `output/monthly/YYYY/YYYY-MM.md`

### Scheduling & Triggers
- Weekly generated Friday evening — captures full work week, ready for Monday review
- Monthly generated 1st business day of next month — captures full month
- Always generate weekly even on partial weeks (2-3 dailies) — note if partial, maintain cadence
- CLI triggerable on-demand: `python -m work_intel weekly --date YYYY-MM-DD` and `python -m work_intel monthly --date YYYY-MM`
- Both automatic scheduling (via Cowork) and manual CLI supported

### Claude's Discretion
- Exact LLM prompt design for thread detection
- Weekly/monthly Jinja2 template layout and formatting
- How backlinks are inserted into daily files
- Thread significance scoring algorithm
- Partial week annotation format

</decisions>

<specifics>
## Specific Ideas

- Weekly should feel like a Monday morning briefing — what happened last week that matters going into this week
- Monthly should surface patterns you wouldn't notice day-to-day: "You spent 40% of meeting time on hiring this month"
- Threads should read as mini-stories with an arc, not disconnected bullet points across days
- Success criteria emphasizes "threads, not concatenation" — the LLM must genuinely trace connections

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-temporal-roll-ups*
*Context gathered: 2026-04-03*
