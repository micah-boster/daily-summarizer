# Phase 20: Entity Discovery + Backfill - Context

**Gathered:** 2026-04-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Populate the entity registry from 6+ months of historical summaries and wire ongoing discovery into the daily pipeline as a post-synthesis step. Cross-reference discovered entities with HubSpot contacts and deals for enrichment. Entity attribution (tagging synthesis items with entity refs) is Phase 21; merge/split review is Phase 22.

</domain>

<decisions>
## Implementation Decisions

### Entity extraction approach
- Extend existing SynthesisItem/CommitmentRow Pydantic models with optional `entity_names` field
- LLM extracts entities as part of synthesis, tagging each as 'partner' or 'person'
- Entities above a confidence threshold are auto-registered in the registry; low-confidence entities are flagged for review
- If entity extraction fails (LLM error, bad parse), skip silently and log a warning — daily summary generates normally with empty entity fields

### Backfill behavior
- Progress bar with counts: "Processing 2025-10-01 to 2026-04-05... [###---] 120/180 days, 47 entities found"
- Track which days have been processed; skip already-scanned days on re-run. `--force` flag to override and re-scan
- Use LLM extraction on historical summaries (send synthesis text through entity extraction prompt) — richer results than just parsing sidecar fields
- Process in weekly batches (7 days at a time) with checkpoint/resume capability — if interrupted, resume from last completed batch

### HubSpot cross-referencing
- Exact name match first, then fuzzy fallback (e.g., 'Affirm Inc' → 'Affirm'). Store match confidence.
- Store HubSpot contact/deal ID, email (if contact), and deal stage (if deal) — enough to link back without duplicating HubSpot
- Cross-reference on both backfill and daily pipeline runs
- If HubSpot API is unavailable or rate-limited, skip enrichment and flag entity as 'pending_enrichment' for later retry

### Name normalization
- Strip common US company suffixes: Inc, LLC, Corp, Ltd, Co, LP, Partners, Group, Holdings
- People names: match 'Colin Roberts' = 'Colin R.' but NOT 'Colin' alone — require first+last for auto-match
- Normalize to lowercase for matching comparison, but preserve first-seen casing as the display name
- High-confidence normalization matches auto-add as aliases; low-confidence matches create merge proposals for review

### Claude's Discretion
- Exact confidence threshold values for auto-registration vs flagging
- Batch processing concurrency and rate limiting for LLM calls during backfill
- Specific fuzzy matching algorithm/library choice for HubSpot matching
- Checkpoint storage format for backfill resume capability

</decisions>

<specifics>
## Specific Ideas

- Entity extraction should be validated against 20+ real summaries to ensure quality before wiring into the pipeline
- Backfill should work with the existing sidecar JSON format in the output directory
- The success criteria require "Affirm Inc" and "Affirm" to resolve to the same entity — normalization must handle this case specifically

</specifics>

<deferred>
## Deferred Ideas

- **Low-confidence merge proposals:** CONTEXT decisions say "low-confidence matches create merge proposals for review." Merge proposal infrastructure (table, review UI, resolution logic) is Phase 22's domain. Phase 20 registers high-confidence entities only; low-confidence matches are logged but not written to a merge_proposals table. Phase 22 will implement the merge proposal workflow.

</deferred>

---

*Phase: 20-entity-discovery-backfill*
*Context gathered: 2026-04-06*
