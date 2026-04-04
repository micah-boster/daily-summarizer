# Architecture Patterns

**Domain:** Multi-source work intelligence pipeline -- expanding ingestion layer
**Researched:** 2026-04-03

## Current Architecture (Baseline)

The existing pipeline follows a clean three-stage pattern:

```
INGEST                    NORMALIZE                EXTRACT/SYNTHESIZE        OUTPUT
calendar.py ──┐
transcripts.py ┼──> normalizer.py ──> extractor.py ──> synthesizer.py ──> writer.py
drive.py ──────┘     (match + dedup)   (per-meeting)    (daily rollup)     (markdown)
gmail.py ──────┘                                                            slack.py
```

Key characteristics:
- **NormalizedEvent** is the universal internal model (Pydantic), tightly coupled to calendar events
- **Two-stage synthesis:** Stage 1 extracts per-meeting, Stage 2 cross-references into daily brief
- **Transcript-to-event matching:** Transcripts are attached to calendar events by time+title similarity
- **DailySynthesis** model aggregates events into substance/decisions/commitments sections
- **Config-driven:** YAML config controls source patterns, model selection, output paths
- **Batch processing:** End-of-day run for a target date, no real-time component

## Problem: NormalizedEvent Is Meeting-Centric

The current NormalizedEvent model assumes everything is a calendar event with optional transcript. New sources break this assumption:

| Source | Nature | Fits NormalizedEvent? |
|--------|--------|----------------------|
| Calendar + Transcripts | Time-bounded meeting with attendees | YES (designed for this) |
| Slack messages | Async threads across channels | NO -- no start/end time, no attendees list, thread-based |
| HubSpot activities | CRM events: deal stage changes, notes, tasks | NO -- structured data, not meetings |
| Google Docs edits | Document activity for a date | NO -- content changes, not events |
| Notion page updates | Page/database mutations | NO -- structured properties, not meetings |

**This is the central architectural decision for v1.5.**

## Recommended Architecture

### New Model: SourceItem (Sibling to NormalizedEvent)

Do NOT force new sources into NormalizedEvent. Instead, introduce a parallel normalized model for non-meeting intelligence:

```python
class SourceItem(BaseModel):
    """A normalized unit of work intelligence from any non-meeting source."""
    id: str
    source: str                          # "slack", "hubspot", "google_docs", "notion"
    source_channel: str | None = None    # "#product-dev", "Deal: Acme Corp", etc.
    timestamp: datetime
    date: str                            # YYYY-MM-DD for date-based grouping
    item_type: str                       # "message", "thread_summary", "deal_change",
                                         # "note", "doc_edit", "page_update", "task"
    title: str                           # Thread topic, deal name, doc title, page title
    content: str                         # The substantive text content
    participants: list[str] = []         # People involved (names/handles)
    metadata: dict = {}                  # Source-specific structured data
    url: str | None = None               # Deep link back to source
    raw_data: dict | None = None         # Original API response
```

### Why Not Extend NormalizedEvent?

NormalizedEvent has 15+ calendar-specific fields (attendees with response status, meeting links, recurring flags, all-day detection, calendar IDs). Cramming Slack messages or HubSpot deal changes into this model creates a god object where most fields are None for most records. Separate models that converge at synthesis is cleaner.

### Updated Pipeline Flow

```
INGEST (existing)              NORMALIZE              EXTRACT              SYNTHESIZE         OUTPUT
calendar.py ──┐
transcripts.py ┼──> normalizer.py ──> [NormalizedEvent] ──┐
drive.py ──────┘     (match + dedup)                       │
                                                           ├──> extractor.py ──> synthesizer.py ──> writer.py
INGEST (new)                                               │    (Stage 1)       (Stage 2)
slack.py ──────┐                                           │
hubspot.py ────┤                                           │
google_docs.py ┤──> source_normalizer.py ──> [SourceItem] ─┘
notion.py ─────┘     (dedup across sources)
```

