"""
Admin Campaign API Router

REST API for root admin campaign moderation, monitoring, and configuration.
This is the NEW campaign-centric admin API.

The OLD advertising.py router manages legacy sponsored_vendors and will be
deprecated once the campaign platform is fully live (Phase 5).

All endpoints require ROOT_ADMIN auth.

PRD Reference: Section 6.8 (Admin Moderation Console)
Routes: /admin/ads/campaigns/*  (campaign monitor & review)
"""

import logging
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.core.database import mongo
from app.dependencies.auth_extended import ExtendedAuthUser, require_root_admin
from app.models.advertising_campaign import (
    ReviewCampaignDecisionRequest,
    ReviewCreativeDecisionRequest,
    SetFreeTierRequest,
    UpdateCPLPricingRequest,
)
from app.services.admin_campaign_service import AdminCampaignService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/ads/campaigns", tags=["Admin Campaigns"])


# =============================================================================
# DEPENDENCY INJECTION
# =============================================================================


async def get_admin_campaign_service() -> AdminCampaignService:
    """Get admin campaign service instance."""
    return AdminCampaignService(mongo.db)


def get_ad_billing_service():
    """Get ad billing service instance."""
    from app.services.ad_billing_service import AdBillingService

    try:
        from app.services.stripe_service import StripeService

        stripe_svc = StripeService(mongo.db)
    except Exception:
        stripe_svc = None
    return AdBillingService(mongo.db, stripe_service=stripe_svc)


# =============================================================================
# REVIEW QUEUE
# =============================================================================


