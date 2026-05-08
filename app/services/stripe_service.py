"""Stripe payment utilities used to manage subscription checkout and lifecycle."""

import html
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import stripe
from bson import ObjectId
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError
from stripe import InvalidRequestError, SignatureVerificationError, StripeError

from app.core.database import mongo
from app.core.settings import settings
from app.models.subscription import SubscriptionStatus, normalize_subscription_status
from app.services.couple_lifecycle_service import (
    COUPLE_PORTAL_STATE_REVOKED,
    couple_lifecycle_service,
)
from app.services.email_service_resend import ResendEmailService
from app.services.planner_access_lifecycle_service import (
    planner_access_lifecycle_service,
)
from app.services.stripe_meter_helpers import assert_meter_config
from app.utils.id_utils import to_object_id
from app.utils.planner_ownership import (
    build_wedding_owner_query,
    extract_wedding_owner_identity,
    normalize_query_id,
    resolve_planner_email,
)

logger = logging.getLogger(__name__)


def _safe_external_url(url: Optional[str]) -> Optional[str]:
    """Return ``url`` only if it uses an http(s) scheme, else None.

    Defends against `javascript:` / `data:` URI XSS in email href
    interpolations. Live verification (2026-04-29) caught
    `invoice_pdf="javascript:alert(1)"` slipping past ``html.escape`` and
    landing in an ``<a href>``. ``html.escape(quote=True)`` only escapes
    ``"``/``'``; it does NOT validate the URL scheme. This helper closes
    that gap. Stripe-supplied URLs always begin with ``https://``, so this
    is a no-op for legitimate input.
    """
    if not url:
        return None
    s = str(url).strip()
    if not s:
        return None
    lower = s.lower()
    if lower.startswith("https://") or lower.startswith("http://"):
        return s
    return None


# Initialize Stripe
if settings.stripe_enabled and settings.stripe_secret_key:
    stripe.api_key = settings.stripe_secret_key
    # Pin the API version so MeterEvent / MeterEventAdjustment / Meter
    # behavior does not drift on Stripe-side default changes between
    # SDK upgrades. Matches the SDK 15.1.0 default
    # (stripe._api_version._ApiVersion.CURRENT). Bump intentionally when
    # the codebase adopts a newer API behavior. Mirrored in
    # scripts/seed_subscription_plans.py — keep both in sync.
    stripe.api_version = "2026-04-22.dahlia"
else:
    logger.warning("Stripe is not enabled or API key is missing")


