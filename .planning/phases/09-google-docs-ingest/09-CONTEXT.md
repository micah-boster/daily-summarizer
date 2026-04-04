# Phase 9: Google Docs Ingest - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Daily summaries include documents the user created or edited that day, with content extracts and comment/suggestion activity. Covers all Google Workspace file types (Docs, Sheets, Slides). Cross-source deduplication and commitment extraction are separate phases (Phase 10).

</domain>

<decisions>
## Implementation Decisions

### Edit Detection Scope
- Any modification counts — created, edited content, added comments, suggestions
- Include shared docs the user edited (not just owned docs)
- Exclude view-only activity — only docs with actual modifications
- No discovery mode needed — include all edited docs automatically per day

### Content Extraction
- Title + smart extract focused on what changed that day (new sections, edited paragraphs, key changes)
- Plain text extraction — no need to preserve heading hierarchy or formatting
- Truncate to first N chars for long docs (e.g., 2000-3000 chars) rather than LLM-summarizing each doc
- For Sheets and Slides: title + metadata only (file was edited, title, edit time) — no content extraction

### Comments & Suggestions
- Include all comment activity on docs the user owns or is mentioned in, plus comments the user made
- Include resolved comments — they represent decisions made that day
- Treat suggestions (proposed edits) the same as regular comments
- Comment text included verbatim, truncated at a reasonable length per comment

### Doc Filtering & Privacy
- Config-based exclusion list for doc IDs or title patterns to skip (e.g., personal journal, 1:1 notes)
- No domain filtering — use whichever Google account is authenticated
- All Google Workspace file types included: Docs, Sheets, Slides
- Docs get full content extraction; Sheets/Slides get title + metadata only

### Claude's Discretion
- Exact char limit for content truncation
- How to detect "what changed" (revision API vs full content diff vs recent content)
- SourceItem structure for doc items
- Error handling for inaccessible docs
- Comment truncation length

</decisions>

<specifics>
## Specific Ideas

- Follow the same SourceItem pattern established in Phase 6 for doc items
- Attribution format: "(per Google Doc [title])" as specified in requirements
- Config exclusion list should follow the same pattern as Slack channel curation config

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 09-google-docs-ingest*
*Context gathered: 2026-04-04*
