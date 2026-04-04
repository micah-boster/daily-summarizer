# Feature Research: Multi-Source Data Ingestion (v1.5)

**Domain:** Work intelligence -- expanded data source integrations (Slack, HubSpot, Google Docs, Notion)
**Researched:** 2026-04-03
**Confidence:** MEDIUM -- API capabilities well-documented; cross-source dedup patterns are less standardized and need implementation validation

## Feature Landscape

### Table Stakes (Users Expect These)

These are the minimum features that make each new source actually useful in the daily synthesis. Without these, adding the source adds noise without signal.

#### Slack Ingestion

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Channel message fetch for curated list | Core value: see async decisions that never surface in meetings | LOW | `conversations.history` with date range filter. Internal/custom apps retain Tier 3 limits (50+ req/min, 1000 msg/req) -- rate limits only punitive for non-Marketplace commercially distributed apps |
| Thread resolution (fetch replies) | Slack threads are where decisions actually happen; top-level messages alone are misleading | MEDIUM | `conversations.replies` per thread. Requires detecting which messages have thread_ts != ts, then batch-fetching. Can be chatty on API calls for active channels |
| Channel discovery + curation config | User needs to select high-signal channels, not ingest all 50+ | LOW | `conversations.list` to enumerate, store curated list in config YAML. Already a project decision |
| Bot/app message filtering | Bot spam (deploy notifications, CI alerts) drowns signal | LOW | Filter by `subtype` field and `bot_id` presence. Configurable allow/block list |
| Source attribution in output | "Per Slack #channel-name" lets reader trace back to source | LOW | Attach channel name to each normalized item. Existing pattern in transcript source attribution |

#### HubSpot Ingestion

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Deal stage changes for target date | Deal movement is the primary CRM signal for a manager/exec | MEDIUM | Use CRM search API with `lastmodifieddate` filter on deals, then check `dealstage` property changes via property history. Requires `hubspot-api-python` SDK |
| Contact activity notes | Manual notes logged by team members are high-signal, low-volume | LOW | Engagements API filtered by type=NOTE and date range |
| Task creation/completion | Tasks represent commitments that should flow into daily commitments section | LOW | Engagements API filtered by type=TASK with `hs_timestamp` date filter |
| Meeting logs (HubSpot meetings, not calendar) | Some meetings are logged in HubSpot but not calendar | LOW | Engagements API filtered by type=MEETING. Cross-reference with calendar events for dedup |
| Deal-level attribution | "Per HubSpot: [Deal Name]" in synthesis output | LOW | Attach deal name from association lookups |

#### Google Docs Ingestion

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Detect docs created/edited today | Know what documents were worked on, even without meeting context | LOW | Google Drive API `files.list` with `modifiedTime` filter and `mimeType='application/vnd.google-apps.document'`. Already have Google OAuth creds |
| Extract document title + brief content summary | Title alone is insufficient; need enough content to understand what the doc is about | MEDIUM | Google Docs API `documents.get` returns structured JSON. Need to extract text from body elements. For long docs, truncate to first N paragraphs or use LLM summarization |
| Distinguish "I edited" vs "shared with me" | Only surface docs the user actually worked on, not every shared doc | LOW | `modifiedByMeTime` field in Drive API distinguishes user edits from others' edits |
| Source attribution | "Per Google Docs: [Doc Title]" | LOW | Straightforward metadata attachment |

#### Notion Ingestion

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Detect pages updated today | Surface Notion work activity that doesn't appear anywhere else | MEDIUM | Use database query with `last_edited_time` timestamp filter. Requires knowing which databases/spaces to monitor -- needs a curated list like Slack channels. **IMPORTANT:** Notion API version 2025-09-03 introduced breaking changes for multi-source databases; must use `data_source_id` |
| Page title + property changes | Know what changed, not just that something changed | MEDIUM | Retrieve page properties via pages API. For content changes, need to use blocks API to get page content -- Notion doesn't expose diffs, only current state |
| Database entry changes | Track structured data changes (e.g., project status updates, task completions) | MEDIUM | Query database with date filter, compare against previous run's snapshot to detect changes. Notion has no native "what changed" API -- must diff against stored state |
| Workspace/database curation config | Like Slack channels: user picks which Notion databases matter | LOW | Config YAML list of database IDs to monitor |
| Source attribution | "Per Notion: [Page Title]" or "Per Notion: [Database Name]" | LOW | Metadata from page/database objects |

