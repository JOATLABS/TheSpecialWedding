from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from app.services.import_service import GuestImportService

router = APIRouter()

import_service = GuestImportService()

@router.post("/admin/guests/import", tags=["Admin"])
def import_guests(file: UploadFile = File(...), wedding_id: str = Query(...)):
    try:
        return import_service.import_csv(file, wedding_id)
    except HTTPException as e:
        raise e
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to process guest import")