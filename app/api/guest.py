from fastapi import APIRouter, Depends, HTTPException, Query
import inspect
from app.services.guest_service import GuestService
from app.models.guest import UpdateGuestRequest, GuestModel, CreateGuestRequest
from app.dependencies.auth_extended import require_wedding_planner_only, ExtendedAuthUser, check_wedding_access
from app.utils.token_generator import generate_token

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
async def search_guest(
    wedding_id: str = Query(..., description="Wedding ID to search within"),
    phone: str = Query(None, description="Guest phone number"),
    name: str = Query(None, description="Guest name"),
    current_user: ExtendedAuthUser = Depends(require_wedding_planner_only)
):
    """
    Search for a guest by phone or name within a specific wedding.
    Requires authentication and wedding access.
    """
    # Verify user has access to this wedding
    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    try:
        return await guest_service.get_guest_by_phone_or_name(
            phone=phone,
            name=name,
            wedding_id=wedding_id
        )
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


@router.put("/guests/{guest_id}", tags=["Admin"])
async def update_guest(
    guest_id: str,
    update_data: UpdateGuestRequest,
    current_user: ExtendedAuthUser = Depends(require_wedding_planner_only)
):
    """Update guest information. Only updateable fields: name, phone, email, group_id, role, plus_one settings."""
    # Get guest to check wedding access
    guest = await guest_service.get_guest(guest_id)
    if inspect.isawaitable(guest):
        guest = await guest
    if not await check_wedding_access(current_user, guest.get("wedding_id")):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")
    try:
        # Convert Pydantic model to dict, excluding unset fields
        update_dict = update_data.model_dump(exclude_unset=True)
        return await guest_service.update_guest(guest_id, update_dict)
    except HTTPException as e:
        raise e
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Failed to update guest: {str(err)}")


@router.delete("/guests/{guest_id}", tags=["Admin"])
async def delete_guest(guest_id: str, current_user: ExtendedAuthUser = Depends(require_wedding_planner_only)):
    # Get guest to check wedding access
    guest = await guest_service.get_guest(guest_id)
    if inspect.isawaitable(guest):
        guest = await guest
    if not await check_wedding_access(current_user, guest.get("wedding_id")):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")
    try:
        return await guest_service.delete_guest(guest_id)
    except HTTPException as e:
        raise e
    except Exception:
        raise HTTPException(status_code=500, detail="Unexpected error occurred")


@router.post("/guests", tags=["Admin"])
async def create_guest(
    guest_data: CreateGuestRequest,
    wedding_id: str = Query(...),
    current_user: ExtendedAuthUser = Depends(require_wedding_planner_only)
):
    """Create a single guest for a wedding."""
    # Check if user has access to this wedding
    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")
    try:
        return await guest_service.create_guest(guest_data, wedding_id)
    except HTTPException as e:
        raise e
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Failed to create guest: {str(err)}")
