from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Optional, Literal
from pydantic import BaseModel, Field
from app.services.guest_verification_service import GuestVerificationService
from app.dependencies.auth_extended import require_admin_or_planner, ExtendedAuthUser, check_wedding_access

router = APIRouter()
verification_service = GuestVerificationService()


class GuestVerificationRequest(BaseModel):
    token: Optional[str] = Field(None, description="Guest invitation token")
    name: Optional[str] = Field(None, description="Guest name for verification")
    phone: Optional[str] = Field(None, description="Guest phone number for verification")
    email: Optional[str] = Field(None, description="Guest email for verification")
    password: Optional[str] = Field(None, description="Password for password-protected weddings")
    otp_code: Optional[str] = Field(None, description="OTP verification code")
    contact: Optional[str] = Field(None, description="Contact (phone/email) for OTP verification")


class PrivacySettingsUpdate(BaseModel):
    privacy_mode: str = Field(..., description="Privacy mode: public, password, private")
    guest_auth_required: bool = Field(default=True)
    password_protection: Optional[str] = Field(None, description="Password for password mode")
    allow_guest_sharing: bool = Field(default=False)
    require_phone_verification: bool = Field(default=True)
    require_name_verification: bool = Field(default=True)


class RequestRSVPLinkRequest(BaseModel):
    """Request model for guest RSVP link request."""
    slug: str = Field(..., description="Wedding slug")
    contact: str = Field(..., description="Phone number or email address")
    contact_type: Literal["phone", "email"] = Field(..., description="Type of contact: phone or email")


@router.post("/weddings/verify-guest-access/{slug}", tags=["Guest"])
async def verify_guest_access(slug: str, verification: GuestVerificationRequest):
    """
    Verify visitor access to view a wedding page based on privacy settings.

    Privacy modes:
    - public: Anyone can view
    - password: Anyone with the correct password can view
    - private: ONLY guests on the guest list can view. They must:
      1. Enter their phone/email (must match a guest record for this wedding)
      2. Receive OTP to that contact via SMS/email
      3. Verify OTP to prove they control that contact

    For RSVP with invite token, use GET /weddings/guest-access/{slug}/{token} instead.
    """
    try:
        result = await verification_service.verify_wedding_page_access(
            slug=slug,
            verification_data=verification.dict()
        )

        if not result.get("access"):
            # Check if OTP is required - if so, return the response (not an error)
            if result.get("otp_required"):
                return result

            # Otherwise, access is denied
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
async def get_wedding_privacy_info(slug: str):
    """
    Get privacy information about a wedding without granting access.
    Used to show appropriate authentication form to guests.
    """
    try:
        return await verification_service.get_wedding_privacy_info(slug)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting privacy info: {str(e)}")


@router.get("/weddings/guest-access/{slug}/{token}", tags=["Guest"])
async def get_wedding_with_token_access(slug: str, token: str):
    """
    Get wedding and guest data using invite token.

    Used by RSVP flow after OTP verification.
    The token is the authorization - no privacy checks needed.
    Guest received a personalized invite link with this token.
    """
    try:
        # Use direct token lookup - no privacy checks needed
        result = await verification_service.get_rsvp_access_by_token(slug, token)

        if not result.get("access"):
            raise HTTPException(status_code=403, detail="Invalid guest token")

        return {
            "wedding": result["wedding"],
            "guest": result.get("guest"),
            "rsvp": result.get("rsvp")  # Include existing RSVP data if guest already submitted
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Token verification error: {str(e)}")


@router.post("/guests/request-rsvp-link", tags=["Guest"])
async def request_rsvp_link(
    request_data: RequestRSVPLinkRequest,
    http_request: Request
):
    """
    Request personal RSVP link to be sent via SMS or email.

    This endpoint allows guests who have lost their invitation link to
    request it again by providing their phone number or email address.

    Security features:
    - Rate limited (3 requests per contact per 10 minutes)
    - Always returns success to prevent guest enumeration
    - Only sends to the provided contact method (no cross-channel leakage)
    - Logged for security auditing

    Returns:
        Generic success message regardless of whether guest was found
    """
    try:
        # Get client IP for rate limiting
        client_ip = http_request.client.host if http_request.client else "unknown"

        result = await verification_service.request_and_send_rsvp_link(
            slug=request_data.slug,
            contact=request_data.contact,
            contact_type=request_data.contact_type,
            client_ip=client_ip
        )

        return result

    except Exception as e:
        # Even on errors, return generic success to prevent enumeration
        return {
            "success": True,
            "message": "If you're on the guest list, you'll receive your RSVP link shortly."
        }


@router.put("/weddings/{wedding_id}/privacy-settings", tags=["Admin"])
async def update_wedding_privacy_settings(
    wedding_id: str,
    privacy_settings: PrivacySettingsUpdate,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Update privacy settings for a wedding - Admin only
    """
    # Check if user has access to this wedding
    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")
    try:
        return await verification_service.update_wedding_privacy_settings(
            wedding_id=wedding_id,
            privacy_settings=privacy_settings.dict()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating privacy settings: {str(e)}")


@router.get("/weddings/{wedding_id}/access-logs", tags=["Admin"])
async def get_wedding_access_logs(
    wedding_id: str,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Get access logs for a wedding - Admin only
    """
    # Check if user has access to this wedding
    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")
    try:
        from app.core.database import mongo
        logs = await mongo.db["access_logs"].find(
            {"wedding_id": wedding_id},
            {"_id": 0}
        ).sort("timestamp", -1).limit(100).to_list(length=100)

        return {"logs": logs}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting access logs: {str(e)}")
