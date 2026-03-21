"""
Vendor Campaign API Router

REST API for vendor self-service campaign management.
Vendors access these endpoints from their portal at /portal/ads/.

All endpoints require advertising_vendor auth (is_advertising_vendor).
Root admin can also access all endpoints for support/debugging.

PRD Reference: Section 6.4 (Vendor Campaign Manager)
Routes: /portal/ads/campaigns/*
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from app.dependencies.auth_extended import (
    get_current_user_extended,
    ExtendedAuthUser,
)
from app.core.database import mongo
from app.services.vendor_campaign_service import VendorCampaignService
from app.models.advertising_campaign import (
    CreateCampaignRequest,
    UpdateCampaignRequest,
    CreateCreativeRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/portal/ads", tags=["Vendor Campaigns"])


# =============================================================================
# DEPENDENCY INJECTION
# =============================================================================

async def get_vendor_campaign_service() -> VendorCampaignService:
    """Get vendor campaign service instance."""
    return VendorCampaignService(mongo.db)


async def require_advertising_vendor(
    current_user: ExtendedAuthUser = Depends(get_current_user_extended),
) -> ExtendedAuthUser:
    """
    Require advertising_vendor role or root admin.

    Advertising vendors are independent entities, separate from
    planner-added vendors. They sign up at vendor.thespecialwedding.io.
    """
    if current_user.is_root_admin or current_user.is_advertising_vendor:
        return current_user
    raise HTTPException(
        status_code=403,
        detail="Advertising vendor access required"
    )


def _get_vendor_id(user: ExtendedAuthUser) -> str:
    """
    Extract the vendor's user _id for campaign ownership.

    This is the advertising vendor's user _id from the users collection,
    NOT a vendor_profile_id from the planner vendor directory.
    """
    vendor_id = user.user_data.get("_id")
    if not vendor_id:
        raise HTTPException(status_code=400, detail="Vendor identity not found")
    return str(vendor_id)


# =============================================================================
# CAMPAIGN CRUD
# =============================================================================

@router.post("/campaigns", status_code=201)
async def create_campaign(
    request: CreateCampaignRequest,
    service: VendorCampaignService = Depends(get_vendor_campaign_service),
    current_user: ExtendedAuthUser = Depends(require_advertising_vendor),
):
    """
    Create a new draft campaign.

    Vendors start here. The campaign is created in 'draft' status.
    Add creatives, set targeting, then submit for review.
    """
    vendor_id = _get_vendor_id(current_user)
    data = request.model_dump(exclude_unset=True)

    return await service.create_campaign(
        vendor_id=vendor_id,
        vendor_email=current_user.email,
        vendor_name=current_user.user_data.get("name", current_user.email),
        data=data,
    )


@router.get("/campaigns")
async def list_campaigns(
    status: Optional[str] = Query(None, description="Filter by campaign status"),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    service: VendorCampaignService = Depends(get_vendor_campaign_service),
    current_user: ExtendedAuthUser = Depends(require_advertising_vendor),
):
    """List the vendor's own campaigns."""
    vendor_id = _get_vendor_id(current_user)
    return await service.list_campaigns(
        vendor_id=vendor_id,
        status_filter=status,
        limit=limit,
        skip=skip,
    )


@router.get("/campaigns/{campaign_id}")
async def get_campaign(
    campaign_id: str,
    service: VendorCampaignService = Depends(get_vendor_campaign_service),
    current_user: ExtendedAuthUser = Depends(require_advertising_vendor),
):
    """Get a single campaign (vendor-scoped)."""
    vendor_id = _get_vendor_id(current_user)
    return await service.get_campaign(campaign_id, vendor_id=vendor_id)


@router.put("/campaigns/{campaign_id}")
async def update_campaign(
    campaign_id: str,
    request: UpdateCampaignRequest,
    service: VendorCampaignService = Depends(get_vendor_campaign_service),
    current_user: ExtendedAuthUser = Depends(require_advertising_vendor),
):
    """
    Update a draft campaign.

    Only campaigns in 'draft' status can be edited. Active campaigns
    must be paused first (future phase: edit-and-resubmit flow).
    """
    vendor_id = _get_vendor_id(current_user)
    updates = request.model_dump(exclude_unset=True)
    return await service.update_campaign(campaign_id, vendor_id, updates)


@router.delete("/campaigns/{campaign_id}")
async def delete_campaign(
    campaign_id: str,
    service: VendorCampaignService = Depends(get_vendor_campaign_service),
    current_user: ExtendedAuthUser = Depends(require_advertising_vendor),
):
    """
    Delete a draft campaign.

    Only campaigns in 'draft' status can be deleted. This is a hard delete
    since drafts have no live data associated with them.
    """
    vendor_id = _get_vendor_id(current_user)
    return await service.delete_campaign(campaign_id, vendor_id)


# =============================================================================
# CAMPAIGN LIFECYCLE
# =============================================================================

@router.post("/campaigns/{campaign_id}/submit")
async def submit_for_review(
    campaign_id: str,
    service: VendorCampaignService = Depends(get_vendor_campaign_service),
    current_user: ExtendedAuthUser = Depends(require_advertising_vendor),
):
    """
    Submit a draft campaign for root admin review.

    Validates that the campaign has: a name, at least one primary creative,
    a vendor category, and at least one target region.
    """
    vendor_id = _get_vendor_id(current_user)
    return await service.submit_for_review(campaign_id, vendor_id)


