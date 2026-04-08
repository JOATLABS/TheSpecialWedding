"""
Stripe Payment API Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Header
from typing import Optional
from bson import ObjectId
from pydantic import BaseModel, Field
import secrets
import stripe
from app.services.stripe_service import stripe_service
from app.dependencies.auth_extended import require_admin_or_planner, ExtendedAuthUser
from app.models.subscription import (
    ACTIVE_SUBSCRIPTION_STATUSES,
    BILLING_PORTAL_RECOVERY_SUBSCRIPTION_STATUSES,
    PUBLIC_CHECKOUT_ALLOWED_STATUSES,
    normalize_subscription_status,
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["Stripe Payments"])
PAYABLE_PAYMENT_INTENT_STATUSES = {
    "requires_payment_method",
    "requires_confirmation",
    "requires_action",
}


# ==================== REQUEST MODELS ====================


def _is_public_checkout_resume_candidate(user_doc: dict) -> bool:
    """Allow unauthenticated checkout resumes only for public self-signups."""

    status = normalize_subscription_status(user_doc.get("subscription_status"))
    return (
        status in PUBLIC_CHECKOUT_ALLOWED_STATUSES
        and user_doc.get("registration_source") == "public_signup"
    )


async def _get_payment_request_by_public_token(public_token: str) -> dict:
    from app.core.database import mongo

    payment_request = await mongo.db["payment_requests"].find_one(
        {"public_token": public_token}
    )
    if not payment_request:
        raise HTTPException(status_code=404, detail="Payment request not found")

    return payment_request


class CreateCheckoutSessionRequest(BaseModel):
    """Request model for creating a Stripe Checkout Session"""

    plan_id: str = Field(..., description="Subscription plan ID")
    billing_interval: str = Field(
        default="monthly", description="Billing interval: monthly or yearly"
    )
    success_url: Optional[str] = Field(None, description="Success redirect URL")
    cancel_url: Optional[str] = Field(None, description="Cancel redirect URL")
    trial_days: Optional[int] = Field(
        default=None, ge=0, description="Number of trial days"
    )


class PublicCreateCheckoutSessionRequest(CreateCheckoutSessionRequest):
    """Public request model (no auth) for creating a Stripe Checkout Session after registration"""

    email: str = Field(..., description="Email to validate pending user ownership")


class CreatePortalSessionRequest(BaseModel):
    """Request model for creating a Customer Portal Session"""

    return_url: Optional[str] = Field(
        None, description="Return URL after portal session"
    )
    flow_type: Optional[str] = Field(
        None,
        description="Portal flow type: 'payment_method_update', 'subscription_update', or 'subscription_cancel'",
    )


class CreatePaymentIntentRequest(BaseModel):
    """Request model for creating a payment intent for couple payments"""

    amount: float = Field(..., description="Payment amount in dollars", gt=0)
    currency: str = Field(default="usd", description="Currency code")
    wedding_id: str = Field(..., description="Associated wedding ID")
    description: Optional[str] = Field(None, description="Payment description")
    metadata: Optional[dict] = Field(default=None, description="Additional metadata")
    destination_user_id: Optional[str] = Field(
        None, description="Internal ID of the user to receive funds (Connect account)"
    )


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
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    Create a Stripe Checkout Session for subscription signup

    This endpoint creates a hosted payment page where users can
    subscribe to a plan with their credit card.
    """
    try:
        user_id = str(current_user.user_data.get("_id"))
        current_status = normalize_subscription_status(
            current_user.user_data.get("subscription_status")
            or current_user.subscription_status
        )

        if (
            current_status in ACTIVE_SUBSCRIPTION_STATUSES
            or current_status in BILLING_PORTAL_RECOVERY_SUBSCRIPTION_STATUSES
        ):
            raise HTTPException(
                status_code=409,
                detail="Your account already has an active billing relationship. Use the billing portal to manage or update it.",
            )

        session = await stripe_service.create_checkout_session(
            user_id=user_id,
            plan_id=request.plan_id,
            billing_interval=request.billing_interval,
            success_url=request.success_url or "",
            cancel_url=request.cancel_url or "",
            trial_days=request.trial_days,
        )

        return {"status": "success", "checkout_session": session}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating checkout session: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create checkout session: {str(e)}"
        )


