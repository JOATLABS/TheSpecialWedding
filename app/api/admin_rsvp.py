from fastapi import APIRouter, Response, Depends, Query, HTTPException
from app.services.admin_rsvp_service import AdminRSVPService
from app.dependencies.auth_extended import require_wedding_planner_only, ExtendedAuthUser, check_wedding_access
from app.services.guest_service import GuestService
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

admin_service = AdminRSVPService()
guest_service = GuestService()


class AdminRSVPUpdateRequest(BaseModel):
    """Request model for admin to update or create an RSVP"""
    attending: List[str] = []
    dietary: Optional[str] = None
    confirmed_by_admin: bool = True


@router.get("/rsvps", tags=["Admin"])
async def get_rsvps(wedding_id: Optional[str] = Query(None), current_user: ExtendedAuthUser = Depends(require_wedding_planner_only)):
    # Check wedding access if wedding_id is provided
    if wedding_id and not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")
    return await admin_service.get_all_rsvps(wedding_id)

@router.get("/rsvps/export", tags=["Admin"])
async def export_rsvps(wedding_id: Optional[str] = Query(None), current_user: ExtendedAuthUser = Depends(require_wedding_planner_only)):
    # Check wedding access if wedding_id is provided
    if wedding_id and not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")
    csv_data = await admin_service.export_rsvps_to_csv()
    return Response(content=csv_data, media_type="text/csv", headers={
        "Content-Disposition": "attachment; filename=rsvps.csv"
    })


@router.put("/rsvps/{guest_id}", tags=["Admin"])
async def admin_update_rsvp(
    guest_id: str,
    rsvp_data: AdminRSVPUpdateRequest,
    current_user: ExtendedAuthUser = Depends(require_wedding_planner_only)
):
    """Admin endpoint to create or update an RSVP for a guest (manual confirmation)."""
    # Get guest to check wedding access
    guest = await guest_service.get_guest(guest_id)
    if not await check_wedding_access(current_user, guest.get("wedding_id")):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    try:
        return await admin_service.admin_create_or_update_rsvp(
            guest_id=guest_id,
            wedding_id=guest.get("wedding_id"),
            attending=rsvp_data.attending,
            dietary=rsvp_data.dietary,
            confirmed_by_admin=rsvp_data.confirmed_by_admin
        )
    except HTTPException as e:
        raise e
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Failed to update RSVP: {str(err)}")


@router.delete("/rsvps/{guest_id}", tags=["Admin"])
async def admin_delete_rsvp(
    guest_id: str,
    current_user: ExtendedAuthUser = Depends(require_wedding_planner_only)
):
    """Admin endpoint to delete an RSVP for a guest."""
    # Get guest to check wedding access
    guest = await guest_service.get_guest(guest_id)
    if not await check_wedding_access(current_user, guest.get("wedding_id")):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    try:
        return await admin_service.delete_rsvp(guest_id)
    except HTTPException as e:
        raise e
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Failed to delete RSVP: {str(err)}")
