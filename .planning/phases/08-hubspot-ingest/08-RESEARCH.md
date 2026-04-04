# Phase 8: HubSpot Ingest - Research

**Researched:** 2026-04-04
**Domain:** HubSpot CRM API v3 + Python SDK for deal, contact, ticket, and engagement ingestion
**Confidence:** HIGH

## Summary

HubSpot provides a well-maintained official Python SDK (`hubspot-api-client` v12.x) that wraps the CRM API v3. The SDK supports all object types needed: deals, contacts, tickets, and engagement types (calls, emails, meetings, notes, tasks). The Search API (`do_search`) enables date-filtered queries using `hs_lastmodifieddate` with millisecond timestamps. Deal stage history is available via `propertiesWithHistory=dealstage` on GET endpoints. Associations between objects (deal-contact-company) use the v4 associations API integrated into the SDK.

The project already has HubSpot source types defined in `src/models/sources.py` (HUBSPOT_DEAL, HUBSPOT_CONTACT, HUBSPOT_TICKET, HUBSPOT_ACTIVITY) and content types (STAGE_CHANGE, ACTIVITY, NOTE). Authentication uses a private app access token (env var), following the same pattern as Slack (env var token, no OAuth flow).

**Primary recommendation:** Use `hubspot-api-client` v12.x with private app token auth. Build `src/ingest/hubspot.py` following the existing Slack/Google Docs ingest pattern: config-gated, returns `list[SourceItem]`, wired into `main.py` and `synthesizer.py`.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Ingest deal stage transitions AND key property changes (amount, close date, owner reassignment)
- Include newly created deals on the target date
- Moderate detail per deal: deal name, amount, current stage, owner
- Configurable ownership scope: default to user's deals, with config option to expand to all deals or specific owners/teams
- Ingest contact notes, logged calls, logged emails, and meetings associated with contacts
- Include both auto-logged (email integration) and manually logged activities
- Attribution format: "Note on John Smith (Acme Corp): ..." -- contact name + company
- Same configurable ownership scope as deals (default to my contacts, expandable)
- Prioritize by type: calls and meetings get more detail; emails and tasks get brief mentions
- Tickets: include status changes, newly created, and resolved tickets
- Deduplicate HubSpot meetings/calls against meetings already captured from Google Calendar/transcript sources -- skip the HubSpot version if already present
- Cross-source dedup for emails: if the same email appears from both Gmail and HubSpot, keep only one
- When an activity is linked to multiple objects, attribute to primary object only (no duplication)
- Fixed hierarchy: deal > contact > company -- deals always take priority
- Summary groups HubSpot items by object type (deals section, contacts section, tickets section) rather than chronological

### Claude's Discretion
- Volume cap strategy per activity type (how many items per type before "and X more")
- Exact dedup matching logic for cross-source meetings and emails
- How to handle activities with no object association
- Ticket detail level and formatting

### Deferred Ideas (OUT OF SCOPE)
- None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| HUBSPOT-01 | Ingest deal stage changes and deal activity for the target date | Search API `do_search` with `hs_lastmodifieddate` filter; `propertiesWithHistory=dealstage` for stage transitions; deal properties include dealname, amount, dealstage, closedate, hubspot_owner_id |
| HUBSPOT-02 | Ingest contact activity and notes | Search contacts by `hs_lastmodifieddate`; fetch associated notes/calls/emails/meetings via engagement search with contact associations |
| HUBSPOT-03 | Ingest tickets, calls, emails, meetings, and task activity | Each engagement type has its own search endpoint (`/crm/v3/objects/{type}/search`); tickets searched similarly to deals |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| hubspot-api-client | 12.x | Official HubSpot API v3 Python SDK | Official, actively maintained, wraps all CRM endpoints |
| pydantic | 2.x | Data validation (already in project) | Existing project dependency |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-dateutil | 2.x | Timestamp conversion (already in project) | Converting dates to millisecond timestamps for Search API |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| hubspot-api-client | Raw httpx requests | SDK handles auth, pagination, retry; raw HTTP would require manual implementation |
| hubspot-api-client | hubspot3 (community) | Deprecated, v2 API only, unmaintained |

