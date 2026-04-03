# Phase 1: Foundation and Calendar Ingestion - Research

**Researched:** 2026-04-03
**Domain:** Pydantic data modeling, Jinja2 markdown templating, Google Calendar API ingestion, Python CLI, YAML config
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Output Structure:**
- Full detail per event: title, time, duration, all attendees, meeting link, description snippet
- Narrative block format — short prose paragraph per event (not bullets or tables)
- Neutral log tone — third-person factual ("Meeting with Sarah Chen, 2:00-2:30pm. Discussed Q3 planning.")
- Summary header at top of daily file: meeting count, total meeting hours, transcript count (0 in Phase 1)
- Include calendar event description/agenda body when present — richer context per event
- Full skeleton with stub sections for future phases (Decisions, Commitments, Substance) — consistent structure from day one
- Raw API response cached to `output/raw/` alongside the daily markdown

**Calendar Filtering:**
- Include declined meetings in a separate section — useful to see what was skipped
- Include cancelled events in a separate section — useful to see what dropped off
- Include all-day events in their own section at the top — they set day context
- Include all events regardless of attendee role (organizer, required, optional, FYI)
- Tag recurring events — annotate to distinguish routine from one-off meetings
- Include Focus Time and OOO blocks — they're part of the day's structure
- Configurable calendar ID list in config file — not just primary calendar
- Configurable title-pattern exclusion list (default: empty, include everything)

**Pipeline Invocation:**
- Date range support built in: `--from` and `--to` flags for backfill
- Overwrite existing output on re-run — latest run wins, no force flag needed
- Configuration via YAML config file with environment variable overrides
- CLI design (defaults, flag names, module entrypoint): Claude's discretion

**Data Model:**
- Full attendee detail: name, email, response status (accepted/declined/tentative)
- Transcript fields (transcript_text, transcript_source) included now as Optional/None — populated in Phase 2
- Hierarchical DailySynthesis model: nested Section objects (calendar_events, substance, decisions, commitments)
- JSON-serializable from day one via Pydantic `.model_dump_json()` — Phase 5 sidecar is trivial later

### Claude's Discretion
- Organization of events within the daily markdown (chronological vs grouped — Claude picks)
- CLI design: module entrypoint, flag names, defaults-to-today behavior
- Exact section ordering within the daily markdown template
- Error handling and logging approach
- Naming conventions for raw cache files

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INGEST-02 | Ingest Google Calendar events (Bounce workspace) for meeting skeleton | Google Calendar API v3 events.list with singleEvents=True, multi-calendar support via calendarList API, eventType filtering for focusTime/OOO, Pydantic models for normalization |
| OUT-01 | Structured output file per day (markdown) with source attribution | Jinja2 templating with `.md.j2` template files, date-based directory hierarchy `output/daily/YYYY/MM/YYYY-MM-DD.md`, DailySynthesis Pydantic model with nested sections |
</phase_requirements>

## Summary

Phase 1 builds three foundational pieces: Pydantic data models (NormalizedEvent, DailySynthesis with nested Section hierarchy), a Jinja2-based markdown output writer, and a Google Calendar ingestion module. The existing codebase from Phase 0 already has OAuth working (`src/auth/google_oauth.py`) with calendar.readonly scope, a working `googleapiclient.discovery.build("calendar", "v3")` call in `src/validation/daily_check.py`, and a venv managed by uv. Phase 1 adds pydantic, jinja2, and pyyaml as new dependencies.

The Google Calendar API is well-understood and the existing validation script proves the auth flow works. The main complexity lies in: (1) handling multiple calendar IDs and event types (focusTime, outOfOffice, cancelled, all-day), (2) building a hierarchical Pydantic model that is both useful now and extensible for Phases 2-5, and (3) producing a Jinja2 markdown template that renders narrative prose blocks rather than structured tables or lists.

