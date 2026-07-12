"""Planner-owned storefront administration and allowlisted public reads."""

from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.constants.storefront import CUSTOM_DOMAIN_FEATURE, STOREFRONT_FEATURE
from app.dependencies.auth_extended import ExtendedAuthUser
from app.dependencies.storefront_access import (
    require_storefront_feature,
    require_storefront_owner,
)
from app.models.storefront import (
    PublicStorefrontResponse,
    StorefrontAccessResponse,
    StorefrontAssetDeleteResponse,
    StorefrontAssetResponse,
    StorefrontDomainConnectRequest,
    StorefrontDomainResponse,
    StorefrontInquiryRequest,
    StorefrontInquiryResponse,
    StorefrontSettingsEnvelope,
    StorefrontSettingsUpdate,
    StorefrontSettingsUpdateEnvelope,
    StorefrontUploadCompleteRequest,
    StorefrontUploadReservationResponse,
)
from app.services.storefront_domain_service import storefront_domain_service
from app.services.storefront_entitlement_service import StorefrontEntitlements
from app.services.storefront_inquiry_service import storefront_inquiry_service
from app.services.storefront_media_service import (
    MAX_STOREFRONT_ASSET_SIZE_BYTES,
    storefront_media_service,
)
from app.services.storefront_service import storefront_service
from app.utils.rate_limiter import get_client_ip

router = APIRouter()
public_router = APIRouter()

require_planner_storefront = require_storefront_feature(STOREFRONT_FEATURE)
require_custom_domain = require_storefront_feature(CUSTOM_DOMAIN_FEATURE)


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
    "/storefront/preview-data",
    response_model=PublicStorefrontResponse,
)
async def get_storefront_preview_data(
    current_user: ExtendedAuthUser = Depends(require_storefront_owner),
    _entitlements: StorefrontEntitlements = Depends(require_planner_storefront),
):
    """Return canonical owner content even before first settings persistence."""

    return await storefront_service.get_owner_preview_seed(current_user)


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


@router.post(
    "/storefront/custom-domain",
    response_model=StorefrontDomainResponse,
    status_code=status.HTTP_201_CREATED,
)
async def connect_storefront_custom_domain(
    payload: StorefrontDomainConnectRequest,
    current_user: ExtendedAuthUser = Depends(require_storefront_owner),
    _entitlements: StorefrontEntitlements = Depends(require_custom_domain),
):
    return await storefront_domain_service.connect(current_user, payload.domain)


@router.get(
    "/storefront/custom-domain/status",
    response_model=StorefrontDomainResponse | None,
)
async def refresh_storefront_custom_domain(
    current_user: ExtendedAuthUser = Depends(require_storefront_owner),
    _entitlements: StorefrontEntitlements = Depends(require_custom_domain),
):
    return await storefront_domain_service.refresh(current_user)


@router.delete(
    "/storefront/custom-domain",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def disconnect_storefront_custom_domain(
    current_user: ExtendedAuthUser = Depends(require_storefront_owner),
    _entitlements: StorefrontEntitlements = Depends(require_custom_domain),
):
    await storefront_domain_service.disconnect(current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/storefront/upload-url",
    response_model=StorefrontUploadReservationResponse,
)
async def reserve_storefront_upload(
    filename: str = Query(min_length=1, max_length=255),
    slot: Literal["hero", "about"] = Query(),
    content_type: Literal["image/jpeg", "image/png", "image/webp"] = Query(),
    size_bytes: int = Query(gt=0, le=MAX_STOREFRONT_ASSET_SIZE_BYTES),
    current_user: ExtendedAuthUser = Depends(require_storefront_owner),
    _entitlements: StorefrontEntitlements = Depends(require_planner_storefront),
):
    # The original filename is validated for request bounds but intentionally
    # never participates in the storage key.
    _ = filename
    return await storefront_media_service.reserve(
        current_user,
        slot=slot,
        content_type=content_type,
        size_bytes=size_bytes,
    )


@router.post(
    "/storefront/upload-complete",
    response_model=StorefrontAssetResponse,
)
async def finalize_storefront_upload(
    payload: StorefrontUploadCompleteRequest,
    current_user: ExtendedAuthUser = Depends(require_storefront_owner),
    _entitlements: StorefrontEntitlements = Depends(require_planner_storefront),
):
    return await storefront_media_service.finalize(current_user, payload.asset_id)


@router.delete(
    "/storefront/upload",
    response_model=StorefrontAssetDeleteResponse,
)
async def delete_storefront_upload(
    asset_id: str = Query(min_length=1, max_length=120),
    current_user: ExtendedAuthUser = Depends(require_storefront_owner),
    _entitlements: StorefrontEntitlements = Depends(require_planner_storefront),
):
    return await storefront_media_service.cleanup(current_user, asset_id)


@public_router.get(
    "/storefront/{identifier}",
    response_model=PublicStorefrontResponse,
)
async def get_public_storefront(identifier: str):
    """Resolve only a stored, published, currently entitled storefront slug."""

    return await storefront_service.get_public_storefront(identifier)


@public_router.post(
    "/storefront/{identifier}/inquiries",
    response_model=StorefrontInquiryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_storefront_inquiry(
    identifier: str,
    payload: StorefrontInquiryRequest,
    request: Request,
):
    """Persist a lead for the exact same public storefront that can render."""

    return await storefront_inquiry_service.capture(
        identifier,
        payload,
        client_ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
