# Phase 7: Slack Ingest + Synthesis Integration - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Ingest Slack messages from curated channels and DMs, expand active threads, and integrate Slack content into daily summaries alongside existing meeting content. Includes a discovery mode for proposing channels/DMs to track. Source attribution throughout output. Creating new Slack integrations beyond ingestion, or adding other source types, are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Channel content scope
- Bot messages excluded by default, with a configurable allowlist for specific bots (e.g., keep Salesforce alerts, skip Giphy)
- Aggressive pre-synthesis filtering: skip join/leave events, channel topic changes, reactions-only messages, single-word responses ('ok', 'thanks', 'lol'), link-only messages with no commentary, and edited-away messages
- Time window: since-last-run tracking per channel (store last-ingested timestamp, only grab new messages since then)

### Thread expansion rules
- Expansion threshold: 3+ replies AND 2+ distinct participants (both conditions must be met)
- Thresholds are user-configurable in config
- Threads below threshold: show parent message with reply count hint (e.g., "(5 replies)")
- Threads above threshold: expanded representation (Claude's discretion on format — summarized thread vs key messages quoted)

### DM handling & privacy
- Both 1:1 and group DMs eligible for ingestion
- Discovery-assisted opt-in: no DMs ingested by default; discovery mode suggests active DMs based on frequency, user confirms which to include
- Attribution names the person: "(per Slack DM with Sarah Chen)" style
- DM content filtering: Claude's discretion on appropriate filtering level for DMs vs channels

### Discovery mode
- Interactive prompt: step through each proposed channel/DM one at a time
- Each proposal shows activity stats (message count, participant count) + 2-3 recent topic keywords
- DM discovery flow structure: Claude's discretion (separate pass vs combined)
- Re-runnable anytime: user can re-run to add new channels/remove old ones, showing what's already configured vs new suggestions
- Periodic auto-suggest: discovery periodically flags new active channels the user isn't tracking yet

### Claude's Discretion
- Volume cap strategy per channel (how to handle high-volume channels)
- Thread expansion display format (summarized vs key messages quoted)
- DM filtering level relative to channel filtering
- Discovery flow structure (channels and DMs separate or combined)
- Technical implementation of periodic auto-suggest timing

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 07-slack-ingest-synthesis-integration*
*Context gathered: 2026-04-04*
