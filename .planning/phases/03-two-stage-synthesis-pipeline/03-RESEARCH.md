# Phase 3: Two-Stage Synthesis Pipeline - Research

**Researched:** 2026-04-03
**Domain:** LLM-based meeting transcript extraction and cross-meeting synthesis
**Confidence:** HIGH

## Summary

Phase 3 introduces the core intelligence layer: a two-stage pipeline where Stage 1 runs per-meeting extraction (decisions, commitments, substance, open questions, tensions) from each transcript, and Stage 2 merges those extractions into a daily synthesis organized by the three core questions. The pipeline uses the Anthropic Python SDK to send transcript text to Claude with carefully designed prompts. The key technical challenges are: (1) prompt engineering that produces structured, evidence-only output with source attribution, (2) handling variable transcript lengths within Claude's context window, (3) enforcing zero evaluative language through both prompt design and post-processing validation.

The existing codebase already has: NormalizedEvent with transcript_text attached, DailySynthesis with Section models (Substance, Decisions, Commitments), a Jinja2 template with those three sections, and a main.py pipeline that currently creates empty sections. Phase 3 fills those sections with LLM-extracted content and updates the template to support per-meeting appendices.

**Primary recommendation:** Use the Anthropic Python SDK directly with structured prompts (not function calling) for extraction, Pydantic for response validation, and a post-processing validator that rejects evaluative language before writing output.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Extract five categories per meeting: decisions, tasks/commitments, substance, open questions, and tensions/disagreements
- Signal-filtered granularity: capture items that would matter if missed, skip trivial scheduling decisions and low-signal chatter
- Daily synthesis organized by question: three sections -- Substance, Decisions, Commitments
- Structured multi-line bullets within each section: item, who, rationale/context, source
- Executive summary (3-5 sentences) auto-included only on busy days with 5+ meetings that have transcripts; omitted on lighter days
- Neutral reporter tone: facts only, no editorializing or implications
- Inline parenthetical attribution on every item: "(Meeting Title -- Key Participants)"
- Citation includes meeting title and key participants involved in that specific item
- When an item pulls from multiple meetings, list all sources
- Per-meeting appendix includes relative file path links to cached raw transcripts in `output/raw/`
- Meetings without transcripts: listed in a separate "Meetings without transcripts" section
- Short meetings (under 10 min): full extraction treatment regardless of duration

### Claude's Discretion
- Rationale preservation depth per decision (one-line vs. full reasoning chain)
- Adapting extraction structure for 1:1s vs. group meetings based on content
- Whether to flag recurrence patterns in extraction metadata
- Loading skeleton / empty state handling for days with no meetings
- Exact prompt engineering approach for evidence-only enforcement

### Deferred Ideas (OUT OF SCOPE)
- None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SYNTH-01 | Daily synthesis answering: What happened of substance today? | Stage 1 extraction of substance category + Stage 2 cross-meeting merge into Substance section |
| SYNTH-02 | Daily synthesis answering: What decisions were made, by whom, with what rationale? | Stage 1 extraction of decisions with participant attribution + Stage 2 merge into Decisions section |
| SYNTH-03 | Daily synthesis answering: What tasks/commitments were created, completed, or deferred? | Stage 1 extraction of tasks/commitments with owners + Stage 2 merge into Commitments section |
| SYNTH-04 | Prompt engineering that enforces evidence-only framing (no evaluative language) | Evidence-only prompt patterns + post-processing validator (banned phrases, sentiment heuristics) |
| OUT-02 | Source linking: each summary item traces back to the specific transcript or calendar event | Inline parenthetical attribution pattern in both extraction and synthesis prompts |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | >=0.45.0 | Claude API client for extraction and synthesis | Official Anthropic Python SDK; this project uses Claude as its LLM |
| pydantic | >=2.12.5 | Response validation and data models | Already in project; validates extraction output structure |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| jinja2 | >=3.1.6 | Template rendering for updated daily output | Already in project; extend template for synthesis sections and appendix |
| pyyaml | >=6.0.3 | Configuration for prompt templates and synthesis settings | Already in project; add synthesis config section |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Raw API calls | LangChain/LlamaIndex | Overkill for two-prompt pipeline; adds complexity without value |
| Pydantic validation | JSON schema validation | Pydantic already in project, provides better error messages |
| Claude structured output | OpenAI function calling | Project is Claude-native; use native response parsing |

**Installation:**
```bash
pip install anthropic>=0.45.0
```

## Architecture Patterns