### Cross-Source Features (Table Stakes for v1.5)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Normalized event model expansion | All sources must produce items the synthesis pipeline can consume | MEDIUM | Current `NormalizedEvent` is calendar-centric (start_time, attendees, transcript). Need a broader `NormalizedItem` or add a `source_type` discriminator with source-specific fields. **Key dependency: this shapes everything downstream** |
| Source-aware synthesis prompts | Slack threads need different extraction than meeting transcripts or HubSpot deal changes | MEDIUM | Current `EXTRACTION_PROMPT` assumes meeting transcript format. Need source-type-specific prompt templates, or a unified prompt that handles heterogeneous input |
| Cross-source deduplication | Same topic in meeting + Slack + HubSpot = one synthesized item, not three | HIGH | This is the hardest feature. Time-proximity + title-similarity (current approach) won't work across source types. Needs LLM-assisted or embedding-based topic matching. Start with simple heuristics (same people + same day + keyword overlap) and iterate |
| Source attribution throughout output | Every bullet in substance/decisions/commitments traces back to origin source | LOW | Extend existing `(per [source])` pattern. Already works for meetings; apply consistently to all sources |
| Per-source error isolation | One source failing should not block the entire pipeline | LOW | Existing pattern: transcript failures don't block calendar. Apply same try/except isolation to each new source |

### Differentiators (Competitive Advantage)

Features that make this system genuinely more useful than reading each source individually. Not required for launch, but high-value.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Cross-source thread detection | "This HubSpot deal was also discussed in Slack #sales and in Tuesday's meeting" -- connecting dots across sources that humans miss | HIGH | Requires entity/topic matching across source types. Could use LLM to identify topic clusters across normalized items. **Strong candidate for v1.5.1 iteration rather than v1.5.0 launch** |
| Slack signal scoring | Auto-rank Slack messages by likely importance: messages mentioning user, messages with decisions/commitments, threads with high reply count | MEDIUM | Heuristic scoring: mentions of user, reaction count, reply count, message length, presence of keywords. Reduces noise before LLM processing |
| Incremental ingestion with state tracking | Only fetch what's new since last run, not re-fetch entire day | MEDIUM | Store last-fetched timestamp/cursor per source. Slack has `oldest`/`latest` params. HubSpot has `lastmodifieddate`. Drive has `changes.list` with page tokens. Notion has `last_edited_time` filter. Saves API calls and processing time |
| Commitment deadline extraction from all sources | Structured who/what/by-when from Slack messages and HubSpot tasks, not just meetings | MEDIUM | Extend existing commitment extraction to all source types. HubSpot tasks already have structured deadlines. Slack commitments need LLM extraction. Already on the PROJECT.md active requirements list |
| HubSpot deal stage narrative | "Deal X moved from Proposal to Negotiation" as a synthesized event rather than raw property change | LOW | Transform HubSpot property history into human-readable narrative. Low complexity, high readability impact |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Full Slack workspace ingestion | "Don't miss anything" | 50+ channels at 100+ messages/day = massive noise, high LLM cost, slow pipeline. Most channels are zero-signal for an exec | Curated channel list (5-15 channels). Discovery command to suggest high-activity channels, user confirms |
| Google Docs full-text ingestion | "Understand what I wrote" | Long documents (10+ pages) blow up context windows and LLM costs. Most doc content is not relevant to daily intelligence | Title + first 500 words + any comments/suggestions. Or LLM-summarize to 200 words max |
| Real-time Slack monitoring | "See decisions as they happen" | Breaks batch architecture, adds webhook complexity, creates intraday noise. System is designed for end-of-day synthesis | End-of-day batch fetch. Already an explicit out-of-scope decision in PROJECT.md |
| Notion full page content ingestion | "Know everything that changed" | Notion pages can be huge (entire wikis). Block-by-block content retrieval is API-intensive | Title + property changes + first-level blocks only. Content summary for pages with significant changes |
| HubSpot full CRM sync | "See all customer activity" | Full CRM dump includes hundreds of contacts, thousands of activities. Most is irrelevant daily noise | Scoped to deal stage changes, notes, and tasks on deals the user owns or is associated with |
| Automatic channel/database discovery without curation | "Just figure out what's important" | What's important is highly personal and context-dependent. Auto-discovery over-includes | Discovery command that suggests, user curates. Config file is the source of truth |
| Email body ingestion (beyond transcripts) | "My inbox is where work happens" | Email is the noisiest source by far. Spam, newsletters, automated notifications. Signal extraction is extremely hard | Defer to v2.0+ or never. Current transcript-from-email approach is the right scoping |
| Notion webhook subscriptions | "Get notified of changes" | Over-engineering for batch; adds webhook server complexity | Polling via search API in daily batch |
| Slack DM ingestion | "Decisions happen in DMs too" | Privacy boundary; DMs mix personal and work context | Public/private channels only from curated list |
| Google Docs change tracking (revision diffs) | "Show me what changed" | Revision API is slow and diffs are noisy at document scale | Fetch current content of docs modified that day; title + summary is sufficient |

