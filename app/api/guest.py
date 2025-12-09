from fastapi import APIRouter, Depends, HTTPException, Query
import inspect
from app.services.guest_service import GuestService
from app.dependencies.auth_extended import require_wedding_planner_only, ExtendedAuthUser, check_wedding_access

router = APIRouter()

guest_service = GuestService()


@router.get("/invite/{token}", tags=["Guest"])
async def get_guest(token: str, wedding_id: str = Query(...)):
    try:
        return await guest_service.get_guest_by_token(token, wedding_id)
    except HTTPException as e:
        raise e
    except Exception:
        raise HTTPException(status_code=500, detail="Unexpected error occurred")


@router.get("/invite/search", tags=["Guest"])
async def search_guest(phone: str = Query(None), name: str = Query(None)):
    try:
        return await guest_service.get_guest_by_phone_or_name(phone=phone, name=name)
    except HTTPException as e:
        raise e
    except Exception:
        raise HTTPException(status_code=500, detail="Unexpected error occurred")


@router.get("/guests", tags=["Admin"])
async def list_guests(wedding_id: str = Query(...), current_user: ExtendedAuthUser = Depends(require_wedding_planner_only)):
    # Check if user has access to this wedding
    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")
    try:
        return await guest_service.list_guests_by_wedding(wedding_id)
    except HTTPException as e:
        raise e
    except Exception:
        raise HTTPException(status_code=500, detail="Unexpected error occurred")


async def update_guest(guest_id: str, update_data: dict, current_user: ExtendedAuthUser = Depends(require_wedding_planner_only)):
    # Get guest to check wedding access
    guest = await guest_service.get_guest(guest_id)
    if inspect.isawaitable(guest):
        guest = await guest
    if not await check_wedding_access(current_user, guest.get("wedding_id")):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")
        raise HTTPException(status_code=403, detail="Access to this wedding denied")
    try:
        return await guest_service.update_guest(guest_id, update_data)
    except HTTPException as e:
        raise e
    except Exception:
        raise HTTPException(status_code=500, detail="Unexpected error occurred")


async def delete_guest(guest_id: str, current_user: ExtendedAuthUser = Depends(require_wedding_planner_only)):
    # Get guest to check wedding access
    guest = await guest_service.get_guest(guest_id)
    if inspect.isawaitable(guest):
        guest = await guest
    if not await check_wedding_access(current_user, guest.get("wedding_id")):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")
    guest = await guest_service.get_guest(guest_id)
    if not await check_wedding_access(current_user, guest.get("wedding_id")):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")
    try:
        return await guest_service.delete_guest(guest_id)
    except HTTPException as e:
        raise e
    except Exception:
        raise HTTPException(status_code=500, detail="Unexpected error occurred")
