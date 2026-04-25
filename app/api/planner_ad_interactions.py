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
  POST /planner/ads/draft-quote         — AI-generate a personalized quote request

Auth model:
- Reads (``/sponsored-cards``, ``/directory-status``) — wedding_planner,
  root admin, or team member (``require_team_or_planner``).
- Mutations (``/add-to-directory``, ``/request-quote``, ``/draft-quote``) —
  wedding_planner, root admin, or team member with the
  ``manage_vendors`` permission (``require_team_permission``).
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.database import mongo
from app.dependencies.auth_extended import (
    ExtendedAuthUser,
    get_current_user_extended,
    get_owner_identity,
    require_team_or_planner,
    require_team_permission,
)
from app.services.planner_ad_interaction_service import PlannerAdInteractionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/planner/ads", tags=["Planner Ad Interactions"])
require_manage_vendors = require_team_permission("manage_vendors")


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
    message: str = Field(
        ..., min_length=1, max_length=2000, description="Quote request message"
    )
    wedding_id: Optional[str] = Field(
        None, description="Wedding to associate quote with"
    )
    wedding_context: Optional[WeddingContext] = Field(
        None, description="Wedding details for context"
    )
    click_id: Optional[str] = Field(None, description="Attribution click ID")
    auto_add_to_directory: bool = Field(
        True, description="Auto-add vendor to directory"
    )


class DraftQuoteRequest(BaseModel):
    campaign_id: str = Field(..., description="Campaign to draft quote for")
    wedding_context: Optional[WeddingContext] = Field(
        None, description="Wedding details for context"
    )


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
        logger.warning(
            "Fraud detection service unavailable; fraud checks will be skipped"
        )

    # Auction service — bid-based ranking for sponsored cards
    auction_service = None
    try:
        from app.services.ad_auction_service import AdAuctionService

        auction_service = AdAuctionService(mongo.db)
    except Exception:
        logger.warning(
            "Auction service unavailable; falling back to quality_score sort"
        )

    return PlannerAdInteractionService(
        mongo.db,
        email_service=email_service,
        billing_service=billing_service,
        fraud_detection_service=fraud_detection_service,
        auction_service=auction_service,
    )


async def require_planner_or_admin(
    current_user: ExtendedAuthUser = Depends(get_current_user_extended),
) -> ExtendedAuthUser:
    """Require wedding_planner role or root admin.

    NOTE: Sponsored-card endpoints no longer depend on this gate directly —
    they use ``require_team_or_planner`` for reads and
    ``require_team_permission('manage_vendors')`` for mutations so team
    members can see the rail and perform directory actions only when their
    planner has granted the ``manage_vendors`` permission. This helper is
    retained because downstream tests override it, and removing it would
    silently break those overrides.
    """
    if current_user.is_root_admin or current_user.is_wedding_planner:
        return current_user
    raise HTTPException(
        status_code=403,
        detail="Wedding planner access required",
    )


async def require_ads_enabled() -> bool:
    """
    Dependency that checks if the advertising platform is enabled.

    Uses the cached config (60s TTL) so this is efficient on the hot ad-serving path.
    Returns True if enabled; raises 403 if disabled.
    """
    try:
        from app.services.ad_platform_config_service import AdPlatformConfigService

        config_service = AdPlatformConfigService(mongo.db)
        config = await config_service.get_config()  # uses TTL cache
        if not config.get("ads_enabled", True):
            raise HTTPException(
                status_code=403,
                detail="Advertising platform is currently disabled",
            )
    except HTTPException:
        raise
    except Exception:
        # If config service is unavailable, allow ads (fail-open)
        logger.warning("Could not check ads_enabled flag; defaulting to enabled")
    return True


def _get_planner_email(user: ExtendedAuthUser) -> str:
    """Resolve the planner-scoped email for directory/lead attribution.

    Team members operate on their owning planner's directory, so leads,
    adds, and quote requests must attribute to the planner rather than the
    team member's own email. Falls back to the caller's own email for
    root-admin callers where ``get_owner_identity`` returns ``(None, None)``.
    """
    _, owner_email = get_owner_identity(user)
    if owner_email:
        return owner_email
    return user.email


def _get_planner_id(user: ExtendedAuthUser) -> str:
    """Resolve the planner-scoped user id for directory scoping.

    Falls back to the caller's own id (or email) when the caller has no
    owning planner — typically a root-admin session.
    """
    owner_id, _ = get_owner_identity(user)
    if owner_id:
        return owner_id
    data = user.user_data or {}
    uid = data.get("_id")
    return str(uid) if uid else user.email


def _get_planner_name(user: ExtendedAuthUser) -> str:
    """Extract the display name used as the sender on quote requests.

    For team members we keep the actual caller's name — the vendor-facing
    email is signed by the person who clicked the button, not by the
    owning planner, which mirrors how real teams introduce themselves.
    """
    data = user.user_data or {}
    return data.get("name") or data.get("display_name") or user.email


# ═════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═════════════════════════════════════════════════════════════════════════


@router.get("/sponsored-cards")
async def get_sponsored_cards(
    location: Optional[str] = Query(None, description="Planner location for targeting"),
    categories: Optional[str] = Query(
        None, description="Comma-separated vendor categories"
    ),
    limit: int = Query(3, ge=1, le=10, description="Max cards to return"),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
    service: PlannerAdInteractionService = Depends(get_planner_ad_interaction_service),
    _ads_on: bool = Depends(require_ads_enabled),
):
    """
    Get sponsored vendor cards for the planner rail.

    Returns active campaigns enriched with primary creative info,
    filtered to exclude vendors the planner already added.

    Team members can read the rail regardless of ``manage_vendors`` so
    they see what the planner sees; the mutating endpoints
    (``add-to-directory``, ``request-quote``, ``draft-quote``) are the
    ones gated on ``manage_vendors``.
    """
    planner_email = _get_planner_email(current_user)
    planner_id = _get_planner_id(current_user)
    cat_list = [c.strip() for c in categories.split(",")] if categories else None

    cards = await service.get_sponsored_cards(
        planner_email=planner_email,
        planner_id=planner_id,
        planner_location=location,
        categories=cat_list,
        limit=limit,
    )
    return {"cards": cards, "count": len(cards)}


