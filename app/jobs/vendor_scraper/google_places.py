"""
Google Places API Client

Uses the Google Places Text Search (New) API to find wedding vendors
by city and category. Returns structured results with name, address,
phone, website, rating, and photo references.

Requires GOOGLE_MAPS_API_KEY in environment.
"""

import os
import logging
from typing import List, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

# Google Places Text Search endpoint (New API)
TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

# Google Places Photo endpoint
PHOTO_URL_TEMPLATE = "https://places.googleapis.com/v1/{photo_name}/media"

# Fields we request (controls billing — only request what we need)
FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.nationalPhoneNumber",
        "places.internationalPhoneNumber",
        "places.websiteUri",
        "places.rating",
        "places.userRatingCount",
        "places.photos",
        "places.addressComponents",
        "places.location",
        "places.priceLevel",
    ]
)


async def search_vendors(query: str, max_results: int = 20) -> List[Dict]:
    """
    Search Google Places for vendors matching the query.

    Args:
        query: e.g. "wedding photographer in Atlanta, GA"
        max_results: max results to return (Google caps at 20 per request)

    Returns:
        List of dicts with normalized vendor data.
    """
    if not GOOGLE_MAPS_API_KEY:
        logger.error("GOOGLE_MAPS_API_KEY not set — cannot search Google Places")
        return []

    try:
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
            "X-Goog-FieldMask": FIELD_MASK,
        }
        body = {
            "textQuery": query,
            "maxResultCount": min(max_results, 20),
            "languageCode": "en",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(TEXT_SEARCH_URL, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        places = data.get("places", [])
        results = []

        for place in places:
            vendor_data = _normalize_place(place)
            if vendor_data:
                results.append(vendor_data)

        logger.info(f"Google Places returned {len(results)} results for: {query}")
        return results

    except httpx.HTTPStatusError as e:
        logger.error(
            f"Google Places API error ({e.response.status_code}): {e.response.text[:300]}"
        )
        return []
    except Exception as e:
        logger.error(f"Google Places search failed for '{query}': {e}")
        return []


def _normalize_place(place: Dict) -> Optional[Dict]:
    """Extract and normalize fields from a Google Places result."""
    place_id = place.get("id")
    display_name = place.get("displayName", {}).get("text", "").strip()
    if not display_name:
        return None

    # Parse address components into city/state/country/postal_code
    address_parts = _parse_address_components(place.get("addressComponents", []))

    # Get the best photo reference
    photo_url = None
    photos = place.get("photos", [])
    if photos:
        photo_name = photos[0].get("name")
        if photo_name:
            photo_url = get_photo_url(photo_name, max_width=400)

    return {
        "google_place_id": place_id,
        "business_name": display_name,
        "address": place.get("formattedAddress"),
        "city": address_parts.get("city"),
        "state": address_parts.get("state"),
        "country": address_parts.get("country", "US"),
        "postal_code": address_parts.get("postal_code"),
        "phone": place.get("nationalPhoneNumber")
        or place.get("internationalPhoneNumber"),
        "website": place.get("websiteUri"),
        "google_rating": place.get("rating"),
        "google_rating_count": place.get("userRatingCount"),
        "photo_url": photo_url,
    }


def _parse_address_components(components: List[Dict]) -> Dict[str, str]:
    """Extract city, state, country, postal_code from Google address components."""
    result = {}
    for comp in components:
        types = comp.get("types", [])
        text = comp.get("longText", "")
        short = comp.get("shortText", "")

        if "locality" in types:
            result["city"] = text
        elif "administrative_area_level_1" in types:
            result["state"] = short  # e.g. "GA" instead of "Georgia"
        elif "country" in types:
            result["country"] = short  # e.g. "US"
        elif "postal_code" in types:
            result["postal_code"] = text

    return result


def get_photo_url(photo_name: str, max_width: int = 400) -> str:
    """
    Build a Google Places photo URL.

    The photo_name comes from the Places API response (e.g. "places/ChIJ.../photos/AfL...")
    and the media endpoint returns the actual image when called with the API key.
    """
    return (
        f"{PHOTO_URL_TEMPLATE.format(photo_name=photo_name)}"
        f"?maxWidthPx={max_width}&key={GOOGLE_MAPS_API_KEY}"
    )
