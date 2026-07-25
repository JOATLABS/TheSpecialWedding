from fastapi import APIRouter, Depends, HTTPException, Query

from app.constants.billing import (
    CANONICAL_PUBLIC_PLAN_BILLING_MODEL,
    CANONICAL_PUBLIC_PLAN_IDS_BY_NAME,
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
from app.utils.subscription_plan_seed_policy import legacy_canonical_plan_aliases

router = APIRouter()
subscription_service = SubscriptionService()


def _can_read_subscription_for_user(
    current_user: ExtendedAuthUser, user_id: str
) -> bool:
    return (
        current_user.is_root_admin or str(current_user.user_data.get("_id")) == user_id
    )


def _sanitized_plan_payload(plan: dict, *, id_field: str) -> dict:
    """Return the shared public-safe plan shape with the requested ID key."""

    return {
        id_field: plan["_id"],
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
    }


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
    if not _can_read_subscription_for_user(current_user, user_id):
        raise HTTPException(
            status_code=403, detail="Can only view your own subscription"
        )

    subscription = await subscription_service.get_user_subscription(user_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="No active subscription found")

    return subscription


@router.get("/admin/users/{user_id}/subscription-plan", tags=["ROOT_ADMIN", "User"])
async def get_user_subscription_plan(
    user_id: str, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Return sanitized plan terms for the user's own billing relationship."""

    if not _can_read_subscription_for_user(current_user, user_id):
        raise HTTPException(
            status_code=403, detail="Can only view your own subscription plan"
        )

    plan = await subscription_service.get_user_billing_plan(user_id)
    if not plan:
        raise HTTPException(status_code=404, detail="No billing plan found")
    return _sanitized_plan_payload(plan, id_field="id")


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
            errors.append(f"Plan {plan.get('name', 'Unknown')}: {e!s}")

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
        # SOLO — free tier, 1 ACTIVE wedding at a time
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
            "max_weddings_lifetime": False,
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
                "basic_analytics": False,
                "vendor_management": False,
                "seating_orchestration": False,
                "ai_features": False,
                "qr_checkin": False,
                "automated_reminders": False,
                "calendar_sync": False,
                "payment_processing": False,
                "vendor_collaboration": False,
                "advanced_analytics": False,
                "planner_storefront": False,
                "custom_domain": False,
                "priority_support": False,
                "white_label": False,
                "api_access": False,
                "dedicated_support": False,
            },
            "features_list": [
                "1 wedding to try us out",
                "Guest list & RSVP system",
                "Branded wedding website",
                "Basic timeline builder",
                "1GB guest memories storage",
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
            "description": "For independent planners running their solo practice with paid planning tools and higher limits.",
            "price_monthly": 49,
            "price_yearly": 490,
            "trial_days": 30,
            "billing_model": CANONICAL_PUBLIC_PLAN_BILLING_MODEL,
            "is_metered": False,
            "max_weddings": -1,
            "max_weddings_lifetime": False,
            "max_guests_per_wedding": -1,
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
                "vendor_collaboration": False,
                "advanced_analytics": False,
                "planner_storefront": False,
                "custom_domain": False,
                "priority_support": False,
                "white_label": False,
                "api_access": False,
                "dedicated_support": False,
            },
            "features_list": [
                "Unlimited weddings",
                "Unlimited guests",
                "Vendor management",
                "Seating orchestration",
                "Automated reminders",
                "Calendar sync (Google, Outlook)",
                "300 AI credits/month",
                "25GB guest memories storage",
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
            "description": "For agencies running a team of planners. Everything in Boutique, plus five staff seats, higher AI and storage limits, a planner storefront, and custom-domain options.",
            "price_monthly": 149,
            "price_yearly": 1490,
            "trial_days": 30,
            "billing_model": CANONICAL_PUBLIC_PLAN_BILLING_MODEL,
            "is_metered": False,
            "max_weddings": -1,
            "max_weddings_lifetime": False,
            "max_guests_per_wedding": -1,
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
                "vendor_collaboration": False,
                "advanced_analytics": True,
                "planner_storefront": True,
                "custom_domain": True,
                "priority_support": True,
                "white_label": False,
                "api_access": False,
                "dedicated_support": False,
            },
            "features_list": [
                "Unlimited weddings",
                "Unlimited guests",
                "Everything in Boutique",
                "Team collaboration (5 staff seats)",
                "Planner storefront on a shareable platform URL",
                "Optional custom domain (app.yourbrand.com)",
                "1,500 AI credits/month",
                "100GB guest memories storage",
                "Priority support (12h response)",
                "Support-assisted onboarding by request",
            ],
            "is_featured": True,
            "is_active": True,
            "display_order": 2,
            "sort_order": 2,
        },
        # ============================================================
        # ENTERPRISE — $399/mo, larger-team support tier
        # ============================================================
        {
            "name": "Enterprise",
            "description": "For larger planning teams that need more seats, higher AI usage, expanded guest memories storage, and launch support.",
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
                "vendor_collaboration": False,
                "planner_storefront": True,
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
                "Planner storefront on a shareable platform URL",
                "Optional custom domain",
                "20 staff seats",
                "5,000 AI credits/month",
                "500GB guest memories storage",
                "Support-assisted launch planning",
            ],
            "is_featured": False,
            "is_active": True,
            "display_order": 3,
            "sort_order": 3,
        },
    ]

    created_plans = []
    updated_plans = []
    skipped_plans = []
    archived_aliases = []
    existing_plans = await subscription_service.list_plans(include_inactive=True)
    existing_by_id = {str(plan.get("_id")): plan for plan in existing_plans}
    legacy_aliases_by_canonical_id: dict[str, list[object]] = {}
    for legacy_plan_id, canonical_plan_id in legacy_canonical_plan_aliases(
        existing_plans,
        require_canonical_present=False,
    ):
        legacy_aliases_by_canonical_id.setdefault(canonical_plan_id, []).append(
            legacy_plan_id
        )

    for plan_data in default_plans:
        plan_name = plan_data["name"]
        canonical_plan_id = CANONICAL_PUBLIC_PLAN_IDS_BY_NAME[plan_name]
        existing_plan = existing_by_id.get(canonical_plan_id)

        if existing_plan:
            refreshed = await subscription_service.refresh_seeded_plan_fields(
                existing_plan["_id"],
                {
                    "description": plan_data["description"],
                    "features": plan_data["features"],
                    "features_list": plan_data["features_list"],
                },
            )
            if refreshed:
                updated_plans.append(plan_data["name"])
            else:
                skipped_plans.append(plan_data["name"])
        else:
            try:
                # create_plan derives the same canonical ID from these names.
                await subscription_service.create_plan(plan_data, current_user.email)
                created_plans.append(plan_name)
            except Exception as e:
                return {"error": f"Failed to create plan '{plan_name}': {e!s}"}

        for legacy_plan_id in legacy_aliases_by_canonical_id.get(canonical_plan_id, []):
            archived = await subscription_service.archive_legacy_plan_alias(
                legacy_plan_id,
                canonical_plan_id,
            )
            if archived:
                archived_aliases.append(str(legacy_plan_id))
    return {
        "message": "Default subscription plans seeding completed",
        "created_plans": len(created_plans),
        "updated_plans": len(updated_plans),
        "skipped_plans": len(skipped_plans),
        "archived_aliases": len(archived_aliases),
        "details": {
            "created": created_plans,
            "updated": updated_plans,
            "skipped": skipped_plans,
            "archived_aliases": archived_aliases,
        },
    }


# ==================== PUBLIC SUBSCRIPTION PLANS (FOR PRICING PAGE) ====================


@router.get("/public/subscription-plans", tags=["Public"])
async def get_public_subscription_plans():
    """Get active subscription plans for public pricing page.

    Returns sanitized plan data - excludes internal IDs (Stripe, MongoDB metadata)
    to prevent data leakage to competitors or malicious actors.
    """
    plans = await subscription_service.list_plans(include_inactive=False)

    return [_sanitized_plan_payload(plan, id_field="_id") for plan in plans]


@router.get("/public/subscription-plans/{plan_id}", tags=["Public"])
async def get_public_subscription_plan(plan_id: str):
    """Get subscription plan details for public view"""
    plan = await subscription_service.get_plan(plan_id)
    if plan.get("is_active") is not True:
        raise HTTPException(status_code=404, detail="Subscription plan not found")
    return _sanitized_plan_payload(plan, id_field="id")
