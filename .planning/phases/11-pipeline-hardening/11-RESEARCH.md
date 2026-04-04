# Phase 11: Pipeline Hardening - Research

**Researched:** 2026-04-04
**Domain:** Python pipeline architecture, dependency management, refactoring
**Confidence:** HIGH

## Summary

Phase 11 is a quality/reliability phase that addresses 9 specific success criteria: bug fixes, architectural decomposition, dead code removal, and dependency pinning. The codebase issues are well-characterized by the v1.5 milestone audit and direct code inspection. No new libraries are needed -- this is purely a refactoring and hardening phase.

The central challenge is decomposing `run_daily()` (a 300-line monolith in `src/main.py`) into a pipeline runner pattern where each source is a pluggable stage. Secondary concerns include fixing a `NameError` bug in the no-credentials path, consolidating duplicate Commitment models, sharing a single Anthropic client across all Claude API calls, and making Slack ingestion date-aware for backfill scenarios.

**Primary recommendation:** Decompose `run_daily()` into a pipeline runner with a source registry pattern. Each ingest source becomes a function with a common signature. The runner iterates sources, collects results, then runs synthesis. This makes all other success criteria (imports, shared client, date passing) fall out naturally.

## Standard Stack

### Core (already installed -- no new deps)
| Library | Version | Purpose | Note |
|---------|---------|---------|------|
| anthropic | >=0.45.0 | Claude API | Share one client instance |
| pydantic | >=2.12.5 | Data models | Consolidate Commitment models |
| uv | (tool) | Dependency management | Lock file + upper-bound pins |

### No new libraries needed
This phase adds zero new dependencies. All work is refactoring existing code.

## Architecture Patterns

### Current Structure (problems)
```
src/main.py          # 550 lines, run_daily() is ~300 lines
  - Inline try/except blocks for each source (Slack, HubSpot, Docs, Calendar)
  - Conditional imports inside function body
  - Each source block manually manages its own error handling
  - No shared Anthropic client -- 5 separate instantiations across files
  - creds variable scoping bug in no-credentials path
```

### Recommended Decomposition

**Pattern: Pipeline Runner with Source Functions**

```python
# src/pipeline.py (NEW)

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import anthropic

@dataclass
class PipelineContext:
    """Shared state passed through all pipeline stages."""
    config: dict
    target_date: date
    output_dir: Path
    template_dir: Path
    claude_client: anthropic.Anthropic  # ONE shared client
    google_creds: object | None = None  # None when unavailable

@dataclass
class IngestResult:
    """Uniform return type from all ingest sources."""
    events: list  # NormalizedEvent list (calendar only)
    source_items: list  # SourceItem list (Slack, HubSpot, Docs)
    extractions: list  # MeetingExtraction list (calendar+transcript only)

def run_pipeline(ctx: PipelineContext) -> None:
    """Orchestrate: ingest all sources -> synthesize -> output."""
    # Phase 1: Ingest (each source independent)
    calendar_result = ingest_calendar(ctx)
    slack_result = ingest_slack(ctx)
    hubspot_result = ingest_hubspot(ctx)
    docs_result = ingest_docs(ctx)

    # Phase 2: Synthesize (merges all results)
    synthesis_result = run_synthesis(ctx, calendar_result, slack_result,
                                     hubspot_result, docs_result)

    # Phase 3: Output (write markdown, sidecar, notifications)
    write_outputs(ctx, synthesis_result, ...)
```

**Key design decisions for decomposition:**

1. **PipelineContext dataclass** holds shared state (config, date, claude_client, creds). Passed to every stage.
2. **Each ingest function** takes `PipelineContext`, returns `IngestResult` or empty result on failure. Handles its own try/except.
3. **Adding a new source** means: (a) write `ingest_foo(ctx)` function, (b) call it from `run_pipeline()`. Two locations, not four.
4. **main.py stays thin**: just CLI parsing + `PipelineContext` construction + `run_pipeline()` call.

