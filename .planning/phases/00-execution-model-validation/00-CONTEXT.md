# Phase 0: Execution Model Validation - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Prove the daily automation foundation works before building on it: Cowork scheduled task fires reliably, Google OAuth authenticates Calendar + Gmail APIs with auto-refresh, Claude Code session can execute Python scripts. No real pipeline logic — just validation that the execution model is sound.

</domain>

<decisions>
## Implementation Decisions

### Schedule timing & cadence
- Run daily at end of workday (~5-6pm ET)
- Run every day including weekends (weekend runs may produce minimal output)
- Timezone: US Eastern
- Validation test uses a real Calendar API call (not a lightweight ping) to prove scheduling AND OAuth together

### OAuth & credential management
- Google Cloud project needs to be set up from scratch (create project, enable APIs, create OAuth client)
- Store credentials in local dotfile (.env or .credentials/ directory), gitignored
- Request all scopes upfront: Calendar read + Gmail read (avoids re-auth when Phase 2 adds Gmail ingestion)
- Slack DM notification when OAuth token expires and can't auto-refresh
- Documented re-auth procedure for manual token refresh

### Failure handling & observability
- On failure: log error to file AND send Slack DM notification with the error
- Retry once after 15 minutes on failure; if retry also fails, notify and stop
- Slack notifications go to DM (not a channel)

### Validation evidence
- Each successful run produces a timestamped output file (real calendar event list for that day: titles, times, attendees)
- A summary validation log tracks each day's result: timestamp, API response status, pass/fail
- 5 successful runs total (not necessarily consecutive calendar days) = validation passed
- Output files serve as primary evidence; summary log for quick review

### Claude's Discretion
- Log file location and naming convention
- Whether validation script becomes the production scheduler skeleton or gets replaced in Phase 1
- Exact retry mechanism implementation
- Specific Slack notification format

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

*Phase: 00-execution-model-validation*
*Context gathered: 2026-04-02*
