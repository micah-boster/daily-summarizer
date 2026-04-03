# Phase 4: Temporal Roll-Ups - Research

**Researched:** 2026-04-03
**Domain:** LLM-based temporal synthesis (weekly thread detection, monthly narrative generation)
**Confidence:** HIGH

## Summary

Phase 4 adds two new output types alongside the existing daily pipeline: weekly thread-based summaries and monthly thematic narratives. The core technical challenge is **thread detection** -- using Claude to semantically link items across daily summaries into coherent threads with narrative arcs, rather than simply concatenating bullet points.

The existing codebase provides strong foundations: Jinja2 templating (`writer.py`), Anthropic API patterns (`synthesizer.py`, `extractor.py`), Pydantic models (`models.py`, `events.py`), evidence-only validation (`validator.py`), and a CLI-based pipeline (`main.py`). Phase 4 reuses all of these patterns and extends them to multi-day synthesis.

**Primary recommendation:** Build a two-stage weekly pipeline (1. read dailies + detect threads, 2. synthesize into weekly brief) and a single-stage monthly pipeline (read weeklies + synthesize narrative). Both pipelines use the same Anthropic API patterns as the existing daily synthesis, with new Pydantic models, Jinja2 templates, and CLI subcommands.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- LLM-based semantic linking -- Claude reads all dailies for a period and identifies connections across days
- Source material: synthesis sections only (executive summary, substance, decisions, commitments) -- not per-meeting extractions
- Threads show timeline narrative progression: "Mon: raised concern -> Wed: explored options -> Thu: locked in decision"
- Threads ranked by significance, not frequency -- a one-time board decision outranks a recurring standup topic
- Categories (decisions, commitments, substance) become tags on threads, not organizing sections
- 1-2 page executive brief -- scannable in 3-5 minutes
- Significance-based prioritization: important single-day items elevated alongside multi-day threads
- Open commitments and unresolved questions carry forward in a "Still open" section with status tracking
- Standalone file: `output/weekly/YYYY/YYYY-WXX.md`
- Daily files get backlinks to their parent weekly once generated
- Monthly focus on strategic patterns: emerging themes, time allocation shifts, priority arcs over 4 weeks
- Analytical briefing tone (third-person) for monthly
- Light metrics section in monthly: total meetings, hours, top recurring attendees, decision count
- 2-3 pages, ~10 minute read for monthly
- Standalone file: `output/monthly/YYYY/YYYY-MM.md`
- Weekly generated Friday evening; Monthly generated 1st business day of next month
- Always generate weekly even on partial weeks (2-3 dailies) -- note if partial
- CLI triggerable: `python -m work_intel weekly --date YYYY-MM-DD` and `python -m work_intel monthly --date YYYY-MM`
- Both automatic scheduling (via Cowork) and manual CLI supported

### Claude's Discretion
- Exact LLM prompt design for thread detection
- Weekly/monthly Jinja2 template layout and formatting
- How backlinks are inserted into daily files
- Thread significance scoring algorithm
- Partial week annotation format

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TEMP-01 | Temporal roll-ups: weekly summary from accumulated dailies | Thread detection pipeline reads daily .md files from `output/daily/YYYY/MM/`, uses Claude to identify cross-day threads, renders via Jinja2 weekly template |
| TEMP-02 | Temporal roll-ups: monthly narrative with progress and themes | Monthly pipeline reads weekly .md files from `output/weekly/YYYY/`, uses Claude to synthesize thematic arcs, renders via Jinja2 monthly template |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | >=0.45.0 | Claude API for thread detection and narrative synthesis | Already in use for daily pipeline |
| jinja2 | >=3.1.6 | Markdown template rendering for weekly/monthly output | Already in use for daily template |
| pydantic | >=2.12.5 | Data models for threads, weekly/monthly synthesis | Already in use for daily models |
| pyyaml | >=6.0.3 | Config loading | Already in use |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-dateutil | >=2.9.0 | ISO week calculation, month boundary math | Week number derivation, date range iteration |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Claude for thread detection | Embedding-based similarity | Embeddings find surface similarity; Claude understands semantic thread continuity and narrative progression. User locked in LLM approach. |
| Jinja2 for templates | f-strings | Jinja2 already established; templates enable non-code formatting changes |

**Installation:** No new dependencies needed. All libraries already in pyproject.toml.

## Architecture Patterns

