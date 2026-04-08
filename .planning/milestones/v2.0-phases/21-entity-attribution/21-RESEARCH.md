# Phase 21: Entity Attribution - Research

**Researched:** 2026-04-08
**Domain:** Entity matching, SQLite persistence, JSON sidecar enrichment
**Confidence:** HIGH

## Summary

Phase 21 connects synthesis output to the entity registry built in Phases 19-20. The core task is straightforward: take the `entity_names` lists already produced by Claude during synthesis (on `SynthesisItem` and `CommitmentRow` models), match them against the registry via `normalize_for_matching` + `EntityRepository.resolve_name`, and persist the results to both SQLite (`entity_mentions` table) and the JSON sidecar (`entity_references` per item + top-level summary).

The critical discovery is that `synthesize_daily()` currently **strips entity_names** from the structured output when converting to its dict return format (line 452: `[item.content for item in output.substance]`). Phase 21 must either modify the return format to preserve full `SynthesisItem`/`CommitmentRow` objects, or return them alongside the existing format. The attributor needs access to both the content strings and their associated `entity_names` lists.

All infrastructure already exists: the `entity_mentions` table with proper indexes (Phase 19 migration v1), `EntityRepository.resolve_name` with alias/merge-target following, `normalize_for_matching` for name normalization, and `get_connection_from_config` with graceful degradation. The `DailySidecar` Pydantic model needs new fields for entity references. No new libraries are needed.

**Primary recommendation:** Build a thin `EntityAttributor` class that takes synthesis output items + entity registry connection, returns attribution results. Wire it into `async_pipeline` after synthesis as a try/except-wrapped optional stage, similar to the existing `_discover_and_register_entities` pattern.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Normalize-then-exact match: run normalize_for_matching on both the synthesis name and registry name, match if equal
- No fuzzy fallback -- normalized exact + alias matching only (already high quality)
- When a name doesn't match any registered entity, skip silently -- no auto-registration (that's Phase 20's job)
- Check both entity_names lists AND commitment.who field for potential matches
- Attribution runs on all three sections: substance, decisions, and commitments
- Confidence: 1.0 for exact normalized match, 0.7 for alias-based match
- No minimum threshold -- include all matches
- Per-item entity_references: each substance/decision/commitment item gets its own `entity_references` list
- Each reference contains: entity_id, name, confidence (minimal, lean)
- Top-level entity summary: deduplicated list of all entities mentioned that day with mention counts
- Per-synthesis-item granularity for SQLite: one row per entity per synthesis item
- Item identification: SHA256 content hash (truncated) -- deterministic, no schema changes
- Re-runs replace: delete existing mentions for that date, insert fresh ones (idempotent)
- Keep everything: no retention/cleanup policy

### Claude's Discretion
- entity_mentions table schema details (columns, indexes)
- Schema migration version number
- How to extract text for content hashing (full content vs normalized)
- Top-level entity summary format in sidecar

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ATTR-01 | Synthesis items include entity references as structured output fields during Claude synthesis | Entity names are ALREADY extracted by Claude in `SynthesisItem.entity_names` and `CommitmentRow.entity_names` (Phase 20 extended these models). The attributor matches these names against the registry and produces `entity_references` with entity_id + confidence. No additional Claude calls needed. |
| ATTR-02 | Entity references are stored in both JSON sidecar and SQLite for portability and querying | Sidecar: extend `DailySidecar` with per-item `entity_references` and top-level `entity_summary`. SQLite: use existing `entity_mentions` table (schema v1). Content hash as `source_id` for deterministic item identification. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sqlite3 | stdlib | Entity mention persistence | Already used throughout entity subsystem |
| hashlib | stdlib | SHA256 content hash for item identification | Deterministic, no dependencies |
| pydantic | existing | Sidecar model extension, attribution result models | Project standard for all models |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| src.entity.normalizer | existing | `normalize_for_matching` for name comparison | Every name match attempt |
| src.entity.repository | existing | `resolve_name` for alias + merge-target resolution | Entity registry lookups |
| src.entity.db | existing | `get_connection_from_config` for graceful DB access | Opening entity DB connection |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| SHA256 content hash | Incremental integer IDs | Hash is deterministic and needs no schema change; integer IDs would require adding an auto-increment column to synthesis models |
| Truncated hash (16 chars) | Full SHA256 (64 chars) | 16 hex chars = 64 bits = sufficient uniqueness for daily item counts (<100 items/day); saves storage |

