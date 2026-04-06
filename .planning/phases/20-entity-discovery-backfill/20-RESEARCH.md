# Phase 20: Entity Discovery + Backfill - Research

**Researched:** 2026-04-06
**Domain:** NLP entity extraction, name normalization, HubSpot cross-referencing, batch processing with checkpointing
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Extend existing SynthesisItem/CommitmentRow Pydantic models with optional `entity_names` field
- LLM extracts entities as part of synthesis, tagging each as 'partner' or 'person'
- Entities above a confidence threshold are auto-registered in the registry; low-confidence entities are flagged for review
- If entity extraction fails (LLM error, bad parse), skip silently and log a warning -- daily summary generates normally with empty entity fields
- Progress bar with counts: "Processing 2025-10-01 to 2026-04-05... [###---] 120/180 days, 47 entities found"
- Track which days have been processed; skip already-scanned days on re-run. `--force` flag to override and re-scan
- Use LLM extraction on historical summaries (send synthesis text through entity extraction prompt) -- richer results than just parsing sidecar fields
- Process in weekly batches (7 days at a time) with checkpoint/resume capability -- if interrupted, resume from last completed batch
- Exact name match first, then fuzzy fallback (e.g., 'Affirm Inc' -> 'Affirm'). Store match confidence.
- Store HubSpot contact/deal ID, email (if contact), and deal stage (if deal) -- enough to link back without duplicating HubSpot
- Cross-reference on both backfill and daily pipeline runs
- If HubSpot API is unavailable or rate-limited, skip enrichment and flag entity as 'pending_enrichment' for later retry
- Strip common US company suffixes: Inc, LLC, Corp, Ltd, Co, LP, Partners, Group, Holdings
- People names: match 'Colin Roberts' = 'Colin R.' but NOT 'Colin' alone -- require first+last for auto-match
- Normalize to lowercase for matching comparison, but preserve first-seen casing as the display name
- High-confidence normalization matches auto-add as aliases; low-confidence matches create merge proposals for review

### Claude's Discretion
- Exact confidence threshold values for auto-registration vs flagging
- Batch processing concurrency and rate limiting for LLM calls during backfill
- Specific fuzzy matching algorithm/library choice for HubSpot matching
- Checkpoint storage format for backfill resume capability

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DISC-01 | System discovers entities by scanning existing daily summary sidecars via backfill command | Backfill CLI architecture, sidecar JSON parsing, LLM extraction prompt design, weekly batch processing with checkpointing |
| DISC-02 | New pipeline runs automatically discover and register new entities as a post-synthesis step | SynthesisItem/CommitmentRow model extension with entity_names, post-synthesis entity registration in async_pipeline |
| DISC-05 | Discovered entities are cross-referenced with HubSpot contacts/deals by name match | HubSpot SDK search API patterns, name normalization layer, fuzzy matching with rapidfuzz |
</phase_requirements>

## Summary

Phase 20 requires three interlocking capabilities: (1) an entity extraction prompt that takes synthesis text and outputs structured entity names with types, (2) a backfill CLI that processes historical sidecar JSONs through this extraction in weekly batches with checkpoint/resume, and (3) a HubSpot cross-referencing layer that matches discovered entities against CRM contacts and deals by name.

The project already has a fully functional entity registry (Phase 19) with SQLite storage, alias management, and name resolution. The synthesis pipeline uses Claude structured outputs via `json_schema` constrained decoding (Phase 14/18). The HubSpot SDK is already integrated with search APIs for contacts and deals. The key new work is: extending the structured output models to include entity names, building a name normalization layer, creating the backfill orchestrator with batch processing, and wiring HubSpot search for name-based lookups.

A critical constraint is that only 3 sidecar JSON files currently exist in the output directory (2026-03-18, 2026-04-03, 2026-04-05), and the 04-03 and 04-05 sidecars are nearly empty. The backfill command will need to read daily markdown files as an alternative input source when sidecars are absent, or the backfill approach should use LLM extraction on the markdown content directly (which aligns with the CONTEXT.md decision to "send synthesis text through entity extraction prompt").