@router.post("/add-to-directory", status_code=201)
async def add_to_directory(
    body: AddToDirectoryRequest,
    current_user: ExtendedAuthUser = Depends(require_manage_vendors),
    service: PlannerAdInteractionService = Depends(get_planner_ad_interaction_service),
    _ads_on: bool = Depends(require_ads_enabled),
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
    current_user: ExtendedAuthUser = Depends(require_manage_vendors),
    service: PlannerAdInteractionService = Depends(get_planner_ad_interaction_service),
    _ads_on: bool = Depends(require_ads_enabled),
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
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
    service: PlannerAdInteractionService = Depends(get_planner_ad_interaction_service),
    _ads_on: bool = Depends(require_ads_enabled),
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


@router.post("/draft-quote")
async def draft_quote(
    body: DraftQuoteRequest,
    current_user: ExtendedAuthUser = Depends(require_manage_vendors),
    service: PlannerAdInteractionService = Depends(get_planner_ad_interaction_service),
    _ads_on: bool = Depends(require_ads_enabled),
):
    """
    AI-generate a personalized quote request message for a vendor.

    Uses the AI service to draft a context-aware message based on the
    vendor's campaign info and optionally the planner's wedding details.
    Returns a suggested subject + body that the planner can edit before sending.
    """
    planner_name = _get_planner_name(current_user)
    planner_id = _get_planner_id(current_user)

    # Resolve campaign to get vendor info
    campaign = await service._get_active_campaign(body.campaign_id)
    creative = await service._get_primary_creative(campaign)

    # Build AI context from campaign + wedding info
    ai_context = {
        "vendor_name": campaign.get("vendor_name", "Vendor"),
        "vendor_category": campaign.get("category", "wedding vendor"),
        "service_area": campaign.get("target_location", ""),
        "planner_name": planner_name,
    }

    # Add creative details if available
    if creative:
        ai_context["headline"] = creative.get("headline", "")
        ai_context["description"] = creative.get("description", "")

    # Add wedding context if provided
    if body.wedding_context:
        wc = body.wedding_context
        if wc.date:
            ai_context["wedding_date"] = wc.date
        if wc.location:
            ai_context["wedding_location"] = wc.location
        if wc.guest_count:
            ai_context["guest_count"] = wc.guest_count
        if wc.venue:
            ai_context["venue"] = wc.venue
        if wc.budget_range:
            ai_context["budget_range"] = wc.budget_range

    # Build prompt
    prompt = f"Draft a quote request from {planner_name} to {ai_context['vendor_name']} ({ai_context['vendor_category']})."
    if ai_context.get("service_area"):
        prompt += f" They serve the {ai_context['service_area']} area."
    if ai_context.get("wedding_date"):
        prompt += f" Wedding date: {ai_context['wedding_date']}."
    if ai_context.get("wedding_location"):
        prompt += f" Location: {ai_context['wedding_location']}."
    if ai_context.get("guest_count"):
        prompt += f" Guest count: {ai_context['guest_count']}."
    if ai_context.get("venue"):
        prompt += f" Venue: {ai_context['venue']}."
    if ai_context.get("budget_range"):
        prompt += f" Budget range: {ai_context['budget_range']}."

    # Call AI service
    try:
        import json

        from app.services.ai_service import (
            AIGenerationError,
            InsufficientCreditsError,
            ai_service,
        )

        result = await ai_service.generate(
            user_id=planner_id,
            tenant_id=planner_id,
            feature="ad_quote_draft",
            prompt=prompt,
            context=ai_context,
        )

        # Parse AI response
        response_text = result.get("response", "")
        try:
            parsed = json.loads(response_text)
        except (json.JSONDecodeError, TypeError):
            # If AI returned plain text, wrap it
            parsed = {
                "subject": f"Quote Request — {ai_context['vendor_category'].replace('_', ' ').title()}",
                "body": response_text,
                "tone": "professional",
            }

        return {
            "draft": parsed,
            "credits_used": result.get("credits_used", 0),
            "model_used": result.get("model_used", "unknown"),
        }

    except InsufficientCreditsError as e:
        raise HTTPException(
            status_code=402,
            detail={"error": "insufficient_credits", "message": e.message},
        )
    except AIGenerationError as e:
        raise HTTPException(
            status_code=503,
            detail={"error": e.error_code, "message": e.message},
        )
    except ImportError:
        # AI service not available — return a basic template instead
        logger.warning("AI service not available; returning template draft")
        vendor_name = campaign.get("vendor_name", "Vendor")
        category = campaign.get("category", "services").replace("_", " ")
        return {
            "draft": {
                "subject": f"Quote Request — {category.title()}",
                "body": (
                    f"Hi {vendor_name},\n\n"
                    f"I'm {planner_name}, a wedding planner, and I found your profile on The Special Wedding. "
                    f"I'm interested in your {category} services and would love to discuss pricing and availability.\n\n"
                    "Could you share your packages and any availability you have?\n\n"
                    "Thank you!"
                ),
                "tone": "professional",
            },
            "credits_used": 0,
            "model_used": "template",
        }
