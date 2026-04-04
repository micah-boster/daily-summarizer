# Phase 7: Slack Ingest + Synthesis Integration - Research

**Researched:** 2026-04-04
**Domain:** Slack API ingestion, message filtering, thread expansion, discovery mode, synthesis prompt integration
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Bot messages excluded by default, with a configurable allowlist for specific bots (e.g., keep Salesforce alerts, skip Giphy)
- Aggressive pre-synthesis filtering: skip join/leave events, channel topic changes, reactions-only messages, single-word responses ('ok', 'thanks', 'lol'), link-only messages with no commentary, and edited-away messages
- Time window: since-last-run tracking per channel (store last-ingested timestamp, only grab new messages since then)
- Thread expansion threshold: 3+ replies AND 2+ distinct participants (both conditions must be met)
- Thresholds are user-configurable in config
- Threads below threshold: show parent message with reply count hint (e.g., "(5 replies)")
- Threads above threshold: expanded representation
- Both 1:1 and group DMs eligible for ingestion
- Discovery-assisted opt-in: no DMs ingested by default; discovery mode suggests active DMs based on frequency, user confirms which to include
- Attribution names the person: "(per Slack DM with Sarah Chen)" style
- Interactive prompt: step through each proposed channel/DM one at a time
- Each proposal shows activity stats (message count, participant count) + 2-3 recent topic keywords
- Re-runnable anytime: user can re-run to add new channels/remove old ones, showing what's already configured vs new suggestions
- Periodic auto-suggest: discovery periodically flags new active channels the user isn't tracking yet

### Claude's Discretion
- Volume cap strategy per channel (how to handle high-volume channels)
- Thread expansion display format (summarized vs key messages quoted)
- DM filtering level relative to channel filtering
- Discovery flow structure (channels and DMs separate or combined)
- Technical implementation of periodic auto-suggest timing

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SLACK-01 | Ingest messages from curated list of Slack channels (user-configurable) | slack_sdk WebClient + conversations_history with oldest/latest params; config.yaml channel list; since-last-run tracking via JSON state file |
| SLACK-02 | Expand active threads above configurable threshold | conversations_replies for threads meeting 3+ replies AND 2+ participants; reply_count and reply_users_count from parent message metadata |
| SLACK-03 | Ingest DMs and group DMs | Same conversations_history method works for im/mpim channel types; im:history + mpim:history scopes; discovery-assisted opt-in |
| SLACK-04 | Discovery mode proposes active channels, user confirms/rejects | users_conversations lists all channels the user is in; activity stats from conversations_history; interactive CLI prompt; JSON config persistence |
| SYNTH-05 | Source-aware synthesis prompts handle Slack alongside meetings | Extend SYNTHESIS_PROMPT to accept SourceItem blocks alongside MeetingExtraction; format Slack items with channel/DM attribution |
| SYNTH-07 | Source attribution in all output | SourceItem.display_context + attribution_text() already support "(per Slack #channel)" format; wire through synthesis prompt and output template |
</phase_requirements>

## Summary

Phase 7 adds Slack message ingestion to the existing meeting-based daily summary pipeline. The core technical work involves: (1) a new `src/ingest/slack.py` module using the official `slack_sdk` Python library to pull messages from configured channels and DMs via the Conversations API, (2) a message filtering layer that aggressively removes noise before synthesis, (3) thread expansion logic that fetches replies for active discussions, (4) a discovery CLI command that proposes channels/DMs for the user to opt into, and (5) updates to the synthesis prompt and pipeline to merge Slack SourceItems alongside meeting MeetingExtractions.

The project already has the `SourceItem` model (Phase 6) with `SourceType.SLACK_MESSAGE` and `SourceType.SLACK_THREAD` enum values, the `SynthesisSource` Protocol, and attribution infrastructure (`display_context`, `attribution_text()`). The main integration challenge is adapting the synthesis stage -- currently hardcoded for `MeetingExtraction` objects -- to also accept `SourceItem` objects from Slack. The Slack SDK is mature, well-documented, and has built-in rate-limit retry handling.

