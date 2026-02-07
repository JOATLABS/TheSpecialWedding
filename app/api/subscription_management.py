from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from app.dependencies.auth_extended import require_root_admin, require_admin_or_planner, ExtendedAuthUser
from app.services.subscription_service import SubscriptionService
from app.models.subscription import (
    CreateSubscriptionPlanRequest,
    UpdateSubscriptionPlanRequest,
    AssignSubscriptionRequest,
    SubscriptionPlanModel,
    UserSubscriptionModel
)

router = APIRouter()
subscription_service = SubscriptionService()

# ==================== SUBSCRIPTION PLAN MANAGEMENT (ROOT_ADMIN ONLY) ====================

@router.post("/subscription-plans", tags=["ROOT_ADMIN"])
async def create_subscription_plan(
    plan_data: CreateSubscriptionPlanRequest,
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """Create a new subscription plan - ROOT_ADMIN only"""
    return await subscription_service.create_plan(plan_data.dict(), current_user.email)

@router.get("/subscription-plans", tags=["ROOT_ADMIN"])
async def list_subscription_plans(
    include_inactive: bool = Query(False, description="Include inactive plans"),
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """List all subscription plans - ROOT_ADMIN only"""
    return await subscription_service.list_plans(include_inactive)

@router.get("/subscription-plans/{plan_id}", tags=["ROOT_ADMIN"])
async def get_subscription_plan(
    plan_id: str,
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """Get subscription plan details - ROOT_ADMIN only"""
    return await subscription_service.get_plan(plan_id)

@router.put("/subscription-plans/{plan_id}", tags=["ROOT_ADMIN"])
async def update_subscription_plan(
    plan_id: str,
    update_data: UpdateSubscriptionPlanRequest,
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """Update subscription plan - ROOT_ADMIN only"""
    return await subscription_service.update_plan(plan_id, update_data.dict(exclude_unset=True))

@router.delete("/subscription-plans/{plan_id}", tags=["ROOT_ADMIN"])
async def delete_subscription_plan(
    plan_id: str,
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """Delete subscription plan - ROOT_ADMIN only"""
    return await subscription_service.delete_plan(plan_id)

# ==================== USER SUBSCRIPTION MANAGEMENT ====================

@router.post("/users/{user_id}/subscription", tags=["ROOT_ADMIN"])
async def assign_subscription_to_user(
    user_id: str,
    subscription_data: AssignSubscriptionRequest,
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """Assign subscription plan to user - ROOT_ADMIN only"""
    return await subscription_service.assign_subscription(
        user_id=user_id,
        plan_id=subscription_data.plan_id,
        billing_interval=subscription_data.billing_interval,
        trial_days=subscription_data.trial_days,  # Default is 0 (no trial)
        creator_email=current_user.email
    )

@router.get("/users/{user_id}/subscription", tags=["ROOT_ADMIN", "User"])
async def get_user_subscription(
    user_id: str,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Get user's current subscription"""
    # Users can only see their own subscription unless they're ROOT_ADMIN
    if not current_user.is_root_admin and current_user.user_data.get("_id") != user_id:
        raise HTTPException(status_code=403, detail="Can only view your own subscription")

    subscription = await subscription_service.get_user_subscription(user_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="No active subscription found")

    return subscription

@router.delete("/users/{user_id}/subscription", tags=["ROOT_ADMIN"])
async def cancel_user_subscription(
    user_id: str,
    reason: str = Query("", description="Cancellation reason"),
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """Cancel user subscription - ROOT_ADMIN only"""
    return await subscription_service.cancel_subscription(user_id, reason)


@router.patch("/users/{user_id}/subscription/billing-interval", tags=["ROOT_ADMIN", "User"])
async def change_billing_interval(
    user_id: str,
    new_interval: str = Query(..., description="New billing interval: monthly or yearly"),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Change subscription billing interval with proration.

    Users can switch their own subscription between monthly and yearly billing.
    ROOT_ADMIN can change any user's billing interval.

    Proration is applied automatically:
    - Switching to yearly: Credit for unused monthly time, charge for yearly
    - Switching to monthly: Credit for unused yearly time, charge for monthly
    """
    # Users can only change their own billing interval unless they're ROOT_ADMIN
    if not current_user.is_root_admin and current_user.user_data.get("_id") != user_id:
        raise HTTPException(status_code=403, detail="Can only change your own billing interval")

    from app.services.stripe_service import stripe_service
    return await stripe_service.change_subscription_billing_interval(user_id, new_interval)


# ==================== USAGE TRACKING & LIMITS ====================

@router.get("/users/{user_id}/usage", tags=["ROOT_ADMIN", "User"])
async def get_user_usage_stats(
    user_id: str,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Get user's current usage statistics"""
    # Users can only see their own usage unless they're ROOT_ADMIN
    if not current_user.is_root_admin and current_user.user_data.get("_id") != user_id:
        raise HTTPException(status_code=403, detail="Can only view your own usage")
    return await subscription_service.get_usage_stats(user_id)

@router.post("/users/{user_id}/usage/check", tags=["ROOT_ADMIN", "User"])
async def check_usage_limits(
    user_id: str,
    resource_type: str = Query(..., description="Resource type: weddings, ai_credits, staff_seats"),
    amount: int = Query(1, description="Amount to check"),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Check if user can use more of a resource without exceeding limits"""
    # Users can only check their own limits unless they're ROOT_ADMIN
    if not current_user.is_root_admin and current_user.user_data.get("_id") != user_id:
        raise HTTPException(status_code=403, detail="Can only check your own limits")
    return await subscription_service.check_usage_limits(user_id, resource_type, amount)

@router.post("/users/{user_id}/usage/increment", tags=["ROOT_ADMIN"])
async def increment_user_usage(
    user_id: str,
    resource_type: str = Query(..., description="Resource type: weddings, ai_credits, staff_seats"),
    amount: int = Query(1, description="Amount to increment"),
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """Increment usage for a specific resource - ROOT_ADMIN only"""
    return await subscription_service.increment_usage(user_id, resource_type, amount)

@router.post("/users/{user_id}/usage/reset", tags=["ROOT_ADMIN"])
async def reset_monthly_usage(
    user_id: str,
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """Reset monthly usage counters - ROOT_ADMIN only"""
    return await subscription_service.reset_monthly_usage(user_id)

# ==================== ANALYTICS & REPORTING ====================

@router.get("/analytics/subscriptions", tags=["ROOT_ADMIN"])
def get_subscription_analytics(
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """Get platform-wide subscription analytics - ROOT_ADMIN only"""
    return subscription_service.get_subscription_analytics()

@router.get("/subscriptions", tags=["ROOT_ADMIN"])
async def list_all_subscriptions(
    status: str = Query(None, description="Filter by status (active, trial, cancelled, expired)"),
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """List all user subscriptions for billing dashboard - ROOT_ADMIN only"""
    return await subscription_service.list_all_subscriptions(status_filter=status)

# ==================== SUBSCRIPTION LIMITS MIDDLEWARE ====================

def require_subscription_limit(resource_type: str, amount: int = 1):
    """Factory function to create subscription limit checking dependencies"""
    async def limit_checker(current_user: ExtendedAuthUser = Depends(require_admin_or_planner)) -> ExtendedAuthUser:
        # ROOT_ADMIN bypasses all limits
        if current_user.is_root_admin:
            return current_user
        # Check user's subscription limits
        user_id = current_user.user_data.get("_id")
        if not user_id:
            raise HTTPException(status_code=403, detail="User ID not found")

        limits_check = await subscription_service.check_usage_limits(user_id, resource_type, amount)

        if not limits_check.get("allowed", False):
            raise HTTPException(
                status_code=402,  # Payment Required
                detail=limits_check.get("message", f"Subscription limit exceeded for {resource_type}")
            )
        return current_user
    return limit_checker

# ==================== SYSTEM ADMINISTRATION ====================

@router.post("/system/sync-plans-to-stripe", tags=["ROOT_ADMIN"])
async def sync_plans_to_stripe(current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """
    Manually sync all existing subscription plans to Stripe Products/Prices.
    Useful if you added Stripe credentials after creating plans.
    """
    from app.services.stripe_service import stripe_service

    plans = await subscription_service.list_plans(include_inactive=True)
    synced_count = 0
    errors = []

    for plan in plans:
        try:
            stripe_data = stripe_service.sync_plan_to_stripe(plan)
            # Update local DB with new IDs
            await subscription_service.update_plan(plan["_id"], stripe_data)
            synced_count += 1
        except Exception as e:
            errors.append(f"Plan {plan.get('name', 'Unknown')}: {str(e)}")

    return {
        "message": f"Synced {synced_count} plans to Stripe",
        "errors": errors
    }

@router.post("/system/seed-default-plans", tags=["ROOT_ADMIN"])
async def seed_default_subscription_plans(current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Seed default subscription plans - ROOT_ADMIN only"""
    default_plans = [
        {
            "name": "Boutique",
            "description": "14-day free trial to explore all features",
            "price_monthly": 0.00,
            "price_yearly": 0.00,
            "max_weddings": 1,
            "max_guests_per_wedding": 50,
            "ai_credits_monthly": 10,
            "storage_gb": 1,
            "staff_seats": 0,
            "features": {
                "basic_website_builder": True,
                "guest_management": True,
                "rsvp_system": True,
                "basic_email_templates": True,
                "photo_gallery": True,
                "basic_analytics": False,
                "mobile_app_access": True,
                "email_support": True,
                "ai_tools": False,
                "advanced_reporting": False,
                "white_label": False,
                "custom_integrations": False,
                "multi_user_collaboration": False,
                "priority_support": False,
                "custom_domain": False
            },
            "is_featured": False,
            "is_active": True,
            "display_order": 0,
            "sort_order": 0
        },
        {
            "name": "Starter",
            "description": "Perfect for new wedding planners starting their business",
            "price_monthly": 49.99,
            "price_yearly": 479.99,
            "max_weddings": 3,
            "max_guests_per_wedding": 150,
            "ai_credits_monthly": 50,
            "storage_gb": 5,
            "staff_seats": 1,
            "features": {
                "basic_website_builder": True,
                "guest_management": True,
                "rsvp_system": True,
                "basic_email_templates": True,
                "photo_gallery": True,
                "basic_analytics": True,
                "mobile_app_access": True,
                "email_support": True,
                "ai_tools": False,
                "advanced_reporting": False,
                "white_label": False,
                "custom_integrations": False,
                "multi_user_collaboration": False,
                "priority_support": False,
                "custom_domain": False
            },
            "is_featured": False,
            "is_active": True,
            "display_order": 1,
            "sort_order": 1
        },
        {
            "name": "Professional",
            "description": "For established planners managing multiple weddings",
            "price_monthly": 99.99,
            "price_yearly": 959.99,
            "max_weddings": 10,
            "max_guests_per_wedding": 300,
            "ai_credits_monthly": 200,
            "storage_gb": 25,
            "staff_seats": 3,
            "features": {
                "basic_website_builder": True,
                "guest_management": True,
                "rsvp_system": True,
                "basic_email_templates": True,
                "photo_gallery": True,
                "basic_analytics": True,
                "mobile_app_access": True,
                "email_support": True,
                "ai_tools": True,
                "advanced_reporting": True,
                "white_label": False,
                "custom_integrations": True,
                "multi_user_collaboration": True,
                "priority_support": True,
                "custom_domain": True
            },
            "is_featured": True,
            "is_active": True,
            "display_order": 2,
            "sort_order": 2
        },
        {
            "name": "Enterprise",
            "description": "For large wedding planning agencies and high-volume planners",
            "price_monthly": 199.99,
            "price_yearly": 1919.99,
            "max_weddings": -1,
            "max_guests_per_wedding": -1,
            "ai_credits_monthly": 1000,
            "storage_gb": 100,
            "staff_seats": -1,
            "features": {
                "basic_website_builder": True,
                "guest_management": True,
                "rsvp_system": True,
                "basic_email_templates": True,
                "photo_gallery": True,
                "basic_analytics": True,
                "mobile_app_access": True,
                "email_support": True,
                "ai_tools": True,
                "advanced_reporting": True,
                "white_label": True,
                "custom_integrations": True,
                "multi_user_collaboration": True,
                "priority_support": True,
                "custom_domain": True
            },
            "is_featured": False,
            "is_active": True,
            "display_order": 3,
            "sort_order": 3
        }
    ]

    created_plans = []
    skipped_plans = []

    for plan_data in default_plans:
        # Check if plan already exists
        existing_plans = await subscription_service.list_plans(include_inactive=True)
        existing_plan = next((p for p in existing_plans if p["name"] == plan_data["name"]), None)

        if existing_plan:
            skipped_plans.append(plan_data["name"])
            continue

        try:
            # Note: create_plan will internally call stripe_service.sync_plan_to_stripe
            await subscription_service.create_plan(plan_data, current_user.email)
            created_plans.append(plan_data["name"])  # Store the plan name instead of the result
        except Exception as e:
            # If seeding fails (e.g. stripe config missing), we might want to log it but continue?
            # For now, let's return error so admin knows.
            return {"error": f"Failed to create plan '{plan_data['name']}': {str(e)}"}
    return {
        "message": "Default subscription plans seeding completed",
        "created_plans": len(created_plans),
        "skipped_plans": len(skipped_plans),
        "details": {
            "created": created_plans,
            "skipped": skipped_plans
        }
    }

# ==================== PUBLIC SUBSCRIPTION PLANS (FOR PRICING PAGE) ====================

@router.get("/public/subscription-plans", tags=["Public"])
async def get_public_subscription_plans():
    """Get active subscription plans for public pricing page.

    Returns sanitized plan data - excludes internal IDs (Stripe, MongoDB metadata)
    to prevent data leakage to competitors or malicious actors.
    """
    plans = await subscription_service.list_plans(include_inactive=False)

    # Sanitize: only return public-safe fields
    public_plans = []
    for plan in plans:
        public_plans.append({
            "_id": plan["_id"],  # Plan ID needed for selection
            "name": plan.get("name"),
            "description": plan.get("description"),
            "price_monthly": plan.get("price_monthly", 0),
            "price_yearly": plan.get("price_yearly"),
            "max_weddings": plan.get("max_weddings", 1),
            "max_guests_per_wedding": plan.get("max_guests_per_wedding", 100),
            "ai_credits_monthly": plan.get("ai_credits_monthly", 10),
            "storage_gb": plan.get("storage_gb", 1),
            "staff_seats": plan.get("staff_seats", 0),
            "features": plan.get("features", {}),
            "features_list": plan.get("features_list", []),
            "is_featured": plan.get("is_featured", False),
            "is_active": plan.get("is_active", True),
            "display_order": plan.get("display_order", plan.get("sort_order", 0)),
            # Explicitly EXCLUDE: stripe_product_id, stripe_price_id_*, created_by, etc.
        })

    return public_plans

@router.get("/public/subscription-plans/{plan_id}", tags=["Public"])
async def get_public_subscription_plan(plan_id: str):
    """Get subscription plan details for public view"""
    plan = await subscription_service.get_plan(plan_id)
    # Remove sensitive fields for public view
    public_plan = {
        "id": plan["_id"],
        "name": plan["name"],
        "description": plan.get("description"),
        "price_monthly": plan["price_monthly"],
        "price_yearly": plan.get("price_yearly"),
        "max_weddings": plan["max_weddings"],
        "max_guests_per_wedding": plan["max_guests_per_wedding"],
        "ai_credits_monthly": plan["ai_credits_monthly"],
        "storage_gb": plan["storage_gb"],
        "staff_seats": plan["staff_seats"],
        "features": plan.get("features", {}),
        "is_featured": plan.get("is_featured", False)
    }
    return public_plan
