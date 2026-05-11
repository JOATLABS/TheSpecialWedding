from fastapi import APIRouter, Depends, HTTPException, Query

from app.constants.billing import (
    CANONICAL_PUBLIC_PLAN_BILLING_MODEL,
    plan_billing_model,
)
from app.dependencies.auth_extended import (
    ExtendedAuthUser,
    require_admin_or_planner,
    require_root_admin,
)
from app.models.subscription import (
    AssignSubscriptionRequest,
    CreateSubscriptionPlanRequest,
    UpdateSubscriptionPlanRequest,
)
from app.services.subscription_service import SubscriptionService

router = APIRouter()
subscription_service = SubscriptionService()

# ==================== SUBSCRIPTION PLAN MANAGEMENT (ROOT_ADMIN ONLY) ====================


@router.post("/subscription-plans", tags=["ROOT_ADMIN"])
async def create_subscription_plan(
    plan_data: CreateSubscriptionPlanRequest,
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Create a new subscription plan - ROOT_ADMIN only"""
    return await subscription_service.create_plan(plan_data.dict(), current_user.email)


@router.get("/subscription-plans", tags=["ROOT_ADMIN"])
async def list_subscription_plans(
    include_inactive: bool = Query(False, description="Include inactive plans"),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """List all subscription plans - ROOT_ADMIN only"""
    return await subscription_service.list_plans(include_inactive)


@router.get("/subscription-plans/{plan_id}", tags=["ROOT_ADMIN"])
async def get_subscription_plan(
    plan_id: str, current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """Get subscription plan details - ROOT_ADMIN only"""
    return await subscription_service.get_plan(plan_id)


@router.put("/subscription-plans/{plan_id}", tags=["ROOT_ADMIN"])
async def update_subscription_plan(
    plan_id: str,
    update_data: UpdateSubscriptionPlanRequest,
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Update subscription plan - ROOT_ADMIN only"""
    return await subscription_service.update_plan(
        plan_id, update_data.dict(exclude_unset=True)
    )


@router.delete("/subscription-plans/{plan_id}", tags=["ROOT_ADMIN"])
async def delete_subscription_plan(
    plan_id: str, current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """Delete subscription plan - ROOT_ADMIN only"""
    return await subscription_service.delete_plan(plan_id)


# ==================== USER SUBSCRIPTION MANAGEMENT ====================


def _can_read_usage_for_user(current_user: ExtendedAuthUser, user_id: str) -> bool:
    """Allow self-service usage reads plus team-member owner-scope reads.

    Frontend planner-cap surfaces intentionally use the planner owner's id for
    team-member sessions because subscription caps bill against the owner plan,
    not the acting team member. Keep that owner-scope allowance tightly limited
    to read-only usage endpoints; unrelated user ids still fail closed.
    """
    if current_user.is_root_admin:
        return True

    session_user_id = str(current_user.user_data.get("_id") or "")
    if session_user_id and session_user_id == user_id:
        return True

    owner_id = str(current_user.parent_planner_id or "")
    return bool(current_user.is_team_member and owner_id and owner_id == user_id)


@router.post("/users/{user_id}/subscription", tags=["ROOT_ADMIN"])
async def assign_subscription_to_user(
    user_id: str,
    subscription_data: AssignSubscriptionRequest,
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Assign subscription plan to user - ROOT_ADMIN only"""
    return await subscription_service.assign_subscription(
        user_id=user_id,
        plan_id=subscription_data.plan_id,
        billing_interval=subscription_data.billing_interval,
        trial_days=subscription_data.trial_days,  # Default is 0 (no trial)
        creator_email=current_user.email,
    )


@router.get("/users/{user_id}/subscription", tags=["ROOT_ADMIN", "User"])
async def get_user_subscription(
    user_id: str, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Get user's current subscription"""
    # Users can only see their own subscription unless they're ROOT_ADMIN
    if (
        not current_user.is_root_admin
        and str(current_user.user_data.get("_id")) != user_id
    ):
        raise HTTPException(
            status_code=403, detail="Can only view your own subscription"
        )

    subscription = await subscription_service.get_user_subscription(user_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="No active subscription found")

    return subscription


@router.delete("/users/{user_id}/subscription", tags=["ROOT_ADMIN"])
async def cancel_user_subscription(
    user_id: str,
    reason: str = Query("", description="Cancellation reason"),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Cancel user subscription - ROOT_ADMIN only"""
    return await subscription_service.cancel_subscription(user_id, reason)


@router.patch(
    "/users/{user_id}/subscription/billing-interval", tags=["ROOT_ADMIN", "User"]
)
async def change_billing_interval(
    user_id: str,
    new_interval: str = Query(
        ..., description="New billing interval: monthly or yearly"
    ),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
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
    if (
        not current_user.is_root_admin
        and str(current_user.user_data.get("_id")) != user_id
    ):
        raise HTTPException(
            status_code=403, detail="Can only change your own billing interval"
        )

    from app.services.stripe_service import stripe_service

    return await stripe_service.change_subscription_billing_interval(
        user_id, new_interval
    )


# ==================== USAGE TRACKING & LIMITS ====================


@router.get("/users/{user_id}/usage", tags=["ROOT_ADMIN", "User"])
async def get_user_usage_stats(
    user_id: str, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Get user's current usage statistics"""
    if not _can_read_usage_for_user(current_user, user_id):
        raise HTTPException(status_code=403, detail="Can only view your own usage")
    return await subscription_service.get_usage_stats(user_id)


@router.post("/users/{user_id}/usage/check", tags=["ROOT_ADMIN", "User"])
async def check_usage_limits(
    user_id: str,
    resource_type: str = Query(
        ...,
        description="Resource type: weddings, ai_credits, staff_seats, storage",
    ),
    amount: int = Query(
        1,
        description=(
            "Amount to check. For storage this is bytes, not GB. For "
            "weddings/staff_seats this is count. For ai_credits this "
            "is credits."
        ),
    ),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """Check if user can use more of a resource without exceeding limits.

    Behavior per resource type:

    * ``weddings``, ``staff_seats``, ``storage`` — **hard cap**.
      Response includes ``allowed=false`` when the projected total
      would exceed the plan limit. Callers must refuse the action.
    * ``ai_credits`` — **soft cap**. ``allowed`` is always true; the
      response carries ``overage``, ``overage_credits``, and
      ``overage_cost_cents`` for the UI and billing to pick up.
    """
    if not _can_read_usage_for_user(current_user, user_id):
        raise HTTPException(status_code=403, detail="Can only check your own limits")
    return await subscription_service.check_usage_limits(user_id, resource_type, amount)


@router.post("/users/{user_id}/usage/increment", tags=["ROOT_ADMIN"])
async def increment_user_usage(
    user_id: str,
    resource_type: str = Query(
        ...,
        description="Resource type: weddings, ai_credits, staff_seats, storage",
    ),
    amount: int = Query(1, description="Amount to increment"),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Increment usage for a specific resource - ROOT_ADMIN only"""
    return await subscription_service.increment_usage(user_id, resource_type, amount)


@router.post("/users/{user_id}/usage/reset", tags=["ROOT_ADMIN"])
async def reset_monthly_usage(
    user_id: str, current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """Reset monthly usage counters - ROOT_ADMIN only"""
    return await subscription_service.reset_monthly_usage(user_id)


# ==================== ANALYTICS & REPORTING ====================


@router.get("/analytics/subscriptions", tags=["ROOT_ADMIN"])
async def get_subscription_analytics(
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Get platform-wide subscription analytics - ROOT_ADMIN only"""
    return await subscription_service.get_subscription_analytics()


@router.get("/subscriptions", tags=["ROOT_ADMIN"])
async def list_all_subscriptions(
    status: str = Query(
        None, description="Filter by status (active, trial, cancelled, expired)"
    ),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """List all user subscriptions for billing dashboard - ROOT_ADMIN only"""
    return await subscription_service.list_all_subscriptions(status_filter=status)


# ==================== SUBSCRIPTION LIMITS MIDDLEWARE ====================


def require_subscription_limit(resource_type: str, amount: int = 1):
    """Factory function to create subscription limit checking dependencies"""

    async def limit_checker(
        current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
    ) -> ExtendedAuthUser:
        # ROOT_ADMIN bypasses all limits
        if current_user.is_root_admin:
            return current_user
        # Check user's subscription limits
        user_id = current_user.user_data.get("_id")
        if not user_id:
            raise HTTPException(status_code=403, detail="User ID not found")

        limits_check = await subscription_service.check_usage_limits(
            user_id, resource_type, amount
        )

        if not limits_check.get("allowed", False):
            raise HTTPException(
                status_code=402,  # Payment Required
                detail=limits_check.get(
                    "message", f"Subscription limit exceeded for {resource_type}"
                ),
            )
        return current_user

    return limit_checker


# ==================== SYSTEM ADMINISTRATION ====================


@router.post("/system/sync-plans-to-stripe", tags=["ROOT_ADMIN"])
async def sync_plans_to_stripe(
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """
    Manually sync all existing subscription plans to Stripe Products/Prices.
    Useful if you added Stripe credentials after creating plans.
    """
    plans = await subscription_service.list_plans(include_inactive=True)
    synced_count = 0
    errors = []

    for plan in plans:
        try:
            await subscription_service.update_plan(plan["_id"], {})
            synced_count += 1
        except Exception as e:
            errors.append(f"Plan {plan.get('name', 'Unknown')}: {str(e)}")

    return {"message": f"Synced {synced_count} plans to Stripe", "errors": errors}


@router.post("/system/seed-default-plans", tags=["ROOT_ADMIN"])
async def seed_default_subscription_plans(
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Seed default subscription plans - ROOT_ADMIN only.

    Manual fallback for situations where the container boot seed didn't
    fire. Plans here MUST match ``scripts/seed_subscription_plans.py``;
    drift between the two is how the 2026-05-09 pricing refresh ended up
    half-applied. If the seed script changes, mirror it here in the same
    PR. Long-term fix: extract the plan dicts to a shared constants module.
    """
    default_plans = [
        # ============================================================
        # SOLO — free tier, 1 lifetime wedding, drives upgrade
        # ============================================================
        {
            "name": "Solo",
            "description": "Try us with your first client. One wedding, on us.",
            "price_monthly": 0,
            "price_yearly": 0,
            "trial_days": 0,
            "billing_model": CANONICAL_PUBLIC_PLAN_BILLING_MODEL,
            "is_metered": False,
            "max_weddings": 1,
            "max_weddings_lifetime": True,
            "max_guests_per_wedding": 50,
            "ai_credits_monthly": 0,
            "storage_gb": 1,
            "staff_seats": 1,
            "features": {
                "guest_management": True,
                "email_invitations": True,
                "rsvp_system": True,
                "wedding_website": True,
                "timeline_builder": True,
            },
            "features_list": [
                "1 wedding to try us out",
                "Up to 50 guests",
                "Guest list & RSVP system",
                "Branded wedding website",
                "Basic timeline builder",
                "1GB storage",
            ],
            "is_featured": False,
            "is_active": True,
            "display_order": 0,
            "sort_order": 0,
        },
        # ============================================================
        # BOUTIQUE — $49/mo, the solo planner running their business
        # ============================================================
        {
            "name": "Boutique",
            "description": "For independent planners running their solo practice.",
            "price_monthly": 49,
            "price_yearly": 490,
            "trial_days": 14,
            "billing_model": CANONICAL_PUBLIC_PLAN_BILLING_MODEL,
            "is_metered": False,
            "max_weddings": 10,
            "max_weddings_lifetime": False,
            "max_guests_per_wedding": 200,
            "ai_credits_monthly": 300,
            "storage_gb": 25,
            "staff_seats": 1,
            "features": {
                "guest_management": True,
                "email_invitations": True,
                "rsvp_system": True,
                "wedding_website": True,
                "timeline_builder": True,
                "basic_analytics": True,
                "vendor_management": True,
                "seating_orchestration": True,
                "ai_features": True,
                "qr_checkin": True,
                "automated_reminders": True,
                "calendar_sync": True,
                "payment_processing": True,
            },
            "features_list": [
                "Up to 10 weddings/month",
                "Up to 200 guests per wedding",
                "AI-powered timeline & vendor matching",
                "Vendor management",
                "Seating orchestration",
                "QR check-in & live counts",
                "Automated reminders",
                "Calendar sync (Google, Outlook)",
                "300 AI credits/month",
                "25GB storage",
                "Email support",
            ],
            "is_featured": False,
            "is_active": True,
            "display_order": 1,
            "sort_order": 1,
        },
        # ============================================================
        # SIGNATURE — $149/mo (featured), team-of-planners agency
        # ============================================================
        {
            "name": "Signature",
            "description": "For agencies running a team of planners.",
            "price_monthly": 149,
            "price_yearly": 1490,
            "trial_days": 14,
            "billing_model": CANONICAL_PUBLIC_PLAN_BILLING_MODEL,
            "is_metered": False,
            "max_weddings": 30,
            "max_weddings_lifetime": False,
            "max_guests_per_wedding": 500,
            "ai_credits_monthly": 1500,
            "storage_gb": 100,
            "staff_seats": 5,
            "features": {
                "guest_management": True,
                "email_invitations": True,
                "rsvp_system": True,
                "wedding_website": True,
                "timeline_builder": True,
                "basic_analytics": True,
                "vendor_management": True,
                "seating_orchestration": True,
                "ai_features": True,
                "qr_checkin": True,
                "automated_reminders": True,
                "calendar_sync": True,
                "payment_processing": True,
                "vendor_collaboration": True,
                "advanced_analytics": True,
                "custom_domain": True,
                "priority_support": True,
            },
            "features_list": [
                "Up to 30 weddings/month",
                "Up to 500 guests per wedding",
                "Everything in Boutique",
                "Team collaboration (5 staff seats)",
                "Vendor-collaboration workspaces",
                "Cross-wedding analytics & revenue tracking",
                "Custom domain (app.yourbrand.com)",
                "1,500 AI credits/month",
                "100GB storage",
                "Priority support (12h response)",
                "Group onboarding session",
            ],
            "is_featured": True,
            "is_active": True,
            "display_order": 2,
            "sort_order": 2,
        },
        # ============================================================
        # ENTERPRISE — $399/mo, white-label / franchise tier
        # ============================================================
        {
            "name": "Enterprise",
            "description": "For large agencies, franchises, and white-label partners.",
            "price_monthly": 399,
            "price_yearly": 3990,
            "trial_days": 30,
            "billing_model": CANONICAL_PUBLIC_PLAN_BILLING_MODEL,
            "is_metered": False,
            "max_weddings": -1,
            "max_weddings_lifetime": False,
            "max_guests_per_wedding": -1,
            "ai_credits_monthly": 5000,
            "storage_gb": 500,
            "staff_seats": 20,
            "features": {
                "guest_management": True,
                "email_invitations": True,
                "rsvp_system": True,
                "wedding_website": True,
                "timeline_builder": True,
                "basic_analytics": True,
                "advanced_analytics": True,
                "vendor_management": True,
                "seating_orchestration": True,
                "ai_features": True,
                "qr_checkin": True,
                "automated_reminders": True,
                "calendar_sync": True,
                "payment_processing": True,
                "vendor_collaboration": True,
                "custom_domain": True,
                "priority_support": True,
                "white_label": True,
                "api_access": True,
                "dedicated_support": True,
            },
            "features_list": [
                "Unlimited weddings",
                "Unlimited guests",
                "Everything in Signature",
                "White-label (your brand, no Special Wedding mentions)",
                "API access + webhooks",
                "20 staff seats",
                "5,000 AI credits/month",
                "500GB storage",
                "Dedicated success manager",
                "Custom integrations",
            ],
            "is_featured": False,
            "is_active": True,
            "display_order": 3,
            "sort_order": 3,
        },
    ]

    created_plans = []
    skipped_plans = []

    for plan_data in default_plans:
        # Check if plan already exists
        existing_plans = await subscription_service.list_plans(include_inactive=True)
        existing_plan = next(
            (p for p in existing_plans if p["name"] == plan_data["name"]), None
        )

        if existing_plan:
            skipped_plans.append(plan_data["name"])
            continue

        try:
            # Note: create_plan will internally call stripe_service.sync_plan_to_stripe
            await subscription_service.create_plan(plan_data, current_user.email)
            created_plans.append(
                plan_data["name"]
            )  # Store the plan name instead of the result
        except Exception as e:
            # If seeding fails (e.g. stripe config missing), we might want to log it but continue?
            # For now, let's return error so admin knows.
            return {"error": f"Failed to create plan '{plan_data['name']}': {str(e)}"}
    return {
        "message": "Default subscription plans seeding completed",
        "created_plans": len(created_plans),
        "skipped_plans": len(skipped_plans),
        "details": {"created": created_plans, "skipped": skipped_plans},
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
        public_plans.append(
            {
                "_id": plan["_id"],  # Plan ID needed for selection
                "name": plan.get("name"),
                "description": plan.get("description"),
                "price_monthly": plan.get("price_monthly", 0),
                "price_yearly": plan.get("price_yearly"),
                "billing_model": plan.get("billing_model") or plan_billing_model(plan),
                "is_metered": bool(plan.get("is_metered", False)),
                "max_weddings": plan.get("max_weddings", 1),
                "max_guests_per_wedding": plan.get("max_guests_per_wedding", 100),
                "ai_credits_monthly": plan.get("ai_credits_monthly", 10),
                "storage_gb": plan.get("storage_gb", 1),
                "staff_seats": plan.get("staff_seats", 0),
                "features": plan.get("features", {}),
                "features_list": plan.get("features_list", []),
                "is_featured": plan.get("is_featured", False),
                "is_active": plan.get("is_active", True),
                "trial_days": plan.get("trial_days", 0),
                "display_order": plan.get("display_order", plan.get("sort_order", 0)),
                # Explicitly EXCLUDE: stripe_product_id, stripe_price_id_*, created_by, etc.
            }
        )

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
        "billing_model": plan.get("billing_model") or plan_billing_model(plan),
        "is_metered": bool(plan.get("is_metered", False)),
        "max_weddings": plan["max_weddings"],
        "max_guests_per_wedding": plan["max_guests_per_wedding"],
        "ai_credits_monthly": plan["ai_credits_monthly"],
        "storage_gb": plan["storage_gb"],
        "staff_seats": plan["staff_seats"],
        "features": plan.get("features", {}),
        "features_list": plan.get("features_list", []),
        "is_featured": plan.get("is_featured", False),
        "trial_days": plan.get("trial_days", 0),
        "display_order": plan.get("display_order", plan.get("sort_order", 0)),
    }
    return public_plan
