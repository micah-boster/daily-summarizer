# STACK.md -- Work Intelligence / Daily Synthesis Pipeline

**Project:** Work Intelligence System (Daily Summarizer)
**Research date:** 2026-03-23
**Dimension:** Technology stack for a Python-based personal work intelligence pipeline
**Confidence note:** Web search/fetch were unavailable during this research session. Versions are based on known stable releases as of early 2026. Each recommendation includes a confidence level. **Verify versions with `pip index versions <package>` before pinning.**

---

## Executive Summary

The stack is deliberately simple: Google's official Python client libraries for API access, `httpx` for Gong's REST API, Pydantic for data modeling, Jinja2 for markdown templating, and Claude (via plan limits, not API) for LLM synthesis. No frameworks, no ORMs, no vector databases, no workflow engines. The pipeline is a sequential Python script triggered by Cowork scheduled tasks.

---

## 1. Runtime & Language

| Component | Recommendation | Version | Confidence | Rationale |
|-----------|---------------|---------|------------|-----------|
| Python | CPython | `>=3.11, <3.13` | HIGH | 3.11+ for `tomllib`, improved error messages, and `StrEnum`. Avoid 3.13 until ecosystem catches up. 3.12 is the sweet spot. |
| Package manager | `uv` | `>=0.5` | HIGH | Faster than pip/poetry, handles venvs, lockfiles, and Python version management in one tool. Claude Code already works well with uv. |
| Virtual env | uv-managed venv | -- | HIGH | `uv venv` + `uv pip install`. No conda, no pyenv -- uv replaces both. |

### What NOT to use
- **Poetry**: Slower, heavier, and uv has surpassed it for most workflows.
- **Conda**: Overkill for a pure-Python project with no native dependencies.
- **Python 3.10 or below**: Missing `tomllib`, worse error messages, no `StrEnum`.

---

## 2. Google API Access (Calendar + Gmail)

| Component | Package | Version | Confidence | Rationale |
|-----------|---------|---------|------------|-----------|
| Google API client | `google-api-python-client` | `>=2.150.0` | MEDIUM (verify) | Official Google client. Handles discovery-based API access for both Gmail and Calendar. Mature, well-documented, stable API surface. |
| Auth library | `google-auth` | `>=2.36.0` | MEDIUM (verify) | Core auth library for Google APIs. Handles OAuth2 tokens, service accounts, refresh logic. |
| OAuth flow | `google-auth-oauthlib` | `>=1.2.0` | MEDIUM (verify) | Desktop OAuth flow for first-time auth. Only needed for initial token generation -- after that, refresh tokens handle reauth. |
| HTTP transport | `google-auth-httplib2` | `>=0.2.0` | MEDIUM (verify) | Required transport adapter for google-api-python-client. |

### Auth strategy
1. Run OAuth desktop flow once to get refresh token
2. Store `token.json` locally (add to `.gitignore`)
3. Pipeline loads token, auto-refreshes, and uses it for both Gmail and Calendar APIs
4. Scopes needed: `gmail.readonly`, `calendar.readonly`

### Why this and not alternatives
- **`google-cloud-*` libraries**: Those are for GCP services (BigQuery, Cloud Storage, etc.), not Gmail/Calendar consumer APIs.
- **`gspread` / `pygsheets`**: Wrong abstraction. We need raw Gmail and Calendar API access, not a convenience wrapper for Sheets.
- **`simplegmail`**: Abandoned, limited, doesn't support Calendar.
- **Direct REST with httpx**: Possible but you'd reimplement token refresh, discovery, pagination. The official client handles all of this.

---

## 3. Gong API Access

| Component | Package | Version | Confidence | Rationale |
|-----------|---------|---------|------------|-----------|
| HTTP client | `httpx` | `>=0.27.0` | MEDIUM (verify) | Modern async-capable HTTP client. Used for direct REST calls to Gong API. |

### Why httpx, not a Gong SDK
- **There is no official Gong Python SDK.** Gong provides a REST API with OpenAPI spec but no maintained Python client.
- **Community SDKs (`gong-python-client`, etc.)**: Poorly maintained, low download counts, lag behind API changes. Do not use.
- **httpx over requests**: httpx has a cleaner API, native async support (useful if pipeline grows), HTTP/2 support, and is actively maintained. `requests` works fine too but httpx is the modern default.

