# Project Research Summary

**Project:** Work Intelligence System — v1.5 Expanded Ingest
**Domain:** Multi-source work intelligence pipeline (Slack, HubSpot, Google Docs, Notion)
**Researched:** 2026-04-03
**Confidence:** HIGH (stack, architecture, pitfalls) / MEDIUM (cross-source dedup implementation)

## Executive Summary

This project extends an existing, production-validated daily synthesis pipeline to consume four new data sources: Slack channel messages, HubSpot CRM activity, Google Docs edits, and Notion page updates. The existing stack (Python 3.12, anthropic, Google API clients, Pydantic, Jinja2) requires only three net-new dependencies: `slack-sdk`, `hubspot-api-client`, and `notion-client`. Google Docs reuses existing OAuth credentials with no additional setup. All three new services use simple bearer tokens stored in `.env`, with no OAuth dance required — a significant simplification compared to the existing Google OAuth setup.

The recommended approach is to introduce a parallel `SourceItem` Pydantic model alongside the existing `NormalizedEvent`, rather than extending `NormalizedEvent` with nullable fields for every source type. The two paths converge at synthesis. Slack is the highest-signal new source and should be built first, with an end-to-end synthesis validation (model → ingest → extract → output) before adding more sources. Cross-source deduplication should be delegated to the LLM at synthesis time rather than implemented as heuristic string-matching — this is the most important architectural decision and the area where engineering instinct most often leads to over-engineering.

The key risk is scope creep during implementation: full-workspace Slack ingestion, full Google Docs content extraction, and comprehensive Notion block parsing are all anti-features that degrade output quality and inflate cost. The MVP is three sources (defer Notion to v1.5.x), a `SourceItem` model, source-aware synthesis prompts, and per-source error isolation. Notion is the most complex integration (no native change detection, breaking API version changes in Sept 2025, manual page-sharing requirement) and should not be attempted until the three primary sources are validated and generating useful daily output.

## Key Findings

### Recommended Stack

Three new dependencies cover all four sources. All are official SDKs actively maintained by their respective companies. Notion's SDK (`notion-client`) is community-maintained but officially endorsed by Notion. No database, web framework, or retry library additions are needed — the existing stack handles all supporting concerns.

**Core technologies:**
- `slack-sdk>=3.41.0`: Official Slack Python SDK — handles token management, rate-limit backoff, cursor pagination automatically. Build as an internal app (not Marketplace-distributed) to retain Tier 3 rate limits (50 req/min vs 1 req/min for commercial apps).
- `hubspot-api-client>=12.0.0`: Official HubSpot Python SDK for V3 API — typed clients for CRM objects, deals, engagements. Pin to `<13.0.0` to avoid surprise breaking changes between major versions.
- `notion-client>=3.0.0`: Official Notion Python port — sync/async support, thin REST wrapper. Must target API version 2025-09-03 for multi-source database support (`data_source_id` required).
- No new dependency for Google Docs — existing `google-api-python-client` and `drive.readonly` OAuth scope already cover Docs content retrieval. Do not modify `SCOPES`.

**New env vars:** `SLACK_BOT_TOKEN` (xoxb-), `HUBSPOT_ACCESS_TOKEN` (pat-), `NOTION_TOKEN` (ntn-)

**Rate limits:** Notion (3 req/s) is the only source requiring pacing — add 0.35s delay between calls. Slack (50 req/min), HubSpot (100-190 req/10s), and Google Docs (300 req/min) are trivially within limits for a daily batch.

### Expected Features

**Must have for v1.5.0 launch (P0/P1):**
- `SourceItem` model — foundation everything else depends on; `NormalizedEvent` is too calendar-centric (15+ nullable fields) to extend for new sources
- Slack channel ingestion from a curated list — messages + thread replies, bot message filtering, thread collapsing into single items per conversation
- HubSpot deal + activity ingestion — deal stage changes, contact notes, tasks for target date via engagements API
- Google Docs change detection — docs created/edited by user that day, title + first 2000 chars; reuses existing Google OAuth
- Source-aware synthesis prompts — different extraction approach for Slack (batch extraction) vs HubSpot/Docs (raw feed to Stage 2)
- Source attribution in all output — every bullet traces to origin with `(per [source]: [detail])`
- Per-source error isolation — each source fails independently without blocking pipeline (existing pattern from transcript handling)
- Config-driven source enablement — each source toggleable in `config.yaml` with channel lists, DB IDs, feature flags

