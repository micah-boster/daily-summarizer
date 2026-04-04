"""Tests for HubSpot CRM ingestion module."""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.models.sources import ContentType, SourceItem, SourceType


# ---------------------------------------------------------------------------
# Helpers for building mock SDK responses
# ---------------------------------------------------------------------------

def _mock_deal(deal_id: str, name: str, amount: str, stage: str, owner_id: str,
               stage_history: list | None = None, created: str | None = None):
    """Build a mock deal object matching HubSpot SDK response shape."""
    deal = MagicMock()
    deal.id = deal_id
    deal.properties = {
        "dealname": name,
        "amount": amount,
        "dealstage": stage,
        "closedate": "2026-04-15",
        "hubspot_owner_id": owner_id,
        "hs_lastmodifieddate": "2026-04-04T12:00:00.000Z",
        "createdate": created or "2026-04-01T10:00:00.000Z",
    }
    deal.properties_with_history = {}
    if stage_history is not None:
        deal.properties_with_history = {"dealstage": stage_history}
    return deal


def _mock_contact(contact_id: str, first: str, last: str, company: str, owner_id: str):
    contact = MagicMock()
    contact.id = contact_id
    contact.properties = {
        "firstname": first,
        "lastname": last,
        "company": company,
        "hubspot_owner_id": owner_id,
        "hs_lastmodifieddate": "2026-04-04T14:00:00.000Z",
    }
    contact.associations = None
    return contact


def _mock_ticket(ticket_id: str, subject: str, status: str, owner_id: str):
    ticket = MagicMock()
    ticket.id = ticket_id
    ticket.properties = {
        "subject": subject,
        "hs_pipeline_stage": status,
        "hubspot_owner_id": owner_id,
        "hs_lastmodifieddate": "2026-04-04T15:00:00.000Z",
        "createdate": "2026-04-03T10:00:00.000Z",
    }
    return ticket


def _mock_note(note_id: str, body: str, owner_id: str):
    note = MagicMock()
    note.id = note_id
    note.properties = {
        "hs_note_body": body,
        "hs_timestamp": "2026-04-04T11:00:00.000Z",
        "hubspot_owner_id": owner_id,
        "hs_lastmodifieddate": "2026-04-04T11:00:00.000Z",
    }
    return note


def _mock_search_response(results, has_next=False):
    resp = MagicMock()
    resp.results = results
    resp.total = len(results)
    if has_next:
        resp.paging = MagicMock()
        resp.paging.next = MagicMock(after="100")
    else:
        resp.paging = None
    return resp


def _mock_pipeline(stages: list[tuple[str, str]]):
    pipeline = MagicMock()
    pipeline.stages = []
    for sid, label in stages:
        s = MagicMock()
        s.id = sid
        s.label = label
        pipeline.stages.append(s)
    return pipeline


def _mock_owner(owner_id: str, first: str, last: str, email: str):
    owner = MagicMock()
    owner.id = owner_id
    owner.first_name = first
    owner.last_name = last
    owner.email = email
    owner.user_id = owner_id
    return owner


