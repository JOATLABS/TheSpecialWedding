from fastapi import APIRouter, Response, Depends, Query, HTTPException
from app.services.admin_rsvp_service import AdminRSVPService
from app.dependencies.auth_extended import require_wedding_planner_only, ExtendedAuthUser, check_wedding_access
from typing import Optional

router = APIRouter()

admin_service = AdminRSVPService()

@router.get("/rsvps", tags=["Admin"])
async def get_rsvps(wedding_id: Optional[str] = Query(None), current_user: ExtendedAuthUser = Depends(require_wedding_planner_only)):
    # Check wedding access if wedding_id is provided
    if wedding_id and not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")
    return admin_service.get_all_rsvps(wedding_id)

@router.get("/rsvps/export", tags=["Admin"])
async def export_rsvps(wedding_id: Optional[str] = Query(None), current_user: ExtendedAuthUser = Depends(require_wedding_planner_only)):
    # Check wedding access if wedding_id is provided
    if wedding_id and not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")
    csv_data = admin_service.export_rsvps_to_csv()
    return Response(content=csv_data, media_type="text/csv", headers={
        "Content-Disposition": "attachment; filename=rsvps.csv"
    })
