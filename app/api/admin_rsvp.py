from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel

from app.dependencies.auth_extended import (
    ExtendedAuthUser,
    check_wedding_access,
    enforce_team_permission,
    require_wedding_planner_only,
)
from app.services.admin_rsvp_service import AdminRSVPService
from app.services.guest_service import GuestService
from app.services.sse_manager import sse_manager

router = APIRouter()

admin_service = AdminRSVPService()
guest_service = GuestService()


class AdminRSVPUpdateRequest(BaseModel):
    """Request model for admin to update or create an RSVP"""

    attending: list[str] = []
    dietary: str | None = None
    phone: str | None = None
    email: str | None = None
    confirmed_by_admin: bool = True


@router.get("/rsvps", tags=["Admin"])
async def get_rsvps(
    wedding_id: str | None = Query(None),
    guest_ids: str | None = Query(None, description="Comma-separated guest IDs"),
    current_user: ExtendedAuthUser = Depends(require_wedding_planner_only),
):
    # Check wedding access if wedding_id is provided
    if wedding_id and not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    guest_id_list = None
    if guest_ids is not None:
        guest_id_list = [
            guest_id.strip() for guest_id in guest_ids.split(",") if guest_id.strip()
        ]

    return await admin_service.get_all_rsvps(wedding_id, guest_id_list)


@router.get("/rsvps/export", tags=["Admin"])
async def export_rsvps(
    wedding_id: str | None = Query(None),
    current_user: ExtendedAuthUser = Depends(require_wedding_planner_only),
):
    # Check wedding access if wedding_id is provided
    if wedding_id and not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")
    csv_data = await admin_service.export_rsvps_to_csv()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=rsvps.csv"},
    )


@router.put("/rsvps/{guest_id}", tags=["Admin"])
async def admin_update_rsvp(
    guest_id: str,
    rsvp_data: AdminRSVPUpdateRequest,
    current_user: ExtendedAuthUser = Depends(require_wedding_planner_only),
):
    """Admin endpoint to create or update an RSVP for a guest (manual confirmation)."""
    enforce_team_permission(current_user, "manage_guests")
    # Get guest to check wedding access
    guest = await guest_service.get_guest(guest_id)
    if not await check_wedding_access(current_user, guest.get("wedding_id")):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    try:
        # If admin provided phone/email, update the guest record directly
        if rsvp_data.phone or rsvp_data.email:
            update_fields = {}
            if rsvp_data.phone is not None:
                update_fields["phone"] = rsvp_data.phone
            if rsvp_data.email is not None:
                update_fields["email"] = rsvp_data.email
            if update_fields:
                await guest_service.update_guest(guest_id, update_fields)

        result = await admin_service.admin_create_or_update_rsvp(
            guest_id=guest_id,
            wedding_id=guest.get("wedding_id"),
            attending=rsvp_data.attending,
            dietary=rsvp_data.dietary,
            confirmed_by_admin=rsvp_data.confirmed_by_admin,
        )

        await sse_manager.broadcast_data_change(
            current_user.email,
            "rsvp",
            "updated",
            wedding_id=str(guest.get("wedding_id", "")),
            record_id=guest_id,
        )

        return result
    except HTTPException as e:
        raise e
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Failed to update RSVP: {err!s}")


@router.delete("/rsvps/{guest_id}", tags=["Admin"])
async def admin_delete_rsvp(
    guest_id: str,
    current_user: ExtendedAuthUser = Depends(require_wedding_planner_only),
):
    """Admin endpoint to delete an RSVP for a guest."""
    enforce_team_permission(current_user, "manage_guests")
    # Get guest to check wedding access
    guest = await guest_service.get_guest(guest_id)
    if not await check_wedding_access(current_user, guest.get("wedding_id")):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    try:
        result = await admin_service.delete_rsvp(guest_id)

        await sse_manager.broadcast_data_change(
            current_user.email,
            "rsvp",
            "deleted",
            wedding_id=str(guest.get("wedding_id", "")),
            record_id=guest_id,
        )

        return result
    except HTTPException as e:
        raise e
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Failed to delete RSVP: {err!s}")