### Component Boundaries

| Component | Responsibility | New/Modified | Communicates With |
|-----------|---------------|--------------|-------------------|
| `src/ingest/slack.py` | Fetch messages from curated channels for target date | NEW | Slack API via slack_sdk |
| `src/ingest/hubspot.py` | Fetch deal changes, notes, tasks for target date | NEW | HubSpot API via hubspot-api-client |
| `src/ingest/google_docs.py` | Fetch docs created/edited on target date | NEW | Google Drive + Docs API (existing creds) |
| `src/ingest/notion.py` | Fetch page updates, database changes for target date | NEW | Notion API via notion-client |
| `src/models/events.py` | Add SourceItem model alongside NormalizedEvent | MODIFIED | All ingest + synthesis modules |
| `src/ingest/source_normalizer.py` | Cross-source dedup, normalize SourceItems | NEW | All new ingest modules |
| `src/synthesis/extractor.py` | Add source_item extraction (non-meeting) | MODIFIED | New extraction prompt for SourceItems |
| `src/synthesis/synthesizer.py` | Merge meeting + source extractions | MODIFIED | Both extraction paths |
| `src/synthesis/prompts.py` | Add prompts for source-specific extraction | MODIFIED | extractor.py |
| `src/models/events.py` | Update DailySynthesis to include source_items | MODIFIED | writer.py, synthesizer.py |
| `src/output/writer.py` | Render source attribution in output | MODIFIED | DailySynthesis model |
| `config/config.yaml` | Add source configuration sections | MODIFIED | All new ingest modules |
| `src/auth/slack_auth.py` | Slack bot token management | NEW | slack.py |
| `src/auth/hubspot_auth.py` | HubSpot private app token | NEW | hubspot.py |
| `src/auth/notion_auth.py` | Notion integration token | NEW | notion.py |
| `src/main.py` | Orchestrate new ingest sources in run_daily() | MODIFIED | All ingest modules |

## Data Flow Per Source

### Slack

```
1. Read curated channel list from config (slack.channels)
2. For each channel:
   a. conversations.history(channel, oldest=start_of_day, latest=end_of_day)
   b. For messages with thread_ts != ts (thread parents with replies):
      conversations.replies(channel, ts) to get full thread
   c. Filter: skip bot messages, join/leave, reactions-only
3. Collapse threads into single SourceItem per thread
   - title = first message or channel topic
   - content = thread summary (collapse to key points if >N messages)
   - participants = unique human posters in thread
   - source_channel = "#channel-name"
   - url = deep link to thread
4. For high-volume channels: pre-filter with keyword/participant matching
```

**Rate limit concern:** Slack's conversations.history is rate-limited. For new non-Marketplace apps, starting May 2025 it is 1 request/minute with max 15 messages per request. If the app is an existing Marketplace-distributed app or was installed before the cutoff, older limits apply (50 req/min, 100 messages/request). For a curated list of 5-10 channels, even the restrictive limits work within a batch pipeline that runs once daily -- but the code must handle pagination and backoff gracefully.

**Thread collapsing strategy:** Slack threads are the unit of intelligence, not individual messages. A 30-message thread about "should we hire a HubSpot contractor" is one SourceItem with content summarizing the thread outcome, not 30 items. For threads with >10 messages, consider an LLM pre-summarization step (cheap, fast, Haiku-tier) before feeding into the main extraction pipeline.

### HubSpot

```
1. Read HubSpot scope from config (hubspot.object_types, hubspot.pipeline_ids)
2. Fetch recent activity:
   a. CRM search API: deals updated in date range
      - Filter by lastmodifieddate within target day
      - Include properties: dealname, dealstage, amount, closedate, pipeline
      - Include associations: contacts, companies
   b. Engagements API: notes, tasks, calls created on target date
      - Filter by hs_timestamp or hs_createdate
      - Include body text and associations
3. Normalize each into SourceItem:
   - Deal stage change: item_type="deal_change", content="Deal X moved from Stage A to Stage B"
   - Note: item_type="note", content=note body, title=associated deal/contact name
   - Task: item_type="task", content=task body, participants=[owner]
   - metadata = {deal_id, pipeline, stage_from, stage_to, amount}
```

