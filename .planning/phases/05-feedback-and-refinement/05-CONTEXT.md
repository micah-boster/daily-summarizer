# Phase 5: Feedback and Refinement - Context

**Gathered:** 2026-04-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Pipeline improves over time through explicit priority configuration, quality tracking, and structured data output. User can configure priorities that visibly influence daily synthesis emphasis. Quality metrics are tracked via diff-based detection. A JSON sidecar file is produced alongside each daily markdown for programmatic task extraction and source metadata.

</domain>

<decisions>
## Implementation Decisions

### Priority Configuration Format
- YAML config file (e.g., `priorities.yaml`) in the project root
- Three priority buckets: projects, people, and topics — each as a simple list
- Simple on/off: if an item is listed, it's a priority. No numeric weights or tiers
- Separate `suppress` list for items to de-emphasize (noisy meetings, low-signal topics, etc.)

### Priority Influence on Synthesis
- Priority items get boosted detail and their own dedicated subsections in the daily output
- Non-priority items still appear but receive briefer treatment
- Suppressed items collapse into a one-liner summary (e.g., "Also: 3 routine standups") — not omitted entirely
- No visible markers or attribution — priorities shape the output seamlessly
- User trusts the config is working without needing "[priority]" tags

### Quality Metrics and Tracking
- Diff-based edit detection: system saves raw output, user edits file in place, next run diffs against raw to measure corrections
- File-on-disk is always the final/reviewed version — no explicit "mark as reviewed" step required
- Quality metrics surfaced in a separate rolling quality report file (not inline in daily summaries)
- Report tracks trends over time: edit frequency, section correction rates, data volume per run

### JSON Sidecar Output
- JSON file lives alongside the daily markdown: same directory, same base name with `.json` extension (e.g., `2026-04-03.json`)
- Primary downstream use case: programmatic task extraction (feeding tasks/commitments into task managers, Notion, etc.)
- Task fields: description, owner, source (which meeting/email), date captured, due date (if mentioned), status (new/in-progress/completed)
- Also includes: decisions made with source attribution

### Claude's Discretion
- Priority influence on roll-ups (weekly/monthly) — Claude determines appropriate behavior per temporal level
- Quality report metrics selection — Claude determines meaningful volume/health metrics based on pipeline architecture
- JSON sidecar contents beyond tasks and decisions — Claude determines right balance of completeness vs. noise
- Quality report format and structure

</decisions>

<specifics>
## Specific Ideas

- Priority config should feel like a simple "tell the system what matters to you" — not a complex rules engine
- Suppress list exists because some recurring meetings and topics generate noise that drowns out signal
- Diff-based quality tracking is hands-off: user just edits the output naturally, system learns from the diffs
- JSON sidecar is task-extraction-first: the shape should make it trivial to pipe tasks into downstream tools

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-feedback-and-refinement*
*Context gathered: 2026-04-03*
