# Architecture Research: Work Intelligence / Daily Synthesis Pipeline

**Research type:** Project Research — Architecture dimension
**Date:** 2026-03-23
**Status:** Complete

---

## 1. How Systems Like This Are Typically Structured

Work intelligence and daily synthesis pipelines follow a four-stage linear architecture. The stages are: **Ingestion**, **Normalization**, **Synthesis**, and **Storage/Output**. Each stage has a clear input contract and output contract, which makes them independently testable and replaceable.

The general pattern across personal analytics tools, automated journaling systems, and LLM-powered summarization pipelines is:

```
[Scheduled Trigger]
    |
    v
[Ingestion Layer] -- pulls raw data from external APIs
    |
    v
[Normalization Layer] -- transforms heterogeneous data into common schema
    |
    v
[Synthesis Layer] -- LLM processes normalized events against prompt templates
    |
    v
[Storage / Output Layer] -- writes structured files, optionally triggers roll-ups
```

This is essentially a batch ETL pipeline where the "Transform" step is an LLM call rather than a deterministic function. The key architectural insight: **the LLM is a transform step, not the orchestrator.** Python code handles data movement, error handling, and file I/O. The LLM handles semantic compression and question-answering.

---

## 2. Component Definitions and Boundaries

### 2.1 Scheduler / Orchestrator

**Responsibility:** Triggers the pipeline on a schedule (end-of-day batch). Manages the sequence of stages. Handles top-level error reporting.

**Boundary:** The orchestrator calls each stage in sequence. It does not know how any stage works internally. It passes a date/time range and receives a status.

**For this project:** Claude Code + Cowork scheduled tasks. The scheduled task invokes a Python entry point. No need for Airflow, Temporal, or n8n — the pipeline is a single linear sequence with no branching or parallelism requirements in v1.

**Interface:**
- Input: Date to process (defaults to yesterday)
- Output: Success/failure status, path to generated summary file

### 2.2 Ingestion Layer

**Responsibility:** Pulls raw data from external sources for a given date range. Each source has its own ingestion module. Returns raw, source-specific data structures.

**Boundary:** Ingestion modules know how to authenticate and query one external API. They do not interpret or transform the data beyond what is needed to extract it. Each module is independent — adding a new source means adding a new module, not modifying existing ones.

**Modules for v1:**
| Module | Source | What It Pulls |
|--------|--------|---------------|
| `ingest_calendar.py` | Google Calendar API | Events for the target date: title, time, duration, attendees, description |
| `ingest_gmail_transcripts.py` | Gmail API | Emails matching transcript patterns (Gemini auto-transcriptions, Gong delivery emails). Extracts transcript text from email bodies or attachments. |

**Interface per module:**
- Input: Date range, credentials/auth config
- Output: List of raw source-specific dicts (e.g., `list[CalendarEvent]`, `list[TranscriptEmail]`)

**Key design point:** Ingestion should be idempotent. Running it twice for the same date produces the same result. This means the pipeline can safely retry on failure.

### 2.3 Normalization Layer

**Responsibility:** Transforms heterogeneous raw data from ingestion into a common event schema. Performs deduplication (e.g., a calendar event and its corresponding transcript get linked, not duplicated). Applies initial filtering (drop low-signal events like cancelled meetings, empty calendar blocks).

**Boundary:** Normalization knows the common schema and knows how to map each source type into it. It does not know anything about synthesis questions or LLM prompts. It does not make semantic judgments — only structural transformations.

**Common Event Schema (v1):**
```python
@dataclass
class NormalizedEvent:
    id: str                    # Deterministic hash for dedup
    timestamp: datetime        # When it occurred
    source: str                # "google_calendar", "gmail_gemini", "gmail_gong"
    event_type: str            # "meeting", "transcript", "calendar_block"
    title: str                 # Meeting title or email subject
    participants: list[str]    # Names/emails of people involved
    duration_minutes: int | None
    content: str               # Transcript text, event description, or empty
    metadata: dict             # Source-specific fields (calendar link, email ID, etc.)
```

**Interface:**
- Input: Raw data from all ingestion modules
- Output: `list[NormalizedEvent]` sorted by timestamp

