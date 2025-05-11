from fastapi import APIRouter, Path, HTTPException, Body
from app.services.guest_service import GuestService
from app.models.guest import PlusOneModel

router = APIRouter()
guest_service = GuestService()

@router.post("/invite/{token}/plus-one", tags=["Plus One"])
def add_plus_one(token: str = Path(...), plus_one: PlusOneModel = Body(...)):
    """
    Add a plus-one guest to an invitation
    """
    try:
        return guest_service.add_plus_one(token, plus_one)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error occurred: {str(e)}")

@router.delete("/invite/{token}/plus-one/{index}", tags=["Plus One"])
def remove_plus_one(token: str = Path(...), index: int = Path(...)):
    """
    Remove a plus-one guest from an invitation
    """
    try:
        return guest_service.remove_plus_one(token, index)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error occurred: {str(e)}")

@router.put("/invite/{token}/plus-one/{index}", tags=["Plus One"])
def update_plus_one(token: str = Path(...), index: int = Path(...), plus_one: PlusOneModel = Body(...)):
    """
    Update a plus-one guest's information
    """
    try:
        return guest_service.update_plus_one(token, index, plus_one)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error occurred: {str(e)}")