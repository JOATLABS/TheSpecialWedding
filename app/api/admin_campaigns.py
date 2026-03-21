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
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from typing import Optional

from app.dependencies.auth_extended import (
    get_current_user_extended,
    require_root_admin,
    ExtendedAuthUser,
)
from app.core.database import mongo
from app.services.admin_campaign_service import AdminCampaignService
from app.models.advertising_campaign import (
    ReviewCampaignDecisionRequest,
    ReviewCreativeDecisionRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/ads/campaigns", tags=["Admin Campaigns"])


# =============================================================================
# DEPENDENCY INJECTION
# =============================================================================

async def get_admin_campaign_service() -> AdminCampaignService:
    """Get admin campaign service instance."""
    return AdminCampaignService(mongo.db)


# =============================================================================
# REVIEW QUEUE
# =============================================================================

@router.get("/review")
async def get_review_queue(
    status: Optional[str] = Query(
        None,
        description="Filter by status (default: pending_review)"
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
    return await service.get_fraud_signals(
        status_filter=status, limit=limit, skip=skip
    )


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

@router.get("/vendors")
async def list_vendor_accounts(
    status: Optional[str] = Query(None, description="Filter by account status"),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    service: AdminCampaignService = Depends(get_admin_campaign_service),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """List advertising vendor accounts."""
    return await service.list_vendor_accounts(
        status_filter=status, limit=limit, skip=skip
    )


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
