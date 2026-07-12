"""Planner-owned storefront administration and allowlisted public reads."""

from fastapi import APIRouter, Depends

from app.constants.storefront import STOREFRONT_FEATURE
from app.dependencies.auth_extended import ExtendedAuthUser
from app.dependencies.storefront_access import (
    require_storefront_feature,
    require_storefront_owner,
)
from app.models.storefront import (
    PublicStorefrontResponse,
    StorefrontAccessResponse,
    StorefrontSettingsEnvelope,
    StorefrontSettingsUpdate,
    StorefrontSettingsUpdateEnvelope,
)
from app.services.storefront_entitlement_service import StorefrontEntitlements
from app.services.storefront_service import storefront_service

router = APIRouter()
public_router = APIRouter()

require_planner_storefront = require_storefront_feature(STOREFRONT_FEATURE)


@router.get("/storefront/access", response_model=StorefrontAccessResponse)
async def get_storefront_access(
    current_user: ExtendedAuthUser = Depends(require_storefront_owner),
):
    """Return independent current-plan capabilities for the planner owner."""

    return await storefront_service.get_access(current_user)


@router.get("/storefront/settings", response_model=StorefrontSettingsEnvelope)
async def get_storefront_settings(
    current_user: ExtendedAuthUser = Depends(require_storefront_owner),
    _entitlements: StorefrontEntitlements = Depends(require_planner_storefront),
):
    """Read the entitled planner owner's authored storefront settings."""

    return {"settings": await storefront_service.get_settings(current_user)}


@router.post(
    "/storefront/settings",
    response_model=StorefrontSettingsUpdateEnvelope,
)
async def update_storefront_settings(
    settings: StorefrontSettingsUpdate,
    current_user: ExtendedAuthUser = Depends(require_storefront_owner),
    _entitlements: StorefrontEntitlements = Depends(require_planner_storefront),
):
    """Create or edit allowlisted settings without touching provider state."""

    saved = await storefront_service.update_settings(current_user, settings)
    return {"status": "success", "settings": saved}


@router.get(
    "/storefront/preview/{slug}",
    response_model=PublicStorefrontResponse,
)
async def preview_storefront(
    slug: str,
    current_user: ExtendedAuthUser = Depends(require_storefront_owner),
    _entitlements: StorefrontEntitlements = Depends(require_planner_storefront),
):
    """Render the owner's saved draft through the public DTO without publishing."""

    return await storefront_service.get_owner_preview(current_user, slug)


@public_router.get(
    "/storefront/{identifier}",
    response_model=PublicStorefrontResponse,
)
async def get_public_storefront(identifier: str):
    """Resolve only a stored, published, currently entitled storefront slug."""

    return await storefront_service.get_public_storefront(identifier)
