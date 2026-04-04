# Phase 10: Cross-Source Synthesis + Commitments - Research

**Researched:** 2026-04-04
**Domain:** LLM-based cross-source deduplication, structured commitment extraction, prompt engineering
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Conservative merging only -- merge when clearly the same topic (same project, same people, same decision). Err on showing two items rather than losing detail
- When sources have conflicting details (e.g., different dates), show both with inline attribution -- let the reader resolve
- Narrative merge style -- one coherent paragraph/bullet weaving both sources together with inline attribution like "(per standup)" and "(per Slack #channel)"
- Dedup logic integrated into the synthesis prompt itself (one LLM pass), not a separate post-synthesis dedup step
- Explicit commitments only -- someone clearly says they'll do something ("I'll send the deck by Friday", "John will follow up"). No implied obligations
- Extract everyone's commitments, not just the user's -- full picture of what was promised across all participants
- Normalize vague deadlines to actual dates where possible: "next week" -> date range, "by end of day" -> specific date. Leave truly vague ones ("soon") as text
- Deduplicate commitments across sources -- same commitment discussed in meeting AND Slack appears once with multi-source attribution
- Dedicated "## Commitments" section at the TOP of the daily summary, before detailed activity sections -- high visibility
- Table format with columns: Who | What | By When | Source
- Inline parenthetical attribution for consolidated activity items: "...project timeline updated (per standup, per Slack #proj-alpha)"
- Commitments array with core fields only: `who`, `what`, `by_when` (ISO date string or text like "unspecified"), `source` (array of attribution strings)
- Final output only in sidecar -- no merge lineage or consolidated_topics tracking
- Low-confidence dedup matches: keep items separate
- Partial commitments: include with gaps marked -- who = "TBD" or by_when = "unspecified"
- Single-source days: always run the full pipeline regardless of source count
- Pipeline runs the same synthesis prompt whether 1 source or 5

### Claude's Discretion
- Exact prompt engineering for dedup instructions within the synthesis prompt
- Confidence threshold tuning for what constitutes "clearly the same topic"
- Table formatting details (column widths, date formatting in table)
- How to handle commitments that reference future dates beyond the current day

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SYNTH-06 | Cross-source deduplication handled at synthesis time via LLM (same topic across sources = one consolidated item) | Prompt engineering pattern for single-pass dedup within synthesis prompt; conservative merge rules; inline multi-source attribution format |
| SYNTH-08 | Commitment deadlines extracted and structured (who/what/by-when) in synthesis output and JSON sidecar | Claude structured outputs (`output_config`) for guaranteed JSON schema; dual-output prompt pattern (narrative + structured); Commitment model mapping |
</phase_requirements>

## Summary

Phase 10 enhances the existing two-stage synthesis pipeline to handle two new capabilities: (1) cross-source deduplication where the same topic appearing in meetings, Slack, Google Docs, and HubSpot is consolidated into a single item with multi-source attribution, and (2) structured commitment extraction where explicit promises are parsed into who/what/by-when records for both markdown display and JSON sidecar output.

The existing architecture is well-positioned for this. The `synthesize_daily()` function in `src/synthesis/synthesizer.py` already receives all source types (meeting extractions, Slack items, Docs items) and passes them to a single Claude prompt. The current `SYNTHESIS_PROMPT` already contains a basic dedup instruction ("If the same topic came up in multiple meetings, write ONE bullet and list both meetings") and basic commitment extraction ("ALWAYS include the owner name and deadline"). Phase 10 deepens both capabilities: richer dedup instructions with conservative merge rules, and a separate structured output pass for machine-readable commitments.

The key architectural decision is that Claude's structured outputs feature (`output_config.format` with `json_schema` type) should be used for commitment extraction to guarantee valid JSON schema conformance. This avoids brittle regex parsing of LLM output. The synthesis prompt handles both dedup and narrative output in a single pass (locked decision), while a lightweight second call extracts structured commitments from the already-synthesized output.