**Primary recommendation:** Use `slack_sdk>=3.33.0` WebClient with bot token auth. Follow the existing ingest pattern (calendar.py) for module structure. Store Slack state (last-ingested timestamps, channel config) in a JSON file under `config/`. Extend `synthesize_daily()` to accept both MeetingExtractions and SourceItems.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| slack_sdk | >=3.33.0 | Slack Web API client | Official Slack Python SDK; includes WebClient, built-in retry handlers, cursor pagination helpers |
| pydantic | >=2.12.5 | Data modeling | Already in project; SourceItem model ready for Slack data |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| slack_sdk.http_retry | (included) | Rate limit handling | Always -- attach RateLimitErrorRetryHandler to WebClient |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| slack_sdk WebClient | Raw httpx calls to Slack API | Would lose cursor pagination helpers, retry handlers, type hints; no benefit since slack_sdk is lightweight |
| Bot token (xoxb-) | User token (xoxp-) | User tokens have broader access but are less secure, harder to manage; bot tokens are the Slack-recommended approach for internal apps |

**Installation:**
```bash
uv add "slack_sdk>=3.33.0"
```

## Architecture Patterns

### Recommended Project Structure
```
src/
  ingest/
    slack.py            # Core Slack API client + message fetching
    slack_filter.py     # Message filtering (noise removal, bot filtering)
    slack_discovery.py  # Channel/DM discovery mode
  config.py             # Extended with Slack config loading
  main.py               # Extended with Slack ingest step + discovery subcommand
config/
  config.yaml           # Extended with slack section
  slack_state.json      # Per-channel last-ingested timestamps + channel list
```

### Pattern 1: Slack Client Initialization with Rate Limit Handling
**What:** Initialize WebClient with bot token and built-in retry handler
**When to use:** Every Slack API call
**Example:**
```python
# Source: https://slack.dev/python-slack-sdk/web/index.html
from slack_sdk.web import WebClient
from slack_sdk.http_retry.builtin_handlers import RateLimitErrorRetryHandler

def build_slack_client(token: str) -> WebClient:
    client = WebClient(token=token)
    rate_limit_handler = RateLimitErrorRetryHandler(max_retry_count=2)
    client.retry_handlers.append(rate_limit_handler)
    return client
```

### Pattern 2: Cursor-Paginated Message Fetching with Time Window
**What:** Fetch messages since last run using oldest/latest params with cursor pagination
**When to use:** Channel and DM history retrieval
**Example:**
```python
# Source: https://docs.slack.dev/reference/methods/conversations.history/
def fetch_channel_messages(
    client: WebClient,
    channel_id: str,
    oldest: str,  # Unix timestamp string
    latest: str,
) -> list[dict]:
    messages: list[dict] = []
    cursor = None
    while True:
        response = client.conversations_history(
            channel=channel_id,
            oldest=oldest,
            latest=latest,
            limit=200,
            cursor=cursor,
        )
        messages.extend(response["messages"])
        cursor = response.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return messages
```

### Pattern 3: Thread Expansion with Threshold Check
**What:** Check parent message metadata for reply_count and reply_users_count before fetching replies
**When to use:** For every message that has reply_count > 0
**Example:**
```python
# Source: https://docs.slack.dev/reference/methods/conversations.replies/
def should_expand_thread(msg: dict, config: dict) -> bool:
    reply_count = msg.get("reply_count", 0)
    reply_users_count = msg.get("reply_users_count", 0)
    min_replies = config.get("slack", {}).get("thread_min_replies", 3)
    min_participants = config.get("slack", {}).get("thread_min_participants", 2)
    return reply_count >= min_replies and reply_users_count >= min_participants

def fetch_thread_replies(
    client: WebClient,
    channel_id: str,
    thread_ts: str,
) -> list[dict]:
    replies: list[dict] = []
    cursor = None
    while True:
        response = client.conversations_replies(
            channel=channel_id,
            ts=thread_ts,
            limit=200,
            cursor=cursor,
        )
        # First message is the parent; skip it
        batch = response["messages"]
        if not replies:
            batch = batch[1:]  # skip parent on first page
        replies.extend(batch)
        cursor = response.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return replies
```

