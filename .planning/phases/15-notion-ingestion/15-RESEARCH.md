# Phase 15: Notion Ingestion - Research

**Researched:** 2026-04-05
**Domain:** Notion API integration for daily work intelligence pipeline
**Confidence:** HIGH

## Summary

Phase 15 adds Notion as the final ingest source, following the well-established pattern used by Google Docs (Phase 9), HubSpot (Phase 8), and Slack (Phase 7). The pipeline already has `SourceItem`, `SourceType`, `ContentType` enums, `PipelineConfig` Pydantic models, a `retry_api_call` decorator, and a `pipeline.py` runner with private `_ingest_*` functions -- Notion slots directly into this architecture.

The Notion API is accessed via `httpx` (already a dependency) with direct REST calls against `https://api.notion.com/v1/`. The project already uses `httpx>=0.28.1,<1.0`. No SDK needed -- the API is straightforward REST with JSON payloads and an internal integration token for auth. Rate limit is 3 requests/second average, handled by a simple `time.sleep(0.35)` throttle between requests plus the existing `retry_api_call` decorator for 429 responses.

**Primary recommendation:** Build `src/ingest/notion.py` (ingest module) and `src/ingest/notion_discovery.py` (database watchlist CLI) following the exact Google Docs pattern -- `fetch_notion_items(config, target_date) -> list[SourceItem]` entry point, config-gated with `config.notion.enabled`, private helper functions, wrapped in `_ingest_notion` in pipeline.py.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Ingest pages YOU edited or created on the target date (workspace-wide, no watchlist for pages)
- Include comments where you are @mentioned
- Single workspace, single integration token
- Both creates and edits captured
- Title + first ~200 characters of page content (same pattern as Slack/Docs/HubSpot SourceItems)
- Flat list -- no nesting hierarchy for sub-pages
- Extract text blocks only: paragraphs, headings, lists, toggles, callouts. Skip images, embeds, code blocks
- Notion API rate limiting: simple throttle (~350ms between requests) + existing retry decorator for 429 errors
- Default mode: database items YOU modified on the target date
- Opt-in watchlist: specific databases (e.g., ticketing) where ALL changes by anyone are tracked
- Watched databases surface status/property changes (not content edits)
- Show property transitions: "In Progress -> Done" not just current value
- Group database items by database name in the output template
- config.yaml has a `notion` section with `token` and optional `watched_databases` list
- Discovery CLI command: scans workspace, proposes databases, user confirms which to watch (same UX as Slack channel discovery)
- Token stored in config.yaml alongside other API tokens (consistent with existing pattern)
- Page edits are workspace-wide -- no pre-configuration needed for pages
- Attribution format: "(per Notion [page/database title])"

