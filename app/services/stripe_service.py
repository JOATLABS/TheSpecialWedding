"""Stripe payment utilities used to manage subscription checkout and lifecycle."""

import stripe
from fastapi import HTTPException
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from app.core.settings import settings
from app.core.database import mongo
from bson import ObjectId
import logging

from app.models.subscription import SubscriptionStatus
from app.services.email_service_resend import ResendEmailService

logger = logging.getLogger(__name__)

# Initialize Stripe
if settings.stripe_enabled and settings.stripe_secret_key:
    stripe.api_key = settings.stripe_secret_key
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
        self.email_service = ResendEmailService()

    def _ensure_stripe_enabled(self):
        """Verify Stripe is properly configured"""
        if not settings.stripe_enabled:
            raise HTTPException(
                status_code=503,
                detail="Stripe payment processing is currently disabled"
            )
        if not settings.stripe_secret_key:
            raise HTTPException(
                status_code=500,
                detail="Stripe configuration error: Missing secret key"
            )

    # ==================== CUSTOMER MANAGEMENT ====================

    async def get_or_create_customer(self, user_id: str, email: str, name: Optional[str] = None) -> str:
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
            customer_record = await self.stripe_customers_collection.find_one({"user_id": user_id})

            if customer_record and customer_record.get("stripe_customer_id"):
                # Verify customer exists in Stripe
                try:
                    stripe.Customer.retrieve(customer_record["stripe_customer_id"])
                    return customer_record["stripe_customer_id"]
                except stripe.error.InvalidRequestError:
                    # Customer doesn't exist in Stripe, create new one
                    logger.warning(f"Stripe customer {customer_record['stripe_customer_id']} not found, creating new")

            # Create new Stripe customer
            customer = stripe.Customer.create(
                email=email,
                name=name or email,
                metadata={"user_id": user_id}
            )

            # Save customer ID to database
            await self.stripe_customers_collection.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "user_id": user_id,
                        "stripe_customer_id": customer.id,
                        "email": email,
                        "created_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc)
                    }
                },
                upsert=True
            )

            logger.info(f"Created Stripe customer {customer.id} for user {user_id}")
            return customer.id

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating customer: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Payment service error: {str(e)}")
        except Exception as e:
            logger.error(f"Error creating Stripe customer: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error creating customer: {str(e)}")

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
                    meters = stripe.billing.Meter.list(status='active')
                    for meter in meters.data:
                        if meter.event_name == meter_event_name:
                            meter_id = meter.id
                            break
                except Exception as e:
                    logger.warning(f"Failed to list Stripe meters: {e}")

            if is_metered and not meter_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Metered plan '{plan.get('_id')}' requires a valid Stripe meter_id or meter_event_name"
                )

            # 1. Create or Update Product
            if not product_id:
                product = stripe.Product.create(
                    name=plan["name"],
                    description=plan.get("description", ""),
                    metadata={"plan_id": plan["_id"]}
                )
                product_id = product.id
            else:
                try:
                    stripe.Product.retrieve(product_id)
                    stripe.Product.modify(
                        product_id,
                        name=plan["name"],
                        description=plan.get("description", ""),
                        metadata={"plan_id": plan["_id"]}
                    )
                except stripe.error.InvalidRequestError:
                    # Product might have been deleted in Stripe
                    product = stripe.Product.create(
                        name=plan["name"],
                        description=plan.get("description", ""),
                        metadata={"plan_id": plan["_id"]}
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
                            price.unit_amount == amount_cents and
                            price.currency == "usd" and
                            price.recurring.interval == interval
                        )

                        # Check metered config
                        if matches and is_metered:
                            matches = (price.recurring.usage_type == "metered")
                            if meter_id:
                                matches = matches and (getattr(price.recurring, "meter", None) == meter_id)
                        elif matches and not is_metered:
                            matches = (price.recurring.usage_type != "metered")

                        if matches:
                            return current_price_id

                        # Price exists but doesn't match - will create new, deactivate old below
                    except stripe.error.InvalidRequestError:
                        current_price_id = None  # Price not found, just create new

                price_kwargs = {
                    "product": product_id,
                    "unit_amount": amount_cents,
                    "currency": "usd",
                    "recurring": expected_recurring,
                    "nickname": f"{plan['name']} {interval.title()}"
                }

                if is_metered and meter_id:
                    price_kwargs["recurring"]["meter"] = meter_id
                    price_kwargs["recurring"]["usage_type"] = "metered"

                new_price = stripe.Price.create(**price_kwargs)

                # Deactivate old price if it existed (Stripe best practice)
                if current_price_id:
                    try:
                        stripe.Price.modify(current_price_id, active=False)
                        logger.info(f"Deactivated old price {current_price_id} after creating new price {new_price.id}")
                    except stripe.error.StripeError as e:
                        logger.warning(f"Could not deactivate old price {current_price_id}: {e}")

                return new_price.id

            new_price_id_monthly = ensure_price(price_id_monthly, plan.get("price_monthly"), "month")
            new_price_id_yearly = ensure_price(price_id_yearly, plan.get("price_yearly"), "year")

            result = {
                "stripe_product_id": product_id,
                "stripe_price_id_monthly": new_price_id_monthly,
                "stripe_price_id_yearly": new_price_id_yearly
            }

            # If we found a meter_id and it wasn't in the plan, return it so we can update the DB
            if meter_id and not plan.get("meter_id"):
                result["meter_id"] = meter_id

            return result

        except stripe.error.StripeError as e:
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

        except stripe.error.InvalidRequestError as e:
            # Product might not exist in Stripe
            logger.warning(f"Could not archive Stripe product {stripe_product_id}: {str(e)}")
            return False
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error archiving product: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Stripe Archive Error: {str(e)}")

    def report_meter_event(
        self,
        event_name: str,
        payload: Dict[str, Any],
        timestamp: Optional[datetime] = None,
        identifier: Optional[str] = None
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
                "timestamp": int(timestamp.timestamp())
            }

            # Add idempotency identifier if provided - prevents duplicate billing on retries
            if identifier:
                meter_params["identifier"] = identifier[:100]  # Max 100 chars

            event = stripe.billing.MeterEvent.create(**meter_params)
            return {"status": "success", "event_id": event.identifier}
        except stripe.error.StripeError as e:
            error_msg = str(e)
            # Duplicate identifier = already recorded (this is success, not error)
            if "identifier" in error_msg.lower() and ("already" in error_msg.lower() or "duplicate" in error_msg.lower()):
                logger.info(f"Meter event already recorded (idempotent): {identifier}")
                return {"status": "success", "event_id": identifier, "already_recorded": True}
            logger.error(f"Stripe error reporting usage: {error_msg}")
            return {"status": "error", "message": error_msg}


    async def create_checkout_session(
        self,
        user_id: str,
        plan_id: str,
        billing_interval: str = "monthly",
        success_url: str = None,
        cancel_url: str = None,
        trial_days: int = 0
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
                raise HTTPException(status_code=404, detail="Subscription plan not found")

            if not plan.get("is_active", True):
                raise HTTPException(status_code=400, detail="Subscription plan is not currently active")

            # Metered flag for downstream usage (quantity rules)
            is_metered = plan.get("is_metered", False)

            # Respect plan-level trial configuration when available
            plan_trial_days = plan.get("trial_days")
            if isinstance(plan_trial_days, int) and plan_trial_days >= 0:
                trial_days = plan_trial_days
            trial_days = max(trial_days, 0)

            # Get or create Stripe customer
            customer_id = await self.get_or_create_customer(
                user_id=user_id,
                email=user["email"],
                name=user.get("full_name") or user.get("email")
            )

            # Determine price based on billing interval
            price_id_field = f"stripe_price_id_{billing_interval}"
            stripe_price_id = plan.get(price_id_field)

            # If Stripe IDs are missing, sync them now
            if not stripe_price_id:
                logger.info(f"Stripe price ID missing for plan {plan_id}, syncing now...")
                sync_result = self.sync_plan_to_stripe(plan)

                # Update plan in DB with new IDs
                await self.plans_collection.update_one(
                    {"_id": plan_id},
                    {"$set": sync_result}
                )

                stripe_price_id = sync_result.get(price_id_field)

            if not stripe_price_id:
                raise HTTPException(status_code=500, detail=f"Failed to resolve Stripe price for {billing_interval} billing")

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

            if trial_days > 0:
                subscription_data["trial_period_days"] = trial_days
                subscription_data["trial_settings"] = {
                    "end_behavior": {
                        # We collect cards up front, so cancel if a payment method is missing at the end of trial
                        "missing_payment_method": "cancel"
                    }
                }

            # Build line item; quantity must be omitted for metered prices
            line_item: Dict[str, Any] = {"price": stripe_price_id}
            if not is_metered:
                line_item["quantity"] = 1

            # Create checkout session
            checkout_session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=["card"],
                line_items=[line_item],
                mode="subscription",
                success_url=success_url,
                cancel_url=cancel_url,
                subscription_data=subscription_data,
                allow_promotion_codes=True,
                billing_address_collection="auto",
                payment_method_collection="always",
                customer_update={
                    "address": "auto",
                    "name": "auto"
                }
            )

            # Save session reference
            await self.subscriptions_collection.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "stripe_checkout_session_id": checkout_session.id,
                        "stripe_checkout_created_at": datetime.now(timezone.utc)
                    }
                },
                upsert=True
            )

            logger.info(f"Created checkout session {checkout_session.id} for user {user_id}")

            return {
                "session_id": checkout_session.id,
                "url": checkout_session.url,
                "customer_id": customer_id,
                "expires_at": checkout_session.expires_at
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating checkout session: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Payment service error: {str(e)}")
        except Exception as e:
            logger.error(f"Error creating checkout session: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error creating checkout session: {str(e)}")

    def _parse_timestamp(self, timestamp: Optional[int]) -> Optional[datetime]:
        """Convert Stripe timestamps to naive UTC datetimes."""

        if not timestamp:
            return None
        try:
            return datetime.utcfromtimestamp(timestamp)
        except Exception:
            return None

    def _map_stripe_status(self, stripe_status: Optional[str]) -> str:
        """Translate Stripe subscription status to internal subscription state."""

        if not stripe_status:
            return SubscriptionStatus.ACTIVE.value

        mapping = {
            "trialing": SubscriptionStatus.TRIAL.value,
            "active": SubscriptionStatus.ACTIVE.value,
            "past_due": SubscriptionStatus.SUSPENDED.value,
            "unpaid": SubscriptionStatus.SUSPENDED.value,
            "incomplete": SubscriptionStatus.SUSPENDED.value,
            "incomplete_expired": SubscriptionStatus.CANCELLED.value,
            "canceled": SubscriptionStatus.CANCELLED.value,
            "cancelled": SubscriptionStatus.CANCELLED.value,
        }
        return mapping.get(stripe_status, SubscriptionStatus.ACTIVE.value)

    async def _sync_subscription_state(
        self,
        user_id: Optional[str],
        subscription: Optional[Dict[str, Any]],
        customer_id: Optional[str] = None,
        plan_id: Optional[str] = None,
        extra_updates: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Persist subscription details so MongoDB mirrors Stripe's lifecycle."""

        now = datetime.now(timezone.utc)
        subscription = subscription or {}

        if not plan_id:
            plan_id = subscription.get("metadata", {}).get("plan_id")

        if not user_id:
            user_id = subscription.get("metadata", {}).get("user_id")

        stripe_subscription_id = subscription.get("id")
        stripe_status = subscription.get("status")
        internal_status = self._map_stripe_status(stripe_status)

        trial_end = self._parse_timestamp(subscription.get("trial_end"))
        trial_start = self._parse_timestamp(subscription.get("trial_start"))
        current_period_start = self._parse_timestamp(subscription.get("current_period_start")) or now
        current_period_end = self._parse_timestamp(subscription.get("current_period_end")) or now

        subscription_updates: Dict[str, Any] = {
            "stripe_subscription_id": stripe_subscription_id,
            "stripe_customer_id": customer_id,
            "status": internal_status,
            "stripe_status": stripe_status,
            "trial_end_date": trial_end,
            "trial_start_date": trial_start,
            "current_period_start": current_period_start,
            "current_period_end": current_period_end,
            "updated_at": now,
        }

        if plan_id:
            subscription_updates["plan_id"] = plan_id

        if extra_updates:
            subscription_updates.update(extra_updates)

        query: Dict[str, Any] = {}
        if stripe_subscription_id:
            query["stripe_subscription_id"] = stripe_subscription_id
        if user_id:
            query.setdefault("user_id", user_id)

        if not query:
            raise HTTPException(status_code=500, detail="Unable to associate Stripe subscription with local record")

        update_document: Dict[str, Any] = {"$set": subscription_updates}
        set_on_insert: Dict[str, Any] = {}

        if user_id:
            set_on_insert["user_id"] = user_id
        if plan_id:
            set_on_insert["plan_id"] = plan_id
        if stripe_subscription_id:
            set_on_insert["stripe_subscription_id"] = stripe_subscription_id

        if set_on_insert:
            update_document["$setOnInsert"] = set_on_insert

        await self.subscriptions_collection.update_one(query, update_document, upsert=True)

        if user_id:
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
                user_updates["trial_warning_sent"] = False
            else:
                user_updates["trial_end_date"] = None
                user_updates["trial_warning_sent"] = False

            unset_fields: Dict[str, Any] = {}

            # Auto-activate and verify when a paid/trial subscription is established
            if internal_status in (SubscriptionStatus.ACTIVE.value, SubscriptionStatus.TRIAL.value):
                user_updates["is_active"] = True
                user_updates["email_verified"] = True
                unset_fields["email_verification_token"] = ""
                unset_fields["verification_token_expires"] = ""
                unset_fields["pending_expires_at"] = ""

            update_doc: Dict[str, Any] = {"$set": user_updates}
            if unset_fields:
                update_doc["$unset"] = unset_fields

            await self.users_collection.update_one(
                {"_id": ObjectId(user_id)},
                update_doc
            )

        return {
            "status": internal_status,
            "stripe_status": stripe_status,
            "trial_end": trial_end,
            "user_id": user_id,
            "stripe_subscription_id": stripe_subscription_id,
        }

    # ==================== SUBSCRIPTION MODIFICATIONS ====================

    async def change_subscription_billing_interval(
        self,
        user_id: str,
        new_billing_interval: str  # "monthly" or "yearly"
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
            raise HTTPException(status_code=400, detail="Billing interval must be 'monthly' or 'yearly'")

        try:
            # Get current subscription
            subscription = await self.subscriptions_collection.find_one({
                "user_id": user_id,
                "status": {"$in": ["active", "trial"]}
            })

            if not subscription:
                raise HTTPException(status_code=404, detail="No active subscription found")

            stripe_subscription_id = subscription.get("stripe_subscription_id")
            if not stripe_subscription_id:
                raise HTTPException(status_code=400, detail="Subscription not linked to Stripe")

            current_interval = subscription.get("billing_interval", "monthly")
            if current_interval == new_billing_interval:
                raise HTTPException(status_code=400, detail=f"Already on {new_billing_interval} billing")

            # Get the plan to find the new price ID
            plan_id = subscription.get("plan_id")
            plan = await self.plans_collection.find_one({"_id": plan_id})
            if not plan:
                raise HTTPException(status_code=404, detail="Subscription plan not found")

            # Get the new price ID
            new_price_field = f"stripe_{new_billing_interval}_price_id"
            new_price_id = plan.get(new_price_field)

            if not new_price_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"No {new_billing_interval} pricing available for this plan"
                )

            # Retrieve current Stripe subscription to get item ID
            stripe_sub = stripe.Subscription.retrieve(stripe_subscription_id)

            if not stripe_sub.get("items") or not stripe_sub["items"].get("data"):
                raise HTTPException(status_code=500, detail="Unable to retrieve subscription items")

            subscription_item_id = stripe_sub["items"]["data"][0]["id"]

            # Modify the subscription with proration
            # proration_behavior: 'create_prorations' applies credit/charge for unused time
            updated_stripe_sub = stripe.Subscription.modify(
                stripe_subscription_id,
                items=[{
                    "id": subscription_item_id,
                    "price": new_price_id,
                }],
                proration_behavior="create_prorations",
                metadata={
                    "billing_interval": new_billing_interval,
                    "changed_from": current_interval,
                    "changed_at": datetime.now(timezone.utc).isoformat()
                }
            )

            # Calculate new period end based on interval
            now = datetime.now(timezone.utc)
            if new_billing_interval == "yearly":
                from datetime import timedelta
                period_end = now + timedelta(days=365)
            else:
                if now.month == 12:
                    period_end = now.replace(year=now.year + 1, month=1)
                else:
                    period_end = now.replace(month=now.month + 1)

            # Update local subscription record
            await self.subscriptions_collection.update_one(
                {"_id": subscription["_id"]},
                {
                    "$set": {
                        "billing_interval": new_billing_interval,
                        "current_period_start": now,
                        "current_period_end": period_end,
                        "updated_at": now,
                    }
                }
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
                "proration_applied": True
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error changing billing interval: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Payment service error: {str(e)}")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error changing billing interval: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to change billing interval: {str(e)}")

    # ==================== CUSTOMER PORTAL ====================

    async def create_portal_session(
        self,
        user_id: str,
        return_url: str = None,
        flow_type: str = None
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
            customer_record = await self.stripe_customers_collection.find_one({"user_id": user_id})
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
                portal_params["flow_data"] = {
                    "type": "payment_method_update"
                }
            elif flow_type == "subscription_update":
                # Get the current subscription to specify which one to update
                subscription = await self.subscriptions_collection.find_one({"user_id": user_id})
                if subscription and subscription.get("stripe_subscription_id"):
                    portal_params["flow_data"] = {
                        "type": "subscription_update",
                        "subscription_update": {
                            "subscription": subscription["stripe_subscription_id"]
                        }
                    }

            # Create portal session
            portal_session = stripe.billing_portal.Session.create(**portal_params)

            logger.info(f"Created portal session for user {user_id} with flow_type={flow_type}")

            return {
                "url": portal_session.url
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating portal session: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Payment service error: {str(e)}")
        except Exception as e:
            logger.error(f"Error creating portal session: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error creating portal session: {str(e)}")

    # ==================== WEBHOOK HANDLING ====================

    async def handle_webhook_event(self, payload: bytes, signature: str) -> Dict[str, Any]:
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

        try:
            # Verify webhook signature
            event = stripe.Webhook.construct_event(
                payload, signature, settings.stripe_webhook_secret
            )

            event_type = event["type"]
            data = event["data"]["object"]

            logger.info(f"Processing webhook event: {event_type}")

            # Handle different event types
            if event_type == "checkout.session.completed":
                return await self._handle_checkout_completed(data)
            elif event_type == "customer.subscription.created":
                return await self._handle_subscription_created(data)
            elif event_type == "customer.subscription.updated":
                return await self._handle_subscription_updated(data)
            elif event_type == "customer.subscription.deleted":
                return await self._handle_subscription_deleted(data)
            elif event_type == "customer.subscription.trial_will_end":
                return await self._handle_subscription_trial_will_end(data)
            elif event_type == "invoice.paid":
                return await self._handle_invoice_paid(data)
            elif event_type == "invoice.payment_failed":
                return await self._handle_invoice_payment_failed(data)
            elif event_type == "payment_intent.succeeded":
                return await self._handle_payment_intent_succeeded(data)
            elif event_type == "payment_intent.payment_failed":
                return await self._handle_payment_intent_failed(data)
            elif event_type == "account.updated":
                return await self._handle_account_updated(data)
            else:
                logger.info(f"Unhandled event type: {event_type}")
                return {"status": "ignored", "event_type": event_type}

        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid signature")
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Webhook processing error: {str(e)}")

    async def _handle_checkout_completed(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """Handle successful checkout session completion"""
        try:
            user_id = session["metadata"].get("user_id")
            plan_id = session["metadata"].get("plan_id")
            subscription_id = session.get("subscription")

            if not user_id or not plan_id:
                logger.error("Missing metadata in checkout session")
                return {"status": "error", "message": "Missing metadata"}

            subscription: Optional[Dict[str, Any]] = None

            if subscription_id:
                try:
                    subscription = stripe.Subscription.retrieve(subscription_id)
                except stripe.error.StripeError as e:
                    logger.error(f"Unable to retrieve subscription {subscription_id}: {str(e)}")

            sync_result = await self._sync_subscription_state(
                user_id=user_id,
                subscription=subscription,
                customer_id=session.get("customer"),
                plan_id=plan_id,
                extra_updates={
                    "stripe_subscription_id": subscription_id,
                    "payment_status": session.get("payment_status"),
                    "stripe_checkout_session_id": session.get("id"),
                    "stripe_checkout_completed_at": datetime.now(timezone.utc),
                }
            )

            logger.info(
                "Checkout completed for user %s, subscription %s (status: %s)",
                user_id,
                subscription_id,
                sync_result.get("stripe_status") or sync_result.get("status")
            )
            return {"status": "success", "user_id": user_id, "subscription_id": subscription_id}

        except Exception as e:
            logger.error(f"Error handling checkout completed: {str(e)}")
            return {"status": "error", "message": str(e)}

    async def _handle_subscription_created(self, subscription: Dict[str, Any]) -> Dict[str, Any]:
        """Handle new subscription creation"""
        try:
            result = await self._sync_subscription_state(
                user_id=subscription.get("metadata", {}).get("user_id"),
                subscription=subscription,
                customer_id=subscription.get("customer")
            )

            logger.info(
                "Subscription %s created (user=%s, status=%s)",
                subscription.get("id"),
                result.get("user_id"),
                result.get("stripe_status") or result.get("status")
            )
            return {"status": "success", "user_id": result.get("user_id")}

        except Exception as e:
            logger.error(f"Error handling subscription created: {str(e)}")
            return {"status": "error", "message": str(e)}

    async def _handle_subscription_updated(self, subscription: Dict[str, Any]) -> Dict[str, Any]:
        """Handle subscription updates"""
        try:
            result = await self._sync_subscription_state(
                user_id=subscription.get("metadata", {}).get("user_id"),
                subscription=subscription,
                customer_id=subscription.get("customer")
            )

            logger.info(
                "Subscription %s updated (status=%s)",
                subscription.get("id"),
                result.get("stripe_status") or result.get("status")
            )
            return {"status": "success", "subscription_id": subscription.get("id")}

        except Exception as e:
            logger.error(f"Error handling subscription updated: {str(e)}")
            return {"status": "error", "message": str(e)}

    async def _handle_subscription_deleted(self, subscription: Dict[str, Any]) -> Dict[str, Any]:
        """Handle subscription cancellation/deletion"""
        try:
            stripe_sub_id = subscription["id"]

            result = await self._sync_subscription_state(
                user_id=subscription.get("metadata", {}).get("user_id"),
                subscription=subscription,
                customer_id=subscription.get("customer"),
                extra_updates={
                    "status": SubscriptionStatus.CANCELLED.value,
                    "cancelled_at": datetime.now(timezone.utc),
                }
            )

            logger.info(
                "Subscription %s cancelled (user=%s)",
                stripe_sub_id,
                result.get("user_id")
            )
            return {"status": "success", "subscription_id": stripe_sub_id}

        except Exception as e:
            logger.error(f"Error handling subscription deleted: {str(e)}")
            return {"status": "error", "message": str(e)}

    async def _handle_subscription_trial_will_end(self, subscription: Dict[str, Any]) -> Dict[str, Any]:
        """Record trial end reminders for alignment with internal notifications."""

        try:
            result = await self._sync_subscription_state(
                user_id=subscription.get("metadata", {}).get("user_id"),
                subscription=subscription,
                customer_id=subscription.get("customer"),
                extra_updates={
                    "trial_will_end_notified_at": datetime.now(timezone.utc)
                }
            )

            logger.info(
                "Trial will end soon for subscription %s (user=%s)",
                subscription.get("id"),
                result.get("user_id")
            )
            return {"status": "success", "subscription_id": subscription.get("id")}

        except Exception as e:
            logger.error(f"Error handling subscription trial end notice: {str(e)}")
            return {"status": "error", "message": str(e)}

    async def _handle_invoice_paid(self, invoice: Dict[str, Any]) -> Dict[str, Any]:
        """Handle successful invoice payment"""
        try:
            subscription_id = invoice.get("subscription")
            if not subscription_id:
                return {"status": "ignored"}

            subscription = None
            try:
                subscription = stripe.Subscription.retrieve(subscription_id)
            except stripe.error.StripeError as e:
                logger.error(f"Unable to refresh subscription {subscription_id} during invoice.paid: {str(e)}")

            if subscription:
                await self._sync_subscription_state(
                    user_id=subscription.get("metadata", {}).get("user_id"),
                    subscription=subscription,
                    customer_id=subscription.get("customer"),
                    extra_updates={
                        "payment_status": "paid",
                        "last_payment_date": datetime.now(timezone.utc),
                    }
                )
            else:
                await self.subscriptions_collection.update_one(
                    {"stripe_subscription_id": subscription_id},
                    {"$set": {
                        "payment_status": "paid",
                        "last_payment_date": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc)
                    }}
                )

            logger.info(f"Invoice paid for subscription {subscription_id}")

            # Send payment success notification to user
            await self._send_payment_notification(
                subscription_id=subscription_id,
                notification_type="payment_success",
                invoice=invoice
            )

            return {"status": "success", "subscription_id": subscription_id}

        except Exception as e:
            logger.error(f"Error handling invoice paid: {str(e)}")
            return {"status": "error", "message": str(e)}

    async def _handle_invoice_payment_failed(self, invoice: Dict[str, Any]) -> Dict[str, Any]:
        """Handle failed invoice payment"""
        try:
            subscription_id = invoice.get("subscription")
            if not subscription_id:
                return {"status": "ignored"}

            subscription = None
            try:
                subscription = stripe.Subscription.retrieve(subscription_id)
            except stripe.error.StripeError as e:
                logger.error(f"Unable to refresh subscription {subscription_id} during invoice.payment_failed: {str(e)}")

            if subscription:
                await self._sync_subscription_state(
                    user_id=subscription.get("metadata", {}).get("user_id"),
                    subscription=subscription,
                    customer_id=subscription.get("customer"),
                    extra_updates={
                        "payment_status": "past_due",
                        "last_payment_attempt": datetime.now(timezone.utc),
                    }
                )
            else:
                await self.subscriptions_collection.update_one(
                    {"stripe_subscription_id": subscription_id},
                    {"$set": {
                        "payment_status": "past_due",
                        "last_payment_attempt": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc)
                    }}
                )

            logger.warning(f"Invoice payment failed for subscription {subscription_id}")

            # Send payment failed notification to user
            await self._send_payment_notification(
                subscription_id=subscription_id,
                notification_type="payment_failed",
                invoice=invoice
            )

            return {"status": "success", "subscription_id": subscription_id}

        except Exception as e:
            logger.error(f"Error handling invoice payment failed: {str(e)}")
            return {"status": "error", "message": str(e)}

    async def _handle_payment_intent_succeeded(self, payment_intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle successful payment intent - updates payment_requests collection
        for couple payments created by planners, and handles autopilot scheduled payments.
        """
        try:
            payment_intent_id = payment_intent.get("id")
            if not payment_intent_id:
                return {"status": "ignored", "reason": "no payment_intent_id"}

            # Get receipt URL from charges
            receipt_url = None
            if payment_intent.get("charges", {}).get("data"):
                receipt_url = payment_intent["charges"]["data"][0].get("receipt_url")

            # Check if this is an autopilot scheduled payment
            metadata = payment_intent.get("metadata", {})
            if metadata.get("payment_type") == "scheduled":
                from app.services.autopilot_service import autopilot_service
                await autopilot_service.handle_payment_succeeded(
                    payment_intent_id=payment_intent_id,
                    receipt_url=receipt_url
                )
                logger.info(f"Autopilot scheduled payment {payment_intent_id} succeeded")
                return {"status": "success", "payment_intent_id": payment_intent_id, "type": "scheduled"}

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
                        "payment_method_type": payment_intent.get("payment_method_types", [None])[0]
                    }
                }
            )

            if result.modified_count > 0:
                logger.info(f"Payment request {payment_intent_id} marked as succeeded")

                # Notify planner about the payment
                await self._notify_planner_payment_received(
                    payment_intent_id=payment_intent_id,
                    amount=payment_intent.get("amount_received", 0) / 100,
                    payer_name=metadata.get("customer_name", "Customer")
                )

                return {"status": "success", "payment_intent_id": payment_intent_id}
            else:
                # This payment intent might not be from our payment requests (could be subscription)
                logger.debug(f"No payment request found for {payment_intent_id} - may be a subscription payment")
                return {"status": "ignored", "reason": "not_a_payment_request"}

        except Exception as e:
            logger.error(f"Error handling payment intent succeeded: {str(e)}")
            return {"status": "error", "message": str(e)}

    async def _handle_payment_intent_failed(self, payment_intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle failed payment intent - handles autopilot scheduled payment failures
        with retry logic.
        """
        try:
            payment_intent_id = payment_intent.get("id")
            if not payment_intent_id:
                return {"status": "ignored", "reason": "no payment_intent_id"}

            # Get error details
            last_error = payment_intent.get("last_payment_error", {})
            error_code = last_error.get("code", "unknown")
            error_message = last_error.get("message", "Payment failed")

            # Check if this is an autopilot scheduled payment
            metadata = payment_intent.get("metadata", {})
            if metadata.get("payment_type") == "scheduled":
                from app.services.autopilot_service import autopilot_service
                await autopilot_service.handle_payment_failed(
                    payment_intent_id=payment_intent_id,
                    error_code=error_code,
                    error_message=error_message
                )
                logger.info(f"Autopilot scheduled payment {payment_intent_id} failed: {error_message}")
                return {"status": "handled", "payment_intent_id": payment_intent_id, "type": "scheduled"}

            # Update payment request status for non-autopilot payments
            payment_requests_collection = mongo.db["payment_requests"]
            result = await payment_requests_collection.update_one(
                {"payment_intent_id": payment_intent_id},
                {
                    "$set": {
                        "status": "failed",
                        "failure_reason": error_message,
                        "failure_code": error_code,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )

            if result.modified_count > 0:
                logger.info(f"Payment request {payment_intent_id} marked as failed")
                return {"status": "handled", "payment_intent_id": payment_intent_id}
            else:
                logger.debug(f"No payment request found for failed {payment_intent_id}")
                return {"status": "ignored", "reason": "not_a_payment_request"}

        except Exception as e:
            logger.error(f"Error handling payment intent failed: {str(e)}")
            return {"status": "error", "message": str(e)}

    async def _handle_account_updated(self, account: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle Stripe Connect account updates - syncs onboarding status
        when account.updated event fires (e.g., after user completes onboarding).
        """
        try:
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
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
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
                    "payouts_enabled": payouts_enabled
                }
            else:
                logger.warning(f"No user found with stripe_connect_id: {account_id}")
                return {"status": "ignored", "reason": "user_not_found"}

        except Exception as e:
            logger.error(f"Error handling account updated: {str(e)}")
            return {"status": "error", "message": str(e)}

    # ==================== PAYMENT NOTIFICATIONS ====================

    async def _send_payment_notification(
        self,
        subscription_id: str,
        notification_type: str,
        invoice: Dict[str, Any] = None
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
            subscription = await self.subscriptions_collection.find_one({
                "stripe_subscription_id": subscription_id
            })

            if not subscription:
                logger.warning(f"No subscription found for notification: {subscription_id}")
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
            user_name = user.get("first_name") or user.get("company_name") or user_email.split("@")[0]

            # Get plan details
            plan = None
            if subscription.get("plan_id"):
                try:
                    if ObjectId.is_valid(subscription["plan_id"]):
                        plan = await self.plans_collection.find_one({"_id": ObjectId(subscription["plan_id"])})
                    else:
                        plan = await self.plans_collection.find_one({"_id": subscription["plan_id"]})
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
                currency=currency
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
                    invoice_pdf=invoice.get("invoice_pdf") if invoice else None
                )
            else:  # payment_failed
                subject = f"Payment Failed - Action Required"
                html_content = self._render_payment_failed_email(
                    user_name=user_name,
                    plan_name=plan_name,
                    amount=amount,
                    currency=currency
                )

            # Send the email
            if not getattr(self.email_service, "configured", False):
                logger.warning("Email service not configured, skipping email notification")
                return

            result = await self.email_service.send_email(
                to_email=user_email,
                subject=subject,
                html_content=html_content,
                email_type="billing_notification"
            )

            if result.get("success"):
                logger.info(f"Payment notification sent to {user_email} for {notification_type}")
            else:
                logger.error(f"Failed to send payment notification: {result.get('error')}")

        except Exception as e:
            # Don't fail the webhook if notification fails
            logger.error(f"Error sending payment notification: {str(e)}")

    async def _create_in_app_notification(
        self,
        user_id: str,
        user_email: str,
        notification_type: str,
        plan_name: str,
        amount: float,
        currency: str
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
                    "user_id": user_email,  # Target specific user by email
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
                        "plan_name": plan_name
                    }
                }
            else:  # payment_failed
                notification = {
                    "_id": ObjectId(),
                    "title": "Payment Failed",
                    "message": f"We couldn't process your payment of ${amount:.2f} {currency} for {plan_name}. Please update your payment method.",
                    "type": "billing",
                    "target_audience": "specific_user",
                    "user_id": user_email,  # Target specific user by email
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
                        "action_url": "/admin/planner/billing"
                    }
                }

            await notifications_collection.insert_one(notification)
            logger.info(f"Created in-app {notification_type} notification for user {user_email}")

        except Exception as e:
            logger.error(f"Error creating in-app notification: {str(e)}")

    async def _notify_planner_payment_received(
        self,
        payment_intent_id: str,
        amount: float,
        payer_name: str
    ):
        """Notify planner about a received payment from couple/vendor"""
        try:
            # Get the payment request to find the wedding and planner
            payment_requests_collection = mongo.db["payment_requests"]
            payment_request = await payment_requests_collection.find_one({
                "payment_intent_id": payment_intent_id
            })

            if not payment_request:
                logger.debug(f"No payment request found for {payment_intent_id}")
                return

            wedding_id = payment_request.get("wedding_id")
            planner_email = payment_request.get("created_by")

            if not planner_email:
                # Try to get planner from wedding
                if wedding_id:
                    wedding = await mongo.db["weddings"].find_one({"_id": wedding_id})
                    if wedding:
                        planner_email = wedding.get("assigned_planner_email")

            if not planner_email:
                logger.debug(f"No planner found for payment {payment_intent_id}")
                return

            # Import here to avoid circular imports
            from app.services.planner_notification_service import planner_notification_service

            await planner_notification_service.notify_payment_received(
                planner_id=planner_email,
                wedding_id=wedding_id or "",
                amount=amount,
                payer_name=payer_name,
                payment_id=payment_intent_id
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
        invoice_pdf: Optional[str] = None
    ) -> str:
        """Render payment success email HTML"""
        download_section = ""
        if invoice_pdf:
            download_section = f'''
                <tr>
                  <td style="padding:20px 40px 0;">
                    <a href="{invoice_pdf}" style="display:inline-block;padding:12px 24px;background:#2563eb;color:#ffffff;text-decoration:none;border-radius:8px;font-size:14px;font-weight:500;">Download Invoice PDF</a>
                  </td>
                </tr>
            '''

        return f'''
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
                    <p style="margin:0 0 24px;font-size:16px;line-height:1.6;">Hi {user_name},</p>
                    <p style="margin:0 0 24px;font-size:16px;line-height:1.6;color:#475569;">We've received your payment. Here are the details:</p>

                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;border-radius:12px;padding:20px;margin-bottom:24px;">
                      <tr>
                        <td style="padding:8px 16px;">
                          <p style="margin:0;font-size:14px;color:#64748b;">Plan</p>
                          <p style="margin:4px 0 0;font-size:16px;font-weight:500;color:#0f172a;">{plan_name}</p>
                        </td>
                      </tr>
                      <tr>
                        <td style="padding:8px 16px;">
                          <p style="margin:0;font-size:14px;color:#64748b;">Amount</p>
                          <p style="margin:4px 0 0;font-size:16px;font-weight:500;color:#0f172a;">${amount:.2f} {currency}</p>
                        </td>
                      </tr>
                      <tr>
                        <td style="padding:8px 16px;">
                          <p style="margin:0;font-size:14px;color:#64748b;">Date</p>
                          <p style="margin:4px 0 0;font-size:16px;font-weight:500;color:#0f172a;">{invoice_date}</p>
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
        '''

    def _render_payment_failed_email(
        self,
        user_name: str,
        plan_name: str,
        amount: float,
        currency: str
    ) -> str:
        """Render payment failed email HTML"""
        return f'''
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
                    <p style="margin:0 0 24px;font-size:16px;line-height:1.6;">Hi {user_name},</p>
                    <p style="margin:0 0 24px;font-size:16px;line-height:1.6;color:#475569;">We were unable to process your payment of <strong>${amount:.2f} {currency}</strong> for your <strong>{plan_name}</strong> subscription.</p>

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
                          <a href="{settings.frontend_url or ''}/admin/planner/billing" style="display:inline-block;padding:14px 28px;color:#ffffff;text-decoration:none;font-size:14px;font-weight:500;">Update Payment Method</a>
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
        '''

    # ==================== CONNECT / MARKETPLACE ====================

    async def create_connected_account(self, user_id: str, email: str, country: str = "US") -> str:
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
                metadata={"user_id": user_id}
            )

            # Save account ID to user record
            await self.users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"stripe_connect_id": account.id, "updated_at": datetime.now(timezone.utc)}}
            )

            logger.info(f"Created Stripe connected account {account.id} for user {user_id}")
            return account.id

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating connected account: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Stripe Connect error: {str(e)}")

    def create_account_link(self, account_id: str, refresh_url: str, return_url: str) -> str:
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
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating account link: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Stripe Connect error: {str(e)}")

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
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error retrieving account: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Stripe Connect error: {str(e)}")

    # ==================== PAYMENT COLLECTION FOR COUPLES ====================

    def create_payment_intent_for_couple(
        self,
        amount: float,
        currency: str = "usd",
        wedding_id: str = None,
        description: str = None,
        metadata: Dict[str, Any] = None,
        destination_account_id: str = None
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
                create_kwargs["transfer_data"] = {
                    "destination": destination_account_id
                }
                # Optional: Add application_fee_amount here if the platform takes a cut
                # create_kwargs["application_fee_amount"] = int(amount * 100 * 0.01) # 1% fee

            payment_intent = stripe.PaymentIntent.create(**create_kwargs)

            logger.info(f"Created payment intent {payment_intent.id} for amount {amount}")

            return {
                "payment_intent_id": payment_intent.id,
                "client_secret": payment_intent.client_secret,
                "amount": amount,
                "currency": currency,
                "status": payment_intent.status
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating payment intent: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Payment service error: {str(e)}")
        except Exception as e:
            logger.error(f"Error creating payment intent: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error creating payment intent: {str(e)}")

    async def create_vendor_payment_intent(
        self,
        sender_user_id: str,
        vendor_connect_id: str,
        amount: float,
        currency: str = "usd",
        description: str = None
    ) -> Dict[str, Any]:
        """
        Create a payment intent for a Planner to pay a Vendor.
        The Planner pays (as a customer) and funds go to Vendor (connected account).
        """
        self._ensure_stripe_enabled()

        try:
            # Ensure sender has a customer ID
            user = await self.users_collection.find_one({"_id": ObjectId(sender_user_id)})
            customer_id = await self.get_or_create_customer(sender_user_id, user["email"], user.get("full_name"))

            payment_intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),
                currency=currency.lower(),
                customer=customer_id,
                description=description or f"Payment to vendor",
                transfer_data={
                    "destination": vendor_connect_id
                },
                metadata={
                    "sender_user_id": sender_user_id,
                    "vendor_connect_id": vendor_connect_id
                },
                automatic_payment_methods={"enabled": True},
            )

            return {
                "payment_intent_id": payment_intent.id,
                "client_secret": payment_intent.client_secret,
                "amount": amount,
                "currency": currency,
                "status": payment_intent.status
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating vendor payment: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Payment service error: {str(e)}")


# Create singleton instance
stripe_service = StripeService()