**Primary recommendation:** Build models first (they are the contract everything depends on), then the output writer (testable with mock data immediately), then the calendar ingestion module. Use `argparse` for CLI (stdlib, no extra dependency for this simple use case). Use PyYAML for config (user decision). Do NOT pass `eventTypes` to the API — omitting it returns all event types, avoiding a known repeated-parameter bug in google-api-python-client.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | >=2.12.0 | Data models (NormalizedEvent, DailySynthesis, Attendee, Section) | v2 is the standard Python data modeling library. `.model_dump_json()` gives free JSON serialization. Validates at API boundaries. |
| jinja2 | >=3.1.4 | Markdown template rendering for daily output files | Industry-standard Python templating. Conditional sections, loops, template inheritance for daily/weekly variants. |
| pyyaml | >=6.0.2 | Configuration file parsing (YAML config with env var overrides) | User decision. PyYAML 6.x is stable. Always use `yaml.safe_load()`. |
| google-api-python-client | >=2.193.0 | Google Calendar API v3 access | Already installed and proven in Phase 0 validation script. |
| google-auth | >=2.49.1 | OAuth2 token management | Already installed and proven in Phase 0. |
| python-dateutil | >=2.9.0 | Robust datetime parsing from API responses | Already installed. `dateutil.parser.isoparse()` handles RFC3339 timestamps from Google API. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| argparse | stdlib | CLI argument parsing (--from, --to, --config) | Entry point for pipeline invocation. Stdlib avoids new dependency for simple flags. |
| zoneinfo | stdlib | Timezone handling (America/New_York) | Already used in Phase 0 validation. Python 3.12 stdlib. |
| pathlib | stdlib | File path construction for output directory hierarchy | Create `output/daily/YYYY/MM/` paths. |
| logging | stdlib | Structured logging for pipeline runs | Claude's discretion area. Standard library logging with reasonable defaults. |
| tomllib | stdlib | Read pyproject.toml if needed | Already available in Python 3.12. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| argparse | click or typer | Click/Typer have nicer APIs but add dependencies for 3 flags. argparse is sufficient. |
| pyyaml | tomllib (TOML) | TOML is in stdlib and safer, but user decided YAML. YAML with `safe_load()` is fine. |
| jinja2 | f-strings | f-strings break down for conditional sections and loops over variable-length event lists. Jinja2 is correct for multi-section documents. |

**Installation:**
```bash
uv add pydantic jinja2 pyyaml
```

## Architecture Patterns

### Recommended Project Structure
```
src/
├── __init__.py
├── main.py              # CLI entry point with argparse
├── config.py            # YAML config loading + env var overrides
├── auth/                # [EXISTS] OAuth module from Phase 0
│   ├── __init__.py
│   └── google_oauth.py
├── models/
│   ├── __init__.py
│   └── events.py        # NormalizedEvent, Attendee, Section, DailySynthesis
├── ingest/
│   ├── __init__.py
│   └── calendar.py      # Google Calendar API ingestion
├── output/
│   ├── __init__.py
│   └── writer.py        # Jinja2 template rendering + file writing
├── notifications/       # [EXISTS] Slack notifications from Phase 0
│   ├── __init__.py
│   └── slack.py
└── validation/          # [EXISTS] Phase 0 validation (can be preserved or deprecated)
    ├── __init__.py
    ├── daily_check.py
    └── run_log.py
templates/
└── daily.md.j2          # Jinja2 template for daily markdown output
config/
└── config.yaml          # Default configuration file
output/
├── daily/
│   └── YYYY/MM/YYYY-MM-DD.md
└── raw/
    └── YYYY/MM/DD/calendar.json
```

### Pattern 1: Pydantic Models as the System Contract
**What:** Define all data structures as Pydantic BaseModel classes. Every component communicates through these typed models — ingestion produces them, output consumes them.
**When to use:** Always. Models are the first thing built and the last thing changed.
**Example:**
```python
# Source: https://docs.pydantic.dev/latest/concepts/models/
from pydantic import BaseModel, Field
from datetime import datetime
from enum import StrEnum

class ResponseStatus(StrEnum):
    ACCEPTED = "accepted"
    DECLINED = "declined"
    TENTATIVE = "tentative"
    NEEDS_ACTION = "needsAction"

class Attendee(BaseModel):
    name: str | None = None
    email: str
    response_status: ResponseStatus = ResponseStatus.NEEDS_ACTION
    is_self: bool = False
    is_organizer: bool = False

class NormalizedEvent(BaseModel):
    id: str
    source: str  # "google_calendar"
    title: str
    start_time: datetime | None = None  # None for all-day
    end_time: datetime | None = None
    all_day: bool = False
    date: str | None = None  # YYYY-MM-DD for all-day events
    duration_minutes: int | None = None
    attendees: list[Attendee] = Field(default_factory=list)
    description: str | None = None
    location: str | None = None
    meeting_link: str | None = None
    is_recurring: bool = False
    event_type: str = "default"  # default, focusTime, outOfOffice, birthday
    status: str = "confirmed"  # confirmed, tentative, cancelled
    calendar_id: str = "primary"
    # Phase 2 fields — present but unpopulated
    transcript_text: str | None = None
    transcript_source: str | None = None
    raw_data: dict | None = None  # Original API response
```

