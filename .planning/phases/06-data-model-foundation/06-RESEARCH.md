# Phase 6: Data Model Foundation - Research

**Researched:** 2026-04-03
**Domain:** Pydantic data modeling, Python Protocol-based interfaces, shared model architecture
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### SourceItem Fields
- Source type taxonomy: Claude's discretion — pick approach that fits existing codebase patterns (exact enum vs grouped enum with sub_type)
- Context info: Both structured context dict (machine-readable) AND display_context string (human-readable for synthesis output)
- Participants: Always tracked on every SourceItem — list of participants enables "what did Person X do today" queries across all sources
- Relevance signal: None on the model — synthesis decides importance (matches v1.0 pattern)
- Source URL: Always present — source_url field on every SourceItem for click-through from summaries to original context
- Content type: Explicit content_type field to distinguish formats (message, thread, note, edit, stage_change, etc.) — helps synthesis handle different shapes

#### Commitment Semantics
- Definition: Explicit promises AND assigned action items — not vague intentions like "we should look into that"
- Deadline handling: by_when is optional, null OK — commitment still tracked without a date, downstream can flag undated commitments
- Status tracking: Include status enum (open, completed, deferred) on the model now — even if v1.5 only creates "open" ones, the field is ready
- Ownership: Single owner field — the person responsible for doing the thing. No separate assigner field.

#### Content Representation
- Storage: Full raw content AND a pre-computed summary/excerpt field — synthesis can use either depending on context
- Summary generation: Ingest modules generate excerpts at fetch time — summary ready before synthesis runs, keeps synthesis focused on cross-source work
- Source links: source_url always present for traceability

#### Cross-Model Relationships
- Model relationship: SourceItem and NormalizedEvent are peer models implementing a shared interface/protocol — synthesis accepts both, no changes to existing NormalizedEvent
- Commitment attribution: Direct reference (source_id or source_ref) pointing to the SourceItem/NormalizedEvent the commitment was extracted from
- Pipeline output: Unified collection — synthesis receives one list of all source items (meetings become interface-compatible alongside new sources). Cleaner for Phase 10 cross-source dedup.
- Attribution format: Common attribution_text() method on the shared interface — all sources produce consistent "(per Source X)" strings

### Claude's Discretion
- Source type enum design (exact vs grouped)
- Shared interface implementation approach (Protocol, ABC, or mixin)
- Field naming conventions and validation rules
- How NormalizedEvent adapts to the shared interface without breaking existing code

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| MODEL-01 | New `SourceItem` Pydantic model for non-meeting sources (Slack messages, HubSpot activities, Doc edits) parallel to existing `NormalizedEvent` | Pydantic v2 BaseModel patterns, StrEnum for source types, field validation, Protocol-based shared interface |
| MODEL-02 | Commitment data structure captures who, what, by-when with source attribution | Pydantic v2 optional datetime fields, StrEnum for status, source reference pattern |
</phase_requirements>

## Summary

This phase introduces two new Pydantic v2 models (`SourceItem` and `Commitment`) and a shared interface (`SynthesisSource` Protocol) that unifies how the synthesis pipeline consumes data from both existing meeting events and new sources (Slack, HubSpot, Docs). The existing `NormalizedEvent` and `DailySynthesis` models must remain completely unchanged — the shared interface is structural conformance via Python's `typing.Protocol`, requiring zero modifications to `NormalizedEvent`.

The codebase already uses Pydantic v2 (2.12.5) with `BaseModel`, `Field`, and `StrEnum` consistently. The project follows a clean pattern: models in `src/models/`, synthesis logic in `src/synthesis/`, tests in `tests/test_models.py`. All new models belong in `src/models/` following established conventions. The existing `NormalizedEvent` already has `id`, `title`, `source`, `attendees`, `start_time`, and `transcript_text` fields that map naturally to the shared interface.

