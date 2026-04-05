# Phase 14: Structured Output Migration - Research

**Researched:** 2026-04-05
**Status:** Complete

## Current Architecture

### Claude API Call Sites (6 total across 5 files)

| File | Function | What It Does | In Scope? |
|------|----------|-------------|-----------|
| `src/synthesis/extractor.py` | `_call_claude_with_retry` | Per-meeting transcript extraction | YES |
| `src/synthesis/synthesizer.py` | `_call_claude_with_retry` | Daily cross-meeting synthesis | YES |
| `src/synthesis/weekly.py` | `_call_claude_with_retry` | Weekly thread detection roll-up | NO (Phase 14 scope is extractor + synthesizer only per success criteria) |
| `src/synthesis/monthly.py` | `_call_claude_with_retry` | Monthly narrative roll-up | NO |
| `src/synthesis/commitments.py` | `_call_claude_structured_with_retry` | Commitment extraction (ALREADY uses structured outputs) | NO (already done) |

### Regex/Markdown Parsing to Replace

**extractor.py (~150 lines of parsing):**
- `_parse_section_items()` (lines 27-102): Parses pipe-delimited and bold-label formats from markdown
- `_parse_legacy_blocks()` (lines 105-148): Parses multi-line block format (- **Decision:** / - **Participants:**)
- `_parse_extraction_response()` (lines 151-212): Splits by ## headers, maps sections to fields

**synthesizer.py (~84 lines of parsing):**
- `_parse_synthesis_response()` (lines 426-509): Splits by ## headers, extracts bullet items and table rows for commitments

**Total parsing code to delete: ~234 lines** (matches success criteria)

### Existing Data Models

**`src/synthesis/models.py`** contains:
- `ExtractionItem(BaseModel)`: content, participants, rationale
- `MeetingExtraction(BaseModel)`: meeting_title, meeting_time, meeting_participants, decisions/commitments/substance/open_questions/tensions (all list[ExtractionItem]), low_signal

**Downstream consumers of extraction output:**
- `synthesizer.py`: `_format_extractions_for_prompt()` reads MeetingExtraction fields
- `pipeline.py`: passes extractions list to synthesizer
- `sidecar.py`: reads extraction data for JSON sidecar output

**Downstream consumers of synthesis output:**
- `output/writer.py`: writes the dict to markdown
- `sidecar.py`: writes JSON sidecar from the dict
- `pipeline.py`: orchestrates the flow
- `commitments.py`: takes synthesis text as input (string, not structured)

### Existing Structured Output Pattern (commitments.py)

The codebase already has a working structured output implementation:
1. Define Pydantic model with `model_config = ConfigDict(extra="forbid")`
2. Generate schema via `Model.model_json_schema()`
3. Call API with `output_config={"format": {"type": "json_schema", "schema": schema}}`
4. Fallback to beta header if output_config not supported
5. Parse response: `json.loads(response.content[0].text)` then `Model.model_validate(data)`

### SDK Support

- **anthropic SDK version:** 0.88.0 (supports `output_config` parameter)
- **API parameter:** `output_config={"format": {"type": "json_schema", "schema": ...}}`
- **Response format:** `response.content[0].text` contains JSON string
- **Fallback path:** Beta header `anthropic-beta: output-format-2025-01-24` with `extra_body`

## Implementation Analysis

### Plan 14-01: Extraction Migration

**What changes:**
1. Create `MeetingExtractionOutput` Pydantic model in `src/synthesis/models.py` (new output model for API response)
2. Modify `extract_meeting()` to use `output_config` with json_schema instead of plain text
3. Parse response as JSON -> validate with Pydantic instead of regex
4. Delete `_parse_section_items()`, `_parse_legacy_blocks()`, `_parse_extraction_response()`
5. Update EXTRACTION_PROMPT to work optimally with json_schema (no markdown format instructions)

**Output model design for extraction:**
```
MeetingExtractionOutput:
  reasoning: str  # Scratchpad field (discarded downstream)
  decisions: list[ExtractionItemOutput]
  commitments: list[ExtractionItemOutput]
  substance: list[ExtractionItemOutput]
  open_questions: list[ExtractionItemOutput]
  tensions: list[ExtractionItemOutput]

ExtractionItemOutput:
  content: str
  participants: list[str]
  rationale: str | None
```

**Key considerations:**
- `reasoning` field goes first in schema so Claude "thinks" before extracting
- MeetingExtractionOutput maps 1:1 to existing MeetingExtraction but without meeting metadata (title/time/participants come from the event, not Claude)
- After parsing, construct MeetingExtraction from event metadata + parsed output (same downstream interface)

### Plan 14-02: Synthesis Migration

**What changes:**
1. Create `DailySynthesisOutput` Pydantic model in `src/synthesis/models.py`
2. Modify `synthesize_daily()` to use `output_config` with json_schema
3. Parse response as JSON -> validate with Pydantic instead of regex
4. Delete `_parse_synthesis_response()`
5. Update SYNTHESIS_PROMPT for json_schema
6. Return typed model (or dict converted from model for backward compatibility)

**Output model design for synthesis:**
```
DailySynthesisOutput:
  executive_summary: str | None
  substance: list[SynthesisItem]
  decisions: list[SynthesisItem]
  commitments: list[CommitmentItem]

SynthesisItem:
  content: str  # The bullet point text including attribution

CommitmentItem:
  who: str
  what: str
  by_when: str
  source: str  # Attribution text
```

**Key considerations:**
- synthesize_daily() currently returns a dict with string lists; switching to a typed model requires updating downstream consumers (writer.py, sidecar.py, pipeline.py)
- Can return the model and provide `.to_legacy_dict()` method for backward compatibility during transition
- Evidence-only validation (`validate_evidence_only`) runs on the response text; with structured output, run it on concatenated content fields instead
- Token budget truncation logic is about INPUT size, unaffected by output format change

### Shared Infrastructure

**New shared helper function** for structured Claude API calls:
- Already exists in commitments.py; should be extracted to a shared location (e.g., `retry.py` or a new `src/synthesis/api.py`)
- Both plans can use the same `call_claude_structured()` pattern

### Test Impact

**Tests to update:**
- `tests/test_extractor.py`: All parser tests become obsolete (test the Pydantic models + API mock instead)
- `tests/test_synthesizer.py`: Parser tests become obsolete; format tests still valid
- New tests: Pydantic model validation, JSON parsing from mock API responses, error/retry handling

### Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Structured output returns slightly different content than markdown parsing | Medium | Golden-file comparison test on a known transcript |
| Schema too strict, Claude fails validation on edge cases | Low | Include `reasoning` scratchpad field; use permissive types (Optional, default_factory=list) |
| SDK version incompatibility on output_config | Low | Fallback pattern already proven in commitments.py |
| Downstream consumers break on new return type | Medium | Maintain dict interface initially; migrate consumers in same plan |

## RESEARCH COMPLETE

---

*Phase: 14-structured-output-migration*
*Research completed: 2026-04-05*
