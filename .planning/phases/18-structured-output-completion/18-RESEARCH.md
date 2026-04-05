# Phase 18: Structured Output Completion - Research

**Researched:** 2026-04-05
**Domain:** Claude API structured outputs migration (weekly.py, monthly.py)
**Confidence:** HIGH

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| STRUCT-01 | All Claude API call sites migrated from markdown response parsing to structured outputs (json_schema) with Pydantic model validation | Established pattern in extractor.py/synthesizer.py/commitments.py; new Pydantic output models needed for weekly and monthly; beta header fallback removal; dead import cleanup |
</phase_requirements>

## Summary

Phase 14 migrated extractor.py and synthesizer.py to Claude structured outputs (`json_schema` constrained decoding via `output_config`), but missed two call sites: `weekly.py` and `monthly.py`. Both files still use a plain `_call_claude_with_retry` function that sends a prompt and receives free-text markdown, then parses the response with fragile regex/string-splitting logic (`_parse_weekly_response` and `_parse_monthly_response`). This is the last gap blocking STRUCT-01 completion.

Additionally, three files (extractor.py, synthesizer.py, commitments.py) retain a beta header fallback using `output-format-2025-01-24`, which the Anthropic API now rejects with 400 errors. This fallback path must be removed. Finally, pipeline.py has a dead import of `dedup_source_items` that is only used in `pipeline_async.py`.

**Primary recommendation:** Replicate the exact structured output pattern from extractor.py/synthesizer.py into weekly.py and monthly.py -- create new Pydantic output models, use `output_config` for the API call, parse JSON with `model_validate`, and remove the old regex parsers. Simultaneously remove the deprecated beta header fallback from all three already-migrated files and clean up the dead import.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | >=0.45.0,<1.0 | Claude API client | Project dependency; `output_config` parameter is the GA structured output interface |
| pydantic | v2 (BaseModel) | JSON schema generation + response validation | Already used throughout `src/synthesis/models.py` |
| tenacity | (via retry.py) | Retry decorator for API calls | Already wired into all Claude call sites |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| json (stdlib) | n/a | Parse structured response text | `json.loads(response.content[0].text)` then Pydantic validate |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `output_config` (GA) | Beta header `output-format-2025-01-24` | Beta header is now REJECTED by the API (400 errors) -- must use `output_config` |
| Pydantic `.model_json_schema()` | Hand-crafted JSON schema | Pydantic auto-generates correct schema; hand-crafted is error-prone |

## Architecture Patterns

### Pattern 1: Structured Output API Call (Established in extractor.py)

**What:** Use `output_config` parameter with `json_schema` format type, passing a Pydantic-generated schema. Parse response with `json.loads` + `model_validate`.

**When to use:** Every Claude API call that expects structured data.

**Example from extractor.py (lines 35-47):**
```python
@retry_api_call
def _call_claude_structured_with_retry(client, model, max_tokens, prompt, schema):
    return client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": schema,
            }
        },
    )
```

**Response parsing pattern (extractor.py lines 180-181):**
```python
data = json.loads(response.content[0].text)
output = MeetingExtractionOutput.model_validate(data)
```

### Pattern 2: Output Model with Reasoning Scratchpad

**What:** Pydantic output model includes a `reasoning` field as a scratchpad for Claude's thinking. This field is discarded downstream.

**When to use:** All structured output models where Claude needs to reason before producing structured data.

**Example from models.py (DailySynthesisOutput):**
```python
class DailySynthesisOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reasoning: str = ""  # Scratchpad (discarded downstream)
    # ... structured fields
```

### Pattern 3: Output Model Separate from Domain Model

**What:** API output model (e.g., `MeetingExtractionOutput`) is separate from the domain model (e.g., `MeetingExtraction`). A converter function maps between them, adding metadata not from Claude.

**When to use:** When the domain model has fields (like meeting_title, dates) that come from the caller, not from Claude's output.

**For weekly/monthly:** The existing domain models (`WeeklySynthesis`, `MonthlySynthesis` in `rollups.py`) have fields populated by the caller (week_number, year, start_date, etc.). New output models should only contain fields Claude produces.

