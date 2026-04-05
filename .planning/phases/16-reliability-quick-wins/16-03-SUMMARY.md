---
phase: 16-reliability-quick-wins
plan: 03
subsystem: intelligence
tags: [dedup, similarity, difflib]

requires:
  - phase: 13-typed-config-foundation
    provides: Pydantic config model for new DedupConfig section
  - phase: 06-data-model-foundation
    provides: SourceItem model with title, timestamp, source_type
provides:
  - Algorithmic cross-source dedup pre-filter before LLM synthesis
  - Title similarity matching using difflib SequenceMatcher
  - Dedup decision logging to separate file for threshold tuning
  - Configurable similarity threshold and enable/disable toggle
affects: [pipeline, synthesis]

tech-stack:
  added: []
  patterns:
    - "Pre-synthesis filter: deterministic dedup before LLM processing"
    - "Union-find clustering for grouping similar items"
    - "Separate decision log file for operational review"

key-files:
  created:
    - src/dedup.py
    - tests/test_dedup.py
  modified:
    - src/config.py
    - src/pipeline.py

key-decisions:
  - "difflib.SequenceMatcher for title similarity (no external deps)"
  - "0.85 default threshold (conservative to minimize false positives)"
  - "Only compare items within same calendar day"
  - "Merge keeps longest content, unions participants, uses earliest timestamp"
  - "Redistribution only happens when items are actually merged (avoids test interference)"
  - "Dedup decisions logged to output/dedup_logs/dedup_YYYY-MM-DD.log"

patterns-established:
  - "DedupConfig model with enabled, similarity_threshold, log_dir"
  - "Union-find clustering for grouping items by similarity"
  - "Conditional redistribution: only re-split when merges occurred"

requirements-completed: [DEDUP-01]

duration: 5min
completed: 2026-04-05
---

# Phase 16: Reliability Quick Wins - Plan 03 Summary

**Cross-source dedup pre-filter consolidates near-identical items before LLM synthesis using 0.85 title similarity threshold**

## What Changed
- New `src/dedup.py` module with `dedup_source_items()` function
- Pipeline runs dedup after all ingest, before synthesis
- Items with similar titles (>= 0.85 ratio) on the same day are merged
- Merge decisions logged to `output/dedup_logs/dedup_YYYY-MM-DD.log`
- `DedupConfig` model with `enabled`, `similarity_threshold`, `log_dir`
- Can be disabled via `dedup.enabled: false` in config.yaml

## Self-Check: PASSED
- [x] All 9 dedup tests pass
- [x] Identical and near-identical titles merged (verified by test)
- [x] Different-day items never merged (verified by test)
- [x] Decision log written with titles, sources, scores (verified by test)
- [x] Disabled config skips dedup (verified by test)
- [x] Full test suite (458 tests) passes with no regressions