### Pattern 4: Message-to-SourceItem Conversion
**What:** Convert raw Slack message dicts to SourceItem models with proper attribution
**When to use:** After filtering, before synthesis
**Example:**
```python
from src.models.sources import ContentType, SourceItem, SourceType

def message_to_source_item(
    msg: dict,
    channel_name: str,
    channel_id: str,
    user_map: dict[str, str],  # user_id -> display_name
    is_dm: bool = False,
    dm_partner: str | None = None,
) -> SourceItem:
    user_id = msg.get("user", "")
    user_name = user_map.get(user_id, user_id)
    ts = msg["ts"]

    if is_dm:
        display_ctx = f"Slack DM with {dm_partner}"
    else:
        display_ctx = f"Slack #{channel_name}"

    return SourceItem(
        id=f"slack_{channel_id}_{ts}",
        source_type=SourceType.SLACK_MESSAGE,
        content_type=ContentType.MESSAGE,
        title=f"Message from {user_name}",
        timestamp=datetime.fromtimestamp(float(ts), tz=timezone.utc),
        content=msg.get("text", ""),
        participants=[user_name],
        source_url=f"https://slack.com/archives/{channel_id}/p{ts.replace('.', '')}",
        display_context=display_ctx,
        context={"channel_id": channel_id, "thread_ts": msg.get("thread_ts")},
        raw_data=msg,
    )
```

### Pattern 5: Discovery Mode with Interactive Prompts
**What:** List user's channels via users_conversations, compute activity stats, prompt for each
**When to use:** `python -m src.main discover-slack` subcommand
**Example flow:**
```python
# 1. List all channels user is in
response = client.users_conversations(types="public_channel,private_channel,mpim,im", limit=200)

# 2. For each channel not already configured, fetch recent messages for stats
for channel in unconfigured_channels:
    history = client.conversations_history(channel=channel["id"], limit=100)
    msg_count = len(history["messages"])
    participants = set(m.get("user") for m in history["messages"])
    # Extract topic keywords via simple frequency analysis
    # Present to user: "Add #design-team? (47 messages, 8 participants, topics: redesign, sprint, figma)"
```

### Anti-Patterns to Avoid
- **Fetching ALL history on first run:** Use a sensible lookback window (e.g., 24 hours or configurable) for the initial run, not the entire channel history.
- **One API call per message for user lookup:** Cache user_id -> display_name mapping in memory; fetch once with users_info per unknown user, not per message.
- **Filtering after synthesis:** Apply aggressive filtering BEFORE sending to Claude. Token waste and diluted output quality otherwise.
- **Storing bot token in config.yaml:** Use SLACK_BOT_TOKEN environment variable (like existing SLACK_WEBHOOK_URL pattern).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Rate limit backoff | Custom sleep/retry logic | `RateLimitErrorRetryHandler` from slack_sdk | Reads Retry-After header correctly, configurable max retries |
| Cursor pagination | Manual cursor tracking | slack_sdk cursor parameter in each method | Methods return response_metadata.next_cursor natively |
| Message timestamp parsing | Custom float-to-datetime | `datetime.fromtimestamp(float(ts), tz=timezone.utc)` | Slack timestamps are Unix epoch floats with microsecond precision |
| Slack deep link URLs | String concatenation guessing | `https://slack.com/archives/{channel_id}/p{ts_no_dot}` | Standard Slack permalink format; remove the dot from ts |
| User display name resolution | Parsing message text for @mentions | `users_info` API + in-memory cache | Messages contain user IDs, not names; must resolve via API |

