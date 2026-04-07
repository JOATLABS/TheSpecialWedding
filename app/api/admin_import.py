from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Depends
from app.services.import_service import GuestImportService
from app.dependencies.auth_extended import (
    require_wedding_planner_only,
    ExtendedAuthUser,
    check_wedding_access,
    enforce_team_permission,
)

router = APIRouter()

import_service = GuestImportService()


@router.post("/guests/import", tags=["Admin"])
async def import_guests(
    file: UploadFile = File(...),
    wedding_id: str = Query(...),
    current_user: ExtendedAuthUser = Depends(require_wedding_planner_only),
):
    enforce_team_permission(current_user, "manage_guests")
    # Check if user has access to this wedding
    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    # Validate file is CSV
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    if file.content_type not in {"text/csv", "application/vnd.ms-excel", "text/plain"}:
        raise HTTPException(status_code=400, detail="Invalid file content type for CSV")

    try:
        return await import_service.import_csv(file, wedding_id)
    except HTTPException as e:
        raise e
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to process guest import")
