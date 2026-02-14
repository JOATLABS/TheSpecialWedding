from fastapi import HTTPException
from app.core.database import mongo
from app.services.stripe_service import stripe_service
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from bson import ObjectId


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
                raise HTTPException(status_code=400, detail="Plan with this name already exists")

            # Sync to Stripe first
            try:
                stripe_data = stripe_service.sync_plan_to_stripe(plan_data)
                plan_data.update(stripe_data)
            except Exception as e:
                # Log but don't block creation if stripe fails?
                # Better to fail so we don't have inconsistent state
                raise HTTPException(status_code=500, detail=f"Failed to sync plan to Stripe: {str(e)}")

            await self.plans_collection.insert_one(plan_data)
            return {"message": "Subscription plan created successfully", "plan_id": plan_data["_id"]}

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error creating subscription plan: {str(e)}")

    async def list_plans(self, include_inactive: bool = False) -> List[dict]:
        """List all subscription plans"""
        try:
            query = {} if include_inactive else {"is_active": True}
            cursor = self.plans_collection.find(query).sort("sort_order", 1)
            plans = await cursor.to_list(length=None)
            return plans
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error listing plans: {str(e)}")

    async def get_plan(self, plan_id: str) -> dict:
        """Get subscription plan by ID"""
        try:
            plan = await self.plans_collection.find_one({"_id": plan_id})
            if not plan:
                raise HTTPException(status_code=404, detail="Subscription plan not found")
            return plan
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error retrieving plan: {str(e)}")

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
                raise HTTPException(status_code=404, detail="Subscription plan not found")

            merged_plan = {**existing_plan, **update_data}

            # Sync to Stripe
            try:
                stripe_data = stripe_service.sync_plan_to_stripe(merged_plan)
                update_data.update(stripe_data)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to sync plan to Stripe: {str(e)}")

            await self.plans_collection.update_one(
                {"_id": plan_id},
                {"$set": update_data}
            )

            return {"message": "Subscription plan updated successfully"}

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error updating plan: {str(e)}")

    async def delete_plan(self, plan_id: str) -> dict:
        """Delete subscription plan (only if no active subscriptions)"""
        try:
            # Check if any users have active subscriptions to this plan
            active_subs = await self.subscriptions_collection.count_documents({
                "plan_id": plan_id,
                "status": {"$in": ["active", "trial"]}
            })

            if active_subs > 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot delete plan: {active_subs} active subscriptions exist"
                )

            # Get the plan first to retrieve Stripe product ID
            plan = await self.plans_collection.find_one({"_id": plan_id})
            if not plan:
                raise HTTPException(status_code=404, detail="Subscription plan not found")

            # Archive the Stripe product (deactivate, don't delete)
            stripe_product_id = plan.get("stripe_product_id")
            if stripe_product_id:
                try:
                    stripe_service.archive_stripe_product(stripe_product_id)
                except Exception as e:
                    # Log but don't block deletion - Stripe sync can be fixed manually
                    print(f"Warning: Failed to archive Stripe product {stripe_product_id}: {e}")

            result = await self.plans_collection.delete_one({"_id": plan_id})

            if result.deleted_count == 0:
                raise HTTPException(status_code=404, detail="Subscription plan not found")

            return {"message": "Subscription plan deleted successfully", "stripe_archived": bool(stripe_product_id)}

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error deleting plan: {str(e)}")

    # User Subscription Management
    async def assign_subscription(self, user_id: str, plan_id: str, billing_interval: str = "monthly",
                                  trial_days: int = 0, creator_email: str = "") -> dict:
        """Assign subscription plan to user"""
        try:
            # Verify user exists
            user = await self.users_collection.find_one({"_id": ObjectId(user_id)})
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            # Verify plan exists
            plan = await self.get_plan(plan_id)

            # Check if user already has an active subscription
            existing_sub = await self.subscriptions_collection.find_one({
                "user_id": user_id,
                "status": {"$in": ["active", "trial"]}
            })

            if existing_sub:
                raise HTTPException(status_code=400, detail="User already has an active subscription")

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
                "storage_gb": plan.get("storage_gb", 1),
                "staff_seats": plan.get("staff_seats", 0),
                "features": plan.get("features", {}),
                "price_monthly": plan.get("price_monthly", 0),
                "price_yearly": plan.get("price_yearly"),
                "stripe_price_id_monthly": plan.get("stripe_price_id_monthly"),
                "stripe_price_id_yearly": plan.get("stripe_price_id_yearly"),
                "snapshot_date": now,
            }

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
                "usage": {
                    "weddings_created": 0,
                    "ai_credits_used": 0,
                    "storage_used_gb": 0,
                    "staff_seats_used": 0
                },
                "created_at": now,
                "updated_at": now,
                "created_by": creator_email
            }

            await self.subscriptions_collection.insert_one(subscription_data)

            # Initialize usage tracking
            await self.initialize_usage_tracking(user_id, subscription_data["_id"])

            # Update user subscription info
            await self.users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {
                    "plan_id": plan_id,
                    "subscription_status": subscription_data["status"],
                    "updated_at": now
                }}
            )
            return {
                "message": "Subscription assigned successfully",
                "subscription_id": subscription_data["_id"],
                "status": subscription_data["status"],
                "trial_end_date": subscription_data.get("trial_end_date")
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error assigning subscription: {str(e)}")

    async def get_user_subscription(self, user_id: str) -> Optional[dict]:
        """Get user's current subscription"""
        try:
            subscription = await self.subscriptions_collection.find_one({
                "user_id": user_id,
                "status": {"$in": ["active", "trial"]}
            })
            return subscription
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error retrieving subscription: {str(e)}")

    async def cancel_subscription(self, user_id: str, reason: str = "") -> dict:
        """Cancel user subscription"""
        try:
            now = datetime.now(timezone.utc)
            result = await self.subscriptions_collection.update_one(
                {"user_id": user_id, "status": {"$in": ["active", "trial"]}},
                {"$set": {
                    "status": "cancelled",
                    "cancelled_at": now,
                    "updated_at": now,
                    "cancellation_reason": reason
                }}
            )

            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="No active subscription found")

            # Update user status
            await self.users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {
                    "subscription_status": "cancelled",
                    "updated_at": now
                }}
            )

            return {"message": "Subscription cancelled successfully"}

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error cancelling subscription: {str(e)}")

    # Usage Tracking
    async def initialize_usage_tracking(self, user_id: str, subscription_id: str) -> dict:
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
                "last_updated": now
            }
            # Use upsert to avoid duplicates
            await self.usage_collection.update_one(
                {"_id": usage_data["_id"]},
                {"$set": usage_data},
                upsert=True
            )

            return usage_data

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error initializing usage tracking: {str(e)}")

    async def get_usage_stats(self, user_id: str) -> dict:
        """Get current usage statistics for user"""
        try:
            current_month = datetime.now(timezone.utc).strftime("%Y-%m")
            usage = await self.usage_collection.find_one({
                "user_id": user_id,
                "current_month": current_month
            })
            if not usage:
                # Initialize if doesn't exist
                subscription = await self.get_user_subscription(user_id)
                if subscription:
                    usage = await self.initialize_usage_tracking(user_id, subscription["_id"])
                else:
                    return {"error": "No active subscription found"}

            return usage

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error retrieving usage stats: {str(e)}")

    async def check_usage_limits(self, user_id: str, resource_type: str, requested_amount: int = 1) -> dict:
        """Check if user can use more of a resource without exceeding limits

        Uses plan_snapshot (grandfathered limits) if available, falls back to current plan for
        backwards compatibility with subscriptions created before snapshots were added.
        """
        try:
            subscription = await self.get_user_subscription(user_id)
            if not subscription:
                raise HTTPException(status_code=403, detail="No active subscription found")

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
                current = usage.get("weddings_count", 0)
                limit = limits_source.get("max_weddings", 1)
                if limit != -1 and current + requested_amount > limit:
                    return {
                        "allowed": False,
                        "current_usage": current,
                        "limit": limit,
                        "message": f"Wedding limit exceeded. Plan allows {limit} weddings, you have {current}"
                    }
            elif resource_type == "ai_credits":
                current = usage.get("ai_credits_used_month", 0)
                limit = limits_source.get("ai_credits_monthly", 10)
                remaining = max(0, limit - current)
                if current + requested_amount > limit:
                    return {
                        "allowed": False,
                        "current_usage": current,
                        "limit": limit,
                        "remaining": remaining,
                        "message": f"AI credits limit exceeded. Plan allows {limit} credits per month, you have used {current}"
                    }
                # Return early with remaining and limit for ai_credits
                return {
                    "allowed": True,
                    "current_usage": current,
                    "limit": limit,
                    "remaining": remaining
                }

            elif resource_type == "staff_seats":
                current = usage.get("staff_seats_used", 0)
                limit = limits_source.get("staff_seats", 0)
                if current + requested_amount > limit:
                    return {
                        "allowed": False,
                        "current_usage": current,
                        "limit": limit,
                        "message": f"Staff seats limit exceeded. Plan allows {limit} staff accounts"
                    }

            return {"allowed": True, "current_usage": usage.get(f"{resource_type}_used", 0)}

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error checking usage limits: {str(e)}")

    async def increment_usage(self, user_id: str, resource_type: str, amount: int = 1) -> dict:
        """Increment usage for a specific resource"""
        try:
            current_month = datetime.now(timezone.utc).strftime("%Y-%m")
            # Map resource types to database fields
            field_mapping = {
                "weddings": "weddings_count",
                "ai_credits": "ai_credits_used_month",
                "staff_seats": "staff_seats_used"
            }

            if resource_type not in field_mapping:
                raise HTTPException(status_code=400, detail=f"Invalid resource type: {resource_type}")

            field_name = field_mapping[resource_type]

            result = await self.usage_collection.update_one(
                {"user_id": user_id, "current_month": current_month},
                {
                    "$inc": {field_name: amount},
                    "$set": {"last_updated": datetime.now(timezone.utc)}
                }
            )

            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="Usage tracking record not found")

            return {"message": f"Usage incremented: {resource_type} +{amount}"}

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error incrementing usage: {str(e)}")

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
                raise HTTPException(status_code=404, detail="No active subscription found")

            # Create new usage tracking record for the new month
            new_usage_id = f"usage_{user_id}_{current_month}"

            usage_data = {
                "_id": new_usage_id,
                "user_id": user_id,
                "subscription_id": subscription["_id"],
                "weddings_count": 0,  # Keep wedding count (doesn't reset monthly)
                "ai_credits_used_month": 0,  # Reset monthly credits
                "storage_used_gb": 0.0,  # Keep storage count
                "staff_seats_used": 0,
                "current_month": current_month,
                "credits_reset_date": next_reset,
                "last_updated": now
            }
            await self.usage_collection.update_one(
                {"_id": new_usage_id},
                {"$set": usage_data},
                upsert=True
            )

            return {"message": "Monthly usage counters reset successfully"}

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error resetting monthly usage: {str(e)}")

    # Analytics and Reporting
    async def get_subscription_analytics(self) -> dict:
        """Get platform-wide subscription analytics (ROOT_ADMIN only)"""
        try:
            # Total subscriptions by status
            status_counts = {}
            for status in ["trial", "active", "cancelled", "expired"]:
                count = await self.subscriptions_collection.count_documents({"status": status})
                status_counts[status] = count
            # Total subscriptions by plan
            plan_pipeline = [
                {"$group": {"_id": "$plan_id", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
            plan_counts_cursor = self.subscriptions_collection.aggregate(plan_pipeline)
            plan_counts = await plan_counts_cursor.to_list(length=None)
            # Monthly recurring revenue (MRR) calculation - includes both monthly AND yearly
            # For yearly subscriptions, we calculate the monthly equivalent (price_yearly / 12)
            active_subs = await self.subscriptions_collection.find({
                "status": "active"
            }).to_list(length=None)

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
                "plan_breakdown": {item["_id"]: item["count"] for item in plan_counts},
                "monthly_recurring_revenue": round(mrr, 2),
                "annual_recurring_revenue": round(arr, 2),
                "mrr_breakdown": {
                    "from_monthly_billing": round(mrr_from_monthly, 2),
                    "from_yearly_billing": round(mrr_from_yearly, 2),
                    "monthly_subscribers": monthly_sub_count,
                    "yearly_subscribers": yearly_sub_count
                },
                "generated_at": datetime.now(timezone.utc)
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error generating analytics: {str(e)}")

    async def list_all_subscriptions(self, status_filter: Optional[str] = None) -> List[dict]:
        """List all user subscriptions with details (ROOT_ADMIN only)"""
        try:
            # Build query
            query = {}
            if status_filter and status_filter != "all":
                query["status"] = status_filter

            # Fetch all subscriptions
            subscriptions = await self.subscriptions_collection.find(query).to_list(length=None)

            # Build lookup maps for plans and users
            plans = await self.plans_collection.find({}).to_list(length=None)
            plans_map = {str(plan.get("_id", "")): plan for plan in plans}

            users = await self.users_collection.find({}).to_list(length=None)
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
                    "company_name": user.get("company_name", sub.get("company_name", "")),
                    "plan_id": plan_id,
                    "plan_name": plan.get("name", sub.get("plan_name", "Unknown Plan")),
                    "status": sub.get("status", "unknown"),
                    "billing_interval": billing_interval,
                    "amount": amount,
                    "current_period_start": format_date(sub.get("current_period_start")),
                    "current_period_end": format_date(sub.get("current_period_end")),
                    "created_at": format_date(sub.get("created_at")),
                }
                formatted_subscriptions.append(formatted_sub)

            return formatted_subscriptions
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error listing subscriptions: {str(e)}")


# Singleton instance
subscription_service = SubscriptionService()
