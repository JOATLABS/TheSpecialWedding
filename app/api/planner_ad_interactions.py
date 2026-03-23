"""
Planner Ad Interaction API Router

Phase 3: Planner-facing endpoints for interacting with sponsored vendor
cards on the advertising campaign platform.

Routes: /planner/ads/*

Endpoints:
  GET  /planner/ads/sponsored-cards     — Get sponsored vendor cards for rail
  POST /planner/ads/add-to-directory    — Add vendor to planner's directory
  POST /planner/ads/request-quote       — Send quote request to vendor
  GET  /planner/ads/directory-status    — Check if vendor already in directory

Auth: wedding_planner role or root admin.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.dependencies.auth_extended import (
    ExtendedAuthUser,
    get_current_user_extended,
)
from app.core.database import mongo
from app.services.planner_ad_interaction_service import PlannerAdInteractionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/planner/ads", tags=["Planner Ad Interactions"])


# ═════════════════════════════════════════════════════════════════════════
# REQUEST / RESPONSE MODELS
# ═════════════════════════════════════════════════════════════════════════

class AddToDirectoryRequest(BaseModel):
    campaign_id: str = Field(..., description="Campaign to add from")
    click_id: Optional[str] = Field(None, description="Attribution click ID")


class WeddingContext(BaseModel):
    date: Optional[str] = None
    location: Optional[str] = None
    guest_count: Optional[int] = None
    venue: Optional[str] = None
    budget_range: Optional[str] = None


class RequestQuoteRequest(BaseModel):
    campaign_id: str = Field(..., description="Campaign to request quote from")
    message: str = Field(..., min_length=1, max_length=2000, description="Quote request message")
    wedding_id: Optional[str] = Field(None, description="Wedding to associate quote with")
    wedding_context: Optional[WeddingContext] = Field(None, description="Wedding details for context")
    click_id: Optional[str] = Field(None, description="Attribution click ID")
    auto_add_to_directory: bool = Field(True, description="Auto-add vendor to directory")


# ═════════════════════════════════════════════════════════════════════════
# DEPENDENCY INJECTION
# ═════════════════════════════════════════════════════════════════════════

def get_planner_ad_interaction_service() -> PlannerAdInteractionService:
    """Get planner ad interaction service instance."""
    # Email service is optional; import lazily to avoid circular deps
    email_service = None
    try:
        from app.services.email_service_resend import ResendEmailService
        email_service = ResendEmailService(mongo.db)
    except Exception:
        logger.warning("Email service unavailable; quote emails will be skipped")

    # Billing service — CPL charges on lead creation
    billing_service = None
    try:
        from app.services.ad_billing_service import AdBillingService
        from app.services.stripe_service import StripeService
        stripe_svc = StripeService(mongo.db)
        billing_service = AdBillingService(mongo.db, stripe_service=stripe_svc)
    except Exception:
        logger.warning("Ad billing service unavailable; CPL charges will be skipped")

    # Fraud detection service — real-time click fraud checks
    fraud_detection_service = None
    try:
        from app.services.ad_fraud_detection_service import AdFraudDetectionService
        fraud_detection_service = AdFraudDetectionService(mongo.db)
    except Exception:
        logger.warning("Fraud detection service unavailable; fraud checks will be skipped")

    return PlannerAdInteractionService(
        mongo.db,
        email_service=email_service,
        billing_service=billing_service,
        fraud_detection_service=fraud_detection_service,
    )


async def require_planner_or_admin(
    current_user: ExtendedAuthUser = Depends(get_current_user_extended),
) -> ExtendedAuthUser:
    """Require wedding_planner role or root admin."""
    if current_user.is_root_admin or current_user.is_wedding_planner:
        return current_user
    raise HTTPException(
        status_code=403,
        detail="Wedding planner access required",
    )


def _get_planner_email(user: ExtendedAuthUser) -> str:
    """Extract planner email from auth user."""
    return user.email


def _get_planner_id(user: ExtendedAuthUser) -> str:
    """Extract planner user ID for directory scoping.

    Falls back to email when _id is not available (e.g. in tests).
    """
    data = user.user_data or {}
    uid = data.get("_id")
    return str(uid) if uid else user.email


def _get_planner_name(user: ExtendedAuthUser) -> str:
    """Extract planner display name from auth user."""
    data = user.user_data or {}
    return data.get("name") or data.get("display_name") or user.email


# ═════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═════════════════════════════════════════════════════════════════════════

@router.get("/sponsored-cards")
async def get_sponsored_cards(
    location: Optional[str] = Query(None, description="Planner location for targeting"),
    categories: Optional[str] = Query(None, description="Comma-separated vendor categories"),
    limit: int = Query(3, ge=1, le=10, description="Max cards to return"),
    current_user: ExtendedAuthUser = Depends(require_planner_or_admin),
    service: PlannerAdInteractionService = Depends(get_planner_ad_interaction_service),
):
    """
    Get sponsored vendor cards for the planner rail.

    Returns active campaigns enriched with primary creative info,
    filtered to exclude vendors the planner already added.
    """
    planner_email = _get_planner_email(current_user)
    cat_list = [c.strip() for c in categories.split(",")] if categories else None

    cards = await service.get_sponsored_cards(
        planner_email=planner_email,
        planner_location=location,
        categories=cat_list,
        limit=limit,
    )
    return {"cards": cards, "count": len(cards)}


@router.post("/add-to-directory", status_code=201)
async def add_to_directory(
    body: AddToDirectoryRequest,
    current_user: ExtendedAuthUser = Depends(require_planner_or_admin),
    service: PlannerAdInteractionService = Depends(get_planner_ad_interaction_service),
):
    """
    Add a vendor from an active campaign to the planner's vendor directory.

    Creates a new VendorProfile tagged with source: 'sponsored_ad' and
    records attribution (ad_lead + ad_event).

    Returns 409 if vendor already in planner's directory from this campaign.
    """
    planner_email = _get_planner_email(current_user)
    planner_id = _get_planner_id(current_user)
    result = await service.add_to_directory(
        campaign_id=body.campaign_id,
        planner_email=planner_email,
        planner_id=planner_id,
        click_id=body.click_id,
    )
    return result


@router.post("/request-quote", status_code=201)
async def request_quote(
    body: RequestQuoteRequest,
    current_user: ExtendedAuthUser = Depends(require_planner_or_admin),
    service: PlannerAdInteractionService = Depends(get_planner_ad_interaction_service),
):
    """
    Send a quote request to an advertising vendor.

    Creates an ad_lead (lead_type: quote_request), sends email to vendor,
    and optionally auto-adds vendor to planner's directory.
    """
    planner_email = _get_planner_email(current_user)
    planner_id = _get_planner_id(current_user)
    planner_name = _get_planner_name(current_user)

    wedding_ctx = body.wedding_context.dict() if body.wedding_context else None

    result = await service.request_quote(
        campaign_id=body.campaign_id,
        planner_email=planner_email,
        planner_name=planner_name,
        planner_id=planner_id,
        wedding_id=body.wedding_id,
        message=body.message,
        wedding_context=wedding_ctx,
        click_id=body.click_id,
        auto_add_to_directory=body.auto_add_to_directory,
    )
    return result


@router.get("/directory-status")
async def check_directory_status(
    campaign_id: str = Query(..., description="Campaign ID to check"),
    current_user: ExtendedAuthUser = Depends(require_planner_or_admin),
    service: PlannerAdInteractionService = Depends(get_planner_ad_interaction_service),
):
    """
    Check if a vendor from a specific campaign is already in the
    planner's directory. Used to toggle Add-to-Directory button state.
    """
    planner_email = _get_planner_email(current_user)
    return await service.check_directory_status(
        campaign_id=campaign_id,
        planner_email=planner_email,
    )
