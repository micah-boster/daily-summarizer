# Phase 22: Merge + Split Review - Research

**Researched:** 2026-04-08
**Domain:** Entity deduplication with CLI review workflow
**Confidence:** HIGH

## Summary

Phase 22 adds merge proposal generation, interactive CLI review, merge execution, and split/undo capability to the entity subsystem. The foundation is already extensive: the SQLite schema includes `merge_proposals` and `merge_target_id` fields (Phase 19), `MergeProposal` model exists, `rapidfuzz` is already a dependency used in `hubspot_xref.py` with a `FUZZY_THRESHOLD=80` pattern, and the entity repository has soft-delete, alias management, and merge-target-following resolution.

The work is primarily internal Python/SQLite with no new external dependencies. All patterns (TDD, repository, CLI subcommands, normalizer) are well-established in the codebase from Phases 19-21.

**Primary recommendation:** Extend the existing EntityRepository with merge/split operations, add a proposal generator module using rapidfuzz, and wire new CLI subcommands following the established cli.py pattern.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Reuse rapidfuzz from Phase 20 for name similarity scoring
- Threshold: 80+ score triggers a merge proposal
- Same entity type only (partner-to-partner, person-to-person) -- no cross-type proposals
- Name similarity is the sole signal -- shared context (co-occurrence in sources) is shown for review but does not affect ranking
- Interactive one-by-one CLI experience via `entity review`
- Each proposal shows: both entity names, which sources mentioned each, and mention counts
- No context snippets -- keep it compact
- When accepting, the most-mentioned name becomes canonical automatically
- Interactive only -- no --json output mode for review
- `--limit N` CLI flag controls proposals per session (default 10)
- Merged-away entity is soft-deleted with merge_target_id set (consistent with Phase 19 patterns)
- All mentions from merged-away entity are reassigned (entity_id updated) to the surviving entity
- All aliases from merged-away entity transfer to the surviving entity
- Merged-away entity's canonical name becomes an alias on the surviving entity
- `entity split` reverses a merge: restores the soft-deleted entity (clears deleted_at and merge_target_id)
- Mentions are re-attributed by matching original source name against restored entity names
- Aliases transferred during merge are moved back to the restored entity
- merge_proposals table records the merge history, which informs what to reverse
- On-demand generation only via `entity review` -- no background/pipeline scanning
- Rejections stored as merge_proposals rows with status='rejected' -- generator filters these out
- No separate audit log -- merge_proposals table + `entity split` is sufficient for reversibility

### Claude's Discretion
- Proposal ranking/ordering within a review session
- Exact CLI formatting and prompt text
- How to handle edge cases (e.g., entity already merged, circular merges)
- Whether to show a summary at end of review session

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DISC-03 | Users can merge duplicate entity references via interactive CLI review with persistent rejection | Existing merge_proposals table, MergeProposal model, rapidfuzz dependency, EntityRepository soft-delete pattern |
| DISC-04 | Users can split incorrectly merged entities and mentions are re-attributed | Existing merge_target_id field, entity_mentions table with entity_id FK, aliases table for transfer tracking |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| rapidfuzz | (existing) | Name similarity scoring via `fuzz.token_sort_ratio` | Already used in hubspot_xref.py with same threshold |
| sqlite3 | stdlib | Proposal storage, mention reassignment, alias transfer | Already the entity persistence layer |
| pydantic | (existing) | MergeProposal model already exists in models.py | Project standard for all data models |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| argparse | stdlib | CLI subcommand wiring for `entity review` and `entity split` | Following existing cli.py pattern |

### Alternatives Considered
None needed -- all components are already in the project.

## Architecture Patterns

### Existing Project Structure (entity module)
```
src/entity/
├── __init__.py
├── attributor.py       # Phase 21 - mention attribution
├── backfill.py         # Phase 20 - historical entity discovery
├── cli.py              # CLI subcommand dispatch
├── db.py               # Connection management with migrations
├── discovery.py        # Phase 20 - entity extraction
├── hubspot_xref.py     # Phase 20 - HubSpot cross-reference
├── migrations.py       # Schema versioning (currently v2)
├── models.py           # Pydantic models (Entity, Alias, MergeProposal, etc.)
├── normalizer.py       # Name normalization for matching
├── repository.py       # CRUD, alias management, name resolution
```

### New Files for Phase 22
```
src/entity/
├── merger.py           # Proposal generation + merge/split execution
```

### Pattern 1: Repository Extension
**What:** Add merge/split methods to EntityRepository
**When to use:** For all database operations (merge execution, mention reassignment, split reversal)
**Rationale:** The repository is the single data access layer; merge/split are entity CRUD operations.

Key operations to add to repository:
- `execute_merge(source_id, target_id)` -- soft-delete source, reassign mentions, transfer aliases
- `execute_split(entity_id)` -- reverse merge using merge_proposals history
- `get_mention_count(entity_id)` -- count mentions for canonical name selection
- `reassign_mentions(from_entity_id, to_entity_id)` -- bulk UPDATE entity_mentions
- `transfer_aliases(from_entity_id, to_entity_id)` -- move aliases between entities

### Pattern 2: Proposal Generator as Standalone Module
**What:** A `merger.py` module that generates proposals by comparing all active entities of the same type using rapidfuzz
**When to use:** Called by `entity review` CLI command on-demand
**Rationale:** Follows the pattern of discovery.py and hubspot_xref.py as focused modules

Key function: `generate_proposals(repo, entity_type=None, limit=10)` that:
1. Loads all active entities (optionally filtered by type)
2. Loads existing rejected proposals to skip
3. Compares all pairs using `fuzz.token_sort_ratio` on normalized names
4. Filters pairs scoring >= 80
5. Ranks by score descending
6. Returns top N proposals with context (mention counts per entity)

