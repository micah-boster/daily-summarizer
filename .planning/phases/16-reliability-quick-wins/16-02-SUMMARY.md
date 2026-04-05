---
phase: 16-reliability-quick-wins
plan: 02
subsystem: operations
tags: [cache, cleanup, retention]

requires:
  - phase: 13-typed-config-foundation
    provides: Pydantic config model for new CacheConfig section
provides:
  - Automatic raw cache cleanup at pipeline startup
  - Configurable TTL for raw data (14 days) and dedup logs (30 days)
  - Safe exclusion of processed output from cleanup
affects: [pipeline, operations]

tech-stack:
  added: []
  patterns:
    - "Startup cleanup hook: run maintenance at pipeline start before ingest"
    - "Safe directory exclusion: only walk explicitly targeted dirs (raw, dedup_logs)"
    - "Bottom-up empty directory cleanup after file deletion"

key-files:
  created:
    - src/cache_cleanup.py
    - tests/test_cache_cleanup.py
  modified:
    - src/config.py
    - src/pipeline.py

key-decisions:
  - "Cleanup runs at very start of run_pipeline(), before any ingest"
  - "Only walks output/raw/ and output/dedup_logs/ -- never daily/, quality/, validation/"
  - "Uses file mtime for age detection (simple, works with existing cache structure)"
  - "Separate TTL for dedup logs (30 days) vs raw cache (14 days)"

patterns-established:
  - "Pipeline startup hook pattern: maintenance tasks before ingest begins"
  - "CacheConfig Pydantic model with raw_ttl_days and dedup_log_ttl_days"

requirements-completed: [OPS-01]

duration: 5min
completed: 2026-04-05
---

# Phase 16: Reliability Quick Wins - Plan 02 Summary

**Automatic cache retention policy deletes raw data files older than 14-day TTL at pipeline startup**

## What Changed
- New `src/cache_cleanup.py` module with `cleanup_raw_cache()` function
- Pipeline calls cleanup at startup before ingest begins
- `CacheConfig` model with `raw_ttl_days` (14) and `dedup_log_ttl_days` (30)
- Empty directories cleaned up bottom-up after file deletion
- Processed output (daily/, quality/, validation/) never touched

## Self-Check: PASSED
- [x] All 7 cache cleanup tests pass
- [x] Old raw files deleted, recent files preserved (verified by test)
- [x] daily/ and quality/ directories never touched (verified by test)
- [x] Dedup logs use separate 30-day TTL (verified by test)
