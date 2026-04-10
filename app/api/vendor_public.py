"""
Public Vendor API

Public (no auth required) endpoints for viewing vendor profiles.
Used by the public vendor profile page at /vendors/{id}.
"""

import logging

from bson import ObjectId
from fastapi import APIRouter, HTTPException

from app.core.database import mongo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/vendors", tags=["Public Vendors"])


# Fields safe to expose publicly (excludes internal notes, tax IDs, revenue, etc.)
PUBLIC_VENDOR_FIELDS = {
    "_id": 1,
    "business_name": 1,
    "contact_name": 1,
    "email": 1,
    "phone": 1,
    "website": 1,
    "address": 1,
    "city": 1,
    "state": 1,
    "country": 1,
    "service_category": 1,
    "custom_service_category": 1,
    "service_subcategories": 1,
    "service_description": 1,
    "portfolio_urls": 1,
    "logo_url": 1,
    "typical_price_min": 1,
    "typical_price_max": 1,
    "currency": 1,
    "lead_time_days": 1,
    "service_radius_miles": 1,
    "is_preferred": 1,
    "weddings_count": 1,
    "tags": 1,
    "source": 1,
    "google_place_id": 1,
}


def _normalize_public_vendor_doc(doc: dict) -> dict:
    """Backfill optional collection fields for older vendor records."""
    doc["service_subcategories"] = doc.get("service_subcategories") or []
    doc["portfolio_urls"] = doc.get("portfolio_urls") or []
    doc["tags"] = doc.get("tags") or []
    doc["currency"] = doc.get("currency") or "USD"
    doc["source"] = doc.get("source") or "manual"
    return doc


@router.get("/sitemap-ids")
async def get_vendor_sitemap_ids():
    """
    Return a list of active vendor IDs for the XML sitemap.
    No authentication required. Returns only IDs, no sensitive data.
    """
    cursor = mongo.db["vendor_profiles"].find({"is_active": True}, {"_id": 1})
    ids = [str(doc["_id"]) async for doc in cursor]
    return ids


@router.get("/directory")
async def list_public_vendors(
    category: str = None,
    location: str = None,
    search: str = None,
    limit: int = 24,
    skip: int = 0,
):
    """
    List active vendors for the public directory page. No auth required.
    Returns only publicly-safe fields. Supports category, location, and search filters.
    """
    query = {"is_active": True}

    if category:
        query["service_category"] = category
    if location:
        query["$or"] = [
            {"city": {"$regex": location, "$options": "i"}},
            {"state": {"$regex": location, "$options": "i"}},
            {"country": {"$regex": location, "$options": "i"}},
        ]
    if search:
        search_conditions = [
            {"business_name": {"$regex": search, "$options": "i"}},
            {"service_description": {"$regex": search, "$options": "i"}},
            {"service_category": {"$regex": search, "$options": "i"}},
        ]
        if "$or" in query:
            query["$and"] = [{"$or": query.pop("$or")}, {"$or": search_conditions}]
        else:
            query["$or"] = search_conditions

    limit = min(limit, 50)  # cap at 50

    total = await mongo.db["vendor_profiles"].count_documents(query)
    cursor = (
        mongo.db["vendor_profiles"]
        .find(query, PUBLIC_VENDOR_FIELDS)
        .sort("weddings_count", -1)
        .skip(skip)
        .limit(limit)
    )
    vendors = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        doc = _normalize_public_vendor_doc(doc)
        vendors.append(doc)

    # Get distinct categories for filter dropdown
    categories = await mongo.db["vendor_profiles"].distinct(
        "service_category", {"is_active": True}
    )

    return {
        "vendors": vendors,
        "total": total,
        "categories": sorted([c for c in categories if c]),
        "page": skip // limit + 1 if limit > 0 else 1,
        "page_size": limit,
    }


@router.get("/{vendor_id}/public")
async def get_public_vendor_profile(vendor_id: str):
    """
    Get a vendor's public profile. No authentication required.
    Returns only publicly-safe fields (no internal notes, tax IDs, revenue, etc.).
    """
    try:
        oid = ObjectId(vendor_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Vendor not found")

    vendor = await mongo.db["vendor_profiles"].find_one(
        {"_id": oid, "is_active": True}, PUBLIC_VENDOR_FIELDS
    )

    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    # Convert ObjectId to string for JSON serialization
    vendor["_id"] = str(vendor["_id"])
    vendor = _normalize_public_vendor_doc(vendor)

    return vendor
