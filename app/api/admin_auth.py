from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from app.models.admin_user import AdminLoginModel
from app.services.auth_service import AuthService
from app.dependencies.auth_extended import get_current_user_extended, ExtendedAuthUser
from app.utils.serializers import serialize_mongo_doc

router = APIRouter()

auth_service = AuthService()

@router.options("/token", tags=["Auth"])
def login_options():
    """Handle CORS preflight for login endpoint"""
    return {"message": "OK"}

@router.post("/token", tags=["Auth"])
def login_for_access_token(credentials: AdminLoginModel):
    return auth_service.login_and_get_token(credentials.email, credentials.password)

@router.get("/profile", tags=["Auth"])
def get_current_user_profile(current_user: ExtendedAuthUser = Depends(get_current_user_extended)):
    """Get current user profile information with cache-busting headers"""
    profile_data = {
        "email": current_user.email,
        "role": current_user.role,
        "is_root_admin": current_user.is_root_admin,
        "is_wedding_planner": current_user.is_wedding_planner,
        "is_vendor": current_user.is_vendor,
        "user_data": serialize_mongo_doc(current_user.user_data)
    }
    
    # Add cache-busting headers to prevent browser caching of user profile data
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate, private",
        "Pragma": "no-cache",
        "Expires": "0",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY"
    }
    
    return JSONResponse(content=profile_data, headers=headers)