### Import Strategy

Move ALL conditional imports to module level:
```python
# src/pipeline.py -- TOP OF FILE
from src.ingest.slack import fetch_slack_items
from src.ingest.hubspot import fetch_hubspot_items
from src.ingest.google_docs import fetch_google_docs_items
from src.ingest.calendar import fetch_events_for_date
from src.synthesis.extractor import extract_all_meetings
from src.synthesis.synthesizer import synthesize_daily
from src.synthesis.commitments import extract_commitments
```

If a dependency is missing (e.g., `slack_sdk` not installed), the import fails at startup with a clear traceback, not silently at runtime.

### Anti-Patterns to Avoid
- **God function:** `run_daily()` doing ingest + synthesis + output + quality tracking + notifications in one function. Split into discrete stages.
- **Conditional imports inside loops:** Current pattern hides broken dependencies until runtime hits that branch.
- **Implicit variable scoping:** `creds` and `synthesis_result` assigned inside try blocks but referenced outside. Use explicit `None` initialization before the try.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dependency pinning | Manual version tracking | `uv lock` + upper-bound pins in pyproject.toml | uv resolves the full dependency graph |
| Client pooling | Custom connection pool | Single `anthropic.Anthropic()` passed via context | SDK handles connection pooling internally |
| Pipeline orchestration | Custom plugin system | Simple function calls in sequence | Only 4 sources; a registry pattern is overkill |

## Common Pitfalls

### Pitfall 1: NameError in no-credentials branch (COMMITMENT-NOCREDS)
**What goes wrong:** When Google creds are unavailable, `main.py` takes the `else` branch (line 350-362) which creates a minimal `DailySynthesis` but never assigns `synthesis_result`. The commitment extraction block (line 364+) references `synthesis_result` and hits `NameError`, caught by broad `except Exception`.
**Why it happens:** `synthesis_result` is only assigned inside the `if calendar_service is not None:` branch.
**How to fix:** Initialize `synthesis_result` before the branch. In the new pipeline runner, the synthesis stage always runs on whatever data was collected (even if only Slack/HubSpot).
**Warning signs:** Zero commitments extracted when running without Google creds but with Slack/HubSpot enabled.

### Pitfall 2: Slack backfill uses wrong time window
**What goes wrong:** `fetch_slack_items(config)` uses `datetime.now(timezone.utc)` as the `latest` timestamp and cursor-based `oldest` from state. When backfilling past dates (e.g., `--from 2026-03-28`), it fetches current messages, not messages from March 28.
**Why it happens:** `fetch_slack_items` was designed for "run daily" not "backfill past dates". It has no `target_date` parameter.
**How to fix:** Add `target_date: date` parameter to `fetch_slack_items`. Compute `oldest`/`latest` from target_date boundaries instead of using cursors when backfilling. Keep cursor-based behavior for same-day runs.
**Warning signs:** Backfill daily summaries have no Slack content or have today's Slack content.

### Pitfall 3: HubSpot owner resolution assumes first result
**What goes wrong:** `_resolve_owner_id()` with `scope="mine"` calls `owners_api.get_page()` and returns `results[0].id` -- the first owner in the list, which may not be the authenticated user.
**Why it happens:** Private app tokens don't have a "current user" concept. The code comments acknowledge this.
**How to fix:** Require explicit `owner_id` in config when `scope="mine"`. The config should have `hubspot.owner_id: "12345"`. Fall back to the current behavior only if not set, with a warning.
**Warning signs:** Seeing other people's HubSpot activity in your daily summary.

### Pitfall 4: Multiple Anthropic client instantiations
**What goes wrong:** Five separate `anthropic.Anthropic()` calls across `extractor.py`, `synthesizer.py`, `commitments.py`, `weekly.py`, `monthly.py`. Each creates its own HTTP session.
**Why it happens:** Each module was built independently.
**How to fix:** Create one client in `PipelineContext` and pass it through. Each function gains a `client: anthropic.Anthropic` parameter. The module-level `anthropic.Anthropic()` becomes the fallback default for backward compatibility.

