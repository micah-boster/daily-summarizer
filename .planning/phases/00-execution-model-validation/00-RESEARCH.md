# Phase 0: Execution Model Validation - Research

**Researched:** 2026-04-02
**Domain:** Cowork scheduling, Google OAuth2 (Calendar + Gmail), Slack notifications, Claude Code session execution
**Confidence:** MEDIUM-HIGH

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- Run daily at end of workday (~5-6pm ET), every day including weekends
- Timezone: US Eastern
- Validation test uses a real Calendar API call (not a lightweight ping) to prove scheduling AND OAuth together
- Google Cloud project needs to be set up from scratch (create project, enable APIs, create OAuth client)
- Store credentials in local dotfile (.env or .credentials/ directory), gitignored
- Request all scopes upfront: Calendar read + Gmail read
- Slack DM notification when OAuth token expires and can't auto-refresh
- On failure: log error to file AND send Slack DM notification with the error
- Retry once after 15 minutes on failure; if retry also fails, notify and stop
- Each successful run produces a timestamped output file (real calendar event list: titles, times, attendees)
- A summary validation log tracks each day's result: timestamp, API response status, pass/fail
- 5 successful runs total (not necessarily consecutive calendar days) = validation passed
- Output files serve as primary evidence; summary log for quick review

### Claude's Discretion
- Log file location and naming convention
- Whether validation script becomes the production scheduler skeleton or gets replaced in Phase 1
- Exact retry mechanism implementation
- Specific Slack notification format

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INGEST-01 | Semi-automated daily pipeline: script pulls calendar + transcript data, processes through Claude, outputs structured summary | This phase validates the execution model (Cowork + OAuth + Claude Code session) that INGEST-01 depends on. The scheduled task, Google API auth, and Python script execution patterns researched here form the foundation for all subsequent pipeline work. |

</phase_requirements>

## Summary

Phase 0 validates three independent capabilities that the entire pipeline depends on: (1) Cowork scheduled tasks firing reliably on a daily cadence, (2) Google OAuth2 authenticating against Calendar and Gmail APIs with automatic token refresh, and (3) Claude Code sessions within Cowork executing Python scripts that read/write files and produce structured output.

The research reveals two scheduling options: **Cowork Desktop scheduled tasks** (run on local machine, require machine awake) and **Claude Code Cloud scheduled tasks** (run on Anthropic infrastructure, always-on). Desktop tasks are the correct choice for this project because the pipeline needs local filesystem access for OAuth token storage, output files, and the project repository. The critical reliability caveat is that the machine must be awake and Claude Desktop must be open at task time -- but the 5-6pm ET schedule falls within normal work hours, and Cowork will auto-run a skipped task when the machine wakes.