**Primary recommendation:** Enhance the existing synthesis prompt with explicit dedup rules and attribution format instructions, then add a second lightweight Claude call using `output_config` structured outputs to extract commitments as guaranteed-valid JSON.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | >=0.45.0 (upgrade to latest for `output_config`) | Claude API with structured outputs | Already in use; structured outputs GA for schema-enforced JSON extraction |
| pydantic | >=2.12.5 | Schema definitions for commitments, sidecar models | Already in use; integrates with `client.messages.parse()` for Pydantic-to-JSON-schema |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-dateutil | >=2.9.0 | Relative date parsing ("next Tuesday", "end of week") | Normalizing vague deadline text to ISO dates |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Structured outputs (`output_config`) | Regex parsing of markdown output | Structured outputs guarantee valid JSON; regex is fragile with LLM output variations |
| Second Claude call for commitments | Single prompt returning both markdown + JSON | Two calls is cleaner separation of concerns; the narrative prompt stays readable; the structured call is cheap (small input from already-synthesized text) |
| `python-dateutil` for date normalization | LLM-only normalization in the prompt | dateutil provides deterministic parsing; use LLM for interpretation ("next week") and dateutil for validation |

**Installation:**
```bash
# Ensure anthropic supports output_config (GA in recent versions)
pip install --upgrade anthropic
```

## Architecture Patterns

### Recommended Project Structure
```
src/
├── synthesis/
│   ├── synthesizer.py    # Enhanced SYNTHESIS_PROMPT with dedup rules (modify existing)
│   ├── commitments.py    # NEW: commitment extraction via structured outputs
│   └── prompts.py        # Updated prompt templates
├── models/
│   ├── commitments.py    # Already exists: Commitment model
│   └── sources.py        # Already exists: SourceItem, SourceType
├── sidecar.py            # Enhanced: add commitments array to DailySidecar
└── output/
    └── writer.py         # Enhanced: Commitments table at top of template
templates/
    └── daily.md.j2       # Enhanced: Commitments table before Substance section
```

### Pattern 1: Single-Pass Dedup via Enhanced Synthesis Prompt
**What:** Deduplication is handled entirely within the existing synthesis prompt by adding explicit rules for how to detect and merge cross-source topics. No separate dedup step or post-processing.
**When to use:** Always -- this is a locked decision from CONTEXT.md.
**Why it works:** The LLM already sees all sources in context. Adding explicit merge rules leverages its natural ability to recognize semantic similarity across differently-worded references to the same topic.

**Prompt enhancement pattern:**
```python
# Add to SYNTHESIS_PROMPT in synthesizer.py
DEDUP_INSTRUCTIONS = """
CROSS-SOURCE DEDUPLICATION RULES:
- When the SAME topic appears in multiple sources (meeting, Slack, Google Docs, HubSpot), write ONE consolidated bullet that weaves together details from all sources.
- "Same topic" means: same project AND same specific issue/decision/action. Two items mentioning "Project Alpha" are NOT automatically the same topic -- they must discuss the same specific aspect.
- Append ALL source attributions inline: "Timeline moved to Q3 (per standup, per Slack #proj-alpha)"
- When sources give CONFLICTING details on the same topic, include BOTH details with per-source attribution: "Launch date set to March 15 (per standup) vs March 22 (per Slack #releases)"
- When UNCERTAIN if two items are the same topic, keep them SEPARATE. Two similar-but-distinct items are better than one incorrectly merged item.
- Never merge items from different projects, even if they discuss similar themes.
"""
```

### Pattern 2: Structured Commitment Extraction via Second Claude Call
**What:** After the narrative synthesis completes, make a second Claude API call using `output_config` structured outputs to extract commitments as guaranteed-valid JSON from the synthesized text.
**When to use:** Every pipeline run, regardless of source count.
**Why two calls:** The narrative synthesis prompt is already complex. Asking it to simultaneously produce both freeform narrative and strict JSON in one response degrades quality of both. The second call is cheap -- it operates on the already-synthesized text (small input) and uses structured outputs for guaranteed schema conformance.