## Feature Dependencies

```
[Normalized Item Model Expansion]
    |
    +--requires--> [Slack Ingestion]
    +--requires--> [HubSpot Ingestion]
    +--requires--> [Google Docs Ingestion]
    +--requires--> [Notion Ingestion]
    |
    +--requires--> [Source-Aware Synthesis Prompts]
                       |
                       +--requires--> [Cross-Source Deduplication]
                                          |
                                          +--enhances--> [Cross-Source Thread Detection] (differentiator)

[Google OAuth Credentials] --already exists--> [Google Docs Ingestion]
                                           \--> [Google Drive file listing]

[Slack Channel Discovery] --enables--> [Slack Ingestion]

[HubSpot Auth Setup] --enables--> [HubSpot Ingestion]

[Notion Auth Setup] --enables--> [Notion Ingestion]

[Per-Source Error Isolation] --enhances--> [All Source Ingestion]

[Incremental State Tracking] --enhances--> [All Source Ingestion] (differentiator, can defer)
```

### Dependency Notes

- **Normalized Item Model must come first:** Every source ingestion module depends on a data model that can represent non-calendar items. The current `NormalizedEvent` is too calendar-specific (fields like `start_time`, `end_time`, `attendees`, `meeting_link`, `transcript_text`). This is the foundation layer.
- **Source-aware prompts depend on model expansion:** Can't write source-specific extraction prompts until the data shape from each source is defined.
- **Cross-source dedup depends on all sources flowing through normalization:** You need items from multiple sources to deduplicate them. This is the last integration step, not the first.
- **Google Docs reuses existing auth:** No new OAuth setup needed. Google Drive API shares the same credentials already in use for calendar and Gmail. Only needs additional OAuth scopes (`documents.readonly`, `drive.readonly`).
- **HubSpot and Notion require new auth flows:** Net-new API integrations with their own authentication. HubSpot: private app access token (simplest for personal tool). Notion: internal integration token (created at notion.so/my-integrations, must be shared with target pages/databases).
- **Notion is the most complex integration:** No native change detection API, breaking API version changes, block-by-block content retrieval. Should be last source integrated.

## MVP Definition

### Launch With (v1.5.0)

Minimum to validate multi-source synthesis. Three sources (not four) to reduce launch risk.

- [ ] **Normalized item model expansion** -- Extend or replace `NormalizedEvent` to handle heterogeneous source types (Slack message, HubSpot deal change, doc edit). This is the foundation.
- [ ] **Slack channel ingestion (curated list)** -- Highest signal new source per PROJECT.md learnings. Fetch messages + thread replies from configured channels for target date. Bot filtering.
- [ ] **HubSpot deal + activity ingestion** -- Deal stage changes, notes, and tasks for target date. Structured data that enriches meeting context.
- [ ] **Google Docs change detection** -- List docs created/edited by user on target date. Title + brief summary. Reuses existing OAuth.
- [ ] **Source-aware synthesis prompts** -- Different extraction approach for Slack threads vs HubSpot structured data vs meeting transcripts vs doc summaries.
- [ ] **Source attribution in all output** -- Every synthesized item traces back to origin source with `(per [source]: [detail])` format.
- [ ] **Per-source error isolation** -- Each source fails independently without blocking the pipeline.
- [ ] **Config-driven source enablement** -- Each source can be enabled/disabled and configured in config.yaml.