**Key operations:**
1. Map each source type to `NormalizedEvent` fields
2. Link calendar events to their transcripts (match by time window + attendee overlap)
3. Filter out noise (cancelled events, empty descriptions with no transcript)
4. Sort chronologically

### 2.4 Synthesis Layer

**Responsibility:** Takes normalized events and produces structured answers to the daily synthesis questions. This is where the LLM does its work. Prompt engineering lives here.

**Boundary:** Synthesis receives a flat list of normalized events and a set of question templates. It produces structured text answers. It does not know where the data came from or where the output goes. It does not handle file I/O.

**V1 synthesis questions (from PROJECT.md):**
1. What happened of substance today?
2. What decisions were made, by whom, with what rationale?
3. What tasks/commitments were created, completed, or deferred?

**Interface:**
- Input: `list[NormalizedEvent]`, prompt templates (loaded from config/files)
- Output: `DailySynthesis` dataclass containing structured answers with source attribution

**Key design points:**
- Each answer item must reference the `NormalizedEvent.id` it was derived from (source attribution)
- Prompt templates should be stored as separate files, not hardcoded — they will be iterated frequently during the POC
- The synthesis layer calls Claude via the Claude Code execution context (plan limits, not API). In practice this means the synthesis step may involve writing a prompt to a file, invoking Claude, and parsing the response.
- Evidence-only framing is enforced in the prompt: no evaluative language about people

### 2.5 Storage / Output Layer

**Responsibility:** Takes the synthesis output and writes it to the file system as structured markdown. Maintains a consistent directory structure. Handles naming conventions and linking.

**Boundary:** Storage knows the file system layout and markdown formatting. It does not know about data sources, LLM prompts, or synthesis logic.

**V1 output structure:**
```
output/
  daily/
    2026-03-22.md          # Daily summary for March 22
    2026-03-23.md          # Daily summary for March 23
  raw/                     # Optional: cached raw ingestion data for debugging
    2026-03-22/
      calendar.json
      transcripts.json
```

**Interface:**
- Input: `DailySynthesis` object, target date
- Output: Written markdown file path

---

## 3. Data Flow

### 3.1 End-to-End Flow for a Single Daily Run

```
Cowork Scheduled Task (trigger)
    |
    v
main.py (orchestrator)
    |
    |-- ingest_calendar.py --> Google Calendar API --> raw calendar events
    |-- ingest_gmail_transcripts.py --> Gmail API --> raw transcript emails
    |
    v
normalize.py
    |-- maps calendar events to NormalizedEvent
    |-- maps transcripts to NormalizedEvent
    |-- links transcripts to calendar events (by time + attendees)
    |-- filters noise, deduplicates
    |-- outputs: sorted list[NormalizedEvent]
    |
    v
synthesize.py
    |-- loads prompt templates from prompts/ directory
    |-- constructs prompt: events + questions
    |-- calls Claude (via plan limits, not API)
    |-- parses structured response
    |-- outputs: DailySynthesis with source-attributed answers
    |
    v
output.py
    |-- formats DailySynthesis as markdown
    |-- writes to output/daily/YYYY-MM-DD.md
    |-- optionally caches raw data to output/raw/
    |
    v
Done. Cowork reports success/failure.
```

### 3.2 Data Volume Estimates

| Source | Estimated daily volume | Processing implications |
|--------|----------------------|------------------------|
| Google Calendar | 5-15 events | Small. Fits in a single prompt easily. |
| Gemini transcripts | 3-8 transcripts, each 2k-15k words | This is the bulk of the data. Long transcripts may need chunking or per-meeting pre-summarization before the daily synthesis prompt. |
| Gong transcripts | 1-3 transcripts, each 5k-20k words | Same chunking considerations as Gemini. |

**Context window implication:** A busy day with 8 transcripts averaging 10k words = ~80k words of transcript text. This exceeds most prompt windows if passed raw. Two strategies:
1. **Pre-summarize per meeting** (recommended for v1): Run each transcript through a summarization prompt first, producing ~500 words per meeting. Then feed the per-meeting summaries into the daily synthesis prompt.
2. **Selective inclusion:** Only pass transcripts for meetings flagged as substantive (based on attendees, duration, or title patterns).

