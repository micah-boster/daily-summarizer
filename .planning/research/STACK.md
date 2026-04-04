# Technology Stack: v1.5 Expanded Ingest

**Project:** Work Intelligence System - Data Source Integrations
**Researched:** 2026-04-03
**Overall confidence:** HIGH

## Existing Stack (DO NOT CHANGE)

Already validated and in production. Listed for reference only.

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.12 | Runtime |
| anthropic | >=0.45.0 | Claude API for synthesis |
| google-api-python-client | >=2.193.0 | Google Calendar, Drive, Docs APIs |
| google-auth / google-auth-oauthlib | >=2.49.1 / >=1.3.1 | Google OAuth2 |
| httpx | >=0.28.1 | HTTP client (Slack webhooks) |
| pydantic | >=2.12.5 | Data models |
| jinja2 | >=3.1.6 | Output templates |
| pyyaml | >=6.0.3 | Config |
| python-dotenv | >=1.0.0 | Env vars |

## New Dependencies for v1.5

### Slack API: `slack-sdk`

| | Detail |
|---|--------|
| **Package** | `slack-sdk>=3.41.0` |
| **Why this** | Official Slack Python SDK maintained by Slack. Replaces deprecated `slackclient`. Provides `WebClient` with built-in retry handling, rate limit awareness, and cursor-based pagination. |
| **Why not httpx** | `slack-sdk` handles token management, pagination cursors, rate limit backoff, and typed responses. Raw HTTP would mean reimplementing all of this. |
| **Confidence** | HIGH - official SDK, actively maintained, v3.41.0 released March 2026 |

**Authentication:** Bot Token (xoxb-) via Slack App with custom install to workspace.

| Scope | Purpose | Required For |
|-------|---------|-------------|
| `channels:history` | Read messages from public channels | `conversations.history` |
| `channels:read` | List public channels (discovery) | `conversations.list` |
| `groups:history` | Read messages from private channels | `conversations.history` on private channels |
| `groups:read` | List private channels (discovery) | `conversations.list` for private channels |
| `users:read` | Resolve user IDs to display names | Rendering "who said what" |

Setup: Create Slack App at api.slack.com -> Install to workspace -> Copy Bot User OAuth Token -> Store in `.env` as `SLACK_BOT_TOKEN`.

**Rate Limits (CRITICAL):**
This is an internal/personal app (not commercially distributed), which means Tier 3 limits apply:
- `conversations.history`: ~50 requests/minute per workspace (Tier 3)
- `conversations.list`: ~20 requests/minute (Tier 2)
- `users.info`: ~50 requests/minute (Tier 3)

For a daily batch reading ~10-20 curated channels, this is more than sufficient. The SDK's built-in `RetryHandler` handles 429 responses automatically. No custom rate limiting needed for this use case.

**Warning:** Non-Marketplace commercially distributed apps face 1 req/min limit as of May 2025. This does NOT apply to internal apps installed only in your own workspace.

### HubSpot API: `hubspot-api-client`

| | Detail |
|---|--------|
| **Package** | `hubspot-api-client>=12.0.0` |
| **Why this** | Official HubSpot Python SDK for V3 API. Provides typed client classes for each API domain (deals, contacts, engagements). Handles pagination and auth. |
| **Why not httpx** | HubSpot's API surface is large; the SDK provides pre-built clients for each endpoint family (CRM, engagements, etc.) with pagination helpers. |
| **Confidence** | HIGH - official SDK, v12.0.0 released May 2025 |

**Authentication:** Private App Access Token.

Setup: HubSpot Settings -> Integrations -> Private Apps -> Create -> Select scopes -> Copy access token -> Store in `.env` as `HUBSPOT_ACCESS_TOKEN`. Token does not expire (manual rotation only).

| Scope | Purpose |
|-------|---------|
| `crm.objects.deals.read` | Read deal records and changes |
| `crm.objects.contacts.read` | Read contact records |
| `sales-email-read` | Read email engagement logs |
| `crm.objects.owners.read` | Resolve owner IDs to names |

**Rate Limits:**
- Private apps: 100 requests/10 seconds (Free/Starter), 190 requests/10 seconds (Professional/Enterprise)
- Daily limit: effectively unlimited for this use case (500K+/day)
- For daily batch pulling deal activity and notes, this is far more than sufficient