### Pitfall 5: Dead Commitment model confusion
**What goes wrong:** `src/models/commitments.py` defines `Commitment` (Phase 6), while `src/synthesis/commitments.py` defines `ExtractedCommitment` (Phase 10) and `src/sidecar.py` defines `SidecarCommitment`. Three separate commitment representations.
**Why it happens:** Phase 10 built new models without consolidating with Phase 6.
**How to fix:** Delete `src/models/commitments.py` entirely. The Phase 10 models (`ExtractedCommitment` for extraction, `SidecarCommitment` for output) are the canonical ones. Verify no imports reference the dead model.

## Code Examples

### Fix 1: synthesis_result initialization
```python
# BEFORE (broken): synthesis_result only assigned in calendar branch
if calendar_service is not None:
    # ... 100 lines ...
    synthesis_result = synthesize_daily(...)
else:
    # synthesis_result never assigned!
    synthesis = DailySynthesis(...)

# AFTER: initialize before branch
synthesis_result: dict = {
    "substance": [], "decisions": [], "commitments": [],
    "executive_summary": None,
}
# ... then assign in both branches
```

### Fix 2: Shared Anthropic client
```python
# In pipeline.py or wherever the client is created:
client = anthropic.Anthropic()

# Pass to extraction:
extractions = extract_all_meetings(events, config, client=client)

# Pass to synthesis:
synthesis_result = synthesize_daily(extractions, date, config, client=client,
                                    slack_items=slack_items, ...)

# Pass to commitment extraction:
extracted = extract_commitments(text, date, config, client=client)
```

Each function signature gains `client: anthropic.Anthropic | None = None` with fallback:
```python
def extract_commitments(synthesis_text, target_date, config, client=None):
    client = client or anthropic.Anthropic()
    ...
```

### Fix 3: Slack date-aware backfill
```python
def fetch_slack_items(config: dict, target_date: date | None = None) -> list[SourceItem]:
    """Fetch Slack items. If target_date provided, fetch that day's messages."""
    if target_date is None:
        target_date = date.today()

    tz = ZoneInfo(config.get("pipeline", {}).get("timezone", "America/New_York"))
    day_start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=tz)
    day_end = day_start + timedelta(days=1)

    oldest_ts = str(day_start.timestamp())
    latest_ts = str(day_end.timestamp())
    # Use these instead of cursor-based window
```

### Fix 4: uv.lock and dependency pins
```toml
# pyproject.toml -- add upper-bound pins for critical deps
dependencies = [
    "anthropic>=0.45.0,<1.0",
    "pydantic>=2.12.5,<3.0",
    "slack-sdk>=3.33.0,<4.0",
    "hubspot-api-client>=12.0.0,<13.0",
    "google-api-python-client>=2.193.0,<3.0",
    "jinja2>=3.1.6,<4.0",
]
```

Then remove `uv.lock` from `.gitignore` and commit it.

