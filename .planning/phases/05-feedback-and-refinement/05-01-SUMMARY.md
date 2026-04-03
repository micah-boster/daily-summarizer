---
plan: 05-01
title: Priority Configuration and Quality Metrics
status: complete
duration: single-session
tasks_completed: 2
files_created: 4
files_modified: 2
---

# Plan 05-01: Priority Configuration and Quality Metrics

## What Was Built

### Priority Configuration (src/priorities.py)
- `PriorityConfig` Pydantic model with projects, people, topics, suppress lists
- `load_priorities()` loads from config/priorities.yaml with graceful fallback
- `build_priority_context()` scans extractions for priority matches and builds prompt injection string
- Case-insensitive matching across content, participants, and meeting titles
- Empty/missing config produces no change to synthesis behavior (backward compatible)

### Quality Metrics (src/quality.py)
- `save_raw_output()` saves pipeline output to output/raw/daily/ for future comparison
- `detect_edits()` uses difflib to compare raw vs. current, identifies changed sections
- `update_quality_report()` appends to metrics.jsonl and regenerates quality-report.md
- Rolling trends: 7-day/30-day edit rates, most-edited section, average similarity

### Pipeline Integration
- Synthesis prompt now includes `{priority_context}` slot (src/synthesis/synthesizer.py)
- Quality tracking hooks in src/main.py: detect edits before write, save raw after write
- Both features are non-blocking: failures log warnings but don't stop the pipeline

## Key Files

### Created
- config/priorities.yaml — Example priority configuration
- src/priorities.py — PriorityConfig model, loader, prompt builder
- src/quality.py — Diff detection, metrics tracking, report generation
- tests/test_priorities.py — 17 tests for priority configuration
- tests/test_quality.py — 13 tests for quality metrics

### Modified
- src/synthesis/synthesizer.py — Priority context injection into synthesis prompt
- src/main.py — Quality tracking hooks (detect + save)

## Test Results

30 new tests, all passing. Full suite: 158 tests, 0 failures.

## Self-Check

- [x] Priority config loads from YAML with graceful fallback
- [x] Priority matching is case-insensitive
- [x] Empty priorities produce no change to synthesis
- [x] Raw output saved after each run
- [x] Edit detection identifies section-level changes
- [x] Quality report generates with rolling trends
- [x] No regressions in existing tests