**Primary recommendation:** Extend existing Claude structured output models (SynthesisItem, CommitmentRow) with optional `entity_names: list[str]` fields, build a standalone entity extraction function that works on both live synthesis output and historical markdown/sidecar content, and wire into async_pipeline as an optional post-synthesis step with try/except isolation.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | >=0.45.0,<1.0 | Entity extraction via structured outputs | Already in project; json_schema constrained decoding guarantees valid output |
| pydantic | >=2.12.5,<3.0 | Model extension (SynthesisItem, CommitmentRow) | Already in project; all models use Pydantic v2 |
| hubspot-api-client | >=12.0.0,<13.0 | Contact/deal search for cross-referencing | Already in project; search APIs already used in ingest module |
| sqlite3 | stdlib | Entity registry persistence | Already in project (Phase 19); EntityRepository handles all CRUD |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| rapidfuzz | >=3.0,<4.0 | Fuzzy name matching for HubSpot cross-reference | When exact name match fails; used for "Affirm Inc" -> "Affirm" fallback |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| rapidfuzz | thefuzz (fuzzywuzzy) | rapidfuzz is 10x faster (C++ backend), MIT license, drop-in API compatible. thefuzz is pure Python, slower. Use rapidfuzz. |
| rapidfuzz | jellyfish | jellyfish provides phonetic algorithms (Soundex, Metaphone) but not the token_sort_ratio needed for company name matching. rapidfuzz is better for this use case. |
| LLM extraction on backfill | Regex/NER parsing of sidecar JSON | LLM extraction is richer (understands context, types entities correctly) per CONTEXT.md locked decision. Regex would miss implicit entity references. |

**Installation:**
```bash
uv add "rapidfuzz>=3.0,<4.0"
```

## Architecture Patterns

### Recommended Project Structure
```
src/entity/
├── __init__.py          # existing
├── cli.py               # extend with 'backfill' subcommand
├── db.py                # existing (connection management)
├── discovery.py          # NEW: entity extraction from synthesis text
├── migrations.py         # existing (may need v2 migration for backfill tracking)
├── models.py            # existing (may add BackfillCheckpoint model)
├── normalizer.py         # NEW: name normalization (suffix stripping, casing)
├── hubspot_xref.py       # NEW: HubSpot cross-reference by name match
├── repository.py         # existing (add find_or_create, update_hubspot_id methods)
└── backfill.py           # NEW: backfill orchestrator (weekly batches, checkpoints)
```

### Pattern 1: Extend Structured Output Models
**What:** Add optional `entity_names` field to SynthesisItem and CommitmentRow so the LLM extracts entity references during synthesis.
**When to use:** Ongoing daily pipeline runs (DISC-02).
**Key detail:** The field MUST be optional with a default empty list so existing synthesis prompts continue working if the entity subsystem is disabled. The `extra="forbid"` ConfigDict on these models means the field must be explicitly added.

```python
# In src/synthesis/models.py
class SynthesisItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str
    entity_names: list[str] = Field(default_factory=list)  # NEW

class CommitmentRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    who: str
    what: str
    by_when: str
    source: str
    entity_names: list[str] = Field(default_factory=list)  # NEW
```

### Pattern 2: Standalone Entity Extraction Function
**What:** A function that takes synthesis text (from sidecar JSON or daily markdown) and returns a list of `(name, type, confidence)` tuples using Claude structured outputs.
**When to use:** Both backfill (reading historical files) and daily pipeline (post-synthesis step).
**Key detail:** Must work independently from the synthesis pipeline so it can process any text input. Uses the same `_call_claude_structured_with_retry` pattern already established in synthesizer.py and commitments.py.

```python
# In src/entity/discovery.py
class DiscoveredEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    entity_type: str  # "partner" or "person"
    confidence: float  # 0.0-1.0

class EntityExtractionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reasoning: str = ""
    entities: list[DiscoveredEntity] = Field(default_factory=list)

def extract_entities(text: str, config: PipelineConfig, client=None) -> list[DiscoveredEntity]:
    """Extract entity names from synthesis text using Claude structured outputs."""
    ...
```

### Pattern 3: Post-Synthesis Entity Registration
**What:** After synthesis completes in async_pipeline, iterate over synthesis items' entity_names, normalize each name, resolve against registry, and register new entities.
**When to use:** Every daily pipeline run (DISC-02).
**Key detail:** Wrapped in try/except so entity failures never break the daily summary. Uses the existing `get_connection_from_config()` graceful degradation pattern from db.py.

