"""Tests for evidence-only language validator."""

from src.synthesis.validator import is_clean, validate_evidence_only, validate_source_attribution


# --- Positive cases: violations SHOULD be caught ---


def test_catches_performance_adjectives():
    """Evaluative adjectives applied to work should be caught."""
    violations = validate_evidence_only(
        "Sarah did an excellent job leading the discussion"
    )
    assert len(violations) > 0
    assert any("excellent" in v.text.lower() for v in violations)


def test_catches_editorial_language():
    """Editorial adverbs should be caught."""
    violations = validate_evidence_only(
        "Unfortunately, the team decided to delay the launch"
    )
    assert len(violations) > 0
    assert any("unfortunately" in v.text.lower() for v in violations)


def test_catches_obviously():
    """'Obviously' should be caught as editorial language."""
    violations = validate_evidence_only(
        "The problem was obviously caused by the API change"
    )
    assert len(violations) > 0


def test_catches_speculative_framing():
    """Speculative language about people should be caught."""
    violations = validate_evidence_only(
        "Mike seemed to be frustrated with the timeline"
    )
    assert len(violations) > 0
    assert any("seemed to be" in v.text.lower() for v in violations)


def test_catches_evaluative_decisions():
    """Evaluative framing of decisions should be caught."""
    violations = validate_evidence_only(
        "The team wisely decided to postpone the release"
    )
    assert len(violations) > 0
    assert any("wisely decided" in v.text.lower() for v in violations)


def test_catches_hindsight_judgment():
    """Hindsight judgment should be caught."""
    violations = validate_evidence_only(
        "They should have started the migration earlier"
    )
    assert len(violations) > 0
    assert any("should have" in v.text.lower() for v in violations)


def test_catches_demonstrated_language():
    """'Demonstrated leadership' type phrases should be caught."""
    violations = validate_evidence_only(
        "Sarah demonstrated strong leadership during the crisis"
    )
    assert len(violations) > 0


def test_catches_struggled():
    """'Struggled' applied to a person should be caught."""
    violations = validate_evidence_only(
        "The engineering team struggled to meet the deadline"
    )
    assert len(violations) > 0


# --- Negative cases: clean text should NOT trigger ---


def test_passes_neutral_factual():
    """Neutral factual reporting should pass clean."""
    text = (
        "Team decided to postpone the launch to Q2. "
        "Rationale: resource constraints. "
        "Owner: Sarah."
    )
    violations = validate_evidence_only(text)
    assert len(violations) == 0


def test_passes_action_language():
    """Action-oriented language should pass."""
    text = "Sarah committed to delivering the report by Friday"
    violations = validate_evidence_only(text)
    assert len(violations) == 0


def test_passes_outcome_language():
    """Outcome reporting should pass."""
    text = "The proposal was approved. Three members voted in favor."
    violations = validate_evidence_only(text)
    assert len(violations) == 0


def test_passes_decision_reporting():
    """Simple decision reporting without evaluation should pass."""
    text = "Team decided to use PostgreSQL for the new service. Mike will set up the database."
    violations = validate_evidence_only(text)
    assert len(violations) == 0


def test_passes_commitment_reporting():
    """Commitment reporting should pass."""
    text = "Sarah will send the spec by Friday. Tom will review it by Monday."
    violations = validate_evidence_only(text)
    assert len(violations) == 0


# --- Source attribution tests ---


def test_validates_attribution_present():
    """Items with proper attribution should pass."""
    text = """- **Decision:** Delay launch to Q3 (Team Sync -- Sarah, Mike)
- **Commitment:** Write spec by Friday (Product Review -- Tom)"""
    missing = validate_source_attribution(text)
    assert len(missing) == 0


def test_catches_missing_attribution():
    """Items without parenthetical citation should be flagged."""
    text = """- **Decision:** Delay launch to Q3
- **Commitment:** Write spec by Friday (Product Review -- Tom)"""
    missing = validate_source_attribution(text)
    assert len(missing) == 1
    assert "Delay launch" in missing[0]


def test_attribution_all_missing():
    """Multiple items without attribution should all be flagged."""
    text = """- **Decision:** Delay launch to Q3
- **Commitment:** Write spec by Friday
- **Item:** Pipeline review completed"""
    missing = validate_source_attribution(text)
    assert len(missing) == 3


# --- Edge cases ---


def test_empty_text():
    """Empty string should pass validation."""
    violations = validate_evidence_only("")
    assert len(violations) == 0


def test_is_clean_true():
    """is_clean returns True for clean text."""
    assert is_clean("Team decided to postpone. Owner: Sarah.") is True


def test_is_clean_false():
    """is_clean returns False for evaluative text."""
    assert is_clean("The team wisely decided to postpone") is False


def test_violation_has_context():
    """Violations should include surrounding context."""
    violations = validate_evidence_only(
        "After discussion, the team unfortunately missed the deadline again."
    )
    assert len(violations) > 0
    assert len(violations[0].context) > len(violations[0].text)