```python
# src/synthesis/commitments.py
from pydantic import BaseModel, Field
from datetime import date
import anthropic

class ExtractedCommitment(BaseModel):
    who: str  # Person name, or "TBD" if unclear
    what: str  # The commitment description
    by_when: str  # ISO date string, date range, or "unspecified"
    source: list[str]  # e.g. ["standup", "Slack #proj-alpha"]
    confidence: str = "high"  # "high" or "partial"

class CommitmentsOutput(BaseModel):
    commitments: list[ExtractedCommitment] = Field(default_factory=list)

COMMITMENT_EXTRACTION_PROMPT = """Extract ALL explicit commitments from this daily summary.

Date context: {target_date}

A commitment is when someone EXPLICITLY says they will do something:
- "I'll send the deck by Friday" -> YES
- "John will follow up with the vendor" -> YES
- "We should probably look into that" -> NO (not explicit)
- "The report needs updating" -> NO (no owner committed)

For each commitment:
- who: The person who committed. Use first name. If unclear, use "TBD".
- what: What they committed to do. Be concise.
- by_when: Normalize deadlines relative to {target_date}:
  - "by Friday" -> the next Friday's ISO date
  - "next week" -> "week of YYYY-MM-DD"
  - "end of day" -> "{target_date}"
  - "soon" or no deadline stated -> "unspecified"
- source: Array of source attributions exactly as they appear in the text (e.g., "standup", "Slack #proj-alpha")
- confidence: "high" if who, what, and source are all clear. "partial" if any field is uncertain.

RULES:
- Extract EVERYONE's commitments, not just the user's
- If the SAME commitment appears attributed to multiple sources, list it ONCE with all sources
- Include partial commitments with gaps marked (who="TBD", by_when="unspecified")
- Do NOT invent commitments that aren't explicitly stated

Summary to extract from:
{synthesis_text}
"""

def extract_commitments(
    synthesis_text: str,
    target_date: date,
    config: dict,
) -> list[ExtractedCommitment]:
    client = anthropic.Anthropic()
    synthesis_config = config.get("synthesis", {})
    model = synthesis_config.get("model", "claude-sonnet-4-20250514")

    prompt = COMMITMENT_EXTRACTION_PROMPT.format(
        target_date=target_date.isoformat(),
        synthesis_text=synthesis_text,
    )

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": CommitmentsOutput.model_json_schema(),
            }
        },
    )

    import json
    data = json.loads(response.content[0].text)
    result = CommitmentsOutput.model_validate(data)
    return result.commitments
```

### Pattern 3: Enhanced Sidecar with Commitments Array
**What:** Extend the existing `DailySidecar` model to include a `commitments` array alongside the existing `tasks` and `decisions` arrays.
**When to use:** Every pipeline run.

```python
# Addition to src/sidecar.py
class SidecarCommitment(BaseModel):
    who: str
    what: str
    by_when: str  # ISO date, date range text, or "unspecified"
    source: list[str]

# Add to DailySidecar:
# commitments: list[SidecarCommitment] = Field(default_factory=list)
```

### Pattern 4: Template Reordering for Commitments-First Display
**What:** Move the Commitments section to the top of the daily summary template (after Overview, before Substance) and render as a table.
**When to use:** Always -- locked decision from CONTEXT.md.

### Anti-Patterns to Avoid
- **Merging in post-processing:** Do NOT build a separate dedup pass that runs after synthesis. The user explicitly locked the decision to handle dedup within the synthesis prompt itself.
- **Implied commitment extraction:** Do NOT extract commitments where someone just mentions something should happen. Only explicit "I will" / "X will" statements qualify.
- **Single mega-prompt for narrative + JSON:** Do NOT try to get both the narrative markdown and structured JSON commitments from a single prompt. This degrades both outputs. Use two calls.
- **Aggressive deduplication:** Do NOT merge items just because they mention the same project. They must discuss the same specific topic/decision/action within that project.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON schema enforcement | Regex/string parsing of LLM JSON output | Claude `output_config` structured outputs | Constrained decoding guarantees valid JSON; eliminates retry loops for malformed output |
| Relative date resolution | Custom date math for "next Tuesday", "end of week" | `python-dateutil` relativedelta + LLM interpretation | dateutil handles calendar math edge cases (month boundaries, leap years); LLM interprets natural language |
| Pydantic-to-JSON-Schema conversion | Manual JSON schema writing | `Model.model_json_schema()` | Pydantic auto-generates valid JSON Schema from model definitions; single source of truth |
| Cross-source topic matching | Custom embedding similarity / TF-IDF matching | LLM in-prompt dedup instructions | The LLM already has all sources in context; semantic understanding beats keyword matching for "same topic" detection; locked decision |

