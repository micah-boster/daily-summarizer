# Coding Conventions

**Analysis Date:** 2026-04-04

## Naming Patterns

**Files:**
- Use `snake_case.py` for all modules: `slack_filter.py`, `google_docs.py`, `slack_discovery.py`
- Test files: `test_{module_name}.py` co-located in `tests/` directory (not alongside source)
- Config files: `snake_case.yaml` in `config/` directory
- Templates: `{cadence}.md.j2` in `templates/` directory (e.g., `daily.md.j2`, `weekly.md.j2`)

**Functions:**
- Use `snake_case` for all functions: `fetch_slack_items()`, `build_normalized_output()`
- Private/internal functions prefixed with underscore: `_resolve_channel_name()`, `_parse_synthesis_response()`
- Builder/factory functions use `build_` prefix: `build_slack_client()`, `build_calendar_service()`, `build_daily_sidecar()`
- Fetch functions use `fetch_` prefix: `fetch_events_for_date()`, `fetch_hubspot_items()`
- Parse functions use `parse_` prefix: `parse_gemini_transcript()`, `parse_drive_transcript()`

**Variables:**
- Use `snake_case` for all variables: `slack_items`, `target_date`, `owner_map`
- Constants use `UPPER_SNAKE_CASE`: `DEFAULT_MODEL`, `MAX_BLOCK_TEXT`, `NOISE_SUBTYPES`
- Module-level caches prefixed with underscore: `_user_cache`, `_channel_name_cache`, `_user_email_cache`

**Types/Classes:**
- Use `PascalCase` for all classes: `SourceItem`, `NormalizedEvent`, `DailySynthesis`
- Pydantic models use `PascalCase`: `ExtractionItem`, `MeetingExtraction`, `WeeklyThread`
- Enums use `PascalCase` with `UPPER_SNAKE_CASE` members: `SourceType.SLACK_MESSAGE`, `ContentType.STAGE_CHANGE`
- All enums extend `StrEnum` (not plain `Enum`)

## Code Style

**Formatting:**
- No explicit formatter configuration (no `.prettierrc`, `black.toml`, `ruff.toml`, etc.)
- Consistent 4-space indentation throughout
- Line lengths vary but generally stay under 120 characters
- Trailing commas used in multi-line collections and function signatures

**Linting:**
- No explicit linter configuration detected
- Code is clean and consistent despite no enforced tooling
- All files use `from __future__ import annotations` at the top for PEP 604 union syntax (`str | None`)

**Type Hints:**
- Comprehensive type hints on all function signatures (parameters and return types)
- Uses modern Python 3.12 syntax: `list[str]`, `dict[str, str]`, `str | None`
- Pydantic `Field(default_factory=list)` pattern for mutable defaults
- One instance of `typing.Any` in `src/ingest/google_docs.py` for Google API service objects
- Return types specified on all public functions; private functions also typed

## Import Organization

**Order:**
1. `from __future__ import annotations` (always first, present in every file)
2. Standard library imports (`datetime`, `json`, `logging`, `re`, `pathlib`)
3. Third-party imports (`anthropic`, `pydantic`, `slack_sdk`, `google.*`, `jinja2`)
4. Local imports (`from src.models.sources import ...`, `from src.ingest.slack import ...`)

**Path Style:**
- Absolute imports from `src` package: `from src.models.events import DailySynthesis`
- No path aliases configured
- Conditional/lazy imports inside functions in `src/main.py` for optional dependencies

**Lazy Import Pattern (main.py):**
- Modules with heavy external dependencies are imported inside function bodies
- Pattern: `from src.ingest.slack import fetch_slack_items` inside `run_daily()`
- Purpose: allows pipeline to partially run if some integrations are unavailable
- Use this pattern only in orchestrator code (`main.py`), not in library modules

## Error Handling

**Patterns:**
- **Graceful degradation in pipeline orchestrator:** Every ingest stage in `src/main.py` is wrapped in `try/except Exception` with `logger.warning()`. Pipeline continues even if individual stages fail.
- **Specific exceptions in library code:** Ingest modules catch specific exceptions (e.g., `SlackApiError`, `ValueError`) and log warnings, then return empty results or skip items.
- **Never raise in ingest modules:** All ingest `fetch_*` entry points return empty lists on failure, never propagate exceptions to the caller.
- **Bare `except Exception` in main.py** is intentional for resilience, but library modules should catch specific exceptions.

