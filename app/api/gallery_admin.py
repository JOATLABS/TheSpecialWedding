from fastapi import APIRouter, Query, Depends, UploadFile, File, Form
from app.services.gallery_upload_service import GalleryUploadService
from app.dependencies.auth import require_admin

router = APIRouter()
gallery_service = GalleryUploadService()

# Admin Upload URL Endpoint
@router.get("/gallery/upload-url", tags=["Admin"], dependencies=[Depends(require_admin)])
def get_upload_url(filename: str = Query(...)):
    """Get presigned URL for uploading to S3"""
    return gallery_service.create_presigned_url(filename)

# Admin Get File URL Endpoint
@router.get("/gallery/file-url", tags=["Admin"], dependencies=[Depends(require_admin)])
def get_file_url(key: str = Query(...)):
    """Get URL for a specific file"""
    return gallery_service.get_file_url(key)

# Admin Delete File Endpoint
@router.delete("/gallery", tags=["Admin"], dependencies=[Depends(require_admin)])
def delete_file(key: str = Query(...)):
    """Delete a gallery image"""
    return gallery_service.delete_file(key)

# Admin List Files Endpoint
@router.get("/gallery/list", tags=["Admin"], dependencies=[Depends(require_admin)])
def list_gallery_files(prefix: str = Query("gallery/")):
    """List all uploaded files (admin view)"""
    return gallery_service.list_uploaded_files(prefix=prefix)

# Admin Direct Upload Endpoint
@router.post("/gallery/upload", tags=["Admin"], dependencies=[Depends(require_admin)])
def upload_file(file: UploadFile = File(...), wedding_slug: str = Form(...), folder: str = Form("gallery")):
    """Upload image directly to gallery"""
    return gallery_service.upload_file_direct(file, wedding_slug, folder)