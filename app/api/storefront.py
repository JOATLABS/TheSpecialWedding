"""Planner-owned storefront administration and allowlisted public reads."""

from typing import Literal
from urllib.parse import urlencode, urlparse

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import RedirectResponse

from app.constants.storefront import CUSTOM_DOMAIN_FEATURE, STOREFRONT_FEATURE
from app.core.settings import settings
from app.dependencies.auth_extended import ExtendedAuthUser
from app.dependencies.storefront_access import (
    require_bearer_storefront_owner,
    require_storefront_feature,
    require_storefront_owner,
)
from app.models.storefront import (
    PublicStorefrontResponse,
    StorefrontAccessResponse,
    StorefrontAssetDeleteResponse,
    StorefrontAssetResponse,
    StorefrontDomainAttemptRequest,
    StorefrontDomainClaimRequest,
    StorefrontDomainConnectAuthorizationResponse,
    StorefrontDomainConnectRequest,
    StorefrontDomainDisconnectResponse,
    StorefrontDomainHttpsProbeResponse,
    StorefrontDomainInstructionLinksResponse,
    StorefrontDomainInstructionPublicResponse,
    StorefrontDomainInstructionRequest,
    StorefrontDomainInstructionResponse,
    StorefrontDomainInstructionRevokeResponse,
    StorefrontDomainPreflightRequest,
    StorefrontDomainPreflightResponse,
    StorefrontDomainResponse,
    StorefrontDomainVerifyRequest,
    StorefrontInquiryRequest,
    StorefrontInquiryResponse,
    StorefrontProviderReadinessResponse,
    StorefrontSettingsEnvelope,
    StorefrontSettingsUpdate,
    StorefrontSettingsUpdateEnvelope,
    StorefrontUploadCompleteRequest,
    StorefrontUploadReservationResponse,
)
from app.services.storefront_domain_connect_service import (
    storefront_domain_connect_service,
)
from app.services.storefront_domain_https_probe import (
    PROBE_HEADER,
    PROBE_HOST_HEADER,
    PROBE_INGRESS_HEADER,
    storefront_domain_https_probe_service,
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


def _storefront_frontend_resume_url(attempt_id: str) -> str:
    """Build a server-controlled absolute browser return URL.

    Domain Connect callbacks may be hosted on a dedicated API hostname, so a
    relative redirect would strand the customer on the wrong origin.
    """

    configured = str(settings.frontend_url or "").strip()
    parsed = urlparse(configured)
    try:
        port = parsed.port
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storefront browser return URL is not configured safely",
        ) from exc
    hostname = (parsed.hostname or "").lower().rstrip(".")
    is_loopback = hostname in {"localhost", "127.0.0.1", "::1"}
    if (
        not hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or parsed.scheme not in {"http", "https"}
        or (parsed.scheme == "http" and not is_loopback)
        or (settings.is_production() and parsed.scheme != "https")
        or (settings.is_production() and port not in {None, 443})
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storefront browser return URL is not configured safely",
        )
    origin = f"{parsed.scheme}://{parsed.netloc}"
    query = urlencode({"storefront": "domain", "attempt": attempt_id})
    return f"{origin}/admin/packages?{query}"


@router.get("/storefront/access", response_model=StorefrontAccessResponse)
async def get_storefront_access(
    current_user: ExtendedAuthUser = Depends(require_storefront_owner),
):
    """Return independent current-plan capabilities for the planner owner."""

    return await storefront_service.get_access(current_user)


@router.get(
    "/storefront/provider-readiness",
    response_model=StorefrontProviderReadinessResponse,
)
async def get_storefront_provider_readiness(
    _current_user: ExtendedAuthUser = Depends(require_storefront_owner),
    entitlements: StorefrontEntitlements = Depends(require_planner_storefront),
):
    """Return non-secret readiness; media uses bounded read-only provider checks."""

    return {
        "image_uploads_configured": (
            await storefront_media_service.provider_operational_readiness()
        ),
        "custom_domains_configured": (
            entitlements.custom_domain_enabled
            and storefront_domain_service.provider_configuration_present
        ),
        "runtime_revision": (
            settings.storefront_runtime_revision.strip()
            if settings.storefront_runtime_revision
            and settings.storefront_runtime_revision.strip()
            else None
        ),
    }