**Installation:**
```bash
pip install hubspot-api-client>=12.0.0
```

## Architecture Patterns

### Recommended Module Structure
```
src/
├── ingest/
│   ├── hubspot.py          # Main ingest module (deals, contacts, tickets, engagements)
│   └── ...existing modules
```

Single module (`hubspot.py`) rather than splitting per-object-type. Rationale: the Slack module handles channels + DMs + threads in one file; HubSpot similarly groups related CRM objects in one module with internal helper functions per object type.

### Pattern 1: Private App Token Auth
**What:** HubSpot private apps generate a single access token with scoped permissions. No OAuth refresh flow needed.
**When to use:** Always for this project -- single-user tool, not a marketplace app.
**Example:**
```python
import os
from hubspot import HubSpot

def build_hubspot_client(token: str | None = None) -> HubSpot:
    token = token or os.environ.get("HUBSPOT_ACCESS_TOKEN")
    if not token:
        raise ValueError("No HubSpot token. Set HUBSPOT_ACCESS_TOKEN env var.")
    return HubSpot(access_token=token)
```

### Pattern 2: Search API with Date Filtering
**What:** Use `do_search` with `hs_lastmodifieddate` filter to find objects modified on the target date.
**When to use:** For deals, contacts, tickets -- any CRM object with date-based filtering.
**Example:**
```python
from hubspot.crm.deals import PublicObjectSearchRequest

def search_deals_for_date(client, start_ms, end_ms, properties, owner_id=None):
    filters = [
        {"propertyName": "hs_lastmodifieddate", "operator": "BETWEEN",
         "value": str(start_ms), "highValue": str(end_ms)}
    ]
    if owner_id:
        filters.append({"propertyName": "hubspot_owner_id", "operator": "EQ",
                        "value": owner_id})
    request = PublicObjectSearchRequest(
        filter_groups=[{"filters": filters}],
        properties=properties,
        sorts=[{"propertyName": "hs_lastmodifieddate", "direction": "DESCENDING"}],
        limit=100,
    )
    return client.crm.deals.search_api.do_search(
        public_object_search_request=request
    )
```

### Pattern 3: Deal Stage History via propertiesWithHistory
**What:** GET individual deal with `propertiesWithHistory=dealstage` to get timestamped stage transitions.
**When to use:** After identifying deals modified on target date, fetch stage history for each.
**Example:**
```python
deal = client.crm.deals.basic_api.get_by_id(
    deal_id=deal_id,
    properties=["dealname", "amount", "dealstage", "closedate", "hubspot_owner_id"],
    properties_with_history=["dealstage"],
)
# deal.properties_with_history["dealstage"] contains list of
# {"value": "stage_id", "timestamp": "2026-04-03T...", "sourceType": "..."}
```

### Pattern 4: Associations for Object Relationships
**What:** Use associations parameter on search/get to include related objects.
**When to use:** Getting company name for a contact, or contact/company for a deal.
**Example:**
```python
# When fetching contacts, include company associations
response = client.crm.contacts.basic_api.get_page(
    limit=100,
    properties=["firstname", "lastname", "email", "company"],
    associations=["companies"],
)
```

### Pattern 5: Engagement Search Per Type
**What:** Each engagement type (notes, calls, emails, meetings, tasks) has its own search endpoint.
**When to use:** Fetching activities for the target date.
**Example:**
```python
# Search notes modified on target date
request = PublicObjectSearchRequest(
    filter_groups=[{"filters": [
        {"propertyName": "hs_lastmodifieddate", "operator": "BETWEEN",
         "value": str(start_ms), "highValue": str(end_ms)}
    ]}],
    properties=["hs_note_body", "hs_timestamp", "hubspot_owner_id"],
)
notes = client.crm.objects.notes.search_api.do_search(
    public_object_search_request=request
)
```

