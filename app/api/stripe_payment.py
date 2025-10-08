"""
Stripe Payment API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from typing import Optional
from pydantic import BaseModel, Field
from app.services.stripe_service import stripe_service
from app.dependencies.auth_extended import require_admin_or_planner, ExtendedAuthUser
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stripe", tags=["Stripe Payments"])


# ==================== REQUEST MODELS ====================

class CreateCheckoutSessionRequest(BaseModel):
    """Request model for creating a Stripe Checkout Session"""
    plan_id: str = Field(..., description="Subscription plan ID")
    billing_interval: str = Field(default="monthly", description="Billing interval: monthly or yearly")
    success_url: Optional[str] = Field(None, description="Success redirect URL")
    cancel_url: Optional[str] = Field(None, description="Cancel redirect URL")
    trial_days: int = Field(default=0, description="Number of trial days")


class CreatePortalSessionRequest(BaseModel):
    """Request model for creating a Customer Portal Session"""
    return_url: Optional[str] = Field(None, description="Return URL after portal session")


class CreatePaymentIntentRequest(BaseModel):
    """Request model for creating a payment intent for couple payments"""
    amount: float = Field(..., description="Payment amount in dollars", gt=0)
    currency: str = Field(default="usd", description="Currency code")
    wedding_id: Optional[str] = Field(None, description="Associated wedding ID")
    description: Optional[str] = Field(None, description="Payment description")
    metadata: Optional[dict] = Field(default_factory=dict, description="Additional metadata")


# ==================== CHECKOUT SESSION ENDPOINTS ====================

@router.post("/create-checkout-session")
async def create_checkout_session(
    request: CreateCheckoutSessionRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Create a Stripe Checkout Session for subscription signup

    This endpoint creates a hosted payment page where users can
    subscribe to a plan with their credit card.
    """
    try:
        user_id = str(current_user.user_data.get("_id"))

        session = stripe_service.create_checkout_session(
            user_id=user_id,
            plan_id=request.plan_id,
            billing_interval=request.billing_interval,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            trial_days=request.trial_days
        )

        return {
            "status": "success",
            "checkout_session": session
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating checkout session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create checkout session: {str(e)}")


@router.get("/checkout-session/{session_id}")
async def get_checkout_session(
    session_id: str,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Retrieve details of a Stripe Checkout Session

    Useful for verifying payment completion on the success page.
    """
    try:
        import stripe
        from app.core.settings import settings

        stripe.api_key = settings.stripe_secret_key
        session = stripe.checkout.Session.retrieve(session_id)

        return {
            "status": "success",
            "session": {
                "id": session.id,
                "payment_status": session.payment_status,
                "customer": session.customer,
                "subscription": session.subscription,
                "amount_total": session.amount_total / 100 if session.amount_total else 0,
                "currency": session.currency
            }
        }

    except Exception as e:
        logger.error(f"Error retrieving checkout session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve session: {str(e)}")


# ==================== CUSTOMER PORTAL ENDPOINTS ====================

@router.post("/create-portal-session")
async def create_portal_session(
    request: CreatePortalSessionRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Create a Stripe Customer Portal session

    The portal allows customers to:
    - Update payment methods
    - View billing history
    - Cancel subscriptions
    - Download invoices
    """
    try:
        user_id = str(current_user.user_data.get("_id"))

        portal_session = stripe_service.create_portal_session(
            user_id=user_id,
            return_url=request.return_url
        )

        return {
            "status": "success",
            "portal_url": portal_session["url"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating portal session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create portal session: {str(e)}")


# ==================== WEBHOOK ENDPOINT ====================

@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature")
):
    """
    Handle Stripe webhook events

    This endpoint receives real-time updates from Stripe about:
    - Successful payments
    - Failed payments
    - Subscription changes
    - Customer updates

    IMPORTANT: Configure this endpoint in your Stripe Dashboard:
    https://dashboard.stripe.com/webhooks

    Endpoint URL: https://yourdomain.com/api/stripe/webhook

    Events to listen for:
    - checkout.session.completed
    - customer.subscription.created
    - customer.subscription.updated
    - customer.subscription.deleted
    - invoice.paid
    - invoice.payment_failed
    """
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing stripe-signature header")

    try:
        # Get raw body
        payload = await request.body()

        # Process webhook
        result = stripe_service.handle_webhook_event(payload, stripe_signature)

        return {"status": "success", "result": result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")


# ==================== PAYMENT COLLECTION FOR COUPLES ====================

@router.post("/create-payment-intent")
async def create_payment_intent(
    request: CreatePaymentIntentRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Create a payment intent for collecting payment from couples

    This allows wedding planners to collect payments from their clients
    for services, deposits, or final payments.

    The returned client_secret should be used on the frontend with
    Stripe Elements to complete the payment.
    """
    try:
        # Ensure planner is authorized for the wedding if wedding_id provided
        if request.wedding_id and not current_user.is_root_admin:
            from app.core.database import mongo
            wedding = mongo.db["weddings"].find_one({"_id": request.wedding_id})
            if not wedding:
                raise HTTPException(status_code=404, detail="Wedding not found")

            # Check if user has access to this wedding
            user_id = str(current_user.user_data.get("_id"))
            planner_id = wedding.get("planner_id")
            if planner_id and str(planner_id) != user_id:
                raise HTTPException(
                    status_code=403,
                    detail="You don't have permission to create payments for this wedding"
                )

        payment_intent = stripe_service.create_payment_intent_for_couple(
            amount=request.amount,
            currency=request.currency,
            wedding_id=request.wedding_id,
            description=request.description,
            metadata=request.metadata
        )

        return {
            "status": "success",
            "payment_intent": payment_intent
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating payment intent: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create payment intent: {str(e)}")


# ==================== CONFIGURATION ENDPOINT ====================

@router.get("/config")
async def get_stripe_config(
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Get Stripe public configuration (publishable key)

    This key is safe to expose in frontend code and is required
    to initialize Stripe.js
    """
    from app.core.settings import settings

    if not settings.stripe_enabled:
        raise HTTPException(status_code=503, detail="Stripe is not enabled")

    if not settings.stripe_publishable_key:
        raise HTTPException(status_code=500, detail="Stripe publishable key not configured")

    return {
        "publishable_key": settings.stripe_publishable_key,
        "currency": "usd"
    }


# ==================== PUBLIC WEBHOOK ENDPOINT (NO AUTH) ====================
# Note: The webhook endpoint above should be accessible without authentication
# This is handled by FastAPI's dependency system - we don't use Depends() for webhooks
