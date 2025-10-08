"""
Stripe Payment Service for handling subscription payments and customer management
"""
import stripe
from fastapi import HTTPException
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.core.settings import settings
from app.core.database import mongo
from bson import ObjectId
import logging

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
        self.users_collection = mongo.db["users"]
        self.plans_collection = mongo.db["subscription_plans"]
        self.stripe_customers_collection = mongo.db["stripe_customers"]

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

    def get_or_create_customer(self, user_id: str, email: str, name: Optional[str] = None) -> str:
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
            customer_record = self.stripe_customers_collection.find_one({"user_id": user_id})

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
            self.stripe_customers_collection.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "user_id": user_id,
                        "stripe_customer_id": customer.id,
                        "email": email,
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
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

    def create_checkout_session(
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
            user = self.users_collection.find_one({"_id": ObjectId(user_id)})
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            # Get subscription plan
            plan = self.plans_collection.find_one({"_id": plan_id})
            if not plan:
                raise HTTPException(status_code=404, detail="Subscription plan not found")

            # Get or create Stripe customer
            customer_id = self.get_or_create_customer(
                user_id=user_id,
                email=user["email"],
                name=user.get("full_name") or user.get("email")
            )

            # Determine price based on billing interval
            price_amount = plan.get(f"price_{billing_interval}", plan.get("price_monthly", 0))

            # Create Stripe price object if not exists
            # Note: In production, you should create prices in Stripe Dashboard
            # and store price IDs in your database
            stripe_price = stripe.Price.create(
                unit_amount=int(price_amount * 100),  # Convert to cents
                currency="usd",
                recurring={
                    "interval": "month" if billing_interval == "monthly" else "year"
                },
                product_data={
                    "name": f"{plan['name']} Plan",
                    "description": plan.get("description", ""),
                },
            )

            # Default URLs if not provided
            if not success_url:
                success_url = f"{settings.frontend_url}/admin/billing/success?session_id={{CHECKOUT_SESSION_ID}}"
            if not cancel_url:
                cancel_url = f"{settings.frontend_url}/admin/billing/cancelled"

            # Prepare subscription data
            subscription_data = {
                "metadata": {
                    "user_id": user_id,
                    "plan_id": plan_id,
                    "billing_interval": billing_interval
                }
            }

            if trial_days > 0:
                subscription_data["trial_period_days"] = trial_days

            # Create checkout session
            checkout_session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=["card"],
                line_items=[{
                    "price": stripe_price.id,
                    "quantity": 1,
                }],
                mode="subscription",
                success_url=success_url,
                cancel_url=cancel_url,
                subscription_data=subscription_data,
                allow_promotion_codes=True,
                billing_address_collection="auto",
                customer_update={
                    "address": "auto",
                    "name": "auto"
                }
            )

            # Save session reference
            self.subscriptions_collection.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "stripe_checkout_session_id": checkout_session.id,
                        "stripe_checkout_created_at": datetime.utcnow()
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

    # ==================== CUSTOMER PORTAL ====================

    def create_portal_session(self, user_id: str, return_url: str = None) -> Dict[str, str]:
        """
        Create a Stripe Customer Portal session for subscription management

        Args:
            user_id: Internal user ID
            return_url: URL to return to after portal session

        Returns:
            Dictionary with portal session URL
        """
        self._ensure_stripe_enabled()

        try:
            # Get Stripe customer ID
            customer_record = self.stripe_customers_collection.find_one({"user_id": user_id})
            if not customer_record or not customer_record.get("stripe_customer_id"):
                raise HTTPException(status_code=404, detail="Stripe customer not found")

            customer_id = customer_record["stripe_customer_id"]

            # Default return URL if not provided
            if not return_url:
                return_url = f"{settings.frontend_url}/admin/billing"

            # Create portal session
            portal_session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url,
            )

            logger.info(f"Created portal session for user {user_id}")

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

    def handle_webhook_event(self, payload: bytes, signature: str) -> Dict[str, Any]:
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
                return self._handle_checkout_completed(data)
            elif event_type == "customer.subscription.created":
                return self._handle_subscription_created(data)
            elif event_type == "customer.subscription.updated":
                return self._handle_subscription_updated(data)
            elif event_type == "customer.subscription.deleted":
                return self._handle_subscription_deleted(data)
            elif event_type == "invoice.paid":
                return self._handle_invoice_paid(data)
            elif event_type == "invoice.payment_failed":
                return self._handle_invoice_payment_failed(data)
            else:
                logger.info(f"Unhandled event type: {event_type}")
                return {"status": "ignored", "event_type": event_type}

        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid signature")
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Webhook processing error: {str(e)}")

    def _handle_checkout_completed(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """Handle successful checkout session completion"""
        try:
            user_id = session["metadata"].get("user_id")
            plan_id = session["metadata"].get("plan_id")
            subscription_id = session.get("subscription")

            if not user_id or not plan_id:
                logger.error("Missing metadata in checkout session")
                return {"status": "error", "message": "Missing metadata"}

            # Update subscription record
            self.subscriptions_collection.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "stripe_subscription_id": subscription_id,
                        "stripe_customer_id": session.get("customer"),
                        "status": "active",
                        "payment_status": "paid",
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            # Update user record
            self.users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {
                    "$set": {
                        "subscription_status": "active",
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            logger.info(f"Checkout completed for user {user_id}, subscription {subscription_id}")
            return {"status": "success", "user_id": user_id, "subscription_id": subscription_id}

        except Exception as e:
            logger.error(f"Error handling checkout completed: {str(e)}")
            return {"status": "error", "message": str(e)}

    def _handle_subscription_created(self, subscription: Dict[str, Any]) -> Dict[str, Any]:
        """Handle new subscription creation"""
        try:
            user_id = subscription["metadata"].get("user_id")
            if not user_id:
                logger.error("Missing user_id in subscription metadata")
                return {"status": "error", "message": "Missing user_id"}

            self.subscriptions_collection.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "stripe_subscription_id": subscription["id"],
                        "status": "active" if subscription["status"] == "active" else "trial",
                        "current_period_start": datetime.fromtimestamp(subscription["current_period_start"]),
                        "current_period_end": datetime.fromtimestamp(subscription["current_period_end"]),
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            logger.info(f"Subscription created for user {user_id}")
            return {"status": "success", "user_id": user_id}

        except Exception as e:
            logger.error(f"Error handling subscription created: {str(e)}")
            return {"status": "error", "message": str(e)}

    def _handle_subscription_updated(self, subscription: Dict[str, Any]) -> Dict[str, Any]:
        """Handle subscription updates"""
        try:
            stripe_sub_id = subscription["id"]

            # Find subscription by Stripe subscription ID
            sub_record = self.subscriptions_collection.find_one({"stripe_subscription_id": stripe_sub_id})
            if not sub_record:
                logger.warning(f"Subscription {stripe_sub_id} not found in database")
                return {"status": "not_found"}

            # Update subscription status and period
            self.subscriptions_collection.update_one(
                {"stripe_subscription_id": stripe_sub_id},
                {
                    "$set": {
                        "status": subscription["status"],
                        "current_period_start": datetime.fromtimestamp(subscription["current_period_start"]),
                        "current_period_end": datetime.fromtimestamp(subscription["current_period_end"]),
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            # Update user status
            if sub_record.get("user_id"):
                self.users_collection.update_one(
                    {"_id": ObjectId(sub_record["user_id"])},
                    {
                        "$set": {
                            "subscription_status": subscription["status"],
                            "updated_at": datetime.utcnow()
                        }
                    }
                )

            logger.info(f"Subscription {stripe_sub_id} updated to status {subscription['status']}")
            return {"status": "success", "subscription_id": stripe_sub_id}

        except Exception as e:
            logger.error(f"Error handling subscription updated: {str(e)}")
            return {"status": "error", "message": str(e)}

    def _handle_subscription_deleted(self, subscription: Dict[str, Any]) -> Dict[str, Any]:
        """Handle subscription cancellation/deletion"""
        try:
            stripe_sub_id = subscription["id"]

            # Update subscription status
            result = self.subscriptions_collection.update_one(
                {"stripe_subscription_id": stripe_sub_id},
                {
                    "$set": {
                        "status": "cancelled",
                        "cancelled_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            if result.matched_count > 0:
                # Get subscription to find user
                sub_record = self.subscriptions_collection.find_one({"stripe_subscription_id": stripe_sub_id})
                if sub_record and sub_record.get("user_id"):
                    self.users_collection.update_one(
                        {"_id": ObjectId(sub_record["user_id"])},
                        {
                            "$set": {
                                "subscription_status": "cancelled",
                                "updated_at": datetime.utcnow()
                            }
                        }
                    )

                logger.info(f"Subscription {stripe_sub_id} cancelled")
                return {"status": "success", "subscription_id": stripe_sub_id}
            else:
                logger.warning(f"Subscription {stripe_sub_id} not found for cancellation")
                return {"status": "not_found"}

        except Exception as e:
            logger.error(f"Error handling subscription deleted: {str(e)}")
            return {"status": "error", "message": str(e)}

    def _handle_invoice_paid(self, invoice: Dict[str, Any]) -> Dict[str, Any]:
        """Handle successful invoice payment"""
        try:
            subscription_id = invoice.get("subscription")
            if not subscription_id:
                return {"status": "ignored"}

            # Update subscription payment status
            self.subscriptions_collection.update_one(
                {"stripe_subscription_id": subscription_id},
                {
                    "$set": {
                        "payment_status": "paid",
                        "last_payment_date": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            logger.info(f"Invoice paid for subscription {subscription_id}")
            return {"status": "success", "subscription_id": subscription_id}

        except Exception as e:
            logger.error(f"Error handling invoice paid: {str(e)}")
            return {"status": "error", "message": str(e)}

    def _handle_invoice_payment_failed(self, invoice: Dict[str, Any]) -> Dict[str, Any]:
        """Handle failed invoice payment"""
        try:
            subscription_id = invoice.get("subscription")
            if not subscription_id:
                return {"status": "ignored"}

            # Update subscription payment status
            self.subscriptions_collection.update_one(
                {"stripe_subscription_id": subscription_id},
                {
                    "$set": {
                        "payment_status": "past_due",
                        "last_payment_attempt": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            logger.warning(f"Invoice payment failed for subscription {subscription_id}")
            return {"status": "success", "subscription_id": subscription_id}

        except Exception as e:
            logger.error(f"Error handling invoice payment failed: {str(e)}")
            return {"status": "error", "message": str(e)}

    # ==================== PAYMENT COLLECTION FOR COUPLES ====================

    def create_payment_intent_for_couple(
        self,
        amount: float,
        currency: str = "usd",
        wedding_id: str = None,
        description: str = None,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Create a payment intent for collecting payment from couples
        This allows wedding planners to collect payments from their clients

        Args:
            amount: Amount in dollars
            currency: Currency code (default USD)
            wedding_id: Associated wedding ID
            description: Payment description
            metadata: Additional metadata

        Returns:
            Payment intent details including client_secret for frontend
        """
        self._ensure_stripe_enabled()

        try:
            payment_metadata = metadata or {}
            if wedding_id:
                payment_metadata["wedding_id"] = wedding_id

            payment_intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Convert to cents
                currency=currency.lower(),
                description=description or "Wedding service payment",
                metadata=payment_metadata,
                automatic_payment_methods={"enabled": True},
            )

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


# Create singleton instance
stripe_service = StripeService()
