"""HubSpot CRM ingestion module.

Fetches deal activity, contact notes, tickets, and engagements
(calls, emails, meetings, notes, tasks) for a target date.
Converts to SourceItem objects for synthesis.
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from hubspot import HubSpot
from hubspot.crm.deals import PublicObjectSearchRequest as DealSearchRequest
from hubspot.crm.contacts import PublicObjectSearchRequest as ContactSearchRequest
from hubspot.crm.tickets import PublicObjectSearchRequest as TicketSearchRequest

from src.models.sources import ContentType, SourceItem, SourceType

logger = logging.getLogger(__name__)


def build_hubspot_client(token: str | None = None) -> HubSpot:
    """Initialize a HubSpot API client.

    Args:
        token: Private app access token. Falls back to HUBSPOT_ACCESS_TOKEN env var.

    Returns:
        Configured HubSpot client.

    Raises:
        ValueError: If no token is available.
    """
    token = token or os.environ.get("HUBSPOT_ACCESS_TOKEN")
    if not token:
        raise ValueError(
            "No HubSpot access token found. Set HUBSPOT_ACCESS_TOKEN env var "
            "or pass token directly."
        )
    return HubSpot(access_token=token)


def _date_to_ms_range(target_date: date, tz_name: str = "America/New_York") -> tuple[int, int]:
    """Convert a date to start/end millisecond timestamps for HubSpot Search API.

    Args:
        target_date: The date to convert.
        tz_name: IANA timezone name.

    Returns:
        Tuple of (start_ms, end_ms) for the full day.
    """
    tz = ZoneInfo(tz_name)
    start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=tz)
    end = start + timedelta(days=1)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def _build_stage_map(client: HubSpot) -> dict[str, str]:
    """Build mapping of deal pipeline stage ID -> human-readable label.

    Fetches all deal pipelines and their stages.

    Returns:
        Dict mapping stage_id to stage label string.
    """
    stage_map: dict[str, str] = {}
    try:
        pipelines = client.crm.pipelines.pipelines_api.get_all("deals")
        for pipeline in pipelines.results:
            for stage in pipeline.stages:
                stage_map[stage.id] = stage.label
    except Exception as e:
        logger.warning("Failed to fetch deal pipeline stages: %s", e)
    return stage_map


def _build_ticket_stage_map(client: HubSpot) -> dict[str, str]:
    """Build mapping of ticket pipeline stage ID -> human-readable label."""
    stage_map: dict[str, str] = {}
    try:
        pipelines = client.crm.pipelines.pipelines_api.get_all("tickets")
        for pipeline in pipelines.results:
            for stage in pipeline.stages:
                stage_map[stage.id] = stage.label
    except Exception as e:
        logger.warning("Failed to fetch ticket pipeline stages: %s", e)
    return stage_map


def _build_owner_map(client: HubSpot) -> dict[str, str]:
    """Build mapping of owner ID -> display name.

    Returns:
        Dict mapping owner_id (str) to name string.
    """
    owner_map: dict[str, str] = {}
    try:
        owners = client.crm.owners.owners_api.get_page(limit=500)
        for owner in owners.results:
            name = f"{owner.first_name} {owner.last_name}".strip()
            owner_map[str(owner.id)] = name or owner.email
    except Exception as e:
        logger.warning("Failed to fetch owner list: %s", e)
    return owner_map


def _resolve_owner_id(client: HubSpot, config: dict, owner_map: dict[str, str]) -> str | None:
    """Determine the owner ID filter based on ownership scope config.

    Args:
        client: HubSpot client instance.
        config: Pipeline config dict.
        owner_map: Pre-built owner ID to name map.

    Returns:
        Owner ID string for filtering, or None for no filter (all scope).
    """
    scope = config.get("hubspot", {}).get("ownership_scope", "mine")

    if scope == "all":
        return None

    if scope == "mine":
        # Try to find the authenticated user's owner ID
        try:
            owners = client.crm.owners.owners_api.get_page(limit=500)
            # The first owner with user_id matching is typically the current user
            # In practice, the private app token's owner may need explicit config
            if owners.results:
                return str(owners.results[0].id)
        except Exception as e:
            logger.warning("Could not resolve owner ID for 'mine' scope: %s", e)
        return None

    # Assume scope is a specific owner ID or list
    if isinstance(scope, list):
        return scope[0] if scope else None
    return str(scope)


def _build_search_filters(
    start_ms: int, end_ms: int, owner_id: str | None = None
) -> list[dict]:
    """Build HubSpot search filter groups for date range and optional owner.

    Args:
        start_ms: Start timestamp in milliseconds.
        end_ms: End timestamp in milliseconds.
        owner_id: Optional owner ID to filter by.

    Returns:
        List of filter dicts for PublicObjectSearchRequest.
    """
    filters = [
        {
            "propertyName": "hs_lastmodifieddate",
            "operator": "BETWEEN",
            "value": str(start_ms),
            "highValue": str(end_ms),
        }
    ]
    if owner_id:
        filters.append(
            {
                "propertyName": "hubspot_owner_id",
                "operator": "EQ",
                "value": owner_id,
            }
        )
    return filters


def _get_portal_url(config: dict) -> str:
    """Get HubSpot portal base URL from config."""
    return config.get("hubspot", {}).get("portal_url", "")


def _fetch_deals(
    client: HubSpot,
    start_ms: int,
    end_ms: int,
    config: dict,
    stage_map: dict[str, str],
    owner_map: dict[str, str],
    owner_id: str | None = None,
) -> list[SourceItem]:
    """Fetch deals modified on the target date.

    Searches for deals, fetches stage history for each, and builds SourceItems.

    Returns:
        List of SourceItem objects for deals.
    """
    items: list[SourceItem] = []
    max_deals = config.get("hubspot", {}).get("max_deals", 50)
    portal_url = _get_portal_url(config)

    filters = _build_search_filters(start_ms, end_ms, owner_id)
    deal_properties = [
        "dealname", "amount", "dealstage", "closedate",
        "hubspot_owner_id", "hs_lastmodifieddate", "createdate",
    ]

    try:
        request = DealSearchRequest(
            filter_groups=[{"filters": filters}],
            properties=deal_properties,
            sorts=[{"propertyName": "hs_lastmodifieddate", "direction": "DESCENDING"}],
            limit=min(max_deals, 100),
        )
        response = client.crm.deals.search_api.do_search(
            public_object_search_request=request
        )

        for deal in response.results[:max_deals]:
            props = deal.properties
            deal_name = props.get("dealname", "Unnamed Deal")
            amount = props.get("amount", "")
            current_stage_id = props.get("dealstage", "")
            current_stage = stage_map.get(current_stage_id, current_stage_id)
            owner_name = owner_map.get(props.get("hubspot_owner_id", ""), "Unknown")
            modified = props.get("hs_lastmodifieddate", "")

            # Try to get stage history
            stage_change_text = ""
            content_type = ContentType.ACTIVITY
            try:
                detail = client.crm.deals.basic_api.get_by_id(
                    deal_id=deal.id,
                    properties=deal_properties,
                    properties_with_history=["dealstage"],
                )
                if detail and hasattr(detail, "properties_with_history"):
                    history = detail.properties_with_history.get("dealstage", [])
                    if isinstance(history, list) and len(history) >= 2:
                        prev_stage_id = history[1].value if hasattr(history[1], "value") else str(history[1])
                        prev_stage = stage_map.get(prev_stage_id, prev_stage_id)
                        stage_change_text = f"Stage: {prev_stage} -> {current_stage}"
                        content_type = ContentType.STAGE_CHANGE
            except Exception:
                pass

            # Build content
            parts = []
            if stage_change_text:
                parts.append(stage_change_text)
            if amount:
                parts.append(f"Amount: ${amount}")
            parts.append(f"Current stage: {current_stage}")
            parts.append(f"Owner: {owner_name}")
            content = ". ".join(parts)

            # Build URL
            source_url = f"{portal_url}/deal/{deal.id}" if portal_url else ""

            # Parse timestamp
            ts = datetime.now(timezone.utc)
            if modified:
                try:
                    ts = datetime.fromisoformat(modified.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass

            items.append(SourceItem(
                id=f"hubspot-deal-{deal.id}",
                source_type=SourceType.HUBSPOT_DEAL,
                content_type=content_type,
                title=deal_name,
                timestamp=ts,
                content=content,
                participants=[owner_name],
                source_url=source_url,
                display_context=f"HubSpot deal {deal_name}",
            ))

    except Exception as e:
        logger.warning("Failed to fetch HubSpot deals: %s", e)

    return items[:max_deals]


def _fetch_contacts(
    client: HubSpot,
    start_ms: int,
    end_ms: int,
    config: dict,
    owner_map: dict[str, str],
    owner_id: str | None = None,
) -> list[SourceItem]:
    """Fetch contacts with activity on the target date.

    Returns SourceItems for contact activity (notes, calls, emails, meetings).
    """
    items: list[SourceItem] = []
    max_contacts = config.get("hubspot", {}).get("max_contacts", 50)
    portal_url = _get_portal_url(config)

    filters = _build_search_filters(start_ms, end_ms, owner_id)
    contact_properties = [
        "firstname", "lastname", "company",
        "hubspot_owner_id", "hs_lastmodifieddate",
    ]

    try:
        request = ContactSearchRequest(
            filter_groups=[{"filters": filters}],
            properties=contact_properties,
            sorts=[{"propertyName": "hs_lastmodifieddate", "direction": "DESCENDING"}],
            limit=min(max_contacts, 100),
        )
        response = client.crm.contacts.search_api.do_search(
            public_object_search_request=request
        )

        for contact in response.results[:max_contacts]:
            props = contact.properties
            first = props.get("firstname", "")
            last = props.get("lastname", "")
            name = f"{first} {last}".strip() or "Unknown Contact"
            company = props.get("company", "")
            modified = props.get("hs_lastmodifieddate", "")

            ts = datetime.now(timezone.utc)
            if modified:
                try:
                    ts = datetime.fromisoformat(modified.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass

            display = f"HubSpot contact {name}"
            if company:
                display += f" ({company})"

            source_url = f"{portal_url}/contact/{contact.id}" if portal_url else ""

            content_parts = [f"Contact: {name}"]
            if company:
                content_parts.append(f"Company: {company}")

            items.append(SourceItem(
                id=f"hubspot-contact-{contact.id}",
                source_type=SourceType.HUBSPOT_CONTACT,
                content_type=ContentType.ACTIVITY,
                title=f"Activity on {name}",
                timestamp=ts,
                content=". ".join(content_parts),
                source_url=source_url,
                display_context=display,
            ))

    except Exception as e:
        logger.warning("Failed to fetch HubSpot contacts: %s", e)

    return items[:max_contacts]


def _fetch_tickets(
    client: HubSpot,
    start_ms: int,
    end_ms: int,
    config: dict,
    owner_map: dict[str, str],
    stage_map: dict[str, str] | None = None,
    owner_id: str | None = None,
) -> list[SourceItem]:
    """Fetch tickets modified on the target date.

    Returns SourceItems for ticket activity.
    """
    items: list[SourceItem] = []
    max_tickets = config.get("hubspot", {}).get("max_tickets", 25)
    portal_url = _get_portal_url(config)
    stage_map = stage_map or {}

    filters = _build_search_filters(start_ms, end_ms, owner_id)
    ticket_properties = [
        "subject", "hs_pipeline_stage", "hubspot_owner_id",
        "hs_lastmodifieddate", "createdate",
    ]

    try:
        request = TicketSearchRequest(
            filter_groups=[{"filters": filters}],
            properties=ticket_properties,
            sorts=[{"propertyName": "hs_lastmodifieddate", "direction": "DESCENDING"}],
            limit=min(max_tickets, 100),
        )
        response = client.crm.tickets.search_api.do_search(
            public_object_search_request=request
        )

        for ticket in response.results[:max_tickets]:
            props = ticket.properties
            subject = props.get("subject", "Untitled Ticket")
            status_id = props.get("hs_pipeline_stage", "")
            status = stage_map.get(status_id, status_id)
            owner_name = owner_map.get(props.get("hubspot_owner_id", ""), "Unknown")
            modified = props.get("hs_lastmodifieddate", "")

            ts = datetime.now(timezone.utc)
            if modified:
                try:
                    ts = datetime.fromisoformat(modified.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass

            content = f"Status: {status}. Owner: {owner_name}"
            source_url = f"{portal_url}/ticket/{ticket.id}" if portal_url else ""

            items.append(SourceItem(
                id=f"hubspot-ticket-{ticket.id}",
                source_type=SourceType.HUBSPOT_TICKET,
                content_type=ContentType.ACTIVITY,
                title=subject,
                timestamp=ts,
                content=content,
                source_url=source_url,
                display_context=f"HubSpot ticket {subject}",
            ))

    except Exception as e:
        logger.warning("Failed to fetch HubSpot tickets: %s", e)

    return items[:max_tickets]


def _fetch_engagements(
    client: HubSpot,
    start_ms: int,
    end_ms: int,
    config: dict,
    owner_map: dict[str, str],
    owner_id: str | None = None,
) -> list[SourceItem]:
    """Fetch engagement activities (notes, calls, emails, meetings, tasks).

    Per user decision: calls and meetings get more detail; emails and tasks
    get brief mentions.

    Returns SourceItems for engagement activity.
    """
    items: list[SourceItem] = []
    max_per_type = config.get("hubspot", {}).get("max_activities_per_type", 25)
    portal_url = _get_portal_url(config)

    engagement_types = [
        ("notes", "hs_note_body", ContentType.NOTE, SourceType.HUBSPOT_ACTIVITY, True),
        ("calls", "hs_call_title", ContentType.ACTIVITY, SourceType.HUBSPOT_ACTIVITY, True),
        ("meetings", "hs_meeting_title", ContentType.ACTIVITY, SourceType.HUBSPOT_ACTIVITY, True),
        ("emails", "hs_email_subject", ContentType.ACTIVITY, SourceType.HUBSPOT_ACTIVITY, False),
        ("tasks", "hs_task_subject", ContentType.ACTIVITY, SourceType.HUBSPOT_ACTIVITY, False),
    ]

    filters = _build_search_filters(start_ms, end_ms, owner_id)

    for eng_type, title_prop, content_type, source_type, detailed in engagement_types:
        try:
            search_api = getattr(client.crm.objects, eng_type, None)
            if search_api is None:
                continue

            from hubspot.crm.objects import PublicObjectSearchRequest as ObjSearchRequest
            request = ObjSearchRequest(
                filter_groups=[{"filters": filters}],
                properties=[title_prop, "hs_timestamp", "hubspot_owner_id", "hs_lastmodifieddate"],
                limit=min(max_per_type, 100),
            )
            response = search_api.search_api.do_search(
                public_object_search_request=request
            )

            for obj in response.results[:max_per_type]:
                props = obj.properties
                title = props.get(title_prop, f"Untitled {eng_type}")
                if not title:
                    title = f"Untitled {eng_type}"
                owner_name = owner_map.get(props.get("hubspot_owner_id", ""), "Unknown")
                modified = props.get("hs_lastmodifieddate", "") or props.get("hs_timestamp", "")

                ts = datetime.now(timezone.utc)
                if modified:
                    try:
                        ts = datetime.fromisoformat(modified.replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        pass

                # Calls/meetings get full detail; emails/tasks get brief
                if detailed:
                    content = f"{eng_type.capitalize()}: {title}. Owner: {owner_name}"
                else:
                    content = f"{eng_type.capitalize()}: {title}"

                items.append(SourceItem(
                    id=f"hubspot-{eng_type}-{obj.id}",
                    source_type=source_type,
                    content_type=content_type,
                    title=title,
                    timestamp=ts,
                    content=content,
                    participants=[owner_name] if detailed else [],
                    source_url=portal_url or "",
                    display_context=f"HubSpot {eng_type.rstrip('s')} {title}",
                ))

        except Exception as e:
            logger.warning("Failed to fetch HubSpot %s: %s", eng_type, e)

    return items


def fetch_hubspot_items(
    config: dict, target_date: date | None = None
) -> list[SourceItem]:
    """Main entry point: fetch all HubSpot CRM items for the target date.

    Fetches deals, contacts, tickets, and engagements. Applies ownership
    scoping and volume caps from config.

    Args:
        config: Pipeline configuration dict with hubspot section.
        target_date: The date to fetch items for. Defaults to today.

    Returns:
        Combined list of SourceItem objects from all HubSpot sources.
    """
    hubspot_config = config.get("hubspot", {})
    if not hubspot_config.get("enabled", False):
        return []

    if target_date is None:
        target_date = date.today()

    tz_name = config.get("pipeline", {}).get("timezone", "America/New_York")

    try:
        client = build_hubspot_client()
    except ValueError as e:
        logger.warning("HubSpot client init failed: %s", e)
        return []

    # Build lookup maps
    stage_map = _build_stage_map(client)
    ticket_stage_map = _build_ticket_stage_map(client)
    owner_map = _build_owner_map(client)
    owner_id = _resolve_owner_id(client, config, owner_map)

    # Date range
    start_ms, end_ms = _date_to_ms_range(target_date, tz_name)

    # Fetch all object types
    all_items: list[SourceItem] = []

    deal_items = _fetch_deals(client, start_ms, end_ms, config, stage_map, owner_map, owner_id)
    all_items.extend(deal_items)
    logger.info("Fetched %d HubSpot deal items", len(deal_items))

    contact_items = _fetch_contacts(client, start_ms, end_ms, config, owner_map, owner_id)
    all_items.extend(contact_items)
    logger.info("Fetched %d HubSpot contact items", len(contact_items))

    ticket_items = _fetch_tickets(client, start_ms, end_ms, config, owner_map, ticket_stage_map, owner_id)
    all_items.extend(ticket_items)
    logger.info("Fetched %d HubSpot ticket items", len(ticket_items))

    engagement_items = _fetch_engagements(client, start_ms, end_ms, config, owner_map, owner_id)
    all_items.extend(engagement_items)
    logger.info("Fetched %d HubSpot engagement items", len(engagement_items))

    logger.info("Total HubSpot items: %d", len(all_items))
    return all_items