### Pattern 4: Backfill with Weekly Batching and Checkpointing
**What:** Process historical days in 7-day batches, checkpointing after each batch. On re-run, skip completed batches.
**When to use:** `entity backfill --from DATE --to DATE` CLI command (DISC-01).
**Key detail:** Checkpoint stored in the entity SQLite database (new table or JSON in entity metadata). Each day's processing reads the sidecar JSON or markdown, sends through entity extraction, registers entities. Progress bar shows batch progress.

### Pattern 5: HubSpot Cross-Reference
**What:** After entity registration, search HubSpot contacts and deals by name. Exact match first, then fuzzy fallback with rapidfuzz.
**When to use:** Both backfill and daily pipeline runs (DISC-05).
**Key detail:** The HubSpot SDK's `search_api.do_search()` supports a `query` parameter for text search. Use it for initial candidate retrieval, then apply rapidfuzz for scoring. Store match in `entities.hubspot_id` field (already exists in schema) and entity metadata.

### Anti-Patterns to Avoid
- **Entity extraction in the synthesis prompt itself:** Don't modify the main SYNTHESIS_PROMPT to also extract entities. This couples entity discovery with synthesis quality. Instead, use the existing entity_names field on the output models and add entity-specific instructions as an addendum, or run a separate extraction pass on the output.
- **Blocking the pipeline on HubSpot:** HubSpot cross-reference must be fire-and-forget with graceful degradation. Never let a HubSpot API timeout block daily summary generation.
- **Case-sensitive name matching:** All name comparisons must normalize to lowercase. The display name preserves original casing but matching is case-insensitive.
- **Auto-merging on fuzzy match:** Per STATE.md blocker: "False merges are catastrophic -- zero auto-merge on fuzzy signals, only deterministic IDs." Fuzzy matches should create merge proposals, never auto-merge.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fuzzy string matching | Custom Levenshtein | rapidfuzz `fuzz.token_sort_ratio` | Handles word reordering ("Affirm Inc" vs "Inc Affirm"), C++ speed, well-tested |
| Company suffix stripping | Complex regex | Simple suffix list + str.rstrip | The suffix list (Inc, LLC, Corp, Ltd, Co, LP, Partners, Group, Holdings) is fixed and small |
| Progress bars | Custom terminal output | Simple f-string with \r carriage return | The backfill UI is simple: "Processing... [###---] X/Y days, Z entities". No need for tqdm/rich. |
| Structured JSON extraction | Regex parsing | Claude structured outputs (json_schema) | Project standard since Phase 14. Guaranteed valid JSON, no parsing errors. |
| Checkpoint/resume | File-based JSON checkpoint | SQLite table in entity DB | Entity DB is already the persistence layer. Adding a `backfill_progress` table is cleaner than a separate JSON file. |

**Key insight:** The project already has every building block for this phase. The structured output pattern, HubSpot SDK, entity repository, and async pipeline are all established. The new work is wiring them together with a name normalization layer and backfill orchestrator.

## Common Pitfalls

### Pitfall 1: Entity Explosion from Noisy Extraction
**What goes wrong:** LLM extracts too many entities (every proper noun becomes an entity), flooding the registry with noise.
**Why it happens:** Without clear extraction criteria, Claude will extract meeting room names, product feature names, generic terms ("the team"), etc.
**How to avoid:** Prompt must be very specific: extract only companies/organizations (partners) and individual people. Exclude internal team names, product names, generic groups. Set a minimum confidence threshold (recommend 0.6) for auto-registration. Test against 20+ real summaries per CONTEXT.md specific idea.
**Warning signs:** Registry grows to 100+ entities after processing a few days. Most entities have only 1 mention.

### Pitfall 2: Sidecar JSON Sparsity
**What goes wrong:** Backfill finds very few sidecar JSONs (currently only 3 exist) and most are empty.
**Why it happens:** The project has only been producing sidecar output since Phase 5, and many days have empty sidecars (no meetings, no transcripts).
**How to avoid:** The backfill must also read daily markdown files when sidecars are absent or empty. The markdown files contain the actual synthesis text (substance, decisions, commitments sections). Parse the markdown or use it directly as input to the entity extraction prompt.
**Warning signs:** Backfill reports "0 entities found" for most days.