### Anti-Patterns to Avoid
- **Fetching ALL objects then filtering in Python:** Use Search API server-side filtering. HubSpot has rate limits; pulling everything wastes quota.
- **Using deprecated hapikey auth:** Removed in SDK v5.1.0+. Use private app access token.
- **Ignoring pagination:** Search API returns max 100 (soon 200) results per page. Must handle `after` cursor for large result sets.
- **Making individual GET calls per engagement:** Use search with date filter instead of listing all engagements and filtering client-side.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CRM API wrapper | Custom HTTP client | hubspot-api-client SDK | Handles auth, pagination, retry, model classes |
| Rate limiting | Manual retry/backoff | SDK built-in retry (or simple sleep on 429) | SDK handles standard rate limit responses |
| Timestamp conversion | Custom date math | `int(datetime.timestamp() * 1000)` | HubSpot uses millisecond Unix timestamps; standard Python |
| Pipeline stage name lookup | Hardcoded stage names | `client.crm.pipelines.pipelines_api.get_all("deals")` | Stage IDs are portal-specific; must look up names dynamically |

**Key insight:** The SDK provides typed model classes for all request/response objects. Use `PublicObjectSearchRequest` rather than building raw dicts -- it catches errors at construction time.

## Common Pitfalls

### Pitfall 1: Millisecond vs Second Timestamps
**What goes wrong:** Search API requires millisecond timestamps but Python `datetime.timestamp()` returns seconds.
**Why it happens:** HubSpot uses Java-style millisecond epoch timestamps.
**How to avoid:** Always multiply by 1000: `int(dt.timestamp() * 1000)`.
**Warning signs:** Search returns 0 results when you know data exists.

### Pitfall 2: Search API 10,000 Result Hard Limit
**What goes wrong:** Search API has a hard cap of 10,000 total results regardless of pagination.
**Why it happens:** HubSpot search is powered by Elasticsearch with a max_result_window.
**How to avoid:** For this project (single user, daily window), unlikely to hit. But if needed, narrow date window or add owner filter.
**Warning signs:** `total` in response is exactly 10,000.

### Pitfall 3: Stage IDs vs Stage Names
**What goes wrong:** Deal stage values are internal IDs (e.g., "qualifiedtobuy"), not human-readable names.
**Why it happens:** Stage IDs are stable identifiers; labels can be customized per portal.
**How to avoid:** Fetch pipeline stages at startup, build ID-to-name lookup map.
**Warning signs:** Summary shows stage IDs instead of names like "Qualified to Buy".

### Pitfall 4: Owner ID Resolution
**What goes wrong:** `hubspot_owner_id` is a numeric ID, not a name.
**Why it happens:** Owner objects are separate from contacts/users in HubSpot.
**How to avoid:** Use `client.crm.owners.owners_api.get_page()` to build owner ID-to-name map.
**Warning signs:** Summary shows owner IDs instead of names.

### Pitfall 5: Association Depth
**What goes wrong:** Getting a contact's company requires an extra API call after fetching association IDs.
**Why it happens:** Associations return object IDs, not full objects.
**How to avoid:** Batch-fetch associated companies after collecting all company IDs from contacts.
**Warning signs:** Missing company names in contact attribution.

### Pitfall 6: Engagement Associations Not in Search Results
**What goes wrong:** Search API for engagements (notes, calls, etc.) does not include associations by default.
**Why it happens:** Search returns properties only; associations require separate fetch or using `associations` param on individual GET.
**How to avoid:** After searching engagements, use batch API or individual GET with `associations=["contacts", "deals"]` to link activities to objects.
**Warning signs:** Activities appear without contact/deal attribution.

## Code Examples

