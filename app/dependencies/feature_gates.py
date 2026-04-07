"""
Feature Gate Dependencies

This module provides FastAPI dependencies for checking if users have access
to specific features based on their subscription plan.
"""

from fastapi import Depends, HTTPException, status
from app.dependencies.auth_extended import require_admin_or_planner, ExtendedAuthUser
from app.core.database import mongo
from app.models.subscription import ACTIVE_SUBSCRIPTION_STATUSES
import logging

logger = logging.getLogger(__name__)


async def get_user_plan_features(user_email: str) -> dict:
    """
    Get the feature flags for a user's current subscription plan.

    Returns:
        dict: Feature flags from the user's plan, or empty dict if no plan
    """
    try:
        # Get user's subscription — check both user_email and user_id fields
        # since subscriptions may be stored with either identifier
        subscription = await mongo.db["user_subscriptions"].find_one(
            {
                "user_email": user_email,
                "status": {"$in": list(ACTIVE_SUBSCRIPTION_STATUSES)},
            }
        )

        if not subscription:
            # Fallback: look up by user_id from users collection
            user = await mongo.get_users_collection().find_one({"email": user_email})
            if user:
                user_id_str = str(user["_id"])
                subscription = await mongo.db["user_subscriptions"].find_one(
                    {
                        "user_id": user_id_str,
                        "status": {"$in": list(ACTIVE_SUBSCRIPTION_STATUSES)},
                    }
                )

        if not subscription:
            # Check if user is ROOT_ADMIN (they get all features)
            user = await mongo.get_users_collection().find_one({"email": user_email})
            if user and user.get("role") == "ROOT_ADMIN":
                return {"vendor_management": True}  # ROOT_ADMIN gets everything
            return {}

        # Get the plan details
        plan = await mongo.db["subscription_plans"].find_one(
            {"_id": subscription.get("plan_id")}
        )

        if not plan:
            return {}

        return plan.get("features", {})

    except Exception as e:
        logger.error(f"Error getting user plan features: {str(e)}")
        return {}


async def require_vendor_feature(
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
) -> ExtendedAuthUser:
    """
    Dependency that checks if the user's plan includes vendor management.

    Raises:
        HTTPException 403 if vendor feature is not enabled

    Returns:
        ExtendedAuthUser: The authenticated user
    """
    # ROOT_ADMIN always has access
    if current_user.is_root_admin:
        return current_user

    features = await get_user_plan_features(current_user.email)

    if not features.get("vendor_management", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "feature_not_available",
                "message": "Vendor management is not included in your current plan",
                "feature": "vendor_management",
                "upgrade_required": True,
            },
        )

    return current_user


async def check_feature_enabled(feature_name: str, user_email: str) -> bool:
    """
    Check if a specific feature is enabled for a user.

    Args:
        feature_name: Name of the feature to check
        user_email: User's email address

    Returns:
        bool: True if feature is enabled
    """
    features = await get_user_plan_features(user_email)
    return features.get(feature_name, False)


def require_feature(feature_name: str):
    """
    Factory function to create a dependency for any feature.

    Usage:
        @router.get("/some-endpoint")
        async def endpoint(user = Depends(require_feature("ai_tools"))):
            ...
    """

    async def _check_feature(
        current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
    ) -> ExtendedAuthUser:
        if current_user.is_root_admin:
            return current_user

        features = await get_user_plan_features(current_user.email)

        if not features.get(feature_name, False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "feature_not_available",
                    "message": f"{feature_name.replace('_', ' ').title()} is not included in your current plan",
                    "feature": feature_name,
                    "upgrade_required": True,
                },
            )

        return current_user

    return _check_feature


async def require_team_management(
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
) -> ExtendedAuthUser:
    """
    Feature gate: ensure the planner's plan includes team management (staff_seats > 0).

    Raises:
        HTTPException 403 with upgrade_required if team management is not available
    """
    if current_user.is_root_admin:
        return current_user

    # Check the planner's plan for staff_seats
    email = current_user.email
    try:
        subscription = await mongo.db["user_subscriptions"].find_one(
            {"user_email": email, "status": {"$in": list(ACTIVE_SUBSCRIPTION_STATUSES)}}
        )
        if not subscription:
            user = await mongo.get_users_collection().find_one({"email": email})
            if user:
                subscription = await mongo.db["user_subscriptions"].find_one(
                    {
                        "user_id": str(user["_id"]),
                        "status": {"$in": list(ACTIVE_SUBSCRIPTION_STATUSES)},
                    }
                )

        staff_seats = 0
        if subscription:
            # Prefer plan snapshot (grandfathered limits)
            snapshot = subscription.get("plan_snapshot")
            if snapshot and "staff_seats" in snapshot:
                staff_seats = snapshot["staff_seats"]
            else:
                plan = await mongo.db["subscription_plans"].find_one(
                    {"_id": subscription.get("plan_id")}
                )
                if plan:
                    staff_seats = plan.get("staff_seats", 0)

        if staff_seats <= 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "feature_not_available",
                    "message": "Team management is not included in your current plan. Upgrade to add team members.",
                    "feature": "team_management",
                    "upgrade_required": True,
                },
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking team management feature: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to verify team management access",
        )

    return current_user