**Key insight:** This phase is primarily prompt engineering and pipeline wiring, not library integration. The heavy lifting is done by Claude's natural language understanding (for dedup) and structured outputs (for commitment extraction). The code changes are about getting the right instructions to the LLM and routing the structured output to the right places.

## Common Pitfalls

### Pitfall 1: Over-Merging Distinct Items
**What goes wrong:** The dedup instructions are too aggressive, causing the LLM to merge items that mention the same project but discuss different aspects (e.g., "Project Alpha budget discussion" merged with "Project Alpha timeline review").
**Why it happens:** Dedup rules use project name as the sole matching criterion instead of requiring topic-level specificity.
**How to avoid:** The dedup prompt must explicitly state that items need to share the same *specific issue/decision/action*, not just the same project. Include negative examples in the prompt.
**Warning signs:** Review output for days with many sources -- if consolidation reduces item count by >50%, merging is likely too aggressive.

### Pitfall 2: Phantom Commitments from Suggestions
**What goes wrong:** The LLM extracts "We should look into X" or "It would be good to Y" as commitments, inflating the commitments table with non-binding suggestions.
**Why it happens:** Without strict definitions, LLMs tend to over-extract. The boundary between "suggestion" and "commitment" is fuzzy.
**How to avoid:** The extraction prompt must include explicit negative examples: "We should probably..." -> NO. "It would be good to..." -> NO. Only "I will" / "X will" / "X agreed to" qualify. The `confidence: "partial"` field helps surface uncertain cases.
**Warning signs:** More than 10 commitments per day is suspicious. Review for vague language.

### Pitfall 3: Date Normalization Inconsistency
**What goes wrong:** "Next Tuesday" resolves to different dates depending on whether the synthesis runs on the target date or later. "End of week" is ambiguous (Friday? Sunday?).
**Why it happens:** The LLM doesn't know what day "today" is unless explicitly told. Relative dates need an anchor.
**How to avoid:** Always pass `target_date` to the commitment extraction prompt so the LLM has an anchor. Define conventions: "end of week" = Friday, "next week" = Monday of the following week. Use `python-dateutil` to validate the LLM's date math.
**Warning signs:** Dates in the past appearing as deadlines (the LLM miscalculated).

### Pitfall 4: Sidecar Schema Breaking Existing Consumers
**What goes wrong:** Adding `commitments` array to `DailySidecar` changes the JSON schema, potentially breaking anything that consumes the existing sidecar format.
**Why it happens:** New fields added without considering backward compatibility.
**How to avoid:** The `commitments` field should have `default_factory=list` so existing sidecar files without it still validate. The field is additive -- it doesn't modify existing fields.
**Warning signs:** Test that existing sidecar JSON files still deserialize correctly after model changes.

### Pitfall 5: Token Budget Overflow with Many Sources
**What goes wrong:** With meetings + Slack + HubSpot + Google Docs all feeding into one prompt, the input exceeds the context window or the model's attention degrades on key details.
**Why it happens:** Each source type adds substantial text to the prompt. A busy day with 8 meetings, 20 Slack threads, HubSpot activity, and doc edits can easily reach 50K+ tokens.
**How to avoid:** Monitor input token counts. The existing pipeline already truncates doc content to 200 chars in the prompt. Ensure similar limits exist for all source types. If token counts regularly exceed 100K, consider pre-summarization of low-priority sources.
**Warning signs:** Synthesis output becomes vague or misses items from sources that appear late in the prompt.

