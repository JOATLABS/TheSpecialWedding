from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from app.models.admin_user import AdminLoginModel
from app.services.auth_service import AuthService
from app.dependencies.auth_extended import get_current_user_extended, ExtendedAuthUser
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