### Pattern 2: Jinja2 Template for Narrative Markdown
**What:** Keep the markdown structure in a `.md.j2` template file, separate from Python code. The template uses Jinja2 control flow to conditionally render sections and loop over events.
**When to use:** For all markdown output generation. Templates are iterable without code changes.
**Example:**
```jinja2
{# templates/daily.md.j2 #}
# Daily Summary: {{ date }}

## Overview
- **Meetings:** {{ meeting_count }}
- **Total meeting hours:** {{ total_hours | round(1) }}
- **Transcripts:** {{ transcript_count }}

{% if all_day_events %}
## All-Day Events
{% for event in all_day_events %}
{{ event.title }}{% if event.event_type != "default" %} ({{ event.event_type }}){% endif %}.
{% endfor %}
{% endif %}

## Calendar
{% for event in timed_events %}
{{ event.title }}, {{ event.start_time | format_time }}-{{ event.end_time | format_time }}
{%- if event.duration_minutes %} ({{ event.duration_minutes }} min){% endif %}.
{%- if event.attendees %} With {{ event.attendees | format_attendees }}.{% endif %}
{%- if event.is_recurring %} [Recurring]{% endif %}
{%- if event.description %} {{ event.description | truncate(200) }}{% endif %}

{% endfor %}
```

### Pattern 3: YAML Config with Environment Variable Overrides
**What:** Load config from YAML file, then overlay environment variables for secrets or deployment-specific values.
**When to use:** Pipeline configuration — calendar IDs, exclusion patterns, output paths, timezone.
**Example:**
```python
import os
import yaml
from pathlib import Path

def load_config(config_path: Path | None = None) -> dict:
    default_path = Path("config/config.yaml")
    path = config_path or default_path

    if path.exists():
        with open(path) as f:
            config = yaml.safe_load(f) or {}
    else:
        config = {}

    # Environment variable overrides
    if tz := os.environ.get("SUMMARIZER_TIMEZONE"):
        config.setdefault("pipeline", {})["timezone"] = tz
    if cal_ids := os.environ.get("SUMMARIZER_CALENDAR_IDS"):
        config.setdefault("calendars", {})["ids"] = cal_ids.split(",")

    return config
```

### Pattern 4: Multi-Calendar Ingestion with Event Type Coverage
**What:** Loop over configured calendar IDs, query each with the events.list API, collect and merge results. Do NOT pass `eventTypes` parameter — omitting it returns all event types including focusTime and outOfOffice.
**When to use:** Calendar ingestion module.
**Example:**
```python
from googleapiclient.discovery import build
from datetime import datetime
import zoneinfo

def fetch_events_for_date(
    service,
    target_date: datetime,
    calendar_ids: list[str],
    timezone: str = "America/New_York",
) -> list[dict]:
    tz = zoneinfo.ZoneInfo(timezone)
    start_of_day = target_date.replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=tz
    )
    end_of_day = start_of_day + timedelta(days=1)

    all_events = []
    for cal_id in calendar_ids:
        events_result = service.events().list(
            calendarId=cal_id,
            timeMin=start_of_day.isoformat(),
            timeMax=end_of_day.isoformat(),
            singleEvents=True,       # Expand recurring events into instances
            orderBy="startTime",
            showDeleted=True,         # Include cancelled events
            # Do NOT pass eventTypes — omitting returns ALL types
        ).execute()

        for event in events_result.get("items", []):
            event["_calendar_id"] = cal_id  # Tag source calendar
            all_events.append(event)

    return all_events
```