### Add After Validation (v1.5.x)

Features to add once core multi-source synthesis is working and daily output quality is validated.

- [ ] **Notion ingestion** -- Add after Slack + HubSpot + Docs are stable. Notion API has breaking changes (2025-09-03 multi-source databases) and no native diff support, making it the most complex integration. Trigger: user confirms the three primary sources are generating useful output.
- [ ] **Cross-source deduplication** -- Start with time-proximity + participant-overlap heuristics. LLM-assisted topic matching as iteration. Trigger: user reports redundant items in daily synthesis.
- [ ] **Slack signal scoring** -- Rank messages by importance before LLM processing. Trigger: Slack ingestion works but daily output is too noisy.
- [ ] **Incremental state tracking** -- Store cursors/timestamps to avoid re-fetching. Trigger: pipeline runtime becomes noticeably slow with 4+ sources.
- [ ] **Commitment deadline extraction from Slack/HubSpot** -- Structured who/what/by-when from non-meeting sources. Trigger: user validates meeting commitment extraction is accurate.
- [ ] **HubSpot deal stage narrative** -- Transform raw property changes into "Deal X moved from Proposal to Negotiation." Trigger: HubSpot raw output is hard to read.

### Future Consideration (v2.0+)

- [ ] **Cross-source thread detection** -- Connecting the same topic across Slack, meetings, and HubSpot requires entity-layer awareness. Defer until v2.0 entity layer exists.
- [ ] **Email body ingestion (beyond transcripts)** -- Too noisy for current architecture. Needs sophisticated filtering that likely requires entity layer.
- [ ] **Slack workspace auto-discovery** -- ML-based channel importance scoring. Overkill for personal tool with 5-15 channels.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority | Depends On |
|---------|------------|---------------------|----------|------------|
| Normalized item model expansion | HIGH | MEDIUM | P0 | Nothing (foundation) |
| Slack channel ingestion | HIGH | LOW | P1 | Model expansion |
| HubSpot deal/activity ingestion | HIGH | MEDIUM | P1 | Model expansion, HubSpot auth |
| Google Docs change detection | MEDIUM | LOW | P1 | Model expansion (reuses existing auth) |
| Source-aware synthesis prompts | HIGH | MEDIUM | P1 | Model expansion |
| Source attribution in output | HIGH | LOW | P1 | Model expansion |
| Per-source error isolation | MEDIUM | LOW | P1 | Nothing (pattern already exists) |
| Config-driven source enablement | MEDIUM | LOW | P1 | Nothing |
| Notion ingestion | MEDIUM | HIGH | P2 | Model expansion, Notion auth, API version handling |
| Cross-source deduplication | HIGH | HIGH | P2 | All sources ingesting |
| Slack signal scoring | MEDIUM | MEDIUM | P2 | Slack ingestion |
| Incremental state tracking | LOW | MEDIUM | P2 | All sources ingesting |
| Commitment deadline extraction (multi-source) | MEDIUM | MEDIUM | P2 | Source-aware prompts |
| HubSpot deal stage narrative | MEDIUM | LOW | P2 | HubSpot ingestion |
| Cross-source thread detection | HIGH | HIGH | P3 | Deduplication, entity layer (v2.0) |

**Priority key:**
- P0: Must complete before anything else (foundation)
- P1: Must have for v1.5.0 launch
- P2: Should have, add in v1.5.x iterations
- P3: Nice to have, future consideration

## Ecosystem Context