## Architecture Patterns

### Recommended Project Structure
```
src/entity/
├── attributor.py     # NEW: EntityAttributor class + attribution logic
├── models.py         # EntityMention already exists; add EntityReference model
├── db.py             # Existing: get_connection_from_config
├── normalizer.py     # Existing: normalize_for_matching
├── repository.py     # Existing: resolve_name
├── migrations.py     # May need v3 if entity_mentions schema needs changes
└── ...

src/
├── sidecar.py        # MODIFY: add entity_references + entity_summary fields
├── pipeline_async.py # MODIFY: wire attributor as post-synthesis stage
└── synthesis/
    └── synthesizer.py # MODIFY: preserve entity_names in return dict
```

### Pattern 1: Attributor as Pure Function Module
**What:** A stateless module with functions that take synthesis items + registry connection, return attribution results. No class needed since there's no state to manage beyond the DB connection (which is passed in).
**When to use:** This phase -- matches project style (discovery.py, normalizer.py are all function-based modules).
**Example:**
```python
# src/entity/attributor.py
def attribute_synthesis_items(
    synthesis_output: DailySynthesisOutput,
    conn: sqlite3.Connection,
    target_date: date,
) -> AttributionResult:
    """Match entity_names against registry, return per-item references."""
```

### Pattern 2: Graceful Degradation Wrapper (existing pattern)
**What:** Wrap the entire attribution stage in try/except at the pipeline level, identical to `_discover_and_register_entities` pattern.
**When to use:** Pipeline integration -- ensures attribution failure never blocks daily summary generation.
**Example:**
```python
# In pipeline_async.py (follows existing _discover_and_register_entities pattern)
try:
    attribution_result = attribute_and_persist(
        synthesis_output, target_date, config
    )
    # Enrich sidecar with entity_references
except Exception as e:
    logger.warning("Entity attribution failed: %s. Daily summary unaffected.", e)
```

### Pattern 3: Idempotent Date-Scoped Replacement
**What:** Delete all entity_mentions for the target date before inserting fresh ones. Matches the "re-runs replace" decision.
**When to use:** Every attribution run -- ensures idempotent behavior matching sidecar file overwrite.
**Example:**
```python
conn.execute("DELETE FROM entity_mentions WHERE source_date = ?", (date_str,))
# Then insert fresh mentions
```

### Anti-Patterns to Avoid
- **Calling Claude again for attribution:** Entity names are already extracted during synthesis. Attribution is a registry lookup, not an LLM task.
- **Modifying synthesis models for attribution output:** Attribution results should be separate from synthesis -- added as enrichment, not baked into synthesis models.
- **Auto-registering unmatched names:** User decision: skip silently. Phase 20 handles registration.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Name normalization | Custom lowercasing/stripping | `normalize_for_matching()` | Already handles company suffixes, casing, whitespace |
| Alias resolution | Direct SQL alias queries | `EntityRepository.resolve_name()` | Handles canonical name -> alias -> merge-target chain |
| DB connection lifecycle | Manual sqlite3.connect | `get_connection_from_config()` | Handles WAL mode, migrations, graceful degradation |
| Content hashing | Custom hash function | `hashlib.sha256(content.encode()).hexdigest()[:16]` | stdlib, deterministic, well-tested |

**Key insight:** 90% of the infrastructure already exists from Phases 19-20. This phase is primarily glue code connecting synthesis output to registry lookups and persistence.

## Common Pitfalls

