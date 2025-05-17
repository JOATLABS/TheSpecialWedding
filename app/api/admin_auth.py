from fastapi import APIRouter, HTTPException
from app.models.admin_user import AdminLoginModel
from app.services.auth_service import AuthService

router = APIRouter()

auth_service = AuthService()

@router.post("/token", tags=["Auth"])
def login_for_access_token(credentials: AdminLoginModel):
    return auth_service.login_and_get_token(credentials.email, credentials.password)