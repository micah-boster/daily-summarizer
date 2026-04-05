# Phase 13: Typed Config Foundation - Research

**Researched:** 2026-04-05
**Domain:** Pydantic v2 configuration validation, YAML-to-model migration
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Reject unknown keys at startup with a clear error (strict mode -- catches typos like `slakc:` immediately)
- Optional sections (slack, hubspot, google_docs, etc.) can be omitted entirely from YAML -- defaults fill in (enabled: false, empty lists)
- Validate both types AND sensible ranges (positive ints, non-empty strings where required) -- not just type matching
- Schema-only validation -- no connectivity or resource existence checks at config load time (runtime checks happen when modules execute)
- Keep the existing 3 env var overrides only (SUMMARIZER_TIMEZONE, SUMMARIZER_CALENDAR_IDS, SUMMARIZER_OUTPUT_DIR) -- no expansion
- Env vars are merged into the raw dict BEFORE Pydantic validation -- the model always reflects final truth
- Env var values go through the same Pydantic validation as YAML values -- invalid env var = startup error
- Log env var overrides at DEBUG level so they're visible with verbose mode but silent by default
- Per-section sub-models: SlackConfig, HubSpotConfig, CalendarsConfig, TranscriptsConfig, SynthesisConfig, GoogleDocsConfig, PipelineConfig (root)
- Models live in src/config.py (expand existing file, don't create a package)
- load_config() returns the typed PipelineConfig model -- clean break, no dict access remains
- Pass typed config objects (or sub-models) to functions -- not a global singleton. Modules receive their relevant config via parameter passing
- Friendly human-readable summary: one-line count ("Config invalid: 2 errors") followed by each error with field path and description
- Suggest fixes for unknown keys using fuzzy matching (e.g., "Unknown key 'slakc'. Did you mean 'slack'?")
- Show a valid example snippet for the failing section after the error
- Report ALL validation errors at once -- don't stop at the first
- Exit with code 1 on validation failure (sys.exit(1) after printing errors)

### Claude's Discretion
- Exact Pydantic field validators and custom types
- Internal model method naming
- Test structure and fixtures
- How to handle the `transcripts.matching` and `transcripts.preprocessing` nested config

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CONFIG-01 | Typed config model (Pydantic validation on config.yaml load) with backward-compatible defaults for all existing optional sections | Pydantic v2 BaseModel with `model_config = ConfigDict(extra="forbid")` for strict mode; `Optional` fields with defaults for backward compat; `model_validator` for env var merge; custom error formatter for friendly messages |
</phase_requirements>

## Summary

This phase replaces the raw-dict config access pattern (`config.get("slack", {}).get("enabled", False)`) with a validated Pydantic v2 model tree. The project already uses Pydantic 2.12.5 for data models (`SourceItem`, `NormalizedEvent`, etc.), so no new dependency is needed.

The codebase has 312 config access points (`.get()` and `config[...]`) spread across 24 files. Every function that touches config receives the full `config: dict` parameter and internally navigates to its section. The migration strategy is: (1) define the model tree in `src/config.py`, (2) update `load_config()` to return `PipelineConfig`, (3) update `PipelineContext.config` type, (4) migrate each module to receive its typed sub-model or the root model, (5) replace all `.get()` chains with attribute access.

**Primary recommendation:** Use Pydantic v2 `BaseModel` with `ConfigDict(extra="forbid")` at every level. Define sub-models bottom-up matching the YAML structure. Load YAML as dict, merge env vars, then pass to `PipelineConfig(**raw_dict)`. Wrap the constructor call in a try/except for `ValidationError` and format errors for human output.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | 2.12.5 (already installed) | Model validation, typed config | Already in project, v2 is current stable |
| pyyaml | 6.0.3 (already installed) | YAML parsing | Already used by load_config() |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| difflib (stdlib) | N/A | Fuzzy matching for typo suggestions | `difflib.get_close_matches()` for "did you mean?" on unknown keys |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Pydantic `extra="forbid"` | Custom pre-validator scanning keys | Pydantic's built-in is sufficient; custom only needed for fuzzy suggestions |
| pydantic-settings | Raw Pydantic + manual env merge | pydantic-settings adds complexity for only 3 env vars; manual merge is simpler and the user decided env vars merge into dict BEFORE validation |

**Installation:** No new packages needed. Pydantic 2.12.5 and PyYAML 6.0.3 are already installed.

## Architecture Patterns

### Recommended Model Structure

```
src/config.py
├── PipelineSettings (pipeline section)
├── CalendarsConfig (calendars section)
├── GeminiTranscriptConfig (transcripts.gemini)
├── GongTranscriptConfig (transcripts.gong)
├── TranscriptMatchingConfig (transcripts.matching)
├── TranscriptPreprocessingConfig (transcripts.preprocessing)
├── TranscriptsConfig (transcripts section, contains above 4)
├── SlackFilterConfig (slack.filter)
├── SlackConfig (slack section, contains SlackFilterConfig)
├── GoogleDocsConfig (google_docs section)
├── HubSpotConfig (hubspot section)
├── SynthesisConfig (synthesis section)
└── PipelineConfig (root model, contains all above)
```

### Pattern 1: Nested Sub-Models with Forbid Extra

**What:** Each YAML section maps to a Pydantic model with `extra="forbid"`. Optional sections default to disabled state.
**When to use:** Every config section.

```python
from pydantic import BaseModel, ConfigDict, Field, field_validator

class SlackConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    channels: list[str] = Field(default_factory=list)
    dms: list[str] = Field(default_factory=list)
    thread_min_replies: int = Field(default=3, ge=1)
    thread_min_participants: int = Field(default=2, ge=1)
    max_messages_per_channel: int = Field(default=100, ge=1)
    bot_allowlist: list[str] = Field(default_factory=list)
    discovery_check_days: int = Field(default=7, ge=1)
    filter: SlackFilterConfig = Field(default_factory=SlackFilterConfig)
```

### Pattern 2: Env Var Merge Before Validation

**What:** Merge environment variables into the raw YAML dict before constructing the Pydantic model. This ensures the model always reflects the final truth.
**When to use:** In `load_config()`.

```python
def load_config(config_path: Path | None = None) -> PipelineConfig:
    raw = _load_yaml(config_path)
    _apply_env_overrides(raw)  # mutates raw dict
    return _validate_config(raw)  # returns PipelineConfig or exits
```

### Pattern 3: Custom Error Formatter with Fuzzy Matching

**What:** Catch `ValidationError`, format each error with field path and description, use `difflib.get_close_matches()` for unknown-key suggestions.
**When to use:** In the validation wrapper function.

```python
import difflib
from pydantic import ValidationError

def _validate_config(raw: dict) -> PipelineConfig:
    try:
        return PipelineConfig(**raw)
    except ValidationError as e:
        errors = _format_errors(e, raw)
        print(f"Config invalid: {len(e.errors())} error(s)\n")
        for err in errors:
            print(f"  {err}")
        sys.exit(1)
```

The `extra="forbid"` error type is `"extra_forbidden"`. When this error type is encountered, extract the field name from `err["loc"]` and use `difflib.get_close_matches(field_name, valid_fields)` to suggest corrections.

### Pattern 4: Gradual Function Signature Migration

**What:** Update function signatures from `config: dict` to typed models. Functions that only use one section should receive that sub-model.
**When to use:** During the migration of each module.

```python
# BEFORE
def fetch_slack_items(config: dict, target_date: date) -> list[SourceItem]:
    slack_config = config.get("slack", {})
    if not slack_config.get("enabled", False):
        ...

# AFTER
def fetch_slack_items(config: PipelineConfig, target_date: date) -> list[SourceItem]:
    if not config.slack.enabled:
        ...
```

**Decision point:** Some functions access multiple config sections (e.g., `fetch_slack_items` reads both `slack.*` and `pipeline.timezone`). These should receive the full `PipelineConfig` root model. Functions that only need one section (e.g., internal helpers like `should_expand_thread`) can receive just the sub-model.

### Anti-Patterns to Avoid
- **Converting model back to dict:** Never call `.model_dump()` to pass config around. Always pass the model or sub-model directly.
- **Using `model_validate` with `from_attributes=True` unnecessarily:** The input is a plain dict from YAML; standard `PipelineConfig(**raw)` or `PipelineConfig.model_validate(raw)` is correct.
- **Mixing dict and model access:** During migration, a file must be fully converted. No hybrid `.get()` plus attribute access in the same function.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Type validation | Custom type checks | Pydantic field types + `Field(ge=1)` constraints | Pydantic handles int, str, list, bool, ranges natively |
| Unknown key detection | Dict key scanning | `ConfigDict(extra="forbid")` | Built into Pydantic, raises `extra_forbidden` error |
| Nested defaults | Recursive `setdefault()` calls | Pydantic model defaults + `Field(default_factory=...)` | Model instantiation handles all defaults automatically |
| Fuzzy matching | Levenshtein from scratch | `difflib.get_close_matches()` (stdlib) | Handles 90% of typo cases, zero dependencies |
| Error collection | Manual error list accumulation | Pydantic `ValidationError.errors()` | Pydantic already collects ALL errors before raising |

**Key insight:** Pydantic v2 already does nearly everything this phase needs out of the box. The custom work is limited to: (1) the env-var merge step, (2) the error formatter with fuzzy suggestions, and (3) the example-snippet generator.

## Common Pitfalls

### Pitfall 1: Extra Forbid at Wrong Level
**What goes wrong:** Setting `extra="forbid"` only on the root model but not sub-models. A typo in a nested section (e.g., `slack.chnnels`) would silently pass.
**Why it happens:** Pydantic's `extra` setting is per-model, not inherited.
**How to avoid:** Set `ConfigDict(extra="forbid")` on every sub-model, not just the root.
**Warning signs:** Tests pass with misspelled nested keys.

### Pitfall 2: Dict Keys vs Model Field Names
**What goes wrong:** YAML uses `snake_case` keys that must match Pydantic field names exactly. A field named `output_dir` in the model must match `output_dir` in YAML.
**Why it happens:** Pydantic v2 does not do automatic alias generation by default.
**How to avoid:** Name model fields identically to the YAML keys. For keys with special characters, use `Field(alias="key-name")`.
**Warning signs:** `ValidationError` on fields that clearly exist in the YAML.

### Pitfall 3: Optional Section Handling
**What goes wrong:** If `slack` section is completely omitted from YAML, the raw dict has no `slack` key. If the root model expects `slack: SlackConfig`, Pydantic needs to know to use the default.
**Why it happens:** Missing key in dict != `None` value for key.
**How to avoid:** Declare optional sections as `slack: SlackConfig = Field(default_factory=SlackConfig)`. This creates a default-valued sub-model when the key is missing.
**Warning signs:** `ValidationError: field required` for sections the user intentionally omitted.

### Pitfall 4: Env Var Type Coercion
**What goes wrong:** `SUMMARIZER_CALENDAR_IDS` is a comma-separated string that becomes `list[str]`. If the env var is injected as a string into the raw dict at the `calendars.ids` path, Pydantic will reject it because it expects a list.
**Why it happens:** Env vars are always strings; the current code does the split manually.
**How to avoid:** Keep the existing env var parsing logic (split on comma for calendar IDs) in `_apply_env_overrides()` BEFORE passing to Pydantic. The dict must contain properly typed Python values.
**Warning signs:** Env var overrides that worked before now fail validation.

### Pitfall 5: Breaking Test Fixtures
**What goes wrong:** Many tests pass `config={...}` as plain dicts to `PipelineContext` or directly to functions. After migration, these all break.
**Why it happens:** Tests construct minimal config dicts; the new model requires specific structure.
**How to avoid:** Create a `make_test_config()` helper or use `PipelineConfig.model_validate(partial_dict)` with defaults filling in missing sections. Migrate test fixtures as part of each module's migration.
**Warning signs:** Entire test suite fails after changing `PipelineContext.config` type.

### Pitfall 6: Forgetting `gemini_drive` Sub-Section
**What goes wrong:** The `transcripts` section has a `gemini_drive` sub-section (with `enabled: true`) that is easy to miss when modeling transcripts config.
**Why it happens:** It's a separate feature from `gemini` (email-based), and has a different structure.
**How to avoid:** Map every key in the existing `config.yaml` to a model field. Cross-reference with grep results.
**Warning signs:** `extra_forbidden` error on `gemini_drive` key.

## Code Examples

### Complete Sub-Model Definition (Slack)

```python
from pydantic import BaseModel, ConfigDict, Field

class SlackFilterConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skip_subtypes: list[str] = Field(default_factory=lambda: [
        "channel_join", "channel_leave", "channel_topic",
        "channel_purpose", "channel_name",
    ])
    skip_patterns: list[str] = Field(default_factory=lambda: [
        r"^(ok|thanks|lol|yes|no|sure|yep|nope|haha|nice)$",
    ])

class SlackConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    channels: list[str] = Field(default_factory=list)
    dms: list[str] = Field(default_factory=list)
    thread_min_replies: int = Field(default=3, ge=1)
    thread_min_participants: int = Field(default=2, ge=1)
    max_messages_per_channel: int = Field(default=100, ge=1)
    bot_allowlist: list[str] = Field(default_factory=list)
    discovery_check_days: int = Field(default=7, ge=1)
    filter: SlackFilterConfig = Field(default_factory=SlackFilterConfig)
```

### Error Formatter with Fuzzy Matching

```python
import difflib
import sys
from pydantic import ValidationError

SECTION_EXAMPLES = {
    "slack": 'slack:\n  enabled: true\n  channels: ["C01ABCD2EFG"]',
    "hubspot": 'hubspot:\n  enabled: true\n  ownership_scope: "mine"',
    # ... etc
}

def _format_validation_error(e: ValidationError, raw: dict) -> str:
    lines = [f"Config invalid: {len(e.errors())} error(s)\n"]
    for err in e.errors():
        loc = " -> ".join(str(x) for x in err["loc"])
        msg = err["msg"]
        line = f"  {loc}: {msg}"

        # Fuzzy suggestion for unknown keys
        if err["type"] == "extra_forbidden":
            field_name = str(err["loc"][-1])
            # Determine valid fields at this level
            parent_loc = err["loc"][:-1]
            valid = _get_valid_fields_at(parent_loc)
            matches = difflib.get_close_matches(field_name, valid, n=1, cutoff=0.6)
            if matches:
                line += f'\n    Did you mean "{matches[0]}"?'

        lines.append(line)

        # Show example for the top-level section
        section = str(err["loc"][0]) if err["loc"] else ""
        if section in SECTION_EXAMPLES:
            lines.append(f"\n    Example:\n    {SECTION_EXAMPLES[section]}")

    return "\n".join(lines)
```

### Env Var Override (Pre-Validation Merge)

```python
import logging
import os

logger = logging.getLogger(__name__)

def _apply_env_overrides(raw: dict) -> None:
    """Merge environment variable overrides into raw config dict (mutates in place)."""
    if tz := os.environ.get("SUMMARIZER_TIMEZONE"):
        raw.setdefault("pipeline", {})["timezone"] = tz
        logger.debug("Env override: pipeline.timezone = %s", tz)

    if cal_ids := os.environ.get("SUMMARIZER_CALENDAR_IDS"):
        raw.setdefault("calendars", {})["ids"] = [
            cid.strip() for cid in cal_ids.split(",")
        ]
        logger.debug("Env override: calendars.ids = %s", cal_ids)

    if output_dir := os.environ.get("SUMMARIZER_OUTPUT_DIR"):
        raw.setdefault("pipeline", {})["output_dir"] = output_dir
        logger.debug("Env override: pipeline.output_dir = %s", output_dir)
```

## Config Key Inventory

Complete mapping of every config key to its model field, derived from `config/config.yaml` and grep of all access patterns:

| YAML Path | Type | Default | Constraint | Accessing Files |
|-----------|------|---------|------------|-----------------|
| `pipeline.timezone` | str | "America/New_York" | non-empty | calendar.py, normalizer.py, slack.py |
| `pipeline.output_dir` | str | "output" | non-empty | main.py |
| `calendars.ids` | list[str] | ["primary"] | non-empty list | calendar.py |
| `calendars.exclude_patterns` | list[str] | [] | -- | calendar.py |
| `transcripts.gemini_drive.enabled` | bool | True | -- | drive.py |
| `transcripts.gemini.sender_patterns` | list[str] | [] | -- | transcripts.py |
| `transcripts.gemini.subject_patterns` | list[str] | [] | -- | transcripts.py |
| `transcripts.gong.sender_patterns` | list[str] | [] | -- | transcripts.py |
| `transcripts.gong.subject_patterns` | list[str] | [] | -- | transcripts.py |
| `transcripts.matching.time_window_minutes` | int | 30 | ge=1 | normalizer.py |
| `transcripts.matching.include_unmatched_events` | bool | True | -- | normalizer.py |
| `transcripts.preprocessing.strip_filler` | bool | True | -- | transcripts.py, drive.py |
| `synthesis.model` | str | "claude-sonnet-4-20250514" | non-empty | extractor.py, synthesizer.py, weekly.py, monthly.py, commitments.py |
| `synthesis.extraction_max_output_tokens` | int | 4096 | ge=1 | extractor.py |
| `synthesis.synthesis_max_output_tokens` | int | 8192 | ge=1 | synthesizer.py |
| `synthesis.weekly_max_output_tokens` | int | 8192 | ge=1 | weekly.py |
| `synthesis.monthly_max_output_tokens` | int | 8192 | ge=1 | monthly.py |
| `slack.enabled` | bool | False | -- | pipeline.py, slack.py |
| `slack.channels` | list[str] | [] | -- | slack.py, slack_discovery.py |
| `slack.dms` | list[str] | [] | -- | slack.py, slack_discovery.py |
| `slack.thread_min_replies` | int | 3 | ge=1 | slack.py |
| `slack.thread_min_participants` | int | 2 | ge=1 | slack.py |
| `slack.max_messages_per_channel` | int | 100 | ge=1 | slack.py |
| `slack.bot_allowlist` | list[str] | [] | -- | slack.py |
| `slack.discovery_check_days` | int | 7 | ge=1 | pipeline.py, slack.py |
| `slack.filter.skip_subtypes` | list[str] | [...] | -- | slack_filter.py |
| `slack.filter.skip_patterns` | list[str] | [...] | -- | slack_filter.py |
| `google_docs.enabled` | bool | False | -- | pipeline.py, google_docs.py |
| `google_docs.content_max_chars` | int | 2500 | ge=1 | google_docs.py |
| `google_docs.comment_max_chars` | int | 500 | ge=1 | google_docs.py |
| `google_docs.max_docs_per_day` | int | 50 | ge=1 | google_docs.py |
| `google_docs.exclude_ids` | list[str] | [] | -- | google_docs.py |
| `google_docs.exclude_title_patterns` | list[str] | [] | -- | google_docs.py |
| `hubspot.enabled` | bool | False | -- | pipeline.py, hubspot.py |
| `hubspot.ownership_scope` | str | "mine" | -- | hubspot.py |
| `hubspot.max_deals` | int | 50 | ge=0 | hubspot.py |
| `hubspot.max_contacts` | int | 50 | ge=0 | hubspot.py |
| `hubspot.max_tickets` | int | 25 | ge=0 | hubspot.py |
| `hubspot.max_activities_per_type` | int | 25 | ge=0 | hubspot.py |
| `hubspot.portal_url` | str | "" | -- | hubspot.py |

**Total: 37 distinct config keys across 7 top-level sections.**

## Migration Scope by File

Files ordered by number of config access points (highest first):

| File | Access Count | Sections Used | Migration Complexity |
|------|-------------|---------------|---------------------|
| src/ingest/slack.py | 47 | slack, pipeline | HIGH -- most access points, nested filter config |
| src/ingest/google_docs.py | 39 | google_docs | MEDIUM -- repetitive pattern |
| src/ingest/hubspot.py | 31 | hubspot | MEDIUM -- repetitive pattern |
| src/ingest/calendar.py | 29 | calendars, pipeline | MEDIUM |
| src/ingest/slack_discovery.py | 25 | slack | MEDIUM |
| src/ingest/transcripts.py | 23 | transcripts | MEDIUM |
| src/pipeline.py | 18 | slack, hubspot, google_docs (enabled checks) | LOW -- just enabled checks |
| src/ingest/drive.py | 17 | transcripts | LOW-MEDIUM |
| src/ingest/normalizer.py | 11 | transcripts.matching, pipeline | LOW |
| src/synthesis/extractor.py | 10 | synthesis | LOW |
| src/ingest/slack_filter.py | 6 | (receives config directly) | LOW |
| src/main.py | 5 | pipeline | LOW |
| src/synthesis/monthly.py | 5 | synthesis | LOW |
| src/synthesis/synthesizer.py | 4 | synthesis | LOW |
| src/synthesis/weekly.py | 4 | synthesis | LOW |
| src/quality.py | 4 | (no config section access) | TRIVIAL |
| src/priorities.py | 4 | (separate YAML file, not config.yaml) | OUT OF SCOPE |
| src/synthesis/commitments.py | 2 | synthesis | TRIVIAL |
| src/notifications/slack.py | 2 | (env var only) | TRIVIAL |
| src/config.py | 6 | (this is the source file) | CORE CHANGE |

**Note:** `src/priorities.py` loads its own separate YAML file (`priorities.yaml`), not `config.yaml`. It is out of scope for this phase.

**Note:** Many `.get()` calls in the grep count are for API response parsing (e.g., `event.get("summary")`), not config access. The actual config-accessing `.get()` calls are the ones following patterns like `config.get("section", {}).get("key", default)`. The true config migration count is lower than 312 but still substantial.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Pydantic v1 `Config` inner class | Pydantic v2 `model_config = ConfigDict(...)` | Pydantic 2.0 (Jun 2023) | Must use v2 syntax; v1 compat layer works but is deprecated |
| `validator` decorator | `field_validator` / `model_validator` | Pydantic 2.0 | New decorator names, `mode="before"` / `mode="after"` |
| `schema_extra` | `json_schema_extra` | Pydantic 2.0 | Different name if generating JSON schema |

**Deprecated/outdated:**
- `pydantic-settings`: Was commonly used for env-var-heavy apps. For this project with only 3 env vars, it adds unnecessary complexity vs. manual merge.
- Pydantic v1 `Config` class: Still works via compat layer but should not be used in new code.

## Open Questions

1. **Function signature strategy: root model vs sub-model**
   - What we know: Some functions only access one section, others access two or more (e.g., slack.py accesses both `slack.*` and `pipeline.timezone`)
   - What's unclear: Whether to pass `PipelineConfig` everywhere for consistency, or mix root-model and sub-model params
   - Recommendation: Pass `PipelineConfig` to top-level orchestration functions (fetch_slack_items, fetch_hubspot_items, etc.) since they often access multiple sections. Pass sub-models only to internal helpers that genuinely need one section. This matches the current pattern where top-level functions receive the full dict.

2. **HubSpot `owner_id` field**
   - What we know: `hubspot.owner_id` appears in code (`config.get("hubspot", {}).get("owner_id")`) but is NOT in `config.yaml` -- it may be set dynamically
   - What's unclear: Whether this is a user-configurable field or runtime-only
   - Recommendation: Include `owner_id: str | None = None` as an optional field in HubSpotConfig. If it's truly runtime-only, leave it out and adjust the code.

## Validation Architecture

> `workflow.nyquist_validation` is not present in `.planning/config.json` -- skipping this section.

## Sources

### Primary (HIGH confidence)
- Project codebase analysis: `src/config.py`, `config/config.yaml`, all 24 files with config access
- Pydantic 2.12.5 installed in project -- API verified against training knowledge of Pydantic v2 stable features (BaseModel, ConfigDict, Field, ValidationError)

### Secondary (MEDIUM confidence)
- Pydantic v2 documentation for `extra="forbid"`, `field_validator`, `model_validator` patterns -- well-established stable API since Pydantic 2.0 (Jun 2023)
- `difflib.get_close_matches()` -- Python stdlib, stable API

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- Pydantic already in project, well-known v2 patterns
- Architecture: HIGH -- config structure is fully mapped from existing YAML and code
- Pitfalls: HIGH -- identified from real codebase patterns (312 access points analyzed)

**Research date:** 2026-04-05
**Valid until:** 2026-05-05 (stable domain, no fast-moving dependencies)