**Key insight:** The slack_sdk handles the two hardest parts (pagination and rate limiting) out of the box. The custom work is in filtering logic and synthesis integration, not API plumbing.

## Common Pitfalls

### Pitfall 1: Bot Token Scope Gaps
**What goes wrong:** The Slack app is created but missing required scopes, causing silent failures on DM or private channel access.
**Why it happens:** Scopes must be added before the app is installed; adding scopes after requires reinstallation.
**How to avoid:** Document the complete scope list upfront and verify in app setup:
- `channels:history` (public channel messages)
- `channels:read` (public channel metadata)
- `groups:history` (private channel messages)
- `groups:read` (private channel metadata)
- `im:history` (1:1 DM messages)
- `im:read` (1:1 DM metadata/listing)
- `mpim:history` (group DM messages)
- `mpim:read` (group DM metadata/listing)
- `users:read` (user display names)
**Warning signs:** `missing_scope` error in API response; empty message lists from channels the bot should have access to.

### Pitfall 2: Slack Timestamps Are Strings, Not Floats
**What goes wrong:** Using `oldest=1234567890.0` (float) instead of `oldest="1234567890.000000"` (string) causes the API to return unexpected results or errors.
**Why it happens:** Slack timestamps look like floats but are string identifiers with microsecond precision.
**How to avoid:** Always pass timestamps as strings to API methods. Store them as strings in state files.
**Warning signs:** Missing messages at time boundaries; "invalid_oldest" errors.

### Pitfall 3: Thread Parent Message Duplication
**What goes wrong:** A threaded message appears both in conversations_history (as the parent) and in conversations_replies (as the first reply). This leads to duplicate content in synthesis.
**Why it happens:** conversations_replies returns the parent message as the first element of the messages array.
**How to avoid:** When fetching thread replies, skip the first message (the parent) since you already have it from conversations_history. Or deduplicate by ts.
**Warning signs:** Same message text appearing twice in synthesis output.

### Pitfall 4: High-Volume Channel Token Explosion
**What goes wrong:** A channel like #general with 500+ messages/day generates enormous prompt context, burning tokens and diluting synthesis quality.
**Why it happens:** No per-channel volume cap; all messages sent to synthesis regardless of volume.
**How to avoid:** Implement a volume cap strategy (recommendation: configurable max messages per channel, default 100; for channels exceeding the cap, take a sample or summarize before synthesis).
**Warning signs:** Synthesis prompt exceeding model context window; Claude output becoming vague/generic due to too much input.

### Pitfall 5: Rate Limit Changes for Non-Marketplace Apps (March 2026)
**What goes wrong:** An internal custom app suddenly hits severe rate limits (1 req/min, 15 messages/request) because Slack reclassified it.
**Why it happens:** As of March 3, 2026, Slack applies restrictive limits to non-Marketplace apps that are "commercially distributed outside the Slack Marketplace." Internal customer-built applications are NOT affected and retain Tier 3 limits (50+ req/min).
**How to avoid:** Ensure the app is registered as an internal/custom app, NOT distributed externally. The STATE.md blocker note confirms this is already tracked.
**Warning signs:** HTTP 429 errors with very long Retry-After values; limit parameter capped at 15.

### Pitfall 6: Discovery Mode Overwhelming the User
**What goes wrong:** User runs discovery and gets prompted for 100+ channels one at a time.
**Why it happens:** Large workspaces have many channels; showing all of them is noisy.
**How to avoid:** Pre-filter discovery candidates: only propose channels with recent activity (e.g., messages in last 7 days), minimum message count, and where the user has actually participated (not just joined). Show already-configured channels first for review before new suggestions.
**Warning signs:** User abandoning discovery mode; configuring zero channels because the flow is tedious.

## Code Examples

