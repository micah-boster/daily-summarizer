# Phase 6: Data Model Foundation - Context

**Gathered:** 2026-04-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Define `SourceItem` and `Commitment` Pydantic models that all v1.5 ingest modules and synthesis depend on. Existing `NormalizedEvent` and `DailySynthesis` models must remain unchanged (no regressions). This phase delivers data structures only — no ingest logic, no synthesis changes.

</domain>

<decisions>
## Implementation Decisions

### SourceItem Fields
- Source type taxonomy: Claude's discretion — pick approach that fits existing codebase patterns (exact enum vs grouped enum with sub_type)
- Context info: Both structured context dict (machine-readable) AND display_context string (human-readable for synthesis output)
- Participants: Always tracked on every SourceItem — list of participants enables "what did Person X do today" queries across all sources
- Relevance signal: None on the model — synthesis decides importance (matches v1.0 pattern)
- Source URL: Always present — source_url field on every SourceItem for click-through from summaries to original context
- Content type: Explicit content_type field to distinguish formats (message, thread, note, edit, stage_change, etc.) — helps synthesis handle different shapes

### Commitment Semantics
- Definition: Explicit promises AND assigned action items — not vague intentions like "we should look into that"
- Deadline handling: by_when is optional, null OK — commitment still tracked without a date, downstream can flag undated commitments
- Status tracking: Include status enum (open, completed, deferred) on the model now — even if v1.5 only creates "open" ones, the field is ready
- Ownership: Single owner field — the person responsible for doing the thing. No separate assigner field.

### Content Representation
- Storage: Full raw content AND a pre-computed summary/excerpt field — synthesis can use either depending on context
- Summary generation: Ingest modules generate excerpts at fetch time — summary ready before synthesis runs, keeps synthesis focused on cross-source work
- Source links: source_url always present for traceability

### Cross-Model Relationships
- Model relationship: SourceItem and NormalizedEvent are peer models implementing a shared interface/protocol — synthesis accepts both, no changes to existing NormalizedEvent
- Commitment attribution: Direct reference (source_id or source_ref) pointing to the SourceItem/NormalizedEvent the commitment was extracted from
- Pipeline output: Unified collection — synthesis receives one list of all source items (meetings become interface-compatible alongside new sources). Cleaner for Phase 10 cross-source dedup.
- Attribution format: Common attribution_text() method on the shared interface — all sources produce consistent "(per Source X)" strings

### Claude's Discretion
- Source type enum design (exact vs grouped)
- Shared interface implementation approach (Protocol, ABC, or mixin)
- Field naming conventions and validation rules
- How NormalizedEvent adapts to the shared interface without breaking existing code

</decisions>

<specifics>
## Specific Ideas

- Unified collection approach was chosen specifically to make Phase 10 (cross-source dedup) cleaner
- attribution_text() should produce strings like "(per Slack #channel-name)", "(per HubSpot deal)", "(per Google Doc [title])" — consistent with SYNTH-07 requirement
- Participants field aligns with existing NormalizedEvent pattern (attendees) — should feel familiar

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 06-data-model-foundation*
*Context gathered: 2026-04-03*
