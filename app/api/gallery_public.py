from fastapi import APIRouter, Query
from app.services.gallery_upload_service import GalleryUploadService

router = APIRouter()
gallery_service = GalleryUploadService()

# Public Guest-Facing Endpoint
@router.get("/gallery", tags=["Guest"])
def public_gallery(wedding_slug: str = Query(...)):
    """Get gallery images for a specific wedding"""
    prefix = f"gallery/{wedding_slug}/"
    return gallery_service.list_uploaded_files(prefix=prefix)

# Public QR Code Generator
@router.get("/invite/qr", tags=["Guest"])
def generate_invite_qr(url: str = Query(...)):
    """Generate QR code for invite URL"""
    return gallery_service.generate_qr_code(url)