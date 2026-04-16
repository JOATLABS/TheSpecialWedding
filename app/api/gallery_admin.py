from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from app.dependencies.auth_extended import (
    ExtendedAuthUser,
    check_wedding_access,
    enforce_team_permission,
    require_team_or_planner,
)
from app.services.gallery_media_service import GalleryUploadService
from app.services.wedding_service import WeddingService

router = APIRouter()
gallery_service = GalleryUploadService()
wedding_service = WeddingService()


async def get_accessible_wedding_by_slug(
    wedding_slug: str, current_user: ExtendedAuthUser
) -> dict:
    """Load a wedding by slug and ensure the current user can access it."""
    wedding = await wedding_service.get_wedding_by_slug(wedding_slug)
    if not await check_wedding_access(current_user, str(wedding.get("_id"))):
        raise HTTPException(
            status_code=403, detail="Access denied to this wedding's gallery"
        )
    return wedding


# Admin Upload URL Endpoint
@router.get("/gallery/upload-url", tags=["Admin"])
async def get_upload_url(
    filename: str = Query(...),
    wedding_slug: str = Query(..., description="Wedding slug to upload to"),
    folder: str = Query(
        "gallery", description="Folder to upload to (gallery, our-story, wedding-party)"
    ),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """Get presigned URL for uploading to S3 - validates wedding ownership"""
    enforce_team_permission(current_user, "manage_gallery")
    wedding = await get_accessible_wedding_by_slug(wedding_slug, current_user)

    return gallery_service.create_presigned_url_with_wedding(
        filename,
        wedding_slug,
        folder,
        planner_scope=gallery_service.get_planner_scope_from_wedding(wedding),
    )


# Admin Get File URL Endpoint
@router.get("/gallery/file-url", tags=["Admin"])
async def get_file_url(
    key: str = Query(...),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """Get URL for a specific file - validates wedding ownership"""
    parsed_key = gallery_service.parse_wedding_storage_key(key)
    wedding_slug = parsed_key["wedding_slug"] if parsed_key else None

    if not wedding_slug:
        # If we can't extract wedding_slug, only root admin can proceed
        if not current_user.is_root_admin:
            raise HTTPException(
                status_code=403, detail="Invalid key format or access denied"
            )
    else:
        await get_accessible_wedding_by_slug(wedding_slug, current_user)

    return gallery_service.get_file_url(key)


# Admin Delete File Endpoint
@router.delete("/gallery", tags=["Admin"])
async def delete_file(
    key: str = Query(...),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """Delete a gallery image - validates wedding ownership"""
    enforce_team_permission(current_user, "manage_gallery")
    parsed_key = gallery_service.parse_wedding_storage_key(key)
    wedding_slug = parsed_key["wedding_slug"] if parsed_key else None

    if not wedding_slug:
        # If we can't extract wedding_slug, only root admin can proceed
        if not current_user.is_root_admin:
            raise HTTPException(
                status_code=403, detail="Invalid key format or access denied"
            )
    else:
        await get_accessible_wedding_by_slug(wedding_slug, current_user)

    return gallery_service.delete_file(key)


# Admin List Files Endpoint
@router.get("/gallery/list", tags=["Admin"])
async def list_gallery_files(
    prefix: str = Query("gallery/"),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """List all uploaded files (admin view) - filtered by wedding access"""
    parsed_prefix = gallery_service.parse_wedding_storage_prefix(prefix)
    if parsed_prefix:
        wedding = await get_accessible_wedding_by_slug(
            parsed_prefix["wedding_slug"], current_user
        )
        planner_scope = gallery_service.get_planner_scope_from_wedding(wedding)
        return gallery_service.list_wedding_files(
            folder=parsed_prefix["folder"],
            wedding_slug=parsed_prefix["wedding_slug"],
            planner_scope=planner_scope,
        )

    if not current_user.is_root_admin:
        # If no wedding slug specified and not root admin, return empty
        # This prevents planners from listing all images
        return []

    return gallery_service.list_uploaded_files(prefix=prefix)


# Admin Direct Upload Endpoint
@router.post("/gallery/upload", tags=["Admin"])
async def upload_file(
    file: UploadFile = File(...),
    wedding_slug: str = Form(...),
    folder: str = Form("gallery"),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """Upload image directly to gallery - verifies wedding access"""
    enforce_team_permission(current_user, "manage_gallery")
    wedding = await get_accessible_wedding_by_slug(wedding_slug, current_user)

    return gallery_service.upload_file_direct(
        file,
        wedding_slug,
        folder,
        planner_scope=gallery_service.get_planner_scope_from_wedding(wedding),
    )
