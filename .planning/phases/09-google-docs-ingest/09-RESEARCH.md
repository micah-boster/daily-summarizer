# Phase 9: Google Docs Ingest - Research

**Researched:** 2026-04-04
**Domain:** Google Drive API v3 + Google Docs API v1 for edit detection and content extraction
**Confidence:** HIGH

## Summary

Phase 9 adds Google Docs/Sheets/Slides activity detection to the daily pipeline. The project already has `drive.readonly` scope in OAuth, a working Drive API client (`src/ingest/drive.py`), and a Docs API text extraction function (`_extract_doc_text`). The SourceItem model already defines `GOOGLE_DOC_EDIT` and `GOOGLE_DOC_COMMENT` source types.

The primary approach is to use the Drive API `files.list` with `modifiedTime` filtering to find documents the user edited on the target date, then use the Docs API for content extraction and the Drive API `comments.list` for comment/suggestion activity. The `drive.readonly` scope covers all needed operations (file listing, content reading, comment reading).

**Primary recommendation:** Reuse existing `build_drive_service` and `build_docs_service` from `src/ingest/drive.py`. Create a new `src/ingest/google_docs.py` module following the Slack ingestion pattern (fetch -> filter -> convert to SourceItem). Wire into synthesis via the same `slack_items`-style parameter pattern (rename or generalize to `source_items`).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Any modification counts — created, edited content, added comments, suggestions
- Include shared docs the user edited (not just owned docs)
- Exclude view-only activity — only docs with actual modifications
- No discovery mode needed — include all edited docs automatically per day
- Title + smart extract focused on what changed that day (new sections, edited paragraphs, key changes)
- Plain text extraction — no need to preserve heading hierarchy or formatting
- Truncate to first N chars for long docs (e.g., 2000-3000 chars) rather than LLM-summarizing each doc
- For Sheets and Slides: title + metadata only (file was edited, title, edit time) — no content extraction
- Include all comment activity on docs the user owns or is mentioned in, plus comments the user made
- Include resolved comments — they represent decisions made that day
- Treat suggestions (proposed edits) the same as regular comments
- Comment text included verbatim, truncated at a reasonable length per comment
- Config-based exclusion list for doc IDs or title patterns to skip (e.g., personal journal, 1:1 notes)
- No domain filtering — use whichever Google account is authenticated
- All Google Workspace file types included: Docs, Sheets, Slides
- Docs get full content extraction; Sheets/Slides get title + metadata only
- Attribution format: "(per Google Doc [title])" as specified in requirements

### Claude's Discretion
- Exact char limit for content truncation
- How to detect "what changed" (revision API vs full content diff vs recent content)
- SourceItem structure for doc items
- Error handling for inaccessible docs
- Comment truncation length

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DOCS-01 | Ingest list of documents the user edited on the target date with title and content extract | Drive API `files.list` with `modifiedTime` filter finds edited docs; Docs API extracts content; existing `_extract_doc_text` function reusable |
| DOCS-02 | Ingest comments and suggestions on docs the user owns or is mentioned in | Drive API `comments.list` returns comments including resolved ones; `includeSuggestions=true` parameter available; `fields` parameter gives comment text, author, timestamp |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| google-api-python-client | >=2.193.0 | Drive API v3 + Docs API v1 client | Already installed, used for calendar/gmail/drive ingestion |
| google-auth | >=2.49.1 | OAuth credentials | Already installed, handles token refresh |
| pydantic | >=2.12.5 | SourceItem model | Already used for all data models |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-dateutil | >=2.9.0 | Date parsing from API responses | Already installed, used throughout project |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Drive API `files.list` | Drive Activity API v2 | Activity API gives granular per-change details but requires separate scope (`drive.activity.readonly`), which would trigger re-auth. Files.list with `modifiedTime` is sufficient and works with existing `drive.readonly` scope |
| Docs API full content | Drive Revisions API | Revisions API could show diffs but requires parsing revision content format. Full content with truncation is simpler and matches user's preference for "smart extract" |

**Installation:**
```bash
# No new packages needed — all dependencies already installed
```

## Architecture Patterns

