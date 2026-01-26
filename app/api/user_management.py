from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from typing import List, Optional
from app.dependencies.auth_extended import require_root_admin, require_admin_or_planner, ExtendedAuthUser
from app.services.user_management_service import UserManagementService
from app.services.gallery_upload_service import GalleryUploadService
from pydantic import BaseModel, Field, validator, EmailStr
from typing import Dict
import os

router = APIRouter()
user_service = UserManagementService()
gallery_service = GalleryUploadService()


class UserInviteModel(BaseModel):
    email: str
    role: str  # wedding_planner, vendor
    company_name: Optional[str] = None
    plan_id: Optional[str] = None
    service_type: Optional[str] = None  # For vendors
    assigned_wedding_ids: List[str] = []  # For vendors

    # Trial configuration (Option B: Full Stripe Integration)
    trial_days: int = Field(
        default=0,
        ge=0,
        le=730,  # Stripe max trial is 730 days (2 years)
        description="Trial period in days. 0 = no trial, user must pay immediately."
    )
    trial_end_behavior: str = Field(
        default="pause",
        description="What happens when trial ends without payment method: 'pause' or 'cancel'"
    )
    admin_notes: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Internal notes about this invitation (not shown to user)"
    )

    @validator('trial_end_behavior')
    def validate_trial_end_behavior(cls, v):
        if v not in ('pause', 'cancel'):
            raise ValueError("trial_end_behavior must be 'pause' or 'cancel'")
        return v


class UserUpdateModel(BaseModel):
    company_name: Optional[str] = None
    plan_id: Optional[str] = None
    subscription_status: Optional[str] = None
    max_weddings: Optional[int] = None
    is_active: Optional[bool] = None
    role: Optional[str] = None


class AccountSetupModel(BaseModel):
    token: str
    password: str
    confirm_password: str
    first_name: str = Field(..., min_length=1, max_length=100, description="User's first name")
    last_name: str = Field(..., min_length=1, max_length=100, description="User's last name")

    @validator('first_name', 'last_name')
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError('Name cannot be empty')
        return v.strip()

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
    support_phone: Optional[str] = None  # Phone number guests see when they text HELP
    push_notifications_enabled: Optional[bool] = None  # Enable/disable push notifications