### Pitfall 3: HubSpot Rate Limiting During Batch Cross-Reference
**What goes wrong:** Backfill discovers 50+ entities and fires 50+ HubSpot search queries, hitting rate limits.
**Why it happens:** HubSpot private app tokens have rate limits (100 calls/10 seconds for search API).
**How to avoid:** Batch HubSpot cross-reference: collect all new entity names, search HubSpot once per batch (not per entity). Cache HubSpot results for the session. Use the existing `@retry_api_call` decorator for transient failures.
**Warning signs:** HubSpot API returning 429 errors during backfill.

### Pitfall 4: Duplicate Entity Registration
**What goes wrong:** "Affirm Inc" and "Affirm" both get registered as separate entities.
**Why it happens:** Name normalization runs after registration, or normalization doesn't strip suffixes before checking the registry.
**How to avoid:** Normalize BEFORE checking the registry. Flow: raw name -> normalize (strip suffix, lowercase) -> check registry by normalized name AND aliases -> register only if not found. Auto-add the raw name as an alias if it differs from the normalized canonical name.
**Warning signs:** `entity list` shows near-duplicate names.

### Pitfall 5: Breaking Existing Structured Output Schemas
**What goes wrong:** Adding `entity_names` to SynthesisItem/CommitmentRow breaks the json_schema used with Claude's constrained decoding.
**Why it happens:** The schema is derived from the Pydantic model. If the model changes, the schema sent to Claude changes, and Claude must now fill the new field.
**How to avoid:** The field must have `default_factory=list` so it's optional in the schema. Also update the synthesis prompt to instruct Claude to populate entity_names. Test that existing synthesis still works when entity_names is empty.
**Warning signs:** Synthesis API calls returning errors or empty results after model change.

### Pitfall 6: Backfill Checkpoint Corruption
**What goes wrong:** Backfill is interrupted mid-batch, checkpoint says batch is complete but some days weren't processed.
**Why it happens:** Checkpoint is written before all days in the batch are processed.
**How to avoid:** Only write checkpoint AFTER all days in the batch are successfully processed. Track individual day completion within the batch. On resume, re-process any incomplete days in the last batch.
**Warning signs:** Re-running backfill with `--force` finds new entities that the initial run missed.

## Code Examples

### Entity Name Normalization
```python
# src/entity/normalizer.py
import re

COMPANY_SUFFIXES = [
    "Inc", "LLC", "Corp", "Ltd", "Co", "LP",
    "Partners", "Group", "Holdings",
    "Inc.", "LLC.", "Corp.", "Ltd.", "Co.",
]

# Pre-compile pattern: match suffix at end of string, optionally preceded by comma
_SUFFIX_PATTERN = re.compile(
    r"[,\s]*\b(?:" + "|".join(re.escape(s) for s in COMPANY_SUFFIXES) + r")\.?\s*$",
    re.IGNORECASE,
)

def normalize_company_name(name: str) -> str:
    """Strip common company suffixes and normalize whitespace."""
    cleaned = _SUFFIX_PATTERN.sub("", name).strip()
    return cleaned if cleaned else name  # Don't return empty string

def normalize_for_matching(name: str) -> str:
    """Lowercase and strip suffixes for comparison. Preserve nothing."""
    return normalize_company_name(name).lower().strip()

def names_match_person(name_a: str, name_b: str) -> bool:
    """Check if two person names match. Requires first+last."""
    parts_a = name_a.lower().split()
    parts_b = name_b.lower().split()
    if len(parts_a) < 2 or len(parts_b) < 2:
        return False
    # Full match
    if parts_a == parts_b:
        return True
    # "Colin Roberts" matches "Colin R."
    if parts_a[0] == parts_b[0]:
        if parts_a[-1].rstrip(".") == parts_b[-1].rstrip(".")[:len(parts_a[-1].rstrip("."))]:
            return True
        if parts_b[-1].rstrip(".") == parts_a[-1].rstrip(".")[:len(parts_b[-1].rstrip("."))]:
            return True
    return False
```

### Entity Extraction Prompt Pattern
```python
ENTITY_EXTRACTION_PROMPT = """Extract all named entities (companies/organizations and individual people) from this daily summary text.

Rules:
- ONLY extract companies/organizations (type: "partner") and individual people (type: "person")
- Do NOT extract: internal team names, product names, generic groups ("the team"), meeting room names
- For companies: use the full formal name as it appears (e.g., "Affirm Inc", "Cardless")
- For people: use first and last name when available (e.g., "Colin Roberts", not just "Colin")
- Confidence: 1.0 for explicitly named entities, 0.7 for contextually inferred, 0.4 for ambiguous
- If no entities are found, return an empty list

Text:
{text}
"""
```