| Capability | Reclaim.ai / Clockwise | Notion AI | Slack AI | This System |
|---------|------------------------|-----------|----------|--------------|
| Meeting summarization | Calendar + transcript based | Notion meeting notes only | Slack huddle transcripts only | Multi-source: calendar + transcript + related Slack threads + HubSpot context |
| Cross-source synthesis | Single-source only | Notion workspace only | Slack workspace only | True cross-source daily intelligence across 4+ sources |
| Decision tracking | Not offered | Manual in Notion databases | Channel recaps mention decisions | Automated extraction from all sources with attribution |
| Temporal roll-ups | Weekly time reports only | Not offered | Weekly channel digests | Daily -> weekly -> monthly narrative synthesis |
| CRM integration | Not offered | Basic via Notion databases | Salesforce/HubSpot search (not synthesis) | HubSpot deal changes synthesized into daily intelligence |

The key differentiator: no existing tool synthesizes across Slack + CRM + Docs + meetings into a single coherent daily brief. Each platform's AI features only see their own silo.

## API-Specific Implementation Notes

### Slack
- **Auth:** Bot token with `channels:history`, `groups:history`, `channels:read` scopes. Internal/custom app -- NOT affected by 2026 rate limit crackdown (those only hit non-Marketplace commercially distributed apps).
- **Rate limits:** Tier 3 for internal apps: 50+ req/min, 1000 messages per request. Generous for batch end-of-day use.
- **Key gotcha:** Thread replies require separate `conversations.replies` call per thread. Budget for this in API call volume.
- **SDK:** `slack-sdk` Python package.

### HubSpot
- **Auth:** Private app access token (simplest for personal tool). Scoped to specific HubSpot account.
- **SDK:** `hubspot-api-python` (official, actively maintained). Note: method locations have changed in recent versions (`do_search` moved from `basic_api` to `identifiers_api`).
- **Key gotcha:** No single "what changed today" API. Must query deals by `lastmodifieddate`, then check property history for stage changes. Engagements API for notes/tasks/meetings.

### Google Docs
- **Auth:** Reuses existing Google OAuth credentials. Add `https://www.googleapis.com/auth/documents.readonly` and `https://www.googleapis.com/auth/drive.readonly` scopes.
- **Key gotcha:** Google Docs API returns structured JSON (paragraphs, tables, lists), not plain text. Consider using Drive API `files.export` with `text/plain` mimeType for simpler text extraction instead of parsing the document structure.

### Notion
- **Auth:** Internal integration token (created at notion.so/my-integrations). Must be explicitly shared with target pages/databases.
- **API version:** Must target 2025-09-03 or later for multi-source database support. Breaking change: `data_source_id` required for database operations.
- **SDK:** `notion-sdk-py` (community, sync + async support).
- **Key gotcha:** No "what changed" API. Must query pages by `last_edited_time` filter, then diff against stored state to detect actual changes. Most complex integration of the four.

## Sources

- [Slack conversations.history API](https://api.slack.com/methods/conversations.history)
- [Slack rate limit changes for non-Marketplace apps](https://api.slack.com/changelog/2025-05-terms-rate-limit-update-and-faq)
- [Slack rate limits documentation](https://docs.slack.dev/apis/web-api/rate-limits/)
- [HubSpot CRM Deals API](https://developers.hubspot.com/docs/api-reference/crm-deals-v3/guide)
- [HubSpot hubspot-api-python GitHub](https://github.com/HubSpot/hubspot-api-python)
- [Google Docs API Python quickstart](https://developers.google.com/workspace/docs/api/quickstart/python)
- [Google Drive changes API](https://developers.google.com/workspace/drive/api/guides/manage-changes)
- [Google Drive files.list modifiedTime filter](https://googleapis.github.io/google-api-python-client/docs/dyn/drive_v3.files.html)
- [Notion API database query filters](https://developers.notion.com/reference/post-database-query-filter)
- [Notion API upgrade guide 2025-09-03](https://developers.notion.com/docs/upgrade-guide-2025-09-03)
- [notion-sdk-py GitHub](https://github.com/ramnes/notion-sdk-py)

---
*Feature research for: Work Intelligence System v1.5 -- Multi-Source Data Ingestion*
*Researched: 2026-04-03*