### Recommended Module Structure
```
src/
├── synthesis/
│   ├── __init__.py
│   ├── extractor.py      # Stage 1: per-meeting extraction
│   ├── synthesizer.py    # Stage 2: daily cross-meeting synthesis
│   ├── prompts.py        # Prompt templates (extraction + synthesis)
│   ├── models.py         # Pydantic models for extraction/synthesis output
│   └── validator.py      # Evidence-only language enforcement
├── models/
│   └── events.py         # Updated DailySynthesis + new extraction models
├── output/
│   └── writer.py         # Updated for synthesis sections + appendix
└── main.py               # Updated pipeline: ingest -> extract -> synthesize -> write
```

### Pattern 1: Two-Stage Pipeline Architecture
**What:** Stage 1 runs independently per meeting (parallelizable), producing structured extractions. Stage 2 consumes all extractions and produces the daily synthesis.
**When to use:** Always -- this is the core architecture decision from the roadmap.
**Implementation:**

Stage 1 (Extractor):
- Input: One NormalizedEvent with transcript_text
- Output: MeetingExtraction (Pydantic model) with decisions, commitments, substance, open_questions, tensions
- Each extraction item includes: content, participants involved, rationale (if stated)
- One Claude API call per meeting with transcript

Stage 2 (Synthesizer):
- Input: List of MeetingExtraction objects for the day
- Output: Updated DailySynthesis with filled Substance, Decisions, Commitments sections
- Each synthesis item includes inline source attribution
- Conditional executive summary (5+ transcript meetings)
- One Claude API call for the daily synthesis

### Pattern 2: Prompt-as-Configuration
**What:** Store prompts as Jinja2 templates in a `prompts/` directory or as string constants in prompts.py, parameterized with meeting data.
**When to use:** For both extraction and synthesis prompts.
**Why:** Enables prompt iteration without code changes. Prompts are the highest-leverage tuning surface in this pipeline.

### Pattern 3: Structured Output via Markdown Parsing
**What:** Ask Claude to respond in a specific markdown format, then parse the response into Pydantic models. Do NOT use JSON mode or tool_use for this -- structured markdown is more natural for Claude and easier to debug.
**When to use:** For extraction responses.
**Why:** Meeting extractions are semi-structured text. Claude produces better quality extraction in markdown format than in forced JSON. Parse the markdown sections into Pydantic models after receiving the response.

### Anti-Patterns to Avoid
- **Cramming all meetings into one prompt:** Each meeting extraction should be a separate API call. Cross-meeting synthesis is a separate stage.
- **Evaluative language in prompts:** Never include language like "assess", "evaluate", "rate" in prompts. Use "extract", "identify", "list", "quote".
- **Ignoring empty transcripts:** Events without transcripts should be listed separately, not passed to extraction.
- **Hardcoded prompts in business logic:** Keep prompts separate from pipeline logic for iterability.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Claude API communication | HTTP client wrapper | `anthropic` Python SDK | Handles auth, retries, streaming, error types |
| Response validation | Manual JSON parsing | Pydantic models + markdown parser | Type safety, validation errors, serialization |
| Evaluative language detection | Simple string matching | Regex patterns + curated banned phrase list | Needs to catch subtle evaluative language (see Pitfalls) |

## Common Pitfalls

### Pitfall 1: Evaluative Language Leaking Through
**What goes wrong:** Claude includes phrases like "productive meeting", "good progress", "strong leadership" despite instructions not to.
**Why it happens:** Claude's training data is full of evaluative language in meeting summaries.
**How to avoid:** Three-layer defense: (1) Explicit negative examples in the prompt, (2) Role framing as "court reporter" not "analyst", (3) Post-processing validator that catches banned phrases and patterns.
**Warning signs:** Any adjective applied to a person or their performance.

### Pitfall 2: Attribution Drift in Synthesis
**What goes wrong:** During Stage 2 synthesis, source attribution becomes vague ("in several meetings") or is dropped entirely.
**Why it happens:** When combining items from multiple meetings, Claude may summarize away the specifics.
**How to avoid:** Require the synthesis prompt to preserve inline citations from Stage 1. The synthesis prompt must explicitly say "every item MUST include its source meeting in parentheses."
**Warning signs:** Any synthesis item without a parenthetical citation.

### Pitfall 3: Context Window Overflow
**What goes wrong:** Very long transcripts (1-2 hour meetings) exceed context limits or degrade extraction quality.
**Why it happens:** Full verbatim transcripts can be 50K+ tokens for long meetings.
**How to avoid:** Truncate transcripts that exceed a configurable token limit (e.g., 80K tokens for a single extraction call, leaving room for the prompt and response). Log a warning when truncation occurs. Consider using Claude's 200K context for extraction calls.
**Warning signs:** API errors or noticeably worse extraction quality for long meetings.

