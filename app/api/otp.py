# app/api/otp.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.otp_service import OTPService
import logging

logger = logging.getLogger(__name__)

router = APIRouter()
otp_service = OTPService()


class OTPRequest(BaseModel):
    guest_id: str


class OTPRequestByContact(BaseModel):
    wedding_id: str
    contact: str  # phone or email


class OTPVerify(BaseModel):
    guest_id: str
    otp: str


@router.post("/otp/request", tags=["OTP"])
async def request_otp(payload: OTPRequest):
    """Request an OTP for a guest by guest_id."""
    result = await otp_service.send_otp(payload.guest_id)
    if not result.get("success"):
        error = result.get("error", "Failed to send OTP")
        # Use 400 for client errors (no phone/email, rate limit), 500 for server errors
        status_code = 400 if "contact" in error.lower() or "phone" in error.lower() or "wait" in error.lower() else 500
        raise HTTPException(status_code=status_code, detail=error)
    return {
        "message": "OTP sent successfully",
        "contact_type": result.get("contact_type", "phone")
    }


@router.post("/otp/send-by-contact", tags=["OTP"])
async def send_otp_by_contact(payload: OTPRequestByContact):
    """Send OTP to a guest by their contact info (phone/email) and wedding_id."""
    try:
        result = await otp_service.send_otp_by_contact(
            wedding_id=payload.wedding_id,
            contact=payload.contact
        )

        if not result.get("success"):
            error = result.get("error", "Failed to send OTP")
            logger.warning(f"OTP send failed: {error}")
            raise HTTPException(status_code=400, detail=error)

        return {
            "success": True,
            "message": "OTP sent successfully",
            "contact_type": result.get("contact_type", "unknown")
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending OTP by contact: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send OTP: {str(e)}")


@router.post("/otp/verify", tags=["OTP"])
async def verify_otp_endpoint(payload: OTPVerify):
    """Verify an OTP for a guest by guest_id. Returns guest data on success."""
    result = await otp_service.verify_otp_by_guest_id(payload.guest_id, payload.otp)
    if not result.get("success"):
        error = result.get("error", "Invalid or expired OTP")
        raise HTTPException(status_code=400, detail=error)
    return {
        "message": "OTP verified successfully",
        "guest": result.get("guest"),
        "auth_method": result.get("auth_method", "phone_otp")
    }
