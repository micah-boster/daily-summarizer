# Phase 2: Transcript Ingestion and Normalization - Research

**Researched:** 2026-04-03
**Domain:** Gmail API email parsing, transcript extraction, calendar-transcript linking
**Confidence:** MEDIUM

## Summary

Phase 2 extends the existing Phase 1 pipeline (calendar ingestion) with two new data sources: Gemini meeting transcripts and Gong call summaries, both delivered via Gmail. The core challenge is building a Gmail ingestion module that searches for and parses transcript-bearing emails, then linking those transcripts to the already-ingested calendar events from Phase 1 using time-window and title-based matching.

The Gmail API is already authorized (gmail.readonly scope configured in Phase 0's OAuth module). The `google-api-python-client` library already in the project handles Gmail API access identically to how it handles Calendar API access — `build("gmail", "v1", credentials=creds)` creates the service. Email discovery uses `messages.list()` with query strings (`from:`, `subject:`, `after:`, `before:` operators), and body extraction requires base64url decoding of MIME parts.

**Primary recommendation:** Build a modular Gmail ingestion layer with pluggable transcript parsers (one for Gemini, one for Gong), a configurable email identification system (sender/subject patterns in config.yaml), and a matching pipeline that links transcripts to NormalizedEvent objects using time-window + title similarity scoring.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Gemini transcripts arrive as Gmail emails (not calendar attachments)
- Gong transcripts arrive as emails containing a summary plus a link back to Gong
- For Gong: use the email summary content for now; full Gong transcript pull is a future enhancement
- Email identification patterns (sender addresses, subject line formats) for both sources: Claude to investigate actual patterns during research
- Unmatched transcripts (no calendar event): include as standalone entries in the normalized output, not dropped
- When both Gemini and Gong produce transcripts for the same meeting: Gemini is the primary source
- Time-window and matching strategy for linking: Claude's discretion during implementation
- When multiple calendar events overlap and a transcript arrives: pick the single best-matching event (title + time + attendees), no confidence scoring
- Include all meetings regardless of duration (even very short ones may contain decisions)
- Exclude personal calendar blocks (focus time, lunch, commute, OOO) from ingestion
- Strip filler text (ums, ahs, repeated phrases) at ingestion time before passing to synthesis — reduces token cost
- Calendar events with no transcript: configurable toggle for whether they appear in normalized output (default behavior at Claude's discretion)

### Claude's Discretion
- Email sender/subject identification patterns for Gemini and Gong emails
- Time window for transcript-to-calendar matching
- Raw cache strategy (full email vs extracted content only)
- Orphan transcript display approach
- Pipeline logging verbosity and summary stats
- Default for transcript-less event visibility toggle

### Deferred Ideas (OUT OF SCOPE)
- Full Gong transcript pull via API or link scraping — future enhancement beyond email summary
- Confidence scoring for transcript-calendar matches — v1 uses best-match-only
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INGEST-03 | Ingest meeting transcripts from Gemini (Gmail/Calendar attachments) | Gmail API message search/retrieval with sender/subject filtering; base64url body decoding; Gemini email pattern identification |
| INGEST-04 | Ingest meeting transcripts from Gong (email delivery) | Gmail API same pattern; Gong email identification; summary extraction from email body |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| google-api-python-client | >=2.193.0 | Gmail API access (already installed) | Same library used for Calendar API in Phase 1 |
| pydantic | >=2.12.5 | Data models for transcripts (already installed) | Extends existing NormalizedEvent model |
| python-dateutil | >=2.9.0 | Date parsing from email headers/bodies (already installed) | Handles ISO 8601 and natural date formats |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| re (stdlib) | N/A | Filler text stripping, email pattern matching | Transcript preprocessing |
| base64 (stdlib) | N/A | Decode base64url email body content | Gmail API body extraction |
| email (stdlib) | N/A | Parse RFC 2822 email messages | Raw format email parsing |
| html (stdlib) | N/A | Unescape HTML entities in email bodies | Clean HTML email content |
| difflib (stdlib) | N/A | SequenceMatcher for title similarity | Transcript-calendar matching |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| difflib.SequenceMatcher | fuzzywuzzy/thefuzz | External dep for marginal improvement; stdlib sufficient for title matching |
| re-based filler stripping | NLP libraries (spaCy) | Massive dependency for simple pattern matching; regex is appropriate here |
| Full MIME parsing | Just base64 decode | MIME parsing handles multipart emails correctly; worth the small complexity |

**Installation:** No new packages needed — all dependencies already in pyproject.toml from Phase 0/1.

## Architecture Patterns

### Recommended Project Structure
```
src/
├── ingest/
│   ├── __init__.py
│   ├── calendar.py          # (existing) Phase 1
│   ├── gmail.py             # NEW: Gmail service builder, message search, body extraction
│   ├── transcripts.py       # NEW: Transcript parsers (Gemini, Gong), filler stripping
│   └── normalizer.py        # NEW: Calendar-transcript linking, deduplication, merge
├── models/
│   └── events.py            # EXTEND: Add transcript fields to NormalizedEvent
├── main.py                  # EXTEND: Wire transcript ingestion into pipeline
└── config.py                # EXTEND: Add gmail/transcript config sections
```

### Pattern 1: Gmail Service and Message Retrieval
**What:** Build Gmail service using same OAuth credentials as Calendar, search messages with query operators, extract body content
**When to use:** All email-based transcript discovery

```python
# Gmail service (same credential pattern as calendar.py)
def build_gmail_service(creds: Credentials):
    return build("gmail", "v1", credentials=creds)

# Search messages with Gmail query operators
def search_messages(service, query: str, max_results: int = 50) -> list[dict]:
    results = service.users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute()
    messages = results.get("messages", [])
    # Handle pagination if needed
    while "nextPageToken" in results:
        results = service.users().messages().list(
            userId="me", q=query, maxResults=max_results,
            pageToken=results["nextPageToken"]
        ).execute()
        messages.extend(results.get("messages", []))
    return messages

# Get full message content
def get_message(service, msg_id: str) -> dict:
    return service.users().messages().get(
        userId="me", id=msg_id, format="full"
    ).execute()
```

### Pattern 2: Email Body Extraction
**What:** Decode base64url MIME parts to get plain text or HTML body
**When to use:** Extracting transcript content from Gmail messages

```python
import base64
from email import message_from_bytes

def extract_body(payload: dict) -> str:
    """Extract text body from Gmail message payload."""
    # Simple single-part message
    if "body" in payload and payload["body"].get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8")

    # Multipart: recurse through parts, prefer text/plain
    parts = payload.get("parts", [])
    for part in parts:
        mime_type = part.get("mimeType", "")
        if mime_type == "text/plain" and part.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")

    # Fallback to text/html
    for part in parts:
        mime_type = part.get("mimeType", "")
        if mime_type == "text/html" and part.get("body", {}).get("data"):
            raw = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")
            # Strip HTML tags for plain text
            return strip_html(raw)

    return ""
```

### Pattern 3: Transcript-Calendar Matching
**What:** Link transcripts to calendar events using time window + title similarity
**When to use:** Normalization pipeline after both calendar and transcript data are collected

```python
from difflib import SequenceMatcher

def match_transcript_to_event(
    transcript_time: datetime,
    transcript_title: str,
    events: list[NormalizedEvent],
    time_window_minutes: int = 30,
) -> NormalizedEvent | None:
    """Find best matching calendar event for a transcript."""
    candidates = []
    for event in events:
        if event.start_time is None:
            continue
        time_diff = abs((transcript_time - event.start_time).total_seconds() / 60)
        if time_diff <= time_window_minutes:
            title_score = SequenceMatcher(
                None, transcript_title.lower(), event.title.lower()
            ).ratio()
            candidates.append((event, title_score, time_diff))

    if not candidates:
        return None

    # Sort by title similarity (desc), then time proximity (asc)
    candidates.sort(key=lambda x: (-x[1], x[2]))
    return candidates[0][0]
```

### Pattern 4: Configurable Email Identification
**What:** Store sender/subject patterns in config.yaml rather than hardcoding
**When to use:** Discovering Gemini and Gong emails

```yaml
# config/config.yaml additions
transcripts:
  gemini:
    sender_patterns:
      - "calendar-notification@google.com"
      - "meetings-noreply@google.com"
    subject_patterns:
      - "Transcript"
      - "Meeting notes"
    query: "from:({senders}) subject:({subjects}) after:{date} before:{next_date}"
  gong:
    sender_patterns:
      - "notifications@gong.io"
      - "noreply@gong.io"
    subject_patterns:
      - "call"
      - "conversation"
    query: "from:({senders}) subject:({subjects}) after:{date} before:{next_date}"
  matching:
    time_window_minutes: 30
    include_unmatched_events: true
  preprocessing:
    strip_filler: true
    filler_patterns:
      - "\\b(um|uh|ah|er|like,?|you know,?|I mean,?)\\b"
```

### Anti-Patterns to Avoid
- **Hardcoding email patterns:** Sender addresses and subject patterns WILL change; put them in config.yaml
- **Fetching all emails then filtering:** Use Gmail query operators to filter server-side; much faster than client-side filtering
- **Ignoring multipart MIME:** Gmail messages are often multipart/mixed or multipart/alternative; must recurse through parts
- **Matching by exact title only:** Meeting titles in emails differ from calendar titles (abbreviations, "Re:", prefixes); use fuzzy matching
- **Dropping unmatched data silently:** User explicitly wants orphan transcripts and transcript-less events surfaced

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Gmail API access | Custom HTTP client | google-api-python-client | Already in project, handles auth, pagination, rate limiting |
| Base64 decoding | Manual byte manipulation | base64.urlsafe_b64decode (stdlib) | Gmail uses base64url variant specifically |
| Title similarity | Character-by-character comparison | difflib.SequenceMatcher (stdlib) | Handles insertions, deletions, transpositions |
| Date parsing from emails | Manual regex parsing | python-dateutil.parser.parse | Handles dozens of date formats including email headers |
| HTML stripping | Regex-based tag removal | html.parser or simple re.sub + html.unescape | Regex HTML parsing is fragile |

**Key insight:** This phase is primarily integration work (Gmail API + existing pipeline), not algorithmic innovation. Use stdlib and existing libraries.

## Common Pitfalls

### Pitfall 1: Gmail API Base64url vs Base64
**What goes wrong:** Standard base64.b64decode fails on Gmail body data
**Why it happens:** Gmail uses base64url encoding (- instead of +, _ instead of /) per RFC 4648
**How to avoid:** Always use `base64.urlsafe_b64decode()`, never `base64.b64decode()`
**Warning signs:** UnicodeDecodeError or garbled output when reading email bodies

### Pitfall 2: Multipart Email Body Extraction
**What goes wrong:** Empty transcript text despite email clearly containing content
**Why it happens:** Email body is nested in multipart MIME structure; checking only top-level payload misses it
**How to avoid:** Recursively walk payload.parts looking for text/plain or text/html
**Warning signs:** `payload.get("body", {}).get("data")` returns None for multipart messages

### Pitfall 3: Timezone Mismatch in Matching
**What goes wrong:** Transcripts fail to match calendar events even when times are close
**Why it happens:** Calendar events are in user timezone; email timestamps in UTC or sender timezone
**How to avoid:** Normalize all timestamps to the configured timezone (America/New_York) before matching
**Warning signs:** Matches work for some meetings but not others; evening meetings fail most

### Pitfall 4: Gmail API Rate Limits
**What goes wrong:** 429 errors or empty results during batch email retrieval
**Why it happens:** Gmail API has per-user rate limits; fetching many messages individually hits limits
**How to avoid:** Use batch requests or add small delays; fetch message list first, then batch get details
**Warning signs:** Intermittent empty results or HTTP 429 responses

### Pitfall 5: Email Pattern Changes
**What goes wrong:** Pipeline stops finding transcripts after a Google/Gong update
**Why it happens:** Email senders, subject lines, and body formats change without notice
**How to avoid:** Put patterns in config.yaml, log discovery stats, alert on zero-transcript days
**Warning signs:** transcript_count drops to 0 with no other explanation

### Pitfall 6: Duplicate Calendar Events from Multiple Calendars
**What goes wrong:** Same meeting appears twice in normalized output (once per calendar)
**Why it happens:** Shared calendars or delegated calendars contain duplicates of the same event
**How to avoid:** Deduplicate by event ID prefix (Google Calendar IDs are unique per event) or by (title + start_time + attendees) tuple
**Warning signs:** Meeting count is higher than expected; same meeting title appears consecutively

## Code Examples

### Gmail Service Build (Verified pattern from existing codebase)
```python
# Mirrors calendar.py pattern exactly
from googleapiclient.discovery import build

def build_gmail_service(creds):
    """Create a Gmail API v1 service instance."""
    return build("gmail", "v1", credentials=creds)
```

### Gmail Query Construction for Date Range
```python
def build_transcript_query(
    sender_patterns: list[str],
    subject_patterns: list[str],
    target_date: date,
) -> str:
    """Build Gmail search query for transcript emails on a specific date."""
    senders = " OR ".join(f"from:{s}" for s in sender_patterns)
    subjects = " OR ".join(f"subject:{s}" for s in subject_patterns)
    after = target_date.isoformat()
    before = (target_date + timedelta(days=1)).isoformat()
    return f"({senders}) ({subjects}) after:{after} before:{before}"
```

### Filler Text Stripping
```python
import re

FILLER_PATTERNS = [
    r'\b(?:um|uh|ah|er|mm|hmm|hm)\b',
    r'\b(?:like,?\s+)?you know,?\s*',
    r'\b(?:I mean,?\s*)',
    r'\b(?:sort of|kind of)\b',
    # Repeated words: "the the" -> "the"
    r'\b(\w+)\s+\1\b',
]

def strip_filler(text: str) -> str:
    """Remove filler words and repeated phrases from transcript text."""
    for pattern in FILLER_PATTERNS:
        text = re.sub(pattern, ' ', text, flags=re.IGNORECASE)
    # Collapse multiple spaces
    text = re.sub(r'\s{2,}', ' ', text).strip()
    return text
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| google-api-python-client < 2.0 | google-api-python-client >= 2.x with type hints | 2023 | Modern Python patterns, better IDE support |
| Manual OAuth flow | google-auth + google-auth-oauthlib | 2022 | Already using the current approach in Phase 0 |
| Separate email libraries (imaplib) | Gmail API via REST | Ongoing | API provides search, labels, and structured access |

**Deprecated/outdated:**
- oauth2client: Replaced by google-auth (project already uses google-auth)
- Python email.utils for Gmail: Gmail API provides structured headers directly; no need to parse raw RFC 2822

## Open Questions

1. **Exact Gemini transcript email format**
   - What we know: Google sends automated emails after meetings with transcript links; transcripts also appear in Drive and Calendar
   - What's unclear: Exact sender address, subject line format, and whether the email body contains the full transcript text or just a link to a Google Doc
   - Recommendation: Make the pattern configurable. Start with common patterns (calendar-notification@google.com, meetings-noreply@google.com), then have the user verify/adjust after first run. Log all candidate emails for debugging.

2. **Exact Gong email notification format**
   - What we know: Gong sends subscription emails with call highlights, summaries, and links to recordings. Sender is likely notifications@gong.io.
   - What's unclear: Exact subject line format, whether summary is in email body or requires clicking through, how much context the email summary provides
   - Recommendation: Same configurable approach. Gong emails likely contain enough summary text in the body for v1 purposes. Log full email for debugging.

3. **Gemini transcript: email body vs Google Doc link**
   - What we know: Transcripts are stored in Google Drive. Email may contain just a link.
   - What's unclear: Whether the email itself contains usable transcript text, or only a link that would require Drive API access
   - Recommendation: Try email body first. If body is just a link, fall back to logging a warning. Drive API integration is out of scope for this phase. The email body likely contains at least meeting notes/summary content even if the full transcript is in Drive.

## Sources

### Primary (HIGH confidence)
- Google Gmail API Reference — messages.list and messages.get methods, query operators, pagination
- Existing codebase — google-api-python-client patterns from calendar.py, OAuth from google_oauth.py
- Python stdlib — base64, email, re, difflib, html modules

### Secondary (MEDIUM confidence)
- Google Meet Help Center — transcript delivery behavior, timing, recipients
- Gong Help Center — email notification types and subscription settings

### Tertiary (LOW confidence)
- Exact email sender addresses and subject line formats for both Gemini and Gong (needs runtime verification)
- Whether Gemini email body contains full transcript text vs just a link

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already in project, well-documented APIs
- Architecture: HIGH - follows existing patterns from Phase 1, clean module boundaries
- Email patterns: LOW - sender/subject patterns need runtime verification from actual emails
- Matching algorithm: MEDIUM - standard approach but time window and scoring need tuning
- Pitfalls: HIGH - well-documented Gmail API gotchas (base64url, multipart, rate limits)

**Research date:** 2026-04-03
**Valid until:** 2026-05-03 (stable domain, but email patterns may change)
