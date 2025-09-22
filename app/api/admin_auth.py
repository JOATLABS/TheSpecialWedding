from fastapi import APIRouter, HTTPException, Depends, Response
from fastapi.responses import JSONResponse
from app.models.admin_user import AdminLoginModel
from app.services.auth_service import AuthService
from app.core.settings import get_settings
from app.dependencies.auth_extended import get_current_user_extended, ExtendedAuthUser
from app.utils.serializers import serialize_mongo_doc
from datetime import datetime, timedelta

router = APIRouter()

auth_service = AuthService()

@router.options("/token", tags=["Auth"])
def login_options():
    """Handle CORS preflight for login endpoint"""
    return {"message": "OK"}

@router.post("/token", tags=["Auth"])
def login_for_access_token(credentials: AdminLoginModel, response: Response):
    # Get the token data from the auth service
    token_data = auth_service.login_and_get_token(credentials.email, credentials.password)

    # TWO-COOKIE PATTERN for secure authentication:

    # 1. Set httpOnly cookie for the actual token (secure, not readable by JS)
    # Fetch settings at runtime to respect patched values in tests and dynamic env changes
    settings = get_settings()
    secure_flag = settings.is_production()
    # Use Strict for auth token cookie to reduce CSRF risk (frontend flows should handle redirects/forms appropriately)
    response.set_cookie(
        key="admin_token",
        value=token_data["access_token"],
        max_age=604800,  # 7 days
        httponly=True,
        samesite="strict",  # tighten in production
        secure=secure_flag,
        path="/"
    )

    # 2. Set client-readable cookie for auth state (no sensitive data)
    # This allows the client to know if user is authenticated without exposing token
    response.set_cookie(
        key="admin_authenticated",
        value="true",
        max_age=604800,
        httponly=False,
        samesite="lax",  # keep Lax for UX (navigation) while token cookie is Strict
        secure=secure_flag,
        path="/"
    )

    return token_data

@router.post("/logout", tags=["Auth"])
def logout(response: Response):
    """Clear both authentication cookies (two-cookie pattern)"""
    # Clear the httpOnly token cookie
    response.delete_cookie(key="admin_token", path="/")
    # Clear the client-readable auth state cookie
    response.delete_cookie(key="admin_authenticated", path="/")
    return {"message": "Logged out successfully"}

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