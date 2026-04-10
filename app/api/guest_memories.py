import hashlib
import logging
from datetime import datetime
from typing import Literal, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
)
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.dependencies.auth_extended import (
    ExtendedAuthUser,
    check_wedding_access,
    enforce_team_permission,
    require_team_or_planner,
)
from app.dependencies.couple_auth import require_couple_auth
from app.services.guest_export_service import guest_export_service
from app.services.guest_media_service import NOT_SURE_EVENT, guest_media_service
from app.utils.rate_limiter import check_rate_limit, create_rate_limiter, get_client_ip

logger = logging.getLogger(__name__)

router = APIRouter()

guest_media_bootstrap_limiter = create_rate_limiter(
    "guest_media_bootstrap", requests_per_minute=20
)
guest_media_upload_plan_limiter = create_rate_limiter(
    "guest_media_upload_plan", requests_per_minute=10
)
guest_media_finalize_limiter = create_rate_limiter(
    "guest_media_finalize", requests_per_minute=10
)


def _token_scope_key(request: Request, upload_token: str) -> str:
    token_hash = hashlib.sha256(upload_token.encode("utf-8")).hexdigest()[:16]
    return f"{get_client_ip(request)}:{token_hash}"


async def _apply_public_guest_media_rate_limit(
    request: Request, upload_token: str, bucket
) -> None:
    await check_rate_limit(_token_scope_key(request, upload_token), bucket)


async def _authorize_planner_guest_memories_access(
    wedding_id: str,
    current_user: ExtendedAuthUser,
) -> str:
    enforce_team_permission(current_user, "manage_guests")
    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")
    return wedding_id


class GuestMediaPlanFileRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., min_length=1, max_length=100)
    size_bytes: int = Field(..., gt=0)
    event_type: Optional[str] = Field(default=None, max_length=100)


class GuestMediaUploadPlanRequest(BaseModel):
    uploader_name: str = Field(..., min_length=1, max_length=120)
    batch_event_type: Optional[str] = Field(default=None, max_length=100)
    files: list[GuestMediaPlanFileRequest] = Field(..., min_length=1, max_length=25)


class GuestMediaFinalizeRequest(BaseModel):
    upload_batch_id: str = Field(..., min_length=1, max_length=40)
    asset_ids: list[str] = Field(..., min_length=1, max_length=25)


class CoupleGuestMediaSettingsUpdateRequest(BaseModel):
    enabled: Optional[bool] = Field(default=None)
    upload_closes_at: Optional[datetime] = Field(default=None)


class CoupleGuestMediaReviewRequest(BaseModel):
    review_status: Literal["pending", "kept", "rejected"]


class CoupleGuestMediaExportRequest(BaseModel):
    asset_ids: list[str] = Field(default_factory=list, max_length=5000)
    review_status: Literal["all", "pending", "kept", "rejected"] = "kept"


@router.get("/guest-media/public/{slug}/{upload_token}", tags=["Guest Memories"])
async def get_public_guest_media_context(
    slug: str, upload_token: str, request: Request
):
    await _apply_public_guest_media_rate_limit(
        request, upload_token, guest_media_bootstrap_limiter
    )
    return await guest_media_service.get_public_upload_context(slug, upload_token)


@router.post(
    "/guest-media/public/{slug}/{upload_token}/upload-plan", tags=["Guest Memories"]
)
async def create_guest_media_upload_plan(
    slug: str,
    upload_token: str,
    payload: GuestMediaUploadPlanRequest,
    request: Request,
):
    await _apply_public_guest_media_rate_limit(
        request, upload_token, guest_media_upload_plan_limiter
    )
    return await guest_media_service.create_upload_plan(
        slug,
        upload_token,
        payload.uploader_name,
        payload.batch_event_type,
        [file.model_dump() for file in payload.files],
    )


@router.post(
    "/guest-media/public/{slug}/{upload_token}/finalize", tags=["Guest Memories"]
)
async def finalize_guest_media_upload(
    slug: str,
    upload_token: str,
    payload: GuestMediaFinalizeRequest,
    request: Request,
):
    await _apply_public_guest_media_rate_limit(
        request, upload_token, guest_media_finalize_limiter
    )
    return await guest_media_service.finalize_upload_batch(
        slug,
        upload_token,
        payload.upload_batch_id,
        payload.asset_ids,
    )