### Anti-Patterns to Avoid
- **Regex parsing of Claude output:** Exactly what weekly.py and monthly.py do now. Fragile, breaks on format variations. Structured outputs eliminate this entirely.
- **Beta header fallback:** The `output-format-2025-01-24` header is deprecated and now causes 400 errors. Never use it.
- **Monolithic output model:** Don't put caller-supplied metadata (dates, week numbers) in the Claude output schema. Keep output models focused on what Claude produces.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON schema for API | Hand-craft JSON schema dict | `PydanticModel.model_json_schema()` | Auto-generated, always correct, stays in sync with model |
| Response validation | Manual dict key checking | `PydanticModel.model_validate(data)` | Type coercion, validation errors, extra field rejection |
| Retry logic | Custom retry loops | `@retry_api_call` decorator (already exists) | Consistent retry behavior across all API calls |

## Common Pitfalls

### Pitfall 1: Schema Incompatible with Constrained Decoding
**What goes wrong:** Pydantic generates schemas with features that Claude's json_schema mode may not support (e.g., `$ref`, complex unions, optional types with null).
**Why it happens:** Pydantic v2's schema generation is more complex than what constrained decoding supports.
**How to avoid:** Keep output models flat with simple types. Use `ConfigDict(extra="forbid")`. Test schema generation with `.model_json_schema()` and inspect the result. Avoid deeply nested models.
**Warning signs:** 400 errors from the API with schema validation messages.

### Pitfall 2: Prompt-Schema Mismatch
**What goes wrong:** The prompt asks for one structure but the schema defines another, causing Claude to struggle or produce poor output.
**Why it happens:** The prompt was written for free-text output; the schema is new.
**How to avoid:** Rewrite prompts to match the schema structure exactly. Remove markdown formatting instructions. Add field-level guidance in the prompt that matches schema field names.
**Warning signs:** Empty arrays, default values everywhere, reasoning field doing all the work.

### Pitfall 3: Forgetting to Update Downstream Consumers
**What goes wrong:** The parse functions return different structures after migration, breaking the writer or other consumers.
**Why it happens:** Old regex parsers returned specific dict shapes; new structured output may have different field names or types.
**How to avoid:** Weekly's `synthesize_weekly()` already returns `WeeklySynthesis` model; monthly's `synthesize_monthly()` already returns `MonthlySynthesis` model. The output models should feed into these same domain models. Write converter functions like `_convert_output_to_extraction` in extractor.py.
**Warning signs:** Type errors in writer.py, missing fields in rendered markdown.

### Pitfall 4: Removing Fallback Breaks Older SDK Users
**What goes wrong:** Removing the beta header fallback breaks users on older SDK versions.
**Why it happens:** The fallback was added for SDK version compatibility.
**How to avoid:** The project requires `anthropic>=0.45.0` which supports `output_config`. Removing the fallback is safe. The fallback actively causes 400 errors now anyway.
**Warning signs:** None expected; the fallback is already broken in production.

## Code Examples

### New Pydantic Output Model for Weekly (to create)
```python
class WeeklyThreadOutput(BaseModel):
    """A single thread in Claude's weekly analysis output."""
    model_config = ConfigDict(extra="forbid")

    title: str
    significance: str  # "high" or "medium"
    status: str  # "resolved", "open", "escalated"
    tags: list[str] = Field(default_factory=list)
    progression: str  # Narrative arc
    entries: list[WeeklyThreadEntryOutput] = Field(default_factory=list)

class WeeklyThreadEntryOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day_label: str  # "Monday, March 30" - for date resolution
    category: str  # "decision", "commitment", "substance"
    content: str

class WeeklySynthesisOutput(BaseModel):
    """Structured output model for Claude weekly thread detection."""
    model_config = ConfigDict(extra="forbid")

    reasoning: str = ""
    threads: list[WeeklyThreadOutput] = Field(default_factory=list)
    single_day_items: list[WeeklyThreadEntryOutput] = Field(default_factory=list)
    still_open: list[StillOpenItemOutput] = Field(default_factory=list)

class StillOpenItemOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str
    owner: str | None = None
    since: str | None = None  # ISO date or None
```

