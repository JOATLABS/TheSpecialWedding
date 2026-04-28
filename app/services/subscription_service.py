import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import stripe
from fastapi import HTTPException

from app.core.database import mongo
from app.services.couple_lifecycle_service import (
    COUPLE_PORTAL_STATE_REVOKED,
    couple_lifecycle_service,
)
from app.services.planner_access_lifecycle_service import (
    planner_access_lifecycle_service,
)
from app.services.stripe_service import stripe_service
from app.utils.id_utils import to_object_id
from app.utils.planner_ownership import build_wedding_owner_query, normalize_query_id

logger = logging.getLogger(__name__)


class SubscriptionService:
    def __init__(self):
        self.plans_collection = mongo.db["subscription_plans"]
        self.subscriptions_collection = mongo.db["user_subscriptions"]
        self.usage_collection = mongo.db["usage_tracking"]
        self.users_collection = mongo.get_users_collection()
        self.weddings_collection = mongo.db["weddings"]

    # Subscription Plan Management (ROOT_ADMIN only)
    async def create_plan(self, plan_data: dict, creator_email: str) -> dict:
        """Create a new subscription plan"""
        try:
            plan_data["_id"] = f"plan_{plan_data['name'].lower().replace(' ', '_')}"
            plan_data["created_by"] = creator_email
            plan_data["created_at"] = datetime.now(timezone.utc)
            plan_data["updated_at"] = datetime.now(timezone.utc)
            # Check if plan ID already exists
            existing = await self.plans_collection.find_one({"_id": plan_data["_id"]})
            if existing:
                raise HTTPException(
                    status_code=400, detail="Plan with this name already exists"
                )

            # Sync to Stripe first
            try:
                stripe_data = stripe_service.sync_plan_to_stripe(plan_data)
                plan_data.update(stripe_data)
            except Exception as e:
                # Log but don't block creation if stripe fails?
                # Better to fail so we don't have inconsistent state
                raise HTTPException(
                    status_code=500, detail=f"Failed to sync plan to Stripe: {str(e)}"
                )

            await self.plans_collection.insert_one(plan_data)
            return {
                "message": "Subscription plan created successfully",
                "plan_id": plan_data["_id"],
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error creating subscription plan: {str(e)}"
            )

    async def list_plans(self, include_inactive: bool = False) -> List[dict]:
        """List all subscription plans"""
        try:
            query = {} if include_inactive else {"is_active": True}
            # Safety cap: platforms typically have <500 subscription plans
            MAX_PLANS = 500
            plans = await self.plans_collection.find(query).to_list(length=MAX_PLANS)
            # Sort by sort_order or display_order (plans may use either field)
            plans.sort(key=lambda p: p.get("sort_order", p.get("display_order", 999)))
            return plans
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error listing plans: {str(e)}"
            )

    async def get_plan(self, plan_id: str) -> dict:
        """Get subscription plan by ID"""
        try:
            plan = await self.plans_collection.find_one({"_id": plan_id})
            if not plan:
                raise HTTPException(
                    status_code=404, detail="Subscription plan not found"
                )
            return plan
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error retrieving plan: {str(e)}"
            )

    async def update_plan(self, plan_id: str, update_data: dict) -> dict:
        """Update subscription plan"""
        try:
            # Remove protected fields
            protected_fields = ["_id", "created_at", "created_by"]
            for field in protected_fields:
                update_data.pop(field, None)

            update_data["updated_at"] = datetime.now(timezone.utc)

            # Retrieve existing plan to merge with update data for Stripe sync
            existing_plan = await self.plans_collection.find_one({"_id": plan_id})
            if not existing_plan:
                raise HTTPException(
                    status_code=404, detail="Subscription plan not found"
                )

            merged_plan = {**existing_plan, **update_data}

            # Sync to Stripe
            try:
                stripe_data = stripe_service.sync_plan_to_stripe(merged_plan)
                update_data.update(stripe_data)
            except Exception as e:
                raise HTTPException(
                    status_code=500, detail=f"Failed to sync plan to Stripe: {str(e)}"
                )

            await self.plans_collection.update_one(
                {"_id": plan_id}, {"$set": update_data}
            )

            return {"message": "Subscription plan updated successfully"}

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error updating plan: {str(e)}"
            )

    async def delete_plan(self, plan_id: str) -> dict:
        """Delete subscription plan (only if no active subscriptions)"""
        try:
            # Check if any users have active subscriptions to this plan
            active_subs = await self.subscriptions_collection.count_documents(
                {"plan_id": plan_id, "status": {"$in": ["active", "trial"]}}
            )

            if active_subs > 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot delete plan: {active_subs} active subscriptions exist",
                )

            # Get the plan first to retrieve Stripe product ID
            plan = await self.plans_collection.find_one({"_id": plan_id})
            if not plan:
                raise HTTPException(
                    status_code=404, detail="Subscription plan not found"
                )

            # Archive the Stripe product (deactivate, don't delete)
            stripe_product_id = plan.get("stripe_product_id")
            if stripe_product_id:
                try:
                    stripe_service.archive_stripe_product(stripe_product_id)
                except Exception as e:
                    # Log but don't block deletion - Stripe sync can be fixed manually
                    logger.warning(
                        f"Failed to archive Stripe product {stripe_product_id}: {e}"
                    )

            result = await self.plans_collection.delete_one({"_id": plan_id})

            if result.deleted_count == 0:
                raise HTTPException(
                    status_code=404, detail="Subscription plan not found"
                )

            return {
                "message": "Subscription plan deleted successfully",
                "stripe_archived": bool(stripe_product_id),
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error deleting plan: {str(e)}"
            )

    # User Subscription Management
    async def assign_subscription(
        self,
        user_id: str,
        plan_id: str,
        billing_interval: str = "monthly",
        trial_days: int = 0,
        creator_email: str = "",
        existing_stripe_subscription_id: str = None,
        existing_stripe_customer_id: str = None,
    ) -> dict:
        """Assign subscription plan to user"""
        try:
            # Verify user exists
            user = await self.users_collection.find_one(
                {"_id": to_object_id(user_id, "user_id")}
            )
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            # Verify plan exists
            plan = await self.get_plan(plan_id)

            # Check if user already has an active subscription
            existing_sub = await self.subscriptions_collection.find_one(
                {"user_id": user_id, "status": {"$in": ["active", "trial"]}}
            )

            if existing_sub:
                raise HTTPException(
                    status_code=400, detail="User already has an active subscription"
                )

            # Create subscription
            now = datetime.now(timezone.utc)
            trial_end = now + timedelta(days=trial_days) if trial_days > 0 else now

            if billing_interval == "yearly":
                period_end = now + timedelta(days=365)
            else:  # monthly
                # Calculate next month
                if now.month == 12:
                    period_end = now.replace(year=now.year + 1, month=1)
                else:
                    period_end = now.replace(month=now.month + 1)
            # Create plan snapshot for grandfathering - locks limits at subscription time
            # User keeps these limits even if plan is later modified
            plan_snapshot = {
                "plan_name": plan.get("name"),
                "max_weddings": plan.get("max_weddings", 1),
                "max_guests_per_wedding": plan.get("max_guests_per_wedding", 100),
                "ai_credits_monthly": plan.get("ai_credits_monthly", 10),
                "ai_credit_overage_price": plan.get(
                    "ai_credit_overage_price",
                    self.DEFAULT_AI_CREDIT_OVERAGE_PRICE_USD,
                ),
                "storage_gb": plan.get("storage_gb", 1),
                "staff_seats": plan.get("staff_seats", 0),
                "features": plan.get("features", {}),
                "price_monthly": plan.get("price_monthly", 0),
                "price_yearly": plan.get("price_yearly"),
                "stripe_price_id_monthly": plan.get("stripe_price_id_monthly"),
                "stripe_price_id_yearly": plan.get("stripe_price_id_yearly"),
                "snapshot_date": now,
            }

            # Reuse existing Stripe subscription if caller already created one
            # (e.g., complete_account_setup pre-creates the Stripe subscription
            # before calling assign_subscription to avoid double-billing).
            stripe_subscription_id = existing_stripe_subscription_id
            stripe_customer_id = existing_stripe_customer_id
            price_field = f"stripe_price_id_{billing_interval}"
            stripe_price_id = plan.get(price_field)

            if stripe_subscription_id:
                # Stripe subscription already exists — just ensure we have the customer ID
                if not stripe_customer_id:
                    try:
                        stripe_customer_id = (
                            await stripe_service.get_or_create_customer(
                                user_id=user_id,
                                email=user["email"],
                                name=user.get("full_name") or user.get("email"),
                            )
                        )
                    except Exception as e:
                        logger.warning(
                            f"Could not resolve Stripe customer for existing sub: {e}"
                        )
                logger.info(
                    f"Using existing Stripe subscription {stripe_subscription_id} "
                    f"for user {user_id} (skipped duplicate creation)"
                )
            elif stripe_price_id:
                try:
                    # Get or create Stripe customer
                    stripe_customer_id = await stripe_service.get_or_create_customer(
                        user_id=user_id,
                        email=user["email"],
                        name=user.get("full_name") or user.get("email"),
                    )

                    if stripe_customer_id:
                        sub_params = {
                            "customer": stripe_customer_id,
                            "items": [{"price": stripe_price_id}],
                            "metadata": {"user_id": user_id, "plan_id": plan_id},
                        }
                        if trial_days > 0:
                            sub_params["trial_end"] = int(trial_end.timestamp())

                        stripe_sub = stripe.Subscription.create(**sub_params)
                        stripe_subscription_id = stripe_sub.id
                        logger.info(
                            f"Created Stripe subscription {stripe_subscription_id} "
                            f"for user {user_id} with {trial_days} day trial"
                        )
                except Exception as e:
                    logger.warning(
                        f"Could not create Stripe subscription for admin-assigned plan: {e}. "
                        f"Proceeding with local-only subscription."
                    )
            else:
                logger.info(
                    f"Plan {plan_id} has no Stripe price for {billing_interval} billing. "
                    f"Creating local-only subscription."
                )

            subscription_data = {
                "_id": f"sub_{user_id}_{plan_id}_{int(now.timestamp())}",
                "user_id": user_id,
                "user_email": user["email"],
                "plan_id": plan_id,
                "plan_snapshot": plan_snapshot,  # Grandfathered limits
                "status": "trial" if trial_days > 0 else "active",
                "billing_interval": billing_interval,
                "start_date": now,
                "trial_end_date": trial_end if trial_days > 0 else None,
                "current_period_start": now,
                "current_period_end": period_end,
                "stripe_subscription_id": stripe_subscription_id,
                "stripe_customer_id": stripe_customer_id,
                "usage": {
                    "weddings_count": 0,
                    "ai_credits_used_month": 0,
                    "storage_used_gb": 0,
                    "staff_seats_used": 0,
                },
                "created_at": now,
                "updated_at": now,
                "created_by": creator_email,
            }

            await self.subscriptions_collection.insert_one(subscription_data)

            # Initialize usage tracking
            await self.initialize_usage_tracking(user_id, subscription_data["_id"])

            # Update user subscription info (must include trial_end_date so
            # trial_expiration_service can find and expire trials correctly)
            user_updates: dict = {
                "plan_id": plan_id,
                "subscription_status": subscription_data["status"],
                "is_active": True,
                "updated_at": now,
            }
            if stripe_customer_id:
                user_updates["stripe_customer_id"] = stripe_customer_id
            if trial_days > 0:
                user_updates["trial_end_date"] = trial_end
                user_updates["trial_warning_sent"] = False

            await self.users_collection.update_one(
                {"_id": to_object_id(user_id, "user_id")}, {"$set": user_updates}
            )
            return {
                "message": "Subscription assigned successfully",
                "subscription_id": subscription_data["_id"],
                "status": subscription_data["status"],
                "trial_end_date": subscription_data.get("trial_end_date"),
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error assigning subscription: {str(e)}"
            )

    async def get_user_subscription(self, user_id: str) -> Optional[dict]:
        """Get user's current subscription"""
        try:
            subscription = await self.subscriptions_collection.find_one(
                {"user_id": user_id, "status": {"$in": ["active", "trial"]}}
            )
            return subscription
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error retrieving subscription: {str(e)}"
            )

    async def cancel_subscription(self, user_id: str, reason: str = "") -> dict:
        """Cancel user subscription in both local DB and Stripe, with cleanup orchestration"""
        try:
            now = datetime.now(timezone.utc)

            # Find the subscription first to get Stripe subscription ID
            subscription = await self.subscriptions_collection.find_one(
                {"user_id": user_id, "status": {"$in": ["active", "trial"]}}
            )

            if not subscription:
                raise HTTPException(
                    status_code=404, detail="No active subscription found"
                )

            # Fetch user document for email and other data
            user = await self.users_collection.find_one(
                {"_id": to_object_id(user_id, "user_id")}
            )
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            user_email = user.get("email", "")

            # Cancel in Stripe if there's a Stripe subscription
            stripe_sub_id = subscription.get("stripe_subscription_id")
            if stripe_sub_id:
                try:
                    stripe.Subscription.cancel(stripe_sub_id)
                    logger.info(
                        f"Cancelled Stripe subscription {stripe_sub_id} for user {user_id}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to cancel Stripe subscription {stripe_sub_id}: {str(e)}"
                    )
                    # Still proceed with local cancellation to avoid inconsistent state

            # Update local subscription with optimistic locking
            subscription_version = subscription.get("version", 1)
            result = await self.subscriptions_collection.update_one(
                {"_id": subscription["_id"], "version": subscription_version},
                {
                    "$set": {
                        "status": "cancelled",
                        "cancelled_at": now,
                        "updated_at": now,
                        "cancellation_reason": reason,
                        "cancellation_cleanup_completed": True,
                        "cancellation_cleanup_at": now,
                    },
                    "$inc": {"version": 1},
                },
            )

            if result.matched_count == 0:
                logger.warning(
                    f"Subscription {subscription['_id']} version mismatch (concurrent modification detected). "
                    f"Proceeding with local-only cancellation."
                )

            # Update user status and set is_active to False
            await self.users_collection.update_one(
                {"_id": to_object_id(user_id, "user_id")},
                {
                    "$set": {
                        "subscription_status": "cancelled",
                        "is_active": False,
                        "updated_at": now,
                    }
                },
            )

            logger.info(f"Core cancellation complete for user {user_id}")

            # Initialize cleanup results
            cleanup_results = {
                "team_members_deactivated": 0,
                "couples_blocked": 0,
                "data_suspended": {},
                "payments_paused": {},
                "email_sent": False,
                "couples_notified": 0,
            }

            lifecycle_cleanup = (
                await planner_access_lifecycle_service.suspend_planner_access(
                    planner_id=user_id,
                    planner_email=user_email,
                    team_reason="owner_subscription_cancelled",
                )
            )
            cleanup_results["team_members_deactivated"] = lifecycle_cleanup.get(
                "team_members_deactivated", 0
            )
            cleanup_results["couples_blocked"] = lifecycle_cleanup.get(
                "couples_blocked", 0
            )
            cleanup_results["data_suspended"] = lifecycle_cleanup.get(
                "data_suspended", {}
            )
            cleanup_results["payments_paused"] = lifecycle_cleanup.get(
                "payments_paused", {}
            )

            # Phase 5: Send cancellation email to planner
            try:
                from app.services.email_service_resend import ResendEmailService

                email_service = ResendEmailService()
                email_sent = await email_service.send_subscription_cancelled_email(user)
                cleanup_results["email_sent"] = email_sent
                logger.info(f"Sent cancellation email to user {user_id}: {email_sent}")
            except Exception as e:
                logger.warning(
                    f"Failed to send cancellation email to user {user_id}: {str(e)}"
                )

            # Phase 6: Notify affected couples
            try:
                from app.core.database import mongo
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
                    couples_notified = 0

                    # Build a wedding lookup map for the notification template
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
                                couples_notified += 1
                        except Exception as e:
                            logger.warning(
                                f"Failed to notify couple {couple.get('email')} for wedding {couple.get('wedding_id')}: {str(e)}"
                            )

                    cleanup_results["couples_notified"] = couples_notified
                    logger.info(
                        f"Notified {couples_notified} couples about planner {user_id} cancellation"
                    )
            except Exception as e:
                logger.warning(f"Failed to notify couples for user {user_id}: {str(e)}")

            return {
                "message": "Subscription cancelled successfully",
                "cleanup": cleanup_results,
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error cancelling subscription: {str(e)}"
            )

    # Usage Tracking
    async def initialize_usage_tracking(
        self, user_id: str, subscription_id: str
    ) -> dict:
        """Initialize usage tracking for a new subscription"""
        try:
            now = datetime.now(timezone.utc)
            current_month = now.strftime("%Y-%m")
            # Calculate next month for credits reset
            if now.month == 12:
                credits_reset = datetime(now.year + 1, 1, 1)
            else:
                credits_reset = datetime(now.year, now.month + 1, 1)
            usage_data = {
                "_id": f"usage_{user_id}_{current_month}",
                "user_id": user_id,
                "subscription_id": subscription_id,
                "weddings_count": 0,
                "ai_credits_used_month": 0,
                "storage_used_gb": 0.0,
                "staff_seats_used": 0,
                "current_month": current_month,
                "credits_reset_date": credits_reset,
                "last_updated": now,
            }
            # Use upsert to avoid duplicates
            await self.usage_collection.update_one(
                {"_id": usage_data["_id"]}, {"$set": usage_data}, upsert=True
            )

            return usage_data

        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error initializing usage tracking: {str(e)}"
            )

    # ------------------------------------------------------------------ #
    # Unit-economics defaults
    # ------------------------------------------------------------------ #
    # Soft-cap overage price applied when a planner consumes AI credits
    # beyond their plan_snapshot allowance. Priced per credit. A planner
    # can still call the AI; we track the overage and bill it at period
    # close. This value is used as the default when a plan_snapshot does
    # not carry ``ai_credit_overage_price`` (e.g. subscriptions issued
    # before soft-cap overage was introduced).
    DEFAULT_AI_CREDIT_OVERAGE_PRICE_USD = 0.02

    def _resolve_overage_price(self, limits_source: dict) -> float:
        price = limits_source.get("ai_credit_overage_price")
        try:
            price_f = float(price) if price is not None else 0.0
        except (TypeError, ValueError):
            price_f = 0.0
        if price_f <= 0:
            return self.DEFAULT_AI_CREDIT_OVERAGE_PRICE_USD
        return price_f

    async def _live_storage_bytes(self, user_id: str) -> int:
        """Authoritative storage-used count in bytes for cap enforcement.

        Sums ``size_bytes`` across every uploaded guest_media asset whose
        ``wedding_id`` belongs to a wedding owned by this planner. Same
        philosophy as ``_live_wedding_count``: the
        ``usage_tracking.storage_used_gb`` counter is unreliable (drifts
        on month rollover, drifts on re-provisioning, drifts under write
        ordering races). The aggregation pipeline here is the source of
        truth. Counter remains a read-cache only.
        """
        user = await self.users_collection.find_one(
            {"_id": normalize_query_id(user_id)},
            {"email": 1},
        )
        user_email = user.get("email") if user else None
        owner_query = build_wedding_owner_query(
            planner_id=user_id, planner_email=user_email
        )
        if not owner_query:
            return 0
        weddings_cursor = self.weddings_collection.find(owner_query, {"_id": 1})
        wedding_docs = await weddings_cursor.to_list(length=10000)
        if not wedding_docs:
            return 0
        wedding_ids = [str(w["_id"]) for w in wedding_docs]
        pipeline = [
            {
                "$match": {
                    "wedding_id": {"$in": wedding_ids},
                    "upload_status": "uploaded",
                }
            },
            {"$group": {"_id": None, "total": {"$sum": "$size_bytes"}}},
        ]
        cursor = mongo.db["guest_media_assets"].aggregate(pipeline)
        result = await cursor.to_list(length=1)
        return int(result[0]["total"]) if result else 0

    async def _live_staff_seats_count(self, user_id: str) -> int:
        """Authoritative staff-seats-used count for cap enforcement.

        Counts team_members docs in pending or active status for this
        planner. Same bug class as the weddings counter: the
        ``usage_tracking.staff_seats_used`` counter can drift when
        invites are deactivated without a compensating decrement, when
        a planner is re-provisioned, or on month rollover. The
        team_members collection is already the source of truth
        everywhere else in the codebase (see
        ``team_management_service.check_seat_limit``); this method aligns
        the subscription_service cap path with that same truth.
        """
        cursor = mongo.db["team_members"].aggregate(
            [
                {
                    "$match": {
                        "owner_id": user_id,
                        "status": {"$in": ["pending", "active"]},
                    }
                },
                {"$count": "total"},
            ]
        )
        result = await cursor.to_list(length=1)
        return int(result[0]["total"]) if result else 0

    async def _live_ai_credits_used(self, user_id: str, current_month: str) -> int:
        """Authoritative AI credit spend for the current monthly window.

        Aggregates ``credits_used`` from ``ai_usage_log`` entries for the
        given ``YYYY-MM`` window. Same pattern as the other live-count
        helpers — the ``usage_tracking.ai_credits_used_month`` counter is
        a read-cache; the logs are the source of truth. Prevents the
        counter-drift bug class that forced the weddings fix.
        """
        try:
            year, month = current_month.split("-")
            period_start = datetime(int(year), int(month), 1, tzinfo=timezone.utc)
            if int(month) == 12:
                period_end = datetime(int(year) + 1, 1, 1, tzinfo=timezone.utc)
            else:
                period_end = datetime(int(year), int(month) + 1, 1, tzinfo=timezone.utc)
        except Exception:
            return 0

        cursor = mongo.db["ai_usage_log"].aggregate(
            [
                {
                    "$match": {
                        "user_id": user_id,
                        "created_at": {"$gte": period_start, "$lt": period_end},
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "total": {"$sum": "$credits_used"},
                    }
                },
            ]
        )
        result = await cursor.to_list(length=1)
        return int(result[0]["total"]) if result else 0

    async def _live_wedding_count(self, user_id: str) -> int:
        """Authoritative wedding count for cap enforcement.

        Reads the `weddings` collection directly instead of trusting the
        `usage_tracking.weddings_count` counter, which can drift from
        reality in at least three ways:

        1. ``reset_monthly_usage`` unconditionally sets ``weddings_count=0``
           on every new-month document (the inline note at line 798 already
           flagged this but the code still resets) — so the cap silently
           lifts on each month rollover for a cumulative resource.
        2. If a user record is re-provisioned under the same email (driver
           reseeding, support tools, data migration), weddings keyed by
           ``assigned_planner_email`` persist but the new user's
           ``usage_tracking`` counter starts at 0. This is how the planner
           trial driver was false-passing A1/A2 while the tenancy had 6
           live weddings against a 3-wedding cap.
        3. Any write ordering issue between wedding create and counter
           increment leaves the counter out of sync indefinitely.

        Soft-deleted weddings (``deleted_at`` set by
        ``cascade_delete_service.soft_delete_wedding``) are EXCLUDED — the
        plan cap is on *active* weddings; an archived wedding shouldn't
        consume the same slot a live one would.

        Live-counting via ``build_wedding_owner_query`` (the canonical
        owner filter used everywhere else in the codebase) removes all
        three counter-drift modes at the cost of one ``count_documents``
        call per cap check.
        """
        user = await self.users_collection.find_one(
            {"_id": normalize_query_id(user_id)},
            {"email": 1},
        )
        user_email = user.get("email") if user else None
        owner_query = build_wedding_owner_query(
            planner_id=user_id, planner_email=user_email
        )
        if not owner_query:
            return 0
        # Filter out soft-deleted weddings — the cap is on active weddings
        # only. ``$exists: False`` matches docs without the field; ``$eq:
        # None`` matches docs where the field is explicitly null. Either
        # form means "not soft-deleted".
        active_query = {
            "$and": [
                owner_query,
                {
                    "$or": [
                        {"deleted_at": {"$exists": False}},
                        {"deleted_at": None},
                    ]
                },
            ]
        }
        return await self.weddings_collection.count_documents(active_query)

    async def get_usage_stats(self, user_id: str) -> dict:
        """Get current usage statistics for user.

        ``weddings_count`` in the returned dict is reconciled against the
        live weddings collection before return, so the billing dashboard
        and any other consumer sees the authoritative count regardless of
        counter drift. Drift is logged at INFO so it's visible but doesn't
        alarm. See ``_live_wedding_count`` for why the counter is unreliable.
        """
        try:
            current_month = datetime.now(timezone.utc).strftime("%Y-%m")
            usage = await self.usage_collection.find_one(
                {"user_id": user_id, "current_month": current_month}
            )
            if not usage:
                # Initialize if doesn't exist
                subscription = await self.get_user_subscription(user_id)
                if subscription:
                    usage = await self.initialize_usage_tracking(
                        user_id, subscription["_id"]
                    )
                else:
                    return {"error": "No active subscription found"}

            # Reconcile wedding count with live reality. We don't write back
            # to the counter — the counter stays as an observability
            # breadcrumb; the returned dict carries the truth.
            live_wedding_count = await self._live_wedding_count(user_id)
            stored = usage.get("weddings_count", 0)
            if stored != live_wedding_count:
                logger.info(
                    f"Reconciling weddings_count for user_id={user_id}: "
                    f"usage_tracking.weddings_count={stored} -> "
                    f"live weddings collection count={live_wedding_count}"
                )
                usage["weddings_count"] = live_wedding_count

            return usage

        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error retrieving usage stats: {str(e)}"
            )

    async def check_usage_limits(
        self, user_id: str, resource_type: str, requested_amount: int = 1
    ) -> dict:
        """Check if user can use more of a resource without exceeding limits

        Uses plan_snapshot (grandfathered limits) if available, falls back to current plan for
        backwards compatibility with subscriptions created before snapshots were added.
        """
        try:
            subscription = await self.get_user_subscription(user_id)
            if not subscription:
                raise HTTPException(
                    status_code=403, detail="No active subscription found"
                )

            # Use grandfathered plan_snapshot if available, otherwise fetch current plan
            # This ensures users keep the limits they signed up for even if plan changes
            plan_snapshot = subscription.get("plan_snapshot")
            if plan_snapshot:
                limits_source = plan_snapshot
            else:
                # Backwards compatibility for subscriptions without snapshot
                limits_source = await self.get_plan(subscription["plan_id"])

            usage = await self.get_usage_stats(user_id)

            # Check limits based on resource type
            if resource_type == "weddings":
                # SOURCE OF TRUTH is the weddings collection, not the
                # counter. ``get_usage_stats`` already reconciles the
                # returned dict, but we re-query here to keep this method
                # independently correct — if someone ever stubs or bypasses
                # ``get_usage_stats``, the cap must still hold. The extra
                # round-trip is negligible versus a false-positive cap.
                current = await self._live_wedding_count(user_id)
                limit = limits_source.get("max_weddings", 1)
                if limit != -1 and current + requested_amount > limit:
                    return {
                        "allowed": False,
                        "current_usage": current,
                        "limit": limit,
                        "message": f"Wedding limit exceeded. Plan allows {limit} weddings, you have {current}",
                    }
            elif resource_type == "ai_credits":
                # Soft cap with overage. Live-query the usage log so we
                # can't false-pass on counter drift. A planner in
                # overage still gets ``allowed=true`` so the workflow
                # doesn't break in crunch moments; we annotate the
                # response with overage metadata that callers and the
                # UI can surface and that billing can pick up at
                # period close.
                current_month = datetime.now(timezone.utc).strftime("%Y-%m")
                current = await self._live_ai_credits_used(user_id, current_month)
                limit = limits_source.get("ai_credits_monthly", 10)
                remaining = max(0, limit - current)
                projected = current + requested_amount
                overage_credits = max(0, projected - limit) if limit != -1 else 0
                overage_price = self._resolve_overage_price(limits_source)
                cumulative_overage_credits = (
                    max(0, current - limit) if limit != -1 else 0
                )
                overage_cost_cents = int(
                    round(cumulative_overage_credits * overage_price * 100)
                )
                # ``overage`` flips ONLY when cumulative usage has actually
                # crossed the cap — i.e. real billable usage exists past
                # the included allotment. A request that *would* push the
                # planner over is surfaced separately via
                # ``overage_credits_projected`` so callers can show a
                # "you're about to go into overage" affordance without the
                # billing surface lighting up prematurely.
                return {
                    "allowed": True,
                    "current_usage": current,
                    "limit": limit,
                    "remaining": remaining,
                    "overage": cumulative_overage_credits > 0,
                    "overage_credits": cumulative_overage_credits,
                    "overage_credits_projected": overage_credits,
                    "overage_price_per_credit_usd": overage_price,
                    "overage_cost_cents": overage_cost_cents,
                }

            elif resource_type == "staff_seats":
                # Source of truth is the team_members collection, not
                # the counter — same reasoning as weddings. See
                # ``_live_staff_seats_count`` for the drift modes the
                # counter has historically exhibited.
                current = await self._live_staff_seats_count(user_id)
                limit = limits_source.get("staff_seats", 0)
                if limit != -1 and current + requested_amount > limit:
                    return {
                        "allowed": False,
                        "current_usage": current,
                        "limit": limit,
                        "message": f"Staff seats limit exceeded. Plan allows {limit} staff accounts",
                    }
                return {
                    "allowed": True,
                    "current_usage": current,
                    "limit": limit,
                }

            elif resource_type == "storage":
                # Hard cap. Persistent resource — if a planner can keep
                # writing past cap they compound the infrastructure
                # bill every month the asset lives. Live-query via
                # ``_live_storage_bytes`` so the cap can't drift on
                # counter resets. ``requested_amount`` is interpreted
                # as bytes; the plan_snapshot stores the allowance as
                # GB. -1 = unlimited (Agency).
                current_bytes = await self._live_storage_bytes(user_id)
                limit_gb = limits_source.get("storage_gb", 1)
                if limit_gb == -1:
                    return {
                        "allowed": True,
                        "current_usage_bytes": current_bytes,
                        "current_usage_gb": round(current_bytes / (1024**3), 3),
                        "limit_gb": -1,
                    }
                limit_bytes = int(limit_gb) * (1024**3)
                projected = current_bytes + int(requested_amount)
                if projected > limit_bytes:
                    return {
                        "allowed": False,
                        "current_usage_bytes": current_bytes,
                        "current_usage_gb": round(current_bytes / (1024**3), 3),
                        "limit_gb": limit_gb,
                        "message": (
                            f"Storage limit reached — "
                            f"{round(current_bytes / (1024**3), 2)} of {limit_gb} GB in use. "
                            "Upgrade your plan or delete uploads to free space."
                        ),
                    }
                return {
                    "allowed": True,
                    "current_usage_bytes": current_bytes,
                    "current_usage_gb": round(current_bytes / (1024**3), 3),
                    "limit_gb": limit_gb,
                }

            return {
                "allowed": True,
                "current_usage": usage.get(f"{resource_type}_used", 0),
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error checking usage limits: {str(e)}"
            )

    async def increment_usage(
        self, user_id: str, resource_type: str, amount: int = 1
    ) -> dict:
        """Increment usage for a specific resource"""
        try:
            current_month = datetime.now(timezone.utc).strftime("%Y-%m")
            # Map resource types to database fields. These counters are
            # read-caches: authoritative values come from the live-query
            # helpers (_live_wedding_count, _live_storage_bytes,
            # _live_staff_seats_count, _live_ai_credits_used). Keeping
            # the counters in sync preserves the existing observability
            # breadcrumb and lets `get_usage_stats` short-circuit when
            # the cache matches reality.
            field_mapping = {
                "weddings": "weddings_count",
                "ai_credits": "ai_credits_used_month",
                "staff_seats": "staff_seats_used",
                "storage": "storage_used_bytes",
            }

            if resource_type not in field_mapping:
                raise HTTPException(
                    status_code=400, detail=f"Invalid resource type: {resource_type}"
                )

            field_name = field_mapping[resource_type]

            result = await self.usage_collection.update_one(
                {"user_id": user_id, "current_month": current_month},
                {
                    "$inc": {field_name: amount},
                    "$set": {"last_updated": datetime.now(timezone.utc)},
                },
            )

            if result.matched_count == 0:
                raise HTTPException(
                    status_code=404, detail="Usage tracking record not found"
                )

            return {"message": f"Usage incremented: {resource_type} +{amount}"}

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error incrementing usage: {str(e)}"
            )

    async def reset_monthly_usage(self, user_id: str) -> dict:
        """Reset monthly usage counters (called on subscription renewal)"""
        try:
            now = datetime.now(timezone.utc)
            current_month = now.strftime("%Y-%m")
            # Calculate next reset date
            if now.month == 12:
                next_reset = datetime(now.year + 1, 1, 1)
            else:
                next_reset = datetime(now.year, now.month + 1, 1)

            subscription = await self.get_user_subscription(user_id)
            if not subscription:
                raise HTTPException(
                    status_code=404, detail="No active subscription found"
                )

            # Create new usage tracking record for the new month.
            #
            # NOTE on the counter values below: this writes a *new
            # document* keyed by `(user_id, current_month)`, not a reset
            # of the previous month's row. The previous comments here
            # claimed `weddings_count` and `storage_used_gb` "don't reset
            # monthly" — that was misleading: each month gets its own
            # document, and these fields effectively start at 0 in the
            # new doc. The cap-enforcement code does NOT trust these
            # counters anyway — see `_live_wedding_count`,
            # `_live_storage_bytes`, and `_live_staff_seats_count` for
            # the source-of-truth queries that read the underlying
            # collections directly. The counters here are a read cache
            # used by the planner billing dashboard.
            new_usage_id = f"usage_{user_id}_{current_month}"

            usage_data = {
                "_id": new_usage_id,
                "user_id": user_id,
                "subscription_id": subscription["_id"],
                # All four counters start at 0 in the new month's document.
                # If a UI surface needs cumulative-since-signup numbers, it
                # should query the live collections, not aggregate this
                # cache.
                "weddings_count": 0,
                "ai_credits_used_month": 0,
                "storage_used_gb": 0.0,
                "staff_seats_used": 0,
                "current_month": current_month,
                "credits_reset_date": next_reset,
                "last_updated": now,
            }
            await self.usage_collection.update_one(
                {"_id": new_usage_id}, {"$set": usage_data}, upsert=True
            )

            return {"message": "Monthly usage counters reset successfully"}

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error resetting monthly usage: {str(e)}"
            )

    # Analytics and Reporting
    async def get_subscription_analytics(self) -> dict:
        """Get platform-wide subscription analytics (ROOT_ADMIN only)"""
        try:
            # Total subscriptions by status
            status_counts = {}
            for status in ["trial", "active", "cancelled", "expired", "suspended"]:
                count = await self.subscriptions_collection.count_documents(
                    {"status": status}
                )
                status_counts[status] = count

            # Archived count (separate dimension - archived subs keep their original status)
            archived_count = await self.subscriptions_collection.count_documents(
                {"archived_at": {"$exists": True}}
            )
            # Total subscriptions by plan
            plan_pipeline = [
                {"$group": {"_id": "$plan_id", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
            ]
            plan_counts_cursor = self.subscriptions_collection.aggregate(plan_pipeline)
            # Plan aggregation should have one doc per plan, cap at 500
            plan_counts = await plan_counts_cursor.to_list(length=500)
            # Monthly recurring revenue (MRR) calculation - includes both monthly AND yearly
            # For yearly subscriptions, we calculate the monthly equivalent (price_yearly / 12)
            # Safety cap: process active subscriptions in batches to avoid memory overload
            MAX_ACTIVE_SUBS = 100000
            active_subs = await self.subscriptions_collection.find(
                {"status": "active"}
            ).to_list(length=MAX_ACTIVE_SUBS)

            mrr = 0
            mrr_from_monthly = 0
            mrr_from_yearly = 0
            monthly_sub_count = 0
            yearly_sub_count = 0

            for sub in active_subs:
                plan = await self.get_plan(sub["plan_id"])
                billing_interval = sub.get("billing_interval", "monthly")

                if billing_interval == "yearly":
                    # Convert yearly to monthly equivalent
                    yearly_price = plan.get("price_yearly", 0)
                    monthly_equivalent = yearly_price / 12 if yearly_price else 0
                    mrr_from_yearly += monthly_equivalent
                    yearly_sub_count += 1
                else:
                    # Monthly billing
                    mrr_from_monthly += plan.get("price_monthly", 0)
                    monthly_sub_count += 1

            mrr = mrr_from_monthly + mrr_from_yearly
            arr = mrr * 12  # Annual Recurring Revenue

            return {
                "total_subscriptions": sum(status_counts.values()),
                "status_breakdown": status_counts,
                "archived_subscriptions": archived_count,
                "plan_breakdown": {item["_id"]: item["count"] for item in plan_counts},
                "monthly_recurring_revenue": round(mrr, 2),
                "annual_recurring_revenue": round(arr, 2),
                "mrr_breakdown": {
                    "from_monthly_billing": round(mrr_from_monthly, 2),
                    "from_yearly_billing": round(mrr_from_yearly, 2),
                    "monthly_subscribers": monthly_sub_count,
                    "yearly_subscribers": yearly_sub_count,
                },
                "generated_at": datetime.now(timezone.utc),
            }
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error generating analytics: {str(e)}"
            )

    async def list_all_subscriptions(
        self, status_filter: Optional[str] = None
    ) -> List[dict]:
        """List all user subscriptions with details (ROOT_ADMIN only)"""
        try:
            # Build query
            query = {}
            if status_filter and status_filter != "all":
                if status_filter == "archived":
                    # Archived subs retain original status (cancelled/expired);
                    # archived_at field marks them as archived
                    query["archived_at"] = {"$exists": True}
                else:
                    query["status"] = status_filter

            # Fetch all subscriptions (safety cap: admin view limited to 50k subscriptions)
            MAX_LIST_SUBSCRIPTIONS = 50000
            subscriptions = await self.subscriptions_collection.find(query).to_list(
                length=MAX_LIST_SUBSCRIPTIONS
            )

            # Build lookup maps for plans and users
            # Safety cap: typically <500 plans and <10k users
            MAX_PLANS = 500
            MAX_USERS = 10000
            plans = await self.plans_collection.find({}).to_list(length=MAX_PLANS)
            plans_map = {str(plan.get("_id", "")): plan for plan in plans}

            users = await self.users_collection.find({}).to_list(length=MAX_USERS)
            users_map = {str(user.get("_id", "")): user for user in users}

            formatted_subscriptions = []
            for sub in subscriptions:
                user_id = sub.get("user_id", "")
                user = users_map.get(user_id, {})
                plan_id = sub.get("plan_id", "")
                plan = plans_map.get(plan_id, {})

                # Determine amount based on billing interval
                billing_interval = sub.get("billing_interval", "monthly")
                if billing_interval == "yearly":
                    amount = plan.get("price_yearly", 0)
                else:
                    amount = plan.get("price_monthly", 0)

                # Format dates safely
                def format_date(value):
                    if isinstance(value, datetime):
                        return value.isoformat()
                    return str(value) if value else ""

                formatted_sub = {
                    "_id": str(sub.get("_id", "")),
                    "user_id": user_id,
                    "user_email": user.get("email", sub.get("user_email", "")),
                    "company_name": user.get(
                        "company_name", sub.get("company_name", "")
                    ),
                    "plan_id": plan_id,
                    "plan_name": plan.get("name", sub.get("plan_name", "Unknown Plan")),
                    "status": sub.get("status", "unknown"),
                    "billing_interval": billing_interval,
                    "amount": amount,
                    "current_period_start": format_date(
                        sub.get("current_period_start")
                    ),
                    "current_period_end": format_date(sub.get("current_period_end")),
                    "created_at": format_date(sub.get("created_at")),
                }
                formatted_subscriptions.append(formatted_sub)

            return formatted_subscriptions
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error listing subscriptions: {str(e)}"
            )


# Singleton instance
subscription_service = SubscriptionService()