**Authentication:** HubSpot private app tokens are the simplest path. Create a private app in HubSpot settings, grant CRM scopes (crm.objects.deals.read, crm.objects.contacts.read, crm.objects.companies.read), store the token in .env.

**Scope constraint from PROJECT.md:** Activity logs, deal changes, notes -- not full CRM dump. The ingest module should fetch only records modified on the target date, not enumerate all deals.

### Google Docs

```
1. Reuse existing Google OAuth credentials (already have Drive + Docs scopes)
2. Drive API: search for docs modified on target date
   - query: "mimeType='application/vnd.google-apps.document'
             and modifiedTime >= '{date}T00:00:00'
             and modifiedTime < '{next_date}T00:00:00'"
   - Exclude "Notes by Gemini" docs (already handled by drive.py transcript path)
3. For each doc:
   a. Get file metadata: name, modifiedTime, owners, lastModifyingUser
   b. Get revision list to determine if created vs. edited
   c. Docs API: extract document content (reuse _extract_doc_text from drive.py)
4. Normalize into SourceItem:
   - item_type = "doc_created" or "doc_edited"
   - title = document name
   - content = first N paragraphs or document summary
   - participants = [lastModifyingUser, owners]
   - url = doc URL
   - metadata = {doc_id, revision_count, word_count}
```

**Key distinction from existing drive.py:** The current drive.py searches specifically for "Notes by Gemini" meeting transcripts. google_docs.py handles everything else -- docs the user created or edited that day. The filter must exclude Gemini notes to avoid double-processing.

**Content handling:** For long documents, do NOT send full content through the extraction pipeline. Instead, send the first 2000 characters + document metadata. The synthesis prompt can note "Document X was edited" without needing the full 50-page doc.

### Notion

```
1. Read Notion config (notion.database_ids, notion.page_ids_to_watch)
2. For each tracked database:
   a. databases.query(database_id, filter={
        "timestamp": "last_edited_time",
        "last_edited_time": {"on_or_after": start_of_day_iso}
      })
   b. For each returned page: extract title, properties, last_edited_by
3. For tracked individual pages:
   a. pages.retrieve(page_id) -- check last_edited_time
   b. If edited on target date: blocks.children.list(page_id) for content
4. Normalize into SourceItem:
   - item_type = "page_update" or "database_entry"
   - title = page title
   - content = property changes summary or page content snippet
   - participants = [last_edited_by]
   - source_channel = database name or parent page
   - url = Notion page URL
   - metadata = {page_id, database_id, properties_changed}
```

**Authentication:** Notion internal integration token. Created in Notion settings, must be explicitly shared with target pages/databases. Store token in .env.

**Scope management:** Unlike Slack (where you choose channels) or HubSpot (where you query by date), Notion requires explicitly connecting the integration to each page/database. Config should list database IDs and page IDs to monitor, with the integration shared to those resources in Notion.

## Cross-Source Deduplication

This is the hardest architectural problem in v1.5. The same topic can appear across multiple sources:

```
Meeting transcript: "Decided to hire HubSpot contractor"
Slack #product-dev: Thread about HubSpot contractor budget
HubSpot: New task created "Interview HubSpot contractors"
Notion: Updated hiring tracker page
```

### Strategy: Dedup at Synthesis, Not Ingestion

Do NOT try to match SourceItems to NormalizedEvents or to each other at the normalization layer. Instead:

1. **Ingest everything.** Each source produces its own SourceItems independently.
2. **Extract independently.** Run extraction on meetings and source items separately.
3. **Dedup at synthesis.** The Stage 2 synthesis prompt explicitly instructs Claude to merge duplicate topics across sources, noting all source attributions.