@router.get("/storefront/settings", response_model=StorefrontSettingsEnvelope)
async def get_storefront_settings(
    current_user: ExtendedAuthUser = Depends(require_storefront_owner),
):
    """Read owner-authored settings, including for existing-domain management."""

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


@router.post(
    "/storefront/custom-domain/preflight",
    response_model=StorefrontDomainPreflightResponse,
)
async def preflight_storefront_custom_domain(
    payload: StorefrontDomainPreflightRequest,
    current_user: ExtendedAuthUser = Depends(require_storefront_owner),
    _entitlements: StorefrontEntitlements = Depends(require_custom_domain),
):
    return await storefront_domain_service.preflight(
        current_user, payload.domain, intent=payload.intent
    )


@router.post(
    "/storefront/custom-domain/claim",
    response_model=StorefrontDomainResponse,
    status_code=status.HTTP_201_CREATED,
)
async def claim_storefront_custom_domain(
    payload: StorefrontDomainClaimRequest,
    current_user: ExtendedAuthUser = Depends(require_storefront_owner),
    _entitlements: StorefrontEntitlements = Depends(require_custom_domain),
):
    return await storefront_domain_service.claim(
        current_user,
        payload.domain,
        intent=payload.intent,
        setup_method=payload.setup_method,
    )


@router.post(
    "/storefront/custom-domain/verify",
    response_model=StorefrontDomainResponse,
)
async def verify_storefront_custom_domain(
    _payload: StorefrontDomainVerifyRequest | None = None,
    current_user: ExtendedAuthUser = Depends(require_storefront_owner),
    _entitlements: StorefrontEntitlements = Depends(require_custom_domain),
):
    if _payload and _payload.attempt_id:
        return await storefront_domain_service.verify(
            current_user, attempt_id=_payload.attempt_id
        )
    return await storefront_domain_service.verify(current_user)


@router.post(
    "/storefront/custom-domain/domain-connect/authorize",
    response_model=StorefrontDomainConnectAuthorizationResponse,
)
async def authorize_storefront_domain_connect(
    payload: StorefrontDomainAttemptRequest,
    current_user: ExtendedAuthUser = Depends(require_storefront_owner),
):
    return await storefront_domain_connect_service.start(
        current_user, payload.attempt_id
    )


@router.post(
    "/storefront/custom-domain/domain-connect/start",
    response_model=StorefrontDomainConnectAuthorizationResponse,
)
async def start_storefront_domain_connect_compatibility(
    payload: StorefrontDomainAttemptRequest,
    current_user: ExtendedAuthUser = Depends(require_storefront_owner),
):
    """Compatibility alias for the shipped frontend route."""

    return await storefront_domain_connect_service.start(
        current_user, payload.attempt_id
    )


@router.get("/storefront/custom-domain/domain-connect/callback")
async def callback_storefront_domain_connect(
    flow: str | None = Query(default=None, max_length=256),
    error: str | None = Query(default=None, max_length=80),
    error_description: str | None = Query(default=None, max_length=500),
):
    callback = await storefront_domain_connect_service.record_callback(
        flow or "", error=error, error_description=error_description
    )
    return RedirectResponse(
        url=_storefront_frontend_resume_url(callback["attempt_id"]),
        status_code=303,
    )


@router.post(
    "/storefront/custom-domain/domain-connect/complete",
    response_model=StorefrontDomainResponse,
)
async def complete_storefront_domain_connect(
    payload: StorefrontDomainAttemptRequest,
    current_user: ExtendedAuthUser = Depends(require_bearer_storefront_owner),
):
    return await storefront_domain_connect_service.complete(
        current_user, payload.attempt_id
    )


@router.post(
    "/storefront/custom-domain/retry",
    response_model=StorefrontDomainResponse,
)
async def retry_storefront_custom_domain(
    payload: StorefrontDomainAttemptRequest,
    current_user: ExtendedAuthUser = Depends(require_storefront_owner),
):
    return await storefront_domain_service.retry_provider(
        current_user, payload.attempt_id
    )


