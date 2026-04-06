---
phase: 20-entity-discovery-backfill
verified: 2026-04-06T18:30:00Z
status: passed
score: 5/5 success criteria verified
re_verification: false
---

# Phase 20: Entity Discovery + Backfill Verification Report

**Phase Goal:** The entity registry is populated -- both from 6+ months of historical summaries and automatically on each new pipeline run -- with HubSpot cross-referencing for enrichment
**Verified:** 2026-04-06T18:30:00Z
**Status:** PASSED
**Re-verification:** No -- initial verification

---

## Goal Achievement

### Observable Truths (from ROADMAP.md Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `entity backfill --from 2025-10-01 --to 2026-04-05` scans existing sidecar JSONs and populates the registry | VERIFIED | `src/entity/backfill.py` implements `run_backfill()` with full date-range scanning, sidecar-first fallback to markdown, weekly batching with per-batch checkpoint |
| 2 | A normal daily pipeline run automatically discovers and registers new entities post-synthesis | VERIFIED | `_discover_and_register_entities()` in `src/pipeline_async.py` (line 43) is called at line 509 after sidecar writing, wrapped in try/except for graceful degradation |
| 3 | Discovered entities are cross-referenced with HubSpot contacts/deals by name match | VERIFIED | `src/entity/hubspot_xref.py` implements `cross_reference_entity()` dispatching to `search_hubspot_contact()` and `search_hubspot_deal()` with rapidfuzz fuzzy fallback; wired into both backfill (batch-level) and pipeline (per-entity) |
| 4 | Entity extraction uses structured output fields (entity_names on Pydantic models) and does not break the pipeline on failure | VERIFIED | `SynthesisItem` and `CommitmentRow` both carry `entity_names: list[str] = Field(default_factory=list)` in `src/synthesis/models.py` (lines 63, 75); entire entity discovery block in pipeline_async.py is wrapped in try/except |
| 5 | Name normalization handles common variants so "Affirm Inc" and "Affirm" resolve to the same entity | VERIFIED | `src/entity/normalizer.py` strips 16 suffix variants via compiled regex; `normalize_for_matching()` produces lowercase comparison strings; used before registry lookup in both backfill and pipeline |

**Score:** 5/5 truths verified

---

## Required Artifacts

### Plan 20-01 Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/entity/normalizer.py` | Name normalization for companies and people | VERIFIED | 110 lines; `normalize_company_name`, `normalize_for_matching`, `names_match_person` all implemented with real logic (compiled regex, prefix-based person matching) |
| `src/entity/discovery.py` | Entity extraction via Claude structured outputs | VERIFIED | 135 lines; `DiscoveredEntity`, `EntityExtractionOutput`, `ENTITY_EXTRACTION_PROMPT` with `{text}` placeholder, `extract_entities()` using `@retry_api_call` |
| `src/synthesis/models.py` | Extended with entity_names | VERIFIED | `entity_names: list[str] = Field(default_factory=list)` on both `SynthesisItem` (line 63) and `CommitmentRow` (line 75) |
| `tests/test_entity_normalizer.py` | Tests for name normalization | VERIFIED | 28 tests covering suffix stripping, normalize_for_matching, names_match_person -- all pass |
| `tests/test_discovery.py` | Tests for entity extraction | VERIFIED | 10 tests including mock Claude response, empty text guard, API failure graceful degradation -- all pass |

