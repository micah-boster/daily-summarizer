# Phase 21: Entity Attribution - Context

**Gathered:** 2026-04-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Every synthesis item (substance, decisions, commitments) gets linked to registered entities from the Phase 19/20 registry. Links are persisted to both SQLite (entity_mentions table for querying) and JSON sidecar (entity_references per item for portability). This makes entity-scoped filtering possible in Phase 23.

</domain>

<decisions>
## Implementation Decisions

### Matching strategy
- Normalize-then-exact match: run normalize_for_matching on both the synthesis name and registry name, match if equal
- No fuzzy fallback — normalized exact + alias matching only (already high quality)
- When a name doesn't match any registered entity, skip silently — no auto-registration (that's Phase 20's job)
- Check both entity_names lists AND commitment.who field for potential matches
- Attribution runs on all three sections: substance, decisions, and commitments

### Confidence scoring
- 1.0 for exact normalized match
- 0.7 for alias-based match (matched via registry alias, not direct name)
- No minimum threshold — include all matches since matching is already high quality (no fuzzy)

### Sidecar output shape
- Per-item entity_references: each substance/decision/commitment item gets its own `entity_references` list
- Each reference contains: entity_id, name, confidence (minimal, lean)
- Top-level entity summary: deduplicated list of all entities mentioned that day with mention counts, for quick "who was discussed today" queries

### Mention persistence (SQLite)
- Per-synthesis-item granularity: one row per entity per synthesis item
- Item identification: SHA256 content hash (truncated) — deterministic, no schema changes to synthesis models
- Re-runs replace: delete existing mentions for that date, insert fresh ones (idempotent, matches sidecar overwrite behavior)
- Keep everything: no retention/cleanup policy — historical data is valuable for trend queries

### Claude's Discretion
- entity_mentions table schema details (columns, indexes)
- Schema migration version number
- How to extract text for content hashing (full content vs normalized)
- Top-level entity summary format in sidecar

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

*Phase: 21-entity-attribution*
*Context gathered: 2026-04-08*