**Primary recommendation:** Use `typing.Protocol` with `@runtime_checkable` for the shared `SynthesisSource` interface. This is the cleanest approach because it requires zero changes to `NormalizedEvent` — Protocol uses structural subtyping (duck typing), so any class with the right attributes/methods automatically satisfies the Protocol. Add `attribution_text()` as a standalone function on NormalizedEvent's module (or a thin adapter) rather than modifying the class itself.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | 2.12.5 (installed) | Model validation, serialization | Already the project standard for all models |
| typing / typing_extensions | stdlib | Protocol, runtime_checkable | Standard Python structural subtyping — no dependencies |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| enum (StrEnum) | stdlib (3.12) | Source type, content type, commitment status enums | Already used for ResponseStatus in events.py |
| datetime | stdlib | Timestamp fields on SourceItem, by_when on Commitment | Already used throughout codebase |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Protocol (structural) | ABC (nominal) | ABC requires NormalizedEvent to inherit from it — breaks "no changes" requirement |
| Protocol (structural) | Mixin class | Mixin adds method to NormalizedEvent — technically modifies the class. Protocol avoids this |
| StrEnum for source types | Literal union | StrEnum is already the project pattern (see ResponseStatus). More extensible. |

**Installation:**
No new packages needed. Everything uses stdlib + already-installed pydantic 2.12.5.

## Architecture Patterns

### Recommended Project Structure
```
src/models/
├── __init__.py           # (empty, existing)
├── events.py             # NormalizedEvent, DailySynthesis (UNCHANGED)
├── rollups.py            # Weekly/Monthly models (UNCHANGED)
├── sources.py            # NEW: SourceItem, SynthesisSource Protocol
└── commitments.py        # NEW: Commitment model
```

### Pattern 1: Protocol-Based Shared Interface (SynthesisSource)
**What:** A `typing.Protocol` that defines the common contract both `NormalizedEvent` and `SourceItem` satisfy. Synthesis code types its inputs as `SynthesisSource` instead of `NormalizedEvent`.
**When to use:** Whenever synthesis or downstream code needs to accept items from any source.
**Why Protocol over ABC:** `NormalizedEvent` already satisfies the interface structurally — no code changes needed. Protocol is the only approach that achieves "peer models, no regressions."

```python
from typing import Protocol, runtime_checkable
from datetime import datetime

@runtime_checkable
class SynthesisSource(Protocol):
    """Interface that both NormalizedEvent and SourceItem implement."""
    @property
    def source_id(self) -> str: ...
    @property
    def source_type(self) -> str: ...
    @property
    def title(self) -> str: ...
    @property
    def timestamp(self) -> datetime | None: ...
    @property
    def participants_list(self) -> list[str]: ...
    @property
    def content_for_synthesis(self) -> str | None: ...

    def attribution_text(self) -> str: ...
```

**Key design choice:** The Protocol uses property names that may differ from the model's actual field names. This avoids forcing `NormalizedEvent` field renames. Instead, NormalizedEvent gets lightweight computed properties (or a thin adapter/wrapper) that map its existing fields to the Protocol interface.

**Two viable sub-approaches for NormalizedEvent conformance:**

*Option A — Computed properties added to NormalizedEvent (minimal touch):*
Add `@property` methods to NormalizedEvent that alias existing fields. E.g., `source_id` returns `self.id`, `timestamp` returns `self.start_time`. This does modify the class file but not the data model — no field changes, no serialization changes, all existing tests pass.

*Option B — Adapter function (zero-touch NormalizedEvent):*
Create a `NormalizedEventAdapter` wrapper or standalone functions. Synthesis receives adapters rather than raw NormalizedEvents. More indirection but truly zero changes to events.py.

**Recommendation:** Option A (computed properties). Adding read-only `@property` methods to NormalizedEvent is invisible to existing code — Pydantic v2 ignores non-field properties during serialization, validation, and `model_dump()`. This is the simplest path that fully satisfies "no regressions" because nothing about the data schema changes.

### Pattern 2: StrEnum Source Type Taxonomy
**What:** A `StrEnum` defining all source types across the system.
**When to use:** Every SourceItem declares its source type.

