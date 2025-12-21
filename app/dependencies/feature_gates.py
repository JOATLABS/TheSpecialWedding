"""
Feature Gate Dependencies

This module provides FastAPI dependencies for checking if users have access
to specific features based on their subscription plan.
"""

from fastapi import Depends, HTTPException, status
from typing import Optional
from app.dependencies.auth_extended import require_admin_or_planner, ExtendedAuthUser
from app.core.database import mongo
import logging

logger = logging.getLogger(__name__)


async def get_user_plan_features(user_email: str) -> dict:
    """
    Get the feature flags for a user's current subscription plan.

    Returns:
        dict: Feature flags from the user's plan, or empty dict if no plan
    """
    try:
        # Get user's subscription
        subscription = await mongo.db["user_subscriptions"].find_one(
            {"user_email": user_email, "status": {"$in": ["active", "trial"]}}
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
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
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
                "upgrade_required": True
            }
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
        current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
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
                    "upgrade_required": True
                }
            )

        return current_user

    return _check_feature
