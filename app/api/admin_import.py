from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Depends
from app.services.import_service import GuestImportService
from app.dependencies.auth import require_admin

router = APIRouter()

import_service = GuestImportService()

@router.post("/guests/import", tags=["Admin"], dependencies=[Depends(require_admin)])
def import_guests(file: UploadFile = File(...), wedding_id: str = Query(...)):
    try:
        return import_service.import_csv(file, wedding_id)
    except HTTPException as e:
        raise e
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to process guest import")