@router.get("/review")
async def get_review_queue(
    status: Optional[str] = Query(
        None, description="Filter by status (default: pending_review)"
    ),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    service: AdminCampaignService = Depends(get_admin_campaign_service),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """
    Get the campaign review queue.

    Returns campaigns pending review with their primary creative inlined
    for the review card display. Sorted by submitted_at (FIFO).
    """
    return await service.get_review_queue(
        status_filter=status,
        limit=limit,
        skip=skip,
    )


@router.get("/review/counts")
async def get_review_counts(
    service: AdminCampaignService = Depends(get_admin_campaign_service),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """
    Get status counts for the review dashboard.

    Returns: pending_review, active, paused, rejected, draft, completed, total.
    """
    return await service.get_review_counts()


# =============================================================================
# CAMPAIGN REVIEW ACTIONS
# =============================================================================


@router.put("/{campaign_id}/approve")
async def approve_campaign(
    campaign_id: str,
    request: ReviewCampaignDecisionRequest = Body(
        default=ReviewCampaignDecisionRequest(review_notes=None)
    ),
    service: AdminCampaignService = Depends(get_admin_campaign_service),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """
    Approve a pending_review campaign.

    Sets campaign status to 'active'. Also auto-approves all pending
    creatives for this campaign.
    """
    return await service.approve_campaign(
        campaign_id=campaign_id,
        admin_email=current_user.email,
        review_notes=request.review_notes,
    )


@router.put("/{campaign_id}/reject")
async def reject_campaign(
    campaign_id: str,
    request: ReviewCampaignDecisionRequest = Body(
        default=ReviewCampaignDecisionRequest(review_notes=None)
    ),
    service: AdminCampaignService = Depends(get_admin_campaign_service),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Reject a pending_review campaign with optional notes."""
    return await service.reject_campaign(
        campaign_id=campaign_id,
        admin_email=current_user.email,
        review_notes=request.review_notes,
    )


@router.put("/{campaign_id}/request-changes")
async def request_changes(
    campaign_id: str,
    request: ReviewCampaignDecisionRequest,
    service: AdminCampaignService = Depends(get_admin_campaign_service),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """
    Return a pending_review campaign to the vendor for changes.

    Review notes are REQUIRED — they tell the vendor what to fix.
    Campaign status returns to 'draft' so the vendor can edit and resubmit.
    """
    return await service.request_changes(
        campaign_id=campaign_id,
        admin_email=current_user.email,
        review_notes=request.review_notes or "",
    )


# =============================================================================
# CREATIVE REVIEW
# =============================================================================


@router.get("/review/creatives")
async def get_creative_review_queue(
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    service: AdminCampaignService = Depends(get_admin_campaign_service),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Get creatives pending review."""
    return await service.get_creative_review_queue(limit=limit, skip=skip)


@router.put("/review/creatives/{creative_id}/approve")
async def approve_creative(
    creative_id: str,
    request: ReviewCreativeDecisionRequest = Body(
        default=ReviewCreativeDecisionRequest(review_notes=None)
    ),
    service: AdminCampaignService = Depends(get_admin_campaign_service),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Approve a pending creative."""
    return await service.approve_creative(
        creative_id=creative_id,
        admin_email=current_user.email,
        review_notes=request.review_notes,
    )


@router.put("/review/creatives/{creative_id}/reject")
async def reject_creative(
    creative_id: str,
    request: ReviewCreativeDecisionRequest = Body(
        default=ReviewCreativeDecisionRequest(review_notes=None)
    ),
    service: AdminCampaignService = Depends(get_admin_campaign_service),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Reject a pending creative with optional notes."""
    return await service.reject_creative(
        creative_id=creative_id,
        admin_email=current_user.email,
        review_notes=request.review_notes,
    )


# =============================================================================
# CAMPAIGN MONITORING
# =============================================================================


@router.get("/")
async def list_all_campaigns(
    status: Optional[str] = Query(None, description="Filter by campaign status"),
    vendor_id: Optional[str] = Query(None, description="Filter by vendor"),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    service: AdminCampaignService = Depends(get_admin_campaign_service),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """
    List all campaigns across all vendors.

    Admin campaign monitor — see every campaign on the platform,
    filter by status or vendor.
    """
    return await service.list_all_campaigns(
        status_filter=status,
        vendor_id=vendor_id,
        limit=limit,
        skip=skip,
    )


@router.put("/{campaign_id}/pause")
async def admin_pause_campaign(
    campaign_id: str,
    reason: Optional[str] = Body(None, embed=True),
    service: AdminCampaignService = Depends(get_admin_campaign_service),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """
    Admin forcibly pauses an active campaign.

    Use for policy concerns that don't warrant a full rejection.
    """
    return await service.admin_pause_campaign(
        campaign_id=campaign_id,
        admin_email=current_user.email,
        reason=reason,
    )


@router.put("/{campaign_id}/deactivate")
async def admin_deactivate_campaign(
    campaign_id: str,
    reason: Optional[str] = Body(None, embed=True),
    service: AdminCampaignService = Depends(get_admin_campaign_service),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """
    Admin kills a campaign (sets to rejected from any non-terminal status).

    Use for policy violations or emergency takedowns.
    """
    return await service.admin_deactivate_campaign(
        campaign_id=campaign_id,
        admin_email=current_user.email,
        reason=reason,
    )


# =============================================================================
# REVENUE & ENGAGEMENT
# =============================================================================


@router.get("/revenue")
async def get_revenue_summary(
    days: int = Query(30, ge=1, le=365, description="Period in days"),
    service: AdminCampaignService = Depends(get_admin_campaign_service),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """
    Revenue & engagement summary.

    For free tier, total_revenue is always $0. The engagement metrics
    (impressions, clicks, leads, unique planners, CTR) are real.
    """
    return await service.get_revenue_summary(days=days)


# =============================================================================
# PLANNER FEEDBACK
# =============================================================================


@router.get("/feedback")
async def get_planner_feedback(
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    service: AdminCampaignService = Depends(get_admin_campaign_service),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """
    Planner ad feedback: hidden vendors, suppressed categories,
    reduced frequency requests. Helps admin understand sentiment.
    """
    return await service.get_planner_feedback(limit=limit, skip=skip)


# =============================================================================
# FRAUD SIGNALS
# =============================================================================


@router.get("/fraud-signals")
async def get_fraud_signals(
    status: Optional[str] = Query(None, description="Filter by signal status"),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    service: AdminCampaignService = Depends(get_admin_campaign_service),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Get fraud/anomaly signals (auto-expire after 7 days via TTL index)."""
    return await service.get_fraud_signals(status_filter=status, limit=limit, skip=skip)


@router.put("/fraud-signals/{signal_id}")
async def update_fraud_signal(
    signal_id: str,
    status: str = Body(..., embed=True),
    notes: Optional[str] = Body(None, embed=True),
    service: AdminCampaignService = Depends(get_admin_campaign_service),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Update a fraud signal investigation status."""
    return await service.update_fraud_signal(
        signal_id=signal_id,
        admin_email=current_user.email,
        status=status,
        notes=notes,
    )


# =============================================================================
# VENDOR ACCOUNTS
# =============================================================================


@router.post("/vendors/bulk", status_code=201)
async def bulk_create_vendors(
    vendors: list = Body(
        ...,
        description="List of vendor objects with email, business_name, category, location",
    ),
    service: AdminCampaignService = Depends(get_admin_campaign_service),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """
    Bulk-create advertising vendor accounts.

    Accepts a JSON array of vendor objects. Each must have `email` and `business_name`.
    Optional fields: `category`, `location`, `phone`, `website`, `is_free_tier`.

    Returns summary: created/skipped/failed counts with details.
    """
    if len(vendors) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 vendors per batch")
    return await service.bulk_create_vendor_accounts(
        vendors=vendors,
        admin_email=current_user.email,
    )


@router.get("/vendors")
async def list_vendor_accounts(
    status: Optional[str] = Query(None, description="Filter by account status"),
    category: Optional[str] = Query(None, description="Filter by vendor category"),
    location: Optional[str] = Query(None, description="Text search on vendor location"),
    date_from: Optional[str] = Query(
        None, description="Filter created_at >= this ISO date"
    ),
    date_to: Optional[str] = Query(
        None, description="Filter created_at <= this ISO date"
    ),
    search: Optional[str] = Query(
        None, description="Text search on email or business_name"
    ),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: int = Query(-1, description="Sort order: -1 desc, 1 asc"),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    service: AdminCampaignService = Depends(get_admin_campaign_service),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """List advertising vendor accounts with advanced filtering."""
    return await service.list_vendor_accounts(
        status_filter=status,
        category_filter=category,
        location_filter=location,
        date_from=date_from,
        date_to=date_to,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        skip=skip,
    )


# =============================================================================
# EVENT QUERY ENGINE (Elasticsearch-style)
# =============================================================================


@router.get("/events/query")
async def query_events(
    event_types: Optional[str] = Query(
        None, description="Comma-separated event types to filter"
    ),
    campaign_id: Optional[str] = Query(None, description="Filter by campaign ID"),
    vendor_id: Optional[str] = Query(None, description="Filter by vendor ID"),
    planner_id: Optional[str] = Query(None, description="Filter by planner ID"),
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
    date_from: Optional[str] = Query(None, description="Filter created_at >= ISO date"),
    date_to: Optional[str] = Query(None, description="Filter created_at <= ISO date"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: int = Query(-1, description="-1 desc, 1 asc"),
    limit: int = Query(100, ge=1, le=1000),
    skip: int = Query(0, ge=0),
    aggregate_by: Optional[str] = Query(
        None,
        description="Group by field: event_type, campaign_id, vendor_id, planner_id, placement",
    ),
    service: AdminCampaignService = Depends(get_admin_campaign_service),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """
    Elasticsearch-style event query with filtering, pagination, and aggregation.

    Supports filtering by event_type, campaign_id, vendor_id, planner_id, session_id,
    date range, and optional aggregation (returns grouped counts instead of raw docs).
    """
    event_type_list = (
        [t.strip() for t in event_types.split(",")] if event_types else None
    )
    return await service.query_events(
        event_types=event_type_list,
        campaign_id=campaign_id,
        vendor_id=vendor_id,
        planner_id=planner_id,
        session_id=session_id,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        skip=skip,
        aggregate_by=aggregate_by,
    )


# =============================================================================
# BATCH VENDOR STATS (aggregation pipeline optimization)
# =============================================================================


@router.post("/vendors/stats")
async def get_vendor_stats_batch(
    vendor_ids: list = Body(..., description="List of vendor_id strings"),
    days: int = Body(30, description="Lookback period in days"),
    service: AdminCampaignService = Depends(get_admin_campaign_service),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """
    Get stats for multiple vendors in a single aggregation pipeline.

    Returns impressions, clicks, leads, CTR, and campaign counts for each vendor,
    computed in 2 aggregate queries instead of N+1 individual queries.
    """
    if len(vendor_ids) > 200:
        raise HTTPException(status_code=400, detail="Maximum 200 vendor IDs per batch")
    return await service.get_vendor_stats_batch(vendor_ids=vendor_ids, days=days)


# =============================================================================
# PLATFORM CONFIG
# =============================================================================


@router.get("/config")
async def get_platform_config(
    service: AdminCampaignService = Depends(get_admin_campaign_service),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Get advertising platform configuration."""
    return await service.get_platform_config()


@router.put("/config")
async def update_platform_config(
    updates: dict = Body(...),
    service: AdminCampaignService = Depends(get_admin_campaign_service),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Update advertising platform configuration."""
    return await service.update_platform_config(
        admin_email=current_user.email,
        updates=updates,
    )


# =============================================================================
# FREE TIER MANAGEMENT (Root Admin Only)
# =============================================================================


@router.put("/{campaign_id}/free-tier")
async def set_campaign_free_tier(
    campaign_id: str,
    request: SetFreeTierRequest = Body(...),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Toggle free tier on a single campaign. Root admin only."""
    billing_svc = get_ad_billing_service()
    return await billing_svc.set_campaign_free_tier(
        campaign_id=campaign_id,
        is_free=request.is_free,
        admin_email=current_user.email,
    )


@router.put("/vendors/{vendor_id}/free-tier")
async def set_vendor_free_tier(
    vendor_id: str,
    request: SetFreeTierRequest = Body(...),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Toggle free tier for all campaigns from a vendor. Root admin only."""
    billing_svc = get_ad_billing_service()
    return await billing_svc.set_vendor_free_tier(
        vendor_id=vendor_id,
        is_free=request.is_free,
        reason=request.reason,
        granted_by=current_user.email,
        expires_at=request.expires_at,
    )


@router.get("/vendors/{vendor_id}/free-tier")
async def get_vendor_free_tier_status(
    vendor_id: str,
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Check if a vendor has free tier enabled."""
    billing_svc = get_ad_billing_service()
    status = await billing_svc.get_vendor_free_tier_status(vendor_id)
    return status or {"vendor_id": vendor_id, "is_free": False}


@router.get("/free-tier-vendors")
async def list_free_tier_vendors(
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """List all vendors with free tier enabled."""
    billing_svc = get_ad_billing_service()
    return await billing_svc.list_all_free_tier_vendors()


# =============================================================================
# CPL PRICING
# =============================================================================


@router.put("/{campaign_id}/cpl-pricing")
async def update_campaign_cpl_pricing(
    campaign_id: str,
    request: UpdateCPLPricingRequest = Body(...),
    service: AdminCampaignService = Depends(get_admin_campaign_service),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Update CPL pricing for a campaign. Root admin only."""
    from bson import ObjectId

    updates = {}
    if request.cpl_quote_request is not None:
        updates["cpl_quote_request"] = request.cpl_quote_request
    if request.cpl_directory_add is not None:
        updates["cpl_directory_add"] = request.cpl_directory_add
    if not updates:
        raise HTTPException(status_code=400, detail="No pricing fields provided")

    from datetime import datetime, timezone

    updates["updated_at"] = datetime.now(timezone.utc)

    result = await service.campaigns.update_one(
        {"_id": ObjectId(campaign_id)},
        {"$set": updates},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return {"status": "updated", "campaign_id": campaign_id, **updates}


# =============================================================================
# BILLING REPORTS
# =============================================================================


@router.get("/{campaign_id}/billing")
async def get_campaign_billing(
    campaign_id: str,
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Get billing summary for a campaign."""
    billing_svc = get_ad_billing_service()
    return await billing_svc.get_campaign_billing_summary(campaign_id)


@router.get("/{campaign_id}/lead-charges")
async def get_campaign_lead_charges(
    campaign_id: str,
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """List individual CPL charges for a campaign."""
    billing_svc = get_ad_billing_service()
    return await billing_svc.get_lead_charges(
        campaign_id=campaign_id,
        limit=limit,
        skip=skip,
    )


# =============================================================================
# VENDOR ACCOUNT MANAGEMENT (Phase 10)
# =============================================================================


def get_vendor_signup_service():
    """Get vendor signup service instance."""
    from app.services.vendor_signup_service import VendorSignupService

    return VendorSignupService(mongo.db)


def _validate_vendor_id(vendor_id: str) -> str:
    """Validate vendor_id is a valid ObjectId format."""
    from bson import ObjectId
    from bson.errors import InvalidId

    try:
        ObjectId(vendor_id)
    except (InvalidId, TypeError):
        raise HTTPException(
            status_code=400, detail=f"Invalid vendor ID format: {vendor_id}"
        )
    return vendor_id


@router.post("/vendors/{vendor_id}/approve")
async def approve_vendor_account(
    vendor_id: str,
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """
    Approve a pending vendor account.

    Generates a temp password and emails it to the vendor.
    Root admin only.
    """
    _validate_vendor_id(vendor_id)
    svc = get_vendor_signup_service()
    return await svc.approve_vendor(vendor_id, current_user.email)


@router.post("/vendors/{vendor_id}/suspend")
async def suspend_vendor_account(
    vendor_id: str,
    reason: str = Body("", embed=True),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """
    Suspend an active vendor account. Pauses all their active campaigns.
    Root admin only.
    """
    _validate_vendor_id(vendor_id)
    svc = get_vendor_signup_service()
    return await svc.suspend_vendor(vendor_id, current_user.email, reason)


@router.post("/vendors/{vendor_id}/reactivate")
async def reactivate_vendor_account(
    vendor_id: str,
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """
    Reactivate a suspended vendor account.
    Campaigns remain paused — vendor must resume them manually.
    Root admin only.
    """
    _validate_vendor_id(vendor_id)
    svc = get_vendor_signup_service()
    return await svc.reactivate_vendor(vendor_id, current_user.email)