### Anti-Patterns to Avoid
- **Hardcoding calendar ID as "primary":** User decided configurable calendar ID list. Always read from config.
- **Filtering events in the API call:** User wants ALL events including declined, cancelled, focusTime, OOO. Filter/group in Python after fetching, not in the API query.
- **Building markdown with f-strings:** Template will have conditional sections (declined events, all-day events, stub sections). Jinja2 handles this; f-strings create unmaintainable code.
- **Mixing model definition with business logic:** Models go in `src/models/events.py`. Ingestion logic goes in `src/ingest/calendar.py`. Output logic goes in `src/output/writer.py`. Keep them separate.
- **Using dataclasses instead of Pydantic:** User decided Pydantic with `.model_dump_json()`. Dataclasses lack validation and serialization.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| RFC3339 datetime parsing | Custom regex for Google API timestamps | `dateutil.parser.isoparse()` | Handles timezone offsets, fractional seconds, Z suffix. Edge cases abound. |
| Markdown template rendering | String concatenation with conditional blocks | Jinja2 `.md.j2` templates | Conditional sections, loops, filters. Separates content from presentation. |
| Data validation at API boundary | Manual dict-key checking | Pydantic `model_validate(data)` | Catches missing fields, wrong types, invalid enums immediately. |
| YAML config parsing | Custom config parser | `yaml.safe_load()` + dict overlay | PyYAML is battle-tested. `safe_load` prevents code execution. |
| All-day event detection | Check if "date" vs "dateTime" key exists | Check `event.get("start", {}).get("date")` is not None | Google API uses `date` field for all-day events, `dateTime` for timed events. This is the canonical check. |
| Duration calculation | Manual arithmetic on time strings | `(end_dt - start_dt).total_seconds() / 60` | Parse once with dateutil, subtract datetime objects. |

**Key insight:** Google Calendar API responses are well-structured JSON, but they have multiple representation modes (all-day vs timed events, single vs recurring, different event types). Pydantic validation at the ingestion boundary catches these variations immediately rather than failing downstream.

## Common Pitfalls

### Pitfall 1: All-Day Events Have Different Time Fields
**What goes wrong:** Code assumes `event["start"]["dateTime"]` exists and crashes on all-day events.
**Why it happens:** All-day events use `start.date` (string "2026-04-03") instead of `start.dateTime` (RFC3339 timestamp). The two are mutually exclusive in the API response.
**How to avoid:** Always check for `date` first, then `dateTime`. Set `all_day=True` on the NormalizedEvent when `date` is present.
**Warning signs:** KeyError or None when accessing start/end times on OOO or vacation events.