### Recommended Project Structure
```
src/
├── ingest/
│   ├── google_docs.py     # NEW: Google Docs/Sheets/Slides ingest module
│   └── drive.py           # EXISTING: Reuse build_drive_service, build_docs_service, _extract_doc_text
├── models/
│   └── sources.py         # EXISTING: SourceType.GOOGLE_DOC_EDIT, GOOGLE_DOC_COMMENT already defined
├── synthesis/
│   └── synthesizer.py     # MODIFY: Add google_docs_items parameter alongside slack_items
└── main.py                # MODIFY: Wire google_docs ingestion into daily pipeline
```

### Pattern 1: Ingest Module Pattern (Follow Slack)
**What:** Each ingest module follows the same pattern: build client -> fetch raw data -> filter -> convert to SourceItem list
**When to use:** All new data source ingestions
**Example:**
```python
# Follow the same pattern as slack.py
def fetch_google_docs_items(config: dict, creds: Credentials, target_date: date) -> list[SourceItem]:
    """Fetch edited docs and comments for a target date, return as SourceItems."""
    docs_config = config.get("google_docs", {})
    if not docs_config.get("enabled", False):
        return []

    drive_service = build_drive_service(creds)
    docs_service = build_docs_service(creds)

    # 1. Find docs modified on target_date
    edited_docs = _find_edited_docs(drive_service, target_date, docs_config)

    # 2. Extract content for Docs, metadata for Sheets/Slides
    doc_items = _extract_doc_items(drive_service, docs_service, edited_docs, docs_config)

    # 3. Find comments on docs user owns/is mentioned in
    comment_items = _fetch_comment_items(drive_service, target_date, docs_config)

    return doc_items + comment_items
```

### Pattern 2: Drive API File Search with Date Filtering
**What:** Use `files.list` with `modifiedTime` range to find docs edited on a specific date
**When to use:** Finding user-modified documents for a target date
**Example:**
```python
def _find_edited_docs(drive_service, target_date: date, config: dict) -> list[dict]:
    """Find all docs/sheets/slides the user modified on target_date."""
    date_str = target_date.isoformat()
    next_date_str = (target_date + timedelta(days=1)).isoformat()

    # MIME types for Google Workspace files
    mime_types = [
        "application/vnd.google-apps.document",      # Docs
        "application/vnd.google-apps.spreadsheet",    # Sheets
        "application/vnd.google-apps.presentation",   # Slides
    ]
    mime_filter = " or ".join(f"mimeType = '{m}'" for m in mime_types)

    query = (
        f"({mime_filter}) "
        f"and modifiedTime >= '{date_str}T00:00:00' "
        f"and modifiedTime < '{next_date_str}T00:00:00' "
        "and trashed = false"
    )

    results = []
    page_token = None
    while True:
        response = drive_service.files().list(
            q=query,
            fields="nextPageToken, files(id, name, mimeType, modifiedTime, owners, lastModifyingUser)",
            pageSize=100,
            pageToken=page_token,
        ).execute()
        results.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return results
```

### Pattern 3: Comment Retrieval
**What:** Use Drive API `comments.list` to get comments on documents
**When to use:** Retrieving comment and suggestion activity for DOCS-02
**Example:**
```python
def _fetch_comments_for_doc(drive_service, file_id: str, target_date: date) -> list[dict]:
    """Fetch comments (including resolved and suggestions) on a doc for target_date."""
    date_str = target_date.isoformat()
    next_date_str = (target_date + timedelta(days=1)).isoformat()

    comments = []
    page_token = None
    while True:
        response = drive_service.comments().list(
            fileId=file_id,
            fields="nextPageToken, comments(id, content, author, createdTime, modifiedTime, resolved, replies, quotedFileContent)",
            pageSize=100,
            pageToken=page_token,
            includeDeleted=False,
        ).execute()

        for comment in response.get("comments", []):
            # Include if created or modified on target date
            created = comment.get("createdTime", "")
            modified = comment.get("modifiedTime", "")
            if (created >= f"{date_str}T00:00:00" and created < f"{next_date_str}T00:00:00") or \
               (modified >= f"{date_str}T00:00:00" and modified < f"{next_date_str}T00:00:00"):
                comments.append(comment)

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return comments
```

