from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.dependencies.guest_access import get_guest_access_session
from app.services.gallery_media_service import GalleryUploadService
from app.services.wedding_service import WeddingService

router = APIRouter()
gallery_service = GalleryUploadService()
wedding_service = WeddingService()


class VerifiedGalleryRequest(BaseModel):
    wedding_slug: str = Field(..., description="Wedding slug")
    token: Optional[str] = Field(None, description="Guest invitation token")
    name: Optional[str] = Field(
        None, description="Guest name for verification fallback"
    )
    phone: Optional[str] = Field(
        None, description="Guest phone for verification fallback"
    )
    email: Optional[str] = Field(
        None, description="Guest email for verification fallback"
    )
    password: Optional[str] = Field(
        None, description="Wedding password if password protected"
    )
    otp_code: Optional[str] = Field(None, description="OTP verification code")
    contact: Optional[str] = Field(
        None, description="Contact used for OTP verification"
    )
    limit: int = Field(default=60, ge=1, le=100, description="Maximum files to return")
    cursor: Optional[str] = Field(
        None, description="Continuation cursor from the previous page"
    )


async def _list_gallery_page_for_wedding(
    wedding_slug: str, limit: int, cursor: Optional[str]
):
    wedding = await wedding_service.get_wedding_by_slug(wedding_slug)
    planner_scope = gallery_service.get_planner_scope_from_wedding(wedding)
    return gallery_service.list_wedding_files_page(
        folder="gallery",
        wedding_slug=wedding_slug,
        planner_scope=planner_scope,
        limit=limit,
        cursor=cursor,
    )


# Public Guest-Facing Endpoint - DEPRECATED for security
@router.get("/gallery", tags=["Guest"])
async def public_gallery(
    wedding_slug: str = Query(...),
    limit: int = Query(12, ge=1, le=100),
    cursor: Optional[str] = Query(None),
):
    """
    Get gallery images for a specific wedding - DEPRECATED for security reasons.
    This endpoint now requires guest verification.
    """
    from app.services.guest_verification_service import GuestVerificationService

    verification_service = GuestVerificationService()
    privacy_info = await verification_service.get_wedding_privacy_info(wedding_slug)

    # Only allow public access if wedding is explicitly public
    if privacy_info.get("privacy_mode") == "public":
        return await _list_gallery_page_for_wedding(wedding_slug, limit, cursor)

    raise HTTPException(
        status_code=403,
        detail="Gallery access requires guest verification. Use /gallery/verified endpoint with proper authentication.",
    )


# New secure gallery endpoint
@router.post("/gallery/verified", tags=["Guest"])
async def verified_gallery(request: VerifiedGalleryRequest, http_request: Request):
    """Get gallery images for verified guests only"""
    from app.services.guest_verification_service import GuestVerificationService

    verification_service = GuestVerificationService()
    if request.token:
        result = await verification_service.get_rsvp_access_by_token(
            request.wedding_slug, request.token
        )
    elif any(
        [
            request.name,
            request.phone,
            request.email,
            request.password,
            request.otp_code,
            request.contact,
        ]
    ):
        verification_data = {
            "name": request.name,
            "phone": request.phone,
            "email": request.email,
            "password": request.password,
            "otp_code": request.otp_code,
            "contact": request.contact,
        }
        result = await verification_service.verify_wedding_page_access(
            request.wedding_slug,
            verification_data,
        )
    else:
        session = get_guest_access_session(http_request, slug=request.wedding_slug)
        result = await verification_service.get_session_access(
            slug=request.wedding_slug,
            wedding_id=session.wedding_id,
            guest_id=session.guest_id,
            auth_method=session.auth_method,
            otp_verified=session.otp_verified,
        )

    if not result.get("access"):
        raise HTTPException(status_code=403, detail="Guest verification failed")

    return await _list_gallery_page_for_wedding(
        request.wedding_slug,
        request.limit,
        request.cursor,
    )


# Public QR Code Generator
@router.get("/invite/qr", tags=["Guest"])
def generate_invite_qr(url: str = Query(...)):
    """Generate QR code for invite URL"""
    return gallery_service.generate_qr_code(url)