### Pitfall 6: Structured Output Schema Compatibility
**What goes wrong:** The `output_config` feature requires specific JSON Schema constraints (e.g., `additionalProperties: false` at all levels, no unsupported keywords). Schema compilation fails silently or at runtime.
**Why it happens:** Pydantic's `model_json_schema()` output may include features not supported by Claude's schema compiler.
**How to avoid:** Test the generated schema against the API before relying on it. Keep models simple (no unions, no complex nested optional types). Add `model_config = ConfigDict(extra="forbid")` to Pydantic models used with structured outputs.
**Warning signs:** API errors mentioning schema compilation or unsupported schema features.

## Code Examples

### Enhanced Synthesis Prompt with Dedup Rules
```python
# Source: existing synthesizer.py pattern + CONTEXT.md requirements
SYNTHESIS_PROMPT = """You are producing a daily intelligence brief. Be concise. Every word must earn its place.

Date: {date}
Number of meetings with transcripts: {transcript_count}
Number of Slack sources: {slack_source_count}
Number of Google Docs sources: {docs_source_count}
Number of HubSpot sources: {hubspot_source_count}

{extractions_text}

{slack_items_text}

{docs_items_text}

{hubspot_items_text}

{priority_context}

CROSS-SOURCE DEDUPLICATION:
- When the SAME specific topic appears across multiple sources, consolidate into ONE item.
- "Same topic" = same project + same specific issue/decision/action. NOT just same project name.
- Append all source attributions: "Timeline moved to Q3 (per standup, per Slack #proj-alpha)"
- CONFLICTING details: show both with attribution: "Launch March 15 (per standup) vs March 22 (per Slack #releases)"
- UNCERTAIN matches: keep SEPARATE. Two items > one incorrectly merged item.

Produce a daily summary with these exact sections:

## Commitments
One row per commitment. Extract ONLY explicit commitments (someone clearly said they will do something).
Include everyone's commitments, not just the user's.

| Who | What | By When | Source |
|-----|------|---------|--------|
| [First name] | [What they committed to] | [Normalized date or "unspecified"] | [Source attribution(s)] |

{executive_summary_instruction}## Substance
[... existing substance instructions ...]

## Decisions
[... existing decisions instructions ...]

CRITICAL RULES:
[... existing rules, enhanced with dedup ...]
- COMMITMENTS TABLE: Every row must have a Who. Use "TBD" if unclear. Normalize dates relative to {date}.
- DEDUP COMMITMENTS: Same commitment in meeting AND Slack = one row with both sources.
"""
```

### Commitment Extraction with Structured Outputs
```python
# Source: Anthropic structured outputs docs (https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
import json
import anthropic
from pydantic import BaseModel, Field

class ExtractedCommitment(BaseModel):
    who: str
    what: str
    by_when: str
    source: list[str]

class CommitmentsOutput(BaseModel):
    commitments: list[ExtractedCommitment] = Field(default_factory=list)

client = anthropic.Anthropic()
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    messages=[{"role": "user", "content": prompt}],
    output_config={
        "format": {
            "type": "json_schema",
            "schema": CommitmentsOutput.model_json_schema(),
        }
    },
)
data = json.loads(response.content[0].text)
result = CommitmentsOutput.model_validate(data)
```

### Enhanced Sidecar Model
```python
# Extension of existing src/sidecar.py
class SidecarCommitment(BaseModel):
    who: str
    what: str
    by_when: str  # ISO date, "week of YYYY-MM-DD", or "unspecified"
    source: list[str]  # ["standup", "Slack #proj-alpha"]

class DailySidecar(BaseModel):
    date: str
    generated_at: str
    meeting_count: int
    transcript_count: int
    tasks: list[SidecarTask] = Field(default_factory=list)
    decisions: list[SidecarDecision] = Field(default_factory=list)
    commitments: list[SidecarCommitment] = Field(default_factory=list)  # NEW
    source_meetings: list[SidecarMeeting] = Field(default_factory=list)
```