### Recommended Project Structure
```
src/
├── synthesis/
│   ├── weekly.py         # Weekly thread detection + synthesis
│   ├── monthly.py        # Monthly narrative synthesis
│   └── prompts.py        # Add weekly/monthly prompt templates (existing file)
├── models/
│   └── rollups.py        # WeeklyThread, WeeklySynthesis, MonthlySynthesis models
├── output/
│   └── writer.py         # Extend with write_weekly_summary, write_monthly_summary
└── main.py               # Add weekly/monthly CLI subcommands
templates/
├── daily.md.j2           # Existing
├── weekly.md.j2           # New: weekly roll-up template
└── monthly.md.j2          # New: monthly narrative template
```

### Pattern 1: Two-Stage Weekly Pipeline
**What:** Stage 1 reads all daily .md files for the week and feeds them to Claude with a thread-detection prompt. Stage 2 takes the detected threads and produces the weekly brief.
**When to use:** Weekly synthesis -- this mirrors the existing daily pipeline's two-stage pattern (extract per-meeting, then synthesize).
**Why:** Thread detection is a distinct cognitive task from narrative synthesis. Separating them gives clearer prompts and better results.

### Pattern 2: Daily File Reader
**What:** Utility function that reads rendered daily .md files from `output/daily/YYYY/MM/YYYY-MM-DD.md` and extracts the synthesis sections (substance, decisions, commitments, executive summary). Strips the per-meeting extractions and calendar sections since user locked the source to synthesis sections only.
**When to use:** Both weekly and monthly pipelines need to read existing output files.

### Pattern 3: Backlink Insertion
**What:** After weekly generation, insert a backlink line at the top of each daily file: `> Part of [Weekly YYYY-WXX](../../../weekly/YYYY/YYYY-WXX.md)`.
**When to use:** After every weekly generation.
**Why:** User specified daily files should get backlinks to their parent weekly.

### Anti-Patterns to Avoid
- **Concatenation disguised as synthesis:** Simply joining daily bullets under weekly headers. The whole point is thread detection and narrative progression.
- **Frequency-based ranking:** Sorting threads by how many days they appear. User explicitly said significance > frequency.
- **Section-organized weeklies:** User locked in that categories become tags, not organizing sections. Threads are the organizing unit.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| ISO week numbers | Manual week calculation | `datetime.date.isocalendar()` | Handles year boundaries correctly |
| Week date ranges | Manual Mon-Fri calculation | `python-dateutil.relativedelta` + `isocalendar()` | Edge cases with partial weeks, year boundaries |
| Markdown file parsing | Custom regex parser | Read full file, split on `## ` headers | Daily output format is controlled by our template; simple parsing suffices |

**Key insight:** The existing daily output is structured markdown from our own template. Parsing it is straightforward string splitting, not general-purpose markdown parsing. No library needed.

## Common Pitfalls

### Pitfall 1: Context Window Overflow
**What goes wrong:** Feeding 5 full daily summaries (including per-meeting extractions and calendar sections) into a single Claude call exceeds useful context.
**Why it happens:** Full daily files include raw calendar listings and per-meeting extraction details.
**How to avoid:** Extract ONLY synthesis sections (substance, decisions, commitments, executive summary) from each daily file. Strip calendar, per-meeting extractions, declined/cancelled sections.
**Warning signs:** Weekly output starts repeating calendar details or per-meeting extraction formatting.

### Pitfall 2: Thread Detection Hallucination
**What goes wrong:** Claude invents connections between unrelated items to fill thread slots.
**Why it happens:** Prompt asks for threads; Claude obliges by finding tenuous connections.
**How to avoid:** Prompt explicitly says "only link items that genuinely refer to the same topic, decision, or commitment. It is fine to have single-day items." Include an escape hatch for items that don't thread.
**Warning signs:** Threads with vague titles like "General Updates" or "Various Discussions."

### Pitfall 3: Monthly Becomes a Longer Weekly
**What goes wrong:** Monthly output is just 4 weekly summaries concatenated, not a thematic narrative.
**Why it happens:** Prompt doesn't emphasize the different purpose (strategic patterns vs. operational detail).
**How to avoid:** Monthly prompt explicitly says "this is NOT a longer weekly. Identify 3-5 thematic arcs. Use analytical third-person tone. Surface patterns invisible at weekly granularity."
**Warning signs:** Monthly output that reads like a chronological log of weeks.

