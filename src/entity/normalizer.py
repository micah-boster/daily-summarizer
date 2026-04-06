"""Name normalization for entity matching.

Provides company name suffix stripping and person name matching
for the entity discovery pipeline.
"""

from __future__ import annotations

import re

# Suffixes to strip from company names (trailing only).
# Order matters: longer variants first to avoid partial matches.
COMPANY_SUFFIXES = [
    "Corporation",
    "Holdings",
    "Partners",
    "Group",
    "Inc.",
    "LLC.",
    "Corp.",
    "Ltd.",
    "Co.",
    "Inc",
    "LLC",
    "Corp",
    "Ltd",
    "Co",
    "LP",
]

# Build a single regex pattern: match any suffix at end of string,
# optionally preceded by a comma. The suffix must be preceded by a space
# (or comma+space) and followed by end of string.
_suffix_pattern = re.compile(
    r"[,\s]+(?:" + "|".join(re.escape(s) for s in COMPANY_SUFFIXES) + r")\s*$",
    re.IGNORECASE,
)


def normalize_company_name(name: str) -> str:
    """Strip trailing company suffixes from a name.

    Args:
        name: Company name, possibly with suffix like "Inc", "LLC", etc.

    Returns:
        Name with trailing suffix removed. If stripping would produce
        an empty string, returns the original (stripped of whitespace).
    """
    name = name.strip()
    if not name:
        return ""

    result = _suffix_pattern.sub("", name).strip()

    # Don't return empty string if the entire name was a suffix
    if not result:
        return name

    return result


def normalize_for_matching(name: str) -> str:
    """Normalize a name for comparison: strip suffix and lowercase.

    Args:
        name: Any entity name.

    Returns:
        Lowercased, suffix-stripped version for matching.
    """
    return normalize_company_name(name).lower().strip()


def names_match_person(name_a: str, name_b: str) -> bool:
    """Check if two person names refer to the same individual.

    Requires both names to have at least 2 parts (first + last).
    Matches if first names are equal and one last name is a prefix
    of the other (handles abbreviations like "Colin R." matching
    "Colin Roberts").

    Args:
        name_a: First person name.
        name_b: Second person name.

    Returns:
        True if names match, False otherwise.
    """
    if not name_a or not name_b:
        return False

    parts_a = name_a.lower().split()
    parts_b = name_b.lower().split()

    # Both must have first + last (2+ parts)
    if len(parts_a) < 2 or len(parts_b) < 2:
        return False

    # First names must match exactly
    if parts_a[0] != parts_b[0]:
        return False

    # Last name comparison: strip trailing dots for abbreviation matching
    last_a = parts_a[-1].rstrip(".")
    last_b = parts_b[-1].rstrip(".")

    # One must be a prefix of the other (handles "R" matching "Roberts")
    return last_a.startswith(last_b) or last_b.startswith(last_a)