```python
from enum import StrEnum

class SourceType(StrEnum):
    SLACK_MESSAGE = "slack_message"
    SLACK_THREAD = "slack_thread"
    HUBSPOT_DEAL = "hubspot_deal"
    HUBSPOT_CONTACT = "hubspot_contact"
    HUBSPOT_TICKET = "hubspot_ticket"
    GOOGLE_DOC_EDIT = "google_doc_edit"
    GOOGLE_DOC_COMMENT = "google_doc_comment"
    MEETING = "meeting"  # For NormalizedEvent compatibility
```

**Rationale for flat enum over grouped:** The existing codebase uses flat StrEnums (ResponseStatus). The content_type field already captures sub-categories (message vs thread vs note). A grouped approach would add complexity without clear benefit at this scale.

### Pattern 3: Content Type Enum
**What:** Distinguishes the shape/format of the content within a SourceItem.

```python
class ContentType(StrEnum):
    MESSAGE = "message"
    THREAD = "thread"
    NOTE = "note"
    EDIT = "edit"
    STAGE_CHANGE = "stage_change"
    COMMENT = "comment"
    ACTIVITY = "activity"
```

### Pattern 4: Commitment Status Enum
**What:** Status tracking for commitments, future-proofed.

```python
class CommitmentStatus(StrEnum):
    OPEN = "open"
    COMPLETED = "completed"
    DEFERRED = "deferred"
```

### Anti-Patterns to Avoid
- **Modifying NormalizedEvent fields:** Any rename or removal of existing fields breaks the 16 tests in test_models.py and all downstream code. Use additive-only changes (computed properties).
- **Inheritance from a shared base class:** Making NormalizedEvent inherit from a new base would change MRO and potentially break Pydantic's metaclass machinery. Protocol avoids this entirely.
- **Storing Commitment as a nested field inside SourceItem:** Commitments reference source items but are a separate concern. Keep them as peer models with attribution via source_id reference.
- **Using `dict` for context:** The user explicitly wants BOTH structured context dict AND display_context string. Don't collapse to just one.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Model validation | Custom __init__ checks | Pydantic validators, Field constraints | Pydantic v2 handles this — consistent with codebase |
| Enum serialization | Custom to_json methods | StrEnum (auto-serializes in Pydantic v2) | Pydantic v2 natively serializes StrEnum values |
| Optional datetime parsing | Manual string parsing | Pydantic's datetime coercion | Pydantic v2 auto-parses ISO strings to datetime |
| JSON round-trips | json.dumps/loads | model_dump_json() / model_validate_json() | Already used in test_models.py round-trip tests |

**Key insight:** Pydantic v2 handles all serialization, validation, and type coercion. The only custom code needed is the Protocol definition and the `attribution_text()` method implementations.

## Common Pitfalls

### Pitfall 1: Breaking NormalizedEvent Serialization with Properties
**What goes wrong:** Adding a `@property` to a Pydantic v2 BaseModel that conflicts with a field name causes serialization errors.
**Why it happens:** Pydantic v2 uses `model_fields` for serialization. A `@property` with a name matching a model field overrides the field accessor.
**How to avoid:** Protocol property names MUST NOT collide with existing NormalizedEvent field names. Use distinct names: `source_id` (not `id`), `timestamp` (not `start_time`), `participants_list` (not `attendees`).
**Warning signs:** `model_dump()` output changes or test_models.py tests fail.

### Pitfall 2: Protocol isinstance Checks at Runtime
**What goes wrong:** `isinstance(obj, SynthesisSource)` only checks for method/attribute existence, not signatures or return types.
**Why it happens:** Python's `@runtime_checkable` Protocol only does structural checks on attribute names, not types.
**How to avoid:** Use `isinstance` checks sparingly (e.g., at pipeline entry points for sanity checks). Rely on static type checking (mypy/pyright) for full Protocol conformance.
**Warning signs:** An object passes `isinstance` but fails at runtime because it returns the wrong type from a property.

