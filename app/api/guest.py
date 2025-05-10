from fastapi import APIRouter, Depends, HTTPException
from app.services.guest_service import GuestService

router = APIRouter()

guest_service = GuestService()

@router.get("/invite/{token}", tags=["Guest"])
def get_guest(token: str):
    try:
        return guest_service.get_guest_by_token(token)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Unexpected error occurred")