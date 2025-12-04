from fastapi import APIRouter, Depends, HTTPException, Query
from app.services.plus_one_service import PlusOneService
from app.services.auth_service import get_current_user_id, get_current_user, require_admin_auth
import logging

router = APIRouter(prefix="/admin/plus_ones", tags=["Admin"])
plus_one_service = PlusOneService()

@router.get("", dependencies=[Depends(require_admin_auth)])
def get_plus_ones_for_wedding(wedding_id: str = Query(...)):
    """
    Get all plus-ones for a specific wedding.
    - wedding_id (str): The ID of the wedding to fetch plus-ones for.
    - Returns: A list of plus-one objects.
    """
    try:
        plus_ones = plus_one_service.get_plus_ones_by_wedding_id(wedding_id)
        return plus_ones
    except Exception as e:
        logging.error(f"Error fetching plus ones for wedding {wedding_id}: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")
