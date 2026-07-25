from functools import wraps

from fastapi import HTTPException

from app.dependencies.auth_extended import ExtendedAuthUser
from app.services.subscription_service import SubscriptionService

subscription_service = SubscriptionService()


def enforce_subscription_limit(resource_type: str, amount: int = 1):
    """
    Decorator to enforce subscription limits on endpoints
    Args:
        resource_type: Type of resource (weddings, ai_credits, staff_seats)
        amount: Amount of resource being used (default: 1)
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Find the current_user in kwargs
            current_user = kwargs.get("current_user")

            if not current_user or not isinstance(current_user, ExtendedAuthUser):
                raise HTTPException(status_code=401, detail="Authentication required")

            # ROOT_ADMIN bypasses all limits
            if current_user.is_root_admin:
                return await func(*args, **kwargs)

            # Check user's subscription limits
            user_id = current_user.user_data.get("_id")
            if not user_id:
                raise HTTPException(status_code=403, detail="User ID not found")

            try:
                limits_check = await subscription_service.check_usage_limits(
                    user_id, resource_type, amount
                )

                if not limits_check.get("allowed", False):
                    raise HTTPException(
                        status_code=402,  # Payment Required
                        detail=limits_check.get(
                            "message",
                            f"Subscription limit exceeded for {resource_type}",
                        ),
                    )

                # Execute the original function
                result = await func(*args, **kwargs)

                # If successful, increment usage (for create operations)
                if hasattr(func, "__name__") and "create" in func.__name__.lower():
                    await subscription_service.increment_usage(
                        user_id, resource_type, amount
                    )

                return result

            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Error checking subscription limits: {e!s}",
                )

        return wrapper

    return decorator


def check_feature_access(feature_name: str):
    """
    Decorator to check if user's subscription plan includes a specific feature
    Args:
        feature_name: Name of the feature to check
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Find the current_user in kwargs
            current_user = kwargs.get("current_user")

            if not current_user or not isinstance(current_user, ExtendedAuthUser):
                raise HTTPException(status_code=401, detail="Authentication required")

            # ROOT_ADMIN has access to all features
            if current_user.is_root_admin:
                return await func(*args, **kwargs)

            # Check user's subscription plan features
            user_id = current_user.user_data.get("_id")
            if not user_id:
                raise HTTPException(status_code=403, detail="User ID not found")
            try:
                subscription = await subscription_service.get_user_subscription(user_id)
                if not subscription:
                    raise HTTPException(
                        status_code=403, detail="No active subscription found"
                    )

                plan = await subscription_service.get_plan(subscription["plan_id"])
                features = plan.get("features", {})

                if not features.get(feature_name, False):
                    raise HTTPException(
                        status_code=402,  # Payment Required
                        detail=f"Feature '{feature_name}' not available in your current plan",
                    )

                return await func(*args, **kwargs)

            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(
                    status_code=500, detail=f"Error checking feature access: {e!s}"
                )

        return wrapper

    return decorator


# Convenience decorators for common resources
def limit_weddings(amount: int = 1):
    """Enforce wedding creation limits"""
    return enforce_subscription_limit("weddings", amount)


def limit_ai_credits(amount: int = 1):
    """Enforce AI credits usage limits"""
    return enforce_subscription_limit("ai_credits", amount)


def limit_staff_seats(amount: int = 1):
    """Enforce staff seats limits"""
    return enforce_subscription_limit("staff_seats", amount)


# Convenience decorators for common features
def require_ai_tools():
    """Require AI tools feature"""
    return check_feature_access("ai_tools")


def require_advanced_reporting():
    """Require advanced reporting feature"""
    return check_feature_access("advanced_reporting")


def require_white_label():
    """Require white label feature"""
    return check_feature_access("white_label")


def require_custom_integrations():
    """Require custom integrations feature"""
    return check_feature_access("custom_integrations")


def require_multi_user_collaboration():
    """Require multi-user collaboration feature"""
    return check_feature_access("multi_user_collaboration")
