"""Tests for HubSpot cross-reference module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.entity.hubspot_xref import (
    FUZZY_THRESHOLD,
    cross_reference_entity,
    search_hubspot_contact,
    search_hubspot_deal,
)


# ---------------------------------------------------------------------------
# Helpers: build mock HubSpot SDK responses
# ---------------------------------------------------------------------------


def _mock_contact(contact_id: str, firstname: str, lastname: str, email: str = "test@example.com"):
    """Create a mock HubSpot contact result object."""
    contact = MagicMock()
    contact.id = contact_id
    contact.properties = {
        "firstname": firstname,
        "lastname": lastname,
        "email": email,
        "company": "Acme",
    }
    return contact


def _mock_deal(deal_id: str, dealname: str, dealstage: str = "closedwon"):
    """Create a mock HubSpot deal result object."""
    deal = MagicMock()
    deal.id = deal_id
    deal.properties = {
        "dealname": dealname,
        "dealstage": dealstage,
    }
    return deal


def _mock_client_with_contacts(contacts):
    """Build a mock HubSpot client that returns given contacts on search."""
    client = MagicMock()
    response = MagicMock()
    response.results = contacts
    client.crm.contacts.search_api.do_search.return_value = response
    return client


def _mock_client_with_deals(deals):
    """Build a mock HubSpot client that returns given deals on search."""
    client = MagicMock()
    response = MagicMock()
    response.results = deals
    client.crm.deals.search_api.do_search.return_value = response
    return client


# ---------------------------------------------------------------------------
# search_hubspot_contact
# ---------------------------------------------------------------------------


class TestSearchHubspotContact:
    def test_exact_match_returns_contact(self):
        contact = _mock_contact("101", "Colin", "Roberts", "colin@example.com")
        client = _mock_client_with_contacts([contact])

        result = search_hubspot_contact(client, "Colin Roberts")

        assert result is not None
        assert result["id"] == "101"
        assert result["email"] == "colin@example.com"
        assert result["confidence"] == 1.0

    def test_fuzzy_match_returns_contact_with_score(self):
        contact = _mock_contact("102", "Colin", "Roberts")
        client = _mock_client_with_contacts([contact])

        # "Colin Rob" is close enough for fuzzy match
        result = search_hubspot_contact(client, "Colin Rob")

        assert result is not None
        assert result["id"] == "102"
        assert result["confidence"] < 1.0
        assert result["confidence"] >= FUZZY_THRESHOLD / 100

    def test_no_match_returns_none(self):
        contact = _mock_contact("103", "Totally", "Different")
        client = _mock_client_with_contacts([contact])

        result = search_hubspot_contact(client, "Xyz Abc")

        assert result is None

    def test_empty_results_returns_none(self):
        client = _mock_client_with_contacts([])

        result = search_hubspot_contact(client, "Anyone")

        assert result is None

    def test_api_error_returns_none(self):
        client = MagicMock()
        client.crm.contacts.search_api.do_search.side_effect = Exception("API down")

        result = search_hubspot_contact(client, "Colin Roberts")

        assert result is None


# ---------------------------------------------------------------------------
# search_hubspot_deal
# ---------------------------------------------------------------------------


class TestSearchHubspotDeal:
    def test_exact_match_returns_deal(self):
        deal = _mock_deal("201", "Affirm Partnership", "closedwon")
        client = _mock_client_with_deals([deal])

        result = search_hubspot_deal(client, "Affirm Partnership")

        assert result is not None
        assert result["id"] == "201"
        assert result["deal_stage"] == "closedwon"
        assert result["confidence"] == 1.0

    def test_fuzzy_match_returns_deal(self):
        deal = _mock_deal("202", "Affirm Inc Partnership Deal")
        client = _mock_client_with_deals([deal])

        result = search_hubspot_deal(client, "Affirm Partnership")

        # fuzzy match should work since token_sort_ratio is high
        assert result is not None
        assert result["id"] == "202"
        assert result["confidence"] < 1.0
        assert result["confidence"] >= FUZZY_THRESHOLD / 100

    def test_no_match_returns_none(self):
        deal = _mock_deal("203", "Completely Unrelated Deal")
        client = _mock_client_with_deals([deal])

        result = search_hubspot_deal(client, "Xyz Corp")

        assert result is None

    def test_api_error_returns_none(self):
        client = MagicMock()
        client.crm.deals.search_api.do_search.side_effect = Exception("API error")

        result = search_hubspot_deal(client, "Some Deal")

        assert result is None


# ---------------------------------------------------------------------------
# cross_reference_entity
# ---------------------------------------------------------------------------


class TestCrossReferenceEntity:
    def _make_config(self, access_token: str = "test-token"):
        config = MagicMock()
        config.hubspot.access_token = access_token
        return config

    @patch("src.entity.hubspot_xref.HubSpot")
    @patch("src.entity.hubspot_xref.search_hubspot_contact")
    def test_person_type_searches_contacts(self, mock_search_contact, mock_hubspot_cls):
        mock_search_contact.return_value = {
            "id": "101",
            "email": "colin@example.com",
            "confidence": 1.0,
        }

        result = cross_reference_entity("Colin Roberts", "person", self._make_config())

        assert result is not None
        assert result["hubspot_id"] == "101"
        assert result["hubspot_type"] == "contact"
        assert result["email"] == "colin@example.com"
        mock_search_contact.assert_called_once()

    @patch("src.entity.hubspot_xref.HubSpot")
    @patch("src.entity.hubspot_xref.search_hubspot_deal")
    def test_partner_type_searches_deals(self, mock_search_deal, mock_hubspot_cls):
        mock_search_deal.return_value = {
            "id": "201",
            "deal_stage": "closedwon",
            "confidence": 0.95,
        }

        result = cross_reference_entity("Affirm", "partner", self._make_config())

        assert result is not None
        assert result["hubspot_id"] == "201"
        assert result["hubspot_type"] == "deal"
        mock_search_deal.assert_called_once()

    @patch("src.entity.hubspot_xref.HubSpot")
    @patch("src.entity.hubspot_xref.search_hubspot_deal")
    @patch("src.entity.hubspot_xref.search_hubspot_contact")
    def test_partner_falls_back_to_contacts(self, mock_search_contact, mock_search_deal, mock_hubspot_cls):
        mock_search_deal.return_value = None
        mock_search_contact.return_value = {
            "id": "102",
            "email": "partner@example.com",
            "confidence": 0.85,
        }

        result = cross_reference_entity("Some Partner", "partner", self._make_config())

        assert result is not None
        assert result["hubspot_type"] == "contact"
        mock_search_deal.assert_called_once()
        mock_search_contact.assert_called_once()

    @patch("src.entity.hubspot_xref.HubSpot")
    def test_api_error_returns_none(self, mock_hubspot_cls):
        mock_hubspot_cls.side_effect = Exception("Connection refused")

        result = cross_reference_entity("Test Entity", "partner", self._make_config())

        assert result is None

    def test_empty_access_token_returns_none(self):
        result = cross_reference_entity("Test", "person", self._make_config(access_token=""))

        assert result is None

    def test_no_access_token_returns_none(self):
        config = MagicMock()
        config.hubspot.access_token = ""

        result = cross_reference_entity("Test", "partner", config)

        assert result is None

    @patch("src.entity.hubspot_xref.HubSpot")
    @patch("src.entity.hubspot_xref.search_hubspot_contact")
    @patch("src.entity.hubspot_xref.search_hubspot_deal")
    def test_partner_calls_both_searches(self, mock_search_deal, mock_search_contact, mock_hubspot_cls):
        """Partner entities should search deals first, then contacts."""
        mock_search_deal.return_value = None
        mock_search_contact.return_value = None

        result = cross_reference_entity("Unknown Corp", "partner", self._make_config())

        assert result is None
        mock_search_deal.assert_called_once()
        mock_search_contact.assert_called_once()