@router.post(
    "/storefront/custom-domain/observe",
    response_model=StorefrontDomainResponse | None,
)
async def observe_storefront_custom_domain(
    payload: StorefrontDomainAttemptRequest,
    current_user: ExtendedAuthUser = Depends(require_storefront_owner),
):
    """Enqueue read-only DNS/provider observation without a provider retry."""

    return await storefront_domain_service.observe(current_user, payload.attempt_id)


@router.post(
    "/storefront/custom-domain/instructions",
    response_model=StorefrontDomainInstructionResponse,
)
async def send_storefront_custom_domain_instructions(
    payload: StorefrontDomainInstructionRequest,
    current_user: ExtendedAuthUser = Depends(require_storefront_owner),
):
    return await storefront_domain_service.send_instructions(
        current_user,
        payload.attempt_id,
        email=str(payload.email),
        note=payload.note,
    )


@router.get(
    "/storefront/custom-domain/instructions",
    response_model=StorefrontDomainInstructionLinksResponse,
)
async def list_storefront_custom_domain_instructions(
    attempt_id: str = Query(
        min_length=1,
        max_length=120,
        pattern=r"^[A-Za-z0-9_-]+$",
    ),
    current_user: ExtendedAuthUser = Depends(require_storefront_owner),
):
    return await storefront_domain_service.list_instruction_links(
        current_user, attempt_id
    )


@router.delete(
    "/storefront/custom-domain/instructions/{link_id}",
    response_model=StorefrontDomainInstructionRevokeResponse,
)
async def revoke_storefront_custom_domain_instructions(
    link_id: str = Path(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_-]+$"),
    current_user: ExtendedAuthUser = Depends(require_storefront_owner),
):
    return await storefront_domain_service.revoke_instruction_link(
        current_user, link_id
    )


@router.get(
    "/storefront/custom-domain/status",
    response_model=StorefrontDomainResponse | None,
)
async def refresh_storefront_custom_domain(
    attempt_id: str | None = Query(
        default=None,
        min_length=1,
        max_length=120,
        pattern=r"^[A-Za-z0-9_-]+$",
    ),
    current_user: ExtendedAuthUser = Depends(require_storefront_owner),
):
    if attempt_id:
        return await storefront_domain_service.get_status(
            current_user, attempt_id=attempt_id
        )
    return await storefront_domain_service.get_status(current_user)


@router.delete(
    "/storefront/custom-domain",
    response_model=StorefrontDomainDisconnectResponse,
)
async def disconnect_storefront_custom_domain(
    attempt_id: str | None = Query(
        default=None,
        min_length=1,
        max_length=120,
        pattern=r"^[A-Za-z0-9_-]+$",
    ),
    current_user: ExtendedAuthUser = Depends(require_storefront_owner),
):
    if attempt_id:
        await storefront_domain_service.disconnect(current_user, attempt_id=attempt_id)
    else:
        await storefront_domain_service.disconnect(current_user)
    return StorefrontDomainDisconnectResponse(attempt_id=attempt_id)


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
    "/storefront/domain-instructions/{token}",
    response_model=StorefrontDomainInstructionPublicResponse,
)
async def get_storefront_domain_instructions(
    response: Response,
    token: str = Path(min_length=43, max_length=128, pattern=r"^[A-Za-z0-9_-]+$"),
):
    """Return an expiring read-only DNS snapshot; no mutation is exposed."""

    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return await storefront_domain_service.read_instruction_link(token)


@public_router.get(
    "/storefront/domain-verification-probe",
    response_model=StorefrontDomainHttpsProbeResponse,
)
async def verify_storefront_domain_origin(request: Request, response: Response):
    """Attest exact custom-host routing without requiring storefront publication."""

    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return await storefront_domain_https_probe_service.attest(
        request.headers.get(PROBE_HOST_HEADER, ""),
        request.headers.get(PROBE_HEADER, ""),
        request.headers.get(PROBE_INGRESS_HEADER, ""),
    )


@public_router.get(
    "/storefront/{identifier}",
    response_model=PublicStorefrontResponse,
)
async def get_public_storefront(identifier: str):
    """Resolve only a stored, published storefront slug or active custom host."""

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