### Pitfall 4: Empty/Low-Signal Extraction
**What goes wrong:** Meetings with thin transcripts (e.g., "Hey, can you hear me? Let's reschedule.") produce extraction noise.
**Why it happens:** The pipeline treats all transcripts equally.
**How to avoid:** After extraction, check if the extraction has any substantive content. If all categories are empty or minimal, mark the meeting as "low-signal" in the appendix rather than including empty extractions in synthesis.
**Warning signs:** Extraction with zero items across all categories.

## Code Examples

### Anthropic SDK Usage Pattern
```python
import anthropic

client = anthropic.Anthropic()  # Uses ANTHROPIC_API_KEY env var

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    messages=[
        {"role": "user", "content": prompt}
    ],
)
text = response.content[0].text
```

### Extraction Pydantic Model Pattern
```python
from pydantic import BaseModel, Field

class ExtractionItem(BaseModel):
    content: str
    participants: list[str] = Field(default_factory=list)
    rationale: str | None = None

class MeetingExtraction(BaseModel):
    meeting_title: str
    meeting_time: str
    decisions: list[ExtractionItem] = Field(default_factory=list)
    commitments: list[ExtractionItem] = Field(default_factory=list)
    substance: list[ExtractionItem] = Field(default_factory=list)
    open_questions: list[ExtractionItem] = Field(default_factory=list)
    tensions: list[ExtractionItem] = Field(default_factory=list)
```

### Evidence-Only Validator Pattern
```python
BANNED_PATTERNS = [
    r"\b(?:productive|effective|impressive|excellent|poor|weak|strong)\b",
    r"\b(?:good|great|bad|terrible|wonderful|awful)\s+(?:job|work|effort|performance|leadership)\b",
    r"\b(?:seemed|appeared|felt)\s+(?:to be|like)\b",
    r"\b(?:clearly|obviously|unfortunately|fortunately)\b",
]

def validate_evidence_only(text: str) -> list[str]:
    """Return list of violations found in text."""
    violations = []
    for pattern in BANNED_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            violations.extend(matches)
    return violations
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| JSON mode for structured LLM output | Markdown-based extraction with Pydantic parsing | 2025 | Better quality extraction, more natural output |
| Single-shot full-day synthesis | Two-stage (extract then synthesize) | Standard pattern | Required by roadmap; enables per-meeting audit trail |
| Prompt-and-pray for tone control | Prompt + post-processing validator | Standard pattern | Reliable evidence-only enforcement |

## Open Questions

1. **Claude model selection for extraction vs. synthesis**
   - What we know: Sonnet is fast/cheap for extraction; Opus is better for nuanced synthesis
   - What's unclear: Whether Sonnet extraction quality is sufficient for this use case
   - Recommendation: Start with Sonnet for both (configurable in config.yaml), upgrade if quality insufficient

2. **Transcript token limit threshold**
   - What we know: Claude supports 200K context; typical 1-hour meeting transcript is ~15-25K tokens
   - What's unclear: Optimal truncation threshold that balances quality vs. completeness
   - Recommendation: Set default at 80K tokens per extraction call, configurable

3. **Rate limiting for high-meeting days**
   - What we know: Anthropic API has rate limits; busy days could have 10+ meetings with transcripts
   - What's unclear: Whether sequential calls are fast enough or need async
   - Recommendation: Start with sequential (simpler), add async if needed. Each extraction call should complete in 5-15 seconds.

## Sources

### Primary (HIGH confidence)
- Anthropic Python SDK documentation -- API client patterns, message creation
- Existing codebase analysis -- src/models/events.py, src/main.py, src/output/writer.py, src/ingest/normalizer.py
- CONTEXT.md user decisions -- locked decisions for extraction categories, output format, citation style

### Secondary (MEDIUM confidence)
- LLM meeting summarization patterns -- two-stage extraction is a well-established pattern in production meeting intelligence tools
- Evidence-only enforcement techniques -- prompt engineering + post-processing validation is standard for tone control

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- Anthropic SDK is the obvious choice for a Claude-native project
- Architecture: HIGH -- Two-stage pipeline is mandated by roadmap and well-understood
- Pitfalls: HIGH -- Common LLM extraction issues are well-documented from training data and practitioner experience

**Research date:** 2026-04-03
**Valid until:** 2026-05-03 (stable domain, 30-day validity)
