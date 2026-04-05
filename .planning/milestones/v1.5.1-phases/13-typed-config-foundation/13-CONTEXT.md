# Phase 13: Typed Config Foundation - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace raw dict config access with a Pydantic-validated, typed configuration model. Every config.yaml load is validated at startup — typos and invalid values produce clear errors immediately instead of KeyError mid-run. All ingest modules and synthesis functions access config via typed attributes (e.g., `config.slack.channels`) instead of `.get()` chains.

</domain>

<decisions>
## Implementation Decisions

### Validation Strictness
- Reject unknown keys at startup with a clear error (strict mode — catches typos like `slakc:` immediately)
- Optional sections (slack, hubspot, google_docs, etc.) can be omitted entirely from YAML — defaults fill in (enabled: false, empty lists)
- Validate both types AND sensible ranges (positive ints, non-empty strings where required) — not just type matching
- Schema-only validation — no connectivity or resource existence checks at config load time (runtime checks happen when modules execute)

### Env Var Override Behavior
- Keep the existing 3 env var overrides only (SUMMARIZER_TIMEZONE, SUMMARIZER_CALENDAR_IDS, SUMMARIZER_OUTPUT_DIR) — no expansion
- Env vars are merged into the raw dict BEFORE Pydantic validation — the model always reflects final truth
- Env var values go through the same Pydantic validation as YAML values — invalid env var = startup error
- Log env var overrides at DEBUG level so they're visible with verbose mode but silent by default

### Config Model Structure
- Per-section sub-models: SlackConfig, HubSpotConfig, CalendarsConfig, TranscriptsConfig, SynthesisConfig, GoogleDocsConfig, PipelineConfig (root)
- Models live in src/config.py (expand existing file, don't create a package)
- load_config() returns the typed PipelineConfig model — clean break, no dict access remains
- Pass typed config objects (or sub-models) to functions — not a global singleton. Modules receive their relevant config via parameter passing

### Error Messaging
- Friendly human-readable summary: one-line count ("Config invalid: 2 errors") followed by each error with field path and description
- Suggest fixes for unknown keys using fuzzy matching (e.g., "Unknown key 'slakc'. Did you mean 'slack'?")
- Show a valid example snippet for the failing section after the error
- Report ALL validation errors at once — don't stop at the first
- Exit with code 1 on validation failure (sys.exit(1) after printing errors)

### Claude's Discretion
- Exact Pydantic field validators and custom types
- Internal model method naming
- Test structure and fixtures
- How to handle the `transcripts.matching` and `transcripts.preprocessing` nested config

</decisions>

<specifics>
## Specific Ideas

- Current config has ~443 `.get()` / `config[` access points across 62 files — all must be migrated
- The success criteria requires identical output with valid config (regression safety)
- Phase 14 (Structured Outputs) depends on this — Pydantic models established here become the pattern for response models

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 13-typed-config-foundation*
*Context gathered: 2026-04-04*
