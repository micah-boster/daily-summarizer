"""HubSpot cross-reference for discovered entities.

Searches HubSpot contacts and deals by name with exact match
and fuzzy fallback, enriching entity records with external identifiers.
"""

from __future__ import annotations

import logging

from hubspot import HubSpot
from hubspot.crm.contacts import PublicObjectSearchRequest as ContactSearchRequest
from hubspot.crm.deals import PublicObjectSearchRequest as DealSearchRequest
from rapidfuzz import fuzz

from src.entity.normalizer import normalize_for_matching

logger = logging.getLogger(__name__)

FUZZY_THRESHOLD = 80  # Minimum token_sort_ratio for fuzzy match


def search_hubspot_contact(client: HubSpot, name: str) -> dict | None:
    """Search HubSpot contacts by name. Returns {id, email, confidence} or None."""
    try:
        request = ContactSearchRequest(
            query=name,
            properties=["firstname", "lastname", "email", "company"],
            limit=5,
        )
        response = client.crm.contacts.search_api.do_search(
            public_object_search_request=request
        )
        for contact in response.results:
            props = contact.properties
            full_name = f"{props.get('firstname', '')} {props.get('lastname', '')}".strip()
            # Exact match
            if full_name.lower() == name.lower():
                return {"id": contact.id, "email": props.get("email"), "confidence": 1.0}
            # Fuzzy match
            score = fuzz.token_sort_ratio(full_name.lower(), name.lower())
            if score >= FUZZY_THRESHOLD:
                return {"id": contact.id, "email": props.get("email"), "confidence": score / 100}
        return None
    except Exception as e:
        logger.warning("HubSpot contact search failed for '%s': %s", name, e)
        return None


def search_hubspot_deal(client: HubSpot, name: str) -> dict | None:
    """Search HubSpot deals by name. Returns {id, deal_stage, confidence} or None."""
    try:
        normalized = normalize_for_matching(name)
        request = DealSearchRequest(
            query=name,
            properties=["dealname", "dealstage"],
            limit=5,
        )
        response = client.crm.deals.search_api.do_search(
            public_object_search_request=request
        )
        for deal in response.results:
            deal_name = deal.properties.get("dealname", "")
            # Exact match (normalized)
            if normalize_for_matching(deal_name) == normalized:
                return {"id": deal.id, "deal_stage": deal.properties.get("dealstage"), "confidence": 1.0}
            # Fuzzy match
            score = fuzz.token_sort_ratio(deal_name.lower(), name.lower())
            if score >= FUZZY_THRESHOLD:
                return {"id": deal.id, "deal_stage": deal.properties.get("dealstage"), "confidence": score / 100}
        return None
    except Exception as e:
        logger.warning("HubSpot deal search failed for '%s': %s", name, e)
        return None


def cross_reference_entity(
    entity_name: str,
    entity_type: str,
    config,
) -> dict | None:
    """Cross-reference an entity name with HubSpot contacts and deals.

    Returns dict with match info (hubspot_id, type, confidence, metadata) or None.
    """
    access_token = getattr(config.hubspot, "access_token", "")
    if not access_token:
        return None

    try:
        client = HubSpot(access_token=access_token)

        # For people: search contacts first
        if entity_type == "person":
            contact = search_hubspot_contact(client, entity_name)
            if contact:
                return {
                    "hubspot_id": contact["id"],
                    "hubspot_type": "contact",
                    "email": contact.get("email"),
                    "confidence": contact["confidence"],
                }

        # For partners: search deals first, then contacts
        if entity_type == "partner":
            deal = search_hubspot_deal(client, entity_name)
            if deal:
                return {
                    "hubspot_id": deal["id"],
                    "hubspot_type": "deal",
                    "deal_stage": deal.get("deal_stage"),
                    "confidence": deal["confidence"],
                }
            # Also try contacts (partner companies may be contacts)
            contact = search_hubspot_contact(client, entity_name)
            if contact:
                return {
                    "hubspot_id": contact["id"],
                    "hubspot_type": "contact",
                    "email": contact.get("email"),
                    "confidence": contact["confidence"],
                }

        return None

    except Exception as e:
        logger.warning("HubSpot cross-reference failed for '%s': %s", entity_name, e)
        return None
