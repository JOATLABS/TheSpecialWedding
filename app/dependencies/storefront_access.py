"""Owner and capability dependencies for storefront administration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Depends, HTTPException, status

from app.constants.roles import is_wedding_planner_role
from app.constants.storefront import (
    CUSTOM_DOMAIN_FEATURE,
    STOREFRONT_FEATURE,
    SUPPORTED_STOREFRONT_FEATURES,
)
from app.dependencies.auth_extended import ExtendedAuthUser, get_current_user_extended
from app.services.storefront_entitlement_service import (
    StorefrontEntitlements,
    StorefrontEntitlementResolutionError,
    storefront_entitlement_service,
)
from app.utils.planner_ownership import normalize_planner_id


async def require_storefront_owner(
    current_user: ExtendedAuthUser = Depends(get_current_user_extended),
) -> ExtendedAuthUser:
    """Allow only a planner acting as their own storefront owner."""

    owner_id = normalize_planner_id(current_user.user_data.get("_id"))
    if not is_wedding_planner_role(current_user.role) or not owner_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Planner-owner access required",
        )
    return current_user


def require_storefront_feature(
    feature_name: str,
) -> Callable[[ExtendedAuthUser], Awaitable[StorefrontEntitlements]]:
    """Build a planner-owner dependency for one independent capability."""

    if feature_name not in SUPPORTED_STOREFRONT_FEATURES:
        raise ValueError(f"Unsupported storefront feature: {feature_name}")

    async def _require_feature(
        current_user: ExtendedAuthUser = Depends(require_storefront_owner),
    ) -> StorefrontEntitlements:
        user_data = {**current_user.user_data, "role": current_user.role}
        try:
            entitlements = await storefront_entitlement_service.resolve_for_owner(
                user_data
            )
        except StorefrontEntitlementResolutionError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storefront eligibility is temporarily unavailable",
            ) from exc

        enabled = {
            STOREFRONT_FEATURE: entitlements.storefront_enabled,
            CUSTOM_DOMAIN_FEATURE: entitlements.custom_domain_enabled,
        }[feature_name]
        if not enabled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "feature_not_available",
                    "message": (
                        f"{feature_name.replace('_', ' ').title()} is not "
                        "included in the current plan"
                    ),
                    "feature": feature_name,
                    "upgrade_required": True,
                },
            )
        return entitlements

    return _require_feature
