# Phase 23: Scoped Views + Reports - Research

**Researched:** 2026-04-08
**Domain:** SQLite entity queries, CLI output formatting, Jinja2 report generation
**Confidence:** HIGH

## Summary

Phase 23 builds entirely on the existing entity infrastructure (Phases 19-22). No new external libraries are needed -- the codebase already has SQLite for entity storage, Jinja2 for template rendering, and argparse for CLI. The work is pure application logic: SQL queries against the entity_mentions table, terminal formatting for `entity show` and enriched `entity list`, and a Jinja2 template for `entity report`.

The entity_mentions table already stores source_type (substance/decision/commitment), source_date, confidence, and context_snippet. Combined with JOINs against entities and aliases tables, all the data needed for scoped views is queryable. The commitment data lives in daily sidecar JSON files (not in SQLite), so open commitment counts require scanning sidecar files or extending the SQL schema.

**Primary recommendation:** Add query methods to EntityRepository, a new `views.py` module for view/report logic, a Jinja2 template for entity reports, and extend the existing CLI with `show` (scoped view), `report` (markdown file), and enriched `list` subcommands.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- entity show: Items grouped by date with date headers, showing date + section type + text + source attribution
- entity show: Open commitments in a separate highlighted section at top, before chronological activity
- entity show: Default time range last 30 days, override with --from/--to or --all
- entity report: Three sections -- 1) Entity summary, 2) Open commitments, 3) Activity by date
- entity report: Generated using Jinja2 templates in templates/ dir
- entity report: Default 30-day range, --from/--to override, single entity per invocation
- entity report: Output to output/entities/ as markdown file
- entity list: Enhanced columns -- mention frequency (all-time), open commitments count, last-active date
- entity list: Default sort by last-active date descending, --sort supports active/mentions/name
- entity list: --json flag supported (consistent with Phase 19)
- entity list: --type filter still works
- Temporal summary: Decisions + Commitments rank higher than Substance items
- Temporal summary: Rule-based extraction (no Claude API call) -- deterministic, fast, no cost
- Temporal summary: Top 5 most significant items as highlights section
- Temporal summary: Highlights in BOTH entity show (terminal) and entity report (markdown)
- Full chronological activity follows below highlights

### Claude's Discretion
- Exact significance scoring algorithm (how to weight decisions vs commitments vs recency)
- Terminal formatting (colors, spacing, table widths)
- Jinja2 template design for the markdown report
- How to handle entities with zero mentions in the time range
- Edge case handling (deleted entities, merged entities in views)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| VIEW-01 | User can query entity activity via CLI command with scoped report output | SQL query layer on entity_mentions + CLI entity show with terminal formatting |
| VIEW-02 | System generates per-entity markdown report files covering configurable time range | Jinja2 entity report template + entity report CLI command + output/entities/ directory |
| VIEW-03 | Temporal entity summaries show mention frequency, open commitments, and last-active date | Enriched entity list with aggregated mention data + significance scoring for highlights |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sqlite3 | stdlib | Entity data queries | Already used by entity subsystem (WAL mode, foreign keys) |
| Jinja2 | 3.x (installed) | Markdown report templates | Already used for daily/weekly/monthly templates |
| argparse | stdlib | CLI command wiring | Already used for all entity subcommands |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pathlib | stdlib | File path construction for output/entities/ | Report file writing |
| datetime | stdlib | Date parsing for --from/--to flags | Time range filtering |

### Alternatives Considered
None -- all tools already in the project. No new dependencies needed.

## Architecture Patterns

### Recommended Project Structure
```
src/entity/
├── views.py          # NEW: Query layer + significance scoring + view rendering
├── cli.py            # MODIFY: Add show/report/list enrichment handlers
├── repository.py     # MODIFY: Add aggregate query methods
├── ...existing...
templates/
├── entity_report.md.j2  # NEW: Per-entity report template
output/
└── entities/         # NEW: Generated entity reports
```

### Pattern 1: Repository Query Methods
**What:** Add aggregate SQL queries to EntityRepository for mention stats
**When to use:** Any time we need entity-scoped data from SQLite
**Example:**
```python
def get_entity_mentions_in_range(
    self, entity_id: str, from_date: str | None, to_date: str | None
) -> list[dict]:
    """Fetch mentions for an entity within a date range."""
    query = """
        SELECT em.source_type, em.source_date, em.confidence,
               em.context_snippet, em.source_id
        FROM entity_mentions em
        WHERE em.entity_id = ?
    """
    params = [entity_id]
    if from_date:
        query += " AND em.source_date >= ?"
        params.append(from_date)
    if to_date:
        query += " AND em.source_date <= ?"
        params.append(to_date)
    query += " ORDER BY em.source_date DESC, em.source_type"
    return [dict(row) for row in self._conn.execute(query, params).fetchall()]
```

### Pattern 2: Significance Scoring (Rule-Based)
**What:** Deterministic scoring for highlighting the most important items
**When to use:** Highlights section in both show and report
**Algorithm recommendation:**
- Decision items: base score 3.0
- Commitment items: base score 2.5
- Substance items: base score 1.0
- Recency bonus: +1.0 for items within last 7 days, +0.5 for 7-14 days
- Confidence bonus: multiply by mention confidence (0.2-1.0)
- Sort by score descending, take top 5

