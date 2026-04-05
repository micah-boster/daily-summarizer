# Phase 14: Structured Output Migration - Context

**Gathered:** 2026-04-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace brittle regex/markdown parsing of Claude API responses with `json_schema` structured outputs and Pydantic response models. Per-meeting extraction and daily synthesis both get typed output models. ~234 lines of regex parsing in extractor.py and synthesizer.py are deleted.

</domain>

<decisions>
## Implementation Decisions

### Output model design
- Mirror current extracted fields — MeetingExtractionOutput matches what regex currently extracts (decisions, commitments, substance, etc. as lists)
- DailySynthesisOutput uses a named section list pattern: `List[Section(name, content)]` — flexible if section names evolve
- Include metadata fields: model_id, token_usage, timestamp for debugging/auditing
- All output models live in a dedicated models module (e.g., `models/outputs.py` or `schemas/outputs.py`)

### Migration sequencing
- Extraction first, then synthesis — migrate per-meeting extraction, validate, then tackle daily synthesis
- Two separate plans: 14-01 for extraction migration, 14-02 for synthesis migration
- Claude's Discretion: whether to delete old regex immediately or use a brief flag period; validation approach (golden file vs semantic comparison)

### Edge cases & fallbacks
- On structured output validation failure: retry once with corrective prompt, then raise error
- Allow mostly-empty fields — not every meeting produces decisions/commitments (empty lists are valid)
- Dedicated logging for structured output errors: log raw API response alongside validation error, separate log category
- If a single meeting extraction fails, skip it and continue — synthesize from whatever succeeded, log the failure

### Prompt engineering
- Detailed field descriptions with examples in the JSON schema — help Claude understand expected format per field
- Restructure existing prompts for structured output — not just a format swap, but rewrite for optimal json_schema performance
- Use enum constraints where fields have known categories (e.g., decision types, commitment urgency)
- Include a reasoning/scratchpad field in the schema — Claude fills this first to improve extraction quality, then it's discarded downstream

### Claude's Discretion
- Exact validation approach for old vs new output equivalence
- Whether to delete regex code immediately or keep briefly behind a flag
- Compression algorithm for the scratchpad field (keep vs discard)
- Exact enum values for constrained fields

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

*Phase: 14-structured-output-migration*
*Context gathered: 2026-04-05*
