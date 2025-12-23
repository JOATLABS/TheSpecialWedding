"""
Stripe Payment API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from typing import Optional
from bson import ObjectId
from pydantic import BaseModel, Field
from app.services.stripe_service import stripe_service
from app.dependencies.auth_extended import require_admin_or_planner, ExtendedAuthUser
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["Stripe Payments"])


# ==================== REQUEST MODELS ====================

class CreateCheckoutSessionRequest(BaseModel):
    """Request model for creating a Stripe Checkout Session"""
    plan_id: str = Field(..., description="Subscription plan ID")
    billing_interval: str = Field(default="monthly", description="Billing interval: monthly or yearly")
    success_url: Optional[str] = Field(None, description="Success redirect URL")
    cancel_url: Optional[str] = Field(None, description="Cancel redirect URL")
    trial_days: int = Field(default=0, ge=0, description="Number of trial days")


class PublicCreateCheckoutSessionRequest(CreateCheckoutSessionRequest):
    """Public request model (no auth) for creating a Stripe Checkout Session after registration"""
    email: str = Field(..., description="Email to validate pending user ownership")


class CreatePortalSessionRequest(BaseModel):
    """Request model for creating a Customer Portal Session"""
    return_url: Optional[str] = Field(None, description="Return URL after portal session")
    flow_type: Optional[str] = Field(None, description="Portal flow type: 'payment_method_update' or 'subscription_update'")


class CreatePaymentIntentRequest(BaseModel):
    """Request model for creating a payment intent for couple payments"""
    amount: float = Field(..., description="Payment amount in dollars", gt=0)
    currency: str = Field(default="usd", description="Currency code")
    wedding_id: Optional[str] = Field(None, description="Associated wedding ID")
    description: Optional[str] = Field(None, description="Payment description")
    metadata: Optional[dict] = Field(default_factory=dict, description="Additional metadata")
    destination_user_id: Optional[str] = Field(None, description="Internal ID of the user to receive funds (Connect account)")


class ConnectOnboardRequest(BaseModel):
    """Request model for onboarding a connected account"""
    country: str = Field(default="US", description="Two-letter country code")
    return_url: str = Field(..., description="Return URL after onboarding")
    refresh_url: str = Field(..., description="Refresh URL if onboarding fails")

class VendorPaymentRequest(BaseModel):
    """Request model for paying a vendor"""
    vendor_user_id: str = Field(..., description="User ID of the vendor to pay")
    amount: float = Field(..., description="Payment amount in dollars", gt=0)
    currency: str = Field(default="usd", description="Currency code")
    description: Optional[str] = Field(None, description="Payment description")


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

        session = await stripe_service.create_checkout_session(
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


@router.post("/public/create-checkout-session")
async def create_public_checkout_session(
    request: PublicCreateCheckoutSessionRequest
):
    """
    Public endpoint to create a Stripe Checkout Session for pending signups.
    Validates the pending user by email, then creates checkout without requiring login.
    """
    try:
        pending_user = await stripe_service.users_collection.find_one({"email": request.email})

        if not pending_user:
            raise HTTPException(status_code=404, detail="Pending user not found")

        if pending_user.get("subscription_status") not in ["pending_payment", "trial", "active"]:
            raise HTTPException(status_code=400, detail="User is not eligible for checkout")

        session = await stripe_service.create_checkout_session(
            user_id=str(pending_user["_id"]),
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
        logger.error(f"Error creating public checkout session: {str(e)}")
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

        portal_session = await stripe_service.create_portal_session(
            user_id=user_id,
            return_url=request.return_url,
            flow_type=request.flow_type
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
    - customer.subscription.trial_will_end
    - invoice.paid
    - invoice.payment_failed
    """
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing stripe-signature header")

    try:
        # Get raw body
        payload = await request.body()

        # Process webhook
        result = await stripe_service.handle_webhook_event(payload, stripe_signature)

        return {"status": "success", "result": result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")


# ==================== CONNECT / MARKETPLACE ENDPOINTS ====================

@router.post("/connect/onboard")
async def create_connect_account_link(
    request: ConnectOnboardRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Create a Stripe Connect onboarding link for the current user.
    This allows Planners or Vendors to receive payments.
    """
    try:
        user_id = str(current_user.user_data.get("_id"))
        email = current_user.user_data.get("email")

        # Create or get connected account
        account_id = await stripe_service.create_connected_account(
            user_id=user_id,
            email=email,
            country=request.country
        )

        # Create onboarding link
        url = stripe_service.create_account_link(
            account_id=account_id,
            refresh_url=request.refresh_url,
            return_url=request.return_url
        )

        return {
            "status": "success",
            "url": url,
            "account_id": account_id
        }
    except Exception as e:
        logger.error(f"Error creating connect link: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create onboarding link: {str(e)}")


@router.get("/connect/status")
async def get_connect_status(
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Check the onboarding status of the current user's connected account.
    """
    try:
        user_id = str(current_user.user_data.get("_id"))
        from app.core.database import mongo
        from bson import ObjectId

        user = await mongo.db["users"].find_one({"_id": ObjectId(user_id)})
        connect_id = user.get("stripe_connect_id")

        if not connect_id:
            return {
                "status": "not_connected",
                "charges_enabled": False,
                "payouts_enabled": False,
                "details_submitted": False
            }

        status = stripe_service.get_account_status(connect_id)
        status["status"] = "connected"
        return status

    except Exception as e:
        logger.error(f"Error checking connect status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to check status: {str(e)}")


@router.post("/pay-vendor")
async def pay_vendor(
    request: VendorPaymentRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Create a payment intent for a Planner to pay a Vendor.
    """
    try:
        sender_id = str(current_user.user_data.get("_id"))

        # Verify vendor exists and has connect account
        from app.core.database import mongo
        from bson import ObjectId

        vendor = await mongo.db["users"].find_one({"_id": ObjectId(request.vendor_user_id)})
        if not vendor:
            raise HTTPException(status_code=404, detail="Vendor not found")

        vendor_connect_id = vendor.get("stripe_connect_id")
        if not vendor_connect_id:
            raise HTTPException(status_code=400, detail="Vendor is not set up to receive payments via Stripe")

        # Verify sender permission (if needed, e.g. checking budget)
        # For now, we assume if they pay, they pay.

        result = await stripe_service.create_vendor_payment_intent(
            sender_user_id=sender_id,
            vendor_connect_id=vendor_connect_id,
            amount=request.amount,
            currency=request.currency,
            description=request.description
        )

        return {
            "status": "success",
            "payment_intent": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating vendor payment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create payment: {str(e)}")


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
        destination_account_id = None
        # Ensure planner is authorized for the wedding if wedding_id provided
        if request.wedding_id and not current_user.is_root_admin:
            from app.core.database import mongo
            wedding = await mongo.db["weddings"].find_one({"_id": ObjectId(request.wedding_id)})
            if not wedding:
                raise HTTPException(status_code=404, detail="Wedding not found")

            # Check if user has access to this wedding
            user_id = str(current_user.user_data.get("_id"))
            planner_id = wedding.get("planner_id")

            # If current user is not admin, they must be the planner
            if not current_user.is_root_admin and planner_id and str(planner_id) != user_id:
                raise HTTPException(
                    status_code=403,
                    detail="You don't have permission to create payments for this wedding"
                )

            # If we want to route funds to the planner of the wedding:
            if planner_id:
                planner = mongo.db["users"].find_one({"_id": planner_id})
                if planner and planner.get("stripe_connect_id"):
                    destination_account_id = planner.get("stripe_connect_id")

        # Override destination if explicitly provided (and allowed?)
        # For security, maybe restrict who can set destination_user_id
        if request.destination_user_id:
             # Look up connect ID for this user
             from app.core.database import mongo
             from bson import ObjectId
             dest_user = mongo.db["users"].find_one({"_id": ObjectId(request.destination_user_id)})
             if dest_user and dest_user.get("stripe_connect_id"):
                 destination_account_id = dest_user.get("stripe_connect_id")

        payment_intent = stripe_service.create_payment_intent_for_couple(
            amount=request.amount,
            currency=request.currency,
            wedding_id=request.wedding_id,
            description=request.description,
            metadata=request.metadata,
            destination_account_id=destination_account_id
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


# ==================== BILLING HISTORY ENDPOINTS ====================

@router.get("/invoices")
async def get_invoices(
    limit: int = 10,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Get billing history (invoices) for the current user

    Returns list of past invoices with amounts, dates, status, and PDF links.
    """
    try:
        import stripe
        from app.core.settings import settings
        from app.core.database import mongo
        from bson import ObjectId

        if not settings.stripe_enabled or not settings.stripe_secret_key:
            return []

        stripe.api_key = settings.stripe_secret_key
        user_id = str(current_user.user_data.get("_id"))

        # Get customer ID from stripe_customers collection
        customer_record = await mongo.db["stripe_customers"].find_one({"user_id": user_id})
        if not customer_record or not customer_record.get("stripe_customer_id"):
            return []

        customer_id = customer_record["stripe_customer_id"]

        # Fetch invoices from Stripe
        invoices = stripe.Invoice.list(
            customer=customer_id,
            limit=limit,
            status="paid"  # Only show paid invoices
        )

        result = []
        for invoice in invoices.data:
            result.append({
                "id": invoice.id,
                "date": invoice.created,  # Unix timestamp
                "amount": invoice.amount_paid,  # In cents
                "status": invoice.status,
                "invoice_pdf": invoice.invoice_pdf,
                "description": invoice.lines.data[0].description if invoice.lines.data else "Subscription payment",
                "period_start": invoice.period_start,
                "period_end": invoice.period_end,
                "number": invoice.number
            })

        return result

    except Exception as e:
        logger.error(f"Error fetching invoices: {str(e)}")
        return []


@router.get("/payment-method")
async def get_payment_method(
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Get the default payment method details for the current user

    Returns masked card information (last 4 digits, brand, expiry).
    """
    try:
        import stripe
        from app.core.settings import settings
        from app.core.database import mongo
        from bson import ObjectId

        if not settings.stripe_enabled or not settings.stripe_secret_key:
            return {"has_payment_method": False}

        stripe.api_key = settings.stripe_secret_key
        user_id = str(current_user.user_data.get("_id"))

        # Get customer ID
        customer_record = await mongo.db["stripe_customers"].find_one({"user_id": user_id})
        if not customer_record or not customer_record.get("stripe_customer_id"):
            return {"has_payment_method": False}

        customer_id = customer_record["stripe_customer_id"]

        # Get customer to find default payment method
        customer = stripe.Customer.retrieve(customer_id)

        default_pm_id = customer.invoice_settings.default_payment_method
        if not default_pm_id:
            # Try to get from subscriptions
            subscriptions = stripe.Subscription.list(customer=customer_id, limit=1)
            if subscriptions.data:
                default_pm_id = subscriptions.data[0].default_payment_method

        if not default_pm_id:
            return {"has_payment_method": False}

        # Retrieve payment method details
        pm = stripe.PaymentMethod.retrieve(default_pm_id)

        if pm.type == "card":
            return {
                "has_payment_method": True,
                "type": "card",
                "card_brand": pm.card.brand.capitalize() if pm.card.brand else "Card",
                "card_last_four": pm.card.last4,
                "card_exp_month": pm.card.exp_month,
                "card_exp_year": pm.card.exp_year,
                "card_funding": pm.card.funding
            }
        else:
            return {
                "has_payment_method": True,
                "type": pm.type
            }

    except Exception as e:
        logger.error(f"Error fetching payment method: {str(e)}")
        return {"has_payment_method": False}


@router.get("/subscription")
async def get_subscription_details(
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Get detailed subscription information including payment method

    Returns subscription status, plan details, billing dates, and card info.
    """
    try:
        import stripe
        from app.core.settings import settings
        from app.core.database import mongo
        from bson import ObjectId
        from datetime import datetime

        if not settings.stripe_enabled or not settings.stripe_secret_key:
            raise HTTPException(status_code=503, detail="Stripe is not enabled")

        stripe.api_key = settings.stripe_secret_key
        user_id = str(current_user.user_data.get("_id"))

        # Get local subscription record
        subscription_record = await mongo.db["user_subscriptions"].find_one({"user_id": user_id})
        if not subscription_record:
            raise HTTPException(status_code=404, detail="No subscription found")

        plan_id = subscription_record.get("plan_id")
        plan = None
        if plan_id:
            plan = await mongo.db["subscription_plans"].find_one({"_id": plan_id})

        # Get customer and payment method from Stripe
        customer_record = await mongo.db["stripe_customers"].find_one({"user_id": user_id})
        card_info = {}

        if customer_record and customer_record.get("stripe_customer_id"):
            try:
                customer = stripe.Customer.retrieve(customer_record["stripe_customer_id"])

                # Get default payment method
                default_pm_id = customer.invoice_settings.default_payment_method
                if not default_pm_id:
                    subs = stripe.Subscription.list(customer=customer.id, limit=1)
                    if subs.data:
                        default_pm_id = subs.data[0].default_payment_method

                if default_pm_id:
                    pm = stripe.PaymentMethod.retrieve(default_pm_id)
                    if pm.type == "card":
                        card_info = {
                            "card_brand": pm.card.brand.capitalize() if pm.card.brand else "Card",
                            "card_last_four": pm.card.last4,
                            "card_exp_month": pm.card.exp_month,
                            "card_exp_year": pm.card.exp_year
                        }
            except Exception as e:
                logger.warning(f"Could not fetch Stripe card info: {e}")

        # Build response
        response = {
            "plan_id": plan_id,
            "status": subscription_record.get("status", "active"),
            "billing_interval": subscription_record.get("billing_interval", "monthly"),
            "current_period_start": subscription_record.get("current_period_start"),
            "current_period_end": subscription_record.get("current_period_end"),
            "created_at": subscription_record.get("created_at"),
            "stripe_subscription_id": subscription_record.get("stripe_subscription_id"),
            "stripe_customer_id": subscription_record.get("stripe_customer_id"),
            "payment_status": subscription_record.get("payment_status"),
            **card_info
        }

        if plan:
            response["plan_name"] = plan.get("name")
            response["plan_description"] = plan.get("description")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching subscription details: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch subscription: {str(e)}")


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
