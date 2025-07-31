from fastapi import APIRouter, Query, Depends, UploadFile, File, Form
from app.services.gallery_upload_service import GalleryUploadService
from app.dependencies.auth import require_admin

router = APIRouter()
gallery_service = GalleryUploadService()

# Admin Upload URL Endpoint\@router.get("/gallery/upload-url", tags=["Admin"], dependencies=[Depends(require_admin)])
def get_upload_url(filename: str = Query(...)):
    return gallery_service.create_presigned_url(filename)

# Admin Get File URL Endpoint\@router.get("/gallery/file-url", tags=["Admin"], dependencies=[Depends(require_admin)])
def get_file_url(key: str = Query(...)):
    return gallery_service.get_file_url(key)

# Admin Delete File Endpoint
@router.delete("/gallery/delete", tags=["Admin"], dependencies=[Depends(require_admin)])
def delete_file(key: str = Query(...)):
    return gallery_service.delete_file(key)

# Admin List Files Endpoint\@router.get("/gallery/list", tags=["Admin"], dependencies=[Depends(require_admin)])
def list_gallery_files():
    return gallery_service.list_uploaded_files()

# Admin Direct Upload Endpoint (updated to include wedding_slug)
@router.post("/gallery/upload", tags=["Admin"], dependencies=[Depends(require_admin)])
def upload_file(file: UploadFile = File(...), wedding_slug: str = Form(...)):
    return gallery_service.upload_file_direct(file, wedding_slug)

# Public Guest-Facing Endpoint (now wedding_slug required)
@router.get("/gallery", tags=["Guest"])
def public_gallery(wedding_slug: str = Query(...)):
    prefix = f"gallery/{wedding_slug}/"
    return gallery_service.list_uploaded_files(prefix=prefix)

# Public QR Code Generator\@router.get("/invite/qr", tags=["Guest"])
def generate_invite_qr(url: str = Query(...)):
    return gallery_service.generate_qr_code(url)