**Should have post-launch (P2, v1.5.x):**
- Notion ingestion — defer until three primary sources are stable; most complex integration by far
- Cross-source deduplication — synthesis-level LLM dedup first, add heuristics only if real duplication observed
- Slack signal scoring — rank by mention count, reaction count, reply count before LLM processing
- Incremental state tracking — store cursors/timestamps to avoid re-fetching entire day
- Commitment deadline extraction from Slack/HubSpot — extend existing extraction to non-meeting sources
- HubSpot deal stage narrative — transform raw property changes to human-readable "moved from X to Y"

**Defer to v2.0+ or never (anti-features):**
- Full Slack workspace ingestion — noise, cost, most channels are zero-signal
- Real-time Slack monitoring — breaks batch architecture; webhooks add complexity for no daily-batch benefit
- Full Google Docs content extraction — blows up context windows; title + 2000 chars is sufficient
- Notion webhooks — over-engineering; polling is adequate
- Slack DM ingestion — privacy boundary; personal/work context mixed
- Cross-source thread detection — requires v2.0 entity layer
- Email body ingestion beyond transcripts — too noisy; needs entity layer for signal extraction

### Architecture Approach

The pipeline gains a parallel ingest track for non-meeting sources that converges with the existing calendar/transcript track at synthesis. Each new source module exposes a uniform interface: `fetch_{source}_activity(target_date: date, config: dict) -> list[SourceItem]`. The four new sources can run concurrently (ThreadPoolExecutor) in `main.py` since they hit independent APIs. For extraction: Slack uses a batch LLM extraction step (one Claude call for all day's Slack items). HubSpot, Docs, and Notion skip extraction and feed raw `SourceItem` objects directly to Stage 2 synthesis. Cross-source dedup is handled entirely by the Stage 2 synthesis prompt with explicit instructions to merge duplicate topics and attribute all sources.

**Major components:**
1. `src/models/events.py` (modified) — Add `SourceItem` model; update `DailySynthesis` with source item fields
2. `src/ingest/slack.py`, `hubspot.py`, `google_docs.py`, `notion.py` (new) — One module per source returning `list[SourceItem]`
3. `src/ingest/source_normalizer.py` (new) — UTC timestamp normalization, cross-source grouping for SourceItems
4. `src/synthesis/extractor.py` + `prompts.py` (modified) — Slack batch extraction prompt; updated Stage 2 synthesis prompt with explicit dedup instruction
5. `src/synthesis/synthesizer.py` (modified) — Accept both meeting extractions and source items; pass raw structured sources to Stage 2
6. `src/output/writer.py` (modified) — Render source attribution consistently throughout output
7. `src/auth/slack_auth.py`, `hubspot_auth.py`, `notion_auth.py` (new) — Token management per source
8. `config/config.yaml` (modified) — New sections: `slack.channels`, `hubspot.object_types`, `google_docs.exclude_patterns`, `notion.databases`

**Recommended build order:** `SourceItem` model → Slack ingest → Synthesis prompt update (end-to-end validation with one source) → HubSpot ingest → Google Docs ingest → Notion ingest → Cross-source dedup tuning → Writer/output updates

### Critical Pitfalls

1. **Slack rate limit misclassification** — The May 2025 Slack rate limit change (1 req/min) applies to commercially distributed non-Marketplace apps only. Internal apps retain Tier 3 (50 req/min). Build as internal app, verify "Distribute App" is disabled in Slack app settings. If you see 429s on a 10-channel daily batch, the app is misconfigured.

2. **Cross-source deduplication over-engineered** — String matching across sources fails because the same topic uses different phrasing. Let Stage 2 LLM synthesis handle semantic dedup via explicit prompt instruction: "If the same topic appears across sources, write ONE bullet with all sources attributed." This is more reliable than any heuristic system buildable in a week.

3. **Notion block extraction complexity explosion** — Notion has 50+ block types. Building a comprehensive converter is a scope trap. Handle only 6-7 text types (paragraph, heading_1/2/3, bulleted/numbered list, to_do, code). Use `[unsupported block]` placeholder for everything else. If the block parser exceeds 200 lines, stop and reassess.

4. **Google OAuth scope change triggers re-auth** — The existing `drive.readonly` scope already covers Google Docs content retrieval. Do NOT add `documents.readonly` or any other scope — doing so invalidates the existing token and breaks the pipeline until interactive re-auth. Verify before touching `google_oauth.py`.

5. **Timezone mixing across sources** — Slack (Unix timestamps, UTC), HubSpot (millisecond timestamps, UTC), Google (RFC 3339), Notion (ISO 8601). Normalize all to UTC at ingest. Define "target day" as midnight-to-midnight UTC and be consistent throughout all four modules.

## Implications for Roadmap

Based on combined research, suggested phase structure:

### Phase 1: Data Model Foundation
**Rationale:** `SourceItem` is the foundation every new ingest module and the synthesis layer depend on. Nothing else can be built without it. This is the only hard P0 dependency in the entire feature graph — it blocks everything downstream.
**Delivers:** `SourceItem` Pydantic model (id, source, source_channel, timestamp, date, item_type, title, content, participants, metadata, url, raw_data); updated `DailySynthesis` model with source item fields; `source_normalizer.py` stub with UTC timestamp normalization.
**Addresses:** Normalized item model expansion (P0)
**Avoids:** God object anti-pattern — do not extend `NormalizedEvent` with source-specific nullable fields

### Phase 2: Slack Ingest + End-to-End Synthesis Validation
**Rationale:** Slack fills the "async work" gap that is completely invisible to the current pipeline. Building it first and getting it through to output validates the entire new pipeline path (SourceItem → ingest → extract → synthesize → attribute) before committing to the same pattern for three more sources. The synthesis prompt update must happen in this phase — not later — to confirm the architecture works.
**Delivers:** `src/ingest/slack.py` (channel fetch with date bounds, thread resolution for threads with 3+ replies, bot message filtering, thread collapsing), `src/auth/slack_auth.py`, Slack user ID cache, updated `extractor.py` and `prompts.py` for Slack batch extraction, updated `synthesizer.py` for dual-path synthesis, source attribution in writer output, Slack config section.
**Implements:** Slack ingestion + source-aware synthesis prompts + source attribution + per-source error isolation (all P1)
**Avoids:** Thread reply gap (explicitly fetch `conversations.replies` for threads with reply_count >= 3); user IDs in output (build `users.info` cache at session start)

### Phase 3: HubSpot Ingest
**Rationale:** Structured CRM data with a well-understood API surface. Independent from Slack work. HubSpot activity is naturally low-volume and already structured — skip the LLM extraction step and feed raw `SourceItem` objects directly to Stage 2 synthesis.
**Delivers:** `src/ingest/hubspot.py` (deal stage changes via CRM search API, notes and tasks via engagements API, deal-level source attribution), `src/auth/hubspot_auth.py`, HubSpot config section with object_types and pipeline_ids.
**Implements:** HubSpot deal + activity ingestion (P1)
**Avoids:** "Activity feed" misconception — HubSpot has no single unified endpoint; use CRM search by `lastmodifieddate` for deals + engagements API for notes/tasks separately. Scope to user-owned deals, not full CRM.

### Phase 4: Google Docs Ingest
**Rationale:** Reuses existing Google OAuth credentials with zero new auth setup — the fastest source to add after HubSpot. The `_extract_doc_text` function already exists in `drive.py` and can be reused.
**Delivers:** `src/ingest/google_docs.py` (Drive `files.list` query for docs edited by user on target date using `modifiedByMeTime`, Docs API content extraction truncated at 2000 chars, exclusion of "Notes by Gemini" docs to prevent double-processing with transcript path), Google Docs config section.
**Implements:** Google Docs change detection (P1)
**Avoids:** OAuth scope modification (do not touch `SCOPES` in `google_oauth.py`; `drive.readonly` already works); full content extraction (hard truncation at 2000 chars)

### Phase 5: Notion Ingest
**Rationale:** Deferred from MVP because it is uniquely complex: no native change detection API (must query by `last_edited_time` and diff against state), breaking API version change in Sept 2025 (`data_source_id` required for multi-source databases), block-by-block content retrieval, and manual page-sharing requirement for every database/page to monitor. Only build after Phases 2-4 are validated generating useful daily output.
**Delivers:** `src/ingest/notion.py` (database query by `last_edited_time`, page property extraction, text block content extraction for 6-7 supported types), `src/auth/notion_auth.py`, Notion config section with database IDs and page IDs, health-check diagnostic that verifies integration can access configured pages.
**Implements:** Notion ingestion (P2)
**Avoids:** Block parser scope creep (handle only paragraph, heading_1/2/3, bulleted_list_item, numbered_list_item, to_do, code — placeholder for rest); silently empty results due to missing page sharing (build diagnostic and document setup requirement)

### Phase 6: Cross-Source Dedup Tuning and Iteration
**Rationale:** Can only tune dedup once real multi-source data is flowing from all four sources. This phase is reactive — the synthesis prompt's dedup instructions from Phase 2 may be sufficient, or may need refinement based on observed output quality. Add heuristics (Slack signal scoring, time-proximity grouping) only if concrete problems are observed.
**Delivers:** Refined synthesis prompt dedup instructions based on real output, optional Slack signal scoring (rank by mentions/reactions/replies before LLM, P2), optional incremental state tracking with cursors per source (P2), optional HubSpot deal stage narrative formatting ("moved from Proposal to Negotiation", P2).
**Addresses:** Cross-source deduplication + Slack signal scoring + incremental state tracking (all P2)
**Avoids:** Pre-synthesis entity resolution (fragile, high false-positive rate, this is literally what v2.0's entity layer is for)

### Phase Ordering Rationale

- Model-first is non-negotiable: `SourceItem` is imported by every ingest module and the synthesis layer. Building any source before the model is locked means constant interface churn.
- Slack before HubSpot: Slack requires the synthesis pipeline update to produce useful output. Getting one complete end-to-end path working validates the architecture pattern before replicating it.
- Google Docs before Notion: Docs requires zero new auth and the text extraction function already exists. Notion requires new auth, has a more complex API, and benefits from the patterns established by the earlier sources.
- Dedup tuning last: Reactive to real data. The Phase 2 synthesis prompt handles semantic dedup via LLM instruction; refine only when evidence shows it is insufficient.

### Research Flags

Phases needing closer attention during planning:
- **Phase 5 (Notion):** API version handling (`2025-09-03` breaking changes require `data_source_id`), block extraction scope discipline, manual page-sharing setup as a required pre-step, no native diff API means state-comparison design is needed. Recommend a dedicated planning pass before this phase starts.
- **Phase 6 (Dedup tuning):** No established pattern for semantic dedup of work intelligence across source types at this scale. The synthesis-level LLM approach is sound but prompt quality is empirical — plan for 2-3 iteration cycles.

Phases with standard patterns (safe to plan without additional research):
- **Phase 1 (Model):** Standard Pydantic model addition following existing `NormalizedEvent` pattern.
- **Phase 2 (Slack):** Official SDK, well-documented API, existing ingest module pattern to follow. Thread reply handling is documented.
- **Phase 3 (HubSpot):** Official SDK, structured data model, one-time private app setup. Main complexity is knowing which endpoints map to which activity types (documented in ARCHITECTURE.md).
- **Phase 4 (Google Docs):** No new auth. Existing `_extract_doc_text` utility reusable. Drive query pattern is straightforward.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All SDK choices are official or officially endorsed. Rate limits verified against current docs (March-April 2026). Auth patterns are straightforward bearer tokens for three of four services. HubSpot SDK method location note (do_search moved between API versions) warrants verification against pinned 12.x before Phase 3. |
| Features | MEDIUM | API capabilities are HIGH confidence. The P0/P1 feature set is well-defined and grounded in project scope. Cross-source dedup implementation quality is empirical — depends on prompt iteration with real data. Notion-specific features are MEDIUM given the API complexity. |
| Architecture | HIGH | Based on direct analysis of existing codebase (all src/ files reviewed). `SourceItem` model design is well-reasoned against the existing NormalizedEvent. Graceful degradation pattern already exists in production. Build order derived from hard dependency graph, not preference. |
| Pitfalls | HIGH | All pitfalls are grounded in specific API behaviors, documented version changes, and real failure modes observable in the existing codebase. Slack rate limit classification is a concrete May 2025 changelog item. Google OAuth scope pitfall is directly verifiable in `google_oauth.py`. |

**Overall confidence:** HIGH for v1.5.0 scope (Phases 1-4). MEDIUM for v1.5.x scope (Phases 5-6).

### Gaps to Address

- **Cross-source dedup quality:** The synthesis-level LLM dedup approach is architecturally correct but prompt quality is unknown until real multi-source data flows. Plan for at least two prompt iteration cycles before declaring dedup "done." Do not attempt to measure success without side-by-side comparison of raw sources vs synthesized output.
- **Notion API 2025-09-03 practical impact:** The breaking change (`data_source_id` required for multi-source databases) was confirmed in research but needs validation against a real Notion workspace and the pinned SDK version before Phase 5 implementation begins.
- **HubSpot SDK method locations:** Research flagged that `do_search` moved between `basic_api` and `identifiers_api` in recent SDK versions. Verify method locations against `hubspot-api-client==12.x` docs before Phase 3 implementation.
- **Slack thread volume in practice:** API call budget for `conversations.replies` depends on actual thread activity in configured channels. The "3+ replies" threshold is a reasonable starting point but may need tuning based on real channel activity patterns.
- **Content truncation thresholds:** First 2000 chars for Docs and Notion is a starting estimate. Actual token budget impact depends on how many sources are active simultaneously. May need adjustment once multi-source synthesis runs are measured.

## Sources

### Primary (HIGH confidence)
- Slack Python SDK GitHub (slackapi/python-slack-sdk) — rate limits, OAuth scopes, conversations API, pagination
- Slack rate limit changelog May 2025 (docs.slack.dev/changelog) — internal vs. commercial app classification
- HubSpot Python SDK GitHub (HubSpot/hubspot-api-python) — CRM objects, engagements API, V3 API surface
- HubSpot API usage guidelines (developers.hubspot.com) — rate limit tiers for Private Apps
- Google Docs API Python quickstart (developers.google.com) — OAuth scopes, document structure
- Google Drive files.list API reference (googleapis.github.io) — modifiedTime filter, mimeType query
- Notion API reference (developers.notion.com) — database query filters, request limits (3 req/s)
- Notion upgrade guide 2025-09-03 (developers.notion.com) — breaking changes for multi-source databases
- Existing codebase analysis — models/events.py, ingest/normalizer.py, ingest/calendar.py, ingest/transcripts.py, ingest/drive.py, synthesis/extractor.py, synthesis/synthesizer.py, synthesis/prompts.py, main.py, config.py

### Secondary (MEDIUM confidence)
- notion-sdk-py GitHub (ramnes/notion-sdk-py) — community SDK endorsed by Notion; sync/async support verified
- PyPI package metadata — version numbers and release dates for slack-sdk 3.41.0, hubspot-api-client 12.0.0, notion-client 3.0.0

---
*Research completed: 2026-04-03*
*Ready for roadmap: yes*
