# Phase 22: Merge + Split Review - Context

**Gathered:** 2026-04-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can consolidate fragmented entity references ("Colin" / "Colin R." / "colin@partner.com") via merge proposals and undo incorrect merges via split. Merge proposals are generated on-demand, reviewed interactively via CLI, and resolved (accept/reject) with persistent state. Split reverses a merge and re-attributes mentions to restored entities.

</domain>

<decisions>
## Implementation Decisions

### Matching strategy
- Reuse rapidfuzz from Phase 20 for name similarity scoring
- Threshold: 80+ score triggers a merge proposal
- Same entity type only (partner-to-partner, person-to-person) — no cross-type proposals
- Name similarity is the sole signal — shared context (co-occurrence in sources) is shown for review but does not affect ranking

### Review workflow
- Interactive one-by-one CLI experience via `entity review`
- Each proposal shows: both entity names, which sources mentioned each, and mention counts
- No context snippets — keep it compact
- When accepting, the most-mentioned name becomes canonical automatically
- Interactive only — no --json output mode for review
- `--limit N` CLI flag controls proposals per session (default 10)

### Merge behavior
- Merged-away entity is soft-deleted with merge_target_id set (consistent with Phase 19 patterns)
- All mentions from merged-away entity are reassigned (entity_id updated) to the surviving entity
- All aliases from merged-away entity transfer to the surviving entity
- Merged-away entity's canonical name becomes an alias on the surviving entity

### Split behavior
- `entity split` reverses a merge: restores the soft-deleted entity (clears deleted_at and merge_target_id)
- Mentions are re-attributed by matching original source name against restored entity names
- Aliases transferred during merge are moved back to the restored entity
- merge_proposals table records the merge history, which informs what to reverse

### Proposal lifecycle
- On-demand generation only via `entity review` — no background/pipeline scanning
- Rejections stored as merge_proposals rows with status='rejected' — generator filters these out
- No separate audit log — merge_proposals table + `entity split` is sufficient for reversibility

### Claude's Discretion
- Proposal ranking/ordering within a review session
- Exact CLI formatting and prompt text
- How to handle edge cases (e.g., entity already merged, circular merges)
- Whether to show a summary at end of review session

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

*Phase: 22-merge-split-review*
*Context gathered: 2026-04-08*
