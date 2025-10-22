from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from pydantic import BaseModel, Field
from app.services.guest_verification_service import GuestVerificationService
from app.dependencies.auth_extended import require_admin_or_planner, ExtendedAuthUser, check_wedding_access

router = APIRouter()
verification_service = GuestVerificationService()

class GuestVerificationRequest(BaseModel):
    token: Optional[str] = Field(None, description="Guest invitation token")
    name: Optional[str] = Field(None, description="Guest name for verification")
    phone: Optional[str] = Field(None, description="Guest phone number for verification")
    password: Optional[str] = Field(None, description="Password for password-protected weddings")

class PrivacySettingsUpdate(BaseModel):
    privacy_mode: str = Field(..., description="Privacy mode: public, password, private")
    guest_auth_required: bool = Field(default=True)
    password_protection: Optional[str] = Field(None, description="Password for password mode")
    allow_guest_sharing: bool = Field(default=False)
    require_phone_verification: bool = Field(default=True)
    require_name_verification: bool = Field(default=True)

@router.post("/weddings/verify-guest-access/{slug}", tags=["Guest"])
def verify_guest_access(slug: str, verification: GuestVerificationRequest):
    """
    Verify guest access to a wedding using various authentication methods.
    Returns wedding data if access is granted.
    """
    try:
        result = verification_service.verify_guest_access(
            slug=slug, 
            verification_data=verification.dict()
        )
        
        if not result.get("access"):
            raise HTTPException(
                status_code=403, 
                detail="Guest verification failed",
                headers={"X-Auth-Required": result.get("required_auth", "private")}
            )
        
        return {
            "access": True,
            "wedding": result["wedding"],
            "guest": result.get("guest"),
            "auth_method": result.get("auth_method")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification error: {str(e)}")

@router.get("/weddings/privacy-info/{slug}", tags=["Guest"])
def get_wedding_privacy_info(slug: str):
    """
    Get privacy information about a wedding without granting access.
    Used to show appropriate authentication form to guests.
    """
    try:
        return verification_service.get_wedding_privacy_info(slug)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting privacy info: {str(e)}")

@router.get("/weddings/guest-access/{slug}/{token}", tags=["Guest"])
def get_wedding_with_token_access(slug: str, token: str):
    """
    Get wedding details using token-based authentication.
    This is for direct token-based access (legacy support).
    """
    try:
        result = verification_service.verify_guest_access(
            slug=slug,
            verification_data={"token": token}
        )
        
        if not result.get("access"):
            raise HTTPException(status_code=403, detail="Invalid guest token")
        
        return {
            "wedding": result["wedding"],
            "guest": result.get("guest")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Token verification error: {str(e)}")

@router.put("/weddings/{wedding_id}/privacy-settings", tags=["Admin"])
def update_wedding_privacy_settings(
    wedding_id: str, 
    privacy_settings: PrivacySettingsUpdate,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Update privacy settings for a wedding - Admin only
    """
    # Check if user has access to this wedding
    if not check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")
    
    try:
        return verification_service.update_wedding_privacy_settings(
            wedding_id=wedding_id,
            privacy_settings=privacy_settings.dict()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating privacy settings: {str(e)}")

@router.get("/weddings/{wedding_id}/access-logs", tags=["Admin"])
def get_wedding_access_logs(
    wedding_id: str,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Get access logs for a wedding - Admin only
    """
    # Check if user has access to this wedding
    if not check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")
    
    try:
        from app.core.database import mongo
        logs = list(mongo.db["access_logs"].find(
            {"wedding_id": wedding_id},
            {"_id": 0}
        ).sort("timestamp", -1).limit(100))
        
        return {"logs": logs}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting access logs: {str(e)}")