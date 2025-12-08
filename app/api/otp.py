# app/api/otp.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.otp_service import OTPService

router = APIRouter()
otp_service = OTPService()

class OTPRequest(BaseModel):
    guest_id: str

class OTPVerify(BaseModel):
    guest_id: str
    otp: str

@router.post("/otp/request", tags=["OTP"])
def request_otp(payload: OTPRequest):
    """Request an OTP for a guest."""
    success = otp_service.send_otp(payload.guest_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send OTP")
    return {"message": "OTP sent successfully"}

@router.post("/otp/verify", tags=["OTP"])
def verify_otp(payload: OTPVerify):
    """Verify an OTP for a guest."""
    success = otp_service.verify_otp(payload.guest_id, payload.otp)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    return {"message": "OTP verified successfully"}