### Slack Config Schema (config.yaml extension)
```yaml
# Source: Project convention (extending existing config.yaml pattern)
slack:
  enabled: true
  channels: []  # Populated by discovery mode, e.g., ["C01ABCDEF", "C02GHIJKL"]
  dms: []       # Populated by discovery mode, e.g., ["D01MNOPQR"]
  thread_min_replies: 3
  thread_min_participants: 2
  max_messages_per_channel: 100
  bot_allowlist: []  # Bot user IDs whose messages to keep
  filter:
    skip_subtypes:
      - "channel_join"
      - "channel_leave"
      - "channel_topic"
      - "channel_purpose"
      - "channel_name"
    skip_patterns:
      - "^(ok|thanks|lol|yes|no|sure|yep|nope|haha|nice)$"
```

### State File Schema (slack_state.json)
```json
{
  "channels": {
    "C01ABCDEF": {
      "name": "general",
      "last_ts": "1712188800.000000",
      "last_run": "2026-04-04T00:00:00Z"
    }
  },
  "dms": {
    "D01MNOPQR": {
      "partner_name": "Sarah Chen",
      "last_ts": "1712188800.000000",
      "last_run": "2026-04-04T00:00:00Z"
    }
  }
}
```

### Message Filtering Function
```python
import re

NOISE_SUBTYPES = {
    "channel_join", "channel_leave", "channel_topic",
    "channel_purpose", "channel_name", "bot_add", "bot_remove",
}
TRIVIAL_PATTERN = re.compile(
    r"^(ok|thanks|lol|yes|no|sure|yep|nope|haha|nice|ty|\+1|:[\w+-]+:)$",
    re.IGNORECASE,
)
URL_ONLY_PATTERN = re.compile(r"^<https?://[^>]+>$")

def should_keep_message(
    msg: dict,
    bot_allowlist: list[str],
) -> bool:
    # Skip message subtypes (join/leave/topic changes)
    if msg.get("subtype") in NOISE_SUBTYPES:
        return False
    # Skip bot messages unless allowlisted
    if msg.get("bot_id") and msg.get("bot_id") not in bot_allowlist:
        return False
    if msg.get("subtype") == "bot_message" and msg.get("bot_id") not in bot_allowlist:
        return False
    # Skip edited-away messages (tombstones)
    if msg.get("subtype") == "tombstone":
        return False
    # Skip trivial single-word responses
    text = msg.get("text", "").strip()
    if TRIVIAL_PATTERN.match(text):
        return False
    # Skip link-only messages with no commentary
    if URL_ONLY_PATTERN.match(text):
        return False
    # Skip empty messages (reactions-only have no text)
    if not text and not msg.get("files") and not msg.get("attachments"):
        return False
    return True
```