### Pitfall 1: Synthesizer Strips entity_names
**What goes wrong:** `synthesize_daily()` returns `{"substance": [item.content for item in output.substance]}` -- discarding the `entity_names` field from `SynthesisItem` objects. The attributor needs these names.
**Why it happens:** The dict return format was designed before entity fields existed (Phase 20 added `entity_names` to models but synthesizer conversion wasn't updated).
**How to avoid:** Modify the `_format_synthesis_result` function to return full `SynthesisItem`/`CommitmentRow` objects (or at minimum, include `entity_names` in the return dict). The pipeline already handles both dict and object access patterns (see `_discover_and_register_entities` lines 64-73).
**Warning signs:** Empty `entity_references` in sidecar despite entity_names being in Claude's structured output.

### Pitfall 2: Content Hash Instability
**What goes wrong:** If the content string used for hashing includes volatile elements (timestamps, formatting), the same logical item gets different hashes across re-runs, breaking idempotent replacement.
**Why it happens:** Content strings include source attribution text like "(per meeting Title)" which is stable, but could vary with formatting changes.
**How to avoid:** Hash the core content only. For SynthesisItem: hash `content` field. For CommitmentRow: hash `f"{who}|{what}|{by_when}"`. Document the hash formula.
**Warning signs:** Duplicate mentions accumulating despite delete-then-insert pattern.

### Pitfall 3: Alias Match Not Differentiated from Direct Match
**What goes wrong:** `resolve_name` returns an Entity but doesn't indicate HOW it matched (direct name vs alias). Confidence should be 1.0 for direct, 0.7 for alias.
**Why it happens:** `resolve_name` is a two-step lookup that returns the entity without match metadata.
**How to avoid:** Build attribution logic that first tries `repo.get_by_name(normalized)` (confidence 1.0), then falls back to checking aliases explicitly (confidence 0.7). Don't use `resolve_name` as a black box -- use the two-step pattern directly to track match type.
**Warning signs:** All matches showing confidence 1.0.

### Pitfall 4: Commitment.who Field Forgotten
**What goes wrong:** User decided to check `commitment.who` as a potential entity match source (e.g., "Colin" in the who field). If only `entity_names` is checked, person references in the who field are missed.
**Why it happens:** Easy to forget since substance/decisions only have `entity_names`, but commitments have both.
**How to avoid:** For CommitmentRow items, build the candidate name list as `set(item.entity_names + [item.who])` (excluding "TBD" or empty values).
**Warning signs:** Commitments attributed to companies but not the people who made them.

### Pitfall 5: Sidecar Written Before Attribution
**What goes wrong:** If sidecar is written before attribution runs, entity_references won't be in the JSON file.
**Why it happens:** Current pipeline writes sidecar immediately after synthesis, before entity discovery.
**How to avoid:** Either (a) move sidecar writing after attribution, or (b) pass attribution results into the sidecar builder. Option (b) is cleaner -- attribution produces results, sidecar builder receives them.
**Warning signs:** Sidecar JSON missing entity_references field entirely.

## Code Examples

Verified patterns from existing codebase:

### Content Hash Generation
```python
# Deterministic item identification via SHA256 truncated hash
import hashlib

def content_hash(text: str) -> str:
    """Generate a truncated SHA256 hash for synthesis item identification."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
```

### Two-Step Name Matching with Confidence Tracking
```python
# Based on EntityRepository.resolve_name pattern but tracking match type
from src.entity.normalizer import normalize_for_matching

def match_name_to_entity(
    raw_name: str,
    repo: EntityRepository,
) -> tuple[Entity, float] | None:
    """Match a name against registry, returning (entity, confidence).

    Returns None if no match found.
    Confidence: 1.0 for direct name match, 0.7 for alias match.
    """
    normalized = normalize_for_matching(raw_name)

    # Step 1: direct name match (confidence 1.0)
    entity = repo.get_by_name(normalized)
    if entity is None:
        entity = repo.get_by_name(raw_name)
    if entity:
        # Follow merge target
        if entity.merge_target_id:
            merged = repo.get_by_id(entity.merge_target_id)
            if merged:
                entity = merged
        return entity, 1.0

    # Step 2: alias match (confidence 0.7)
    # Need direct SQL since resolve_name doesn't differentiate
    row = repo._conn.execute(
        "SELECT a.entity_id FROM aliases a "
        "JOIN entities e ON a.entity_id = e.id "
        "WHERE LOWER(a.alias) = LOWER(?) AND e.deleted_at IS NULL",
        (raw_name,),
    ).fetchone()
    if row:
        entity = repo.get_by_id(row["entity_id"])
        if entity and entity.merge_target_id:
            merged = repo.get_by_id(entity.merge_target_id)
            if merged:
                entity = merged
        if entity:
            return entity, 0.7

    return None
```

### Idempotent Mention Persistence
```python
# Delete-then-insert for target date (matches sidecar overwrite behavior)
def persist_mentions(
    conn: sqlite3.Connection,
    mentions: list[EntityMention],
    target_date: str,
) -> int:
    """Persist entity mentions, replacing any existing for the date."""
    conn.execute(
        "DELETE FROM entity_mentions WHERE source_date = ?",
        (target_date,)
    )
    for m in mentions:
        conn.execute(
            "INSERT INTO entity_mentions (id, entity_id, source_type, source_id, "
            "source_date, confidence, context_snippet, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (m.id, m.entity_id, m.source_type, m.source_id,
             m.source_date, m.confidence, m.context_snippet, m.created_at),
        )
    conn.commit()
    return len(mentions)
```

### Sidecar Entity Reference Model
```python
# New models to add to src/sidecar.py
class SidecarEntityReference(BaseModel):
    """An entity reference attached to a synthesis item."""
    entity_id: str
    name: str
    confidence: float

class SidecarEntitySummary(BaseModel):
    """Top-level entity summary for a day."""
    entity_id: str
    name: str
    entity_type: str
    mention_count: int
```

### Pipeline Integration Pattern
```python
# In async_pipeline, after synthesis but before sidecar write
# Follows existing _discover_and_register_entities pattern
attribution_result = None
try:
    from src.entity.attributor import attribute_synthesis
    attribution_result = attribute_synthesis(
        synthesis_output, current, ctx.config
    )
except Exception as e:
    logger.warning("Entity attribution failed: %s. Daily summary unaffected.", e)

# Pass attribution_result to sidecar builder (None means no entity data)
sidecar_path = write_daily_sidecar(
    synthesis, extractions, ctx.output_dir,
    extracted_commitments=extracted_commitments,
    entity_attribution=attribution_result,
)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Entity names extracted but discarded | Phase 20 added entity_names to SynthesisItem/CommitmentRow | Phase 20 (2026-04-06) | Models have the data; synthesizer return format needs updating |
| No entity mentions table | Schema v1 created entity_mentions with indexes | Phase 19 (2026-04-06) | Table ready for use, no migration needed for basic attribution |
| No sidecar entity support | Sidecar is plain tasks/decisions/commitments | Current | Needs extension for entity_references + entity_summary |

## Open Questions

1. **Synthesizer return format change scope**
   - What we know: `synthesize_daily()` must be modified to preserve `entity_names`. The pipeline (`_discover_and_register_entities`) already handles both dict and object access.
   - What's unclear: Whether to return full Pydantic objects or add `entity_names` alongside content strings in the dict.
   - Recommendation: Return full `SynthesisItem`/`CommitmentRow` objects in the dict values (change `[item.content for item in ...]` to `[item for item in ...]`). Then update downstream consumers (writer, sidecar, pipeline) to access `.content` where they need strings. This is the cleanest approach and matches the structured output philosophy.

2. **entity_mentions source_type value**
   - What we know: The column is TEXT with no enum constraint.
   - What's unclear: What value to use -- "daily_synthesis" vs "substance"/"decision"/"commitment" (section-specific).
   - Recommendation: Use section-specific source_type ("substance", "decision", "commitment") so Phase 23 views can filter by section. The `source_id` is the content hash.

3. **Schema migration needed?**
   - What we know: The `entity_mentions` table already exists (v1 migration) with all needed columns: entity_id, source_type, source_id, source_date, confidence, context_snippet.
   - What's unclear: Whether additional indexes would help Phase 23 queries (e.g., compound index on entity_id + source_date).
   - Recommendation: No schema migration needed for Phase 21. The existing indexes (`idx_mentions_entity`, `idx_mentions_source_date`) are sufficient. Phase 23 can add compound indexes if query performance requires it.

## Sources

### Primary (HIGH confidence)
- `src/synthesis/models.py` - SynthesisItem.entity_names and CommitmentRow.entity_names fields confirmed
- `src/synthesis/synthesizer.py` lines 450-458 - synthesizer strips entity_names in return format
- `src/entity/migrations.py` - entity_mentions table schema with all needed columns
- `src/entity/repository.py` - resolve_name two-step lookup with merge-target following
- `src/entity/normalizer.py` - normalize_for_matching function
- `src/pipeline_async.py` - _discover_and_register_entities pattern for graceful degradation
- `src/sidecar.py` - DailySidecar model structure
- `src/entity/db.py` - get_connection_from_config with graceful None return

### Secondary (MEDIUM confidence)
- `src/entity/discovery.py` - entity extraction prompt and structured output pattern (reference for test patterns)
- `tests/test_discovery.py` - test patterns using make_test_config and mock Claude responses

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already in use, no new dependencies
- Architecture: HIGH - Direct extension of existing patterns (discovery, pipeline integration, sidecar)
- Pitfalls: HIGH - Identified from direct codebase analysis (synthesizer stripping entity_names is verified)

**Research date:** 2026-04-08
**Valid until:** 2026-05-08 (stable -- all dependencies are internal)