**Key API endpoints for v1.5:**
- `api_client.crm.deals.basic_api.get_page()` - List deals
- `api_client.crm.deals.search_api.do_search()` - Search deals modified today
- `api_client.crm.objects.notes.basic_api.get_page()` - Get notes/engagements
- `api_client.crm.timeline.events_api` - Timeline events for activity feed

### Google Docs API: NO NEW DEPENDENCY

| | Detail |
|---|--------|
| **Package** | Already have `google-api-python-client` |
| **Why no addition** | `drive.py` already builds a Docs service via `build("docs", "v1", credentials=creds)`. The existing `drive.readonly` OAuth scope already grants read access to Google Docs content. |
| **What's needed** | New ingest module that uses Drive API `files.list()` with `mimeType='application/vnd.google-apps.document'` and `modifiedTime > '{today}'` query to find docs edited that day, then `documents().get()` to fetch content. |
| **Confidence** | HIGH - already working in production for Gemini notes |

**Additional scope needed:** None. `drive.readonly` covers both Drive file listing and Docs content reading.

**Rate Limits:**
- Google Docs API: 300 read requests/minute per user (default)
- Google Drive API: 12,000 queries/day per project
- Trivially sufficient for daily batch

**Strategy for "docs edited today":**
1. `drive.files().list(q="mimeType='application/vnd.google-apps.document' and modifiedTime > '2026-04-02T00:00:00'")` - Find modified docs
2. `docs.documents().get(documentId=id)` - Fetch content for each
3. Filter to docs the user actually edited (not just viewed) using `drive.revisions().list()` if needed

### Notion API: `notion-client`

| | Detail |
|---|--------|
| **Package** | `notion-client>=3.0.0` |
| **Why this** | Official Python port of the Notion reference SDK. Maintained by the community (`ramnes/notion-sdk-py`) but endorsed by Notion. Sync and async support. Simple, thin wrapper around the REST API. |
| **Why not httpx** | Notion's API has specific pagination (cursor-based, block-level), content structures (rich text blocks), and auth patterns that the SDK handles cleanly. |
| **Why not `ultimate-notion`** | Over-abstracted for our needs. We want raw API data to normalize into our own models, not another ORM layer. |
| **Confidence** | HIGH - widely used, 3.0.0 is stable release |

**Authentication:** Internal Integration Token.

Setup: notion.so/my-integrations -> Create integration -> Select workspace -> Copy "Internal Integration Secret" -> Store in `.env` as `NOTION_TOKEN`. Then share target pages/databases with the integration manually.

**Rate Limits (MOST RESTRICTIVE of all four):**
- 3 requests/second average (some burst allowed)
- No paid tier upgrade available
- For daily batch reading ~5-20 pages, this requires:
  - Sequential requests with simple delay (0.35s between calls)
  - Or batch page queries using `search` endpoint to reduce call count

**Key API methods for v1.5:**
- `notion.search(filter={"property": "object", "value": "page"}, sort={"direction": "descending", "timestamp": "last_edited_time"})` - Find recently edited pages
- `notion.pages.retrieve(page_id)` - Get page metadata
- `notion.blocks.children.list(block_id)` - Get page content (blocks)
- `notion.databases.query(database_id, filter=...)` - Query database for recent changes

**Content extraction challenge:** Notion stores content as nested blocks (paragraphs, headings, lists, etc.). Each block type has different structure. Need a block-to-text flattener for synthesis input.

## What NOT to Add

| Library | Why Not |
|---------|---------|
| `requests` | Already have `httpx` which is strictly better (async support, HTTP/2). HubSpot SDK uses `requests` internally but that's its own dependency. |
| `aiohttp` | Not needed. `httpx` already supports async if we need it later. |
| `slack-bolt` | Framework for Slack apps with event handlers/listeners. We're doing batch reads, not building a bot that responds to events. |
| `notion-py` | Unofficial, uses internal API, fragile. Use official `notion-client`. |
| `hubspot3` | Legacy/community wrapper. Official `hubspot-api-client` is maintained by HubSpot. |
| `google-auth-httplib2` | Already in deps but only needed for legacy patterns. Existing code already uses it; no change needed. |
| Any database library | Storage remains flat files for v1.5. DB deferred to v2.0. |
| Any web framework | No API/UI in v1.5. Deferred to v4.0. |
| `tenacity` / retry libraries | Slack SDK has built-in retry. HubSpot SDK handles retries. For Notion, simple `time.sleep` between calls is sufficient given 3 req/s limit. |