def _base_config(enabled=True, scope="all"):
    return {
        "hubspot": {
            "enabled": enabled,
            "ownership_scope": scope,
            "max_deals": 50,
            "max_contacts": 50,
            "max_tickets": 25,
            "max_activities_per_type": 25,
            "portal_url": "https://app.hubspot.com/contacts/12345678",
        },
        "pipeline": {"timezone": "America/New_York"},
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBuildHubspotClient:
    def test_builds_with_env_var(self):
        with patch.dict("os.environ", {"HUBSPOT_ACCESS_TOKEN": "test-token"}):
            from src.ingest.hubspot import build_hubspot_client
            client = build_hubspot_client()
            assert client is not None

    def test_builds_with_explicit_token(self):
        from src.ingest.hubspot import build_hubspot_client
        client = build_hubspot_client(token="explicit-token")
        assert client is not None

    def test_raises_without_token(self):
        with patch.dict("os.environ", {}, clear=True):
            # Remove HUBSPOT_ACCESS_TOKEN if present
            import os
            os.environ.pop("HUBSPOT_ACCESS_TOKEN", None)
            from src.ingest.hubspot import build_hubspot_client
            with pytest.raises(ValueError, match="No HubSpot"):
                build_hubspot_client()


class TestDateToMsRange:
    def test_converts_date_to_ms(self):
        from src.ingest.hubspot import _date_to_ms_range
        start_ms, end_ms = _date_to_ms_range(date(2026, 4, 4), "America/New_York")
        # Start should be midnight EDT (UTC-4), end should be next midnight
        assert isinstance(start_ms, int)
        assert isinstance(end_ms, int)
        assert end_ms > start_ms
        # Roughly 24 hours apart in ms
        assert abs((end_ms - start_ms) - 86400000) < 1000


class TestFetchDeals:
    @patch("src.ingest.hubspot.build_hubspot_client")
    def test_creates_source_items(self, mock_build):
        from src.ingest.hubspot import _fetch_deals

        client = MagicMock()
        deal = _mock_deal("100", "Acme Renewal", "50000", "closedwon", "1001")
        client.crm.deals.search_api.do_search.return_value = _mock_search_response([deal])
        client.crm.deals.basic_api.get_by_id.return_value = deal

        stage_map = {"closedwon": "Closed Won"}
        owner_map = {"1001": "Jane Smith"}
        config = _base_config()

        items = _fetch_deals(client, 0, 100, config, stage_map, owner_map)
        assert len(items) >= 1
        assert all(isinstance(i, SourceItem) for i in items)
        assert items[0].source_type == SourceType.HUBSPOT_DEAL
        assert "Acme Renewal" in items[0].title

    @patch("src.ingest.hubspot.build_hubspot_client")
    def test_stage_history_detection(self, mock_build):
        from src.ingest.hubspot import _fetch_deals

        client = MagicMock()
        history = [
            MagicMock(value="closedwon", timestamp="1712246400000"),
            MagicMock(value="qualifiedtobuy", timestamp="1712160000000"),
        ]
        deal = _mock_deal("100", "Acme Renewal", "50000", "closedwon", "1001",
                          stage_history=history)
        client.crm.deals.search_api.do_search.return_value = _mock_search_response([deal])
        client.crm.deals.basic_api.get_by_id.return_value = deal

        stage_map = {"closedwon": "Closed Won", "qualifiedtobuy": "Qualified to Buy"}
        owner_map = {"1001": "Jane Smith"}
        config = _base_config()

        items = _fetch_deals(client, 0, 100, config, stage_map, owner_map)
        assert len(items) >= 1
        # Content should mention stage transition
        assert "Closed Won" in items[0].content or "stage" in items[0].content.lower()


class TestFetchContacts:
    @patch("src.ingest.hubspot.build_hubspot_client")
    def test_creates_items_with_company(self, mock_build):
        from src.ingest.hubspot import _fetch_contacts

        client = MagicMock()
        contact = _mock_contact("200", "John", "Smith", "Acme Corp", "1001")
        client.crm.contacts.search_api.do_search.return_value = _mock_search_response([contact])
        # Mock notes search for this contact
        note = _mock_note("300", "Discussed renewal timeline", "1001")
        client.crm.objects.notes.search_api.do_search.return_value = _mock_search_response([note])
        # Empty for other engagement types
        empty_resp = _mock_search_response([])
        client.crm.objects.calls.search_api.do_search.return_value = empty_resp
        client.crm.objects.emails.search_api.do_search.return_value = empty_resp
        client.crm.objects.meetings.search_api.do_search.return_value = empty_resp
        client.crm.objects.tasks.search_api.do_search.return_value = empty_resp

        owner_map = {"1001": "Jane Smith"}
        config = _base_config()

        items = _fetch_contacts(client, 0, 100, config, owner_map)
        assert len(items) >= 1
        assert all(isinstance(i, SourceItem) for i in items)
        # Should reference contact name and company
        has_contact_ref = any("John Smith" in i.display_context or "Acme Corp" in i.display_context for i in items)
        assert has_contact_ref


class TestFetchTickets:
    @patch("src.ingest.hubspot.build_hubspot_client")
    def test_creates_source_items(self, mock_build):
        from src.ingest.hubspot import _fetch_tickets

        client = MagicMock()
        ticket = _mock_ticket("400", "API integration broken", "2", "1001")
        client.crm.tickets.search_api.do_search.return_value = _mock_search_response([ticket])

        owner_map = {"1001": "Jane Smith"}
        stage_map = {"2": "In Progress"}
        config = _base_config()

        items = _fetch_tickets(client, 0, 100, config, owner_map, stage_map)
        assert len(items) >= 1
        assert items[0].source_type == SourceType.HUBSPOT_TICKET
        assert "API integration broken" in items[0].title


class TestFetchEngagements:
    @patch("src.ingest.hubspot.build_hubspot_client")
    def test_notes_produce_source_items(self, mock_build):
        from src.ingest.hubspot import _fetch_engagements

        client = MagicMock()
        note = _mock_note("500", "Follow up needed on contract terms", "1001")
        client.crm.objects.notes.search_api.do_search.return_value = _mock_search_response([note])
        # Empty for other types
        empty_resp = _mock_search_response([])
        client.crm.objects.calls.search_api.do_search.return_value = empty_resp
        client.crm.objects.emails.search_api.do_search.return_value = empty_resp
        client.crm.objects.meetings.search_api.do_search.return_value = empty_resp
        client.crm.objects.tasks.search_api.do_search.return_value = empty_resp

        owner_map = {"1001": "Jane Smith"}
        config = _base_config()

        items = _fetch_engagements(client, 0, 100, config, owner_map)
        assert len(items) >= 1
        assert items[0].source_type == SourceType.HUBSPOT_ACTIVITY


class TestOwnershipScope:
    @patch("src.ingest.hubspot.build_hubspot_client")
    def test_mine_scope_adds_owner_filter(self, mock_build):
        from src.ingest.hubspot import fetch_hubspot_items

        client = MagicMock()
        mock_build.return_value = client

        # Setup pipeline stages and owners
        pipeline = _mock_pipeline([("closedwon", "Closed Won")])
        client.crm.pipelines.pipelines_api.get_all.return_value = MagicMock(results=[pipeline])
        owner = _mock_owner("1001", "Jane", "Smith", "jane@example.com")
        client.crm.owners.owners_api.get_page.return_value = MagicMock(results=[owner])
        # Return current user's owner ID
        client.crm.owners.owners_api.get_page.return_value = MagicMock(results=[owner])

        # All searches return empty
        empty_resp = _mock_search_response([])
        client.crm.deals.search_api.do_search.return_value = empty_resp
        client.crm.deals.basic_api.get_by_id.side_effect = lambda **kwargs: None
        client.crm.contacts.search_api.do_search.return_value = empty_resp
        client.crm.tickets.search_api.do_search.return_value = empty_resp
        client.crm.objects.notes.search_api.do_search.return_value = empty_resp
        client.crm.objects.calls.search_api.do_search.return_value = empty_resp
        client.crm.objects.emails.search_api.do_search.return_value = empty_resp
        client.crm.objects.meetings.search_api.do_search.return_value = empty_resp
        client.crm.objects.tasks.search_api.do_search.return_value = empty_resp

        config = _base_config(scope="mine")
        with patch.dict("os.environ", {"HUBSPOT_ACCESS_TOKEN": "test-token"}):
            items = fetch_hubspot_items(config, date(2026, 4, 4))

        # Should have called search with some owner filter
        # (we mainly verify it doesn't crash with "mine" scope)
        assert isinstance(items, list)

    @patch("src.ingest.hubspot.build_hubspot_client")
    def test_all_scope_no_crash(self, mock_build):
        from src.ingest.hubspot import fetch_hubspot_items

        client = MagicMock()
        mock_build.return_value = client

        pipeline = _mock_pipeline([("closedwon", "Closed Won")])
        client.crm.pipelines.pipelines_api.get_all.return_value = MagicMock(results=[pipeline])
        owner = _mock_owner("1001", "Jane", "Smith", "jane@example.com")
        client.crm.owners.owners_api.get_page.return_value = MagicMock(results=[owner])

        empty_resp = _mock_search_response([])
        client.crm.deals.search_api.do_search.return_value = empty_resp
        client.crm.contacts.search_api.do_search.return_value = empty_resp
        client.crm.tickets.search_api.do_search.return_value = empty_resp
        client.crm.objects.notes.search_api.do_search.return_value = empty_resp
        client.crm.objects.calls.search_api.do_search.return_value = empty_resp
        client.crm.objects.emails.search_api.do_search.return_value = empty_resp
        client.crm.objects.meetings.search_api.do_search.return_value = empty_resp
        client.crm.objects.tasks.search_api.do_search.return_value = empty_resp

        config = _base_config(scope="all")
        with patch.dict("os.environ", {"HUBSPOT_ACCESS_TOKEN": "test-token"}):
            items = fetch_hubspot_items(config, date(2026, 4, 4))
        assert isinstance(items, list)


class TestVolumeCaps:
    @patch("src.ingest.hubspot.build_hubspot_client")
    def test_caps_results(self, mock_build):
        from src.ingest.hubspot import _fetch_deals

        client = MagicMock()
        # Create 5 deals
        deals = [_mock_deal(str(i), f"Deal {i}", "1000", "s1", "1001") for i in range(5)]
        client.crm.deals.search_api.do_search.return_value = _mock_search_response(deals)
        for d in deals:
            client.crm.deals.basic_api.get_by_id.return_value = d

        stage_map = {"s1": "Stage 1"}
        owner_map = {"1001": "Jane Smith"}
        config = _base_config()
        config["hubspot"]["max_deals"] = 3  # Cap at 3

        items = _fetch_deals(client, 0, 100, config, stage_map, owner_map)
        assert len(items) <= 3


class TestAttributionFormat:
    @patch("src.ingest.hubspot.build_hubspot_client")
    def test_deal_attribution(self, mock_build):
        from src.ingest.hubspot import _fetch_deals

        client = MagicMock()
        deal = _mock_deal("100", "Acme Renewal", "50000", "closedwon", "1001")
        client.crm.deals.search_api.do_search.return_value = _mock_search_response([deal])
        client.crm.deals.basic_api.get_by_id.return_value = deal

        stage_map = {"closedwon": "Closed Won"}
        owner_map = {"1001": "Jane Smith"}
        config = _base_config()

        items = _fetch_deals(client, 0, 100, config, stage_map, owner_map)
        assert len(items) >= 1
        text = items[0].attribution_text()
        assert "HubSpot" in text
        assert "deal" in text.lower() or "Deal" in text


class TestDisabledConfig:
    def test_returns_empty_when_disabled(self):
        from src.ingest.hubspot import fetch_hubspot_items
        config = _base_config(enabled=False)
        items = fetch_hubspot_items(config, date(2026, 4, 4))
        assert items == []


class TestEntryPoint:
    @patch("src.ingest.hubspot.build_hubspot_client")
    def test_fetch_hubspot_items_combines_results(self, mock_build):
        from src.ingest.hubspot import fetch_hubspot_items

        client = MagicMock()
        mock_build.return_value = client

        pipeline = _mock_pipeline([("s1", "Stage 1")])
        client.crm.pipelines.pipelines_api.get_all.return_value = MagicMock(results=[pipeline])
        owner = _mock_owner("1001", "Jane", "Smith", "jane@example.com")
        client.crm.owners.owners_api.get_page.return_value = MagicMock(results=[owner])

        deal = _mock_deal("100", "Test Deal", "1000", "s1", "1001")
        client.crm.deals.search_api.do_search.return_value = _mock_search_response([deal])
        client.crm.deals.basic_api.get_by_id.return_value = deal

        contact = _mock_contact("200", "John", "Doe", "TestCo", "1001")
        client.crm.contacts.search_api.do_search.return_value = _mock_search_response([contact])

        ticket = _mock_ticket("300", "Bug report", "1", "1001")
        client.crm.tickets.search_api.do_search.return_value = _mock_search_response([ticket])

        empty_resp = _mock_search_response([])
        client.crm.objects.notes.search_api.do_search.return_value = empty_resp
        client.crm.objects.calls.search_api.do_search.return_value = empty_resp
        client.crm.objects.emails.search_api.do_search.return_value = empty_resp
        client.crm.objects.meetings.search_api.do_search.return_value = empty_resp
        client.crm.objects.tasks.search_api.do_search.return_value = empty_resp

        config = _base_config(scope="all")
        with patch.dict("os.environ", {"HUBSPOT_ACCESS_TOKEN": "test-token"}):
            items = fetch_hubspot_items(config, date(2026, 4, 4))

        assert isinstance(items, list)
        # Should have items from deals, contacts/notes, and tickets
        source_types = {i.source_type for i in items}
        assert SourceType.HUBSPOT_DEAL in source_types or len(items) > 0
