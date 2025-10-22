from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from app.dependencies.auth_extended import require_root_admin, require_admin_or_planner, ExtendedAuthUser
from app.services.user_management_service import UserManagementService
from app.models.user_extended import UserModel
from pydantic import BaseModel, validator, EmailStr

router = APIRouter()
user_service = UserManagementService()

class UserInviteModel(BaseModel):
    email: str
    role: str  # wedding_planner, vendor
    company_name: Optional[str] = None
    subscription_plan_id: Optional[str] = None
    service_type: Optional[str] = None  # For vendors
    assigned_wedding_ids: List[str] = []  # For vendors

class UserUpdateModel(BaseModel):
    company_name: Optional[str] = None
    subscription_plan_id: Optional[str] = None
    subscription_status: Optional[str] = None
    max_weddings: Optional[int] = None
    is_active: Optional[bool] = None
    role: Optional[str] = None

class AccountSetupModel(BaseModel):
    token: str
    password: str
    confirm_password: str
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one number')
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v):
            raise ValueError('Password must contain at least one special character')
        return v
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v

class PublicRegistrationModel(BaseModel):
    email: str
    password: str
    first_name: str
    last_name: str
    company_name: str
    selected_plan_id: Optional[str] = None
    role: str = "wedding_planner"
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one number')
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v):
            raise ValueError('Password must contain at least one special character')
        return v

class ChangePasswordModel(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str
    
    @validator('new_password')
    def validate_new_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one number')
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v):
            raise ValueError('Password must contain at least one special character')
        return v
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v

class ChangeEmailModel(BaseModel):
    new_email: EmailStr
    password: str  # Require password confirmation for email changes

class ProfileInfoModel(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company_name: Optional[str] = None
    phone: Optional[str] = None

@router.post("/users/invite", tags=["ROOT_ADMIN"])
def invite_user(invite_data: UserInviteModel, current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Invite a new user to the platform - ROOT_ADMIN only"""
    return user_service.invite_user(invite_data.dict(), current_user.email)

@router.get("/users", tags=["ROOT_ADMIN"])
def list_users(role: Optional[str] = None, current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """List all users with optional role filter - ROOT_ADMIN only"""
    return user_service.list_users(role_filter=role)

@router.get("/users/{user_id}", tags=["ROOT_ADMIN"])
def get_user(user_id: str, current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Get user details - ROOT_ADMIN only"""
    return user_service.get_user(user_id)

@router.put("/users/{user_id}", tags=["ROOT_ADMIN"])
def update_user(user_id: str, update_data: UserUpdateModel, current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Update user details - ROOT_ADMIN only"""
    return user_service.update_user(user_id, update_data.dict(exclude_unset=True))

@router.delete("/users/{user_id}", tags=["ROOT_ADMIN"])
def delete_user(user_id: str, current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Delete user - ROOT_ADMIN only"""
    return user_service.delete_user(user_id)

@router.post("/users/{user_id}/assign-wedding", tags=["ROOT_ADMIN"])
def assign_wedding_to_planner(user_id: str, wedding_id: str, current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Assign a wedding to a planner - ROOT_ADMIN only"""
    return user_service.assign_wedding_to_planner(user_id, wedding_id)

@router.delete("/users/{user_id}/unassign-wedding/{wedding_id}", tags=["ROOT_ADMIN"])
def unassign_wedding_from_planner(user_id: str, wedding_id: str, current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Unassign a wedding from a planner - ROOT_ADMIN only"""
    return user_service.unassign_wedding_from_planner(user_id, wedding_id)

@router.post("/users/{user_id}/suspend", tags=["ROOT_ADMIN"])
def suspend_user(user_id: str, current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Suspend a user account - ROOT_ADMIN only"""
    return user_service.suspend_user(user_id)

@router.post("/users/{user_id}/activate", tags=["ROOT_ADMIN"])
def activate_user(user_id: str, current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Activate a user account - ROOT_ADMIN only"""
    return user_service.activate_user(user_id)

# ==================== PUBLIC ACCOUNT SETUP ENDPOINTS ====================

@router.get("/setup/validate-token/{token}", tags=["Public"])
def validate_invitation_token(token: str):
    """Validate invitation token and return invitation details - No auth required"""
    return user_service.validate_invitation_token(token)

@router.post("/setup/complete", tags=["Public"])
def complete_account_setup(setup_data: AccountSetupModel):
    """Complete account setup with password - No auth required"""
    return user_service.complete_account_setup(setup_data.token, setup_data.password)

@router.post("/public/register", tags=["Public"])
def register_wedding_planner(registration_data: PublicRegistrationModel):
    """Public registration for wedding planners - No auth required"""
    return user_service.register_wedding_planner(registration_data.dict())

@router.get("/verify-email/{token}", tags=["Public"])
def verify_email(token: str):
    """Verify email address using token - No auth required"""
    return user_service.verify_email(token)

@router.get("/verify-email-change/{token}", tags=["Public"])
async def verify_email_change(token: str):
    """Verify email address change using token - No auth required"""
    return await user_service.verify_email_change(token)

# ==================== USER PROFILE MANAGEMENT ====================

@router.put("/profile/password", tags=["Profile"])
async def change_password(password_data: ChangePasswordModel, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    """Change user password - Authenticated users only"""
    return await user_service.change_password(
        current_user.email, 
        password_data.current_password, 
        password_data.new_password
    )

@router.put("/profile/email", tags=["Profile"])
async def change_email(email_data: ChangeEmailModel, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    """Change user email address - Authenticated users only"""
    return await user_service.change_email(
        current_user.email, 
        email_data.new_email, 
        email_data.password
    )

@router.get("/profile", tags=["Profile"])
def get_user_profile(current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    """Get current user profile information"""
    return user_service.get_user_profile(current_user.email)

@router.put("/profile/info", tags=["Profile"])
async def update_profile_info(profile_data: ProfileInfoModel, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    """Update user profile information - Authenticated users only"""
    return await user_service.update_profile_info(
        current_user.email,
        profile_data.dict(exclude_unset=True)
    )