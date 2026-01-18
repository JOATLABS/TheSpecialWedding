from fastapi import APIRouter, Query
from app.services.gallery_upload_service import GalleryUploadService

router = APIRouter()
gallery_service = GalleryUploadService()

# Public Guest-Facing Endpoint - DEPRECATED for security
@router.get("/gallery", tags=["Guest"])
async def public_gallery(wedding_slug: str = Query(...)):
    """
    Get gallery images for a specific wedding - DEPRECATED for security reasons.
    This endpoint now requires guest verification.
    """
    from fastapi import HTTPException
    from app.services.guest_verification_service import GuestVerificationService

    verification_service = GuestVerificationService()
    privacy_info = await verification_service.get_wedding_privacy_info(wedding_slug)

    # Only allow public access if wedding is explicitly public
    if privacy_info.get("privacy_mode") == "public":
        prefix = f"gallery/{wedding_slug}/"
        return gallery_service.list_uploaded_files(prefix=prefix)

    raise HTTPException(
        status_code=403,
        detail="Gallery access requires guest verification. Use /gallery/verified endpoint with proper authentication."
    )

# New secure gallery endpoint
@router.post("/gallery/verified", tags=["Guest"])
async def verified_gallery(
    wedding_slug: str = Query(...),
    token: str = Query(None, description="Guest verification token"),
    name: str = Query(None, description="Guest name for verification"),
    phone: str = Query(None, description="Guest phone for verification"),
    password: str = Query(None, description="Wedding password if password-protected")
):
    """Get gallery images for verified guests only"""
    from app.services.guest_verification_service import GuestVerificationService

    verification_service = GuestVerificationService()

    # Verify guest access
    verification_data = {
        "token": token,
        "name": name,
        "phone": phone,
        "password": password
    }

    result = await verification_service.verify_guest_access(wedding_slug, verification_data)

    if not result.get("access"):
        raise HTTPException(status_code=403, detail="Guest verification failed")

    # Return gallery if verified
    prefix = f"gallery/{wedding_slug}/"
    return gallery_service.list_uploaded_files(prefix=prefix)

# Public QR Code Generator
@router.get("/invite/qr", tags=["Guest"])
def generate_invite_qr(url: str = Query(...)):
    """Generate QR code for invite URL"""
    return gallery_service.generate_qr_code(url)