## Installation

```bash
# New dependencies only (add to pyproject.toml)
uv add slack-sdk hubspot-api-client notion-client
```

Updated `pyproject.toml` dependencies section (additions only):
```toml
"slack-sdk>=3.41.0",
"hubspot-api-client>=12.0.0",
"notion-client>=3.0.0",
```

## Environment Variables (New)

```bash
# .env additions
SLACK_BOT_TOKEN=xoxb-...          # Slack app bot token
HUBSPOT_ACCESS_TOKEN=pat-...       # HubSpot private app token
NOTION_TOKEN=ntn_...               # Notion internal integration secret
```

## Authentication Summary

| Service | Auth Type | Token Lifetime | Refresh Needed | Setup Complexity |
|---------|-----------|---------------|----------------|-----------------|
| Slack | Bot OAuth Token | Until app uninstalled or token revoked | No (persistent) | Low - create app, install, copy token |
| HubSpot | Private App Access Token | Indefinite (manual rotation) | No | Low - create private app, select scopes, copy token |
| Google Docs | OAuth2 (existing) | Access token: 1hr, auto-refresh | Yes (already handled) | None - already set up |
| Notion | Internal Integration Token | Until revoked | No | Low - create integration, share pages |

Key insight: All three new services use simple bearer tokens stored in `.env`. No OAuth dance required (unlike the existing Google setup). This significantly simplifies the auth story.

## Rate Limit Summary

| Service | Limit | Daily Batch Impact | Mitigation Needed |
|---------|-------|-------------------|-------------------|
| Slack | 50 req/min (Tier 3, internal app) | None - 10-20 channels is trivial | SDK built-in retry |
| HubSpot | 100-190 req/10s | None - small number of daily queries | None |
| Google Docs | 300 read req/min | None - handful of docs per day | None |
| Notion | 3 req/s average | Minimal - add 0.35s delay between calls | Simple sleep or SDK-level pacing |

Notion is the only service where rate limiting is a design consideration, and even then it's manageable with a simple delay for the expected volume (~5-20 pages/day).

## Integration Points with Existing Code

Each new source should follow the existing ingest module pattern:

```
src/ingest/
    calendar.py     # existing - Google Calendar
    drive.py        # existing - Google Drive / Gemini notes
    gmail.py        # existing - Gmail
    transcripts.py  # existing - transcript processing
    normalizer.py   # existing - normalize ingest data
    slack.py        # NEW - Slack channel messages
    hubspot.py      # NEW - HubSpot activity
    google_docs.py  # NEW - Google Docs edited that day
    notion.py       # NEW - Notion page/database changes
```

Each module should return normalized data matching existing Pydantic models in `src/models/`, feeding into `normalizer.py` for cross-source deduplication before synthesis.

## Sources

- [Slack Python SDK (GitHub)](https://github.com/slackapi/python-slack-sdk) - Official SDK repo
- [Slack conversations.history](https://docs.slack.dev/reference/methods/conversations.history/) - Method docs
- [Slack rate limits](https://docs.slack.dev/apis/web-api/rate-limits/) - Tier system
- [Slack rate limit changes for non-Marketplace apps](https://docs.slack.dev/changelog/2025/05/29/rate-limit-changes-for-non-marketplace-apps/) - May 2025 change
- [HubSpot Python SDK (GitHub)](https://github.com/HubSpot/hubspot-api-python) - Official SDK repo
- [hubspot-api-client (PyPI)](https://pypi.org/project/hubspot-api-client/) - Package info
- [HubSpot API usage limits](https://developers.hubspot.com/docs/developer-tooling/platform/usage-guidelines) - Rate limits
- [HubSpot private apps](https://developers.hubspot.com/docs/apps/legacy-apps/private-apps/overview) - Auth setup
- [notion-sdk-py (GitHub)](https://github.com/ramnes/notion-sdk-py) - Official Python SDK
- [notion-client (PyPI)](https://pypi.org/project/notion-client/) - Package info
- [Notion API rate limits](https://developers.notion.com/reference/request-limits) - 3 req/s limit
- [Notion authorization](https://developers.notion.com/docs/create-a-notion-integration) - Integration setup
- [Google Docs API quickstart](https://developers.google.com/workspace/docs/api/quickstart/python) - Python setup
- [Google Drive files.list](https://developers.google.com/workspace/drive/api/reference/rest/v3/files/list) - Query modified files
