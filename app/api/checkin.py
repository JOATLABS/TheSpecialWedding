from fastapi import APIRouter, Depends, HTTPException
from app.services.checkin_service import CheckInService
from app.dependencies.auth import require_admin, get_current_admin

router = APIRouter()

checkin_service = CheckInService()

@router.post("/checkin/{token}", tags=["Admin"], dependencies=[Depends(require_admin)])
def check_in_guest(token: str, admin_email: str = Depends(get_current_admin)):
    return checkin_service.check_in_guest(token, admin_email)

@router.get("/checkin/status/{token}", tags=["Admin"], dependencies=[Depends(require_admin)])
def check_in_status(token: str):
    return checkin_service.check_in_status(token)