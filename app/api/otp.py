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
        error_code = result.get("error_code", "unknown")

        # Map error codes to appropriate HTTP status codes
        status_map = {
            "rate_limited": 429,
            "invalid_input": 400,
            "guest_not_found": 404,
            "no_contact": 400,
            "invalid_number": 400,
            "number_blocked": 400,
            "daily_limit": 429,
            "not_configured": 503,
            "service_unavailable": 503,
            "network_error": 503,
            "auth_error": 503,
            "all_channels_failed": 503,
            "generation_failed": 500,
            "send_failed": 500,
        }
        status_code = status_map.get(error_code, 500)

        # Include retry_after in response if available
        detail = {
            "message": error,
            "error_code": error_code,
        }
        if result.get("retry_after"):
            detail["retry_after"] = result["retry_after"]

        raise HTTPException(status_code=status_code, detail=detail)

    # Build success response
    response = {
        "message": "OTP sent successfully",
        "contact_type": result.get("contact_type", "phone"),
    }

    # Tell the frontend if email fallback was used (so it can show the right message)
    if result.get("fallback_used"):
        response["fallback_used"] = True
        response["message"] = "We couldn't text you, so we sent your code by email instead."

    return response


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