### Gong API specifics
- Auth: Bearer token (API key from Gong admin settings). Much simpler than Google OAuth.
- Key endpoints: `/v2/calls` (list calls), `/v2/calls/{id}/transcript` (get transcript)
- Rate limits: 3 requests/second for most endpoints. Build in basic backoff.
- Transcripts come as structured JSON with speaker labels and timestamps -- no parsing needed.

### Alternative approach: Gong email delivery
- Gong can email transcript summaries. If the API is too restrictive or requires admin access you don't have, parse transcripts from Gmail instead.
- This means Gong transcripts arrive via the Gmail ingestion path, not a separate API.
- Decision: **Try API first; fall back to Gmail-based ingestion if blocked.**

---

## 4. Data Modeling & Validation

| Component | Package | Version | Confidence | Rationale |
|-----------|---------|---------|------------|-----------|
| Data models | `pydantic` | `>=2.9.0` | HIGH | Type-safe data classes with validation, serialization, and JSON schema generation. Models calendar events, email messages, transcripts, and synthesis output. |

### Why Pydantic
- Google API responses are raw dicts. Pydantic converts them to typed, validated objects immediately at the ingestion boundary.
- Synthesis output needs a defined schema (sections, source links, timestamps). Pydantic enforces that.
- `.model_dump()` gives clean dicts for template rendering. `.model_dump_json()` enables optional JSON storage later.
- V2 is significantly faster than V1 and has cleaner API.

### What NOT to use
- **dataclasses**: No validation, no serialization, no schema generation. Fine for simple cases but this project needs validation at API boundaries.
- **attrs**: Good library but Pydantic has won the ecosystem. Better tooling, documentation, and LLM familiarity.
- **TypedDict**: No runtime validation. Useful for typing but not for data integrity.

---

## 5. Email & Transcript Parsing

| Component | Package | Version | Confidence | Rationale |
|-----------|---------|---------|------------|-----------|
| Email parsing | `python-email` (stdlib) | built-in | HIGH | `email.message` from stdlib handles MIME parsing, attachment extraction, encoding. No external dependency needed. |
| HTML stripping | `beautifulsoup4` | `>=4.12.0` | HIGH | Extracts text from HTML email bodies. Also useful for cleaning up any HTML in transcript content. |
| HTML parser | `lxml` | `>=5.3.0` | MEDIUM (verify) | Fast parser backend for BeautifulSoup. Falls back to stdlib `html.parser` if lxml is problematic. |
| Date parsing | `python-dateutil` | `>=2.9.0` | HIGH | Parses varied date formats from email headers and API responses. `dateutil.parser.parse()` handles most formats without custom logic. |
| Timezone handling | `zoneinfo` (stdlib) | built-in | HIGH | Python 3.11+ has `zoneinfo` in stdlib. No need for `pytz`. |

### Transcript processing strategy

**Gemini transcripts (via Gmail/Calendar):**
- Arrive as email attachments or inline content in Gmail
- Format varies: sometimes plain text, sometimes HTML, sometimes PDF attachment
- Strategy: extract via Gmail API attachment download, then parse based on MIME type
- May need `PyPDF2` (`>=3.0.0`) if transcripts arrive as PDF -- add only if needed

**Gong transcripts (via API):**
- Structured JSON with speaker labels, timestamps, and utterances
- No parsing needed -- map directly to Pydantic models

**Gong transcripts (via email fallback):**
- HTML email with structured summary
- BeautifulSoup extracts the text content
- Less structured than API response but workable

### What NOT to use
- **`mailparser`**: Thin wrapper around stdlib email. Adds dependency without adding value.
- **`flanker`**: Email parsing library from Mailgun. Overkill for read-only parsing.
- **`textract`**: Heavy dependency for text extraction from documents. Only add if PDF transcripts become common.

---

## 6. LLM Synthesis (Claude via Plan Limits)

| Component | Approach | Confidence | Rationale |
|-----------|----------|------------|-----------|
| LLM provider | Claude (Anthropic) via Claude Code | HIGH | Decided in architecture. Uses plan limits, not API. Claude Code executes the synthesis step within the pipeline. |
| Execution model | Cowork scheduled task triggers Claude Code | HIGH | Cowork handles scheduling. Claude Code runs the Python pipeline which includes synthesis prompts. |

### How synthesis works without API keys

This is the most unconventional part of the stack. The pipeline does NOT call the Anthropic API directly. Instead:

