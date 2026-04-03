# Phase 5: Feedback and Refinement - Research

**Completed:** 2026-04-03
**Researcher:** Direct analysis (codebase fully explored)
**Confidence:** HIGH — all integration points verified against existing code

## Executive Summary

Phase 5 adds three features to an existing, well-structured Python pipeline: (1) YAML-based priority configuration that influences synthesis prompts, (2) diff-based quality tracking that compares raw vs. edited output, and (3) JSON sidecar generation alongside daily markdown. All three features integrate cleanly with existing patterns — no architectural changes required.

## Existing Architecture (Integration Points)

### Pipeline Flow (src/main.py)
1. `load_config()` reads `config/config.yaml` → dict
2. Calendar events fetched → `NormalizedEvent` list
3. Transcripts fetched and linked to events
4. Stage 1: `extract_all_meetings()` → `MeetingExtraction` list
5. Stage 2: `synthesize_daily()` → dict with substance/decisions/commitments/executive_summary
6. `DailySynthesis` model built → `write_daily_summary()` → markdown at `output/daily/YYYY/MM/YYYY-MM-DD.md`

### Key Files to Modify
- `src/config.py` — Add priority config loading
- `src/synthesis/synthesizer.py` — Inject priority context into synthesis prompt
- `src/synthesis/prompts.py` — Add priority-aware prompt sections
- `src/output/writer.py` — Add JSON sidecar writer + raw output saver
- `src/main.py` — Wire new features into pipeline
- `src/models/events.py` — Extend DailySynthesis if needed for sidecar data

### Config Structure (config/config.yaml)
Currently flat with `pipeline`, `calendars`, `transcripts`, `synthesis` sections. Priority config can be a separate file (`config/priorities.yaml`) per CONTEXT.md decision, or a new section. CONTEXT.md specifies a separate file.

## Feature 1: Priority Configuration

### Design Approach (Confidence: HIGH)
- **File:** `config/priorities.yaml` — separate from main config per user decision
- **Schema:** Three lists (projects, people, topics) + one suppress list
- **Loading:** New function in `src/config.py` or dedicated `src/priorities.py`
- **Influence mechanism:** Priority items inject additional context into the SYNTHESIS_PROMPT in `src/synthesis/synthesizer.py`

### How Priorities Influence Synthesis
The synthesis prompt (`SYNTHESIS_PROMPT` in `src/synthesis/prompts.py`) can be extended with a priority section:
```
PRIORITY CONTEXT:
High-priority projects: [list]
High-priority people: [list]
High-priority topics: [list]
Suppressed items: [list]

Instructions:
- Give priority items dedicated subsections with extra detail
- Suppress-listed items get one-liner treatment
- Do not add [priority] markers — shape output seamlessly
```

This is injected into the prompt via `synthesize_daily()` which already builds the prompt dynamically. The Claude model handles the emphasis naturally — no code-level filtering needed.

### Priority Matching
- **Projects:** Match against meeting titles, extraction content (substring match)
- **People:** Match against participant names/emails in extractions
- **Topics:** Match against extraction content keywords
- **Suppress:** Match against meeting titles (for recurring noisy meetings)

Matching happens at prompt-construction time, not at extraction time. The prompt tells Claude which items are high-priority and which are suppressed.

### Pydantic Model
```python
class PriorityConfig(BaseModel):
    projects: list[str] = Field(default_factory=list)
    people: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    suppress: list[str] = Field(default_factory=list)
```

## Feature 2: Quality Metrics Tracking

### Design Approach (Confidence: HIGH)
Diff-based quality tracking compares raw pipeline output against the user-edited version on the next run.

### Flow
1. Pipeline generates daily markdown → write to `output/daily/YYYY/MM/YYYY-MM-DD.md`
2. **Also** save raw copy to `output/raw/daily/YYYY/MM/YYYY-MM-DD.raw.md`
3. Next day's run: diff yesterday's raw vs. current file on disk
4. Parse diffs to detect: section edits, additions, deletions, word-level changes
5. Accumulate metrics in `output/quality/quality-report.md` (rolling file)

### Diff Detection
Python's `difflib` (stdlib) provides `unified_diff` and `SequenceMatcher`:
- `unified_diff` for line-level changes
- `SequenceMatcher.ratio()` for overall similarity score
- Parse diff hunks to attribute changes to sections (Substance, Decisions, Commitments)

### Metrics to Track
- **Edit frequency:** What % of daily summaries get edited?
- **Section correction rates:** Which sections get edited most often?
- **Edit magnitude:** Average diff ratio (0 = completely rewritten, 1 = untouched)
- **Data volume:** Meeting count, transcript count, extraction count per run
- **Trend:** Rolling 7-day and 30-day averages

