from fastapi import APIRouter, Depends, HTTPException
from app.services.checkin_service import CheckInService
from app.dependencies.auth_extended import require_admin_or_planner, ExtendedAuthUser

router = APIRouter()

checkin_service = CheckInService()

@router.post("/checkin/{token}", tags=["Admin"])
def check_in_guest(token: str, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    return checkin_service.check_in_guest(token, current_user.email)

@router.get("/checkin/status/{token}", tags=["Admin"])
def check_in_status(token: str, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    return checkin_service.check_in_status(token)