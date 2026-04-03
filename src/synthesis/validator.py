"""Evidence-only language enforcement and source attribution validation."""

from __future__ import annotations

import re

from pydantic import BaseModel


# Banned pattern categories for evaluative language detection
_PERFORMANCE_ADJECTIVES = [
    r"\b(?:productive|effective|impressive|excellent|poor|weak|brilliant|incompetent)\s+(?:job|work|effort|performance|leadership|contribution|insight|meeting|discussion|session)\b",
    r"\b(?:good|great|bad|terrible|wonderful|awful|amazing|outstanding)\s+(?:job|work|effort|performance|leadership|contribution|insight)\b",
]

_EDITORIAL_LANGUAGE = [
    r"\b(?:clearly|obviously|unfortunately|fortunately|surprisingly|remarkably|notably)\b",
    r"\b(?:seemed|appeared|felt)\s+(?:to be|like|as if)\b",
    r"\bit(?:'s| is) (?:clear|obvious|evident|apparent) that\b",
]

_EVALUATIVE_FRAMING = [
    r"\b(?:wisely|foolishly|rightly|wrongly|correctly|incorrectly)\s+(?:decided|chose|opted)\b",
    r"\b(?:strong|weak|excellent|poor)\s+(?:decision|choice|move|strategy|approach)\b",
    r"\b(?:showed|demonstrated|displayed|exhibited)\s+(?:\w+\s+)?(?:leadership|initiative|competence|skill)\b",
]

_INDIVIDUAL_IMPLICATIONS = [
    r"\b(?:struggled|excelled|thrived|faltered|dominated)\b",
    r"\b(?:should have|could have|ought to have)\b",
]

# Compile all patterns with category names for debugging
BANNED_PATTERNS: list[tuple[str, re.Pattern]] = []
for _name, _patterns in [
    ("performance_adjective", _PERFORMANCE_ADJECTIVES),
    ("editorial_language", _EDITORIAL_LANGUAGE),
    ("evaluative_framing", _EVALUATIVE_FRAMING),
    ("individual_implication", _INDIVIDUAL_IMPLICATIONS),
]:
    for _pat in _patterns:
        BANNED_PATTERNS.append((_name, re.compile(_pat, re.IGNORECASE)))


class ValidationViolation(BaseModel):
    """A single evaluative language violation found in text."""

    text: str  # The matched text
    pattern: str  # Which pattern category matched
    context: str  # Surrounding ~50 chars for debugging


def validate_evidence_only(text: str) -> list[ValidationViolation]:
    """Scan text for evaluative language violations.

    Checks against all banned patterns and returns detailed violations.
    Empty list means text passes validation.

    Args:
        text: The text to validate.

    Returns:
        List of ValidationViolation objects for each match found.
    """
    violations: list[ValidationViolation] = []

    for category, pattern in BANNED_PATTERNS:
        for match in pattern.finditer(text):
            start = max(0, match.start() - 25)
            end = min(len(text), match.end() + 25)
            context = text[start:end]
            violations.append(
                ValidationViolation(
                    text=match.group(),
                    pattern=category,
                    context=context,
                )
            )

    return violations


def validate_source_attribution(text: str) -> list[str]:
    """Check that synthesis items have inline parenthetical attribution.

    Scans for bullet items (lines starting with - or *) that lack a
    parenthetical source citation pattern like "(Meeting Title".

    Args:
        text: The synthesis output text to check.

    Returns:
        List of item lines missing source attribution.
    """
    missing: list[str] = []
    lines = text.split("\n")

    for line in lines:
        stripped = line.strip()
        # Only check bullet items that contain substantive content
        if not stripped.startswith(("- **", "* **")):
            continue
        # Skip section headers and empty bullets
        if stripped in ("- ", "* ", "- **None**", "* **None**"):
            continue
        # Check for parenthetical citation
        if not re.search(r"\([^)]*--[^)]*\)", stripped):
            missing.append(stripped)

    return missing


def is_clean(text: str) -> bool:
    """Convenience check: returns True if text has no evaluative language violations.

    Args:
        text: The text to validate.

    Returns:
        True if no violations found, False otherwise.
    """
    return len(validate_evidence_only(text)) == 0