This is the right call because:
- Cross-source matching by title/content is fragile (different phrasing across sources)
- LLMs are good at recognizing "these three items are about the same thing"
- Source attribution is preserved ("per meeting X, Slack #channel, HubSpot deal Y")
- The existing synthesizer already deduplicates across meetings; extending to sources is natural

### Updated Synthesis Prompt Pattern

The SYNTHESIS_PROMPT needs to be updated to include source items alongside meeting extractions:

```
Meeting Extractions:
{extractions_text}

Source Activity:
{source_items_text}

DEDUPLICATION: If the same topic appears in a meeting AND in Slack/HubSpot/Docs/Notion,
write ONE bullet with all sources attributed. Example:
- Decided to hire HubSpot contractor (<$5K) -- Micah -- Leadership Sync, Slack #product-dev
```

## Extraction Strategy for Non-Meeting Sources

### Option A: Per-item extraction (NOT recommended)
Send each SourceItem individually to Claude for extraction. Too many API calls, too expensive for low-signal items.

### Option B: Batch extraction by source (Recommended for Slack)
Group SourceItems by source, send one prompt per source type per day:

```
"Here are today's Slack threads from curated channels. Extract substance, decisions, and commitments:"
[All Slack SourceItems for the day]
```

This produces a SourceExtraction model (parallel to MeetingExtraction) that feeds into the Stage 2 synthesizer alongside meeting extractions.

### Option C: Skip extraction, feed raw to synthesis (Recommended for HubSpot/Docs/Notion)
For low-volume sources, the raw SourceItems may be compact enough to feed directly into the Stage 2 synthesis prompt without a separate extraction step. Reserve extraction for high-volume sources.

**Recommendation:** Use Option B for Slack (high volume, needs filtering). Use Option C for HubSpot/Docs/Notion (lower volume, already structured).

## Config Structure Extension

```yaml
# New sections in config/config.yaml

slack:
  enabled: true
  bot_token_env: "SLACK_BOT_TOKEN"    # env var name
  channels:                            # curated channel list
    - id: "C01ABCDEF"
      name: "product-dev"
    - id: "C02GHIJKL"
      name: "leadership"
  exclude_bot_messages: true
  thread_collapse_threshold: 10        # threads > N messages get pre-summarized
  max_messages_per_channel: 200        # safety cap

hubspot:
  enabled: true
  access_token_env: "HUBSPOT_ACCESS_TOKEN"
  object_types:
    - deals
    - notes
    - tasks
  pipeline_ids: []                     # empty = all pipelines

google_docs:
  enabled: true
  # Reuses existing Google OAuth credentials
  exclude_patterns:
    - "Notes by Gemini"               # already handled by transcript pipeline
  max_content_chars: 2000             # truncate doc content for extraction

notion:
  enabled: true
  token_env: "NOTION_TOKEN"
  databases:
    - id: "abc123..."
      name: "Project Tracker"
    - id: "def456..."
      name: "Hiring Pipeline"
  pages: []                            # individual pages to monitor
```

## Patterns to Follow

### Pattern 1: Source Module Interface Contract
Every new ingest module must follow the same interface pattern.

**What:** Each source module exports a single top-level fetch function that accepts (target_date, config) and returns list[SourceItem].
**When:** Every new data source.
**Example:**
```python
# src/ingest/slack.py
def fetch_slack_activity(target_date: date, config: dict) -> list[SourceItem]:
    """Fetch and normalize all Slack activity for a target date."""
    ...

# src/ingest/hubspot.py
def fetch_hubspot_activity(target_date: date, config: dict) -> list[SourceItem]:
    """Fetch and normalize all HubSpot activity for a target date."""
    ...
```

### Pattern 2: Graceful Degradation Per Source
Each source fails independently without blocking the pipeline.