This means the synthesis layer likely has **two LLM calls per day**: one pass for per-meeting summarization, one pass for daily synthesis across all meetings.

---

## 4. Suggested Python Project Structure

```
daily-summarizer/
  src/
    __init__.py
    main.py                  # Entry point / orchestrator
    config.py                # Auth credentials, date ranges, paths
    ingest/
      __init__.py
      calendar.py            # Google Calendar ingestion
      gmail_transcripts.py   # Gmail transcript ingestion (Gemini + Gong)
    normalize/
      __init__.py
      normalizer.py          # Common event schema + transformation logic
      linker.py              # Links transcripts to calendar events
    synthesize/
      __init__.py
      synthesizer.py         # LLM prompt construction + response parsing
    output/
      __init__.py
      writer.py              # Markdown file generation
    models/
      __init__.py
      events.py              # NormalizedEvent, DailySynthesis dataclasses
  prompts/
    meeting_summary.md       # Per-meeting summarization prompt template
    daily_synthesis.md       # Daily synthesis prompt template (the 3 questions)
  output/
    daily/                   # Generated daily summaries
    raw/                     # Cached raw data (optional)
  tests/
    test_normalize.py
    test_output.py
  requirements.txt
  .env                       # API credentials (gitignored)
```

---

## 5. Build Order (Dependencies Between Components)

The components have a strict dependency chain. Build them in this order:

### Phase 1: Foundation (no external dependencies between components)

**Step 1: Data models (`models/events.py`)**
Define `NormalizedEvent`, `DailySynthesis`, and related dataclasses. Everything downstream depends on these types. Build this first.

**Step 2: Output writer (`output/writer.py`)**
Build the markdown formatter and file writer. This seems backwards, but having the output layer working means you can test the full pipeline with mock data immediately. Write a hardcoded `DailySynthesis` object and confirm the markdown output looks right.

### Phase 2: Ingestion (can be built in parallel per source)

**Step 3a: Calendar ingestion (`ingest/calendar.py`)**
Requires: Google Calendar API auth (OAuth2 / service account). Returns raw calendar events.

**Step 3b: Gmail transcript ingestion (`ingest/gmail_transcripts.py`)**
Requires: Gmail API auth (same OAuth2 flow as Calendar). Search queries to find transcript emails. Parsing logic for Gemini and Gong transcript formats (they differ).

These two can be built in parallel since they are independent. Calendar is simpler and should be done first if working sequentially.

### Phase 3: Normalization

**Step 4: Normalizer + Linker (`normalize/`)**
Requires: Steps 1, 3a, 3b complete. Maps raw data to `NormalizedEvent`. Links transcripts to calendar events. This is where you discover edge cases (meetings with no transcript, transcripts with no matching calendar event, cancelled meetings, all-day events).

### Phase 4: Synthesis

**Step 5: Prompt templates (`prompts/`)**
Write the prompt templates for per-meeting summarization and daily synthesis. These will be iterated heavily. Start with a first draft and refine based on output quality.

**Step 6: Synthesizer (`synthesize/synthesizer.py`)**
Requires: Steps 1, 4, 5 complete. This is the core logic: construct the prompt from normalized events + templates, invoke Claude, parse the structured response. The mechanism for calling Claude within Cowork/plan limits (rather than API) needs to be figured out here.

### Phase 5: Orchestration

**Step 7: Main entry point (`main.py`)**
Wire everything together. Handle the date argument, call each stage in sequence, handle errors, report status. Set up the Cowork scheduled task to invoke this.

### Dependency Graph

```
[1. Models] ──────────────────────────────────┐
    |                                          |
    v                                          v
[2. Output Writer]                    [3a. Calendar Ingest]
                                      [3b. Gmail Ingest]
                                              |
                                              v
                                      [4. Normalizer]
                                              |
                                              v
                              [5. Prompts] + [6. Synthesizer]
                                              |
                                              v
                                      [7. Orchestrator (main.py)]
```

---

## 6. Key Architecture Decisions for This Project

### 6.1 Decisions Locked by PROJECT.md Constraints