### Pattern 3: Views Module as Mediator
**What:** `views.py` sits between repository (data) and CLI/template (presentation)
**When to use:** Keeps CLI handlers thin and logic testable
```python
# views.py provides:
def get_entity_scoped_view(repo, entity_name, from_date, to_date) -> EntityScopedView
def get_entity_report_data(repo, entity_name, from_date, to_date) -> EntityReportData
def get_enriched_entity_list(repo, entity_type, sort_by) -> list[EnrichedEntity]
```

### Anti-Patterns to Avoid
- **SQL in CLI handlers:** Keep all queries in repository.py, business logic in views.py
- **Loading full sidecar JSONs for commitment status:** Use entity_mentions table instead -- commitments are already persisted as source_type='commitment' mentions
- **Hitting Claude API for temporal summaries:** User explicitly locked this as rule-based, no LLM calls

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Date range parsing | Custom date parser | datetime.date.fromisoformat | Already used by backfill CLI |
| Markdown rendering | Manual string concat | Jinja2 template | Already used for daily/weekly/monthly |
| Terminal tables | Custom column alignment | %-formatting pattern | Already used in _cmd_list (cli.py L163) |

## Common Pitfalls

### Pitfall 1: Merged Entity Resolution in Views
**What goes wrong:** Querying mentions for an entity misses mentions stored under pre-merge IDs
**Why it happens:** Merged entities have mentions under both the source and target entity IDs
**How to avoid:** When looking up mentions, also include mentions from entities whose merge_target_id points to the queried entity
**Warning signs:** Entity shows fewer mentions than expected after a merge

### Pitfall 2: Open Commitments Detection
**What goes wrong:** No way to distinguish open vs closed commitments in entity_mentions
**Why it happens:** entity_mentions stores that a commitment was mentioned, not its completion status
**How to avoid:** Open commitments require reading from daily sidecar JSON files OR checking the context_snippet field. Since context_snippet stores the first 100 chars of commitment content, we can use it. However, a simpler approach: the entity_mentions table records all commitment mentions -- count by entity gives "commitment involvement" not "open commitments."
**Recommendation:** For "open commitments count" in entity list, scan the most recent sidecar JSON files for commitments mentioning this entity. For the show/report views, display all commitment mentions with their context snippets.

### Pitfall 3: Empty Time Range Results
**What goes wrong:** Entity exists but has zero mentions in the selected date range
**Why it happens:** Narrow date windows or recently registered entities
**How to avoid:** Display "No activity found for [entity] in [range]" rather than empty output. Suggest using --all flag.

### Pitfall 4: Large Output for Prolific Entities
**What goes wrong:** Entity show for a frequently-mentioned entity dumps hundreds of items
**Why it happens:** 30 days of mentions for a core partner could be voluminous
**How to avoid:** The highlights section addresses this naturally (top 5 first). Full activity follows but is chronological, so recent items appear first.

## Code Examples

### Entity Name Resolution (existing pattern)
```python
# From cli.py -- resolve by name, handling aliases and merges
entity = repo.resolve_name(args.name)  # Handles canonical + alias + merge_target
if entity is None:
    print("Entity not found: %s" % args.name, file=sys.stderr)
    sys.exit(1)
```

### Jinja2 Template Loading (existing pattern)
```python
# From src/writer.py (daily template)
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader("templates"))
template = env.get_template("daily.md.j2")
output = template.render(**context)
```

### Date Flag Pattern (existing in backfill CLI)
```python
# Already in cli.py backfill subparser
parser.add_argument("--from", dest="from_date", type=date.fromisoformat)
parser.add_argument("--to", dest="to_date", type=date.fromisoformat)
```

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Raw entity list (name/type/created) | Enriched list with mentions/commitments/last-active | VIEW-03 |
| Basic `entity show` (entity details only) | Scoped activity view with time filtering | VIEW-01 |
| No per-entity reports | Jinja2 markdown reports in output/entities/ | VIEW-02 |

## Open Questions

1. **How to count "open commitments" accurately?**
   - What we know: entity_mentions stores all commitment mentions with context_snippets
   - What's unclear: No explicit "completion status" tracked in entity_mentions
   - Recommendation: Count commitment mentions (source_type='commitment') as commitment involvement. The context_snippet includes the commitment text. For a true "open" count, scan recent sidecar JSONs. Start with mention count; can refine later.

2. **Merged entity mention aggregation**
   - What we know: merge_target_id links merged entities
   - What's unclear: Whether to aggregate ALL historical mentions or just post-merge
   - Recommendation: Aggregate all mentions (pre and post merge) since the user expects to see the full picture

## Sources

### Primary (HIGH confidence)
- Existing codebase: src/entity/ (repository.py, attributor.py, cli.py, migrations.py, models.py)
- Existing codebase: src/entity/db.py (connection factory)
- Existing codebase: templates/daily.md.j2 (Jinja2 template pattern)
- SQLite documentation for aggregate queries (GROUP BY, COUNT, MAX)

### Secondary (MEDIUM confidence)
- Jinja2 template inheritance patterns (established in project)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already in use, no new dependencies
- Architecture: HIGH - follows established patterns in entity/ and templates/
- Pitfalls: HIGH - identified from actual codebase schema and data flow analysis

**Research date:** 2026-04-08
**Valid until:** 2026-05-08