1. Cowork scheduled task fires daily
2. The task runs a Claude Code session
3. Claude Code executes Python scripts that pull data from Gmail, Calendar, Gong
4. The pulled data is formatted into context
5. Claude (within the Code session) processes the context and produces structured synthesis
6. Python scripts write the synthesis output to markdown files

**Implication:** The synthesis step is Claude Code reading/writing files, not a Python `anthropic.Client()` call. The pipeline script prepares the data; Claude Code does the reasoning.

### What NOT to use
- **`anthropic` Python SDK**: Would require API keys and per-token billing. Explicitly out of scope for v1.
- **`openai` SDK**: Wrong provider, wrong cost model.
- **LangChain / LlamaIndex**: Massive over-engineering for a single-provider, single-task pipeline. These frameworks add complexity without value when you have one LLM doing one job.
- **Semantic Kernel**: Same problem. Framework overhead for a simple pipeline.

### Graduation path
If the system proves out and needs to run headlessly (no Cowork/Claude Code), switch to the `anthropic` Python SDK (`>=0.39.0`). The data preparation code stays identical; only the synthesis step changes from "Claude Code processes this" to "API call processes this."

---

## 7. Markdown Output & Templating

| Component | Package | Version | Confidence | Rationale |
|-----------|---------|---------|------------|-----------|
| Templating | `jinja2` | `>=3.1.4` | HIGH | Industry-standard Python templating. Renders daily summary templates from structured data. Supports template inheritance for daily/weekly/monthly variants. |

### Why Jinja2 and not string formatting
- Templates live as separate `.md.j2` files that can be iterated independently of code
- Conditional sections (e.g., only show "Decisions" if decisions exist)
- Loop constructs for variable-length sections (multiple meetings, multiple action items)
- Template inheritance: weekly template extends daily, monthly extends weekly

### What NOT to use
- **f-strings / `.format()`**: Fine for simple cases but unmaintainable for multi-section documents with conditional content.
- **Mako**: Less common, worse documentation, no advantage over Jinja2 for this use case.
- **Markdown libraries (`markdown`, `mistune`)**: These convert markdown to HTML. We're generating markdown, not consuming it.

---

## 8. File Storage & Organization

| Component | Approach | Confidence | Rationale |
|-----------|----------|------------|-----------|
| Storage format | Flat markdown files | HIGH | Decided in architecture. Human-readable, git-friendly, no database overhead. |
| Directory structure | Date-based hierarchy | HIGH | `output/daily/2026/03/2026-03-23.md` pattern. Predictable, filesystem-browsable. |
| Config format | TOML | HIGH | `tomllib` is in stdlib as of 3.11. Cleaner than YAML, simpler than JSON for config. |

### File organization

```
output/
  daily/
    2026/
      03/
        2026-03-23.md       # Daily synthesis
        2026-03-23.json     # Structured data (optional, for programmatic access)
  weekly/
    2026/
      2026-W13.md           # Weekly roll-up
  raw/
    2026/
      03/
        2026-03-23/
          calendar.json     # Raw calendar data (for debugging/reprocessing)
          emails.json       # Raw email data
          transcripts/      # Raw transcript files
```

### What NOT to use (yet)
- **SQLite**: Adds query capability but premature before knowing what queries are needed. Add in Phase 3 if roll-ups need structured queries.
- **Vector database (ChromaDB, Qdrant, etc.)**: Semantic search is a Phase 4+ feature. Don't add infrastructure for future requirements.
- **Obsidian vault**: Possible future destination but coupling to Obsidian's conventions now constrains storage decisions. Write plain markdown that could go anywhere.

---

## 9. Development & Testing

| Component | Package | Version | Confidence | Rationale |
|-----------|---------|---------|------------|-----------|
| Testing | `pytest` | `>=8.3.0` | HIGH | Standard Python test framework. |
| Test fixtures | `pytest-fixtures` (built-in) | -- | HIGH | Fixture-based test data for API response mocking. |
| HTTP mocking | `respx` | `>=0.21.0` | MEDIUM (verify) | Mocks httpx requests. Used for testing Gong API calls without hitting real endpoints. |
| Google API mocking | manual fixtures | -- | HIGH | Google API client is best tested with fixture JSON files loaded into mock discovery. `unittest.mock.patch` on the service object. |
| Linting | `ruff` | `>=0.8.0` | HIGH | Replaces flake8, isort, black in one tool. Fast, opinionated, minimal config. |
| Type checking | `pyright` | `>=1.1.390` | MEDIUM (verify) | Works with Pydantic v2 out of the box. Faster than mypy for iterative development. |