### Pitfall 3: Forgetting `from __future__ import annotations`
**What goes wrong:** Forward references in type hints cause NameErrors at import time.
**Why it happens:** Without PEP 563 deferred evaluation, Python evaluates annotations eagerly.
**How to avoid:** Every module in this project already uses `from __future__ import annotations` at the top. Continue this pattern in new files.
**Warning signs:** Import-time NameError mentioning a model class name.

### Pitfall 4: Circular Imports Between Model Files
**What goes wrong:** `sources.py` imports from `events.py` (for NormalizedEvent), `commitments.py` imports from `sources.py` (for SourceItem reference), creating cycles.
**Why it happens:** Models referencing each other across files.
**How to avoid:** Keep the Protocol definition in `sources.py`. Commitment references sources by `source_id: str` (a plain string), not by importing the SourceItem class directly. No circular dependency.
**Warning signs:** ImportError at module load time.

### Pitfall 5: Over-engineering the Shared Interface
**What goes wrong:** Putting too many methods on the Protocol makes it hard for NormalizedEvent to conform without invasive changes.
**Why it happens:** Temptation to pre-build everything Phase 10 might need.
**How to avoid:** Keep the Protocol minimal — only what synthesis actually needs now: identity, timestamp, content, participants, attribution. Phase 10 can extend it.
**Warning signs:** More than 8-10 members on the Protocol.

## Code Examples

Verified patterns from the existing codebase:

### Existing StrEnum Pattern (from events.py)
```python
# Source: src/models/events.py lines 9-13
class ResponseStatus(StrEnum):
    ACCEPTED = "accepted"
    DECLINED = "declined"
    TENTATIVE = "tentative"
    NEEDS_ACTION = "needsAction"
```

### Existing Pydantic Model Pattern (from events.py)
```python
# Source: src/models/events.py lines 24-43
class NormalizedEvent(BaseModel):
    id: str
    source: str = "google_calendar"
    title: str
    start_time: datetime | None = None
    # ... (uses Field defaults, optional fields, list fields)
    attendees: list[Attendee] = Field(default_factory=list)
    transcript_text: str | None = None
```

### SourceItem Model (recommended shape)
```python
class SourceItem(BaseModel):
    """A work item from any non-meeting source."""
    id: str                                   # Unique ID (e.g., "slack_C123_1234567890")
    source_type: SourceType                   # e.g., SourceType.SLACK_MESSAGE
    content_type: ContentType                 # e.g., ContentType.MESSAGE
    title: str                                # Human-readable title/subject
    timestamp: datetime                       # When this item occurred
    content: str                              # Full raw content
    summary: str | None = None                # Pre-computed excerpt for synthesis
    participants: list[str] = Field(default_factory=list)  # People involved
    source_url: str                           # Click-through URL
    context: dict = Field(default_factory=dict)            # Machine-readable context
    display_context: str = ""                 # Human-readable context string
    raw_data: dict | None = None              # Original API response

    def attribution_text(self) -> str:
        """Produce consistent attribution string for synthesis output."""
        # e.g., "(per Slack #channel-name)", "(per HubSpot deal)"
        return f"(per {self.display_context})" if self.display_context else f"(per {self.source_type.value})"
```

### Commitment Model (recommended shape)
```python
class Commitment(BaseModel):
    """An explicit promise or assigned action item extracted from a source."""
    id: str                                        # Unique commitment ID
    owner: str                                     # Who is responsible
    description: str                               # What they committed to
    by_when: datetime | None = None                # Deadline (optional per user decision)
    status: CommitmentStatus = CommitmentStatus.OPEN
    source_id: str                                 # ID of the SourceItem/NormalizedEvent
    source_type: str                               # "source_item" or "normalized_event"
    source_context: str = ""                       # Display string for attribution
    extracted_at: datetime | None = None           # When this commitment was extracted
```