**What:** Wrap each source's fetch in try/except in main.py, log warning, continue with available data.
**When:** Always. This is the existing pattern for transcripts and must be maintained.
**Example:**
```python
# In run_daily():
source_items: list[SourceItem] = []

for fetch_fn, source_name in [
    (fetch_slack_activity, "Slack"),
    (fetch_hubspot_activity, "HubSpot"),
    (fetch_google_docs_activity, "Google Docs"),
    (fetch_notion_activity, "Notion"),
]:
    try:
        items = fetch_fn(current, config)
        source_items.extend(items)
        logger.info("Fetched %d items from %s", len(items), source_name)
    except Exception as e:
        logger.warning("%s ingestion failed: %s. Continuing.", source_name, e)
```

### Pattern 3: Raw Response Caching
Cache raw API responses for debugging and reprocessing.

**What:** Each source writes its raw API response to output/raw/YYYY/MM/DD/{source}.json, matching the existing calendar caching pattern in calendar.py's cache_raw_response().
**When:** Every source, every run.

### Pattern 4: Date-Bounded Queries
Every API call is scoped to the target date.

**What:** Use each API's native date filtering at query time, never fetch-all-then-filter.
**When:** Every API call.
**Example:**
```python
# Slack: oldest/latest params (Unix timestamps)
client.conversations_history(channel=ch, oldest=str(day_start.timestamp()),
                             latest=str(day_end.timestamp()))

# HubSpot: search filter on lastmodifieddate
filter = {"propertyName": "hs_lastmodifieddate", "operator": "BETWEEN",
          "value": day_start_ms, "highValue": day_end_ms}

# Google Docs: Drive query with modifiedTime
q = f"mimeType='application/vnd.google-apps.document' and modifiedTime > '{iso_start}'"

# Notion: database query with last_edited_time filter
filter = {"timestamp": "last_edited_time",
          "last_edited_time": {"on_or_after": iso_start}}
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: God Model
**What:** Extending NormalizedEvent with 20+ nullable fields to handle every source type.
**Why bad:** Every consumer of NormalizedEvent must now handle a superset of fields that are mostly None. Type safety degrades. The model name becomes a lie -- it is no longer "normalized."
**Instead:** Separate SourceItem model that converges with NormalizedEvent at the synthesis layer.

### Anti-Pattern 2: Real-Time Ingestion
**What:** Setting up webhooks or socket connections for live data.
**Why bad:** The system is a batch pipeline. Real-time adds WebSocket management, webhook endpoints, persistent processes, retry queues. All for data that will be synthesized once daily anyway.
**Instead:** Batch fetch for target date at pipeline runtime. Per PROJECT.md: "end-of-day batch sufficient."

### Anti-Pattern 3: Pre-Synthesis Cross-Source Matching
**What:** Building an entity resolution system to link Slack messages to calendar events to HubSpot deals before synthesis.
**Why bad:** Fragile heuristic matching, high false-positive rate, massive engineering effort. This is literally what v2.0's entity layer is designed for.
**Instead:** Let the LLM do cross-source dedup at synthesis time. It is better at fuzzy topic matching than any heuristic system you would build in a week.

### Anti-Pattern 4: Full Content Ingestion
**What:** Sending entire Slack channel histories or full Google Docs content to Claude.
**Why bad:** Token costs explode, context windows fill with noise, extraction quality drops.
**Instead:** Thread-level collapsing for Slack, first-N-chars for Docs, structured properties for HubSpot/Notion.

### Anti-Pattern 5: Generic API Client Wrapper
**What:** Building an abstraction layer over all four APIs.
**Why bad:** Each API has fundamentally different data models, pagination, and auth. Abstraction would be leaky.
**Instead:** Each ingest module uses its SDK directly; normalization happens at the output (SourceItem model).

## Scalability Considerations

| Concern | Current (2 sources) | v1.5 (6 sources) | v2.0+ (entity layer) |
|---------|---------------------|-------------------|-----------------------|
| API calls per run | ~5-10 (Calendar + Gmail + Drive) | ~20-40 (add Slack channels + HubSpot + Notion) | Same; entity resolution is post-processing |
| LLM API calls | 1 per meeting + 1 synthesis | +1 Slack batch extraction + 1 synthesis | +entity extraction pass |
| Token consumption | ~2K-8K per meeting extraction | +~3K-5K for source batch extractions | +~2K for entity extraction |
| Runtime | ~2-5 min | ~5-10 min (mostly API latency) | ~10-15 min |
| Config complexity | Simple YAML | Moderate (channel lists, DB IDs) | Needs config validation |

## Pipeline Orchestration Update

The updated `run_daily()` flow in main.py:

```
1. Auth: Load Google creds, Slack token, HubSpot token, Notion token
2. Calendar ingest: fetch_events_for_date() -> categorized events
3. Transcript ingest: fetch_all_transcripts() -> match to events
4. Source ingest (parallel-safe, independent):
   a. fetch_slack_activity(date, config) -> list[SourceItem]
   b. fetch_hubspot_activity(date, config) -> list[SourceItem]
   c. fetch_google_docs_activity(date, config) -> list[SourceItem]
   d. fetch_notion_activity(date, config) -> list[SourceItem]