### New Pydantic Output Model for Monthly (to create)
```python
class ThematicArcOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    trajectory: str  # "growing", "declining", "stable", "emerging", "resolved"
    weeks_active: list[int] = Field(default_factory=list)
    description: str  # 2-3 sentence analysis
    key_moments: list[str] = Field(default_factory=list)

class MonthlySynthesisOutput(BaseModel):
    """Structured output model for Claude monthly narrative synthesis."""
    model_config = ConfigDict(extra="forbid")

    reasoning: str = ""
    thematic_arcs: list[ThematicArcOutput] = Field(default_factory=list)
    strategic_shifts: list[str] = Field(default_factory=list)
    emerging_risks: list[str] = Field(default_factory=list)
    still_open: list[StillOpenItemOutput] = Field(default_factory=list)
```

### Converter Function Pattern (weekly example)
```python
def _convert_weekly_output(
    output: WeeklySynthesisOutput,
    summaries: list[dict],
) -> tuple[list[WeeklyThread], list[ThreadEntry], list[dict]]:
    """Convert structured API output to domain models."""
    threads = []
    for t in output.threads:
        entries = []
        for e in t.entries:
            entry_date = _resolve_date(e.day_label, summaries)
            entries.append(ThreadEntry(date=entry_date, content=e.content, category=e.category))
        threads.append(WeeklyThread(
            title=t.title, significance=t.significance,
            entries=entries, progression=t.progression,
            status=t.status, tags=t.tags,
        ))
    # ... single_day_items, still_open similarly
    return threads, single_day_items, still_open
```

### Beta Header Removal (in extractor.py, synthesizer.py, commitments.py)
```python
# REMOVE these entire functions:
# _call_claude_structured_fallback_with_retry
# _call_claude_structured_async_fallback_with_retry

# REMOVE try/except fallback blocks like:
# try:
#     response = _call_claude_structured_with_retry(...)
# except (TypeError, anthropic.BadRequestError):
#     response = _call_claude_structured_fallback_with_retry(...)

# REPLACE with direct call:
response = _call_claude_structured_with_retry(client, model, max_tokens, prompt, schema)
```

### Dead Import Cleanup (pipeline.py line 21)
```python
# REMOVE this line from pipeline.py:
from src.dedup import dedup_source_items
# It is only used in pipeline_async.py (which already imports it)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Beta header `output-format-2025-01-24` | GA `output_config` parameter | Anthropic SDK ~0.45+ | Beta header now returns 400 errors |
| Free-text markdown + regex parsing | `json_schema` constrained decoding | Phase 14 (for extractor/synthesizer) | Eliminates parse failures, guarantees valid JSON |

**Deprecated/outdated:**
- `output-format-2025-01-24` beta header: Rejected by the Anthropic API. Must use `output_config` parameter instead.
- `_call_claude_with_retry` (plain text variant in weekly.py/monthly.py): Replace with structured output variant.

## Scope of Changes

### Files to MODIFY
| File | Change | Complexity |
|------|--------|------------|
| `src/synthesis/models.py` | Add 6-7 new Pydantic output models for weekly and monthly | Low |
| `src/synthesis/weekly.py` | Replace `_call_claude_with_retry` with structured call; replace `_parse_weekly_response` and sub-parsers with converter; update prompt | Medium |
| `src/synthesis/monthly.py` | Replace `_call_claude_with_retry` with structured call; replace `_parse_monthly_response` and sub-parsers with converter; update prompt | Medium |
| `src/synthesis/extractor.py` | Remove beta fallback function and try/except blocks (sync + async) | Low |
| `src/synthesis/synthesizer.py` | Remove beta fallback function and try/except blocks | Low |
| `src/synthesis/commitments.py` | Remove beta fallback function and try/except blocks | Low |
| `src/pipeline.py` | Remove dead `dedup_source_items` import (line 21) | Trivial |
| `tests/test_weekly.py` | Update `TestParseWeeklyResponse` to test new converter function | Low |
| `tests/test_monthly.py` | Update `TestParseMonthlyResponse` to test new converter function | Low |

### Files UNCHANGED
| File | Reason |
|------|--------|
| `src/synthesis/prompts.py` | Prompts may need minor adjustments (remove markdown format instructions, add JSON field guidance) but the core content stays the same |
| `src/models/rollups.py` | Domain models stay unchanged; new output models are separate |
| `src/pipeline_async.py` | Already correct; no dead imports, no direct Claude calls |
| `src/retry.py` | Shared retry decorator, no changes needed |

## Open Questions

1. **Prompt adjustment depth for weekly/monthly**
   - What we know: Prompts currently instruct Claude to produce markdown with specific `##` sections. Structured outputs need prompts that describe JSON fields instead.
   - What's unclear: How much prompt rewriting is needed. The prompts have nuanced instructions about tone, significance ranking, thread detection.
   - Recommendation: Keep the analytical instructions intact, replace formatting instructions with JSON field descriptions. The reasoning scratchpad handles Claude's thinking.

