from fastapi import APIRouter, HTTPException, Path, Body
from app.models.plus_one import PlusOneModel
from app.services.plus_one_service import PlusOneService

router = APIRouter()

plus_one_service = PlusOneService()

@router.post("/plus-ones", tags=["Plus-Ones"])
def add_plus_one(plus_one: PlusOneModel):
    return plus_one_service.add_plus_one(plus_one)

@router.get("/plus-ones/{guest_id}", tags=["Plus-Ones"])
def get_plus_ones(guest_id: str):
    return plus_one_service.get_plus_ones_by_guest(guest_id)

@router.put("/plus-ones/{plus_one_id}", tags=["Plus-Ones"])
def update_plus_one(plus_one_id: str = Path(...), data: dict = Body(...)):
    return plus_one_service.update_plus_one(plus_one_id, data)

@router.delete("/plus-ones/{plus_one_id}", tags=["Plus-Ones"])
def delete_plus_one(plus_one_id: str):
    return plus_one_service.delete_plus_one(plus_one_id)