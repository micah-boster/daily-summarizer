# Testing Patterns

**Analysis Date:** 2026-04-04

## Test Framework

**Runner:**
- pytest >= 9.0.2
- Config: No `pytest.ini`, `pyproject.toml`, or `conftest.py` with custom settings
- Dev dependency only (in `[dependency-groups] dev`)

**Assertion Library:**
- pytest native assertions (`assert`)
- No additional assertion libraries

**Run Commands:**
```bash
uv run pytest                    # Run all tests
uv run pytest tests/test_slack_ingest.py  # Run single file
uv run pytest -v                 # Verbose output
uv run pytest -x                 # Stop on first failure
```

## Test File Organization

**Location:**
- Separate `tests/` directory at project root (not co-located with source)

**Naming:**
- `test_{source_module_name}.py` -- maps 1:1 to source modules
- Example: `src/ingest/slack.py` -> `tests/test_slack_ingest.py`
- Example: `src/synthesis/synthesizer.py` -> `tests/test_synthesizer.py`

**Structure:**
```
tests/
  __init__.py
  test_calendar_ingest.py
  test_drive_ingest.py
  test_extractor.py
  test_gmail_ingest.py
  test_gong_ingest.py
  test_google_docs.py
  test_hubspot_ingest.py
  test_models.py
  test_monthly.py
  test_normalizer.py
  test_notifications.py
  test_priorities.py
  test_quality.py
  test_sidecar.py
  test_slack_discovery.py
  test_slack_ingest.py
  test_source_models.py
  test_synthesizer.py
  test_validator.py
  test_weekly.py
  test_writer.py
```

## Test Structure

**Suite Organization:**
Tests use two patterns:

1. **Class-based grouping** for related behavior:
```python
class TestShouldKeepMessage:
    """Tests for the should_keep_message filter function."""

    def test_normal_message_passes(self):
        msg = {"text": "Hey team, the deploy is done.", "user": "U123"}
        assert should_keep_message(msg) is True

    def test_noise_subtype_channel_join_filtered(self):
        msg = {"text": "joined #general", "subtype": "channel_join"}
        assert should_keep_message(msg) is False
```

2. **Module-level functions** for simpler tests:
```python
def test_format_extractions_for_prompt():
    """Verify formatting includes meeting title and non-empty categories."""
    extractions = [MeetingExtraction(...)]
    text = _format_extractions_for_prompt(extractions)
    assert "Team Sync" in text
```

**Prefer class-based grouping** when testing a single function with many edge cases. Use module-level functions for simpler one-off tests.

**Test Naming Convention:**
- `test_{behavior_description}` -- describes what is being verified
- Examples: `test_bot_message_allowed_via_allowlist`, `test_volume_cap_keeps_most_recent`
- Use descriptive names that read as specifications

**Docstrings:**
- Most test functions have a one-line docstring explaining intent
- Class-level docstrings describe the function under test

## Mocking

**Framework:** `unittest.mock` (stdlib)

**Patterns:**

1. **Patching external API clients** (most common):
```python
@patch("src.ingest.hubspot.build_hubspot_client")
def test_creates_source_items(self, mock_build):
    client = MagicMock()
    client.crm.deals.search_api.do_search.return_value = _mock_search_response([deal])
    items = _fetch_deals(client, 0, 100, config, stage_map, owner_map)
    assert len(items) >= 1
```

2. **Patching environment variables:**
```python
with patch.dict("os.environ", {"SLACK_BOT_TOKEN": "xoxb-env-token"}):
    client = build_slack_client()
    assert client.token == "xoxb-env-token"
```

3. **Patching Claude API calls:**
```python
@patch("src.synthesis.synthesizer.anthropic")
def test_synthesize_daily_with_slack_only(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="## Substance\n- item\n")]
    mock_client.messages.create.return_value = mock_response
```

4. **Patching individual functions (Google Docs):**
```python
@patch("src.ingest.google_docs._extract_doc_text", return_value="content")
@patch("src.ingest.google_docs._get_user_email", return_value="user@example.com")
def test_google_doc_produces_edit_source_item(self, mock_email, mock_extract):
    ...
```

**What to Mock:**
- External API clients (Slack SDK, HubSpot SDK, Google API, Anthropic)
- Environment variables (`os.environ`)
- File I/O only when testing write operations (use `tmp_path` fixture)

**What NOT to Mock:**
- Internal parsing/formatting functions -- test them directly
- Pydantic model construction -- test with real instances
- Pure logic functions (filtering, categorization, deduplication)

## Fixtures and Factories

**Test Data -- Helper Factory Functions:**
Each test module defines `_make_*` and `_mock_*` helpers at module level:

```python
def _make_timed_event(**overrides) -> dict:
    """Create a realistic mock timed event dict from Google Calendar API."""
    event = {
        "id": "evt_timed_1",
        "summary": "Team Standup",
        "start": {"dateTime": "2026-04-01T09:00:00-04:00"},
        "end": {"dateTime": "2026-04-01T09:30:00-04:00"},
        "attendees": [...],
    }
    event.update(overrides)
    return event
```

```python
def _mock_deal(deal_id: str, name: str, amount: str, stage: str, owner_id: str,
               stage_history: list | None = None):
    """Build a mock deal object matching HubSpot SDK response shape."""
    deal = MagicMock()
    deal.id = deal_id
    deal.properties = {"dealname": name, ...}
    return deal
```

**Pattern: Override defaults with kwargs:**
```python
def _make_slack_item(**overrides) -> SourceItem:
    defaults = {
        "id": "slack_C123_1234567890",
        "source_type": SourceType.SLACK_MESSAGE,
        ...
    }
    defaults.update(overrides)
    return SourceItem(**defaults)
```

**pytest Fixtures:**
Used sparingly, primarily for `tmp_path` (built-in) and shared synthesis objects:
```python
@pytest.fixture
def sample_synthesis() -> DailySynthesis:
    return DailySynthesis(date=date(2026, 4, 3), ...)

@pytest.fixture
def sample_extractions() -> list[MeetingExtraction]:
    return [MeetingExtraction(...)]
```

**Location:**
- Factory helpers defined at top of each test file (not in conftest.py)
- No shared `conftest.py` -- each test file is self-contained

## Coverage

**Requirements:** No coverage targets enforced. No coverage configuration detected.

**View Coverage:**
```bash
uv run pytest --cov=src         # Requires pytest-cov (not in deps)
```

## Test Types

**Unit Tests:**
- Majority of tests are unit tests
- Test individual functions in isolation
- Mock all external dependencies (APIs, file I/O)
- Focus on input/output behavior

**Integration Tests:**
- `test_normalizer.py::test_build_normalized_output_integration` -- full match/dedup/categorize pipeline
- `test_sidecar.py::TestBuildDailySidecar` -- tests sidecar construction from real model instances
- `test_writer.py` -- renders actual Jinja2 templates to `tmp_path` and verifies content

**E2E Tests:**
- Not present. No end-to-end tests that exercise the full pipeline with real API calls.

## Common Patterns

**Behavioral Testing (preferred):**
Tests verify WHAT the function produces, not HOW it works internally:
```python
def test_parse_table_format_commitments(self):
    result = _parse_synthesis_response(COMMITMENTS_TABLE_RESPONSE)
    assert len(result["commitments"]) == 2
    assert "John" in result["commitments"][0]
```

**Multi-line Response Constants:**
Claude API responses are defined as module-level string constants for parsing tests:
```python
FULL_SYNTHESIS_RESPONSE = """## Substance
- Q2 pipeline has 3 deals over $100k (Team Sync -- Tom, Sarah)

## Decisions
- Delay product launch to Q3 | Who: Sarah, Mike
...
"""
```

**Async Testing:**
- Not applicable. All code is synchronous.

**Error Testing:**
```python
def test_raises_without_token(self):
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValueError, match="No Slack bot token"):
            build_slack_client(token=None)
```

**File System Testing (using tmp_path):**
```python
def test_creates_file_at_correct_path(self, tmp_path: Path):
    synthesis = _make_synthesis()
    path = write_daily_summary(synthesis, tmp_path, TEMPLATE_DIR)
    assert path.exists()
    assert path == tmp_path / "daily" / "2026" / "04" / "2026-04-01.md"
```

**Edge Case Testing Pattern:**
Tests are thorough on edge cases. The `TestShouldKeepMessage` class in `tests/test_slack_ingest.py` has 30+ tests covering every filter branch including:
- Each noise subtype individually
- Bot allowlist behavior (in list, not in list, empty list)
- Each trivial word pattern
- Messages with files but no text
- Whitespace-only messages

## Test Gaps

**Not tested (or only minimally):**
- `src/main.py` -- the pipeline orchestrator has zero direct tests. All 330+ lines untested.
- `src/synthesis/weekly.py` -- `tests/test_weekly.py` exists but tests are minimal
- `src/synthesis/monthly.py` -- `tests/test_monthly.py` exists but tests are minimal
- `src/ingest/slack_discovery.py` -- interactive CLI flow not tested
- `src/notifications/slack.py` -- `tests/test_notifications.py` exists but webhook posting is hard to test
- `src/validation/daily_check.py` -- retry logic and side effects not unit tested
- `src/auth/google_oauth.py` -- OAuth flow not tested
- No tests for `config.yaml` validation or malformed config handling

**Mocking inconsistency:**
- HubSpot tests import inside test functions: `from src.ingest.hubspot import _fetch_deals` (works but inconsistent with other modules)
- Some test files import `pytest` inside methods: `import pytest` inside `test_raises_without_token`

---

*Testing analysis: 2026-04-04*
