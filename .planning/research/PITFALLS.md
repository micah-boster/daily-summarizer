# Domain Pitfalls: v1.5 Expanded Ingest

**Domain:** Work intelligence - multi-source API integrations
**Researched:** 2026-04-03

## Critical Pitfalls

Mistakes that cause rewrites or major issues.

### Pitfall 1: Slack Rate Limit Misclassification
**What goes wrong:** Treating this as a commercially distributed app rather than an internal app, leading to either (a) unnecessary Marketplace submission or (b) panic about the 1 req/min limit.
**Why it happens:** Slack's May 2025 rate limit changes generated a lot of alarm. The 1 req/min limit is for commercially distributed non-Marketplace apps, NOT internal apps.
**Consequences:** Over-engineering rate limiting, or incorrectly submitting to Marketplace.
**Prevention:** Build as an internal app installed only to your workspace. Verify the app is NOT set to "distribute" in Slack app settings. Internal apps get Tier 3 limits (50 req/min for conversations.history).
**Detection:** If you see rate limit errors on a 10-channel daily batch, your app is misconfigured.

### Pitfall 2: Cross-Source Deduplication Done Wrong
**What goes wrong:** Building dedup as string matching (e.g., "meeting title appears in Slack message") instead of feeding overlapping context to synthesis and letting Claude handle it.
**Why it happens:** Engineering instinct to solve dedup algorithmically. But work topics don't have clean identifiers across sources.
**Consequences:** Either false positives (related but distinct items merged) or false negatives (duplicates not caught). Custom dedup logic becomes a maintenance burden.
**Prevention:** Normalize timestamps and basic metadata. Group items by time proximity. Let synthesis prompts explicitly instruct: "These items may describe the same event from different sources. Synthesize, don't duplicate." The LLM is better at semantic dedup than regex.
**Detection:** Output contains obvious duplicates, or distinct items are incorrectly merged in synthesis.

### Pitfall 3: Notion Block Extraction Complexity Explosion
**What goes wrong:** Building a comprehensive Notion block-to-text converter that handles every block type (50+ types including synced blocks, databases inline, embeds, columns, etc.).
**Why it happens:** Notion's block model is deeply nested and has many types. Completionist instinct.
**Consequences:** Large, fragile block parser. Most block types are irrelevant to daily synthesis.
**Prevention:** Handle only: paragraph, heading_1/2/3, bulleted_list_item, numbered_list_item, to_do, toggle (text only), and code. Skip everything else with a `[unsupported block]` placeholder. Iterate if specific types matter.
**Detection:** Block parser is >200 lines. You're handling embed blocks.

### Pitfall 4: Google OAuth Scope Change Triggers Re-auth
**What goes wrong:** Adding a new OAuth scope to the SCOPES list in `google_oauth.py` forces re-authentication for the user, invalidating the existing token.
**Why it happens:** Google OAuth tokens are scoped. If you add scopes, the old token doesn't cover them.
**Consequences:** Pipeline breaks until user re-authenticates interactively.
**Prevention:** The existing `drive.readonly` scope already covers Google Docs reads. Do NOT add `documents.readonly` or any other scope. Verify the existing scope works for Docs content retrieval before changing anything.
**Detection:** `google_oauth.py` SCOPES list has changed from v1.0.

## Moderate Pitfalls

### Pitfall 5: Slack Channel ID vs Name Confusion
**What goes wrong:** Config stores channel names (#general) but API requires channel IDs (C01234ABC).
**Prevention:** Channel discovery step resolves names to IDs. Store IDs in config, display names in output. Use `conversations.list` to build the mapping.

### Pitfall 6: HubSpot API Version Churn
**What goes wrong:** HubSpot frequently updates their API. The Python SDK has had breaking changes between major versions (the jump from hapikey to access tokens, V2 to V3 API).
**Prevention:** Pin to `hubspot-api-client>=12.0.0,<13.0.0` to avoid surprise breaking changes. The V3 API is the current stable target.

### Pitfall 7: Notion Page Sharing Requirement
**What goes wrong:** Integration can't access any pages because pages must be explicitly shared with the integration in Notion's UI.
**Prevention:** Document the setup step clearly. Build a health-check command that verifies the integration can access expected pages. Consider using `notion.search()` to list accessible pages as a diagnostic.

### Pitfall 8: Slack Thread Messages Not in Channel History
**What goes wrong:** `conversations.history` returns only top-level messages. Thread replies require separate `conversations.replies` calls per thread.
**Prevention:** Check if messages have `thread_ts` and `reply_count > 0`. Fetch threads for substantive conversations (e.g., reply_count >= 3). Budget additional API calls accordingly.

### Pitfall 9: HubSpot "Activity" Is Spread Across Multiple APIs
**What goes wrong:** Expecting a single "activity feed" endpoint. HubSpot activity is split across engagements (calls, emails, meetings, notes), deal property changes, and timeline events.
**Prevention:** Start with engagements API (`crm.objects.notes`, `crm.objects.calls`) and deal search by modified date. Don't try to build a unified activity feed on day one.

## Minor Pitfalls

### Pitfall 10: Timezone Handling Across Sources
**What goes wrong:** Slack uses Unix timestamps (UTC), HubSpot uses millisecond timestamps (UTC), Google uses RFC 3339, Notion uses ISO 8601. Mixing them creates off-by-one-day bugs.
**Prevention:** Normalize all timestamps to UTC at ingest. Use `datetime.timezone.utc` consistently. Define "target day" as midnight-to-midnight UTC (or local, but be consistent).

### Pitfall 11: Slack User ID Resolution
**What goes wrong:** Slack messages contain user IDs (`U01234ABC`) not display names. Output reads "U01234ABC said..." instead of "John said...".
**Prevention:** Build a user cache with `users.info` or `users.list` at start of batch. Cache for the session (user names don't change intra-day).

### Pitfall 12: Large Google Docs Content
**What goes wrong:** A 50-page Google Doc's full content is extracted and sent to synthesis, blowing up token counts.
**Prevention:** Truncate or summarize docs over a threshold (e.g., first 2000 words). The daily summary cares about "what was worked on" not the full document.

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Slack integration | Thread replies missing from history (#8) | Budget conversations.replies calls for threads with 3+ replies |
| Slack integration | Rate limit confusion (#1) | Verify internal app status, not commercial distribution |
| HubSpot integration | Activity spread across APIs (#9) | Start with notes + deal search, expand incrementally |
| Google Docs integration | OAuth scope change (#4) | DO NOT change scopes; existing drive.readonly works |
| Notion integration | Block extraction complexity (#3) | Handle 6-7 text block types only, skip rest |
| Notion integration | Page sharing forgotten (#7) | Build diagnostic/health-check command |
| Cross-source dedup | Over-engineering dedup (#2) | Let synthesis handle semantic dedup, normalize timestamps only |
| All sources | Timezone bugs (#10) | UTC everywhere, explicit day boundary definition |