Google OAuth2 for Calendar + Gmail is well-supported by the official `google-auth-oauthlib` library. The desktop flow uses `InstalledAppFlow.from_client_secrets_file()` with `run_local_server()` for initial auth, then stores a token file with refresh credentials. The credentials auto-refresh via `before_request()` but the refresh token itself can expire (Google's 7-day expiry for "testing" apps, or 6 months for published apps). This is the most likely failure mode and justifies the Slack notification on auth failure.

**Primary recommendation:** Use Cowork Desktop scheduled tasks with a Python validation script that performs a real Calendar API call, writes timestamped output, and sends Slack notifications on failure. Store OAuth tokens in `.credentials/token.json` (gitignored). Use `httpx` for Slack webhook notifications (simpler than the full `slack_sdk` for fire-and-forget alerts).

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `google-api-python-client` | >=2.150.0 | Calendar + Gmail API access | Official Google client, handles discovery, pagination, auth integration |
| `google-auth` | >=2.36.0 | OAuth2 token management, auto-refresh | Core auth library, handles token lifecycle |
| `google-auth-oauthlib` | >=1.2.0 | Desktop OAuth flow (initial auth only) | Official desktop flow for installed apps |
| `google-auth-httplib2` | >=0.2.0 | HTTP transport for google-api-python-client | Required transport adapter |
| `httpx` | >=0.27.0 | Slack webhook HTTP calls | Already in project stack (STACK.md), modern HTTP client |
| Python | 3.12 | Runtime | Per STACK.md recommendation |
| `uv` | >=0.5 | Package/env management | Per STACK.md recommendation |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `python-dateutil` | >=2.9.0 | Parse date/time from API responses | Calendar event time parsing |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Cowork Desktop tasks | Claude Code Cloud tasks | Cloud is more reliable (no machine dependency) but cannot access local filesystem for token storage and output files. Desktop is correct for this project. |
| httpx for Slack | slack_sdk | slack_sdk is heavier, requires bot token setup for DMs. A simple webhook POST via httpx to a Slack incoming webhook (pointed at a DM channel) is sufficient for notifications. |
| Incoming webhook | Slack bot token + chat.postMessage | Bot token enables true DMs to any user but requires more Slack app setup. An incoming webhook configured to post to a personal channel/DM is simpler for self-notification. |

**Installation:**
```bash
uv pip install google-api-python-client google-auth google-auth-oauthlib google-auth-httplib2 httpx python-dateutil
```

## Architecture Patterns

### Recommended Project Structure
```
src/
  auth/
    google_oauth.py      # OAuth flow, token load/save/refresh
    credentials_check.py # Validate credentials, detect expiry
  notifications/
    slack.py             # Slack webhook notification helper
  validation/
    daily_check.py       # Main validation script (entry point for Cowork)
    run_log.py           # Validation log reader/writer
.credentials/
  client_secret.json     # Google OAuth client config (gitignored)
  token.json             # OAuth token with refresh token (gitignored)
output/
  validation/
    YYYY-MM-DD_HH-MM.json  # Timestamped validation output files
    validation_log.jsonl    # Append-only validation summary log
```

### Pattern 1: OAuth Token Load/Refresh/Save Cycle
**What:** Load stored credentials, check expiry, auto-refresh if possible, save updated token, fall back to notification if refresh fails.
**When to use:** Every pipeline execution begins with this pattern.
**Example:**
```python
# Source: Google official docs + google-auth API reference
import json
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
]
CREDENTIALS_DIR = Path(".credentials")
TOKEN_PATH = CREDENTIALS_DIR / "token.json"
CLIENT_SECRET_PATH = CREDENTIALS_DIR / "client_secret.json"


def load_credentials() -> Credentials | None:
    """Load credentials from token file, refresh if expired."""
    if not TOKEN_PATH.exists():
        return None

    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if creds.valid:
        return creds

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            save_credentials(creds)
            return creds
        except Exception as e:
            # Refresh failed -- token revoked or expired beyond refresh
            return None

    return None


def save_credentials(creds: Credentials) -> None:
    """Persist credentials to token file."""
    CREDENTIALS_DIR.mkdir(exist_ok=True)
    TOKEN_PATH.write_text(creds.to_json())


def run_initial_auth() -> Credentials:
    """Run interactive OAuth flow (first time only)."""
    flow = InstalledAppFlow.from_client_secrets_file(
        str(CLIENT_SECRET_PATH), SCOPES
    )
    creds = flow.run_local_server(port=0)
    save_credentials(creds)
    return creds
```

### Pattern 2: Slack Webhook Notification
**What:** Fire-and-forget POST to Slack incoming webhook URL.
**When to use:** On OAuth failure, pipeline errors, or validation results.
**Example:**
```python
# Source: Slack incoming webhooks docs + httpx
import httpx
import os

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")


def notify_slack(message: str) -> bool:
    """Send notification to Slack via incoming webhook. Returns True on success."""
    if not SLACK_WEBHOOK_URL:
        print("SLACK_WEBHOOK_URL not set, skipping notification")
        return False

    try:
        response = httpx.post(
            SLACK_WEBHOOK_URL,
            json={"text": message},
            timeout=10.0,
        )
        return response.status_code == 200
    except httpx.HTTPError:
        return False
```

### Pattern 3: Validation Run with Retry
**What:** Execute validation, retry once on failure after delay, notify on final failure.
**When to use:** The main entry point that Cowork's scheduled task calls.
**Example:**
```python
import time
import json
from datetime import datetime, timezone

RETRY_DELAY_SECONDS = 15 * 60  # 15 minutes


def run_validation() -> dict:
    """Single validation attempt: auth + Calendar API call + output."""
    creds = load_credentials()
    if creds is None:
        raise RuntimeError("OAuth credentials unavailable or refresh failed")

    service = build("calendar", "v3", credentials=creds)
    # Real Calendar API call -- proves auth works
    now = datetime.now(timezone.utc).isoformat()
    events_result = service.events().list(
        calendarId="primary",
        timeMin=now.replace(hour=0, minute=0, second=0),
        timeMax=now,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    events = events_result.get("items", [])
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "pass",
        "event_count": len(events),
        "events": [
            {
                "title": e.get("summary", "No title"),
                "start": e.get("start", {}).get("dateTime", ""),
                "attendees": [a.get("email", "") for a in e.get("attendees", [])],
            }
            for e in events
        ],
    }


def main():
    """Entry point with retry logic."""
    try:
        result = run_validation()
    except Exception as first_error:
        notify_slack(f"Validation failed (attempt 1): {first_error}. Retrying in 15 min.")
        time.sleep(RETRY_DELAY_SECONDS)
        try:
            result = run_validation()
        except Exception as second_error:
            notify_slack(f"Validation FAILED (attempt 2, giving up): {second_error}")
            append_to_log({"timestamp": datetime.now(timezone.utc).isoformat(), "status": "fail", "error": str(second_error)})
            return

    # Write timestamped output
    write_output(result)
    append_to_log(result)
    notify_slack(f"Validation passed: {result['event_count']} events found.")
```

### Anti-Patterns to Avoid
- **Storing OAuth tokens in .env:** The token.json file contains a refresh token that changes on refresh. Environment variables are static. Use a dedicated JSON file that gets updated on each refresh.
- **Using service accounts for personal Gmail/Calendar:** Service accounts cannot access personal Google accounts (only Google Workspace with domain-wide delegation). Must use OAuth2 desktop flow.
- **Polling for schedule instead of using Cowork:** Do not build a cron-like scheduler in Python. Cowork handles scheduling; the Python script should be a single-shot execution.
- **Ignoring the 15-minute retry sleep blocking Cowork:** The `time.sleep(900)` in the retry logic blocks the Cowork session for 15 minutes. This is acceptable for a validation spike but may need rethinking for production (e.g., separate retry task).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OAuth2 token refresh | Custom HTTP token refresh | `google-auth` Credentials.refresh() | Handles token expiry detection, refresh request, error states, new token persistence |
| Google API pagination | Manual nextPageToken loops | google-api-python-client's list_next() | Handles pagination protocol correctly across all Google APIs |
| OAuth2 desktop flow | Manual browser redirect + code exchange | InstalledAppFlow.run_local_server() | Handles local HTTP server, redirect URI, PKCE, code exchange |
| Scheduled execution | Python cron/scheduler library | Cowork scheduled tasks | Cowork manages cadence, handles missed runs, provides execution UI |
| Slack message formatting | Raw string building | Slack Block Kit JSON (if needed) | For now, plain text via webhook is sufficient; don't over-engineer |

**Key insight:** The Google auth ecosystem has many moving parts (client secrets, access tokens, refresh tokens, scopes, consent screens). The official libraries handle all the edge cases. Hand-rolling any part of this flow leads to subtle bugs around token expiry, scope changes, and consent revocation.

## Common Pitfalls

### Pitfall 1: Google OAuth "Testing" App Token Expiry
**What goes wrong:** Refresh tokens for apps in "Testing" publishing status expire after 7 days. The pipeline silently fails after the first week.
**Why it happens:** Google enforces a 7-day refresh token lifetime for apps that haven't been verified/published. Most tutorials don't mention this because they assume short-lived scripts.
**How to avoid:** Either (a) publish the app (push it to "Production" status in Google Cloud Console -- for personal use with <100 users, no verification review is needed) or (b) accept re-auth every 7 days and build the notification + re-auth procedure to handle it gracefully.
**Warning signs:** `google.auth.exceptions.RefreshError` after exactly 7 days of operation.

### Pitfall 2: Cowork Desktop Task Skipping (Machine Asleep)
**What goes wrong:** The 5-6pm task fires but the machine was asleep (lid closed, etc.). Cowork skips the run.
**Why it happens:** Cowork Desktop tasks only run while the machine is awake and the Claude Desktop app is open. On wake, it auto-runs the skipped task, but the timing shifts.
**How to avoid:** (a) Keep machine awake during the scheduled window, (b) use a macOS energy schedule (System Settings > Energy > Schedule) to prevent sleep during 5-6pm, (c) accept that Cowork will auto-run on wake and validate that this behavior is acceptable for the use case.
**Warning signs:** Validation outputs appearing at odd times (e.g., 9am the next morning instead of 5pm).

### Pitfall 3: OAuth Scopes Mismatch on Re-auth
**What goes wrong:** Initial auth requests Calendar-only scopes. Later, when Gmail scope is added, the stored token doesn't have it. The Gmail API call fails with a 403.
**Why it happens:** OAuth scopes are locked at consent time. Adding a scope requires re-running the consent flow.
**How to avoid:** Request BOTH scopes upfront (Calendar read + Gmail read) even though Gmail isn't used until Phase 2. This is already a locked decision in CONTEXT.md.
**Warning signs:** `HttpError 403: Insufficient Permission` when first using Gmail API.

### Pitfall 4: Refresh Token Not Returned on Re-auth
**What goes wrong:** Running the OAuth flow again (e.g., after token expiry) returns only an access token without a refresh token. The next pipeline run fails because there's no refresh token to auto-refresh with.
**Why it happens:** Google only returns a refresh token on the FIRST authorization. Subsequent flows return access-only tokens unless you explicitly include `prompt='consent'` in the auth URL.
**How to avoid:** When running re-auth, use `flow.authorization_url(access_type='offline', prompt='consent')` or configure InstalledAppFlow to include these parameters. Delete the old token.json before re-auth.
**Warning signs:** token.json after re-auth has no `refresh_token` field.

### Pitfall 5: Slack Incoming Webhook for DM Requires Specific Setup
**What goes wrong:** Creating a Slack incoming webhook defaults to posting to a channel, not a DM.
**Why it happens:** Incoming webhooks are associated with a specific channel chosen during webhook creation.
**How to avoid:** When creating the Slack app + incoming webhook, select the DM conversation with yourself (or a personal notification channel) as the target. Alternatively, use the Slack MCP connector in Cowork which is already authenticated.
**Warning signs:** Notifications appearing in a public channel instead of a DM.

## Code Examples

### Google Cloud Project Setup Procedure (Manual Steps)
```
1. Go to https://console.cloud.google.com/
2. Create new project: "Daily Summarizer" (or similar)
3. Enable APIs:
   - Google Calendar API
   - Gmail API
4. Configure OAuth consent screen:
   - User type: External (or Internal if using Workspace)
   - App name: "Daily Summarizer"
   - Scopes: calendar.readonly, gmail.readonly
   - Test users: add your own email
   - Publishing status: Consider "In production" to avoid 7-day token expiry
5. Create OAuth 2.0 Client ID:
   - Application type: Desktop app
   - Download client_secret.json
6. Place client_secret.json in .credentials/ directory
```

### Initial OAuth Flow (Run Once Interactively)
```python
# Run this script once to generate token.json
from auth.google_oauth import load_credentials, run_initial_auth

creds = load_credentials()
if creds is None:
    print("No valid credentials found. Running OAuth flow...")
    creds = run_initial_auth()
    print(f"Credentials saved. Scopes: {creds.scopes}")
else:
    print(f"Credentials valid. Expiry: {creds.expiry}")
```

### Calendar API Call Pattern
```python
# Source: Google Calendar API docs
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import zoneinfo

def fetch_todays_events(creds) -> list[dict]:
    """Fetch today's calendar events in US/Eastern timezone."""
    eastern = zoneinfo.ZoneInfo("America/New_York")
    now = datetime.now(eastern)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)

    service = build("calendar", "v3", credentials=creds)
    events_result = service.events().list(
        calendarId="primary",
        timeMin=start_of_day.isoformat(),
        timeMax=end_of_day.isoformat(),
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    return events_result.get("items", [])
```

### Validation Log (JSONL Append Pattern)
```python
import json
from pathlib import Path
from datetime import datetime, timezone

VALIDATION_LOG = Path("output/validation/validation_log.jsonl")


def append_to_log(entry: dict) -> None:
    """Append a validation result to the JSONL log."""
    VALIDATION_LOG.parent.mkdir(parents=True, exist_ok=True)
    with VALIDATION_LOG.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def count_passes() -> int:
    """Count successful validation runs."""
    if not VALIDATION_LOG.exists():
        return 0
    count = 0
    for line in VALIDATION_LOG.read_text().splitlines():
        entry = json.loads(line)
        if entry.get("status") == "pass":
            count += 1
    return count
```

### Re-auth Procedure Document Template
```markdown
# Google OAuth Re-Authentication Procedure

## When This Is Needed
- Slack notification says "OAuth refresh failed"
- Pipeline logs show `google.auth.exceptions.RefreshError`
- More than 7 days since last auth (if app is in "Testing" status)

## Steps
1. Delete the expired token: `rm .credentials/token.json`
2. Run the auth script: `python -m src.auth.google_oauth`
3. Browser opens -- sign in with your Google account
4. Grant Calendar + Gmail read permissions
5. Verify: `python -c "from src.auth.google_oauth import load_credentials; c = load_credentials(); print('OK' if c else 'FAIL')"`
6. Confirm refresh token exists: check .credentials/token.json has "refresh_token" field

## Troubleshooting
- If no refresh_token in token.json: delete token.json, re-run auth
- If "Access blocked" in browser: check test users list in Google Cloud Console
- If 403 on API call: check scopes in OAuth consent screen configuration
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `oauth2client` library | `google-auth` + `google-auth-oauthlib` | 2019 (oauth2client deprecated) | Must use new library; many old tutorials reference deprecated oauth2client |
| Manual cron jobs | Cowork scheduled tasks | 2025-2026 | No crontab management; Cowork handles scheduling with Claude Code integration |
| Slack legacy webhooks | Slack Apps + incoming webhooks | 2020 | Legacy webhook URLs still work but new setup requires creating a Slack App first |
| `pytz` for timezones | `zoneinfo` (stdlib) | Python 3.9+ | No external dependency needed for timezone handling |

**Deprecated/outdated:**
- `oauth2client`: Fully deprecated. Do not use. All Google tutorials post-2020 use `google-auth`.
- `gflags` for OAuth: Ancient pattern from oauth2client era. Not needed.
- Slack legacy webhooks (pre-Slack-App): Still functional but cannot create new ones.

## Open Questions

1. **Cowork Desktop vs Cloud for Production**
   - What we know: Desktop tasks need machine awake but have local file access. Cloud tasks are always-on but clone from GitHub (no local state).
   - What's unclear: Whether the production pipeline (Phase 1+) should migrate to Cloud tasks with secrets stored as environment variables and output committed to GitHub, versus staying on Desktop.
   - Recommendation: Use Desktop for Phase 0 validation. Revisit for Phase 1 based on reliability results.

2. **Google Cloud App Publishing Status**
   - What we know: "Testing" status = 7-day refresh token expiry. "In production" for <100 users = no Google review needed, longer token lifetime.
   - What's unclear: Exact refresh token lifetime for "In production" personal-use apps (documentation says "6 months of inactivity" but daily use should keep it alive indefinitely).
   - Recommendation: Push to "In production" status immediately. For a personal-use app with 1 user, this requires no verification and eliminates the 7-day expiry problem.

3. **Slack Notification Method: Webhook vs Cowork Slack Connector**
   - What we know: Cowork has a built-in Slack MCP connector. The validation Python script could also use a simple webhook POST.
   - What's unclear: Whether the Cowork Slack connector is accessible from within a Python script running in the Cowork session, or only from Claude's own tool use.
   - Recommendation: Use a Slack incoming webhook via httpx from the Python script. This is self-contained and doesn't depend on Cowork's connector plumbing. Store the webhook URL in .env (gitignored).

4. **Retry Sleep Blocking Cowork Session**
   - What we know: The 15-minute retry delay uses `time.sleep(900)` which blocks the Cowork session.
   - What's unclear: Whether Cowork has a timeout that would kill a session sleeping for 15 minutes.
   - Recommendation: Start with `time.sleep()` for the spike. If Cowork kills the session, switch to a two-stage approach (first run logs failure, Cowork re-runs after delay).

## Sources

### Primary (HIGH confidence)
- [Cowork scheduled tasks official docs](https://support.claude.com/en/articles/13854387-schedule-recurring-tasks-in-cowork) - Desktop scheduling cadences, sleep behavior, tool access
- [Claude Code cloud scheduled tasks](https://code.claude.com/docs/en/web-scheduled-tasks) - Cloud vs desktop comparison, environment setup, frequency options
- [google-auth Credentials API](https://googleapis.dev/python/google-auth/latest/reference/google.oauth2.credentials.html) - Credentials class, refresh mechanism, from_authorized_user_file
- [google-auth-oauthlib flow](https://googleapis.dev/python/google-auth-oauthlib/latest/reference/google_auth_oauthlib.flow.html) - InstalledAppFlow for desktop apps
- [google-api-python-client OAuth docs](https://googleapis.github.io/google-api-python-client/docs/oauth.html) - OAuth2 integration with API client

### Secondary (MEDIUM confidence)
- [Slack incoming webhooks docs](https://api.slack.com/incoming-webhooks) - Webhook setup and posting
- [Google OAuth2 overview](https://developers.google.com/identity/protocols/oauth2) - OAuth2 flow documentation
- STACK.md (project research, 2026-03-23) - Library versions and rationale

### Tertiary (LOW confidence)
- Google "Testing" vs "In production" token lifetime specifics - based on community reports, not found in official documentation with exact numbers

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - official Google libraries, well-documented, per STACK.md decisions
- Architecture (Cowork scheduling): MEDIUM-HIGH - official docs confirm capabilities and limitations; reliability for daily pipelines is the exact thing this phase validates
- Architecture (OAuth flow): HIGH - official library APIs verified, well-established pattern
- Pitfalls: HIGH - 7-day token expiry and refresh-token-not-returned are well-documented gotchas
- Slack notifications: MEDIUM - webhook approach is straightforward but DM-specific setup needs validation during implementation

**Research date:** 2026-04-02
**Valid until:** 2026-05-02 (30 days -- stable domain, Google APIs change slowly)
