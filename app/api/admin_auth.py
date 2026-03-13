from datetime import timedelta

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from app.models.admin_user import AdminLoginModel
from app.services.auth_service import AuthService
from app.dependencies.auth_extended import get_current_user_extended, ExtendedAuthUser
from app.utils.auth_utils import create_access_token
from app.utils.serializers import serialize_mongo_doc
from app.utils.response import dict_response

router = APIRouter()
auth_service = AuthService()


@router.options("/token", tags=["Auth"])
def login_options():
    """Handle CORS preflight for login endpoint"""
    return dict_response(message="OK")


@router.post("/token", tags=["Auth"])
async def login_for_access_token(credentials: AdminLoginModel):
    return await auth_service.login_and_get_token(credentials.email, credentials.password)


@router.post("/token/refresh", tags=["Auth"])
async def refresh_access_token(current_user: ExtendedAuthUser = Depends(get_current_user_extended)):
    """Issue a fresh JWT for an already-authenticated user.

    The caller must present a valid (non-expired) Bearer token. A new token is
    returned with a fresh 60-minute expiry window. This keeps the session alive
    without requiring the user to re-enter credentials, and prevents the SSE
    notification stream from hitting 401s when the original JWT expires.
    """
    token_data = {"sub": current_user.email, "role": current_user.role}
    access_token_expires = timedelta(minutes=60)
    new_token = create_access_token(data=token_data, expires_delta=access_token_expires)
    return {"access_token": new_token, "token_type": "bearer"}


@router.get("/profile", tags=["Auth"])
async def get_current_user_profile(current_user: ExtendedAuthUser = Depends(get_current_user_extended)):
    """Get current user profile information with cache-busting headers"""
    # Serialize user_data first to handle all datetime and ObjectId fields recursively
    serialized_user_data = serialize_mongo_doc(current_user.user_data) or {}
    profile_data = {
        "email": current_user.email,
        "role": current_user.role,
        "is_root_admin": current_user.is_root_admin,
        "is_wedding_planner": current_user.is_wedding_planner,
        "is_vendor": current_user.is_vendor,
        "is_team_member": current_user.is_team_member,
        # Expose profile fields at top level for easier frontend access
        "first_name": serialized_user_data.get("first_name"),
        "last_name": serialized_user_data.get("last_name"),
        "company_name": serialized_user_data.get("company_name"),
        "profile_image_url": serialized_user_data.get("profile_image_url"),
        "push_notifications_enabled": serialized_user_data.get("push_notifications_enabled", True),  # Default to True
        "timezone": serialized_user_data.get("timezone", "America/Chicago"),  # IANA timezone for display
        "onboarding_completed": serialized_user_data.get("onboarding_completed", False),
        "onboarding_completed_at": serialized_user_data.get("onboarding_completed_at"),
        "onboarding_steps_completed": serialized_user_data.get("onboarding_steps_completed", []),
        "user_data": serialized_user_data
    }
    # Add team member context if applicable
    if current_user.is_team_member:
        profile_data["team_permissions"] = current_user.team_permissions or {}
        profile_data["team_wedding_access"] = current_user.team_wedding_access
        profile_data["team_assigned_wedding_ids"] = current_user.team_assigned_wedding_ids
        profile_data["parent_planner_id"] = current_user.parent_planner_id
    # Add cache-busting headers to prevent browser caching of user profile data
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate, private",
        "Pragma": "no-cache",
        "Expires": "0",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY"
    }
    return JSONResponse(content=profile_data, headers=headers)