### Anti-Patterns to Avoid
- **Fetching all files then filtering in Python:** Use Drive API query parameters to filter server-side. The API supports rich query syntax including date ranges and MIME types.
- **Re-implementing OAuth:** The project already has a working `load_credentials()` function. Reuse it.
- **Separate content extraction for each file type:** Only Docs need content extraction. Sheets/Slides get metadata only per user decision.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Date filtering | Manual timestamp comparison | Drive API `modifiedTime` query filter | Server-side filtering is faster and handles timezone correctly |
| Doc content extraction | Custom HTML parser | Existing `_extract_doc_text` in `src/ingest/drive.py` | Already handles structural elements, paragraphs, text runs |
| Comment pagination | Single-page fetch | Drive API pagination with `nextPageToken` | Some docs have 100+ comments |
| Exclusion matching | Ad-hoc string matching | Reuse pattern from Slack config exclusion | Consistent config approach across sources |

**Key insight:** The project already has 80% of the Google API infrastructure. This phase is primarily about wiring existing capabilities into a new module and extending the synthesis pipeline.

## Common Pitfalls

### Pitfall 1: modifiedTime includes view-only access
**What goes wrong:** `modifiedTime` on a shared doc updates when anyone modifies it, not just the authenticated user. Simply filtering by `modifiedTime` will include docs others edited.
**Why it happens:** Drive API `files.list` shows all accessible files, not just ones the user modified.
**How to avoid:** Use the `lastModifyingUser` field to check if the authenticated user was the last modifier. For docs modified by multiple people on the same day, this may miss the user's edits if someone else edited after. Alternative: also check `owners` field for owned docs, and accept that shared doc detection is best-effort with `modifiedTime` range.
**Warning signs:** Seeing documents in the summary that the user only viewed.

### Pitfall 2: Comments API requires file-level access
**What goes wrong:** To list comments on a doc, you need the file ID first. There's no "list all comments across all docs" endpoint.
**Why it happens:** Drive API comments are scoped per-file.
**How to avoid:** Strategy: (1) find docs the user owns or recently accessed, (2) query comments on each. For comment activity on docs the user is mentioned in, search for docs where the user is in the `permissions` list or where comments mention the user.
**Warning signs:** Missing comments on shared docs where the user was mentioned.

### Pitfall 3: drive.readonly scope limitations
**What goes wrong:** The `drive.readonly` scope allows reading files and metadata but NOT listing comments on files the user doesn't own.
**Why it happens:** Comment listing requires at least `drive.readonly` scope, which we have. But there's a nuance: the scope must be properly authorized for the specific API methods.
**How to avoid:** Verify that `comments.list` works with `drive.readonly` scope. If not, we may need `drive.file` scope. Testing will confirm. If scope expansion is needed, the user must re-auth (known blocker per STATE.md decision: "Google Docs reuses existing OAuth -- do NOT modify SCOPES").
**Warning signs:** 403 errors when calling `comments.list`.

### Pitfall 4: Rate limiting on large doc sets
**What goes wrong:** Users with many Google Docs modifications (20+ per day) could hit Drive API rate limits.
**Why it happens:** Content extraction requires one API call per doc (Docs API `documents.get`).
**How to avoid:** Add configurable `max_docs_per_day` limit (default 50). Process in order of most recently modified. Log a warning if limit is hit.
**Warning signs:** 429 errors from Google APIs.

### Pitfall 5: Suggestions vs Comments confusion
**What goes wrong:** Google Docs suggestions (proposed edits) are NOT regular comments. They use `quotedFileContent` and have different structure.
**Why it happens:** Comments and suggestions share the `comments.list` endpoint but suggestions include the `quotedFileContent` field.
**How to avoid:** Check for `quotedFileContent` field to identify suggestions. Treat them the same as comments per user decision, but include the quoted content for context.
**Warning signs:** Suggestions appearing without their proposed edit context.

## Code Examples

### Finding Docs Modified by the Authenticated User
```python
# Get the authenticated user's email for filtering
profile = drive_service.about().get(fields="user(emailAddress)").execute()
user_email = profile["user"]["emailAddress"]

# Filter files where lastModifyingUser matches
docs = _find_edited_docs(drive_service, target_date, config)
user_edited = [
    d for d in docs
    if d.get("lastModifyingUser", {}).get("emailAddress") == user_email
]
```

