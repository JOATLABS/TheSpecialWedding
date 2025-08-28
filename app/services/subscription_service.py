from fastapi import HTTPException
from app.core.database import mongo
from app.models.subscription import (
    SubscriptionPlanModel, 
    UserSubscriptionModel, 
    UsageTrackingModel,
    SubscriptionStatus,
    BillingInterval
)
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import calendar
from bson import ObjectId

class SubscriptionService:
    def __init__(self):
        self.plans_collection = mongo.db["subscription_plans"]
        self.subscriptions_collection = mongo.db["user_subscriptions"]
        self.usage_collection = mongo.db["usage_tracking"]
        self.users_collection = mongo.db["users"]
        self.weddings_collection = mongo.db["weddings"]

    # Subscription Plan Management (ROOT_ADMIN only)
    def create_plan(self, plan_data: dict, creator_email: str) -> dict:
        """Create a new subscription plan"""
        try:
            plan_data["_id"] = f"plan_{plan_data['name'].lower().replace(' ', '_')}"
            plan_data["created_by"] = creator_email
            plan_data["created_at"] = datetime.utcnow()
            plan_data["updated_at"] = datetime.utcnow()
            
            # Check if plan ID already exists
            existing = self.plans_collection.find_one({"_id": plan_data["_id"]})
            if existing:
                raise HTTPException(status_code=400, detail="Plan with this name already exists")
            
            result = self.plans_collection.insert_one(plan_data)
            return {"message": "Subscription plan created successfully", "plan_id": plan_data["_id"]}
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error creating subscription plan: {str(e)}")

    def list_plans(self, include_inactive: bool = False) -> List[dict]:
        """List all subscription plans"""
        try:
            query = {} if include_inactive else {"is_active": True}
            plans = list(self.plans_collection.find(query).sort("sort_order", 1))
            return plans
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error listing plans: {str(e)}")

    def get_plan(self, plan_id: str) -> dict:
        """Get subscription plan by ID"""
        try:
            plan = self.plans_collection.find_one({"_id": plan_id})
            if not plan:
                raise HTTPException(status_code=404, detail="Subscription plan not found")
            return plan
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error retrieving plan: {str(e)}")

    def update_plan(self, plan_id: str, update_data: dict) -> dict:
        """Update subscription plan"""
        try:
            # Remove protected fields
            protected_fields = ["_id", "created_at", "created_by"]
            for field in protected_fields:
                update_data.pop(field, None)
            
            update_data["updated_at"] = datetime.utcnow()
            
            result = self.plans_collection.update_one(
                {"_id": plan_id},
                {"$set": update_data}
            )
            
            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="Subscription plan not found")
            
            return {"message": "Subscription plan updated successfully"}
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error updating plan: {str(e)}")

    def delete_plan(self, plan_id: str) -> dict:
        """Delete subscription plan (only if no active subscriptions)"""
        try:
            # Check if any users have active subscriptions to this plan
            active_subs = self.subscriptions_collection.count_documents({
                "plan_id": plan_id,
                "status": {"$in": ["active", "trial"]}
            })
            
            if active_subs > 0:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Cannot delete plan: {active_subs} active subscriptions exist"
                )
            
            result = self.plans_collection.delete_one({"_id": plan_id})
            
            if result.deleted_count == 0:
                raise HTTPException(status_code=404, detail="Subscription plan not found")
            
            return {"message": "Subscription plan deleted successfully"}
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error deleting plan: {str(e)}")

    # User Subscription Management
    def assign_subscription(self, user_id: str, plan_id: str, billing_interval: str = "monthly", 
                          trial_days: int = 14, creator_email: str = "") -> dict:
        """Assign subscription plan to user"""
        try:
            # Verify user exists
            user = self.users_collection.find_one({"_id": ObjectId(user_id)})
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Verify plan exists
            plan = self.get_plan(plan_id)
            
            # Check if user already has an active subscription
            existing_sub = self.subscriptions_collection.find_one({
                "user_id": user_id,
                "status": {"$in": ["active", "trial"]}
            })
            
            if existing_sub:
                raise HTTPException(status_code=400, detail="User already has an active subscription")
            
            # Create subscription
            now = datetime.utcnow()
            trial_end = now + timedelta(days=trial_days) if trial_days > 0 else now
            
            if billing_interval == "yearly":
                period_end = now + timedelta(days=365)
            else:  # monthly
                # Calculate next month
                if now.month == 12:
                    period_end = now.replace(year=now.year + 1, month=1)
                else:
                    period_end = now.replace(month=now.month + 1)
            
            subscription_data = {
                "_id": f"sub_{user_id}_{plan_id}_{int(now.timestamp())}",
                "user_id": user_id,
                "user_email": user["email"],
                "plan_id": plan_id,
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
            
            result = self.subscriptions_collection.insert_one(subscription_data)
            
            # Initialize usage tracking
            self.initialize_usage_tracking(user_id, subscription_data["_id"])
            
            # Update user subscription info
            self.users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {
                    "subscription_plan_id": plan_id,
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

    def get_user_subscription(self, user_id: str) -> Optional[dict]:
        """Get user's current subscription"""
        try:
            subscription = self.subscriptions_collection.find_one({
                "user_id": user_id,
                "status": {"$in": ["active", "trial"]}
            })
            return subscription
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error retrieving subscription: {str(e)}")

    def cancel_subscription(self, user_id: str, reason: str = "") -> dict:
        """Cancel user subscription"""
        try:
            now = datetime.utcnow()
            
            result = self.subscriptions_collection.update_one(
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
            self.users_collection.update_one(
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
    def initialize_usage_tracking(self, user_id: str, subscription_id: str) -> dict:
        """Initialize usage tracking for a new subscription"""
        try:
            now = datetime.utcnow()
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
            self.usage_collection.update_one(
                {"_id": usage_data["_id"]},
                {"$set": usage_data},
                upsert=True
            )
            
            return usage_data
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error initializing usage tracking: {str(e)}")

    def get_usage_stats(self, user_id: str) -> dict:
        """Get current usage statistics for user"""
        try:
            current_month = datetime.utcnow().strftime("%Y-%m")
            
            usage = self.usage_collection.find_one({
                "user_id": user_id,
                "current_month": current_month
            })
            
            if not usage:
                # Initialize if doesn't exist
                subscription = self.get_user_subscription(user_id)
                if subscription:
                    usage = self.initialize_usage_tracking(user_id, subscription["_id"])
                else:
                    return {"error": "No active subscription found"}
            
            return usage
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error retrieving usage stats: {str(e)}")

    def check_usage_limits(self, user_id: str, resource_type: str, requested_amount: int = 1) -> dict:
        """Check if user can use more of a resource without exceeding limits"""
        try:
            subscription = self.get_user_subscription(user_id)
            if not subscription:
                raise HTTPException(status_code=403, detail="No active subscription found")
            
            plan = self.get_plan(subscription["plan_id"])
            usage = self.get_usage_stats(user_id)
            
            # Check limits based on resource type
            if resource_type == "weddings":
                current = usage.get("weddings_count", 0)
                limit = plan.get("max_weddings", 1)
                if limit != -1 and current + requested_amount > limit:
                    return {
                        "allowed": False,
                        "current_usage": current,
                        "limit": limit,
                        "message": f"Wedding limit exceeded. Plan allows {limit} weddings, you have {current}"
                    }
            
            elif resource_type == "ai_credits":
                current = usage.get("ai_credits_used_month", 0)
                limit = plan.get("ai_credits_monthly", 10)
                if current + requested_amount > limit:
                    return {
                        "allowed": False,
                        "current_usage": current,
                        "limit": limit,
                        "message": f"AI credits limit exceeded. Plan allows {limit} credits per month, you have used {current}"
                    }
            
            
            elif resource_type == "staff_seats":
                current = usage.get("staff_seats_used", 0)
                limit = plan.get("staff_seats", 0)
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

    def increment_usage(self, user_id: str, resource_type: str, amount: int = 1) -> dict:
        """Increment usage for a specific resource"""
        try:
            current_month = datetime.utcnow().strftime("%Y-%m")
            
            # Map resource types to database fields
            field_mapping = {
                "weddings": "weddings_count",
                "ai_credits": "ai_credits_used_month",
                "staff_seats": "staff_seats_used"
            }
            
            if resource_type not in field_mapping:
                raise HTTPException(status_code=400, detail=f"Invalid resource type: {resource_type}")
            
            field_name = field_mapping[resource_type]
            
            result = self.usage_collection.update_one(
                {"user_id": user_id, "current_month": current_month},
                {
                    "$inc": {field_name: amount},
                    "$set": {"last_updated": datetime.utcnow()}
                }
            )
            
            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="Usage tracking record not found")
            
            return {"message": f"Usage incremented: {resource_type} +{amount}"}
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error incrementing usage: {str(e)}")

    def reset_monthly_usage(self, user_id: str) -> dict:
        """Reset monthly usage counters (called on subscription renewal)"""
        try:
            now = datetime.utcnow()
            current_month = now.strftime("%Y-%m")
            
            # Calculate next reset date
            if now.month == 12:
                next_reset = datetime(now.year + 1, 1, 1)
            else:
                next_reset = datetime(now.year, now.month + 1, 1)
            
            subscription = self.get_user_subscription(user_id)
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
            
            self.usage_collection.update_one(
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
    def get_subscription_analytics(self) -> dict:
        """Get platform-wide subscription analytics (ROOT_ADMIN only)"""
        try:
            # Total subscriptions by status
            status_counts = {}
            for status in ["trial", "active", "cancelled", "expired"]:
                count = self.subscriptions_collection.count_documents({"status": status})
                status_counts[status] = count
            
            # Total subscriptions by plan
            plan_pipeline = [
                {"$group": {"_id": "$plan_id", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
            plan_counts = list(self.subscriptions_collection.aggregate(plan_pipeline))
            
            # Monthly recurring revenue (MRR) calculation
            active_subs = list(self.subscriptions_collection.find({
                "status": "active",
                "billing_interval": "monthly"
            }))
            
            mrr = 0
            for sub in active_subs:
                plan = self.get_plan(sub["plan_id"])
                mrr += plan.get("price_monthly", 0)
            
            return {
                "total_subscriptions": sum(status_counts.values()),
                "status_breakdown": status_counts,
                "plan_breakdown": {item["_id"]: item["count"] for item in plan_counts},
                "monthly_recurring_revenue": mrr,
                "generated_at": datetime.utcnow()
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error generating analytics: {str(e)}")