class StripeService:
    """
    Service for managing Stripe payment operations including:
    - Customer creation and management
    - Subscription checkout sessions
    - Customer portal sessions
    - Webhook handling for subscription events
    - Payment collection for couples (Connect/Transfer functionality)
    """

    def __init__(self):
        self.subscriptions_collection = mongo.db["user_subscriptions"]
        self.users_collection = mongo.get_users_collection()
        self.plans_collection = mongo.db["subscription_plans"]
        self.stripe_customers_collection = mongo.db["stripe_customers"]
        self.weddings_collection = mongo.db["weddings"]
        self.email_service = ResendEmailService()

    def _ensure_stripe_enabled(self):
        """Verify Stripe is properly configured"""
        if not settings.stripe_enabled:
            raise HTTPException(
                status_code=503,
                detail="Stripe payment processing is currently disabled",
            )
        if not settings.stripe_secret_key:
            raise HTTPException(
                status_code=500, detail="Stripe configuration error: Missing secret key"
            )

    def _get_billing_sender(self) -> Dict[str, Optional[str]]:
        """Use the dedicated billing sender when configured, otherwise fall back to the default mail sender."""
        return {
            "from_email": settings.resend_billing_email or settings.resend_from_email,
            "from_name": settings.resend_from_name,
        }

    # ==================== CUSTOMER MANAGEMENT ====================

    async def get_or_create_customer(
        self, user_id: str, email: str, name: Optional[str] = None
    ) -> str:
        """
        Get existing Stripe customer ID or create a new customer

        Args:
            user_id: Internal user ID
            email: Customer email
            name: Customer name (optional)

        Returns:
            Stripe customer ID
        """
        self._ensure_stripe_enabled()

        try:
            # Check if customer already exists in our database
            customer_record = await self.stripe_customers_collection.find_one(
                {"user_id": user_id}
            )

            if customer_record and customer_record.get("stripe_customer_id"):
                # Verify customer exists in Stripe
                try:
                    stripe.Customer.retrieve(customer_record["stripe_customer_id"])
                    return customer_record["stripe_customer_id"]
                except InvalidRequestError:
                    # Customer doesn't exist in Stripe, create new one
                    logger.warning(
                        f"Stripe customer {customer_record['stripe_customer_id']} not found, creating new"
                    )

            # Create new Stripe customer
            customer = stripe.Customer.create(
                email=email, name=name or email, metadata={"user_id": user_id}
            )

            # Save customer ID to database — rollback Stripe customer on failure
            try:
                await self.stripe_customers_collection.update_one(
                    {"user_id": user_id},
                    {
                        "$set": {
                            "user_id": user_id,
                            "stripe_customer_id": customer.id,
                            "email": email,
                            "created_at": datetime.now(timezone.utc),
                            "updated_at": datetime.now(timezone.utc),
                        }
                    },
                    upsert=True,
                )
            except Exception as db_err:
                # MongoDB write failed — delete the orphaned Stripe customer
                logger.error(
                    f"MongoDB save failed after Stripe customer creation, rolling back: {db_err}"
                )
                try:
                    stripe.Customer.delete(customer.id)
                    logger.info(f"Rolled back orphaned Stripe customer {customer.id}")
                except Exception as rollback_err:
                    logger.critical(
                        f"ORPHANED Stripe customer {customer.id} for user {user_id} — "
                        f"manual cleanup required. Rollback error: {rollback_err}"
                    )
                raise HTTPException(
                    status_code=500,
                    detail="Failed to save payment profile. Please try again.",
                )

            logger.info(f"Created Stripe customer {customer.id} for user {user_id}")
            return customer.id

        except StripeError as e:
            logger.error(f"Stripe error creating customer: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Payment service error: {str(e)}"
            )
        except HTTPException:
            raise  # Re-raise HTTPExceptions from the MongoDB rollback block
        except Exception as e:
            logger.error(f"Error creating Stripe customer: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error creating customer: {str(e)}"
            )

    # ==================== CHECKOUT SESSION ====================

    # ==================== PRODUCT & PRICE MANAGEMENT ====================

    def sync_plan_to_stripe(self, plan: Dict[str, Any]) -> Dict[str, str]:
        """
        Ensure a local subscription plan exists in Stripe as a Product and Price.
        Returns a dictionary with 'stripe_product_id', 'stripe_price_id_monthly', 'stripe_price_id_yearly'.
        """
        self._ensure_stripe_enabled()

        try:
            product_id = plan.get("stripe_product_id")
            price_id_monthly = plan.get("stripe_price_id_monthly")
            price_id_yearly = plan.get("stripe_price_id_yearly")

            # Metered Billing Config
            is_metered = plan.get("is_metered", False)
            meter_event_name = plan.get("meter_event_name")
            meter_id = plan.get("meter_id")

            # Try to resolve meter_id from event_name if missing
            if is_metered and meter_event_name and not meter_id:
                try:
                    # List meters to find matching event name
                    meters = stripe.billing.Meter.list(status="active")
                    for meter in meters.data:
                        if meter.event_name == meter_event_name:
                            meter_id = meter.id
                            break
                except Exception as e:
                    logger.warning(f"Failed to list Stripe meters: {e}")

            if is_metered and not meter_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Metered plan '{plan.get('_id')}' requires a valid Stripe meter_id or meter_event_name",
                )

            # Preflight: verify the live meter's config matches what the
            # codebase requires. Without this, a meter created in the Stripe
            # Dashboard with the wrong aggregation formula or payload key
            # mappings would cause every meter event to be silently
            # rejected (or, worse on Count/Last, silently overbill on
            # delete-reversals). See METERING_REVIEW_2026-05-04_PART2.md
            # §5 (CC2) and stripe_meter_helpers.assert_meter_config.
            if is_metered and meter_id:
                try:
                    assert_meter_config(meter_id)
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail=str(exc))

            # 1. Create or Update Product
            if not product_id:
                product = stripe.Product.create(
                    name=plan["name"],
                    description=plan.get("description", ""),
                    metadata={"plan_id": plan["_id"]},
                )
                product_id = product.id
            else:
                try:
                    stripe.Product.retrieve(product_id)
                    stripe.Product.modify(
                        product_id,
                        name=plan["name"],
                        description=plan.get("description", ""),
                        metadata={"plan_id": plan["_id"]},
                    )
                except InvalidRequestError:
                    # Product might have been deleted in Stripe
                    product = stripe.Product.create(
                        name=plan["name"],
                        description=plan.get("description", ""),
                        metadata={"plan_id": plan["_id"]},
                    )
                    product_id = product.id

            # 2. Create Prices if missing or if amounts changed (Stripe prices are immutable, create new one)
            # Logic: If we have a price ID, check if it matches current amount. If not, create new.

            # Helper to check/create price
            # Per Stripe docs: prices are immutable. To change amount:
            # 1. Create new price with new amount
            # 2. Switch to new price ID
            # 3. Deactivate old price
            def ensure_price(current_price_id, amount, interval):
                if amount is None:
                    return None

                amount_cents = int(amount * 100)

                # Determine expected recurring config
                expected_recurring = {"interval": interval}
                if is_metered:
                    expected_recurring["usage_type"] = "metered"
                    if meter_id:
                        expected_recurring["meter"] = meter_id

                if current_price_id:
                    try:
                        price = stripe.Price.retrieve(current_price_id)

                        # Check basic fields
                        matches = (
                            price.unit_amount == amount_cents
                            and price.currency == "usd"
                            and price.recurring
                            and price.recurring.interval == interval
                        )

                        # Check metered config
                        if matches and is_metered and price.recurring:
                            matches = price.recurring.usage_type == "metered"
                            if meter_id:
                                matches = matches and (
                                    getattr(price.recurring, "meter", None) == meter_id
                                )
                        elif matches and not is_metered and price.recurring:
                            matches = price.recurring.usage_type != "metered"

                        if matches:
                            return current_price_id

                        # Price exists but doesn't match - will create new, deactivate old below
                    except InvalidRequestError:
                        current_price_id = None  # Price not found, just create new

                price_kwargs = {
                    "product": product_id,
                    "unit_amount": amount_cents,
                    "currency": "usd",
                    "recurring": expected_recurring,
                    "nickname": f"{plan['name']} {interval.title()}",
                }

                if is_metered and meter_id:
                    price_kwargs["recurring"]["meter"] = meter_id
                    price_kwargs["recurring"]["usage_type"] = "metered"

                new_price = stripe.Price.create(**price_kwargs)

                # Deactivate old price if it existed (Stripe best practice)
                if current_price_id:
                    try:
                        stripe.Price.modify(current_price_id, active=False)
                        logger.info(
                            f"Deactivated old price {current_price_id} after creating new price {new_price.id}"
                        )
                    except StripeError as e:
                        logger.warning(
                            f"Could not deactivate old price {current_price_id}: {e}"
                        )

                return new_price.id

            new_price_id_monthly = ensure_price(
                price_id_monthly, plan.get("price_monthly"), "month"
            )
            new_price_id_yearly = ensure_price(
                price_id_yearly, plan.get("price_yearly"), "year"
            )

            result = {
                "stripe_product_id": product_id,
                "stripe_price_id_monthly": new_price_id_monthly,
                "stripe_price_id_yearly": new_price_id_yearly,
            }

            # If we found a meter_id and it wasn't in the plan, return it so we can update the DB
            if meter_id and not plan.get("meter_id"):
                result["meter_id"] = meter_id

            return result

        except StripeError as e:
            logger.error(f"Stripe error syncing plan: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Stripe Sync Error: {str(e)}")

    def archive_stripe_product(self, stripe_product_id: str) -> bool:
        """
        Archive a Stripe product when a subscription plan is deleted.
        This deactivates the product and its prices without permanently deleting them.
        Returns True if successful, raises exception on failure.
        """
        self._ensure_stripe_enabled()

        if not stripe_product_id:
            logger.warning("No Stripe product ID provided for archival")
            return False

        try:
            # Deactivate all prices for this product first
            prices = stripe.Price.list(product=stripe_product_id, active=True)
            for price in prices.data:
                stripe.Price.modify(price.id, active=False)
                logger.info(f"Deactivated Stripe price: {price.id}")

            # Archive the product (set active=False)
            stripe.Product.modify(stripe_product_id, active=False)
            logger.info(f"Archived Stripe product: {stripe_product_id}")
            return True

        except InvalidRequestError as e:
            # Product might not exist in Stripe
            logger.warning(
                f"Could not archive Stripe product {stripe_product_id}: {str(e)}"
            )
            return False
        except StripeError as e:
            logger.error(f"Stripe error archiving product: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Stripe Archive Error: {str(e)}"
            )

    def report_meter_event(
        self,
        event_name: str,
        payload: Dict[str, Any],
        timestamp: Optional[datetime] = None,
        identifier: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a usage event to Stripe Billing Meter.

        Args:
            event_name: Meter event name (must match Stripe meter config)
            payload: Dict with stripe_customer_id and value
            timestamp: Optional timestamp (defaults to now)
            identifier: CRITICAL idempotency key to prevent double-billing.
                       Should be deterministic: f"{customer_id}_{resource_id}_{period}"
                       Stripe enforces uniqueness within 24 hours. Max 100 chars.

        Returns:
            Dict with status and event_id or error message
        """
        self._ensure_stripe_enabled()

        try:
            # Current timestamp if not provided
            if not timestamp:
                timestamp = datetime.now(timezone.utc)

            # Build meter event params
            meter_params: Dict[str, Any] = {
                "event_name": event_name,
                "payload": payload,
                "timestamp": int(timestamp.timestamp()),
            }

            # Add idempotency identifier if provided - prevents duplicate billing on retries
            if identifier:
                meter_params["identifier"] = identifier[:100]  # Max 100 chars

            event = stripe.billing.MeterEvent.create(**meter_params)
            return {"status": "success", "event_id": event.identifier}
        except StripeError as e:
            error_msg = str(e)
            # Duplicate identifier = already recorded (this is success, not error)
            if "identifier" in error_msg.lower() and (
                "already" in error_msg.lower() or "duplicate" in error_msg.lower()
            ):
                logger.info(f"Meter event already recorded (idempotent): {identifier}")
                return {
                    "status": "success",
                    "event_id": identifier,
                    "already_recorded": True,
                }
            logger.error(f"Stripe error reporting usage: {error_msg}")
            return {"status": "error", "message": error_msg}

    async def create_checkout_session(
        self,
        user_id: str,
        plan_id: str,
        billing_interval: str = "monthly",
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
        trial_days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Create a Stripe Checkout Session for subscription signup

        Args:
            user_id: Internal user ID
            plan_id: Subscription plan ID
            billing_interval: "monthly" or "yearly"
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect if payment is cancelled
            trial_days: Number of trial days (default 0)

        Returns:
            Dictionary with checkout session details
        """
        self._ensure_stripe_enabled()

        try:
            # Get user details
            user = await self.users_collection.find_one({"_id": ObjectId(user_id)})
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            # Get subscription plan
            plan = await self.plans_collection.find_one({"_id": plan_id})
            if not plan:
                raise HTTPException(
                    status_code=404, detail="Subscription plan not found"
                )

            if not plan.get("is_active", True):
                raise HTTPException(
                    status_code=400, detail="Subscription plan is not currently active"
                )

            # Metered flag for downstream usage (quantity rules)
            is_metered = plan.get("is_metered", False)

            # Respect plan-level trial configuration when available
            plan_trial_days = plan.get("trial_days")
            if trial_days is None:
                if isinstance(plan_trial_days, int) and plan_trial_days >= 0:
                    trial_days = plan_trial_days
                else:
                    trial_days = 0
            else:
                trial_days = max(trial_days, 0)

            # Get or create Stripe customer
            customer_id = await self.get_or_create_customer(
                user_id=user_id,
                email=user["email"],
                name=user.get("full_name") or user.get("email"),
            )

            # Determine price based on billing interval
            price_id_field = f"stripe_price_id_{billing_interval}"
            stripe_price_id = plan.get(price_id_field)

            # If Stripe IDs are missing, sync them now
            if not stripe_price_id:
                logger.info(
                    f"Stripe price ID missing for plan {plan_id}, syncing now..."
                )
                sync_result = self.sync_plan_to_stripe(plan)

                # Update plan in DB with new IDs
                await self.plans_collection.update_one(
                    {"_id": plan_id}, {"$set": sync_result}
                )

                stripe_price_id = sync_result.get(price_id_field)

            if not stripe_price_id:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to resolve Stripe price for {billing_interval} billing",
                )

            # Default URLs if not provided
            if not success_url:
                success_url = f"{settings.frontend_url}/admin/billing/success?session_id={{CHECKOUT_SESSION_ID}}"
            if not cancel_url:
                cancel_url = f"{settings.frontend_url}/admin/billing/cancelled"

            # Prepare subscription data
            subscription_data: Dict[str, Any] = {
                "metadata": {
                    "user_id": user_id,
                    "plan_id": plan_id,
                    "billing_interval": billing_interval,
                    "trial_days": trial_days,
                }
            }

            has_trial = trial_days > 0
            if has_trial:
                subscription_data["trial_period_days"] = trial_days
                subscription_data["trial_settings"] = {
                    "end_behavior": {
                        # No-card trials are allowed; cancel if the customer does
                        # not add a payment method before the trial ends.
                        "missing_payment_method": "cancel"
                    }
                }

            # Build line item; quantity must be omitted for metered prices
            if is_metered:
                line_items: list = [{"price": stripe_price_id}]
            else:
                line_items: list = [{"price": stripe_price_id, "quantity": 1}]

            # Create checkout session
            # Note: payment_method_types is intentionally omitted so Stripe uses
            # dynamic payment methods managed from the Stripe Dashboard. This
            # automatically enables cards, Apple Pay, Google Pay, and other
            # methods Stripe determines are optimal for each customer.
            checkout_session = stripe.checkout.Session.create(
                customer=customer_id,
                line_items=line_items,  # type: ignore
                mode="subscription",
                success_url=success_url,
                cancel_url=cancel_url,
                subscription_data=subscription_data,  # type: ignore
                metadata={
                    "user_id": user_id,
                    "plan_id": plan_id,
                    "billing_interval": billing_interval,
                },
                allow_promotion_codes=True,
                billing_address_collection="auto",
                payment_method_collection="if_required" if has_trial else "always",
                customer_update={"address": "auto", "name": "auto"},
            )

            # Save session reference — guard against concurrent checkouts.
            # Only overwrite if no unexpired checkout session exists (Stripe
            # sessions expire after 24 h, so we use a 30-min active window to
            # prevent rapid duplicate creation while still allowing retries).
            active_window = datetime.now(timezone.utc) - timedelta(minutes=30)

            result = await self.subscriptions_collection.find_one_and_update(
                {
                    "user_id": user_id,
                    "$or": [
                        {"stripe_checkout_session_id": {"$exists": False}},
                        {"stripe_checkout_created_at": {"$exists": False}},
                        {"stripe_checkout_created_at": {"$lt": active_window}},
                    ],
                },
                {
                    "$set": {
                        "user_id": user_id,
                        "stripe_checkout_session_id": checkout_session.id,
                        "stripe_checkout_created_at": datetime.now(timezone.utc),
                        "stripe_customer_id": customer_id,
                        "billing_interval": billing_interval,
                        "plan_id": plan_id,
                        "status": SubscriptionStatus.PENDING_CHECKOUT.value,
                    },
                    "$setOnInsert": {
                        "created_at": datetime.now(timezone.utc),
                        "user_email": user["email"],
                        "start_date": datetime.now(timezone.utc),
                        "created_by": "system:public_signup",
                    },
                },
                upsert=True,
                return_document=True,
            )

            # If the stored session_id differs, a concurrent request won the race
            if (
                result
                and result.get("stripe_checkout_session_id") != checkout_session.id
            ):
                logger.warning(
                    f"Concurrent checkout detected for user {user_id}. "
                    f"Active session: {result.get('stripe_checkout_session_id')}"
                )
                # Expire the just-created Stripe session to avoid dangling sessions
                try:
                    stripe.checkout.Session.expire(checkout_session.id)
                except Exception:
                    pass  # best-effort cleanup
                raise HTTPException(
                    status_code=409,
                    detail="A checkout session is already in progress. Please complete or wait for it to expire before trying again.",
                )

            logger.info(
                f"Created checkout session {checkout_session.id} for user {user_id}"
            )

            return {
                "session_id": checkout_session.id,
                "url": checkout_session.url,
                "customer_id": customer_id,
                "expires_at": checkout_session.expires_at,
            }

        except HTTPException:
            raise
        except StripeError as e:
            logger.error(f"Stripe error creating checkout session: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Payment service error: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Error creating checkout session: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error creating checkout session: {str(e)}"
            )

    def _parse_timestamp(self, timestamp: Optional[int]) -> Optional[datetime]:
        """Convert Stripe timestamps to timezone-aware UTC datetimes."""

        if not timestamp:
            return None
        try:
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        except Exception:
            return None

    def _map_stripe_status(self, stripe_status: Optional[str]) -> str:
        """Translate Stripe subscription status to internal subscription state."""

        if not stripe_status:
            return SubscriptionStatus.ACTIVE.value

        mapped = normalize_subscription_status(stripe_status)
        if mapped is None:
            logger.warning(
                f"Unknown Stripe subscription status '{stripe_status}', defaulting to ACTIVE"
            )
            return SubscriptionStatus.ACTIVE.value
        return mapped

    async def _sync_subscription_state(
        self,
        user_id: Optional[str],
        subscription: Optional[Dict[str, Any]],
        customer_id: Optional[str] = None,
        plan_id: Optional[str] = None,
        extra_updates: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Persist subscription details so MongoDB mirrors Stripe's lifecycle."""

        now = datetime.now(timezone.utc)
        subscription = subscription or {}

        if not plan_id:
            plan_id = subscription.get("metadata", {}).get("plan_id")

        # When a plan is changed via Stripe Customer Portal, the metadata
        # still holds the original plan_id. Resolve the ACTUAL plan from
        # the current Stripe price on the subscription items.
        try:
            items_data = subscription.get("items", {})
            items_list = (
                items_data.get("data", [])
                if isinstance(items_data, dict)
                else (items_data.data if hasattr(items_data, "data") else [])
            )
            if items_list:
                first_item = (
                    items_list[0]
                    if isinstance(items_list[0], dict)
                    else (
                        items_list[0].to_dict()
                        if hasattr(items_list[0], "to_dict")
                        else {}
                    )
                )
                current_price_id = (
                    first_item.get("price", {}).get("id")
                    if isinstance(first_item.get("price"), dict)
                    else first_item.get("price")
                )
                if current_price_id:
                    # Look up which platform plan owns this Stripe price
                    matched_plan = await self.plans_collection.find_one(
                        {
                            "$or": [
                                {"stripe_price_id_monthly": current_price_id},
                                {"stripe_price_id_yearly": current_price_id},
                            ]
                        }
                    )
                    if matched_plan:
                        resolved_plan_id = matched_plan["_id"]
                        if resolved_plan_id != plan_id:
                            logger.info(
                                f"Plan change detected via Stripe price: {plan_id} → {resolved_plan_id} (price: {current_price_id})"
                            )
                            plan_id = resolved_plan_id
        except Exception as e:
            logger.warning(f"Could not resolve plan from Stripe price: {e}")

        if not user_id:
            user_id = subscription.get("metadata", {}).get("user_id")

        stripe_subscription_id = subscription.get("id")

        # Fallback: if user_id still missing (e.g. Portal-initiated changes
        # where metadata may be empty), look it up from existing subscription
        # or stripe_customers collection so the users collection stays in sync.
        if not user_id and stripe_subscription_id:
            existing_sub = await self.subscriptions_collection.find_one(
                {"stripe_subscription_id": stripe_subscription_id}, {"user_id": 1}
            )
            if existing_sub and existing_sub.get("user_id"):
                user_id = existing_sub["user_id"]
                logger.info(f"Resolved user_id from existing subscription: {user_id}")
        if not user_id and customer_id:
            cust_record = await mongo.db["stripe_customers"].find_one(
                {"stripe_customer_id": customer_id}, {"user_id": 1}
            )
            if cust_record and cust_record.get("user_id"):
                user_id = cust_record["user_id"]
                logger.info(f"Resolved user_id from stripe_customers: {user_id}")

        stripe_subscription_id = subscription.get("id")
        stripe_status = subscription.get("status")
        internal_status = self._map_stripe_status(stripe_status)

        trial_end = self._parse_timestamp(subscription.get("trial_end"))
        trial_start = self._parse_timestamp(subscription.get("trial_start"))

        # Stripe API v13+: current_period_start/end moved to subscription items.
        # Try top-level first (legacy/older API), then fall back to first item.
        current_period_start = self._parse_timestamp(
            subscription.get("current_period_start")
        )
        current_period_end = self._parse_timestamp(
            subscription.get("current_period_end")
        )

        if not current_period_start or not current_period_end:
            items_data = subscription.get("items", {})
            if isinstance(items_data, dict):
                items_list = items_data.get("data", [])
            elif hasattr(items_data, "data"):
                items_list = items_data.data or []
            else:
                items_list = []

            if items_list:
                first_item = (
                    items_list[0]
                    if isinstance(items_list[0], dict)
                    else (
                        items_list[0].to_dict()
                        if hasattr(items_list[0], "to_dict")
                        else {}
                    )
                )
                current_period_start = current_period_start or self._parse_timestamp(
                    first_item.get("current_period_start")
                )
                current_period_end = current_period_end or self._parse_timestamp(
                    first_item.get("current_period_end")
                )

        # Final fallback: use start_date or now
        if not current_period_start:
            current_period_start = (
                self._parse_timestamp(subscription.get("start_date")) or now
            )
        if not current_period_end:
            current_period_end = now

        # Cancel-at-period-end is a top-level Stripe sub field set by the
        # planner via the billing portal or our cancel endpoint. Without
        # syncing it, Mongo never learns the sub is scheduled to cancel —
        # the cancellation banner stays hidden, the renewal cron has no way
        # to skip the about-to-die sub, and the planner experience drifts
        # from Stripe's source of truth.
        cancel_at_period_end = bool(subscription.get("cancel_at_period_end"))
        canceled_at = self._parse_timestamp(subscription.get("canceled_at"))
        cancel_at = self._parse_timestamp(subscription.get("cancel_at"))

        subscription_updates: Dict[str, Any] = {
            "stripe_subscription_id": stripe_subscription_id,
            "stripe_customer_id": customer_id,
            "status": internal_status,
            "stripe_status": stripe_status,
            "trial_end_date": trial_end,
            "trial_start_date": trial_start,
            "current_period_start": current_period_start,
            "current_period_end": current_period_end,
            "cancel_at_period_end": cancel_at_period_end,
            "canceled_at": canceled_at,
            "cancel_at": cancel_at,
            "updated_at": now,
        }

        if plan_id:
            subscription_updates["plan_id"] = plan_id

        if extra_updates:
            subscription_updates.update(extra_updates)

        # Plan-snapshot grandfather rule — write once on first sync of a
        # subscription that has no snapshot yet, never re-write on later
        # webhook events. Closes the gap where `_handle_subscription_created`
        # (webhook path), Portal-initiated creates, and admin-assigned subs
        # created via the Stripe API never go through
        # `handle_checkout_session_completed` (which does write a snapshot at
        # stripe_service.py:1627-1644), so the row lands with
        # `plan_snapshot=None`.  Every feature gate that reads
        # `plan_snapshot` (feature_gates.py:182, subscription_service.py:669,
        # team_management_service.py:225) silently degrades to plan-catalog-
        # live values when the snapshot is missing, which breaks
        # grandfathering the first time a platform admin edits the plan's
        # limits.  Pins Q1 from docs/plans/SUBSCRIPTION_LIFECYCLE_TEST_PLAN.md
        # §6.
        if plan_id and "plan_snapshot" not in subscription_updates:
            snapshot_lookup_query: Dict[str, Any] = {}
            if stripe_subscription_id:
                snapshot_lookup_query["stripe_subscription_id"] = stripe_subscription_id
            elif user_id:
                snapshot_lookup_query["user_id"] = user_id

            existing_snapshot_doc = None
            if snapshot_lookup_query:
                existing_snapshot_doc = await self.subscriptions_collection.find_one(
                    snapshot_lookup_query, {"plan_snapshot": 1, "plan_id": 1}
                )

            # User-initiated plan change refresh: if the incoming plan_id
            # differs from what the subscription doc currently records, the
            # planner upgraded or downgraded their plan in Stripe — the
            # snapshot MUST refresh to the new plan's limits, otherwise the
            # cap-enforcement code would keep reading old values forever
            # (e.g., upgrade Boutique→Signature would still cap weddings at 3).
            #
            # The grandfather rule only protects against admin-initiated plan
            # *limit* changes (admin edits Boutique's max_weddings in the
            # plans collection): the plan_id stays the same, so the snapshot
            # is preserved. A plan_id change is a different event entirely.
            existing_plan_id = (
                existing_snapshot_doc.get("plan_id") if existing_snapshot_doc else None
            )
            plan_changed = existing_plan_id is not None and existing_plan_id != plan_id

            if (
                not existing_snapshot_doc
                or not existing_snapshot_doc.get("plan_snapshot")
                or plan_changed
            ):
                try:
                    plan = await self.plans_collection.find_one({"_id": plan_id})
                    if plan:
                        subscription_updates["plan_snapshot"] = {
                            "plan_name": plan.get("name"),
                            "max_weddings": plan.get("max_weddings", 1),
                            "max_guests_per_wedding": plan.get(
                                "max_guests_per_wedding", 100
                            ),
                            "ai_credits_monthly": plan.get("ai_credits_monthly", 10),
                            "storage_gb": plan.get("storage_gb", 1),
                            "staff_seats": plan.get("staff_seats", 0),
                            "features": plan.get("features", {}),
                            "price_monthly": plan.get("price_monthly", 0),
                            "price_yearly": plan.get("price_yearly"),
                            "stripe_price_id_monthly": plan.get(
                                "stripe_price_id_monthly"
                            ),
                            "stripe_price_id_yearly": plan.get(
                                "stripe_price_id_yearly"
                            ),
                            "snapshot_date": now,
                        }
                        reason = (
                            f"plan changed from {existing_plan_id} → {plan_id}"
                            if plan_changed
                            else "no existing snapshot found"
                        )
                        logger.info(
                            f"Built plan_snapshot for subscription "
                            f"{stripe_subscription_id or user_id} from plan "
                            f"{plan_id} ({reason})"
                        )
                except Exception as e:
                    # Do not fail the webhook sync if plan lookup errors —
                    # the subscription row still needs to be written.  The
                    # row will be missing plan_snapshot until a later event
                    # resyncs successfully.  Logged so this surfaces in ops.
                    logger.error(
                        f"Failed to build plan snapshot for plan {plan_id}: {e}"
                    )

        # Build query to find the existing subscription record.
        # Priority: match by stripe_subscription_id first (authoritative).
        # If no stripe_subscription_id, or no matching record exists yet,
        # fall back to user_id so we update the record created at checkout
        # initiation (which won't have a stripe_subscription_id yet).
        query: Dict[str, Any] = {}
        previous_status = None  # Track for reactivation detection
        if stripe_subscription_id and user_id:
            # Try stripe_subscription_id first; if no doc exists, fall back to user_id
            existing = await self.subscriptions_collection.find_one(
                {"stripe_subscription_id": stripe_subscription_id}
            )
            if existing:
                query["stripe_subscription_id"] = stripe_subscription_id
                previous_status = existing.get("status")
            else:
                # Fall back: find by user_id (pre-existing record from checkout init)
                query["user_id"] = user_id
                fallback_existing = await self.subscriptions_collection.find_one(
                    {"user_id": user_id}, {"status": 1}
                )
                if fallback_existing:
                    previous_status = fallback_existing.get("status")
        elif stripe_subscription_id:
            query["stripe_subscription_id"] = stripe_subscription_id
        elif user_id:
            query["user_id"] = user_id

        if not query:
            raise HTTPException(
                status_code=500,
                detail="Unable to associate Stripe subscription with local record",
            )

        update_document: Dict[str, Any] = {"$set": subscription_updates}

        # $setOnInsert must NOT overlap with $set — MongoDB rejects duplicate
        # field paths across update operators.  Only include fields that are
        # absent from subscription_updates.
        set_on_insert: Dict[str, Any] = {}

        if user_id and "user_id" not in subscription_updates:
            set_on_insert["user_id"] = user_id
        if plan_id and "plan_id" not in subscription_updates:
            set_on_insert["plan_id"] = plan_id
        if (
            stripe_subscription_id
            and "stripe_subscription_id" not in subscription_updates
        ):
            set_on_insert["stripe_subscription_id"] = stripe_subscription_id

        # Ensure required schema fields are populated on first insert
        if user_id and "user_email" not in subscription_updates:
            user_doc = await self.users_collection.find_one(
                {"_id": ObjectId(user_id)}, {"email": 1}
            )
            if user_doc:
                set_on_insert["user_email"] = user_doc["email"]
        if "start_date" not in subscription_updates:
            set_on_insert["start_date"] = now
        if "created_by" not in subscription_updates:
            set_on_insert["created_by"] = "system:stripe_webhook"

        if set_on_insert:
            update_document["$setOnInsert"] = set_on_insert

        # Build user update (if applicable) before starting the transaction
        user_update_doc = None
        if user_id:
            user_doc = await self.users_collection.find_one(
                {"_id": ObjectId(user_id)},
                {"registration_source": 1, "email_verified": 1},
            )
            is_public_signup = (
                user_doc.get("registration_source") == "public_signup"
                if user_doc
                else False
            )
            is_email_verified = (
                bool(user_doc.get("email_verified")) if user_doc else False
            )

            user_updates: Dict[str, Any] = {
                "subscription_status": internal_status,
                "updated_at": now,
            }

            if plan_id:
                user_updates["plan_id"] = plan_id
            if customer_id:
                user_updates["stripe_customer_id"] = customer_id
            if stripe_subscription_id:
                user_updates["stripe_subscription_id"] = stripe_subscription_id

            if internal_status == SubscriptionStatus.TRIAL.value:
                user_updates["trial_end_date"] = trial_end
                # Don't reset trial_warning_sent during trial - the trial cron job manages it
            else:
                user_updates["trial_end_date"] = None
                # Reset flag only when leaving trial state
                user_updates["trial_warning_sent"] = False

            unset_fields: Dict[str, Any] = {}

            # Stripe can establish billing state, but it should not act as email
            # verification for public signups. Keep those accounts blocked until
            # the verification link is used, while still removing the pending
            # signup TTL so a paid account is not reaped.
            if internal_status in (
                SubscriptionStatus.ACTIVE.value,
                SubscriptionStatus.TRIAL.value,
            ):
                if not is_public_signup or is_email_verified:
                    user_updates["is_active"] = True
                unset_fields["pending_expires_at"] = ""

            user_update_doc = {"$set": user_updates}
            if unset_fields:
                user_update_doc["$unset"] = unset_fields

        # Execute both writes in a single transaction so subscriptions and
        # users collections stay consistent.  Falls back to sequential writes
        # if the MongoDB deployment doesn't support transactions (standalone).
        try:
            async with await mongo.client.start_session() as session:
                async with session.start_transaction():
                    await self.subscriptions_collection.update_one(
                        query, update_document, upsert=True, session=session
                    )
                    if user_id and user_update_doc:
                        await self.users_collection.update_one(
                            {"_id": ObjectId(user_id)},
                            user_update_doc,
                            session=session,
                        )
        except Exception as txn_err:
            # Standalone MongoDB (no replica set) doesn't support transactions.
            # Fall back to sequential writes with a warning.
            if (
                "transaction" in str(txn_err).lower()
                or "replica" in str(txn_err).lower()
                or "topology" in str(txn_err).lower()
            ):
                logger.warning(
                    "MongoDB transactions not supported (standalone mode). "
                    "Falling back to sequential writes for subscription sync."
                )
                sub_result = await self.subscriptions_collection.update_one(
                    query, update_document, upsert=True
                )
                logger.info(
                    f"Subscription upsert (fallback): query={query}, "
                    f"matched={sub_result.matched_count}, modified={sub_result.modified_count}, "
                    f"upserted_id={sub_result.upserted_id}"
                )
                if user_id and user_update_doc:
                    user_result = await self.users_collection.update_one(
                        {"_id": ObjectId(user_id)},
                        user_update_doc,
                    )
                    logger.info(
                        f"User update (fallback): user_id={user_id}, "
                        f"matched={user_result.matched_count}, modified={user_result.modified_count}"
                    )
            else:
                logger.error(
                    f"Unexpected error in subscription sync transaction: {str(txn_err)}"
                )
                raise

        # ── Auth cache invalidation ─────────────────────────────────
        # Subscription state just changed in Mongo.  Bust the cached
        # ExtendedAuthUser snapshot for this user so the next request
        # rebuilds from the fresh subscription record instead of
        # serving the stale "blocked / not blocked" flag from the cache.
        # The 10-second TTL would catch up eventually; this makes the
        # transition immediate from the user's perspective.
        if user_id:
            try:
                from app.dependencies.auth_extended import (
                    invalidate_auth_cache_by_user_id,
                )

                await invalidate_auth_cache_by_user_id(user_id)
            except Exception as cache_err:
                logger.debug(
                    f"Auth cache invalidation skipped for user {user_id}: {cache_err}"
                )

        # ── Reactivation detection ──────────────────────────────────
        # If the subscription transitioned FROM a cancelled/blocked state
        # TO active or trial, trigger reactivation cleanup to undo the
        # suspension that was applied during cancellation.
        CANCELLED_STATUSES = {
            SubscriptionStatus.CANCELLED.value,
            SubscriptionStatus.EXPIRED.value,
        }
        ACTIVE_STATUSES = {
            SubscriptionStatus.ACTIVE.value,
            SubscriptionStatus.TRIAL.value,
        }
        if (
            previous_status in CANCELLED_STATUSES
            and internal_status in ACTIVE_STATUSES
            and user_id
        ):
            logger.info(
                "Subscription reactivation detected for user %s: %s → %s. "
                "Triggering reactivation cleanup.",
                user_id,
                previous_status,
                internal_status,
            )
            try:
                await self._handle_reactivation_cleanup(user_id)
            except Exception as reactivation_err:
                # Fire-and-forget: don't block the sync on reactivation failure
                logger.error(
                    "Reactivation cleanup failed for user %s: %s",
                    user_id,
                    str(reactivation_err),
                )

        return {
            "status": internal_status,
            "stripe_status": stripe_status,
            "trial_end": trial_end,
            "user_id": user_id,
            "stripe_subscription_id": stripe_subscription_id,
        }

    async def _handle_reactivation_cleanup(self, user_id: str) -> None:
        """
        Undo the suspension applied during cancellation.

        Phases (fire-and-forget per phase):
          1. Reactivate team members
          2. Restore couple portal access previously blocked by owner cancellation
          3. Unsuspend planner data (weddings, packages, contracts)
          4. Resume paused payment links & scheduled payments
          5. Clear cancellation_cleanup_completed flag on subscription

        Each phase is wrapped in try/except so a single failure
        does not prevent the remaining phases from executing.
        """
        # Atomic guard: prevent duplicate reactivation runs from concurrent
        # webhooks (e.g. subscription.updated + checkout.session.completed).
        try:
            claim = await self.subscriptions_collection.find_one_and_update(
                {
                    "user_id": user_id,
                    "cancellation_cleanup_completed": True,
                },
                {
                    "$set": {
                        "reactivation_cleanup_in_progress": True,
                        "reactivation_cleanup_started_at": datetime.now(timezone.utc),
                    }
                },
                return_document=False,
            )
            if claim is None:
                logger.info(
                    "[Reactivation] No cancelled subscription with cleanup flag for user %s, "
                    "skipping (already reactivated or never cancelled)",
                    user_id,
                )
                return
        except Exception as e:
            logger.warning(
                "[Reactivation] Could not claim reactivation for user %s: %s",
                user_id,
                str(e),
            )
            # Proceed anyway — duplicate reactivation is less harmful than skipped reactivation

        user = await self.users_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            logger.warning(
                "[Reactivation] User %s not found, skipping cleanup", user_id
            )
            return

        user_email = user.get("email", "")

        lifecycle_result = (
            await planner_access_lifecycle_service.restore_planner_access(
                planner_id=user_id,
                planner_email=user_email,
            )
        )
        if lifecycle_result.get("errors"):
            logger.error(
                "[Reactivation] Planner access restore completed with errors for user %s: %s",
                user_id,
                lifecycle_result["errors"],
            )
        else:
            logger.info(
                "[Reactivation] Planner access restore completed for user %s: %s",
                user_id,
                lifecycle_result,
            )

        # Phase 5: Clear the cancellation and reactivation-in-progress flags
        try:
            await self.subscriptions_collection.update_many(
                {"user_id": user_id},
                {
                    "$unset": {
                        "cancellation_cleanup_completed": "",
                        "cancellation_cleanup_at": "",
                        "reactivation_cleanup_in_progress": "",
                        "reactivation_cleanup_started_at": "",
                    },
                    "$set": {
                        "reactivation_cleanup_completed_at": datetime.now(timezone.utc),
                    },
                },
            )
            logger.info(
                "[Reactivation] Phase 4 complete: cleared cancellation flags for user %s",
                user_id,
            )
        except Exception as e:
            logger.error(
                "[Reactivation] Phase 4 (clear flags) failed for user %s: %s",
                user_id,
                str(e),
            )

        logger.info("[Reactivation] All phases complete for user %s", user_id)

    # ==================== SUBSCRIPTION MODIFICATIONS ====================

    async def change_subscription_billing_interval(
        self,
        user_id: str,
        new_billing_interval: str,  # "monthly" or "yearly"
    ) -> Dict[str, Any]:
        """
        Change a user's subscription billing interval (monthly <-> yearly).

        Uses Stripe's subscription modification with proration.

        Args:
            user_id: Internal user ID
            new_billing_interval: Target interval - "monthly" or "yearly"

        Returns:
            Dictionary with update result and proration details
        """
        self._ensure_stripe_enabled()

        if new_billing_interval not in ("monthly", "yearly"):
            raise HTTPException(
                status_code=400, detail="Billing interval must be 'monthly' or 'yearly'"
            )

        try:
            # Get current subscription
            subscription = await self.subscriptions_collection.find_one(
                {"user_id": user_id, "status": {"$in": ["active", "trial"]}}
            )

            if not subscription:
                raise HTTPException(
                    status_code=404, detail="No active subscription found"
                )

            stripe_subscription_id = subscription.get("stripe_subscription_id")
            if not stripe_subscription_id:
                raise HTTPException(
                    status_code=400, detail="Subscription not linked to Stripe"
                )

            current_interval = subscription.get("billing_interval", "monthly")
            if current_interval == new_billing_interval:
                raise HTTPException(
                    status_code=400, detail=f"Already on {new_billing_interval} billing"
                )

            # Get the plan to find the new price ID
            plan_id = subscription.get("plan_id")
            plan = await self.plans_collection.find_one({"_id": plan_id})
            if not plan:
                raise HTTPException(
                    status_code=404, detail="Subscription plan not found"
                )

            # Get the new price ID (field format: stripe_price_id_monthly / stripe_price_id_yearly)
            new_price_field = f"stripe_price_id_{new_billing_interval}"
            new_price_id = plan.get(new_price_field)

            if not new_price_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"No {new_billing_interval} pricing available for this plan",
                )

            # Retrieve current Stripe subscription to get item ID
            stripe_sub = stripe.Subscription.retrieve(stripe_subscription_id)

            if not stripe_sub.get("items") or not stripe_sub["items"].get("data"):
                raise HTTPException(
                    status_code=500, detail="Unable to retrieve subscription items"
                )

            subscription_item_id = stripe_sub["items"]["data"][0]["id"]

            # Modify the subscription with proration
            # proration_behavior: 'create_prorations' applies credit/charge for unused time
            updated_stripe_sub = stripe.Subscription.modify(
                stripe_subscription_id,
                items=[
                    {
                        "id": subscription_item_id,
                        "price": new_price_id,
                    }
                ],
                proration_behavior="create_prorations",
                metadata={
                    "billing_interval": new_billing_interval,
                    "changed_from": current_interval,
                    "changed_at": datetime.now(timezone.utc).isoformat(),
                },
            )

            # Use Stripe's actual period dates instead of naive calculation
            now = datetime.now(timezone.utc)
            period_end = datetime.fromtimestamp(
                updated_stripe_sub["current_period_end"], tz=timezone.utc
            )
            period_start = datetime.fromtimestamp(
                updated_stripe_sub["current_period_start"], tz=timezone.utc
            )

            # Update local subscription record
            await self.subscriptions_collection.update_one(
                {"_id": subscription["_id"]},
                {
                    "$set": {
                        "billing_interval": new_billing_interval,
                        "current_period_start": period_start,
                        "current_period_end": period_end,
                        "updated_at": now,
                    }
                },
            )

            logger.info(
                f"Changed subscription billing for user {user_id}: "
                f"{current_interval} -> {new_billing_interval}"
            )

            return {
                "success": True,
                "previous_interval": current_interval,
                "new_interval": new_billing_interval,
                "stripe_subscription_id": stripe_subscription_id,
                "new_period_end": period_end.isoformat(),
                "proration_applied": True,
            }

        except StripeError as e:
            logger.error(f"Stripe error changing billing interval: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Payment service error: {str(e)}"
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error changing billing interval: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to change billing interval: {str(e)}"
            )

    # ==================== CUSTOMER PORTAL ====================

    async def create_portal_session(
        self,
        user_id: str,
        return_url: Optional[str] = None,
        flow_type: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Create a Stripe Customer Portal session for subscription management

        Args:
            user_id: Internal user ID
            return_url: URL to return to after portal session
            flow_type: Optional flow type - 'payment_method_update' or 'subscription_update'

        Returns:
            Dictionary with portal session URL
        """
        self._ensure_stripe_enabled()

        try:
            # Get Stripe customer ID
            customer_record = await self.stripe_customers_collection.find_one(
                {"user_id": user_id}
            )
            if not customer_record or not customer_record.get("stripe_customer_id"):
                raise HTTPException(status_code=404, detail="Stripe customer not found")

            customer_id = customer_record["stripe_customer_id"]

            # Default return URL if not provided
            if not return_url:
                return_url = f"{settings.frontend_url}/admin/billing"

            # Build portal session params
            portal_params = {
                "customer": customer_id,
                "return_url": return_url,
            }

            # Add flow_data for specific flows
            if flow_type == "payment_method_update":
                portal_params["flow_data"] = {"type": "payment_method_update"}
            elif flow_type == "subscription_update":
                # Get the current subscription to specify which one to update
                subscription = await self.subscriptions_collection.find_one(
                    {"user_id": user_id}
                )
                if subscription and subscription.get("stripe_subscription_id"):
                    portal_params["flow_data"] = {
                        "type": "subscription_update",
                        "subscription_update": {
                            "subscription": subscription["stripe_subscription_id"]
                        },
                    }
            elif flow_type == "subscription_cancel":
                # Direct to subscription cancellation flow
                subscription = await self.subscriptions_collection.find_one(
                    {"user_id": user_id}
                )
                if subscription and subscription.get("stripe_subscription_id"):
                    portal_params["flow_data"] = {
                        "type": "subscription_cancel",
                        "subscription_cancel": {
                            "subscription": subscription["stripe_subscription_id"]
                        },
                    }

            # Create portal session
            portal_session = stripe.billing_portal.Session.create(**portal_params)

            logger.info(
                f"Created portal session for user {user_id} with flow_type={flow_type}"
            )

            return {"url": portal_session.url}

        except StripeError as e:
            logger.error(f"Stripe error creating portal session: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Payment service error: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Error creating portal session: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error creating portal session: {str(e)}"
            )

    # ==================== WEBHOOK HANDLING ====================

    async def handle_webhook_event(
        self, payload: bytes, signature: str
    ) -> Dict[str, Any]:
        """
        Handle Stripe webhook events

        Args:
            payload: Raw webhook payload
            signature: Stripe signature header

        Returns:
            Dictionary with processing result
        """
        self._ensure_stripe_enabled()

        if not settings.stripe_webhook_secret:
            logger.error("Webhook secret not configured")
            raise HTTPException(status_code=500, detail="Webhook configuration error")

        event_type = "unknown"
        try:
            # Verify webhook signature
            event_obj = stripe.Webhook.construct_event(
                payload, signature, settings.stripe_webhook_secret
            )

            # `stripe.Webhook.construct_event` returns a `stripe.Event`
            # (a StripeObject), not a plain dict. Recent versions of the
            # Stripe Python SDK override `__getattr__` to look up attribute
            # access as dict keys on the underlying event payload — which
            # means calling `event.get("id", "")` tries to read a "get" KEY
            # from the event and raises `AttributeError: get` when there
            # isn't one. Every downstream `.get(...)` call on the
            # subscription / customer / invoice payload hits the same trap.
            #
            # Convert to a plain dict at the boundary so every handler in
            # this service can use dict semantics safely. `to_dict()` is
            # recursive — nested StripeObjects in `event["data"]["object"]`
            # become plain dicts too.
            if hasattr(event_obj, "to_dict"):
                event = event_obj.to_dict()
            else:
                # Already a dict in older SDK versions.
                event = dict(event_obj)

            event_type = event["type"]
            event_id = str(event.get("id") or "")
            data = event["data"]["object"]

            # ── Idempotency check with status tracking ──────────────────
            # Best practice: track event processing lifecycle so failed events
            # can be debugged and retried.  Only skip events already marked
            # "processed"; events stuck in "processing" (previous crash) are
            # allowed to re-enter so Stripe retries succeed.
            # Ref: https://dev.to/aniefon_umanah_ac5f21311c/building-reliable-stripe-subscriptions-in-nestjs-webhook-idempotency-and-optimistic-locking-3o91
            if event_id:
                existing = await mongo.db["stripe_webhook_events"].find_one(
                    {"event_id": event_id}
                )
                if existing and existing.get("status") == "processed":
                    logger.info(
                        f"Skipping duplicate webhook event: {event_id} ({event_type})"
                    )
                    return {
                        "status": "already_processed",
                        "event_id": event_id,
                        "event_type": event_type,
                    }

                # Legacy events (pre-status-tracking) have no "status" field.
                # Treat them as already processed to maintain backward compat.
                if existing and "status" not in existing:
                    logger.info(
                        f"Skipping legacy webhook event (no status field): {event_id} ({event_type})"
                    )
                    return {
                        "status": "already_processed",
                        "event_id": event_id,
                        "event_type": event_type,
                    }

                if not existing:
                    # Record event as being processed (with status lifecycle).
                    # Use try/except for DuplicateKeyError to handle the race
                    # condition where two identical webhooks arrive simultaneously
                    # and both pass the find_one check above.
                    try:
                        await mongo.db["stripe_webhook_events"].insert_one(
                            {
                                "event_id": event_id,
                                "event_type": event_type,
                                "status": "processing",
                                "error_message": None,
                                "created_at": datetime.now(timezone.utc),
                                "processed_at": None,
                            }
                        )
                    except DuplicateKeyError:
                        # Another concurrent request already claimed this event
                        logger.info(
                            f"Concurrent duplicate insert for event {event_id}, skipping"
                        )
                        return {
                            "status": "already_processed",
                            "event_id": event_id,
                            "event_type": event_type,
                        }
                else:
                    # Re-processing a previously failed/stuck event
                    await mongo.db["stripe_webhook_events"].update_one(
                        {"event_id": event_id},
                        {"$set": {"status": "processing", "error_message": None}},
                    )

            logger.info(f"Processing webhook event: {event_type}")

            # ── Dispatch to handler with status lifecycle tracking ────
            # On success → mark "processed"; on failure → mark "failed"
            # with error message for debugging / manual retry.
            result = None
            try:
                # Handle different event types
                if event_type == "checkout.session.completed":
                    result = await self._handle_checkout_completed(data)
                elif event_type == "checkout.session.expired":
                    result = await self._handle_checkout_expired(data)
                elif event_type == "customer.subscription.created":
                    result = await self._handle_subscription_created(data)
                elif event_type == "customer.subscription.updated":
                    result = await self._handle_subscription_updated(data)
                elif event_type == "customer.subscription.deleted":
                    result = await self._handle_subscription_deleted(data)
                elif event_type == "customer.subscription.trial_will_end":
                    result = await self._handle_subscription_trial_will_end(data)
                elif event_type == "customer.updated":
                    result = await self._handle_customer_updated(data)
                elif event_type == "invoice.paid":
                    result = await self._handle_invoice_paid(data)
                elif event_type == "invoice.payment_failed":
                    result = await self._handle_invoice_payment_failed(data)
                elif event_type == "invoice.finalized":
                    result = await self._handle_invoice_finalized(data)
                elif event_type == "payment_intent.succeeded":
                    result = await self._handle_payment_intent_succeeded(data)
                elif event_type == "payment_intent.payment_failed":
                    result = await self._handle_payment_intent_failed(data)
                elif event_type == "account.updated":
                    result = await self._handle_account_updated(data)
                elif event_type in ("product.updated", "product.created"):
                    result = await self._handle_product_updated(data)
                elif event_type in ("price.created", "price.updated"):
                    result = await self._handle_price_changed(data)
                elif event_type in ("plan.created", "plan.updated"):
                    # Legacy Stripe plan events map to price/product - acknowledge them
                    logger.info(
                        f"Acknowledged legacy plan event: {event_type} for {data.get('id')}"
                    )
                    result = {"status": "acknowledged", "event_type": event_type}
                else:
                    logger.info(f"Unhandled event type: {event_type}")
                    result = {"status": "ignored", "event_type": event_type}

            except Exception as handler_err:
                # ── Mark event as failed with error detail ────────────
                if event_id:
                    try:
                        await mongo.db["stripe_webhook_events"].update_one(
                            {"event_id": event_id},
                            {
                                "$set": {
                                    "status": "failed",
                                    "error_message": str(handler_err)[:2000],
                                }
                            },
                        )
                    except Exception as update_err:
                        logger.error(
                            f"Failed to mark event {event_id} as failed: {update_err}"
                        )
                raise

            # ── Mark event as successfully processed ──────────────
            # Placed OUTSIDE the handler try/except so a failure here
            # does not get conflated with a handler failure.
            if event_id:
                try:
                    await mongo.db["stripe_webhook_events"].update_one(
                        {"event_id": event_id},
                        {
                            "$set": {
                                "status": "processed",
                                "processed_at": datetime.now(timezone.utc),
                            }
                        },
                    )
                except Exception as update_err:
                    # Handler succeeded — don't crash on status bookkeeping failure
                    logger.error(
                        f"Failed to mark event {event_id} as processed: {update_err}"
                    )

            return result

        except SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid signature")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                f"Error processing webhook event {event_type}: {str(e)}", exc_info=True
            )
            raise HTTPException(
                status_code=500, detail=f"Webhook processing error: {str(e)}"
            )

    async def _handle_checkout_completed(
        self, session: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle successful checkout session completion"""
        user_id = session.get("metadata", {}).get("user_id")
        plan_id = session.get("metadata", {}).get("plan_id")
        subscription_id = session.get("subscription")

        # Fallback: if checkout session metadata is empty, retrieve from
        # the Stripe subscription metadata (which is always populated).
        if (not user_id or not plan_id) and subscription_id:
            try:
                sub_obj = stripe.Subscription.retrieve(subscription_id)
                sub_meta = (
                    sub_obj.get("metadata", {})
                    if isinstance(sub_obj, dict)
                    else dict(getattr(sub_obj, "metadata", {}))
                )
                user_id = user_id or sub_meta.get("user_id")
                plan_id = plan_id or sub_meta.get("plan_id")
                logger.info(
                    f"Retrieved metadata from subscription: user_id={user_id}, plan_id={plan_id}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to retrieve subscription metadata fallback: {str(e)}"
                )

        if not user_id or not plan_id:
            logger.error("Missing metadata in checkout session and subscription")
            return {
                "status": "error",
                "message": "Missing user_id or plan_id metadata in checkout session",
            }

        # Verify user still exists before syncing subscription
        try:
            user_exists = await self.users_collection.find_one(
                {"_id": ObjectId(user_id)}, {"_id": 1}
            )
            if not user_exists:
                logger.error(
                    f"User {user_id} not found during checkout completion — may have been deleted"
                )
                return {"status": "error", "message": f"User {user_id} not found"}
        except Exception as e:
            logger.error(f"Error verifying user {user_id}: {str(e)}")
            return {"status": "error", "message": f"Error verifying user: {str(e)}"}

        subscription: Optional[Dict[str, Any]] = None

        if subscription_id:
            try:
                subscription = stripe.Subscription.retrieve(subscription_id)
            except StripeError as e:
                logger.error(
                    f"Unable to retrieve subscription {subscription_id}: {str(e)}"
                )

        # Build plan snapshot for grandfathering before syncing
        plan_snapshot = None
        try:
            plan = await self.plans_collection.find_one({"_id": plan_id})
            if plan:
                plan_snapshot = {
                    "plan_name": plan.get("name"),
                    "max_weddings": plan.get("max_weddings", 1),
                    "max_guests_per_wedding": plan.get("max_guests_per_wedding", 100),
                    "ai_credits_monthly": plan.get("ai_credits_monthly", 10),
                    "storage_gb": plan.get("storage_gb", 1),
                    "staff_seats": plan.get("staff_seats", 0),
                    "features": plan.get("features", {}),
                    "price_monthly": plan.get("price_monthly", 0),
                    "price_yearly": plan.get("price_yearly"),
                    "stripe_price_id_monthly": plan.get("stripe_price_id_monthly"),
                    "stripe_price_id_yearly": plan.get("stripe_price_id_yearly"),
                    "snapshot_date": datetime.now(timezone.utc),
                }
        except Exception as e:
            logger.error(f"Failed to build plan snapshot for plan {plan_id}: {str(e)}")

        extra_updates = {
            "stripe_subscription_id": subscription_id,
            "payment_status": session.get("payment_status"),
            "stripe_checkout_session_id": session.get("id"),
            "stripe_checkout_completed_at": datetime.now(timezone.utc),
        }
        if plan_snapshot:
            extra_updates["plan_snapshot"] = plan_snapshot

        sync_result = await self._sync_subscription_state(
            user_id=user_id,
            subscription=subscription,
            customer_id=session.get("customer"),
            plan_id=plan_id,
            extra_updates=extra_updates,
        )

        # Initialize usage tracking for the new subscription
        try:
            from app.services.subscription_service import SubscriptionService

            sub_service = SubscriptionService()
            local_sub = await self.subscriptions_collection.find_one(
                {
                    "user_id": user_id,
                    "stripe_subscription_id": subscription_id,
                }
            )
            if local_sub:
                await sub_service.initialize_usage_tracking(user_id, local_sub["_id"])
                logger.info(f"Initialized usage tracking for user {user_id}")
        except Exception as e:
            logger.error(
                f"Failed to initialize usage tracking for user {user_id}: {str(e)}"
            )

        try:
            await self._send_checkout_completion_notification(
                user_id=user_id,
                plan_id=plan_id,
                session=session,
                subscription=subscription,
            )
        except Exception as e:
            logger.error(
                f"Failed to send checkout completion notification for user {user_id}: {str(e)}"
            )

        logger.info(
            "Checkout completed for user %s, subscription %s (status: %s)",
            user_id,
            subscription_id,
            sync_result.get("stripe_status") or sync_result.get("status"),
        )
        return {
            "status": "success",
            "user_id": user_id,
            "subscription_id": subscription_id,
        }

    async def _handle_subscription_created(
        self, subscription: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle new subscription creation"""
        result = await self._sync_subscription_state(
            user_id=subscription.get("metadata", {}).get("user_id"),
            subscription=subscription,
            customer_id=subscription.get("customer"),
        )

        logger.info(
            "Subscription %s created (user=%s, status=%s)",
            subscription.get("id"),
            result.get("user_id"),
            result.get("stripe_status") or result.get("status"),
        )
        return {"status": "success", "user_id": result.get("user_id")}

    async def _handle_subscription_updated(
        self, subscription: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle subscription updates"""
        result = await self._sync_subscription_state(
            user_id=subscription.get("metadata", {}).get("user_id"),
            subscription=subscription,
            customer_id=subscription.get("customer"),
        )

        logger.info(
            "Subscription %s updated (status=%s)",
            subscription.get("id"),
            result.get("stripe_status") or result.get("status"),
        )
        return {"status": "success", "subscription_id": subscription.get("id")}

    async def _handle_subscription_deleted(
        self, subscription: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle subscription cancellation/deletion with cleanup orchestration"""
        stripe_sub_id = subscription["id"]
        now = datetime.now(timezone.utc)

        # Sync subscription state first
        result = await self._sync_subscription_state(
            user_id=subscription.get("metadata", {}).get("user_id"),
            subscription=subscription,
            customer_id=subscription.get("customer"),
            extra_updates={
                "status": SubscriptionStatus.CANCELLED.value,
                "cancelled_at": now,
            },
        )

        user_id = result.get("user_id")
        logger.info("Subscription %s cancelled (user=%s)", stripe_sub_id, user_id)

        # Atomic guard: claim cleanup ownership using findOneAndUpdate.
        # This prevents a race where two concurrent webhooks both pass a
        # non-atomic check-then-act and run cleanup in parallel (Stripe
        # best practice: webhook event ordering is not guaranteed).
        try:
            claim_result = await self.subscriptions_collection.find_one_and_update(
                {
                    "stripe_subscription_id": stripe_sub_id,
                    "cancellation_cleanup_completed": {"$ne": True},
                },
                {
                    "$set": {
                        "cancellation_cleanup_completed": True,
                        "cancellation_cleanup_at": now,
                    }
                },
                return_document=False,  # return the ORIGINAL (pre-update) document
            )
            if claim_result is None:
                # Either the doc doesn't exist or it was already claimed
                logger.info(
                    f"Cleanup already performed for subscription {stripe_sub_id}, skipping"
                )
                return {"status": "success", "subscription_id": stripe_sub_id}
        except Exception as e:
            logger.warning(
                f"Failed to claim cleanup for subscription {stripe_sub_id}: {str(e)}"
            )
            # If we can't claim, err on the side of running cleanup
            # (duplicate cleanup is less harmful than skipped cleanup)

        # If we don't have user_id, we can't proceed with cleanup
        if not user_id:
            logger.warning(
                f"No user_id found for subscription {stripe_sub_id}, skipping cleanup"
            )
            return {"status": "success", "subscription_id": stripe_sub_id}

        # Fetch user document for email and other data
        try:
            user = await self.users_collection.find_one(
                {"_id": to_object_id(user_id, "user_id")}
            )
            if not user:
                logger.warning(
                    f"User {user_id} not found for subscription {stripe_sub_id}, skipping cleanup"
                )
                return {"status": "success", "subscription_id": stripe_sub_id}
            user_email = user.get("email", "")
        except Exception as e:
            logger.warning(f"Failed to fetch user {user_id}: {str(e)}")
            return {"status": "success", "subscription_id": stripe_sub_id}

        lifecycle_result = (
            await planner_access_lifecycle_service.suspend_planner_access(
                planner_id=user_id,
                planner_email=user_email,
                team_reason="webhook_subscription_cancelled",
            )
        )
        if lifecycle_result.get("errors"):
            logger.warning(
                "Planner access suspension completed with errors for user %s: %s",
                user_id,
                lifecycle_result["errors"],
            )
        else:
            logger.info(
                "Planner access suspension completed for user %s: %s",
                user_id,
                lifecycle_result,
            )

        # Phase 5: Send cancellation email to planner
        try:
            from app.services.email_service_resend import ResendEmailService

            email_service = ResendEmailService()
            email_sent = await email_service.send_subscription_cancelled_email(user)
            logger.info(f"Sent cancellation email to user {user_id}: {email_sent}")
        except Exception as e:
            logger.warning(
                f"Failed to send cancellation email to user {user_id}: {str(e)}"
            )

        # Phase 6: Notify affected couples
        try:
            from app.services.email_service_resend import ResendEmailService

            couple_users_collection = mongo.db["couple_users"]
            weddings_query = build_wedding_owner_query(user_id, user_email)
            wedding_ids = []
            if weddings_query:
                planner_weddings = await self.weddings_collection.find(
                    weddings_query,
                    {"_id": 1},
                ).to_list(length=10000)
                wedding_ids = [str(wedding["_id"]) for wedding in planner_weddings]

            couples = []
            if wedding_ids:
                couples = await couple_users_collection.find(
                    {
                        "wedding_id": {"$in": wedding_ids},
                        "setup_completed": True,
                    }
                ).to_list(length=10000)

            if couples:
                email_service = ResendEmailService()

                # Build wedding lookup map for notification template
                wedding_ids = list(
                    {c.get("wedding_id") for c in couples if c.get("wedding_id")}
                )
                weddings_list = await self.weddings_collection.find(
                    {
                        "_id": {
                            "$in": [
                                normalize_query_id(wedding_id)
                                for wedding_id in wedding_ids
                            ]
                        }
                    }
                ).to_list(length=10000)
                weddings_map = {str(w["_id"]): w for w in weddings_list}

                for couple in couples:
                    if (
                        couple_lifecycle_service.infer_stored_state(couple)
                        == COUPLE_PORTAL_STATE_REVOKED
                    ):
                        continue
                    try:
                        wedding = weddings_map.get(couple.get("wedding_id"), {})
                        couple_notification_sent = await email_service.send_planner_cancelled_couple_notification(
                            couple=couple, planner=user, wedding=wedding
                        )
                        if couple_notification_sent:
                            logger.info(
                                f"Notified couple {couple.get('email')} about planner {user_id} cancellation"
                            )
                    except Exception as e:
                        logger.warning(
                            f"Failed to notify couple {couple.get('email')} for wedding {couple.get('wedding_id')}: {str(e)}"
                        )

                logger.info(f"Completed couple notifications for planner {user_id}")
        except Exception as e:
            logger.warning(f"Failed to notify couples for user {user_id}: {str(e)}")

        # Note: cancellation_cleanup_completed flag was already set atomically
        # at the top of this method by the find_one_and_update guard.
        logger.info(f"Cancellation cleanup complete for subscription {stripe_sub_id}")

        return {"status": "success", "subscription_id": stripe_sub_id}

    async def _handle_subscription_trial_will_end(
        self, subscription: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Record trial end reminders for alignment with internal notifications."""
        result = await self._sync_subscription_state(
            user_id=subscription.get("metadata", {}).get("user_id"),
            subscription=subscription,
            customer_id=subscription.get("customer"),
            extra_updates={"trial_will_end_notified_at": datetime.now(timezone.utc)},
        )

        logger.info(
            "Trial will end soon for subscription %s (user=%s)",
            subscription.get("id"),
            result.get("user_id"),
        )
        return {"status": "success", "subscription_id": subscription.get("id")}

    async def _handle_customer_updated(
        self, customer: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle customer.updated - sync email/name changes from Stripe back to our DB."""
        try:
            customer_id = customer.get("id")
            if not customer_id:
                return {"status": "ignored", "reason": "no customer_id"}

            new_email = customer.get("email")
            new_name = customer.get("name")

            # Update our stripe_customers mapping
            update_fields: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}
            if new_email:
                update_fields["email"] = new_email
            if new_name:
                update_fields["name"] = new_name

            result = await self.stripe_customers_collection.update_one(
                {"stripe_customer_id": customer_id}, {"$set": update_fields}
            )

            if result.modified_count > 0:
                logger.info(
                    f"Customer {customer_id} details synced (email={new_email})"
                )
            else:
                logger.debug(f"No local record found for Stripe customer {customer_id}")

            return {"status": "success", "customer_id": customer_id}

        except Exception as e:
            logger.error(f"Error handling customer.updated: {str(e)}")
            raise

    async def _handle_product_updated(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Handle product.updated/product.created - sync product changes to local plans."""
        try:
            product_id = product.get("id")
            if not product_id:
                return {"status": "ignored", "reason": "no product_id"}

            plan_id = product.get("metadata", {}).get("plan_id")
            is_active = product.get("active", True)

            if plan_id:
                # Update local plan's active status to match Stripe
                result = await self.plans_collection.update_one(
                    {"_id": plan_id, "stripe_product_id": product_id},
                    {
                        "$set": {
                            "is_active": is_active,
                            "updated_at": datetime.now(timezone.utc),
                        }
                    },
                )
                if result.modified_count > 0:
                    logger.info(
                        f"Plan {plan_id} synced from Stripe product {product_id} (active={is_active})"
                    )
            else:
                logger.debug(
                    f"Product {product_id} has no plan_id metadata, skipping local sync"
                )

            return {"status": "success", "product_id": product_id}

        except Exception as e:
            logger.error(f"Error handling product.updated: {str(e)}")
            raise

    async def _handle_price_changed(self, price: Dict[str, Any]) -> Dict[str, Any]:
        """Handle price.created/price.updated - log price changes for audit trail."""
        try:
            price_id = price.get("id")
            product_id = price.get("product")
            is_active = price.get("active", True)

            if not price_id:
                return {"status": "ignored", "reason": "no price_id"}

            logger.info(
                f"Price {price_id} changed: product={product_id}, "
                f"active={is_active}, amount={price.get('unit_amount')}"
            )

            return {"status": "acknowledged", "price_id": price_id}

        except Exception as e:
            logger.error(f"Error handling price event: {str(e)}")
            raise

    async def _handle_checkout_expired(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """Handle expired checkout session - clean up pending subscription records
        and optionally delete orphaned Stripe customers who never completed payment."""
        session_id = session.get("id")
        user_id = session.get("metadata", {}).get("user_id")
        customer_id = session.get("customer")

        logger.info(f"Checkout session expired: {session_id} for user {user_id}")

        # Clean up any pending subscription record tied to this checkout session
        if session_id:
            result = await self.subscriptions_collection.update_one(
                {
                    "stripe_checkout_session_id": session_id,
                    "status": {
                        "$in": [
                            "pending",
                            "pending_payment",
                            SubscriptionStatus.PENDING_CHECKOUT.value,
                        ]
                    },
                },
                {
                    "$set": {
                        "status": SubscriptionStatus.EXPIRED.value,
                        "updated_at": datetime.now(timezone.utc),
                        "expired_reason": "checkout_session_expired",
                    }
                },
            )
            if result.modified_count > 0:
                logger.info(
                    f"Marked pending subscription as expired for session {session_id}"
                )

        # Sync user status to "expired" to match subscription record
        if user_id:
            user = await self.users_collection.find_one({"_id": ObjectId(user_id)})
            if user and normalize_subscription_status(
                user.get("subscription_status")
            ) in (
                SubscriptionStatus.PENDING_PAYMENT.value,
                SubscriptionStatus.PENDING_CHECKOUT.value,
                "pending",
            ):
                await self.users_collection.update_one(
                    {"_id": ObjectId(user_id)},
                    {
                        "$set": {
                            "subscription_status": SubscriptionStatus.EXPIRED.value,
                            "checkout_expired_at": datetime.now(timezone.utc),
                            "updated_at": datetime.now(timezone.utc),
                        }
                    },
                )

        # Check if this Stripe customer has any active subscriptions
        # If not, they're orphaned and should be cleaned up
        if customer_id:
            try:
                subs = stripe.Subscription.list(customer=customer_id, limit=1)
                if not subs.data:
                    # No subscriptions at all - delete the orphaned Stripe customer
                    stripe.Customer.delete(customer_id)
                    # Remove from local mapping
                    await self.stripe_customers_collection.delete_one(
                        {"stripe_customer_id": customer_id}
                    )
                    logger.info(f"Cleaned up orphaned Stripe customer {customer_id}")
            except StripeError as e:
                logger.warning(
                    f"Could not clean up Stripe customer {customer_id}: {str(e)}"
                )

        return {"status": "processed", "session_id": session_id}

    async def _handle_invoice_paid(self, invoice: Dict[str, Any]) -> Dict[str, Any]:
        """Handle successful invoice payment"""
        # Check if this is an ad billing invoice
        metadata = invoice.get("metadata", {})
        if metadata.get("platform") == "thespecialwedding_ads":
            return await self._handle_ad_invoice_paid(invoice)

        subscription_id = invoice.get("subscription")
        if not subscription_id:
            return {"status": "ignored", "reason": "no subscription on invoice"}

        subscription = None
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
        except StripeError as e:
            logger.error(
                f"Unable to refresh subscription {subscription_id} during invoice.paid: {str(e)}"
            )

        if subscription:
            await self._sync_subscription_state(
                user_id=subscription.get("metadata", {}).get("user_id"),
                subscription=subscription,
                customer_id=subscription.get("customer"),
                extra_updates={
                    "payment_status": "paid",
                    "last_payment_date": datetime.now(timezone.utc),
                },
            )
        else:
            await self.subscriptions_collection.update_one(
                {"stripe_subscription_id": subscription_id},
                {
                    "$set": {
                        "payment_status": "paid",
                        "last_payment_date": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )

        logger.info(f"Invoice paid for subscription {subscription_id}")

        billing_reason = invoice.get("billing_reason")
        if billing_reason == "subscription_create":
            logger.info(
                "Skipping invoice.paid payment notification for initial subscription invoice %s; checkout.session.completed owns the activation message",
                invoice.get("id"),
            )
            return {
                "status": "success",
                "subscription_id": subscription_id,
                "notification_skipped": True,
            }

        # Send payment success notification (best-effort, don't fail webhook)
        try:
            await self._send_payment_notification(
                subscription_id=subscription_id,
                notification_type="payment_success",
                invoice=invoice,
            )
        except Exception as e:
            logger.error(f"Failed to send payment success notification: {str(e)}")

        return {"status": "success", "subscription_id": subscription_id}

    async def _handle_ad_invoice_paid(self, invoice: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle successful payment of an ad billing invoice.

        Updates vendor_ad_billing record to 'paid' and marks all associated
        ad_lead_charges as 'paid'. Called when Stripe collects payment for
        monthly CPL charges.
        """
        invoice_id = invoice.get("id", "")
        metadata = invoice.get("metadata", {})
        vendor_id = metadata.get("vendor_id", "")
        campaign_id = metadata.get("campaign_id", "")
        now = datetime.now(timezone.utc)

        # Update the billing period record
        update_result = await mongo.db["vendor_ad_billing"].update_many(
            {"stripe_invoice_id": invoice_id},
            {
                "$set": {
                    "payment_status": "paid",
                    "paid_at": now,
                    "updated_at": now,
                }
            },
        )

        # Also update all lead charges associated with this invoice's line items
        # Mark pending charges for this vendor/campaign in the billing period as paid
        if vendor_id:
            await mongo.db["ad_lead_charges"].update_many(
                {
                    "vendor_id": vendor_id,
                    "charge_status": "charged",
                    "stripe_invoice_item_id": {"$ne": None},
                },
                {
                    "$set": {
                        "charge_status": "paid",
                        "updated_at": now,
                    }
                },
            )

        logger.info(
            f"Ad invoice paid: {invoice_id} for vendor {vendor_id} "
            f"campaign {campaign_id} — {update_result.modified_count} billing records updated"
        )

        return {"status": "success", "invoice_id": invoice_id, "platform": "ads"}

    async def _handle_invoice_payment_failed(
        self, invoice: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle failed invoice payment"""
        # Check if this is an ad billing invoice
        metadata = invoice.get("metadata", {})
        if metadata.get("platform") == "thespecialwedding_ads":
            return await self._handle_ad_invoice_payment_failed(invoice)

        subscription_id = invoice.get("subscription")
        if not subscription_id:
            return {"status": "ignored", "reason": "no subscription on invoice"}

        subscription = None
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
        except StripeError as e:
            logger.error(
                f"Unable to refresh subscription {subscription_id} during invoice.payment_failed: {str(e)}"
            )

        if subscription:
            await self._sync_subscription_state(
                user_id=subscription.get("metadata", {}).get("user_id"),
                subscription=subscription,
                customer_id=subscription.get("customer"),
                extra_updates={
                    "payment_status": "past_due",
                    "last_payment_attempt": datetime.now(timezone.utc),
                },
            )
        else:
            await self.subscriptions_collection.update_one(
                {"stripe_subscription_id": subscription_id},
                {
                    "$set": {
                        "payment_status": "past_due",
                        "last_payment_attempt": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )

        logger.warning(f"Invoice payment failed for subscription {subscription_id}")

        # Send payment failed notification (best-effort, don't fail webhook)
        try:
            await self._send_payment_notification(
                subscription_id=subscription_id,
                notification_type="payment_failed",
                invoice=invoice,
            )
        except Exception as e:
            logger.error(f"Failed to send payment failure notification: {str(e)}")

        return {"status": "success", "subscription_id": subscription_id}

    async def _handle_ad_invoice_payment_failed(
        self, invoice: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle failed payment of an ad billing invoice.

        Updates vendor_ad_billing record to 'payment_failed'. Campaigns remain
        active (Stripe will retry) but we flag the billing record. After 3 failed
        attempts Stripe will mark the invoice as uncollectible automatically.
        """
        invoice_id = invoice.get("id", "")
        metadata = invoice.get("metadata", {})
        vendor_id = metadata.get("vendor_id", "")
        campaign_id = metadata.get("campaign_id", "")
        now = datetime.now(timezone.utc)

        # Update billing period record
        update_result = await mongo.db["vendor_ad_billing"].update_many(
            {"stripe_invoice_id": invoice_id},
            {
                "$set": {
                    "payment_status": "payment_failed",
                    "last_payment_attempt": now,
                    "updated_at": now,
                }
            },
        )

        logger.warning(
            f"Ad invoice payment failed: {invoice_id} for vendor {vendor_id} "
            f"campaign {campaign_id} — {update_result.modified_count} billing records updated"
        )

        # Create admin notification for failed ad payment
        try:
            from app.services.config_validator import _create_root_admin_notification

            await _create_root_admin_notification(
                title="Ad Billing Payment Failed",
                message=(
                    f"Stripe invoice {invoice_id} payment failed for vendor {vendor_id}. "
                    f"Campaign: {campaign_id}. Stripe will retry automatically."
                ),
                priority="high",
            )
        except Exception as e:
            logger.error(f"Failed to notify admin of ad payment failure: {e}")

        return {"status": "success", "invoice_id": invoice_id, "platform": "ads"}

    async def _handle_invoice_finalized(
        self, invoice: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle invoice.finalized event.

        For ad billing invoices: updates vendor_ad_billing with the Stripe invoice ID
        and sets status to 'invoiced'. For subscription invoices: acknowledged only.
        """
        metadata = invoice.get("metadata", {})
        invoice_id = invoice.get("id", "")

        if metadata.get("platform") == "thespecialwedding_ads":
            vendor_id = metadata.get("vendor_id", "")
            now = datetime.now(timezone.utc)

            # Update billing records that match this vendor/campaign and are still pending
            update_result = await mongo.db["vendor_ad_billing"].update_many(
                {
                    "stripe_invoice_id": invoice_id,
                    "payment_status": {"$in": ["pending", "invoiced"]},
                },
                {
                    "$set": {
                        "payment_status": "invoiced",
                        "stripe_invoice_id": invoice_id,
                        "updated_at": now,
                    }
                },
            )

            logger.info(
                f"Ad invoice finalized: {invoice_id} for vendor {vendor_id} "
                f"— {update_result.modified_count} billing records updated"
            )
            return {"status": "success", "invoice_id": invoice_id, "platform": "ads"}

        # Non-ad invoices: acknowledge
        logger.info(f"Invoice finalized: {invoice_id}")
        return {"status": "acknowledged", "event_type": "invoice.finalized"}

    async def _handle_payment_intent_succeeded(
        self, payment_intent: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle successful payment intent - updates payment_requests collection
        for couple payments created by planners, and handles autopilot scheduled payments.
        """
        payment_intent_id = payment_intent.get("id")
        if not payment_intent_id:
            return {"status": "ignored", "reason": "no payment_intent_id"}

        # Get receipt URL from charges
        receipt_url = None
        if payment_intent.get("charges", {}).get("data"):
            receipt_url = payment_intent["charges"]["data"][0].get("receipt_url")

        # Check if this is a contract/autopilot payment
        metadata = payment_intent.get("metadata", {})
        payment_type = metadata.get("payment_type")
        if (
            payment_type in {"scheduled", "deposit"}
            or metadata.get("scheduled_payment_id")
            or metadata.get("payment_id")
        ):
            from app.services.autopilot_service import autopilot_service

            await autopilot_service.handle_payment_succeeded(
                payment_intent_id=payment_intent_id, receipt_url=receipt_url
            )
            logger.info(
                "Contract payment %s succeeded (type=%s)",
                payment_intent_id,
                payment_type or "unknown",
            )
            return {
                "status": "success",
                "payment_intent_id": payment_intent_id,
                "type": payment_type or "contract",
            }

        # Update payment request status in our collection
        payment_requests_collection = mongo.db["payment_requests"]
        result = await payment_requests_collection.update_one(
            {"payment_intent_id": payment_intent_id},
            {
                "$set": {
                    "status": "succeeded",
                    "paid_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                    "amount_received": payment_intent.get("amount_received", 0) / 100,
                    "payment_method_type": payment_intent.get(
                        "payment_method_types", [None]
                    )[0],
                }
            },
        )

        if result.modified_count > 0:
            logger.info(f"Payment request {payment_intent_id} marked as succeeded")

            # Notify planner (best-effort, don't fail webhook)
            try:
                await self._notify_planner_payment_received(
                    payment_intent_id=payment_intent_id,
                    amount=payment_intent.get("amount_received", 0) / 100,
                    payer_name=metadata.get("customer_name", "Customer"),
                )
            except Exception as e:
                logger.error(f"Failed to notify planner of payment: {str(e)}")

            return {"status": "success", "payment_intent_id": payment_intent_id}
        else:
            # This payment intent might not be from our payment requests (could be subscription)
            logger.debug(
                f"No payment request found for {payment_intent_id} - may be a subscription payment"
            )
            return {"status": "ignored", "reason": "not_a_payment_request"}

    async def _handle_payment_intent_failed(
        self, payment_intent: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle failed payment intent - handles autopilot scheduled payment failures
        with retry logic.
        """
        payment_intent_id = payment_intent.get("id")
        if not payment_intent_id:
            return {"status": "ignored", "reason": "no payment_intent_id"}

        # Get error details
        last_error = payment_intent.get("last_payment_error", {})
        error_code = last_error.get("code", "unknown")
        error_message = last_error.get("message", "Payment failed")

        # Check if this is a contract/autopilot payment
        metadata = payment_intent.get("metadata", {})
        payment_type = metadata.get("payment_type")
        if (
            payment_type in {"scheduled", "deposit"}
            or metadata.get("scheduled_payment_id")
            or metadata.get("payment_id")
        ):
            from app.services.autopilot_service import autopilot_service

            await autopilot_service.handle_payment_failed(
                payment_intent_id=payment_intent_id,
                error_code=error_code,
                error_message=error_message,
            )
            logger.info(
                "Contract payment %s failed (type=%s): %s",
                payment_intent_id,
                payment_type or "unknown",
                error_message,
            )
            return {
                "status": "handled",
                "payment_intent_id": payment_intent_id,
                "type": payment_type or "contract",
            }

        # Update payment request status for non-autopilot payments
        payment_requests_collection = mongo.db["payment_requests"]
        result = await payment_requests_collection.update_one(
            {"payment_intent_id": payment_intent_id},
            {
                "$set": {
                    "status": "failed",
                    "failure_reason": error_message,
                    "failure_code": error_code,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

        if result.modified_count > 0:
            logger.info(f"Payment request {payment_intent_id} marked as failed")
            return {"status": "handled", "payment_intent_id": payment_intent_id}
        else:
            logger.debug(f"No payment request found for failed {payment_intent_id}")
            return {"status": "ignored", "reason": "not_a_payment_request"}

    async def _handle_account_updated(self, account: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle Stripe Connect account updates - syncs onboarding status
        when account.updated event fires (e.g., after user completes onboarding).
        """
        account_id = account.get("id")
        if not account_id:
            return {"status": "ignored", "reason": "no account_id"}

        charges_enabled = account.get("charges_enabled", False)
        payouts_enabled = account.get("payouts_enabled", False)
        details_submitted = account.get("details_submitted", False)

        # Find and update user with this connect account
        result = await self.users_collection.update_one(
            {"stripe_connect_id": account_id},
            {
                "$set": {
                    "stripe_connect_charges_enabled": charges_enabled,
                    "stripe_connect_payouts_enabled": payouts_enabled,
                    "stripe_connect_details_submitted": details_submitted,
                    "stripe_connect_updated_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

        if result.modified_count > 0:
            logger.info(
                f"Connect account {account_id} updated: charges={charges_enabled}, "
                f"payouts={payouts_enabled}, details_submitted={details_submitted}"
            )
            return {
                "status": "success",
                "account_id": account_id,
                "charges_enabled": charges_enabled,
                "payouts_enabled": payouts_enabled,
            }
        else:
            logger.warning(f"No user found with stripe_connect_id: {account_id}")
            return {"status": "ignored", "reason": "user_not_found"}

    # ==================== PAYMENT NOTIFICATIONS ====================

    async def _send_payment_notification(
        self,
        subscription_id: str,
        notification_type: str,
        invoice: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Send payment notification to the subscription owner.
        Creates both an in-app notification and sends an email.

        Args:
            subscription_id: The Stripe subscription ID
            notification_type: 'payment_success' or 'payment_failed'
            invoice: The invoice data from Stripe
        """
        try:
            # Find the subscription and user
            subscription = await self.subscriptions_collection.find_one(
                {"stripe_subscription_id": subscription_id}
            )

            if not subscription:
                logger.warning(
                    f"No subscription found for notification: {subscription_id}"
                )
                return

            user_id = subscription.get("user_id")
            if not user_id:
                logger.warning(f"No user_id in subscription: {subscription_id}")
                return

            # Find user by ID or email
            user = None
            if ObjectId.is_valid(user_id):
                user = await self.users_collection.find_one({"_id": ObjectId(user_id)})
            if not user:
                user = await self.users_collection.find_one({"email": user_id})

            if not user or not user.get("email"):
                logger.warning(f"User not found for notification: {user_id}")
                return

            user_email = user.get("email")
            user_name = (
                user.get("first_name")
                or user.get("company_name")
                or user_email.split("@")[0]
            )

            # Get plan details
            plan = None
            if subscription.get("plan_id"):
                try:
                    if ObjectId.is_valid(subscription["plan_id"]):
                        plan = await self.plans_collection.find_one(
                            {"_id": ObjectId(subscription["plan_id"])}
                        )
                    else:
                        plan = await self.plans_collection.find_one(
                            {"_id": subscription["plan_id"]}
                        )
                except Exception:
                    pass

            plan_name = plan.get("name", "Subscription") if plan else "Subscription"

            # Calculate amount from invoice
            amount = invoice.get("amount_paid", 0) / 100 if invoice else 0
            currency = (invoice.get("currency", "usd") if invoice else "usd").upper()

            # Create in-app notification first
            await self._create_in_app_notification(
                user_id=user_id,
                user_email=user_email,
                notification_type=notification_type,
                plan_name=plan_name,
                amount=amount,
                currency=currency,
            )

            # Prepare email content
            if notification_type == "payment_success":
                subject = f"Payment Received - {plan_name}"
                html_content = self._render_payment_success_email(
                    user_name=user_name,
                    plan_name=plan_name,
                    amount=amount,
                    currency=currency,
                    invoice_date=datetime.now(timezone.utc).strftime("%B %d, %Y"),
                    invoice_pdf=invoice.get("invoice_pdf") if invoice else None,
                )
            else:  # payment_failed
                subject = "Payment Failed - Action Required"
                html_content = self._render_payment_failed_email(
                    user_name=user_name,
                    plan_name=plan_name,
                    amount=amount,
                    currency=currency,
                )

            # Send the email
            if not getattr(self.email_service, "configured", False):
                logger.warning(
                    "Email service not configured, skipping email notification"
                )
                return

            result = await self.email_service.send_email(
                to_email=user_email,
                subject=subject,
                html_content=html_content,
                email_type="billing_notification",
                **self._get_billing_sender(),
            )

            if result.get("success"):
                logger.info(
                    f"Payment notification sent to {user_email} for {notification_type}"
                )
            else:
                logger.error(
                    f"Failed to send payment notification: {result.get('error')}"
                )

            # Send push notification (non-blocking, separate from email)
            try:
                from app.services.planner_notification_service import (
                    PlannerNotificationService,
                )

                pns = PlannerNotificationService()
                if notification_type == "payment_failed":
                    await pns._send_push_notification(
                        planner_id=user_email,
                        notification_type="payment_failed",
                        title="Payment Failed",
                        message=f"Payment of {currency} {amount:.2f} for {plan_name} failed. Please update your payment method.",
                        action_url="/planner/billing",
                    )
                # payment_success push is already wired via notify_payment_received
            except Exception as push_err:
                logger.warning(
                    f"Push notification for {notification_type} failed: {push_err}"
                )

        except Exception as e:
            # Don't fail the webhook if notification fails
            logger.error(f"Error sending payment notification: {str(e)}")

    async def _send_checkout_completion_notification(
        self,
        user_id: str,
        plan_id: str,
        session: Dict[str, Any],
        subscription: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Send the first successful checkout confirmation after local sync completes."""

        resolved_subscription = subscription or {}
        stripe_status = resolved_subscription.get("status")
        trial_end = self._parse_timestamp(resolved_subscription.get("trial_end"))

        user = await self.users_collection.find_one({"_id": ObjectId(user_id)})
        if not user or not user.get("email"):
            logger.warning(
                f"Skipping checkout completion notification; user {user_id} not found"
            )
            return

        plan = None
        try:
            plan = await self.plans_collection.find_one({"_id": plan_id})
        except Exception:
            plan = None

        plan_name = plan.get("name", "Subscription") if plan else "Subscription"
        user_email = user["email"]
        user_name = (
            user.get("first_name")
            or user.get("company_name")
            or user_email.split("@")[0]
        )
        amount = (session.get("amount_total") or 0) / 100
        currency = (session.get("currency") or "usd").upper()
        billing_url = f"{settings.frontend_url}/admin/planner/billing"
        invoice_date = datetime.now(timezone.utc).strftime("%B %d, %Y")

        # ── Fetch the latest invoice for PDF/hosted links ──────────────
        invoice_pdf_url: Optional[str] = None
        hosted_invoice_url: Optional[str] = None
        invoice_number: Optional[str] = None
        subscription_id = session.get("subscription")
        if subscription_id:
            try:
                invoices = stripe.Invoice.list(
                    subscription=subscription_id,
                    limit=1,
                )
                if invoices.data:
                    latest_invoice = invoices.data[0]
                    invoice_pdf_url = latest_invoice.invoice_pdf
                    hosted_invoice_url = latest_invoice.hosted_invoice_url
                    invoice_number = latest_invoice.number
            except Exception as inv_err:
                logger.warning(
                    f"Could not fetch invoice for checkout completion email (sub {subscription_id}): {inv_err}"
                )

        # Build invoice section for emails (reused across trial and paid paths).
        # _safe_external_url enforces an http(s) scheme allowlist so a malicious
        # `javascript:` URL slipped into Stripe's invoice fields can't surface as
        # an executable href.
        invoice_links_html = ""
        safe_pdf_url_value = _safe_external_url(invoice_pdf_url)
        safe_hosted_url_value = _safe_external_url(hosted_invoice_url)
        if safe_pdf_url_value or safe_hosted_url_value:
            buttons = []
            if safe_pdf_url_value:
                safe_invoice_pdf_url = html.escape(safe_pdf_url_value, quote=True)
                buttons.append(
                    f'<a href="{safe_invoice_pdf_url}" style="display: inline-block; background: #2563eb; color: #ffffff; '
                    f"text-decoration: none; padding: 10px 18px; border-radius: 8px; font-size: 14px; "
                    f'font-weight: 500; margin-right: 8px;">Download Invoice PDF</a>'
                )
            if safe_hosted_url_value:
                safe_hosted_invoice_url = html.escape(safe_hosted_url_value, quote=True)
                buttons.append(
                    f'<a href="{safe_hosted_invoice_url}" style="display: inline-block; background: #ffffff; color: #2563eb; '
                    f"text-decoration: none; padding: 10px 18px; border-radius: 8px; font-size: 14px; "
                    f'font-weight: 500; border: 1px solid #2563eb;">View Invoice Online</a>'
                )
            invoice_links_html = (
                f'<div style="margin: 20px 0;">{"".join(buttons)}</div>'
            )

        invoice_number_line = ""
        if invoice_number:
            safe_invoice_number = html.escape(str(invoice_number), quote=True)
            invoice_number_line = f'<p style="margin: 0 0 8px;"><strong>Invoice:</strong> {safe_invoice_number}</p>'

        safe_plan_name = html.escape(str(plan_name), quote=True)
        safe_user_name = html.escape(str(user_name), quote=True)
        safe_currency = html.escape(str(currency), quote=True)
        safe_invoice_date = html.escape(str(invoice_date), quote=True)
        safe_billing_url = html.escape(str(billing_url), quote=True)

        if stripe_status == "trialing" and trial_end:
            trial_end_label = trial_end.strftime("%B %d, %Y")
            safe_trial_end_label = html.escape(trial_end_label, quote=True)
            subject = f"{plan_name} Trial Activated"
            html_content = f"""
            <div style="font-family: Arial, sans-serif; max-width: 640px; margin: 0 auto; padding: 24px; color: #0f172a;">
              <h1 style="margin-bottom: 12px;">Your {safe_plan_name} trial is active</h1>
              <p>Hi {safe_user_name},</p>
              <p>Your subscription checkout is complete and your <strong>{safe_plan_name}</strong> trial is now active.</p>
              <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 18px; margin: 20px 0;">
                {invoice_number_line}
                <p style="margin: 0 0 8px;"><strong>Trial end date:</strong> {safe_trial_end_label}</p>
                <p style="margin: 0;"><strong>Billing begins after:</strong> {safe_trial_end_label}</p>
              </div>
              {invoice_links_html}
              <p>Your saved payment method will be used automatically when the trial ends unless you change or cancel the subscription first.</p>
              <p><a href="{safe_billing_url}" style="display: inline-block; background: #111827; color: #ffffff; text-decoration: none; padding: 12px 18px; border-radius: 999px;">Manage billing</a></p>
            </div>
            """
            notification_title = "Free Trial Active"
            notification_message = (
                f"Your {plan_name} trial is active through {trial_end_label}."
            )
        else:
            subject = f"{plan_name} Subscription Activated"
            html_content = f"""
            <div style="font-family: Arial, sans-serif; max-width: 640px; margin: 0 auto; padding: 24px; color: #0f172a;">
              <h1 style="margin-bottom: 12px;">Your {safe_plan_name} subscription is active</h1>
              <p>Hi {safe_user_name},</p>
              <p>Your checkout completed successfully and your subscription is ready to use.</p>
              <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 18px; margin: 20px 0;">
                {invoice_number_line}
                <p style="margin: 0 0 8px;"><strong>Amount received:</strong> ${amount:.2f} {safe_currency}</p>
                <p style="margin: 0;"><strong>Processed on:</strong> {safe_invoice_date}</p>
              </div>
              {invoice_links_html}
              <p>You can manage your payment method, billing history, and plan from your billing page any time.</p>
              <p><a href="{safe_billing_url}" style="display: inline-block; background: #111827; color: #ffffff; text-decoration: none; padding: 12px 18px; border-radius: 999px;">Open billing</a></p>
            </div>
            """
            notification_title = "Subscription Active"
            notification_message = (
                f"Your {plan_name} subscription is active and ready to use."
            )

        await mongo.db["notifications"].insert_one(
            {
                "_id": ObjectId(),
                "title": notification_title,
                "message": notification_message,
                "type": "billing",
                "target_audience": "specific_user",
                "user_id": user_id,
                "user_email": user_email,
                "created_by": "system",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "expiry_date": None,
                "is_dismissible": True,
                "priority": "low",
                "status": "active",
                "read_by": [],
                "dismissed_by": [],
                "metadata": {
                    "notification_type": "subscription_activation",
                    "plan_name": plan_name,
                    "amount": amount,
                    "currency": currency,
                    "stripe_subscription_id": session.get("subscription"),
                },
            }
        )

        if not getattr(self.email_service, "configured", False):
            logger.warning(
                "Email service not configured, skipping checkout completion email notification"
            )
            return

        result = await self.email_service.send_email(
            to_email=user_email,
            subject=subject,
            html_content=html_content,
            email_type="subscription_activation",
            **self._get_billing_sender(),
        )

        if result.get("success"):
            logger.info(f"Checkout completion email sent to {user_email}")
        else:
            logger.error(
                f"Failed to send checkout completion email to {user_email}: {result.get('error')}"
            )

    async def _create_in_app_notification(
        self,
        user_id: str,
        user_email: str,
        notification_type: str,
        plan_name: str,
        amount: float,
        currency: str,
    ) -> None:
        """
        Create an in-app notification that appears in the notification bell.

        Args:
            user_id: The user's ID
            user_email: The user's email
            notification_type: 'payment_success' or 'payment_failed'
            plan_name: Name of the subscription plan
            amount: Payment amount
            currency: Currency code (USD, etc.)
        """
        try:
            notifications_collection = mongo.db["notifications"]

            if notification_type == "payment_success":
                notification = {
                    "_id": ObjectId(),
                    "title": "Payment Successful",
                    "message": f"Your payment of ${amount:.2f} {currency} for {plan_name} was processed successfully.",
                    "type": "billing",
                    "target_audience": "specific_user",
                    "user_id": user_id,
                    "user_email": user_email,
                    "created_by": "system",
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                    "expiry_date": None,
                    "is_dismissible": True,
                    "priority": "low",
                    "status": "active",
                    "read_by": [],
                    "dismissed_by": [],
                    "metadata": {
                        "notification_type": "payment_success",
                        "amount": amount,
                        "currency": currency,
                        "plan_name": plan_name,
                    },
                }
            else:  # payment_failed
                notification = {
                    "_id": ObjectId(),
                    "title": "Payment Failed",
                    "message": f"We couldn't process your payment of ${amount:.2f} {currency} for {plan_name}. Please update your payment method.",
                    "type": "billing",
                    "target_audience": "specific_user",
                    "user_id": user_id,
                    "user_email": user_email,
                    "created_by": "system",
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                    "expiry_date": None,
                    "is_dismissible": False,  # Payment failures should not be easily dismissed
                    "priority": "urgent",  # High priority for failed payments
                    "status": "active",
                    "read_by": [],
                    "dismissed_by": [],
                    "metadata": {
                        "notification_type": "payment_failed",
                        "amount": amount,
                        "currency": currency,
                        "plan_name": plan_name,
                        "action_url": "/admin/planner/billing",
                    },
                }

            await notifications_collection.insert_one(notification)
            logger.info(
                f"Created in-app {notification_type} notification for user {user_email}"
            )

        except Exception as e:
            logger.error(f"Error creating in-app notification: {str(e)}")

    async def _notify_planner_payment_received(
        self, payment_intent_id: str, amount: float, payer_name: str
    ):
        """Notify planner about a received payment from couple/vendor"""
        try:
            # Get the payment request to find the wedding and planner
            payment_requests_collection = mongo.db["payment_requests"]
            payment_request = await payment_requests_collection.find_one(
                {"payment_intent_id": payment_intent_id}
            )

            if not payment_request:
                logger.debug(f"No payment request found for {payment_intent_id}")
                return

            wedding_id = payment_request.get("wedding_id")
            planner_email = payment_request.get("created_by")

            if not planner_email:
                # Try to get planner from wedding
                if wedding_id:
                    wedding = await mongo.db["weddings"].find_one(
                        {"_id": normalize_query_id(wedding_id)}
                    )
                    if wedding:
                        (
                            planner_id,
                            wedding_planner_email,
                        ) = extract_wedding_owner_identity(wedding)
                        planner_email = await resolve_planner_email(
                            planner_id, wedding_planner_email
                        )

            if not planner_email:
                logger.debug(f"No planner found for payment {payment_intent_id}")
                return

            # Import here to avoid circular imports
            from app.services.planner_notification_service import (
                planner_notification_service,
            )

            await planner_notification_service.notify_payment_received(
                planner_id=planner_email,
                wedding_id=wedding_id or "",
                amount=amount,
                payer_name=payer_name,
                payment_id=payment_intent_id,
            )
            logger.info(f"Payment notification sent to planner {planner_email}")

        except Exception as e:
            # Don't fail the webhook if notification fails
            logger.error(f"Error sending planner payment notification: {str(e)}")

    def _render_payment_success_email(
        self,
        user_name: str,
        plan_name: str,
        amount: float,
        currency: str,
        invoice_date: str,
        invoice_pdf: Optional[str] = None,
    ) -> str:
        """Render payment success email HTML"""
        safe_user_name = html.escape(user_name, quote=True)
        safe_plan_name = html.escape(plan_name, quote=True)
        safe_currency = html.escape(currency, quote=True)
        safe_invoice_date = html.escape(invoice_date, quote=True)

        # _safe_external_url drops any URL that doesn't start with http(s)
        # — closes the `javascript:` href XSS path live-verify caught.
        safe_pdf_value = _safe_external_url(invoice_pdf)
        download_section = ""
        if safe_pdf_value:
            safe_invoice_pdf = html.escape(safe_pdf_value, quote=True)
            download_section = f"""
                <tr>
                  <td style="padding:20px 40px 0;">
                    <a href="{safe_invoice_pdf}" style="display:inline-block;padding:12px 24px;background:#2563eb;color:#ffffff;text-decoration:none;border-radius:8px;font-size:14px;font-weight:500;">Download Invoice PDF</a>
                  </td>
                </tr>
            """

        return f"""
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f8fafc;padding:40px 0;">
          <tr>
            <td align="center" style="padding:0 16px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border-radius:16px;border:1px solid #e2e8f0;overflow:hidden;">
                <tr>
                  <td style="padding:40px 40px 0;text-align:center;">
                    <div style="width:64px;height:64px;background:#dcfce7;border-radius:50%;margin:0 auto 20px;display:flex;align-items:center;justify-content:center;">
                      <span style="font-size:28px;">✓</span>
                    </div>
                    <h1 style="margin:0 0 8px;font-size:24px;font-weight:600;color:#0f172a;font-family:'SF Pro Display','Helvetica Neue',Helvetica,Arial,sans-serif;">Payment Successful</h1>
                    <p style="margin:0;color:#64748b;font-size:14px;font-family:'SF Pro Text','Helvetica Neue',Helvetica,Arial,sans-serif;">Thank you for your payment</p>
                  </td>
                </tr>
                <tr>
                  <td style="padding:32px 40px;font-family:'SF Pro Text','Helvetica Neue',Helvetica,Arial,sans-serif;color:#0f172a;">
                    <p style="margin:0 0 24px;font-size:16px;line-height:1.6;">Hi {safe_user_name},</p>
                    <p style="margin:0 0 24px;font-size:16px;line-height:1.6;color:#475569;">We've received your payment. Here are the details:</p>

                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;border-radius:12px;padding:20px;margin-bottom:24px;">
                      <tr>
                        <td style="padding:8px 16px;">
                          <p style="margin:0;font-size:14px;color:#64748b;">Plan</p>
                          <p style="margin:4px 0 0;font-size:16px;font-weight:500;color:#0f172a;">{safe_plan_name}</p>
                        </td>
                      </tr>
                      <tr>
                        <td style="padding:8px 16px;">
                          <p style="margin:0;font-size:14px;color:#64748b;">Amount</p>
                          <p style="margin:4px 0 0;font-size:16px;font-weight:500;color:#0f172a;">${amount:.2f} {safe_currency}</p>
                        </td>
                      </tr>
                      <tr>
                        <td style="padding:8px 16px;">
                          <p style="margin:0;font-size:14px;color:#64748b;">Date</p>
                          <p style="margin:4px 0 0;font-size:16px;font-weight:500;color:#0f172a;">{safe_invoice_date}</p>
                        </td>
                      </tr>
                    </table>

                    <p style="margin:0;font-size:14px;color:#64748b;line-height:1.6;">You can view your billing history and manage your subscription in your account settings.</p>
                  </td>
                </tr>
                {download_section}
                <tr>
                  <td style="padding:32px 40px;font-family:'SF Pro Text','Helvetica Neue',Helvetica,Arial,sans-serif;font-size:12px;color:#94a3b8;border-top:1px solid #e2e8f0;">
                    <p style="margin:0;">If you have any questions, please contact our support team.</p>
                    <p style="margin:12px 0 0;">© {datetime.now(timezone.utc).year} The Special Wedding. All rights reserved.</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
        """

    def _render_payment_failed_email(
        self, user_name: str, plan_name: str, amount: float, currency: str
    ) -> str:
        """Render payment failed email HTML"""
        safe_user_name = html.escape(user_name, quote=True)
        safe_plan_name = html.escape(plan_name, quote=True)
        safe_currency = html.escape(currency, quote=True)
        safe_billing_url = html.escape(
            f"{settings.frontend_url or ''}/admin/planner/billing", quote=True
        )

        return f"""
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f8fafc;padding:40px 0;">
          <tr>
            <td align="center" style="padding:0 16px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border-radius:16px;border:1px solid #e2e8f0;overflow:hidden;">
                <tr>
                  <td style="padding:40px 40px 0;text-align:center;">
                    <div style="width:64px;height:64px;background:#fee2e2;border-radius:50%;margin:0 auto 20px;display:flex;align-items:center;justify-content:center;">
                      <span style="font-size:28px;">!</span>
                    </div>
                    <h1 style="margin:0 0 8px;font-size:24px;font-weight:600;color:#0f172a;font-family:'SF Pro Display','Helvetica Neue',Helvetica,Arial,sans-serif;">Payment Failed</h1>
                    <p style="margin:0;color:#dc2626;font-size:14px;font-family:'SF Pro Text','Helvetica Neue',Helvetica,Arial,sans-serif;">Action required to continue your subscription</p>
                  </td>
                </tr>
                <tr>
                  <td style="padding:32px 40px;font-family:'SF Pro Text','Helvetica Neue',Helvetica,Arial,sans-serif;color:#0f172a;">
                    <p style="margin:0 0 24px;font-size:16px;line-height:1.6;">Hi {safe_user_name},</p>
                    <p style="margin:0 0 24px;font-size:16px;line-height:1.6;color:#475569;">We were unable to process your payment of <strong>${amount:.2f} {safe_currency}</strong> for your <strong>{safe_plan_name}</strong> subscription.</p>

                    <div style="background:#fef2f2;border:1px solid #fecaca;border-radius:12px;padding:20px;margin-bottom:24px;">
                      <p style="margin:0;font-size:14px;color:#991b1b;line-height:1.6;"><strong>What you need to do:</strong></p>
                      <ul style="margin:12px 0 0;padding-left:20px;color:#991b1b;font-size:14px;line-height:1.8;">
                        <li>Check that your card hasn't expired</li>
                        <li>Ensure sufficient funds are available</li>
                        <li>Update your payment method if needed</li>
                      </ul>
                    </div>

                    <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 auto;">
                      <tr>
                        <td style="background:#2563eb;border-radius:8px;">
                          <a href="{safe_billing_url}" style="display:inline-block;padding:14px 28px;color:#ffffff;text-decoration:none;font-size:14px;font-weight:500;">Update Payment Method</a>
                        </td>
                      </tr>
                    </table>

                    <p style="margin:24px 0 0;font-size:14px;color:#64748b;line-height:1.6;">If you don't update your payment method, your subscription features may be limited.</p>
                  </td>
                </tr>
                <tr>
                  <td style="padding:32px 40px;font-family:'SF Pro Text','Helvetica Neue',Helvetica,Arial,sans-serif;font-size:12px;color:#94a3b8;border-top:1px solid #e2e8f0;">
                    <p style="margin:0;">If you believe this is an error or need assistance, please contact our support team.</p>
                    <p style="margin:12px 0 0;">© {datetime.now(timezone.utc).year} The Special Wedding. All rights reserved.</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
        """

    # ==================== CONNECT / MARKETPLACE ====================

    async def create_connected_account(
        self, user_id: str, email: str, country: str = "US"
    ) -> str:
        """
        Create a Stripe Express connected account for a user (Planner or Vendor).

        Args:
            user_id: The internal user ID.
            email: The user's email.
            country: The user's country code.

        Returns:
            The new connected account ID.
        """
        self._ensure_stripe_enabled()

        try:
            # Check if user already has a connect account
            user = await self.users_collection.find_one({"_id": ObjectId(user_id)})
            if user and user.get("stripe_connect_id"):
                return user["stripe_connect_id"]

            account = stripe.Account.create(
                type="express",
                country=country,
                email=email,
                capabilities={
                    "card_payments": {"requested": True},
                    "transfers": {"requested": True},
                },
                metadata={"user_id": user_id},
            )

            # Save account ID to user record
            await self.users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {
                    "$set": {
                        "stripe_connect_id": account.id,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )

            logger.info(
                f"Created Stripe connected account {account.id} for user {user_id}"
            )
            return account.id

        except StripeError as e:
            logger.error(f"Stripe error creating connected account: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Stripe Connect error: {str(e)}"
            )

    def create_account_link(
        self, account_id: str, refresh_url: str, return_url: str
    ) -> str:
        """
        Create an onboarding link for a connected account.
        """
        self._ensure_stripe_enabled()

        try:
            account_link = stripe.AccountLink.create(
                account=account_id,
                refresh_url=refresh_url,
                return_url=return_url,
                type="account_onboarding",
            )
            return account_link.url
        except StripeError as e:
            logger.error(f"Stripe error creating account link: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Stripe Connect error: {str(e)}"
            )

    def get_account_status(self, account_id: str) -> Dict[str, Any]:
        """Check if a connected account is fully onboarded."""
        self._ensure_stripe_enabled()

        try:
            account = stripe.Account.retrieve(account_id)
            return {
                "id": account.id,
                "charges_enabled": account.charges_enabled,
                "payouts_enabled": account.payouts_enabled,
                "details_submitted": account.details_submitted,
            }
        except StripeError as e:
            logger.error(f"Stripe error retrieving account: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Stripe Connect error: {str(e)}"
            )

    # ==================== PAYMENT COLLECTION FOR COUPLES ====================

    def create_payment_intent_for_couple(
        self,
        amount: float,
        currency: str = "usd",
        wedding_id: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        destination_account_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a payment intent for collecting payment from couples.
        If destination_account_id is provided, funds are routed to that connected account.
        """
        self._ensure_stripe_enabled()

        try:
            payment_metadata = metadata or {}
            if wedding_id:
                payment_metadata["wedding_id"] = wedding_id

            create_kwargs = {
                "amount": int(amount * 100),
                "currency": currency.lower(),
                "description": description or "Wedding service payment",
                "metadata": payment_metadata,
                "automatic_payment_methods": {"enabled": True},
            }

            # If destination provided, use transfer_data to route funds
            # The platform acts as the merchant of record but funds go to the destination
            if destination_account_id:
                create_kwargs["transfer_data"] = {"destination": destination_account_id}
                # Optional: Add application_fee_amount here if the platform takes a cut
                # create_kwargs["application_fee_amount"] = int(amount * 100 * 0.01) # 1% fee

            payment_intent = stripe.PaymentIntent.create(**create_kwargs)

            logger.info(
                f"Created payment intent {payment_intent.id} for amount {amount}"
            )

            return {
                "payment_intent_id": payment_intent.id,
                "client_secret": payment_intent.client_secret,
                "amount": amount,
                "currency": currency,
                "status": payment_intent.status,
            }

        except StripeError as e:
            logger.error(f"Stripe error creating payment intent: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Payment service error: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Error creating payment intent: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error creating payment intent: {str(e)}"
            )


# Create singleton instance
stripe_service = StripeService()