### Pitfall 4: Backlink Race Condition
**What goes wrong:** If daily file is regenerated after backlink insertion, backlink is lost.
**Why it happens:** `write_daily_summary` overwrites the entire file.
**How to avoid:** Backlink insertion should be idempotent (check if already present). When regenerating daily, either preserve existing backlinks or note that re-running weekly will restore them.
**Warning signs:** Missing backlinks after daily re-runs.

## Code Examples

### Reading Daily Files for a Week
```python
# Pattern: collect daily synthesis content for a date range
from pathlib import Path
from datetime import date, timedelta

def read_daily_summaries(output_dir: Path, start: date, end: date) -> list[dict]:
    """Read daily .md files and extract synthesis sections."""
    summaries = []
    current = start
    while current <= end:
        path = output_dir / "daily" / str(current.year) / f"{current.month:02d}" / f"{current.isoformat()}.md"
        if path.exists():
            content = path.read_text()
            # Extract synthesis sections only (substance, decisions, commitments, exec summary)
            sections = _extract_synthesis_sections(content)
            summaries.append({"date": current, "sections": sections, "path": path})
        current += timedelta(days=1)
    return summaries
```

### Weekly Thread Model
```python
# Pattern: Pydantic model for a detected thread
from pydantic import BaseModel, Field

class ThreadEntry(BaseModel):
    """A single day's contribution to a thread."""
    date: date
    content: str
    category: str  # "decision", "commitment", "substance"

class WeeklyThread(BaseModel):
    """A thread traced across multiple days."""
    title: str
    significance: str  # "high", "medium"
    entries: list[ThreadEntry] = Field(default_factory=list)
    progression: str  # Narrative arc: "raised -> explored -> decided"
    status: str  # "resolved", "open", "escalated"
    tags: list[str] = Field(default_factory=list)  # ["decision", "commitment"]
```

### CLI Subcommand Pattern
```python
# Pattern: extending main.py with subcommands
# Current: python -m src.main --from YYYY-MM-DD
# Phase 4: python -m work_intel weekly --date YYYY-MM-DD
#           python -m work_intel monthly --date YYYY-MM
# Note: CLI name from CONTEXT.md; may need __main__.py in work_intel package
# or alias via pyproject.toml scripts entry
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Static rollups (concatenation) | LLM-based thread detection | 2024-2025 | Claude can identify semantic connections humans would make but simple aggregation misses |
| Section-based weekly organization | Thread-based organization | User decision | Threads with category tags instead of category sections with items |

**Deprecated/outdated:**
- None relevant -- this is a greenfield feature in the project

## Open Questions

1. **CLI namespace: `work_intel` vs `src.main`**
   - What we know: CONTEXT.md says `python -m work_intel weekly --date YYYY-MM-DD` but current entry point is `python -m src.main`
   - What's unclear: Whether to create a `work_intel` package alias or update the CLI namespace
   - Recommendation: Add `weekly` and `monthly` subcommands to `src/main.py` using argparse subparsers. Use `python -m src.main weekly --date YYYY-MM-DD` pattern for now; `work_intel` alias can be added via pyproject.toml `[project.scripts]` if desired but is not a phase requirement.

2. **Partial week threshold**
   - What we know: User says "always generate even on partial weeks (2-3 dailies)"
   - What's unclear: What about a week with only 1 daily?
   - Recommendation: Generate for any non-zero daily count. Add a "Partial week: N of 5 business days" annotation in the template.

## Sources

### Primary (HIGH confidence)
- Project codebase analysis -- `src/synthesis/synthesizer.py`, `src/output/writer.py`, `src/models/events.py`, `src/main.py`
- Project templates -- `templates/daily.md.j2`
- Anthropic Python SDK -- existing usage patterns in extractor.py and synthesizer.py
- Python stdlib `datetime` -- `isocalendar()` for ISO week numbers

### Secondary (MEDIUM confidence)
- Jinja2 templating patterns -- consistent with existing `daily.md.j2` usage in the project

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already in use, no new dependencies
- Architecture: HIGH - follows established patterns from daily pipeline (two-stage, Pydantic models, Jinja2 templates)
- Pitfalls: HIGH - identified from codebase analysis and the specific constraints in CONTEXT.md

**Research date:** 2026-04-03
**Valid until:** 2026-05-03 (stable -- no external dependencies changing)