### HubSpot Cross-Reference Pattern
```python
# src/entity/hubspot_xref.py
from hubspot import HubSpot
from hubspot.crm.contacts import PublicObjectSearchRequest as ContactSearchRequest
from hubspot.crm.deals import PublicObjectSearchRequest as DealSearchRequest
from rapidfuzz import fuzz

FUZZY_THRESHOLD = 80  # Minimum token_sort_ratio for fuzzy match

def search_hubspot_contact(client: HubSpot, name: str) -> dict | None:
    """Search HubSpot contacts by name. Returns contact dict or None."""
    request = ContactSearchRequest(
        query=name,
        properties=["firstname", "lastname", "email", "company"],
        limit=5,
    )
    response = client.crm.contacts.search_api.do_search(
        public_object_search_request=request
    )
    for contact in response.results:
        props = contact.properties
        full_name = f"{props.get('firstname', '')} {props.get('lastname', '')}".strip()
        # Exact match
        if full_name.lower() == name.lower():
            return {"id": contact.id, "email": props.get("email"), "confidence": 1.0}
        # Fuzzy match
        score = fuzz.token_sort_ratio(full_name.lower(), name.lower())
        if score >= FUZZY_THRESHOLD:
            return {"id": contact.id, "email": props.get("email"), "confidence": score / 100}
    return None

def search_hubspot_deal(client: HubSpot, name: str) -> dict | None:
    """Search HubSpot deals by name. Returns deal dict or None."""
    request = DealSearchRequest(
        query=name,
        properties=["dealname", "dealstage"],
        limit=5,
    )
    response = client.crm.deals.search_api.do_search(
        public_object_search_request=request
    )
    for deal in response.results:
        deal_name = deal.properties.get("dealname", "")
        if deal_name.lower() == name.lower():
            return {"id": deal.id, "deal_stage": deal.properties.get("dealstage"), "confidence": 1.0}
        score = fuzz.token_sort_ratio(deal_name.lower(), name.lower())
        if score >= FUZZY_THRESHOLD:
            return {"id": deal.id, "deal_stage": deal.properties.get("dealstage"), "confidence": score / 100}
    return None
```

### Backfill Checkpoint Table (Schema Migration v2)
```python
# Addition to migrations.py
def _migrate_v1_to_v2(conn):
    """Add backfill tracking table."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS backfill_progress (
            id TEXT PRIMARY KEY,
            source_date TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'completed' CHECK(status IN ('completed', 'failed', 'skipped')),
            entities_found INTEGER DEFAULT 0,
            processed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        );
        CREATE INDEX IF NOT EXISTS idx_backfill_date ON backfill_progress(source_date);
    """)
```

