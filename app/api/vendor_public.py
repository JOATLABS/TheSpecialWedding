"""
Public Vendor API

Public (no auth required) endpoints for viewing vendor profiles.
Used by the public vendor profile page at /vendors/{id}.
"""

import logging
from fastapi import APIRouter, HTTPException
from bson import ObjectId

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
}


@router.get("/sitemap-ids")
async def get_vendor_sitemap_ids():
    """
    Return a list of active vendor IDs for the XML sitemap.
    No authentication required. Returns only IDs, no sensitive data.
    """
    cursor = mongo.db["vendor_profiles"].find(
        {"is_active": True},
        {"_id": 1}
    )
    ids = [str(doc["_id"]) async for doc in cursor]
    return ids


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
        {"_id": oid, "is_active": True},
        PUBLIC_VENDOR_FIELDS
    )

    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    # Convert ObjectId to string for JSON serialization
    vendor["_id"] = str(vendor["_id"])

    return vendor