### Date Range to Millisecond Timestamps
```python
from datetime import date, datetime, timezone

def date_to_ms_range(target: date, tz_name: str = "America/New_York"):
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(tz_name)
    start = datetime(target.year, target.month, target.day, tzinfo=tz)
    end = start + timedelta(days=1)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)
```

### Fetch Pipeline Stage Names
```python
def build_stage_map(client) -> dict[str, str]:
    """Build mapping of stage ID -> stage label for all deal pipelines."""
    stage_map = {}
    pipelines = client.crm.pipelines.pipelines_api.get_all("deals")
    for pipeline in pipelines.results:
        for stage in pipeline.stages:
            stage_map[stage.id] = stage.label
    return stage_map
```

### Fetch Owner Names
```python
def build_owner_map(client) -> dict[str, str]:
    """Build mapping of owner ID -> display name."""
    owner_map = {}
    owners = client.crm.owners.owners_api.get_page(limit=100)
    for owner in owners.results:
        name = f"{owner.first_name} {owner.last_name}".strip()
        owner_map[str(owner.id)] = name or owner.email
    return owner_map
```

### Paginated Search Helper
```python
def search_all(search_fn, request, max_results=500):
    """Paginate through search results up to max_results."""
    results = []
    after = None
    while len(results) < max_results:
        if after:
            request.after = after
        response = search_fn(public_object_search_request=request)
        results.extend(response.results)
        if not response.paging or not response.paging.next:
            break
        after = response.paging.next.after
    return results[:max_results]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| hapikey (API key) auth | Private app access token | SDK v5.1.0 (2022) | Must use access token |
| Engagements v1 API | CRM objects v3 per-type endpoints | 2023 | Notes, calls, emails, meetings, tasks each have own endpoint |
| Associations v3 | Associations v4 | 2024 | Labeled associations, batch operations |
| 100 results per search page | 200 results per page (announced) | 2025 | Higher throughput per request |

**Deprecated/outdated:**
- `hapikey` authentication: removed from SDK
- Engagements v1 combined endpoint: still works but v3 per-type is recommended
- `hubspot3` community package: unmaintained, v2 API only

## Open Questions

1. **User's HubSpot subscription tier**
   - What we know: API access requires paid HubSpot (Starter+). Rate limits vary by tier.
   - What's unclear: Which tier the user has (affects rate limits: 190 req/10s for all paid tiers).
   - Recommendation: Code defensively with rate limit handling. Private app access works on all paid tiers.

2. **Exact dedup matching for cross-source meetings**
   - What we know: HubSpot meetings have `hs_meeting_title` and `hs_meeting_start_time`. Calendar events have title and start time.
   - What's unclear: How reliably titles match between HubSpot and Google Calendar.
   - Recommendation: Match on start time (within 5 min window) + fuzzy title match. If uncertain, keep both but note potential duplicate.

3. **Email dedup between Gmail and HubSpot**
   - What we know: HubSpot stores email message IDs. Gmail has its own message IDs.
   - What's unclear: Whether HubSpot exposes the original Gmail message ID.
   - Recommendation: Match on timestamp + subject + sender as a practical approach.

## Sources

### Primary (HIGH confidence)
- HubSpot developer docs: CRM API v3 deals, contacts, tickets, engagements, pipelines, associations v4
- PyPI hubspot-api-client v12.0.0 package metadata and README
- HubSpot/hubspot-api-python GitHub repository

### Secondary (MEDIUM confidence)
- HubSpot Community forums: deal stage history access, search API date filtering, engagement associations
- HubSpot developer changelog: rate limit increases, search API improvements

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Official SDK, well-documented, actively maintained
- Architecture: HIGH - Follows established project ingest patterns, SDK provides clear abstractions
- Pitfalls: HIGH - Well-documented community issues, consistent patterns across forums

**Research date:** 2026-04-04
**Valid until:** 2026-05-04 (stable SDK, infrequent breaking changes)