@router.post("/campaigns/{campaign_id}/pause")
async def pause_campaign(
    campaign_id: str,
    service: VendorCampaignService = Depends(get_vendor_campaign_service),
    current_user: ExtendedAuthUser = Depends(require_advertising_vendor),
):
    """
    Vendor pauses their active campaign.

    Stops ad serving immediately. Vendor can contact admin to reactivate.
    """
    vendor_id = _get_vendor_id(current_user)
    return await service.pause_campaign(campaign_id, vendor_id)


# =============================================================================
# CAMPAIGN STATS
# =============================================================================

@router.get("/campaigns/{campaign_id}/stats")
async def get_campaign_stats(
    campaign_id: str,
    days: int = Query(30, ge=1, le=365, description="Days of history"),
    service: VendorCampaignService = Depends(get_vendor_campaign_service),
    current_user: ExtendedAuthUser = Depends(require_advertising_vendor),
):
    """
    Get campaign performance stats.

    Returns lifetime totals + daily time series from campaign_day_stats.
    """
    vendor_id = _get_vendor_id(current_user)
    return await service.get_campaign_stats(campaign_id, vendor_id, days)


# =============================================================================
# CREATIVE MANAGEMENT
# =============================================================================

@router.post("/campaigns/{campaign_id}/creatives", status_code=201)
async def create_creative(
    campaign_id: str,
    request: CreateCreativeRequest,
    service: VendorCampaignService = Depends(get_vendor_campaign_service),
    current_user: ExtendedAuthUser = Depends(require_advertising_vendor),
):
    """
    Create a new creative for a campaign.

    Image upload is handled separately via presigned R2 URL (AdUploadService).
    Pass the resulting CDN URL as image_url in this request.

    Creatives start in 'pending' review status. The first creative
    (or one marked is_primary=true) becomes the campaign's primary.
    """
    vendor_id = _get_vendor_id(current_user)
    data = request.model_dump(exclude_unset=True)
    return await service.create_creative(campaign_id, vendor_id, data)


@router.get("/campaigns/{campaign_id}/creatives")
async def list_creatives(
    campaign_id: str,
    service: VendorCampaignService = Depends(get_vendor_campaign_service),
    current_user: ExtendedAuthUser = Depends(require_advertising_vendor),
):
    """List creatives for a campaign (vendor-scoped)."""
    vendor_id = _get_vendor_id(current_user)
    # Verify campaign ownership first
    await service.get_campaign(campaign_id, vendor_id=vendor_id)
    return await service.list_creatives(campaign_id, vendor_id=vendor_id)


@router.put("/creatives/{creative_id}")
async def update_creative(
    creative_id: str,
    request: CreateCreativeRequest,
    service: VendorCampaignService = Depends(get_vendor_campaign_service),
    current_user: ExtendedAuthUser = Depends(require_advertising_vendor),
):
    """
    Update a creative.

    If content fields change on an approved creative, it automatically
    reverts to 'pending' review status (creative freeze policy).
    """
    vendor_id = _get_vendor_id(current_user)
    updates = request.model_dump(exclude_unset=True)
    return await service.update_creative(creative_id, vendor_id, updates)


@router.post("/campaigns/{campaign_id}/creatives/{creative_id}/set-primary")
async def set_primary_creative(
    campaign_id: str,
    creative_id: str,
    service: VendorCampaignService = Depends(get_vendor_campaign_service),
    current_user: ExtendedAuthUser = Depends(require_advertising_vendor),
):
    """Set a creative as the campaign's primary (shown in the planner rail)."""
    vendor_id = _get_vendor_id(current_user)
    return await service.set_primary_creative(campaign_id, creative_id, vendor_id)


# =============================================================================
# LEADS
# =============================================================================

@router.get("/leads")
async def get_vendor_leads(
    status: Optional[str] = Query(None, description="Filter by lead status"),
    lead_type: Optional[str] = Query(None, description="Filter by lead type"),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    service: VendorCampaignService = Depends(get_vendor_campaign_service),
    current_user: ExtendedAuthUser = Depends(require_advertising_vendor),
):
    """
    List leads from all of the vendor's campaigns.

    Leads are created when planners interact with sponsored cards:
    quote_request, add_to_directory, message, vendor_invite.
    """
    vendor_id = _get_vendor_id(current_user)
    return await service.get_vendor_leads(
        vendor_id=vendor_id,
        status_filter=status,
        lead_type_filter=lead_type,
        limit=limit,
        skip=skip,
    )


# =============================================================================
# BILLING (Placeholder — free tier)
# =============================================================================

@router.get("/billing")
async def get_billing_summary(
    current_user: ExtendedAuthUser = Depends(require_advertising_vendor),
):
    """
    Billing summary for the vendor.

    Currently always returns $0 (free tier). When billing goes live,
    this will show spend per campaign, invoices, and payment status.
    """
    vendor_id = _get_vendor_id(current_user)
    return {
        "vendor_id": vendor_id,
        "billing_status": "free_tier",
        "total_spend": 0.0,
        "currency": "USD",
        "message": "Advertising is currently free during our beta period.",
    }