### Plan 20-02 Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/entity/backfill.py` | Backfill orchestrator with weekly batching, checkpoint/resume | VERIFIED | 308 lines; `run_backfill()` with weekly batching (7-day batches), per-batch `conn.commit()`, `_is_day_processed` / `_record_day_processed` helpers, `--force` support |
| `src/entity/cli.py` | Extended CLI with backfill subcommand | VERIFIED | `entity backfill --from YYYY-MM-DD --to YYYY-MM-DD [--force]` parser registered at line 68; `_cmd_backfill()` handler at line 229 calls `run_backfill()` |
| `src/entity/migrations.py` | Schema v2 migration adding backfill_progress table | VERIFIED | `_migrate_v1_to_v2()` creates `backfill_progress` table with correct schema; `SCHEMA_VERSION = 2`; assertion ensures migration count matches version |
| `src/pipeline_async.py` | Post-synthesis entity discovery wired | VERIFIED | `_discover_and_register_entities()` at line 43; called at line 509; collects entity_names from substance/decisions/commitments; full try/except wrapping |
| `tests/test_backfill.py` | Tests for backfill orchestrator | VERIFIED | 16 tests covering sidecar/markdown fallback, progress tracking, force flag, deduplication via normalization, weekly batching -- all pass |

### Plan 20-03 Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/entity/hubspot_xref.py` | HubSpot contact/deal search with fuzzy matching | VERIFIED | 129 lines; `search_hubspot_contact()`, `search_hubspot_deal()`, `cross_reference_entity()`; FUZZY_THRESHOLD=80; rapidfuzz token_sort_ratio |
| `tests/test_hubspot_xref.py` | Tests for HubSpot cross-reference | VERIFIED | 16 tests covering exact/fuzzy contact search, deal search, type dispatch, API error handling, empty token guard -- all pass |
| `src/entity/repository.py` | update_hubspot_id method | VERIFIED | `update_hubspot_id()` at line 157 merges HubSpot ID and metadata into entity record via SQL UPDATE with optional metadata merge |

---

## Key Link Verification

### Plan 20-01 Key Links

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `src/entity/discovery.py` | `src/synthesis/models.py` | `EntityExtractionOutput` | WIRED | `EntityExtractionOutput` defined in discovery.py, used to validate Claude structured output response |
| `src/entity/discovery.py` | `src/entity/normalizer.py` | `normalize_for_matching` | NOT WIRED | discovery.py does not import from normalizer.py -- normalization happens in backfill.py and pipeline_async.py before passing names to the repository, not inside extract_entities() itself. This is acceptable: extract_entities returns raw DiscoveredEntity objects; callers normalize before lookup. |

### Plan 20-02 Key Links

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `src/entity/backfill.py` | `src/entity/discovery.py` | `extract_entities` | WIRED | Line 19: `from src.entity.discovery import extract_entities`; called at line 205 |
| `src/entity/backfill.py` | `src/entity/repository.py` | `EntityRepository` | WIRED | Line 21: `from src.entity.repository import EntityRepository`; used at line 190 as context manager |
| `src/entity/backfill.py` | `src/entity/normalizer.py` | `normalize_for_matching` | WIRED | Line 20: `from src.entity.normalizer import normalize_for_matching`; called at line 215 before registry lookup |
| `src/pipeline_async.py` | `src/entity/discovery.py` | `_discover_and_register_entities` | WIRED | Function defined at line 43; called at line 509 in `async_pipeline()` |

### Plan 20-03 Key Links

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `src/entity/hubspot_xref.py` | `src/entity/normalizer.py` | `normalize_for_matching` | WIRED | Line 16: `from src.entity.normalizer import normalize_for_matching`; used in `search_hubspot_deal()` at line 53 |
| `src/entity/backfill.py` | `src/entity/hubspot_xref.py` | `cross_reference_entity` | WIRED | Lazy import at line 264; called at line 272 for each new entity in batch |
| `src/pipeline_async.py` | `src/entity/hubspot_xref.py` | `cross_reference_entity` | WIRED | Lazy import at line 112; called at line 114 for each newly registered entity |