5. Cache all raw responses
6. Stage 1a: extract_all_meetings(events_with_transcripts) -> list[MeetingExtraction]
7. Stage 1b: extract_source_items(slack_items, config) -> list[SourceExtraction]
         (HubSpot/Docs/Notion skip this step -- fed raw into Stage 2)
8. Stage 2: synthesize_daily(meeting_extractions, source_extractions,
                             raw_hubspot_items, raw_docs_items, raw_notion_items)
9. Build DailySynthesis model (updated with source_item_count, source_summary)
10. Write output (markdown, sidecar, Slack notification)
```

Steps 4a-4d can run concurrently (ThreadPoolExecutor) since they hit different APIs with no interdependencies.

## Suggested Build Order

Based on dependency analysis and value delivery:

1. **SourceItem model + source_normalizer.py** -- Foundation everything else depends on
2. **Slack ingest** -- Highest signal source per PROJECT.md learnings, fills the "async work" gap
3. **Updated synthesis prompts + extractor changes** -- Needed to actually use Slack data in output
4. **HubSpot ingest** -- Structured CRM data, independent from Slack work
5. **Google Docs ingest** -- Leverages existing Google OAuth, straightforward
6. **Notion ingest** -- Separate auth, separate API, can be last
7. **Cross-source dedup tuning** -- Refine synthesis prompts based on real multi-source data
8. **DailySynthesis model updates + writer changes** -- Source attribution in output

**Rationale:** Model first (everything depends on it), then highest-value source (Slack), then synthesis integration (to validate the pattern works end-to-end before adding more sources), then remaining sources in order of signal value. Writer updates come last because the synthesis pipeline must produce multi-source output before the writer can render it.

## Sources

- Existing codebase analysis (all src/ files read directly): models/events.py, ingest/normalizer.py, ingest/calendar.py, ingest/transcripts.py, ingest/drive.py, synthesis/extractor.py, synthesis/synthesizer.py, synthesis/prompts.py, main.py, config.py
- [Slack conversations.history API](https://api.slack.com/methods/conversations.history) -- rate limits, pagination
- [Slack Python SDK](https://tools.slack.dev/python-slack-sdk/legacy/conversations) -- conversations API usage
- [HubSpot Python SDK](https://github.com/HubSpot/hubspot-api-python) -- CRM object access patterns
- [Notion API](https://developers.notion.com) -- database query, page retrieval
- [Notion Python SDK (notion-sdk-py)](https://github.com/ramnes/notion-sdk-py) -- community Python client
- PROJECT.md -- scope constraints, v1.0 learnings, design decisions
