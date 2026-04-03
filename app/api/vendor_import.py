"""
Vendor Import API

ROOT_ADMIN-only endpoint for importing vendors from the
local scraper's JSON export file.

POST /admin/vendors/import
  - Accepts JSON array of scraped vendor objects
  - Validates and sanitizes each entry
  - Upserts via VendorService.upsert_scraped_vendor()
  - Returns counts: {inserted, updated, skipped, errors}
"""

import logging
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.dependencies.auth_extended import require_root_admin, ExtendedAuthUser
from app.services.vendor_service import vendor_service
from app.models.vendor import VendorCategory

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── Request / Response Models ──────────────────────────────────────────────

VALID_CATEGORIES = {c.value for c in VendorCategory}
MAX_IMPORT_SIZE = 500  # Hard cap on vendors per import


class VendorImportItem(BaseModel):
    """A single vendor entry from the scraper export JSON."""
    google_place_id: Optional[str] = None
    business_name: str = Field(..., min_length=1, max_length=200)
    email: Optional[str] = Field(default="", max_length=200)
    phone: Optional[str] = Field(default=None, max_length=30)
    website: Optional[str] = Field(default=None, max_length=500)
    address: Optional[str] = Field(default=None, max_length=500)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    country: Optional[str] = Field(default="US", max_length=10)
    postal_code: Optional[str] = Field(default=None, max_length=20)
    service_category: str = Field(...)
    service_description: Optional[str] = Field(default=None, max_length=2000)
    logo_url: Optional[str] = Field(default=None, max_length=1000)
    typical_price_min: Optional[float] = Field(default=None, ge=0)
    typical_price_max: Optional[float] = Field(default=None, ge=0)
    currency: str = Field(default="USD", max_length=5)
    tags: List[str] = Field(default_factory=list)
    scraped_from_state: Optional[str] = None

    @field_validator("service_category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if v not in VALID_CATEGORIES:
            raise ValueError(f"Invalid category '{v}'. Must be one of: {', '.join(sorted(VALID_CATEGORIES))}")
        return v

    @field_validator("business_name")
    @classmethod
    def sanitize_business_name(cls, v: str) -> str:
        # Strip HTML tags
        return re.sub(r"<[^>]+>", "", v).strip()

    @field_validator("service_description")
    @classmethod
    def sanitize_description(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        # Strip HTML tags
        return re.sub(r"<[^>]+>", "", v).strip()[:2000]

    @field_validator("website")
    @classmethod
    def validate_website(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        # Basic URL sanity check — block internal/private IPs
        lower = v.lower()
        blocked_patterns = ["127.0.0.1", "localhost", "10.", "192.168.", "169.254.", "0.0.0.0"]
        for pattern in blocked_patterns:
            if pattern in lower:
                return None
        if not lower.startswith(("http://", "https://")):
            return f"https://{v}"
        return v


class VendorImportRequest(BaseModel):
    """Request body for bulk vendor import."""
    vendors: List[VendorImportItem] = Field(..., min_length=1, max_length=MAX_IMPORT_SIZE)


class VendorImportResponse(BaseModel):
    """Response from vendor import."""
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    error_details: List[Dict[str, Any]] = Field(default_factory=list)
    total: int = 0


# ─── Endpoint ───────────────────────────────────────────────────────────────

@router.post(
    "/vendors/import",
    response_model=VendorImportResponse,
    tags=["Vendor Import"],
    summary="Import vendors from scraper JSON export",
)
async def import_vendors(
    request: VendorImportRequest,
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """
    Import scraped vendors into the vendor directory.

    Accepts the JSON output from the vendor scraper CLI export.
    Each vendor is upserted — existing entries (matched by google_place_id
    or business_name+city+category) are refreshed, new ones are inserted.
    Manually-added vendors are never overwritten.

    ROOT_ADMIN only.
    """
    stats = VendorImportResponse(total=len(request.vendors))

    for i, item in enumerate(request.vendors):
        try:
            vendor_data = item.model_dump(exclude_none=True)
            result = await vendor_service.upsert_scraped_vendor(vendor_data)

            if result is None:
                stats.skipped += 1
            elif result.get("created_at") == result.get("updated_at"):
                # Newly inserted — created_at and updated_at are the same
                stats.inserted += 1
            else:
                # Existing record was refreshed, or it was a manual entry (skipped)
                source = result.get("source", "manual")
                if source == "manual":
                    stats.skipped += 1
                else:
                    stats.updated += 1

        except Exception as e:
            stats.errors += 1
            stats.error_details.append({
                "index": i,
                "business_name": item.business_name,
                "error": str(e),
            })
            logger.error(f"Import error for vendor '{item.business_name}': {e}")

    logger.info(
        f"Vendor import complete by {current_user.email}: "
        f"{stats.inserted} inserted, {stats.updated} updated, "
        f"{stats.skipped} skipped, {stats.errors} errors"
    )

    return stats
