from fastapi import APIRouter, Depends, HTTPException, Query
from app.services.guest_service import GuestService
from app.dependencies.auth_extended import require_admin_or_planner, ExtendedAuthUser, check_wedding_access

router = APIRouter()

guest_service = GuestService()

@router.get("/invite/{token}", tags=["Guest"])
def get_guest(token: str, wedding_id: str = Query(...)):
    try:
        return guest_service.get_guest_by_token(token, wedding_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Unexpected error occurred")

@router.get("/invite/search", tags=["Guest"])
def search_guest(phone: str = Query(None), name: str = Query(None)):
    try:
        return guest_service.get_guest_by_phone_or_name(phone=phone, name=name)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Unexpected error occurred")

@router.get("/guests", tags=["Admin"])
def list_guests(wedding_id: str = Query(...), current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    # Check if user has access to this wedding
    if not check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")
    try:
        return guest_service.list_guests_by_wedding(wedding_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Unexpected error occurred")

@router.put("/guests/{guest_id}", tags=["Admin"])
def update_guest(guest_id: str, update_data: dict, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    # Get guest to check wedding access
    guest = guest_service.get_guest(guest_id)
    if not check_wedding_access(current_user, guest.get("wedding_id")):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")
    try:
        return guest_service.update_guest(guest_id, update_data)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Unexpected error occurred")

@router.delete("/guests/{guest_id}", tags=["Admin"])
def delete_guest(guest_id: str, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    # Get guest to check wedding access
    guest = guest_service.get_guest(guest_id)
    if not check_wedding_access(current_user, guest.get("wedding_id")):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")
    try:
        return guest_service.delete_guest(guest_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Unexpected error occurred")