@router.get("/admin/guest-memories/settings", tags=["Guest Memories"])
async def get_planner_guest_media_settings(
    wedding_id: str = Query(..., description="Wedding ID"),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    await _authorize_planner_guest_memories_access(wedding_id, current_user)
    return await guest_media_service.get_couple_settings(wedding_id)


@router.put("/admin/guest-memories/settings", tags=["Guest Memories"])
async def update_planner_guest_media_settings(
    payload: CoupleGuestMediaSettingsUpdateRequest,
    wedding_id: str = Query(..., description="Wedding ID"),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    if payload.enabled is None and payload.upload_closes_at is None:
        raise HTTPException(
            status_code=400, detail="No guest media settings were provided"
        )

    await _authorize_planner_guest_memories_access(wedding_id, current_user)
    return await guest_media_service.update_couple_settings(
        wedding_id,
        enabled=payload.enabled,
        upload_closes_at=payload.upload_closes_at,
    )


@router.post("/admin/guest-memories/rotate-link", tags=["Guest Memories"])
async def rotate_planner_guest_media_link(
    wedding_id: str = Query(..., description="Wedding ID"),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    await _authorize_planner_guest_memories_access(wedding_id, current_user)
    return await guest_media_service.rotate_upload_link(wedding_id)


@router.get("/admin/guest-memories/qr-code", tags=["Guest Memories"])
async def get_planner_guest_media_qr_code(
    wedding_id: str = Query(..., description="Wedding ID"),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    await _authorize_planner_guest_memories_access(wedding_id, current_user)

    settings_payload = await guest_media_service.get_couple_settings(wedding_id)
    png_bytes = guest_export_service.generate_qr_code(settings_payload["upload_url"])

    wedding_slug = settings_payload.get("wedding", {}).get("slug") or "wedding"
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={
            "Content-Disposition": f'inline; filename="{wedding_slug}-guest-memories-qr.png"',
            "Cache-Control": "private, max-age=300",
        },
    )


@router.get("/admin/guest-memories/sign-pdf", tags=["Guest Memories"])
async def download_planner_guest_media_sign_pdf(
    wedding_id: str = Query(..., description="Wedding ID"),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    await _authorize_planner_guest_memories_access(wedding_id, current_user)

    try:
        settings_payload = await guest_media_service.get_couple_settings(wedding_id)
        qr_bytes = guest_export_service.generate_qr_code(
            settings_payload["upload_url"], box_size=12
        )
        pdf_bytes = await guest_export_service.generate_guest_memories_sign_pdf(
            couple_names=settings_payload.get("wedding", {}).get("couple_names")
            or "Wedding",
            upload_url=settings_payload["upload_url"],
            qr_png_bytes=qr_bytes,
            upload_closes_at=(
                datetime.fromisoformat(
                    settings_payload["upload_closes_at"].replace("Z", "+00:00")
                )
                if settings_payload.get("upload_closes_at")
                else None
            ),
        )
    except ImportError as exc:
        logger.error(f"Guest memories sign PDF generation dependency missing: {exc}")
        raise HTTPException(
            status_code=503,
            detail="PDF generation not available. WeasyPrint may not be installed.",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to generate guest memories sign PDF: {exc}")
        raise HTTPException(
            status_code=500, detail="Failed to generate guest memories sign PDF"
        ) from exc

    wedding_slug = settings_payload.get("wedding", {}).get("slug") or "wedding"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{wedding_slug}-guest-memories-sign.pdf"',
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/couple/portal/memories/settings", tags=["Guest Memories"])
async def get_couple_guest_media_settings(couple: dict = Depends(require_couple_auth)):
    wedding_id = couple.get("wedding_id")
    if not wedding_id:
        raise HTTPException(status_code=404, detail="No wedding linked to this account")
    return await guest_media_service.get_couple_settings(wedding_id)


@router.put("/couple/portal/memories/settings", tags=["Guest Memories"])
async def update_couple_guest_media_settings(
    payload: CoupleGuestMediaSettingsUpdateRequest,
    couple: dict = Depends(require_couple_auth),
):
    if payload.enabled is None and payload.upload_closes_at is None:
        raise HTTPException(
            status_code=400, detail="No guest media settings were provided"
        )

    wedding_id = couple.get("wedding_id")
    if not wedding_id:
        raise HTTPException(status_code=404, detail="No wedding linked to this account")

    return await guest_media_service.update_couple_settings(
        wedding_id,
        enabled=payload.enabled,
        upload_closes_at=payload.upload_closes_at,
    )


@router.post("/couple/portal/memories/rotate-link", tags=["Guest Memories"])
async def rotate_guest_media_link(couple: dict = Depends(require_couple_auth)):
    wedding_id = couple.get("wedding_id")
    if not wedding_id:
        raise HTTPException(status_code=404, detail="No wedding linked to this account")
    return await guest_media_service.rotate_upload_link(wedding_id)


@router.get("/couple/portal/memories/qr-code", tags=["Guest Memories"])
async def get_guest_media_qr_code(couple: dict = Depends(require_couple_auth)):
    wedding_id = couple.get("wedding_id")
    if not wedding_id:
        raise HTTPException(status_code=404, detail="No wedding linked to this account")

    settings_payload = await guest_media_service.get_couple_settings(wedding_id)
    png_bytes = guest_export_service.generate_qr_code(settings_payload["upload_url"])

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={
            "Content-Disposition": 'inline; filename="guest-memories-upload-qr.png"',
            "Cache-Control": "private, max-age=300",
        },
    )


@router.get("/couple/portal/memories", tags=["Guest Memories"])
async def list_couple_guest_media(
    review_status: str = Query("all", pattern="^(all|pending|kept|rejected)$"),
    media_type: str = Query("all", pattern="^(all|image|video)$"),
    event_type: str = Query(
        "all", description=f"Wedding event type filter or {NOT_SURE_EVENT}"
    ),
    uploader_query: Optional[str] = Query(default=None, max_length=120),
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=60),
    couple: dict = Depends(require_couple_auth),
):
    wedding_id = couple.get("wedding_id")
    if not wedding_id:
        raise HTTPException(status_code=404, detail="No wedding linked to this account")

    return await guest_media_service.list_couple_assets(
        wedding_id,
        review_status=review_status,
        media_type=media_type,
        event_type=event_type,
        uploader_query=uploader_query,
        page=page,
        limit=limit,
    )


@router.patch("/couple/portal/memories/{asset_id}/review", tags=["Guest Memories"])
async def review_couple_guest_media(
    asset_id: str,
    payload: CoupleGuestMediaReviewRequest,
    couple: dict = Depends(require_couple_auth),
):
    wedding_id = couple.get("wedding_id")
    if not wedding_id:
        raise HTTPException(status_code=404, detail="No wedding linked to this account")

    return await guest_media_service.update_review_status(
        wedding_id,
        asset_id,
        payload.review_status,
    )


@router.get("/couple/portal/memories/{asset_id}/download", tags=["Guest Memories"])
async def download_guest_media_asset(
    asset_id: str, couple: dict = Depends(require_couple_auth)
):
    wedding_id = couple.get("wedding_id")
    if not wedding_id:
        raise HTTPException(status_code=404, detail="No wedding linked to this account")
    return await guest_media_service.get_asset_download(wedding_id, asset_id)


async def _redirect_to_couple_memory_variant(
    couple: dict, asset_id: str, variant: str
) -> RedirectResponse:
    wedding_id = couple.get("wedding_id")
    if not wedding_id:
        raise HTTPException(status_code=404, detail="No wedding linked to this account")

    target_url = await guest_media_service.get_asset_redirect_url(
        wedding_id, asset_id, variant
    )
    response = RedirectResponse(target_url, status_code=307)
    response.headers["Cache-Control"] = "private, no-store"
    return response


@router.get("/couple/portal/memories/{asset_id}/preview", tags=["Guest Memories"])
async def preview_guest_media_asset(
    asset_id: str, couple: dict = Depends(require_couple_auth)
):
    return await _redirect_to_couple_memory_variant(couple, asset_id, "preview")


@router.get("/couple/portal/memories/{asset_id}/player", tags=["Guest Memories"])
async def player_guest_media_asset(
    asset_id: str, couple: dict = Depends(require_couple_auth)
):
    return await _redirect_to_couple_memory_variant(couple, asset_id, "player")


@router.get("/couple/portal/memories/{asset_id}/thumbnail", tags=["Guest Memories"])
async def thumbnail_guest_media_asset(
    asset_id: str, couple: dict = Depends(require_couple_auth)
):
    return await _redirect_to_couple_memory_variant(couple, asset_id, "thumbnail")


@router.post("/couple/portal/memories/exports", tags=["Guest Memories"])
async def create_guest_media_export(
    payload: CoupleGuestMediaExportRequest,
    background_tasks: BackgroundTasks,
    couple: dict = Depends(require_couple_auth),
):
    wedding_id = couple.get("wedding_id")
    if not wedding_id:
        raise HTTPException(status_code=404, detail="No wedding linked to this account")

    export_job = await guest_media_service.create_export_job(
        wedding_id,
        couple.get("email", "couple"),
        asset_ids=payload.asset_ids or None,
        review_status=payload.review_status,
    )
    background_tasks.add_task(
        guest_media_service.process_export_job, export_job["export_id"]
    )
    return export_job


@router.get("/couple/portal/memories/exports/{export_id}", tags=["Guest Memories"])
async def get_guest_media_export(
    export_id: str, couple: dict = Depends(require_couple_auth)
):
    wedding_id = couple.get("wedding_id")
    if not wedding_id:
        raise HTTPException(status_code=404, detail="No wedding linked to this account")
    return await guest_media_service.get_export_job(wedding_id, export_id)


@router.get(
    "/couple/portal/memories/exports/{export_id}/download", tags=["Guest Memories"]
)
async def download_guest_media_export(
    export_id: str, couple: dict = Depends(require_couple_auth)
):
    wedding_id = couple.get("wedding_id")
    if not wedding_id:
        raise HTTPException(status_code=404, detail="No wedding linked to this account")

    export_job = await guest_media_service.get_export_job(wedding_id, export_id)
    download_url = export_job.get("download_url")
    if not download_url:
        raise HTTPException(
            status_code=409, detail="Export is not ready to download yet"
        )
    return {"download_url": download_url}
