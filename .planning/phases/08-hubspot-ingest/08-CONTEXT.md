# Phase 8: HubSpot Ingest - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Ingest HubSpot CRM activity — deal movements, contact notes, tickets, calls, emails, meetings, and tasks — into daily summaries. Includes configurable ownership scoping. Cross-source deduplication for meetings and emails that overlap with existing sources. CRM reporting, dashboards, and workflow automation are out of scope.

</domain>

<decisions>
## Implementation Decisions

### Deal activity scope
- Ingest deal stage transitions AND key property changes (amount, close date, owner reassignment)
- Include newly created deals on the target date
- Moderate detail per deal: deal name, amount, current stage, owner
- Configurable ownership scope: default to user's deals, with config option to expand to all deals or specific owners/teams

### Contact & note handling
- Ingest contact notes, logged calls, logged emails, and meetings associated with contacts
- Include both auto-logged (email integration) and manually logged activities
- Attribution format: "Note on John Smith (Acme Corp): ..." — contact name + company
- Same configurable ownership scope as deals (default to my contacts, expandable)

### Activity type coverage
- Prioritize by type: calls and meetings get more detail; emails and tasks get brief mentions
- Tickets: include status changes, newly created, and resolved tickets
- Deduplicate HubSpot meetings/calls against meetings already captured from Google Calendar/transcript sources — skip the HubSpot version if already present
- Cross-source dedup for emails: if the same email appears from both Gmail and HubSpot, keep only one

### CRM object relationships
- When an activity is linked to multiple objects, attribute to primary object only (no duplication)
- Fixed hierarchy: deal > contact > company — deals always take priority
- Summary groups HubSpot items by object type (deals section, contacts section, tickets section) rather than chronological

### Claude's Discretion
- Volume cap strategy per activity type (how many items per type before "and X more")
- Exact dedup matching logic for cross-source meetings and emails
- How to handle activities with no object association
- Ticket detail level and formatting

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

*Phase: 08-hubspot-ingest*
*Context gathered: 2026-04-04*