@router.post("/public/create-checkout-session")
async def create_public_checkout_session(request: PublicCreateCheckoutSessionRequest):
    """
    Public endpoint to create a Stripe Checkout Session for pending signups.
    Validates the pending user by email, then creates checkout without requiring login.
    """
    try:
        pending_user = await stripe_service.users_collection.find_one(
            {"email": request.email}
        )

        # Use a generic error message for all failure cases to prevent email enumeration
        if not pending_user:
            raise HTTPException(
                status_code=400,
                detail="Unable to create checkout session. Please check your email and try again.",
            )

        if not _is_public_checkout_resume_candidate(pending_user):
            raise HTTPException(
                status_code=400,
                detail="Unable to create checkout session. Please check your email and try again.",
            )

        session = await stripe_service.create_checkout_session(
            user_id=str(pending_user["_id"]),
            plan_id=request.plan_id,
            billing_interval=request.billing_interval,
            success_url=request.success_url or "",
            cancel_url=request.cancel_url or "",
            trial_days=request.trial_days,
        )

        return {"status": "success", "checkout_session": session}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating public checkout session: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create checkout session: {str(e)}"
        )


@router.get("/checkout-session/{session_id}")
async def get_checkout_session(
    session_id: str, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Retrieve details of a Stripe Checkout Session

    Useful for verifying payment completion on the success page.
    Returns enriched data including plan details, invoice links, and next billing date.
    """
    try:
        import stripe
        from app.core.settings import settings
        from app.core.database import mongo

        stripe.api_key = settings.stripe_secret_key
        session = stripe.checkout.Session.retrieve(session_id)

        result: dict = {
            "id": session.id,
            "payment_status": session.payment_status,
            "customer": session.customer,
            "subscription": session.subscription,
            "amount_total": session.amount_total / 100
            if session.amount_total
            else 0,
            "currency": session.currency,
        }

        # ── Enrich with subscription details (next billing date, trial info) ──
        if session.subscription:
            try:
                sub = stripe.Subscription.retrieve(session.subscription)
                result["subscription_status"] = sub.status
                sub_metadata = getattr(sub, "metadata", {}) or {}
                result["billing_interval"] = (
                    sub_metadata.get("billing_interval", "monthly")
                    if isinstance(sub_metadata, dict)
                    else dict(sub_metadata).get("billing_interval", "monthly")
                )

                if sub.current_period_end:
                    result["next_billing_date"] = sub.current_period_end  # Unix ts

                if sub.trial_end:
                    result["trial_end"] = sub.trial_end  # Unix ts
            except Exception as sub_err:
                logger.warning(
                    f"Could not enrich subscription details for session {session_id}: {sub_err}"
                )

        # ── Enrich with plan details from local DB ──
        session_metadata = getattr(session, "metadata", None) or {}
        plan_id = (
            session_metadata.get("plan_id")
            if isinstance(session_metadata, dict)
            else dict(session_metadata).get("plan_id")
        ) if session_metadata else None
        if plan_id:
            try:
                plan = await mongo.db["subscription_plans"].find_one({"_id": plan_id})
                if plan:
                    result["plan"] = {
                        "name": plan.get("name"),
                        "description": plan.get("description"),
                        "max_weddings": plan.get("max_weddings"),
                        "max_guests_per_wedding": plan.get("max_guests_per_wedding"),
                        "ai_credits_monthly": plan.get("ai_credits_monthly"),
                        "storage_gb": plan.get("storage_gb"),
                        "staff_seats": plan.get("staff_seats", 0),
                        "features": plan.get("features", {}),
                    }
            except Exception as plan_err:
                logger.warning(
                    f"Could not enrich plan details for session {session_id}: {plan_err}"
                )

        # ── Enrich with latest invoice (PDF + hosted URL) ──
        if session.subscription:
            try:
                invoices = stripe.Invoice.list(
                    subscription=session.subscription,
                    limit=1,
                )
                if invoices.data:
                    latest = invoices.data[0]
                    result["invoice"] = {
                        "id": latest.id,
                        "number": latest.number,
                        "invoice_pdf": latest.invoice_pdf,
                        "hosted_invoice_url": latest.hosted_invoice_url,
                        "status": latest.status,
                        "amount_paid": latest.amount_paid / 100 if latest.amount_paid else 0,
                    }
            except Exception as inv_err:
                logger.warning(
                    f"Could not fetch invoice for session {session_id}: {inv_err}"
                )

        return {
            "status": "success",
            "session": result,
        }

    except Exception as e:
        logger.error(f"Error retrieving checkout session: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve session: {str(e)}"
        )


@router.get("/payment-intent/{id}")
async def get_payment_intent_details(id: str):
    """
    Public endpoint to retrieve PaymentIntent details for the payment page.
    No auth required as couples pay without login.
    """
    try:
        import stripe
        from app.core.settings import settings

        if not settings.stripe_secret_key:
            raise HTTPException(status_code=503, detail="Stripe is not configured")

        stripe.api_key = settings.stripe_secret_key

        payment_request = await _get_payment_request_by_public_token(id)
        pi = stripe.PaymentIntent.retrieve(payment_request["payment_intent_id"])

        response = {
            "id": pi.id,
            "amount": pi.amount / 100,
            "currency": pi.currency,
            "status": pi.status,
            "description": pi.description,
            "public_token": payment_request["public_token"],
        }

        if pi.status in PAYABLE_PAYMENT_INTENT_STATUSES:
            response["client_secret"] = pi.client_secret

        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving PI: {e}")
        raise HTTPException(status_code=404, detail="Payment request not found")


@router.get("/payment-intent/{id}/summary")
async def get_payment_intent_summary(id: str):
    """
    Public endpoint to retrieve non-secret PaymentIntent details for the success page.
    """
    try:
        import stripe
        from app.core.settings import settings

        if not settings.stripe_secret_key:
            raise HTTPException(status_code=503, detail="Stripe is not configured")

        stripe.api_key = settings.stripe_secret_key

        payment_request = await _get_payment_request_by_public_token(id)
        pi = stripe.PaymentIntent.retrieve(payment_request["payment_intent_id"])

        return {
            "id": pi.id,
            "amount": pi.amount / 100,
            "currency": pi.currency,
            "status": pi.status,
            "description": pi.description,
            "public_token": payment_request["public_token"],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving PI summary: {e}")
        raise HTTPException(status_code=404, detail="Payment request not found")


# ==================== CUSTOMER PORTAL ENDPOINTS ====================


@router.post("/create-portal-session")
async def create_portal_session(
    request: CreatePortalSessionRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
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
            return_url=request.return_url or "",
            flow_type=request.flow_type or None,
        )

        return {"status": "success", "portal_url": portal_session["url"]}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating portal session: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create portal session: {str(e)}"
        )


# ==================== WEBHOOK ENDPOINT ====================


@router.post("/webhook")
async def stripe_webhook(
    request: Request, stripe_signature: str = Header(None, alias="stripe-signature")
):
    """
    Handle Stripe webhook events

    This endpoint receives real-time updates from Stripe about:
    - Successful payments
    - Failed payments
    - Subscription changes
    - Customer updates
    - Product/price changes

    IMPORTANT: Configure this endpoint in your Stripe Dashboard:
    https://dashboard.stripe.com/webhooks

    Endpoint URL: https://yourdomain.com/stripe/webhook
    (Also available at: https://yourdomain.com/api/stripe/webhook)

    Events to listen for:
    - checkout.session.completed
    - checkout.session.expired
    - customer.subscription.created
    - customer.subscription.updated
    - customer.subscription.deleted
    - customer.subscription.trial_will_end
    - customer.updated
    - invoice.paid
    - invoice.payment_failed
    - invoice.finalized
    - payment_intent.succeeded
    - payment_intent.payment_failed
    - product.updated
    - price.created
    - price.updated
    - account.updated
    """
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing stripe-signature header")

    try:
        # Get raw body
        payload = await request.body()

        # Process webhook
        result = await stripe_service.handle_webhook_event(payload, stripe_signature)

        # Distinguish retriable errors from permanent failures.
        # Missing metadata or deleted users will never succeed — return 200 so Stripe stops retrying.
        # Transient errors (DB timeout, network) should return 500 so Stripe retries.
        if isinstance(result, dict) and result.get("status") == "error":
            error_msg = result.get("message", "unknown")
            logger.error(f"Webhook handler returned error: {error_msg}")

            # Permanent failures: acknowledge receipt, log for manual investigation
            permanent_keywords = [
                "not found",
                "Missing user_id",
                "Missing plan_id",
                "metadata",
            ]
            if any(kw.lower() in error_msg.lower() for kw in permanent_keywords):
                logger.warning(
                    f"Permanent webhook failure (will not retry): {error_msg}"
                )
                return {"status": "error_acknowledged", "message": error_msg}

            # Transient failures: return 500 so Stripe retries
            raise HTTPException(
                status_code=500, detail=f"Webhook handler error: {error_msg}"
            )

        return {"status": "success", "result": result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Webhook processing failed: {str(e)}"
        )


# ==================== CONNECT / MARKETPLACE ENDPOINTS ====================


@router.post("/connect/onboard")
async def create_connect_account_link(
    request: ConnectOnboardRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    Create a Stripe Connect onboarding link for the current user.
    This allows Planners or Vendors to receive payments.
    """
    try:
        user_id = str(current_user.user_data.get("_id"))
        email = current_user.user_data.get("email")
        if not email:
            raise HTTPException(
                status_code=400, detail="User email is required for Connect onboarding"
            )

        # Create or get connected account
        account_id = await stripe_service.create_connected_account(
            user_id=user_id, email=email, country=request.country
        )

        # Create onboarding link
        url = stripe_service.create_account_link(
            account_id=account_id,
            refresh_url=request.refresh_url,
            return_url=request.return_url,
        )

        return {"status": "success", "url": url, "account_id": account_id}
    except Exception as e:
        logger.error(f"Error creating connect link: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create onboarding link: {str(e)}"
        )


@router.get("/connect/status")
async def get_connect_status(
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    Check the onboarding status of the current user's connected account.
    """
    try:
        user_id = str(current_user.user_data.get("_id"))
        from app.core.database import mongo

        user = await mongo.db["users"].find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        connect_id = user.get("stripe_connect_id")

        if not connect_id:
            return {
                "status": "not_connected",
                "charges_enabled": False,
                "payouts_enabled": False,
                "details_submitted": False,
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
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    Create a payment intent for a Planner to pay a Vendor.
    This handles resolving the vendor from either a User ID or a VendorProfile ID.
    """
    try:
        sender_id = str(current_user.user_data.get("_id"))

        from app.core.database import mongo

        # 1. Try finding as User first (direct ID match)
        vendor_user = await mongo.db["users"].find_one(
            {"_id": ObjectId(request.vendor_user_id)}
        )

        # 2. If not found, try finding as VendorProfile and look up associated user by email
        if not vendor_user:
            # Assuming vendors collection name is 'vendor_directory' or 'vendors'.
            # In vendor.py, it's VendorProfile.
            # Based on services/vendorManagementApi.ts, endpoint is /admin/directory, so collection likely 'vendor_directory' or similar.
            # I will check mongo collection name via introspection or common convention.
            # Given vendor.py doesn't specify collection, I'll assume 'vendor_directory' or 'vendors'.
            # Let's try 'vendor_directory' first as per API path.

            vendor_profile = await mongo.db["vendor_directory"].find_one(
                {"_id": ObjectId(request.vendor_user_id)}
            )

            if vendor_profile:
                vendor_email = vendor_profile.get("email")
                if vendor_email:
                    vendor_user = await mongo.db["users"].find_one(
                        {"email": vendor_email}
                    )

        if not vendor_user:
            raise HTTPException(
                status_code=404,
                detail="Vendor user account not found. The vendor must be a registered user to receive payments.",
            )

        vendor_connect_id = vendor_user.get("stripe_connect_id")
        if not vendor_connect_id:
            raise HTTPException(
                status_code=400,
                detail="Vendor has not connected their Stripe account to receive payments.",
            )

        # Verify sender permission (if needed, e.g. checking budget)
        # For now, we assume if they pay, they pay.

        result = await stripe_service.create_vendor_payment_intent(
            sender_user_id=sender_id,
            vendor_connect_id=vendor_connect_id,
            amount=request.amount,
            currency=request.currency,
            description=request.description or "",
        )

        return {"status": "success", "payment_intent": result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating vendor payment: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create payment: {str(e)}"
        )


# ==================== PAYMENT COLLECTION FOR COUPLES ====================


@router.post("/create-payment-intent")
async def create_payment_intent(
    request: CreatePaymentIntentRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
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

            # Try string ID first (wedding IDs are stored as strings like "wedding_XXXXX")
            wedding = await mongo.db["weddings"].find_one({"_id": request.wedding_id})
            if not wedding:
                try:
                    wedding = await mongo.db["weddings"].find_one(
                        {"_id": ObjectId(request.wedding_id)}
                    )
                except Exception:
                    pass
            if not wedding:
                raise HTTPException(status_code=404, detail="Wedding not found")

            # Check if user has access to this wedding
            user_id = str(current_user.user_data.get("_id"))
            planner_id = wedding.get("planner_id")

            # If current user is not admin, they must be the planner
            if (
                not current_user.is_root_admin
                and planner_id
                and str(planner_id) != user_id
            ):
                raise HTTPException(
                    status_code=403,
                    detail="You don't have permission to create payments for this wedding",
                )

            # If we want to route funds to the planner of the wedding:
            if planner_id:
                planner = await mongo.db["users"].find_one({"_id": planner_id})
                if planner and planner.get("stripe_connect_id"):
                    destination_account_id = planner.get("stripe_connect_id")

        # Override destination if explicitly provided (and allowed?)
        # For security, maybe restrict who can set destination_user_id
        if request.destination_user_id:
            # Look up connect ID for this user
            from app.core.database import mongo

            dest_user = await mongo.db["users"].find_one(
                {"_id": ObjectId(request.destination_user_id)}
            )
            if dest_user and dest_user.get("stripe_connect_id"):
                destination_account_id = dest_user.get("stripe_connect_id")

        if not request.wedding_id:
            raise HTTPException(status_code=400, detail="wedding_id is required")

        wedding_id: str = request.wedding_id
        description: str = request.description or ""

        payment_intent = stripe_service.create_payment_intent_for_couple(
            amount=request.amount,
            currency=request.currency,
            wedding_id=wedding_id,
            description=description,
            metadata=request.metadata or {},
            destination_account_id=destination_account_id or "",
        )

        # Save payment request record to Mongo
        from app.core.database import mongo
        from datetime import datetime, timezone

        public_token = secrets.token_urlsafe(24)

        await mongo.db["payment_requests"].insert_one(
            {
                "user_id": str(current_user.user_data.get("_id")),
                "public_token": public_token,
                "payment_intent_id": payment_intent["payment_intent_id"],
                "amount": request.amount,
                "currency": request.currency,
                "status": "pending",  # Initial status
                "wedding_id": wedding_id,
                "description": request.description,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
        )

        payment_intent["public_token"] = public_token

        return {"status": "success", "payment_intent": payment_intent}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating payment intent: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create payment intent: {str(e)}"
        )


@router.get("/payment-requests")
async def get_payment_requests(
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    Get list of payment requests created by the current planner.
    Includes wedding_title for associated weddings.
    """
    try:
        from app.core.database import mongo

        user_id = str(current_user.user_data.get("_id"))

        cursor = (
            mongo.db["payment_requests"]
            .find({"user_id": user_id})
            .sort("created_at", -1)
        )
        requests = await cursor.to_list(length=100)

        # Collect wedding IDs to fetch titles (support both string and ObjectId formats)
        string_wedding_ids = set()
        objectid_wedding_ids = set()
        for req in requests:
            if req.get("wedding_id"):
                string_wedding_ids.add(req["wedding_id"])
                try:
                    objectid_wedding_ids.add(ObjectId(req["wedding_id"]))
                except Exception:
                    pass

        # Fetch wedding titles in bulk (try both ID formats)
        wedding_titles = {}
        if string_wedding_ids:
            # Try string IDs first
            weddings_cursor = mongo.db["weddings"].find(
                {"_id": {"$in": list(string_wedding_ids)}}, {"_id": 1, "title": 1}
            )
            weddings = await weddings_cursor.to_list(length=len(string_wedding_ids))
            wedding_titles = {
                str(w["_id"]): w.get("title", "Untitled Wedding") for w in weddings
            }

            # Fallback: try ObjectId format for any not found
            if objectid_wedding_ids and len(wedding_titles) < len(string_wedding_ids):
                weddings_cursor = mongo.db["weddings"].find(
                    {"_id": {"$in": list(objectid_wedding_ids)}}, {"_id": 1, "title": 1}
                )
                weddings = await weddings_cursor.to_list(
                    length=len(objectid_wedding_ids)
                )
                for w in weddings:
                    wedding_titles[str(w["_id"])] = w.get("title", "Untitled Wedding")

        # Enrich requests with wedding_title and convert ObjectId to str
        for req in requests:
            req["_id"] = str(req["_id"])
            if req.get("wedding_id"):
                req["wedding_title"] = wedding_titles.get(req["wedding_id"], None)

        return requests
    except Exception as e:
        logger.error(f"Error fetching payment requests: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch payment requests")


# ==================== BILLING HISTORY ENDPOINTS ====================


@router.get("/invoices")
async def get_invoices(
    limit: int = 10, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Get billing history (invoices) for the current user

    Returns list of past invoices with amounts, dates, status, and PDF links.
    """
    try:
        import stripe
        from app.core.settings import settings
        from app.core.database import mongo

        if not settings.stripe_enabled or not settings.stripe_secret_key:
            return []

        stripe.api_key = settings.stripe_secret_key
        user_id = str(current_user.user_data.get("_id"))

        # Get customer ID from stripe_customers collection
        customer_record = await mongo.db["stripe_customers"].find_one(
            {"user_id": user_id}
        )
        if not customer_record or not customer_record.get("stripe_customer_id"):
            return []

        customer_id = customer_record["stripe_customer_id"]

        # Fetch invoices from Stripe
        invoices = stripe.Invoice.list(
            customer=customer_id,
            limit=limit,
            status="paid",  # Only show paid invoices
        )

        result = []
        for invoice in invoices.data:
            result.append(
                {
                    "id": invoice.id,
                    "date": invoice.created,  # Unix timestamp
                    "amount": invoice.amount_paid,  # In cents
                    "status": invoice.status,
                    "invoice_pdf": invoice.invoice_pdf,
                    "description": invoice.lines.data[0].description
                    if invoice.lines.data
                    else "Subscription payment",
                    "period_start": invoice.period_start,
                    "period_end": invoice.period_end,
                    "number": invoice.number,
                }
            )

        return result

    except Exception as e:
        logger.error(f"Error fetching invoices: {str(e)}")
        return []


@router.get("/payment-method")
async def get_payment_method(
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    Get the default payment method details for the current user

    Returns masked card information (last 4 digits, brand, expiry).
    """
    try:
        from app.core.settings import settings
        from app.core.database import mongo

        if not settings.stripe_enabled or not settings.stripe_secret_key:
            return {"has_payment_method": False}

        stripe.api_key = settings.stripe_secret_key
        user_id = str(current_user.user_data.get("_id"))

        # Get customer ID
        customer_record = await mongo.db["stripe_customers"].find_one(
            {"user_id": user_id}
        )
        if not customer_record or not customer_record.get("stripe_customer_id"):
            return {"has_payment_method": False}

        customer_id = customer_record["stripe_customer_id"]

        # Get customer to find default payment method
        customer = stripe.Customer.retrieve(customer_id)

        # Safely get default payment method from invoice_settings
        default_pm_id: Optional[str] = None
        invoice_settings = customer.invoice_settings
        if invoice_settings is not None:
            pm_ref = invoice_settings.default_payment_method
            # Could be a string ID or an expanded PaymentMethod object
            if isinstance(pm_ref, str):
                default_pm_id = pm_ref
            elif pm_ref is not None:
                # Expanded PaymentMethod object - get its ID
                default_pm_id = pm_ref.id

        if not default_pm_id:
            # Try to get from subscriptions
            subscriptions = stripe.Subscription.list(customer=customer_id, limit=1)
            if subscriptions.data:
                sub_pm = subscriptions.data[0].default_payment_method
                if isinstance(sub_pm, str):
                    default_pm_id = sub_pm
                elif sub_pm is not None:
                    default_pm_id = sub_pm.id

        if not default_pm_id:
            return {"has_payment_method": False}

        # Retrieve payment method details
        pm = stripe.PaymentMethod.retrieve(default_pm_id)

        # Safely access card details with explicit None checks
        if pm.type == "card":
            card = pm.card
            if card is not None:
                card_brand = card.brand
                return {
                    "has_payment_method": True,
                    "type": "card",
                    "card_brand": card_brand.capitalize() if card_brand else "Card",
                    "card_last_four": card.last4,
                    "card_exp_month": card.exp_month,
                    "card_exp_year": card.exp_year,
                    "card_funding": card.funding,
                }

        # Non-card payment method
        return {"has_payment_method": True, "type": pm.type}

    except Exception as e:
        logger.error(f"Error fetching payment method: {str(e)}")
        return {"has_payment_method": False}


@router.get("/subscription")
async def get_subscription_details(
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    Get detailed subscription information including payment method

    Returns subscription status, plan details, billing dates, and card info.
    """
    try:
        import stripe
        from app.core.settings import settings
        from app.core.database import mongo

        if not settings.stripe_enabled or not settings.stripe_secret_key:
            raise HTTPException(status_code=503, detail="Stripe is not enabled")

        stripe.api_key = settings.stripe_secret_key
        user_id = str(current_user.user_data.get("_id"))

        # Get local subscription record
        subscription_record = await mongo.db["user_subscriptions"].find_one(
            {"user_id": user_id}
        )

        # Fallback: if user_subscriptions record is missing (e.g. standalone MongoDB
        # transaction failed during webhook), reconstruct from the users collection
        # which is also updated by _sync_subscription_state.
        if not subscription_record:
            from bson import ObjectId as _ObjId

            user_doc = await mongo.db["users"].find_one(
                {"_id": _ObjId(user_id)},
                {
                    "subscription_status": 1,
                    "plan_id": 1,
                    "stripe_subscription_id": 1,
                    "stripe_customer_id": 1,
                    "trial_end_date": 1,
                    "created_at": 1,
                },
            )
            normalized_status = (
                normalize_subscription_status(user_doc.get("subscription_status"))
                if user_doc
                else None
            )
            if user_doc and normalized_status in ACTIVE_SUBSCRIPTION_STATUSES:
                # Construct a minimal subscription record from users collection
                subscription_record = {
                    "user_id": user_id,
                    "plan_id": user_doc.get("plan_id"),
                    "status": normalized_status,
                    "stripe_subscription_id": user_doc.get("stripe_subscription_id"),
                    "stripe_customer_id": user_doc.get("stripe_customer_id"),
                    "billing_interval": "monthly",
                    "current_period_start": user_doc.get("created_at"),
                    "trial_end_date": user_doc.get("trial_end_date"),
                    "payment_status": "paid",
                }
                logger.info(
                    f"Reconstructed subscription from users collection for user {user_id}"
                )
            else:
                raise HTTPException(status_code=404, detail="No subscription found")

        plan_id = subscription_record.get("plan_id")
        plan = None
        if plan_id:
            plan = await mongo.db["subscription_plans"].find_one({"_id": plan_id})

        # Get customer and payment method from Stripe
        customer_record = await mongo.db["stripe_customers"].find_one(
            {"user_id": user_id}
        )
        card_info = {}

        if customer_record and customer_record.get("stripe_customer_id"):
            try:
                customer = stripe.Customer.retrieve(
                    customer_record["stripe_customer_id"]
                )

                # Safely get default payment method from invoice_settings
                default_pm_id: str | None = None
                invoice_settings = customer.invoice_settings
                if invoice_settings is not None:
                    pm_ref = invoice_settings.default_payment_method
                    if isinstance(pm_ref, str):
                        default_pm_id = pm_ref
                    elif pm_ref is not None:
                        default_pm_id = pm_ref.id

                if not default_pm_id:
                    subs = stripe.Subscription.list(customer=customer.id, limit=1)
                    if subs.data:
                        sub_pm = subs.data[0].default_payment_method
                        if isinstance(sub_pm, str):
                            default_pm_id = sub_pm
                        elif sub_pm is not None:
                            default_pm_id = sub_pm.id

                if default_pm_id:
                    pm = stripe.PaymentMethod.retrieve(default_pm_id)
                    if pm.type == "card":
                        card = pm.card
                        if card is not None:
                            card_brand = card.brand
                            card_info = {
                                "card_brand": card_brand.capitalize()
                                if card_brand
                                else "Card",
                                "card_last_four": card.last4,
                                "card_exp_month": card.exp_month,
                                "card_exp_year": card.exp_year,
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
            **card_info,
        }

        if plan:
            response["plan_name"] = plan.get("name")
            response["plan_description"] = plan.get("description")
            response["ai_credits_total"] = plan.get("ai_credits_monthly")
            response["weddings_total"] = plan.get("max_weddings")
            billing_interval = subscription_record.get("billing_interval", "monthly")
            response["price"] = (
                plan.get("price_yearly")
                if billing_interval == "yearly"
                else plan.get("price_monthly")
            )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching subscription details: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch subscription: {str(e)}"
        )


# ==================== CONFIGURATION ENDPOINT ====================


@router.get("/config")
async def get_stripe_config():
    """
    Get Stripe public configuration (publishable key)

    This key is safe to expose in frontend code and is required
    to initialize Stripe.js. No auth required — the publishable key
    is designed to be public (pk_live_ / pk_test_) and is needed by
    the couple-facing payment page (/pay/[id]) which has no login.
    """
    from app.core.settings import settings

    if not settings.stripe_enabled:
        raise HTTPException(status_code=503, detail="Stripe is not enabled")

    if not settings.stripe_publishable_key:
        raise HTTPException(
            status_code=500, detail="Stripe publishable key not configured"
        )

    return {"publishable_key": settings.stripe_publishable_key, "currency": "usd"}


# ==================== PUBLIC WEBHOOK ENDPOINT (NO AUTH) ====================
# Note: The webhook endpoint above should be accessible without authentication
# This is handled by FastAPI's dependency system - we don't use Depends() for webhooks