### Quality Report Format
Rolling markdown file updated each run:
```markdown
# Quality Report
Last updated: YYYY-MM-DD

## Recent (Last 7 Days)
| Date | Edit Detected | Similarity | Sections Changed |
|------|--------------|------------|------------------|
| ... | Yes/No | 95% | Commitments |

## Trends
- Edit rate (7d): 40%
- Edit rate (30d): 35%
- Most-edited section: Commitments (60%)
- Average similarity: 92%
```

### Storage
- Raw copies: `output/raw/daily/YYYY/MM/YYYY-MM-DD.raw.md` (mirrors daily structure)
- Quality data: `output/quality/metrics.json` (append-only JSON lines for programmatic access)
- Quality report: `output/quality/quality-report.md` (human-readable, regenerated each run)

## Feature 3: JSON Sidecar Output

### Design Approach (Confidence: HIGH)
Produce `YYYY-MM-DD.json` alongside `YYYY-MM-DD.md` in the same directory.

### Schema (Task-Extraction-First per CONTEXT.md)
```python
class SidecarTask(BaseModel):
    description: str
    owner: str | None = None
    source_meeting: str
    date_captured: str  # ISO date
    due_date: str | None = None
    status: str = "new"  # new, in-progress, completed

class SidecarDecision(BaseModel):
    description: str
    decision_makers: list[str] = Field(default_factory=list)
    rationale: str | None = None
    source_meeting: str

class DailySidecar(BaseModel):
    date: str  # ISO date
    generated_at: str  # ISO datetime
    meeting_count: int
    transcript_count: int
    tasks: list[SidecarTask] = Field(default_factory=list)
    decisions: list[SidecarDecision] = Field(default_factory=list)
    source_meetings: list[dict] = Field(default_factory=list)  # title, time, participants
```

### Generation Strategy
The sidecar is generated from the same `MeetingExtraction` objects that feed the synthesizer. No additional Claude API call needed — the structured data already exists in the extraction models:
- `MeetingExtraction.commitments` → `SidecarTask` (map commitment → task)
- `MeetingExtraction.decisions` → `SidecarDecision`
- Meeting metadata → `source_meetings`

### Writer Integration
Add `write_daily_sidecar()` to `src/output/writer.py`:
```python
def write_daily_sidecar(synthesis: DailySynthesis, output_dir: Path) -> Path:
    # Same path logic as markdown but with .json extension
    sidecar = build_sidecar(synthesis)
    path = file_dir / f"{d.isoformat()}.json"
    path.write_text(sidecar.model_dump_json(indent=2))
    return path
```

## Priority Influence on Roll-Ups (Claude's Discretion)

Per CONTEXT.md, Claude determines how priorities affect weekly/monthly roll-ups:
- **Weekly:** Priority items get thread-level treatment even if single-day. Suppress-listed items excluded from thread detection.
- **Monthly:** Priority projects/topics get dedicated arc mentions if they persist. No structural changes to prompts — just annotate extraction data.

## Dependencies and Risks

### Dependencies
- `difflib` (stdlib) — no new packages for diff detection
- `pydantic` (already in project) — for sidecar models
- `pyyaml` (already in project) — for priorities.yaml loading

### Risks
- **LOW:** Priority matching may produce false positives on common names/words. Mitigation: exact match for people, substring for projects/topics.
- **LOW:** Raw file comparison may fail if output format changes between versions. Mitigation: store raw alongside, compare only when both exist.
- **NONE:** JSON sidecar generation is deterministic from existing extraction data. No new API calls.

## Testing Strategy

### Priority Configuration
- Unit test: load priorities.yaml, validate PriorityConfig model
- Unit test: priority prompt injection produces expected prompt text
- Integration test: synthesis with priorities produces different output emphasis

### Quality Metrics
- Unit test: diff detection correctly identifies section-level changes
- Unit test: metrics accumulation and report generation
- Unit test: no-edit case (raw == current) correctly recorded

### JSON Sidecar
- Unit test: sidecar generation from known MeetingExtraction data
- Unit test: sidecar file written to correct path with correct schema
- Integration test: full pipeline produces both .md and .json files

---

## RESEARCH COMPLETE

All three Phase 5 features integrate cleanly with the existing pipeline architecture. No new dependencies, no architectural changes, no API additions. Priority configuration extends synthesis prompts, quality tracking uses stdlib difflib, and JSON sidecar maps directly from existing extraction models.
