from fastapi import APIRouter, HTTPException, Path, Body, Depends
from app.models.plus_one import PlusOneModel
from app.services.plus_one_service import PlusOneService
from app.services.guest_service import GuestService
from app.dependencies.auth_extended import require_wedding_planner_only, ExtendedAuthUser, check_wedding_access

router = APIRouter()

plus_one_service = PlusOneService()
guest_service = GuestService()

@router.post("/plus-ones", tags=["Plus-Ones"])
async def add_plus_one(plus_one: PlusOneModel, current_user: ExtendedAuthUser = Depends(require_wedding_planner_only)):
    # Get guest to verify wedding access
    guest = guest_service.get_guest(plus_one.guest_id)
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")

    if not await check_wedding_access(current_user, guest.get("wedding_id")):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    return await plus_one_service.add_plus_one(plus_one)

@router.get("/plus-ones/{guest_id}", tags=["Plus-Ones"])
async def get_plus_ones(guest_id: str, current_user: ExtendedAuthUser = Depends(require_wedding_planner_only)):
    # Get guest to verify wedding access
    guest = guest_service.get_guest(guest_id)
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")

    if not await check_wedding_access(current_user, guest.get("wedding_id")):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    return await plus_one_service.get_plus_ones_by_guest(guest_id)

@router.put("/plus-ones/{plus_one_id}", tags=["Plus-Ones"])
async def update_plus_one(plus_one_id: str = Path(...), data: dict = Body(...), current_user: ExtendedAuthUser = Depends(require_wedding_planner_only)):
    # Get plus-one to find guest and verify wedding access
    plus_one = plus_one_service.get_plus_one(plus_one_id)
    if not plus_one:
        raise HTTPException(status_code=404, detail="Plus-one not found")

    guest = guest_service.get_guest(plus_one.get("guest_id"))
    if not guest:
        raise HTTPException(status_code=404, detail="Associated guest not found")

    if not await check_wedding_access(current_user, guest.get("wedding_id")):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    return await plus_one_service.update_plus_one(plus_one_id, data)

@router.delete("/plus-ones/{plus_one_id}", tags=["Plus-Ones"])
async def delete_plus_one(plus_one_id: str, current_user: ExtendedAuthUser = Depends(require_wedding_planner_only)):
    # Get plus-one to find guest and verify wedding access
    plus_one = plus_one_service.get_plus_one(plus_one_id)
    if not plus_one:
        raise HTTPException(status_code=404, detail="Plus-one not found")

    guest = guest_service.get_guest(plus_one.get("guest_id"))
    if not guest:
        raise HTTPException(status_code=404, detail="Associated guest not found")

    if not await check_wedding_access(current_user, guest.get("wedding_id")):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    return await plus_one_service.delete_plus_one(plus_one_id)