### What NOT to use
- **`tox`**: Overkill for a single-Python-version personal project.
- **`black`**: Ruff replaces it. One fewer tool.
- **`flake8` / `isort`**: Same -- ruff handles all of this.
- **`mypy`**: Slower than pyright, worse Pydantic v2 support.

---

## 10. Complete Dependency List

### Core (required)

```toml
[project]
requires-python = ">=3.11,<3.13"

dependencies = [
    "google-api-python-client>=2.150.0",
    "google-auth>=2.36.0",
    "google-auth-oauthlib>=1.2.0",
    "google-auth-httplib2>=0.2.0",
    "httpx>=0.27.0",
    "pydantic>=2.9.0",
    "beautifulsoup4>=4.12.0",
    "python-dateutil>=2.9.0",
    "jinja2>=3.1.4",
]
```

### Development

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "respx>=0.21.0",
    "ruff>=0.8.0",
    "pyright>=1.1.390",
]
```

### Conditional (add only if needed)

| Package | When to add | Version |
|---------|-------------|---------|
| `lxml` | If BeautifulSoup parsing is too slow with `html.parser` | `>=5.3.0` |
| `PyPDF2` | If Gemini transcripts arrive as PDF attachments | `>=3.0.0` |
| `anthropic` | If graduating from plan limits to API-based execution | `>=0.39.0` |

---

## 11. What This Stack Deliberately Excludes

| Excluded | Why |
|----------|-----|
| **LangChain / LlamaIndex** | Framework overhead for a single-LLM, single-task pipeline. Adds abstraction layers that obscure what's happening. When the pipeline is "pull data, format prompt, get response, write file," a framework adds complexity without value. |
| **Celery / RQ / task queues** | Pipeline is a single sequential batch job. No concurrency, no distributed processing, no queue needed. Cowork handles scheduling. |
| **FastAPI / Flask** | No web server needed. This is a batch pipeline, not a service. |
| **Docker** | Runs on Micah's local machine via Claude Code. Containerization adds deployment complexity for zero benefit in v1. |
| **Any vector database** | Semantic search / RAG is a Phase 4+ feature. Don't add infrastructure for speculative requirements. |
| **Any ORM (SQLAlchemy, etc.)** | No database in v1. Flat files. |
| **`requests`** | httpx is the modern replacement. One HTTP client, not two. |
| **YAML for config** | TOML is in stdlib (3.11+), cleaner syntax, no `ruamel.yaml` / `pyyaml` dependency debates. |
| **Async (asyncio)** | Pipeline is sequential batch processing. Async adds complexity for no throughput benefit when you're making a few dozen API calls in series. Consider only if API pagination becomes a bottleneck. |

---

## 12. Confidence Summary

| Category | Confidence | Note |
|----------|------------|------|
| Runtime (Python 3.12, uv) | HIGH | Well-established, no risk |
| Google API libraries | MEDIUM | Library choices are correct; exact version pins need verification via PyPI |
| httpx for Gong | MEDIUM | Correct approach; verify Gong API access/permissions are available |
| Pydantic v2 | HIGH | Standard choice, well-established |
| Email parsing (stdlib + bs4) | HIGH | Proven approach |
| Jinja2 templating | HIGH | Standard choice |
| Claude via plan limits (not API) | HIGH for concept, MEDIUM for reliability | Cowork scheduling reliability is the key unknown. The Cowork spike (from decisions doc) validates this. |
| Flat file storage | HIGH | Correct for v1; migration path to DB is clean |
| Dev tooling (ruff, pyright, pytest) | HIGH | Standard modern Python tooling |

---

## 13. Version Verification Checklist

Run this after creating the project to pin exact versions:

```bash
# Verify latest stable versions
uv pip index versions google-api-python-client
uv pip index versions google-auth
uv pip index versions google-auth-oauthlib
uv pip index versions httpx
uv pip index versions pydantic
uv pip index versions beautifulsoup4
uv pip index versions jinja2
uv pip index versions python-dateutil
uv pip index versions ruff
uv pip index versions pyright
uv pip index versions pytest
uv pip index versions respx
```

**Minimum versions in this document are based on known stable releases as of early 2026. They may be slightly behind current. Always verify before pinning.**

---

*Research produced: 2026-03-23. Feeds into roadmap and project scaffolding.*
