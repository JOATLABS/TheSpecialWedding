from fastapi import APIRouter, Query, Depends, UploadFile, File, Form, HTTPException
from app.services.gallery_upload_service import GalleryUploadService
from app.services.wedding_service import WeddingService
from app.dependencies.auth_extended import (
    get_current_user_extended,
    ExtendedAuthUser,
    check_wedding_access,
    require_team_or_planner,
    enforce_team_permission,
)

router = APIRouter()
gallery_service = GalleryUploadService()
wedding_service = WeddingService()


async def verify_wedding_access_by_slug(wedding_slug: str, current_user: ExtendedAuthUser) -> bool:
    """Verify that the current user has access to the wedding by slug"""
    if current_user.is_root_admin:
        return True

    # Get the wedding by slug
    wedding = await wedding_service.get_wedding_by_slug(wedding_slug)
    if not wedding:
        return False

    # Check if planner is assigned to this wedding
    if current_user.is_wedding_planner:
        assigned_email = wedding.get("assigned_planner_email")
        if assigned_email and assigned_email == current_user.email:
            return True

    return False


# Admin Upload URL Endpoint
@router.get("/gallery/upload-url", tags=["Admin"])
async def get_upload_url(
    filename: str = Query(...),
    wedding_slug: str = Query(..., description="Wedding slug to upload to"),
    folder: str = Query("gallery", description="Folder to upload to (gallery, our-story, wedding-party)"),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner)
):
    """Get presigned URL for uploading to S3 - validates wedding ownership"""
    enforce_team_permission(current_user, "manage_gallery")
    # Verify access to this wedding
    if not await verify_wedding_access_by_slug(wedding_slug, current_user):
        raise HTTPException(status_code=403, detail="Access denied to this wedding's gallery")

    return gallery_service.create_presigned_url_with_wedding(filename, wedding_slug, folder)


# Admin Get File URL Endpoint
@router.get("/gallery/file-url", tags=["Admin"])
async def get_file_url(key: str = Query(...), current_user: ExtendedAuthUser = Depends(require_team_or_planner)):
    """Get URL for a specific file - validates wedding ownership"""
    # Extract wedding_slug from key (format: folder/wedding-slug/timestamp_filename)
    parts = key.split("/")
    wedding_slug = parts[1] if len(parts) >= 2 else None

    if not wedding_slug:
        # If we can't extract wedding_slug, only root admin can proceed
        if not current_user.is_root_admin:
            raise HTTPException(status_code=403, detail="Invalid key format or access denied")
    else:
        # Verify access to this wedding
        if not await verify_wedding_access_by_slug(wedding_slug, current_user):
            raise HTTPException(status_code=403, detail="Access denied to this wedding's gallery")

    return gallery_service.get_file_url(key)


# Admin Delete File Endpoint
@router.delete("/gallery", tags=["Admin"])
async def delete_file(key: str = Query(...), current_user: ExtendedAuthUser = Depends(require_team_or_planner)):
    """Delete a gallery image - validates wedding ownership"""
    enforce_team_permission(current_user, "manage_gallery")
    # Extract wedding_slug from key (format: folder/wedding-slug/timestamp_filename)
    parts = key.split("/")
    wedding_slug = parts[1] if len(parts) >= 2 else None

    if not wedding_slug:
        # If we can't extract wedding_slug, only root admin can proceed
        if not current_user.is_root_admin:
            raise HTTPException(status_code=403, detail="Invalid key format or access denied")
    else:
        # Verify access to this wedding
        if not await verify_wedding_access_by_slug(wedding_slug, current_user):
            raise HTTPException(status_code=403, detail="Access denied to this wedding's gallery")

    return gallery_service.delete_file(key)


# Admin List Files Endpoint
@router.get("/gallery/list", tags=["Admin"])
async def list_gallery_files(prefix: str = Query("gallery/"), current_user: ExtendedAuthUser = Depends(require_team_or_planner)):
    """List all uploaded files (admin view) - filtered by wedding access"""
    # Extract wedding slug from prefix (format: "folder/wedding-slug/")
    parts = prefix.strip("/").split("/")
    if len(parts) >= 2:
        wedding_slug = parts[1]  # e.g., "gallery/john-jane/" -> "john-jane"

        # Verify access to this wedding
        if not await verify_wedding_access_by_slug(wedding_slug, current_user):
            raise HTTPException(status_code=403, detail="Access denied to this wedding's gallery")
    elif not current_user.is_root_admin:
        # If no wedding slug specified and not root admin, return empty
        # This prevents planners from listing all images
        return []

    return gallery_service.list_uploaded_files(prefix=prefix)


# Admin Direct Upload Endpoint
@router.post("/gallery/upload", tags=["Admin"])
async def upload_file(file: UploadFile = File(...), wedding_slug: str = Form(...), folder: str = Form("gallery"), current_user: ExtendedAuthUser = Depends(require_team_or_planner)):
    """Upload image directly to gallery - verifies wedding access"""
    enforce_team_permission(current_user, "manage_gallery")
    # Verify access to this wedding
    if not await verify_wedding_access_by_slug(wedding_slug, current_user):
        raise HTTPException(status_code=403, detail="Access denied to upload to this wedding's gallery")

    return gallery_service.upload_file_direct(file, wedding_slug, folder)