### Pattern 3: Interactive CLI Review Loop
**What:** An input() loop in cli.py that presents proposals one at a time
**When to use:** `entity review [--limit N] [--type partner|person]`
**Rationale:** CONTEXT.md specifies interactive one-by-one experience

### Anti-Patterns to Avoid
- **Auto-merging:** Never merge without explicit user confirmation. CONTEXT.md is clear: zero auto-merge.
- **Circular merge chains:** If entity A -> B and user tries to merge C -> A, follow the chain to B. The existing `resolve_name` already follows merge_target_id one level.
- **Orphaned aliases:** When splitting, aliases that were transferred during merge MUST be moved back.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Name similarity | Custom edit distance | `rapidfuzz.fuzz.token_sort_ratio` | Already in project, handles word reordering |
| Name normalization | New normalizer | `normalizer.normalize_for_matching()` | Already strips suffixes, lowercases |
| UUID generation | Custom IDs | `uuid4().hex` | Project standard in repository.py |
| Timestamp generation | Manual datetime | `models._now_utc()` | Project standard for all entity timestamps |

## Common Pitfalls

### Pitfall 1: N^2 Comparison Explosion
**What goes wrong:** Comparing all entity pairs is O(n^2). With 500 entities, that's 125,000 comparisons.
**Why it happens:** Naive all-pairs approach without type filtering.
**How to avoid:** Filter by entity_type first (user constraint: same type only). Partners and people are separate pools. Also skip already-merged entities (merge_target_id IS NOT NULL) and soft-deleted entities.
**Warning signs:** Slow `entity review` startup time.

### Pitfall 2: Mention Re-attribution During Split
**What goes wrong:** After split, mentions may not correctly return to the restored entity.
**How to avoid:** Track which mentions were reassigned during merge (merge_proposals row records source/target). During split, match mentions by their original source name against the restored entity's names/aliases.
**Warning signs:** Split entity shows 0 mentions after restoration.

### Pitfall 3: Alias Collision During Merge
**What goes wrong:** Source entity's canonical name added as alias on target, but alias already exists on another entity.
**How to avoid:** The aliases table has a UNIQUE constraint on `alias`. Use INSERT OR IGNORE or catch IntegrityError.
**Warning signs:** sqlite3.IntegrityError on merge.

### Pitfall 4: Double-Merge Proposals
**What goes wrong:** Same pair proposed again after rejection because rejection wasn't checked.
**How to avoid:** Query merge_proposals for existing rows (any status) for each pair before generating new proposals. Check both orderings (A,B and B,A).
**Warning signs:** User sees the same pair they already rejected.

## Code Examples

### Proposal Generation Pattern
```python
# Source: existing hubspot_xref.py pattern
from rapidfuzz import fuzz
from src.entity.normalizer import normalize_for_matching

def score_pair(name_a: str, name_b: str) -> float:
    norm_a = normalize_for_matching(name_a)
    norm_b = normalize_for_matching(name_b)
    return fuzz.token_sort_ratio(norm_a, norm_b)
```

### Merge Execution Pattern
```python
# Source: existing repository.py soft-delete pattern
def execute_merge(self, source_id: str, target_id: str) -> None:
    now = _now_utc()
    # 1. Reassign mentions
    self._conn.execute(
        "UPDATE entity_mentions SET entity_id = ? WHERE entity_id = ?",
        (target_id, source_id),
    )
    # 2. Transfer aliases (skip collisions)
    # 3. Add source canonical name as alias on target
    # 4. Soft-delete source with merge_target_id
    self._conn.execute(
        "UPDATE entities SET deleted_at = ?, merge_target_id = ?, updated_at = ? "
        "WHERE id = ?",
        (now, target_id, now, source_id),
    )
    self._conn.commit()
```

### Split Reversal Pattern
```python
# Reverse: clear soft-delete, clear merge_target_id, re-attribute
def execute_split(self, entity_id: str) -> None:
    now = _now_utc()
    # 1. Restore entity (clear deleted_at and merge_target_id)
    self._conn.execute(
        "UPDATE entities SET deleted_at = NULL, merge_target_id = NULL, updated_at = ? "
        "WHERE id = ?",
        (now, entity_id),
    )
    # 2. Re-attribute mentions (match by source name)
    # 3. Move back aliases that were transferred during merge
    self._conn.commit()
```

## Open Questions

1. **Mention re-attribution accuracy during split**
   - What we know: Mentions were bulk-reassigned during merge. Split needs to reverse this.
   - What's unclear: If the source_id in entity_mentions is unique enough to trace back to the original entity.
   - Recommendation: Use the merge_proposals row (source_entity_id/target_entity_id) plus name matching against the mention's context to determine which mentions belong to the restored entity. For mentions that can't be unambiguously attributed, leave them on the surviving entity (safe default).

## Sources

### Primary (HIGH confidence)
- Codebase analysis: src/entity/models.py -- MergeProposal model already defined
- Codebase analysis: src/entity/migrations.py -- merge_proposals table, merge_target_id column in schema v1
- Codebase analysis: src/entity/repository.py -- resolve_name follows merge_target_id
- Codebase analysis: src/entity/hubspot_xref.py -- rapidfuzz usage pattern with FUZZY_THRESHOLD=80
- Codebase analysis: src/entity/normalizer.py -- normalize_for_matching() for name comparison
- Codebase analysis: src/entity/cli.py -- existing CLI subcommand pattern

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already in project
- Architecture: HIGH - extending well-established patterns
- Pitfalls: HIGH - based on codebase analysis, not speculation

**Research date:** 2026-04-08
**Valid until:** 2026-05-08 (stable internal patterns)