@router.post("/users/invite", tags=["ROOT_ADMIN"])
async def invite_user(invite_data: UserInviteModel, current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Invite a new user to the platform - ROOT_ADMIN only"""
    return await user_service.invite_user(invite_data.dict(), current_user.email)


@router.get("/users", tags=["ROOT_ADMIN"])
async def list_users(role: Optional[str] = None, current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """List all users with optional role filter - ROOT_ADMIN only"""
    return await user_service.list_users(role_filter=role)


@router.get("/users/{user_id}", tags=["ROOT_ADMIN"])
async def get_user(user_id: str, current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Get user details - ROOT_ADMIN only"""
    return await user_service.get_user(user_id)


@router.put("/users/{user_id}", tags=["ROOT_ADMIN"])
async def update_user(user_id: str, update_data: UserUpdateModel, current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Update user details - ROOT_ADMIN only"""
    return await user_service.update_user(user_id, update_data.dict(exclude_unset=True))


@router.delete("/users/{user_id}", tags=["ROOT_ADMIN"])
async def delete_user(user_id: str, current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Delete user - ROOT_ADMIN only"""
    return await user_service.delete_user(user_id)


@router.post("/users/{user_id}/assign-wedding", tags=["ROOT_ADMIN"])
async def assign_wedding_to_planner(user_id: str, wedding_id: str, current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Assign a wedding to a planner - ROOT_ADMIN only"""
    return await user_service.assign_wedding_to_planner(user_id, wedding_id)


@router.delete("/users/{user_id}/unassign-wedding/{wedding_id}", tags=["ROOT_ADMIN"])
async def unassign_wedding_from_planner(user_id: str, wedding_id: str, current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Unassign a wedding from a planner - ROOT_ADMIN only"""
    return await user_service.unassign_wedding_from_planner(user_id, wedding_id)


@router.post("/users/{user_id}/suspend", tags=["ROOT_ADMIN"])
async def suspend_user(user_id: str, current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Suspend a user account - ROOT_ADMIN only"""
    return await user_service.suspend_user(user_id)


@router.post("/users/{user_id}/activate", tags=["ROOT_ADMIN"])
async def activate_user(user_id: str, current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Activate a user account - ROOT_ADMIN only"""
    return await user_service.activate_user(user_id)


# ==================== INVITATION MANAGEMENT ENDPOINTS ====================


@router.get("/admin/invitations", tags=["ROOT_ADMIN"])
async def list_invitations(
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """
    List all invitations with optional filtering - ROOT_ADMIN only

    Args:
        status: Filter by status (pending, completed, expired, cancelled)
        page: Page number (default 1)
        limit: Items per page (default 20)
    """
    return await user_service.list_invitations(status=status, page=page, limit=limit)


@router.get("/admin/invitations/stats", tags=["ROOT_ADMIN"])
async def get_invitation_stats(current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Get invitation counts by status - ROOT_ADMIN only"""
    return await user_service.get_invitation_stats()


@router.post("/admin/invitations/{invitation_id}/resend", tags=["ROOT_ADMIN"])
async def resend_invitation(
    invitation_id: str,
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """Resend invitation email with new token - ROOT_ADMIN only"""
    return await user_service.resend_invitation(invitation_id, resent_by=current_user.email)


class CancelInvitationModel(BaseModel):
    reason: Optional[str] = None


@router.post("/admin/invitations/{invitation_id}/cancel", tags=["ROOT_ADMIN"])
async def cancel_invitation(
    invitation_id: str,
    cancel_data: CancelInvitationModel = None,
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """Cancel a pending invitation - ROOT_ADMIN only"""
    reason = cancel_data.reason if cancel_data else None
    return await user_service.cancel_invitation(
        invitation_id,
        cancelled_by=current_user.email,
        reason=reason
    )


# ==================== PUBLIC ACCOUNT SETUP ENDPOINTS ====================


@router.get("/setup/validate-token/{token}", tags=["Public"])
async def validate_invitation_token(token: str):
    """Validate invitation token and return invitation details - No auth required"""
    return await user_service.validate_invitation_token(token)


@router.post("/setup/complete", tags=["Public"])
async def complete_account_setup(setup_data: AccountSetupModel):
    """Complete account setup with password and name - No auth required"""
    return await user_service.complete_account_setup(
        setup_data.token,
        setup_data.password,
        setup_data.first_name,
        setup_data.last_name
    )


@router.post("/public/register", tags=["Public"])
async def register_wedding_planner(registration_data: PublicRegistrationModel):
    """Public registration for wedding planners - No auth required"""
    return await user_service.register_wedding_planner(registration_data.dict())


@router.get("/verify-email/{token}", tags=["Public"])
async def verify_email(token: str):
    """Verify email address using token - No auth required"""
    return await user_service.verify_email(token)


@router.get("/verify-email-change/{token}", tags=["Public"])
async def verify_email_change(token: str):
    """Verify email address change using token - No auth required"""
    return await user_service.verify_email_change(token)


# ==================== PASSWORD RESET ENDPOINTS ====================


class ForgotPasswordModel(BaseModel):
    email: EmailStr


class ResetPasswordModel(BaseModel):
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


@router.post("/forgot-password", tags=["Public"])
async def forgot_password(data: ForgotPasswordModel):
    """Request a password reset email - No auth required"""
    return await user_service.request_password_reset(data.email)


@router.get("/reset-password/validate/{token}", tags=["Public"])
async def validate_reset_token(token: str):
    """Validate a password reset token - No auth required"""
    return await user_service.validate_password_reset_token(token)


@router.post("/reset-password", tags=["Public"])
async def reset_password(data: ResetPasswordModel):
    """Reset password using reset token - No auth required"""
    return await user_service.reset_password(data.token, data.password)


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
async def get_user_profile(current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    """Get current user profile information"""
    return await user_service.get_user_profile(current_user.email)


@router.put("/profile/info", tags=["Profile"])
async def update_profile_info(profile_data: ProfileInfoModel, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    """Update user profile information - Authenticated users only"""
    return await user_service.update_profile_info(
        current_user.email,
        profile_data.dict(exclude_unset=True)
    )


@router.post("/profile/image", tags=["Profile"])
async def upload_profile_image(
    file: UploadFile = File(...),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Upload a profile image for the current user"""
    import os
    from datetime import datetime

    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: {', '.join(allowed_types)}"
        )

    # Validate file size (max 5MB)
    file_size = 0
    chunk_size = 1024 * 1024  # 1MB chunks
    content = b""
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        file_size += len(chunk)
        content += chunk
        if file_size > 5 * 1024 * 1024:  # 5MB
            raise HTTPException(status_code=400, detail="File size exceeds 5MB limit")

    # Reset file position for upload
    from io import BytesIO
    file.file = BytesIO(content)

    # Generate unique filename using user ID
    user_id = current_user.user_data.get("_id", current_user.email.replace("@", "_at_"))
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    ext = os.path.splitext(file.filename or "image.jpg")[1] or ".jpg"
    key = f"profile-images/{user_id}/{timestamp}{ext}"

    # Upload to S3/R2
    try:
        gallery_service.s3.upload_fileobj(
            file.file,
            gallery_service.bucket_name,
            key,
            ExtraArgs={"ContentType": file.content_type}
        )

        # Generate the public URL
        custom_domain = os.getenv("MEDIA_DOMAIN")
        if not custom_domain:
            raise HTTPException(status_code=500, detail="MEDIA_DOMAIN environment variable is not configured")
        # Ensure URL has https:// prefix
        if not custom_domain.startswith(('http://', 'https://')):
            custom_domain = f"https://{custom_domain}"
        image_url = f"{custom_domain}/{key}"

        # Update user profile with new image URL
        await user_service.update_profile_info(
            current_user.email,
            {"profile_image_url": image_url}
        )

        return {
            "message": "Profile image uploaded successfully",
            "profile_image_url": image_url
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload image: {str(e)}")


@router.delete("/profile/image", tags=["Profile"])
async def delete_profile_image(current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    """Delete the current user's profile image"""
    # Get current profile image URL
    user_profile = await user_service.get_user_profile(current_user.email)
    current_image = user_profile.get("profile_image_url") if user_profile else None

    if current_image:
        # Extract key from URL
        custom_domain = os.getenv("MEDIA_DOMAIN")
        if custom_domain:
            # Ensure URL comparison accounts for https:// prefix
            if not custom_domain.startswith(('http://', 'https://')):
                custom_domain = f"https://{custom_domain}"
            if current_image.startswith(custom_domain):
                key = current_image.replace(f"{custom_domain}/", "")
                try:
                    gallery_service.s3.delete_object(
                        Bucket=gallery_service.bucket_name,
                        Key=key
                    )
                except Exception:
                    pass  # Ignore deletion errors

    # Update user profile to remove image URL
    await user_service.update_profile_info(
        current_user.email,
        {"profile_image_url": None}
    )

    return {"message": "Profile image deleted successfully"}