**Anti-patterns to avoid:**
- Do NOT use bare `except:` (always `except Exception`)
- Do NOT silently swallow exceptions without logging
- Every `except` block must include a `logger.warning()` or `logger.error()` call

**Error hierarchy pattern:**
```python
try:
    result = do_work()
except SpecificApiError as e:
    logger.warning("Descriptive message: %s", e)
    return []  # or continue
except Exception as e:
    logger.warning("Unexpected error in context: %s", e)
    return []
```

## Logging

**Framework:** Python stdlib `logging`

**Setup:** Configured once in `src/main.py`:
```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)
```

**Patterns:**
- Every module creates its own logger: `logger = logging.getLogger(__name__)`
- Use `logger.info()` for normal operational events (fetched N items, wrote file)
- Use `logger.warning()` for recoverable errors and degraded functionality
- Use `logger.error()` only for fatal errors in the day's processing
- Use `logger.debug()` for verbose operational detail (skip reasons, cache hits)
- Use `%s` string formatting, NOT f-strings in log calls: `logger.info("Fetched %d items", count)`

## Comments

**When to Comment:**
- Module-level docstrings on every file describing the module's purpose
- Function docstrings using Google-style format on all public functions
- Private functions also have docstrings (consistent throughout)
- Inline comments for non-obvious logic (e.g., "Skip parent message (first item on first page)")

**Docstring Format (Google style):**
```python
def function_name(param1: str, param2: int) -> list[str]:
    """One-line summary of what the function does.

    Extended description if needed.

    Args:
        param1: Description of param1.
        param2: Description of param2.

    Returns:
        Description of return value.

    Raises:
        ValueError: When something is wrong.
    """
```

## Function Design

**Size:** Functions are moderate-sized (20-60 lines typical). The largest function is `run_daily()` in `src/main.py` at ~330 lines (this is a concern -- see CONCERNS.md).

**Parameters:**
- Use `config: dict` as the standard way to pass pipeline configuration
- Use Pydantic models for structured data transfer between modules
- Optional parameters use `| None = None` pattern
- Use keyword arguments for clarity in calls with 3+ parameters

**Return Values:**
- Return empty list `[]` on failure from fetch functions
- Return `None` for single-item lookups that fail
- Return tuple of `(result, metadata)` for functions needing two outputs (e.g., `build_normalized_output() -> tuple[dict, list[dict]]`)
- Return `dict` for synthesis results (not yet Pydantic models -- see CONCERNS.md)

## Module Design

**Exports:**
- No explicit `__all__` definitions in any module
- `__init__.py` files are all empty (no re-exports)
- Import directly from the module file: `from src.ingest.slack import fetch_slack_items`

**Barrel Files:**
- Not used. Always import from the specific module.

**Module Entry Point Pattern:**
Each ingest module follows this pattern:
1. `build_*_client()` - Create authenticated API client
2. Internal `_fetch_*()` functions for each data type
3. `fetch_*_items()` - Main entry point that orchestrates all fetches and returns `list[SourceItem]`

**Anthropic Client Pattern:**
Claude API calls create a new `anthropic.Anthropic()` client per call. This is intentional (stateless) but means no client reuse:
```python
client = anthropic.Anthropic()
response = client.messages.create(
    model=model,
    max_tokens=max_tokens,
    messages=[{"role": "user", "content": prompt}],
)
response_text = response.content[0].text
```

## Config Access Pattern

Configuration is passed as a plain `dict` loaded from YAML. Access nested values with `.get()` chains and defaults:
```python
slack_config = config.get("slack", {})
max_per_channel = slack_config.get("max_messages_per_channel", 100)
```

No Pydantic validation on config load -- see CONCERNS.md for improvement opportunity.

## Pydantic Usage

- All data models use Pydantic v2 `BaseModel`
- Use `Field(default_factory=list)` for mutable defaults
- Use `model_dump_json()` and `model_validate_json()` for serialization
- Use `ConfigDict(extra="forbid")` on models that need strict validation (e.g., `ExtractedCommitment`)
- Enums extend `StrEnum` for automatic string serialization

---

*Convention analysis: 2026-04-04*