### NormalizedEvent Protocol Conformance (computed properties)
```python
# Added to NormalizedEvent in events.py — additive only, no field changes
@property
def source_id(self) -> str:
    return self.id

@property
def timestamp(self) -> datetime | None:
    return self.start_time

@property
def participants_list(self) -> list[str]:
    return [a.name or a.email for a in self.attendees]

@property
def content_for_synthesis(self) -> str | None:
    return self.transcript_text

def attribution_text(self) -> str:
    return f"(per {self.title})"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Pydantic v1 validators | Pydantic v2 `@field_validator`, `model_validator` | Pydantic 2.0 (2023) | Already on v2 — use v2 patterns only |
| ABC for shared interfaces | Protocol (PEP 544) | Python 3.8+ | Protocol enables structural subtyping without inheritance |
| Manual JSON serialization | `model_dump_json()` / `model_validate_json()` | Pydantic 2.0 | Already used in test_models.py |

**Deprecated/outdated:**
- Pydantic v1 `validator` decorator: use `field_validator` instead (project already uses v2 patterns)
- `schema_extra` config: replaced by `json_schema_extra` in v2 (not currently used in project)

## Open Questions

1. **NormalizedEvent `attribution_text()` format**
   - What we know: User wants "(per Slack #channel-name)", "(per HubSpot deal)" style strings per SYNTH-07
   - What's unclear: What should NormalizedEvent's attribution look like? "(per [meeting title])" or "(per Google Calendar)" or "(per meeting: [title])"?
   - Recommendation: Use `"(per {self.title})"` — meeting title is most informative for attribution. Can refine in Phase 10 if needed.

2. **SourceItem ID generation strategy**
   - What we know: Each SourceItem needs a unique `id` field
   - What's unclear: Convention for composing IDs across sources (e.g., `slack_C123_ts1234` vs UUID)
   - Recommendation: Use source-prefixed deterministic IDs (e.g., `slack_{channel}_{ts}`, `hubspot_deal_{id}`) so the same item always produces the same ID. This supports dedup in Phase 10. Leave exact format to ingest modules in Phases 7-9.

3. **Commitment extraction timing**
   - What we know: MODEL-02 defines the Commitment data structure. SYNTH-08 (Phase 10) handles extraction.
   - What's unclear: Whether Phase 6 needs test fixtures that demonstrate commitment creation
   - Recommendation: Phase 6 creates the model and validates it can be instantiated. Commitment extraction logic is Phase 10 scope (SYNTH-08).

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `src/models/events.py` — existing NormalizedEvent, DailySynthesis, StrEnum patterns
- Codebase inspection: `src/synthesis/models.py` — existing MeetingExtraction patterns
- Codebase inspection: `tests/test_models.py` — existing test patterns (184 tests collected)
- Codebase inspection: `pyproject.toml` — pydantic 2.12.5, Python 3.12
- [Pydantic v2 Models docs](https://docs.pydantic.dev/latest/concepts/models/) — BaseModel API, field configuration
- [Pydantic v2 Types docs](https://docs.pydantic.dev/latest/concepts/types/) — type validation, custom types

### Secondary (MEDIUM confidence)
- [Pydantic Protocol discussion #5767](https://github.com/pydantic/pydantic/discussions/5767) — Protocol as field type requires `arbitrary_types_allowed`
- [Pydantic Protocol issue #10161](https://github.com/pydantic/pydantic/issues/10161) — Protocol type support limitations
- [Pydantic Protocol issue #11878](https://github.com/pydantic/pydantic/issues/11878) — defining Protocol for Pydantic models

### Tertiary (LOW confidence)
- None — all claims verified against codebase or official Pydantic docs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — project already uses Pydantic v2 + StrEnum; no new dependencies
- Architecture: HIGH — Protocol pattern verified against Python 3.12 stdlib and Pydantic v2 compatibility; codebase patterns well-understood
- Pitfalls: HIGH — pitfalls derived from direct codebase analysis (field name conflicts, import patterns)

**Research date:** 2026-04-03
**Valid until:** 2026-05-03 (stable domain — Pydantic v2 and stdlib typing are mature)