### Template Reordering (daily.md.j2)
```jinja2
# Daily Summary: {{ date }}

## Overview
{{ meeting_count }} meetings, {{ "%.1f"|format(total_meeting_hours) }}h, {{ transcript_count }} transcripts.

{% if commitment_rows %}
## Commitments

| Who | What | By When | Source |
|-----|------|---------|--------|
{% for c in commitment_rows %}
| {{ c.who }} | {{ c.what }} | {{ c.by_when }} | {{ c.source|join(", ") }} |
{% endfor %}

{% endif %}
{% if executive_summary %}
## Executive Summary
{{ executive_summary }}

{% endif %}
{% if substance.items %}
## Substance
...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Regex parsing of LLM JSON | `output_config` structured outputs | Late 2025 (GA) | Eliminates malformed JSON; no retry loops needed |
| `output_format` parameter (beta) | `output_config.format` parameter (GA) | 2026 | Beta header no longer required; parameter renamed |
| Prompt-only JSON enforcement | Constrained decoding at inference | Late 2025 | Model literally cannot produce tokens violating schema |
| Single-prompt narrative+JSON | Two-call pattern (narrative + structured extraction) | Best practice 2025+ | Better quality for both outputs; separation of concerns |

**Deprecated/outdated:**
- `output_format` parameter: Still works during transition period but replaced by `output_config.format`
- Beta header `structured-outputs-2025-11-13`: No longer required for structured outputs
- Tool-use hack for JSON extraction: `output_config` is the proper mechanism now

## Open Questions

1. **Anthropic SDK version compatibility with `output_config`**
   - What we know: `output_config.format` is GA and requires a recent SDK version. Project pins `>=0.45.0`.
   - What's unclear: Exact minimum SDK version supporting `output_config` (vs old `output_format`).
   - Recommendation: Upgrade to latest anthropic SDK before implementation. Test `output_config` with a simple schema to verify support. Fall back to `output_format` if needed (still works during transition).

2. **Pydantic `model_json_schema()` compatibility with Claude's schema compiler**
   - What we know: Claude's structured outputs support standard JSON Schema with some limitations (no `$ref`, no `patternProperties`).
   - What's unclear: Whether Pydantic's generated schema for `CommitmentsOutput` will pass Claude's schema compiler without modification.
   - Recommendation: Test early. If Pydantic generates unsupported constructs, manually define the JSON schema dict instead of using `model_json_schema()`.

3. **Token budget on busy multi-source days**
   - What we know: The synthesis prompt receives all sources concatenated. Each source type adds text.
   - What's unclear: Typical token counts for a busy day with all 4+ source types active.
   - Recommendation: Add token counting (via `response.usage`) and log warnings if input exceeds 80K tokens. Implement truncation strategy for the largest source groups if needed.

## Sources

### Primary (HIGH confidence)
- Anthropic Structured Outputs docs (https://platform.claude.com/docs/en/build-with-claude/structured-outputs) - `output_config.format` syntax, Python SDK integration, JSON schema requirements, GA status
- Existing codebase analysis - `src/synthesis/synthesizer.py`, `src/sidecar.py`, `src/models/commitments.py`, `src/models/sources.py`
- CONTEXT.md locked decisions - All dedup and commitment extraction architectural choices

### Secondary (MEDIUM confidence)
- Anthropic SDK Pydantic integration pattern (`client.messages.parse()`) - Referenced in official docs, but not yet tested against project's Pydantic version
- Two-call pattern (narrative + structured extraction) - Common pattern in LLM applications, verified by multiple sources

### Tertiary (LOW confidence)
- Token budget estimates for busy multi-source days - Based on general estimation, not measured against actual pipeline data

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Using existing libraries (anthropic, pydantic) with documented new features
- Architecture: HIGH - Enhancement of existing well-understood pipeline; locked decisions from user eliminate ambiguity
- Pitfalls: HIGH - Based on direct codebase analysis and known LLM behavior patterns
- Prompt engineering: MEDIUM - Dedup prompt instructions are well-reasoned but will need tuning with real data

**Research date:** 2026-04-04
**Valid until:** 2026-05-04 (30 days - stable domain, locked decisions)