**Note on Plan 20-01 key link:** The plan specified that `discovery.py` normalizes extracted names before returning -- this was not implemented inside `extract_entities()`. Instead normalization correctly happens at the caller level (backfill.py line 215, pipeline_async.py line 86) before registry lookup. The goal is achieved: deduplication via normalization works correctly. This is an architectural difference from the plan but not a gap.

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| DISC-01 | 20-01, 20-02 | System discovers entities by scanning existing daily summary sidecars via backfill command | SATISFIED | `run_backfill()` in backfill.py scans sidecar JSON files (`_read_day_content` prefers sidecar, falls back to markdown); CLI `entity backfill --from --to` fully wired |
| DISC-02 | 20-01, 20-02 | New pipeline runs automatically discover and register new entities as a post-synthesis step | SATISFIED | `_discover_and_register_entities()` called at pipeline_async.py line 509 after sidecar writing, before Slack notification; gracefully skipped on failure |
| DISC-05 | 20-03 | Discovered entities are cross-referenced with HubSpot contacts/deals by name match | SATISFIED | `cross_reference_entity()` dispatches to contact/deal search with exact+fuzzy matching; wired into both backfill (batch level) and pipeline (per entity); `update_hubspot_id()` stores enrichment data |

All three requirements are fully satisfied. No orphaned requirements.

---

## Anti-Patterns Found

No anti-patterns detected. Specific review of:

- No TODO/FIXME/placeholder comments in any phase 20 source files
- The two `return []` occurrences in discovery.py are intentional graceful degradation (empty input guard at line 113, API failure handler at line 134) -- not stubs
- No empty handler implementations
- No console.log-only implementations

---

## Human Verification Required

### 1. Live backfill run against actual output files

**Test:** Run `python -m src.main entity backfill --from 2025-10-01 --to 2026-04-05` against actual output directory
**Expected:** Progress display shows days processed, entities found; registry populated with real partners/people from historical summaries
**Why human:** Cannot verify without actual sidecar files present; test suite uses mocked file I/O

### 2. Live daily pipeline entity discovery

**Test:** Run a daily pipeline run with a real Anthropic API key and verify entity_names are populated in synthesis output
**Expected:** New entities from the day's meetings appear in the entity registry after the pipeline run
**Why human:** Requires live API calls to Claude with real meeting data; synthesis entity_names population depends on Claude following the prompt instruction

### 3. HubSpot cross-reference with live credentials

**Test:** Set `hubspot.access_token` in config and run backfill or pipeline; verify entity records are enriched with HubSpot IDs
**Expected:** Entities matching HubSpot contacts/deals have `hubspot_id` populated; unmatched entities have `pending_enrichment: true` in metadata when token is set
**Why human:** Requires live HubSpot API credentials; test suite uses mocked SDK responses

---

## Test Results Summary

| Test File | Tests | Result |
|-----------|-------|--------|
| tests/test_entity_normalizer.py | 28 | All pass |
| tests/test_discovery.py | 10 | All pass |
| tests/test_backfill.py | 16 | All pass |
| tests/test_hubspot_xref.py | 16 | All pass |
| Full suite | 601 | All pass |

---

## Commit Verification

All 7 phase 20 commits verified in git history:

| Commit | Plan | Description |
|--------|------|-------------|
| `57211f8` | 20-01 Task 1 | feat: add entity name normalizer with company suffix stripping and person matching |
| `5979e1c` | 20-01 Task 2 | feat: add entity extraction module and extend synthesis models with entity_names |
| `fa40f34` | 20-02 Task 1 | feat: backfill orchestrator, schema v2 migration, and CLI command |
| `a219f7e` | 20-02 Task 2 | feat: wire ongoing entity discovery into async_pipeline post-synthesis |
| `3f539d5` | 20-03 Task 1 | feat: add rapidfuzz dependency and update_hubspot_id method |
| `9f30624` | 20-03 Task 2 (RED) | test: add failing tests for HubSpot cross-reference |
| `26e05f4` | 20-03 Task 2 (GREEN) | feat: HubSpot cross-reference with TDD and pipeline wiring |

---

_Verified: 2026-04-06T18:30:00Z_
_Verifier: Claude (gsd-verifier)_
