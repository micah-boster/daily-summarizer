"""Tests for entity name normalization: company suffixes, matching, person names."""

from __future__ import annotations

from src.entity.normalizer import (
    names_match_person,
    normalize_company_name,
    normalize_for_matching,
)


# --- normalize_company_name tests ---


def test_normalize_strips_inc():
    assert normalize_company_name("Affirm Inc") == "Affirm"


def test_normalize_strips_inc_dot():
    assert normalize_company_name("Affirm Inc.") == "Affirm"


def test_normalize_strips_llc():
    assert normalize_company_name("Cardless LLC") == "Cardless"


def test_normalize_strips_corp():
    assert normalize_company_name("Acme Corp") == "Acme"


def test_normalize_strips_corporation():
    assert normalize_company_name("Acme Corporation") == "Acme"


def test_normalize_strips_co():
    assert normalize_company_name("Big Co") == "Big"


def test_normalize_strips_partners():
    assert normalize_company_name("Venture Partners") == "Venture"


def test_normalize_strips_holdings():
    assert normalize_company_name("Alpha Holdings") == "Alpha"


def test_normalize_strips_trailing_only():
    """LP Ventures LP -> LP Ventures (only strips trailing suffix)."""
    assert normalize_company_name("LP Ventures LP") == "LP Ventures"


def test_normalize_no_empty_result():
    """If stripping suffix would leave empty, return original."""
    assert normalize_company_name("Inc") == "Inc"


def test_normalize_empty_string():
    assert normalize_company_name("") == ""


def test_normalize_whitespace():
    assert normalize_company_name("  Affirm Inc  ") == "Affirm"


def test_normalize_clean_name_passthrough():
    assert normalize_company_name("Affirm") == "Affirm"


def test_normalize_strips_ltd():
    assert normalize_company_name("Global Ltd") == "Global"


def test_normalize_strips_lp():
    assert normalize_company_name("Capital LP") == "Capital"


def test_normalize_strips_group():
    assert normalize_company_name("Tech Group") == "Tech"


# --- normalize_for_matching tests ---


def test_for_matching_lowercases_and_strips():
    assert normalize_for_matching("Affirm Inc") == "affirm"


def test_for_matching_all_caps():
    assert normalize_for_matching("CARDLESS LLC") == "cardless"


def test_for_matching_clean_name():
    assert normalize_for_matching("Affirm") == "affirm"


# --- names_match_person tests ---


def test_person_match_abbreviated_last():
    assert names_match_person("Colin Roberts", "Colin R.") is True


def test_person_match_exact():
    assert names_match_person("Colin Roberts", "Colin Roberts") is True


def test_person_match_case_insensitive():
    assert names_match_person("Colin Roberts", "colin roberts") is True


def test_person_no_match_first_only():
    """First name alone does NOT match full name (require first+last)."""
    assert names_match_person("Colin", "Colin Roberts") is False


def test_person_no_match_different_first():
    assert names_match_person("Colin Roberts", "Sarah Roberts") is False


def test_person_match_abbreviated_last_name():
    """Colin Rob should match Colin Roberts (prefix of last name)."""
    assert names_match_person("Colin Roberts", "Colin Rob") is True


def test_person_no_match_empty():
    assert names_match_person("", "") is False


def test_person_no_match_one_empty():
    assert names_match_person("Colin Roberts", "") is False


def test_person_no_match_other_empty():
    assert names_match_person("", "Colin Roberts") is False