### Post-Synthesis Entity Registration in Pipeline
```python
# Addition to async_pipeline.py (after sidecar writing)
async def _discover_and_register_entities(
    synthesis_result: dict,
    target_date: date,
    config: PipelineConfig,
    client: anthropic.Anthropic | None = None,
) -> None:
    """Post-synthesis entity discovery and registration. Fire-and-forget."""
    if not config.entity.enabled:
        return
    try:
        # Collect entity names from synthesis items
        all_entity_names: list[str] = []
        for section in ["substance", "decisions"]:
            for item in synthesis_result.get(section, []):
                if hasattr(item, "entity_names"):
                    all_entity_names.extend(item.entity_names)
        for commitment in synthesis_result.get("commitments", []):
            if hasattr(commitment, "entity_names"):
                all_entity_names.extend(commitment.entity_names)

        if not all_entity_names:
            return

        # Normalize and register
        with EntityRepository(config.entity.db_path) as repo:
            for raw_name in set(all_entity_names):
                normalized = normalize_for_matching(raw_name)
                existing = repo.resolve_name(normalized)
                if existing is None:
                    # Determine type from context (default to partner for companies)
                    entity_type = "person" if _looks_like_person(raw_name) else "partner"
                    repo.add_entity(raw_name, entity_type)
    except Exception as e:
        logger.warning("Entity discovery failed: %s. Daily summary unaffected.", e)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Free-text markdown parsing for LLM outputs | json_schema constrained decoding | Phase 14 (2026-04-05) | Entity extraction MUST use structured outputs, not regex parsing |
| Sync pipeline execution | Async pipeline with asyncio.gather | Phase 17 (2026-04-05) | Entity registration should be an async post-synthesis step |
| Raw dict config access | Pydantic typed config | Phase 13 (2026-04-05) | EntityConfig already exists; extend with discovery-specific fields |

**Deprecated/outdated:**
- Markdown parsing for LLM outputs: Completely replaced by structured outputs in Phase 14/18. Entity extraction must follow this pattern.
- Sync pipeline entry point: pipeline.py still exists but async_pipeline.py is the active path. New entity wiring goes in async_pipeline.

## Open Questions

1. **Backfill input source when sidecars are empty**
   - What we know: Only 3 sidecar JSONs exist. 2 are nearly empty. There are 5+ daily markdown files.
   - What's unclear: Should backfill parse markdown files directly, or should it only work with sidecars?
   - Recommendation: Backfill should read markdown files as the primary source (the actual synthesis text). Sidecar JSON is supplementary for structured commitment/task data. The CONTEXT.md says "send synthesis text through entity extraction prompt" which supports using markdown content.

2. **Confidence threshold for auto-registration**
   - What we know: CONTEXT.md delegates this to Claude's discretion. ConfidenceLevel constants exist: HIGH=1.0, MEDIUM=0.7, LOW=0.4, FUZZY=0.2.
   - What's unclear: Where exactly to draw the auto-register vs flag-for-review line.
   - Recommendation: Auto-register at >= 0.7 (MEDIUM and above). Flag for review at 0.4-0.7. Discard below 0.4. These thresholds should be configurable in EntityConfig.

3. **Backfill LLM cost estimate**
   - What we know: STATE.md notes "$2-5 for 180 days" needs pilot verification. Currently only ~5 days have output files.
   - What's unclear: Actual token costs per day of entity extraction.
   - Recommendation: The entity extraction prompt is much smaller than full synthesis (just the output text, not all source material). Estimate ~500 input tokens + ~200 output tokens per day = ~700 tokens/day. At Claude Sonnet pricing (~$3/M input, $15/M output), 180 days = ~$0.15 input + ~$0.54 output = ~$0.69 total. Well within budget.

4. **HubSpot search API query parameter behavior**
   - What we know: The HubSpot SDK's `do_search()` accepts a `query` parameter for full-text search across default searchable properties (contacts: firstname, lastname, email, phone, company; deals: dealname).
   - What's unclear: Whether the query parameter does substring matching or exact word matching.
   - Recommendation: Use the `query` parameter for initial candidate retrieval (it does fuzzy text search), then apply rapidfuzz for precise scoring on the results. This is a two-stage approach: HubSpot narrows candidates, rapidfuzz scores them.

## Sources

### Primary (HIGH confidence)
- Project codebase: `src/entity/` (Phase 19 entity registry -- models, repository, migrations, CLI)
- Project codebase: `src/synthesis/models.py` (SynthesisItem, CommitmentRow, DailySynthesisOutput)
- Project codebase: `src/pipeline_async.py` (async pipeline orchestrator -- integration point)
- Project codebase: `src/ingest/hubspot.py` (HubSpot SDK usage patterns -- search_api.do_search)
- Project codebase: `src/sidecar.py` (DailySidecar model and builder)
- Project codebase: `src/config.py` (EntityConfig, PipelineConfig)

### Secondary (MEDIUM confidence)
- rapidfuzz library: MIT license, C++ backend, token_sort_ratio for company name matching. Used in Phase 22 plan already (referenced in ROADMAP.md).
- HubSpot SDK search API: `query` parameter does full-text search. Based on existing usage in `src/ingest/hubspot.py` lines 229-237 and 328-337.

### Tertiary (LOW confidence)
- HubSpot API rate limits for private app tokens (100 calls/10s for search) -- based on general HubSpot documentation knowledge, needs verification for this specific account tier.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in project, only rapidfuzz is new (well-known, referenced in ROADMAP.md for Phase 22)
- Architecture: HIGH -- integration points are clear, patterns established by Phase 14/17/19
- Pitfalls: HIGH -- based on direct codebase analysis (sparse sidecars, model constraints, existing patterns)

**Research date:** 2026-04-06
**Valid until:** 2026-05-06 (stable domain, no fast-moving dependencies)