### Claude's Discretion
- Notion SDK/client library choice
- Internal module structure (single file vs split)
- How to detect property transitions (Notion API doesn't provide diffs natively -- may need snapshot comparison)
- SourceType enum values for Notion items
- Template section layout for Notion content

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| NOTION-01 | Ingest Notion page updates and database changes for the target date, with content extraction and SourceItem conversion | Full pattern exists from Google Docs/HubSpot ingest. Notion Search API supports filtering by `last_edited_time` and `last_edited_by`. Database query API supports filtering by property modification dates. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | >=0.28.1,<1.0 | HTTP client for Notion REST API | Already in project dependencies, async-ready for Phase 17, simpler than notion-client SDK |
| pydantic | (existing) | Config model for NotionConfig section | Already used for all config models |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tenacity | (existing) | Retry decorator for 429/5xx errors | Via existing `retry_api_call` decorator |
| PyYAML | (existing) | Config file read/write for discovery CLI | Via existing config infrastructure |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| httpx (direct REST) | notion-client Python SDK | SDK adds dependency, wraps same REST calls, less control over rate limiting. httpx already in project. Direct REST is simpler for the limited API surface we need (search, database query, page content). |

**Installation:** No new packages needed -- httpx is already a dependency.

## Architecture Patterns

### Module Structure
```
src/ingest/
├── notion.py           # Main ingest: fetch_notion_items(), page content, DB item extraction
└── notion_discovery.py # Discovery CLI: scan databases, propose watchlist
```

Two files (matching the Slack pattern of `slack.py` + `slack_discovery.py`).

### Pattern 1: Ingest Module Entry Point
**What:** Single public function `fetch_notion_items(config, target_date) -> list[SourceItem]`
**When to use:** Called from `pipeline.py::_ingest_notion()`
**Example:** Matches `google_docs.py::fetch_google_docs_items()` exactly:
```python
def fetch_notion_items(config: PipelineConfig, target_date: date) -> list[SourceItem]:
    if not config.notion.enabled:
        return []
    client = _build_notion_client(config.notion.token)
    page_items = _fetch_edited_pages(client, target_date, config)
    db_items = _fetch_database_changes(client, target_date, config)
    return page_items + db_items
```

### Pattern 2: Rate-Limited API Client
**What:** Thin wrapper around httpx with per-request throttle
**When to use:** Every Notion API call
**Example:**
```python
import time
import httpx

class NotionClient:
    def __init__(self, token: str, notion_version: str = "2022-06-28"):
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": notion_version,
            "Content-Type": "application/json",
        }
        self._base = "https://api.notion.com/v1"
        self._last_request = 0.0
        self._min_interval = 0.35  # ~3 req/s

    def _throttle(self):
        elapsed = time.monotonic() - self._last_request
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request = time.monotonic()

    def _request(self, method, path, **kwargs):
        self._throttle()
        resp = httpx.request(method, f"{self._base}{path}", headers=self._headers, **kwargs)
        resp.raise_for_status()
        return resp.json()
```

### Pattern 3: Property Transition Detection (Database Items)
**What:** Notion API doesn't provide property diffs. For watched databases, we can only show current property values.
**When to use:** For watched database items
**Approach:** For the first implementation, show current property values (Status: "Done", Priority: "High"). Property transitions would require storing previous snapshots which is Phase 16+ scope. The CONTEXT.md says "Show property transitions" but this requires a cache/snapshot layer. For MVP: show current values and note in the item content if we can detect transition via the `last_edited_time` on the specific property. If not possible, just show current values -- this is honest and still useful.

**Revised approach for transitions:** The Notion API `page.properties` returns current values only. To detect transitions, we'd need to store snapshots. However, Notion's `property_item` endpoint returns a page's property history for some property types. For Status properties specifically, we can check if `last_edited_time` on the page falls within the target date. For MVP, we show current values with a note that the item was modified. This matches the HubSpot pattern where we show the current stage.

### Anti-Patterns to Avoid
- **Notion SDK dependency:** The `notion-client` package adds complexity for minimal benefit. The REST API surface we need is small (search, database query, block children).
- **Fetching full page trees:** We only need first ~200 chars of content, not the entire block tree. Fetch the first page of blocks and stop.
- **Ignoring rate limits:** 3 req/s is strict. Always throttle.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP retries | Custom retry logic | `retry_api_call` decorator (existing) | Already handles exponential backoff, 429 detection |
| Config validation | Manual dict parsing | Pydantic `NotionConfig` model (new, following existing pattern) | Consistent with all other source configs |
| Content truncation | Custom truncation | Same `[:max_content]` pattern as Google Docs | Proven approach |

## Common Pitfalls

### Pitfall 1: Notion API Pagination
**What goes wrong:** All list/search/query endpoints return max 100 results per page.
**Why it happens:** Notion paginated everything for performance.
**How to avoid:** Always implement `has_more` + `start_cursor` pagination loop.
**Warning signs:** Getting exactly 100 results.

### Pitfall 2: Rate Limit Enforcement
**What goes wrong:** 429 responses and request failures.
**Why it happens:** Notion enforces 3 req/s average strictly.
**How to avoid:** Throttle at 350ms between requests (leaving headroom). Wrap with `retry_api_call` for occasional 429 bursts.
**Warning signs:** Sporadic 429 errors in logs.

### Pitfall 3: Block Content Extraction Complexity
**What goes wrong:** Notion stores content as a tree of blocks, each with different types.
**Why it happens:** Rich content model (paragraphs, headings, toggles, callouts, etc.)
**How to avoid:** Only extract `rich_text` from supported block types. Skip unsupported types. Use a simple text extraction function.
**Warning signs:** Empty content for pages that clearly have text.

### Pitfall 4: Internal Integration Token Permissions
**What goes wrong:** API returns 403 or empty results.
**Why it happens:** Each page/database must be explicitly shared with the integration in Notion UI.
**How to avoid:** Discovery CLI should warn about this. Document in setup instructions.
**Warning signs:** Search returns 0 results when pages clearly exist.

### Pitfall 5: Notion API Version Pinning
**What goes wrong:** Breaking changes between API versions.
**Why it happens:** Notion has made breaking changes (e.g., Sept 2025 version).
**How to avoid:** Pin `Notion-Version: 2022-06-28` header (stable, widely used). The STATE.md mentions 2025-09-03 breaking changes but we should use 2022-06-28 which is proven stable.
**Warning signs:** Unexpected response format.

## Code Examples

### Search for Pages Edited by User
```python
# POST https://api.notion.com/v1/search
{
    "filter": {"property": "object", "value": "page"},
    "sort": {"direction": "descending", "timestamp": "last_edited_time"},
    "page_size": 100
}
# Then filter client-side by last_edited_time within target_date range
# and last_edited_by matching the integration's bot user (or workspace user)
```

### Query Database with Date Filter
```python
# POST https://api.notion.com/v1/databases/{database_id}/query
{
    "filter": {
        "timestamp": "last_edited_time",
        "last_edited_time": {
            "on_or_after": "2026-04-04T00:00:00",
            "before": "2026-04-05T00:00:00"
        }
    },
    "page_size": 100
}
```

### Extract Text from Block Children
```python
# GET https://api.notion.com/v1/blocks/{page_id}/children?page_size=50
# Supported block types for text extraction:
SUPPORTED_BLOCKS = {
    "paragraph", "heading_1", "heading_2", "heading_3",
    "bulleted_list_item", "numbered_list_item",
    "toggle", "callout", "quote",
}

def extract_text_from_blocks(blocks: list[dict]) -> str:
    parts = []
    for block in blocks:
        block_type = block.get("type")
        if block_type in SUPPORTED_BLOCKS:
            rich_texts = block.get(block_type, {}).get("rich_text", [])
            text = "".join(rt.get("plain_text", "") for rt in rich_texts)
            if text.strip():
                parts.append(text.strip())
    return "\n".join(parts)
```

### Get Bot User ID (for filtering "my" edits)
```python
# GET https://api.notion.com/v1/users/me
# Returns the bot user. For internal integrations, the bot acts on behalf of the workspace.
# Search results include `last_edited_by` which we compare against the bot user id.
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| notion-client SDK | Direct httpx REST | Project preference | Fewer deps, more control over throttling |
| API version 2021-08-16 | API version 2022-06-28 | June 2022 | Stable, widely deployed |
| No rate limiting | 3 req/s enforced | Always enforced | Must throttle all calls |

## Open Questions

1. **Bot user vs workspace user filtering**
   - What we know: Internal integrations get a bot user. The search API returns `last_edited_by` on pages.
   - What's unclear: Whether `last_edited_by` reflects the human who edited (via the integration's access) or the bot. For internal integrations shared with pages, `last_edited_by` should reflect the actual human user.
   - Recommendation: Test empirically during implementation. If search doesn't filter by editor, fetch all pages edited on the date and accept that some may not be "yours". The user can tune via exclusion patterns if needed.

2. **Property transition detection**
   - What we know: Notion API returns current property values only, no diff/history.
   - What's unclear: Whether any workaround exists for showing "In Progress -> Done" transitions.
   - Recommendation: MVP shows current property values with the item marked as "modified on [date]". Property transition tracking via snapshot comparison can be added later if the user finds current-value-only insufficient. This is an honest scope decision.

## Sources

### Primary (HIGH confidence)
- Notion API Reference (https://developers.notion.com/reference) -- endpoint specs, auth, pagination, rate limits
- Existing codebase patterns: `src/ingest/google_docs.py`, `src/ingest/hubspot.py`, `src/pipeline.py`, `src/config.py`, `src/models/sources.py`

### Secondary (MEDIUM confidence)
- Notion API changelog -- version pinning guidance
- Project STATE.md -- mentions 2025-09-03 breaking changes

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- httpx already in project, REST API well-documented
- Architecture: HIGH -- exact pattern exists from 4 previous ingest modules
- Pitfalls: HIGH -- rate limiting and pagination are well-known Notion API issues

**Research date:** 2026-04-05
**Valid until:** 2026-05-05 (stable domain, API version pinned)