### Converting a Doc Edit to SourceItem
```python
def _doc_to_source_item(doc_meta: dict, content: str, config: dict) -> SourceItem:
    """Convert a Drive file metadata + content to a SourceItem."""
    max_content = config.get("google_docs", {}).get("content_max_chars", 2500)
    truncated = content[:max_content] if len(content) > max_content else content

    doc_name = doc_meta["name"]
    mime = doc_meta.get("mimeType", "")

    # Determine content type label
    if "spreadsheet" in mime:
        file_type = "Google Sheet"
    elif "presentation" in mime:
        file_type = "Google Slides"
    else:
        file_type = "Google Doc"

    return SourceItem(
        id=doc_meta["id"],
        source_type=SourceType.GOOGLE_DOC_EDIT,
        content_type=ContentType.EDIT,
        title=doc_name,
        timestamp=dateutil_parse(doc_meta["modifiedTime"]),
        content=truncated,
        participants=[],
        source_url=f"https://docs.google.com/document/d/{doc_meta['id']}",
        display_context=f"Google Doc {doc_name}",
    )
```

### Converting a Comment to SourceItem
```python
def _comment_to_source_item(comment: dict, doc_name: str, file_id: str) -> SourceItem:
    """Convert a Drive comment to a SourceItem."""
    author = comment.get("author", {}).get("displayName", "Unknown")
    content = comment.get("content", "")
    quoted = comment.get("quotedFileContent", {}).get("value", "")

    # Build rich content: quoted text + comment
    full_content = f'"{quoted}" — {content}' if quoted else content

    return SourceItem(
        id=comment["id"],
        source_type=SourceType.GOOGLE_DOC_COMMENT,
        content_type=ContentType.COMMENT,
        title=f"Comment by {author} on {doc_name}",
        timestamp=dateutil_parse(comment["createdTime"]),
        content=full_content[:500],  # Truncate per config
        participants=[author],
        source_url=f"https://docs.google.com/document/d/{file_id}",
        display_context=f"Google Doc {doc_name}",
    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Google Drive API v2 | Google Drive API v3 | 2015 | v3 is the only supported version; v2 deprecated |
| Separate OAuth for each API | Single token with multiple scopes | N/A | Project already does this correctly |

**Deprecated/outdated:**
- Drive API v2: fully replaced by v3. All v2 endpoints are deprecated.
- `drive.appdata` scope: not applicable here. `drive.readonly` is the correct scope.

## Open Questions

1. **Does `comments.list` work with `drive.readonly` scope on shared docs?**
   - What we know: `drive.readonly` grants read access to all Drive files and metadata. Comments are metadata.
   - What's unclear: Some Google API docs suggest comment access may require file-level permissions beyond just drive scope.
   - Recommendation: Test with a shared doc. If 403, fall back to only fetching comments on owned docs. Do NOT expand scopes (per STATE.md decision).

2. **Best approach for "what changed" detection**
   - What we know: User wants "smart extract focused on what changed that day." Options: (a) full content with truncation, (b) Drive Revisions API to get specific changes, (c) both.
   - What's unclear: Whether Revisions API provides useful diffs vs just versioned snapshots.
   - Recommendation: Start with full content extraction + truncation (option a). This is simpler, already works with `_extract_doc_text`, and matches the user's stated preference for truncation over LLM summarization. Revisions API can be added later if content extracts are too noisy.

3. **How to find docs where user is mentioned in comments (not owner)**
   - What we know: There's no "comments mentioning me" API endpoint across all files.
   - What's unclear: Efficient way to find docs where user was mentioned in comments.
   - Recommendation: Focus on (a) docs the user edited (already found via `modifiedTime`), and (b) docs the user owns. Comments on shared docs where user is only mentioned but didn't edit may be missed. This is acceptable for v1 and can be improved later.

## Sources

### Primary (HIGH confidence)
- Google Drive API v3 reference: files.list, comments.list endpoints
- Existing codebase: `src/ingest/drive.py` for Drive/Docs service construction and text extraction
- Existing codebase: `src/models/sources.py` for SourceItem, SourceType definitions
- Existing codebase: `src/ingest/slack.py` for ingest module pattern

### Secondary (MEDIUM confidence)
- Google Drive API scope documentation for `drive.readonly` capabilities
- Google Docs API v1 for document content structure

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already installed and in use
- Architecture: HIGH - follows established ingest module pattern from Slack phase
- Pitfalls: MEDIUM - comment scope access needs runtime verification

**Research date:** 2026-04-04
**Valid until:** 2026-05-04 (Google APIs are stable, 30-day validity)