### Synthesis Prompt Extension for Multi-Source
```python
# Extension to existing SYNTHESIS_PROMPT in synthesizer.py
MULTI_SOURCE_SYNTHESIS_PROMPT = """You are producing a daily intelligence brief. Be concise. Every word must earn its place.

Date: {date}
Number of meetings with transcripts: {transcript_count}
Number of Slack sources: {slack_source_count}

{extractions_text}

{slack_items_text}

{priority_context}

Produce a daily summary with these exact sections:
...
[Same rules as current SYNTHESIS_PROMPT, plus:]
- Slack items use "(per Slack #channel-name)" or "(per Slack DM with Person)" as source attribution.
- Merge duplicate topics across meetings AND Slack. One bullet, multiple sources.
"""
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| slackclient library | slack_sdk library | 2020 (slackclient deprecated) | Use slack_sdk, not slackclient |
| RTM API for reading messages | Conversations API (REST) | 2020+ | RTM deprecated for most use cases; use conversations.history/replies |
| No built-in retry | RateLimitErrorRetryHandler | slack_sdk 3.9.0 (2021) | No need for custom retry logic |
| Token-based pagination | Cursor-based pagination | 2018 | All list/history methods use cursor; never use page/count params |

**Deprecated/outdated:**
- `slackclient` package: Replaced by `slack_sdk`. Do not install slackclient.
- RTM API: Not needed for batch ingestion. Conversations API is the right approach.
- `channels.history` / `im.history` / `groups.history`: Replaced by unified `conversations.history`. The old methods still work but are legacy.

## Open Questions

1. **Volume cap strategy for high-traffic channels**
   - What we know: Some channels may have 500+ messages/day. Sending all to synthesis wastes tokens and dilutes quality.
   - What's unclear: Best strategy -- truncate to most recent N? Sample evenly? Pre-summarize with a cheaper model?
   - Recommendation: Start with "most recent N messages" (configurable, default 100). Add pre-summarization as a follow-up if needed. The planner should decide.

2. **Periodic auto-suggest implementation**
   - What we know: User wants discovery to periodically flag new active channels.
   - What's unclear: How to trigger periodic suggestions -- on every pipeline run? Weekly? Separate cron job?
   - Recommendation: Check for new qualifying channels on each pipeline run; if found, log a suggestion but don't block the pipeline. Add a `--discover` flag or check a "last_discovery_check" timestamp.

3. **DM partner name resolution**
   - What we know: DM channels have a `user` field (the other person's ID). Need to resolve to display name.
   - What's unclear: For group DMs (mpim), there are multiple members. How to format attribution?
   - Recommendation: For 1:1 DMs: "(per Slack DM with {name})". For group DMs: "(per Slack DM with {name1}, {name2}, ...)" or "(per Slack group DM)" if too many names.

4. **Synthesis prompt structure for mixed sources**
   - What we know: Current synthesizer takes `list[MeetingExtraction]`. Need to also accept `list[SourceItem]`.
   - What's unclear: Should Slack items go into the same prompt as meeting extractions, or be a separate synthesis pass?
   - Recommendation: Single prompt, separate sections. Meeting extractions first (as today), then a "### Slack Activity" section with SourceItems formatted for synthesis. This avoids a second API call and lets Claude deduplicate across sources naturally.

## Sources

### Primary (HIGH confidence)
- [Slack conversations.history API docs](https://docs.slack.dev/reference/methods/conversations.history/) - message fetching, pagination, oldest/latest params
- [Slack conversations.replies API docs](https://docs.slack.dev/reference/methods/conversations.replies/) - thread expansion, cursor pagination
- [Slack users.conversations API docs](https://docs.slack.dev/reference/methods/users.conversations/) - channel/DM discovery
- [Slack rate limits docs](https://docs.slack.dev/apis/web-api/rate-limits/) - Tier 3 limits for internal apps (50+ req/min)
- [Slack scopes reference](https://docs.slack.dev/reference/scopes/) - required bot token scopes
- [slack_sdk Python installation](https://docs.slack.dev/tools/python-slack-sdk/installation/) - pip install, version info
- [slack_sdk RateLimitErrorRetryHandler](https://docs.slack.dev/tools/python-slack-sdk/reference/http_retry/builtin_handlers.html) - built-in retry handler

### Secondary (MEDIUM confidence)
- [Rate limit changes for non-Marketplace apps (May 2025)](https://docs.slack.dev/changelog/2025/05/29/rate-limit-changes-for-non-marketplace-apps/) - confirmed internal apps unaffected
- [Slack SDK GitHub releases](https://github.com/slackapi/python-slack-sdk/releases) - latest version 3.41.0

### Tertiary (LOW confidence)
- None -- all findings verified with official docs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - slack_sdk is the only official Python SDK; well-documented, stable
- Architecture: HIGH - Conversations API patterns are well-established; existing SourceItem model designed for this use case
- Pitfalls: HIGH - rate limits, scope requirements, and timestamp handling are well-documented in official docs
- Synthesis integration: MEDIUM - the multi-source prompt design is a novel integration point; will need iteration

**Research date:** 2026-04-04
**Valid until:** 2026-05-04 (stable domain; Slack API rarely has breaking changes for internal apps)