### Pitfall 2: eventTypes Repeated Parameter Bug
**What goes wrong:** Passing `eventTypes=["default", "focusTime", "outOfOffice"]` to `service.events().list()` may raise a ValueError about repeated URL parameters.
**Why it happens:** google-api-python-client has a known issue (GitHub #667) where repeated query parameters are rejected by URL validation logic.
**How to avoid:** Do NOT pass `eventTypes` at all. When omitted, the API returns all event types. Filter in Python if needed.
**Warning signs:** ValueError containing "URL-encoded content contains a repeated value".

### Pitfall 3: Cancelled Events Require showDeleted=True
**What goes wrong:** Cancelled events don't appear in results even though user wants them in a separate section.
**Why it happens:** The `events.list` API defaults to hiding cancelled events. You must pass `showDeleted=True` to include them.
**How to avoid:** Always pass `showDeleted=True`. Cancelled events have `status: "cancelled"`. Group them separately in the output template.
**Warning signs:** User reports missing cancelled meetings.

### Pitfall 4: Recurring Event Detection
**What goes wrong:** Code doesn't know which events are recurring vs one-off.
**Why it happens:** When `singleEvents=True`, recurring events are expanded into individual instances. The parent recurring event is not returned. However, each instance has a `recurringEventId` field pointing to the parent.
**How to avoid:** Check for `recurringEventId` on each event. If present, the event is an instance of a recurring series. Set `is_recurring=True` on the NormalizedEvent.
**Warning signs:** No events tagged as recurring even though the calendar has weekly standups.

### Pitfall 5: Pagination on Busy Calendars
**What goes wrong:** Only first page of events returned (max 250 per page by default, 2500 max).
**Why it happens:** `events.list` paginates results. If there are more events than `maxResults`, a `nextPageToken` is returned.
**How to avoid:** Always check for `nextPageToken` and loop until exhausted. For single-day queries this is unlikely to matter (few people have 250+ events in a day), but build the pagination loop defensively.
**Warning signs:** Truncated event lists on days with many calendar entries.

### Pitfall 6: YAML Boolean Gotcha
**What goes wrong:** YAML values like `yes`, `no`, `on`, `off`, `true`, `false` are silently coerced to Python booleans.
**Why it happens:** YAML 1.1 spec treats these strings as boolean literals.
**How to avoid:** Always quote string values that could be misinterpreted. Use `yaml.safe_load()` (not `yaml.load()`). Validate config values with Pydantic after loading.
**Warning signs:** Config value that should be string "yes" becomes Python `True`.

### Pitfall 7: Jinja2 Whitespace in Markdown
**What goes wrong:** Generated markdown has extra blank lines or missing newlines, breaking formatting.
**Why it happens:** Jinja2 control blocks (`{% if %}`, `{% for %}`) produce newlines by default.
**How to avoid:** Use `{%- ... -%}` (dash trim) on control blocks to strip surrounding whitespace. Or set `trim_blocks=True, lstrip_blocks=True` on the Jinja2 Environment.
**Warning signs:** Double blank lines between events, or events running together without spacing.

## Code Examples

### Google Calendar API: Detect All-Day vs Timed Events
```python
# Source: https://developers.google.com/workspace/calendar/api/v3/reference/events
def is_all_day(event: dict) -> bool:
    """All-day events use 'date' field, timed events use 'dateTime'."""
    return "date" in event.get("start", {})

def get_event_times(event: dict) -> tuple[datetime | None, datetime | None, str | None]:
    """Extract start/end times, handling both all-day and timed events."""
    from dateutil.parser import isoparse

    start = event.get("start", {})
    end = event.get("end", {})

    if "date" in start:
        # All-day event: return dates as strings, no datetime
        return None, None, start["date"]

    start_dt = isoparse(start["dateTime"]) if "dateTime" in start else None
    end_dt = isoparse(end["dateTime"]) if "dateTime" in end else None
    return start_dt, end_dt, None
```

### Pydantic Model with Nested Sections
```python
# Source: https://docs.pydantic.dev/latest/concepts/models/
from pydantic import BaseModel, Field
from datetime import datetime, date

class Section(BaseModel):
    """A section of the daily synthesis. Stub sections have empty items."""
    title: str
    items: list[str] = Field(default_factory=list)

class DailySynthesis(BaseModel):
    """Top-level model for a daily summary file."""
    date: date
    generated_at: datetime
    meeting_count: int = 0
    total_meeting_hours: float = 0.0
    transcript_count: int = 0  # Always 0 in Phase 1

    all_day_events: list[NormalizedEvent] = Field(default_factory=list)
    timed_events: list[NormalizedEvent] = Field(default_factory=list)
    declined_events: list[NormalizedEvent] = Field(default_factory=list)
    cancelled_events: list[NormalizedEvent] = Field(default_factory=list)

    # Stub sections for future phases
    substance: Section = Field(default_factory=lambda: Section(title="Substance"))
    decisions: Section = Field(default_factory=lambda: Section(title="Decisions"))
    commitments: Section = Field(default_factory=lambda: Section(title="Commitments"))

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
```

### Jinja2 Environment Setup for Markdown
```python
# Source: https://jinja.palletsprojects.com/en/stable/api/
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

def create_jinja_env(template_dir: Path = Path("templates")) -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        trim_blocks=True,       # Remove newline after block tag
        lstrip_blocks=True,     # Strip leading whitespace before block tag
        keep_trailing_newline=True,  # Keep final newline in file
    )
    # Custom filters for markdown rendering
    env.filters["format_time"] = lambda dt: dt.strftime("%-I:%M%p").lower() if dt else ""
    env.filters["format_attendees"] = lambda attendees: ", ".join(
        a.name or a.email for a in attendees if not a.is_self
    )
    return env
```

### YAML Config File Structure
```yaml
# config/config.yaml
pipeline:
  timezone: "America/New_York"
  output_dir: "output"

calendars:
  ids:
    - "primary"
    # Add additional calendar IDs here
  exclude_patterns: []
  # Example: ["Focus Time", "Lunch"]
```

### CLI Entry Point with argparse
```python
import argparse
from datetime import date, timedelta

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Daily work intelligence summarizer")
    parser.add_argument(
        "--from", dest="from_date", type=date.fromisoformat,
        default=date.today(), help="Start date (YYYY-MM-DD, default: today)"
    )
    parser.add_argument(
        "--to", dest="to_date", type=date.fromisoformat,
        default=None, help="End date (YYYY-MM-DD, default: same as --from)"
    )
    parser.add_argument(
        "--config", type=str, default="config/config.yaml",
        help="Path to config file"
    )
    args = parser.parse_args()
    if args.to_date is None:
        args.to_date = args.from_date
    return args
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Pydantic v1 `.json()` | Pydantic v2 `.model_dump_json()` | Pydantic v2 (2023) | v1 `.json()` is deprecated. Always use v2 API. |
| `pytz` for timezones | `zoneinfo` (stdlib) | Python 3.9+ | No external dependency needed. Already used in Phase 0. |
| `oauth2client` for Google auth | `google-auth` + `google-auth-oauthlib` | 2018+ | oauth2client is abandoned. Already using correct libraries. |
| Manual `requests` + discovery | `google-api-python-client` | N/A (always current) | Discovery-based client handles API versioning automatically. |
| YAML 1.1 (`yaml.load()`) | YAML 1.1 (`yaml.safe_load()`) | Security best practice | `yaml.load()` can execute arbitrary Python code. Never use it. |

**Deprecated/outdated:**
- `pydantic.BaseModel.json()` / `.dict()` — use `.model_dump_json()` / `.model_dump()` instead
- `oauth2client` — replaced by `google-auth`
- `pytz` — replaced by stdlib `zoneinfo`

## Open Questions

1. **eventTypes parameter behavior with google-api-python-client**
   - What we know: Omitting `eventTypes` returns all event types (confirmed by official docs). Passing it as a list may trigger a repeated-parameter bug (GitHub #667).
   - What's unclear: Whether recent versions of google-api-python-client have fixed the repeated parameter issue.
   - Recommendation: Do not pass `eventTypes`. Omitting it returns all types. Filter in Python if needed. This is safer and simpler.

2. **Focus Time and OOO event structure**
   - What we know: These events have `eventType` field set to "focusTime" or "outOfOffice". They appear when `eventTypes` is omitted.
   - What's unclear: Whether these events have all the same fields as regular events (attendees, description, etc.) or are sparse.
   - Recommendation: Handle gracefully — treat missing fields as None/empty. Pydantic optional fields handle this automatically.

3. **Meeting link extraction**
   - What we know: Regular events may have `hangoutLink` for classic Hangouts or `conferenceData.entryPoints[].uri` for Google Meet. External meeting links (Zoom, Teams) appear in the `location` or `description` fields.
   - What's unclear: Exact field paths for all meeting link scenarios.
   - Recommendation: Check `conferenceData.entryPoints` first, then `hangoutLink`, then scan `location` for URL patterns. Extract what's available; don't fail if missing.

## Sources

### Primary (HIGH confidence)
- [Google Calendar API v3 Events resource](https://developers.google.com/workspace/calendar/api/v3/reference/events) - Event field definitions, status values, attendee structure
- [Google Calendar API v3 Events.list](https://developers.google.com/workspace/calendar/api/v3/reference/events/list) - Query parameters including eventTypes, showDeleted, singleEvents
- [Google Calendar API Event Types guide](https://developers.google.com/workspace/calendar/api/guides/event-types) - focusTime, outOfOffice, birthday event type handling
- [Google Calendar API Recurring Events guide](https://developers.google.com/workspace/calendar/api/guides/recurringevents) - singleEvents expansion, recurringEventId field
- [Pydantic v2 Models documentation](https://docs.pydantic.dev/latest/concepts/models/) - BaseModel, Field, model_dump, model_dump_json
- [Pydantic v2 Serialization](https://docs.pydantic.dev/latest/concepts/serialization/) - Serialization modes, exclude_none, by_alias

### Secondary (MEDIUM confidence)
- [google-api-python-client GitHub #667](https://github.com/googleapis/google-api-python-client/issues/667) - Repeated parameter bug affecting eventTypes
- [google-api-python-client events() docs](https://googleapis.github.io/google-api-python-client/docs/dyn/calendar_v3.events.html) - Python method signatures
- [PyYAML documentation](https://pyyaml.org/wiki/PyYAML) - safe_load usage

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries are well-established and either already installed (google-api-python-client, google-auth, python-dateutil) or standard choices (pydantic, jinja2, pyyaml)
- Architecture: HIGH - Pattern follows ARCHITECTURE.md research from project planning, build order validated (models -> output -> ingestion)
- Pitfalls: HIGH - Google Calendar API quirks are well-documented; Pydantic v2 and Jinja2 are mature with known gotchas documented in official docs

**Research date:** 2026-04-03
**Valid until:** 2026-05-03 (30 days — stable libraries, stable API)