### Fix 5: HubSpot owner_id from config
```python
def _resolve_owner_id(client, config, owner_map):
    hubspot_config = config.get("hubspot", {})
    scope = hubspot_config.get("ownership_scope", "mine")

    # NEW: explicit owner_id takes precedence
    explicit_id = hubspot_config.get("owner_id")
    if explicit_id:
        return str(explicit_id)

    if scope == "all":
        return None

    if scope == "mine":
        logger.warning(
            "hubspot.owner_id not set — falling back to first owner in list. "
            "Set hubspot.owner_id in config.yaml for reliable filtering."
        )
        # ... existing fallback logic ...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `uv.lock` in `.gitignore` | Commit `uv.lock` for reproducible builds | Industry standard | Ensures exact same deps on every machine |
| Lower-bound-only pins (`>=X`) | Upper-bound pins (`>=X,<Y`) | Best practice for apps | Prevents surprise major version breakage |
| Per-call `anthropic.Anthropic()` | Shared client per pipeline run | Performance best practice | Reuses HTTP connections, reduces overhead |
| Conditional runtime imports | Module-level imports | Python best practice | Fail fast on missing deps |

## Specific Changes by Success Criterion

| # | Criterion | Files Affected | Change Type |
|---|-----------|---------------|-------------|
| 1 | No-creds commitment fix | `src/main.py` (or new `pipeline.py`) | Bug fix: initialize synthesis_result before branch |
| 2 | Decompose run_daily() | `src/main.py`, new `src/pipeline.py` | Refactor: extract pipeline runner |
| 3 | Module-level imports | `src/main.py` (or `pipeline.py`) | Refactor: move imports to top |
| 4 | Shared Anthropic client | `src/synthesis/extractor.py`, `synthesizer.py`, `commitments.py`, `weekly.py`, `monthly.py` | Refactor: add client param |
| 5 | Remove dead Commitment model | `src/models/commitments.py` (delete), verify no imports | Dead code removal |
| 6 | uv.lock + dep pins | `pyproject.toml`, `.gitignore`, `uv.lock` | Config: pins + unignore lockfile |
| 7 | Slack backfill date | `src/ingest/slack.py`, `src/main.py` | Bug fix: add target_date param |
| 8 | HubSpot owner_id config | `src/ingest/hubspot.py` | Bug fix: use config owner_id |
| 9 | REQUIREMENTS.md + SUMMARY frontmatter | `.planning/REQUIREMENTS.md`, phase SUMMARY files | Bookkeeping: update statuses |

## Open Questions

1. **Pipeline runner: dataclass vs function args?**
   - What we know: PipelineContext dataclass is cleaner for 5+ shared params
   - What's unclear: Whether weekly/monthly pipelines should share the same context
   - Recommendation: Use PipelineContext for daily; weekly/monthly already work fine as-is

2. **SynthesisSource Protocol: keep or remove?**
   - What we know: Defined in `src/models/sources.py`, never used as type constraint
   - What's unclear: Whether future phases will use it
   - Recommendation: Keep it -- it documents the interface contract. It's not dead code, it's a specification. But flag as unused in a comment.

3. **Pre-existing test failures: fix in Phase 11 or Phase 12?**
   - What we know: `test_notifications.py`, `test_extractor.py`, `test_writer.py` fail
   - The ROADMAP assigns test fixes to Phase 12
   - Recommendation: Leave for Phase 12 per ROADMAP. Phase 11 focuses on pipeline code, not test infrastructure.

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection of `src/main.py`, `src/synthesis/*.py`, `src/ingest/*.py`, `src/models/*.py`
- `.planning/v1.5-MILESTONE-AUDIT.md` -- gap analysis identifying MODEL-02-DEAD-CODE and COMMITMENT-NOCREDS
- `.planning/ROADMAP.md` -- Phase 11 success criteria

### Secondary (MEDIUM confidence)
- `pyproject.toml` and `.gitignore` -- current dependency state

## Metadata

**Confidence breakdown:**
- Bug fixes (criteria 1, 7, 8): HIGH -- bugs verified by direct code inspection
- Architecture (criterion 2): HIGH -- straightforward decomposition of known code
- Imports (criterion 3): HIGH -- mechanical refactoring
- Shared client (criterion 4): HIGH -- 5 instantiation sites identified
- Dead code (criterion 5): HIGH -- audit confirmed, no imports found
- Dependency pinning (criterion 6): HIGH -- standard uv workflow
- Bookkeeping (criterion 9): HIGH -- gaps enumerated in audit

**Research date:** 2026-04-04
**Valid until:** 2026-05-04 (stable -- no external API changes expected)