| Decision | Settled as | Implication |
|----------|-----------|-------------|
| Language | Python | All pipeline logic in Python |
| Orchestration | Claude Code + Cowork scheduled tasks | No Airflow/Temporal. Simple sequential script. |
| LLM execution | Plan limits, not API | Synthesis step runs within Claude session, not via API calls. This constrains how the synthesizer works — it cannot make programmatic HTTP calls to Claude. |
| Storage | Flat markdown files | No database in v1. Roll-ups will read from the daily markdown files. |
| Scope | Bounce.AI only | Single workspace, single calendar, single Gmail account. |
| Batch cadence | End-of-day | No real-time processing. One run per day. |

### 6.2 Decisions Still Open

| Decision | Options | Recommendation | Reason |
|----------|---------|----------------|--------|
| How Claude is invoked for synthesis | (a) Claude Code subprocess, (b) Write prompt to file and have Cowork task process it, (c) Inline within the same Cowork session | (c) Inline — the Python script prepares the data and prompt, then the Cowork session that invoked it handles the LLM call | Simplest approach. The Cowork task runs Python to ingest/normalize, then uses the output as context for synthesis within the same session. |
| Transcript chunking strategy | (a) Pass full transcripts, (b) Pre-summarize per meeting, (c) Truncate to first N words | (b) Pre-summarize per meeting | Long transcripts will blow context windows. Per-meeting summaries give the daily synthesis prompt manageable input. |
| Calendar-to-transcript linking | (a) Time-window matching, (b) Attendee overlap, (c) Title matching, (d) Combination | (d) Combination of time-window + attendee overlap | No single signal is reliable. Time gets the candidate set, attendees confirm the match. |
| Raw data caching | (a) Cache raw ingestion data, (b) Only keep normalized output | (a) Cache raw data during POC | Debugging is critical during the POC. Cache everything so you can re-run normalization and synthesis without re-ingesting. |
| Prompt template format | (a) Inline strings, (b) Separate .md files, (c) Jinja templates | (b) Separate .md files | Prompts will be iterated constantly. Keeping them in files makes editing easy without touching code. |

### 6.3 The Plan-Limits Execution Model

This is the most unusual architectural constraint. Because the system runs on Claude plan limits (not API), the synthesis step cannot be a standard programmatic API call. The execution model is:

1. Cowork scheduled task fires
2. Task invokes Python script for ingestion + normalization
3. Python script writes normalized data to a structured file (JSON or markdown)
4. The Cowork task (which is a Claude session) reads the normalized data
5. The Cowork task applies the synthesis prompt templates against the data
6. The Cowork task writes the final daily summary markdown file

This means **the Python pipeline handles stages 1-2 (ingestion + normalization) and stage 4 (file writing), while the Claude session handles stage 3 (synthesis).** The boundary between Python and Claude is the normalized data file.

---

## 7. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Gmail API auth complexity (OAuth2 for personal use) | Blocks ingestion entirely | Use Google service account or app-specific password. Test auth flow before building anything else. |
| Transcript format varies between Gemini and Gong | Normalization breaks on unexpected formats | Build format detection + multiple parsers. Cache raw data so you can iterate parsers without re-ingesting. |
| Long transcripts exceed context window | Synthesis quality degrades or fails | Pre-summarize per meeting before daily synthesis. Two-pass LLM approach. |
| Plan-limits execution model is fragile | Cannot programmatically retry or handle errors cleanly | Keep the Python portion (ingest + normalize) fully independent and retryable. If synthesis fails, the normalized data is cached and can be re-processed. |
| Calendar events without transcripts produce thin summaries | Daily summary has gaps | Accept this for v1. Calendar-only events still provide the meeting skeleton (who, when, what topic). |

---

## 8. Quality Gate Checklist

- [x] Components clearly defined with boundaries (Section 2: five components, each with explicit responsibility, boundary, and interface)
- [x] Data flow direction explicit (Section 3: end-to-end flow diagram with data types at each stage)
- [x] Build order implications noted (Section 5: seven-step build order with dependency graph)

---

*This document informs the phase structure in the project roadmap. The build order in Section 5 maps directly to implementation phases.*