2. **Date resolution in weekly thread entries**
   - What we know: Current regex parser resolves "Monday, March 30" to actual dates by matching against summaries. Structured output will have a `day_label` string field.
   - What's unclear: Whether Claude will consistently produce parseable day labels in structured mode.
   - Recommendation: Keep the date resolution logic but simplify it. If Claude produces ISO dates directly (via prompt instruction), even better.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | pytest.ini or pyproject.toml (standard) |
| Quick run command | `pytest tests/test_weekly.py tests/test_monthly.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STRUCT-01 (weekly) | Weekly structured output parsing | unit | `pytest tests/test_weekly.py -x` | Yes (needs update) |
| STRUCT-01 (monthly) | Monthly structured output parsing | unit | `pytest tests/test_monthly.py -x` | Yes (needs update) |
| STRUCT-01 (fallback removal) | No beta header fallback in extractor/synthesizer/commitments | unit | `pytest tests/test_extractor.py tests/test_synthesizer.py -x` | Yes (verify no fallback tested) |
| STRUCT-01 (dead import) | pipeline.py has no dedup_source_items import | unit | `python -c "from src import pipeline"` | N/A (trivial) |

### Sampling Rate
- **Per task commit:** `pytest tests/test_weekly.py tests/test_monthly.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before verification

### Wave 0 Gaps
- [ ] `tests/test_weekly.py::TestParseWeeklyResponse` -- must be rewritten to test converter function instead of regex parser
- [ ] `tests/test_monthly.py::TestParseMonthlyResponse` -- must be rewritten to test converter function instead of regex parser
- [ ] New test: verify `WeeklySynthesisOutput.model_json_schema()` produces valid schema
- [ ] New test: verify `MonthlySynthesisOutput.model_json_schema()` produces valid schema

## Sources

### Primary (HIGH confidence)
- Project codebase: `src/synthesis/extractor.py` -- established structured output pattern (output_config, schema, model_validate)
- Project codebase: `src/synthesis/synthesizer.py` -- established structured output pattern with DailySynthesisOutput
- Project codebase: `src/synthesis/models.py` -- existing Pydantic output models with ConfigDict(extra="forbid") and reasoning field
- Project codebase: `src/synthesis/weekly.py` -- current implementation (plain API call + regex parsing)
- Project codebase: `src/synthesis/monthly.py` -- current implementation (plain API call + regex parsing)
- `.planning/v1.5.1-MILESTONE-AUDIT.md` -- gap identification, beta header issue documentation

### Secondary (MEDIUM confidence)
- Project `pyproject.toml`: anthropic>=0.45.0 confirms `output_config` support
- Audit evidence: beta header `output-format-2025-01-24` causes 400 errors in production

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - established pattern already working in 3 files
- Architecture: HIGH - direct replication of existing pattern
- Pitfalls: HIGH - well-understood from Phase 14 experience
- Scope: HIGH - all files read and analyzed, changes are mechanical

**Research date:** 2026-04-05
**Valid until:** 2026-05-05 (stable -- internal codebase migration, no external API changes expected)
