from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Depends
from app.services.import_service import GuestImportService
from app.dependencies.auth_extended import require_admin_or_planner, ExtendedAuthUser, check_wedding_access

router = APIRouter()

import_service = GuestImportService()

@router.post("/guests/import", tags=["Admin"])
def import_guests(file: UploadFile = File(...), wedding_id: str = Query(...), current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    # Check if user has access to this wedding
    if not check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")
    try:
        return import_service.import_csv(file, wedding_id)
    except HTTPException as e:
        raise e
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to process guest import")