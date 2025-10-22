from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, validator, EmailStr
from typing import Optional
from app.services.otp_service import OTPService
from app.dependencies.auth_extended import require_root_admin, ExtendedAuthUser
import re
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/otp", tags=["OTP Verification"])

class SendOTPRequest(BaseModel):
    wedding_id: str = Field(..., description="Wedding ID", min_length=1, max_length=100)
    contact: str = Field(..., description="Phone number or email", min_length=5, max_length=255)
    contact_type: str = Field(..., description="Contact type: 'phone' or 'email'", pattern="^(phone|email)$")
    
    @validator('contact')
    def validate_contact(cls, v, values):
        """Validate contact format based on type"""
        contact_type = values.get('contact_type')
        
        if contact_type == 'email':
            # Basic email validation - more thorough validation in service layer
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, v.strip()):
                raise ValueError('Invalid email format')
            return v.strip().lower()
        
        elif contact_type == 'phone':
            # Remove non-digit characters except +
            cleaned_phone = re.sub(r'[^\d+]', '', v.strip())
            
            # Validate phone number format (US and international)
            phone_pattern = r'^\+?1?[2-9]\d{2}[2-9]\d{2}\d{4}$|^\+\d{7,15}$'
            if not re.match(phone_pattern, cleaned_phone):
                raise ValueError('Invalid phone number format')
            return cleaned_phone
        
        return v.strip()
    
    @validator('wedding_id')
    def sanitize_wedding_id(cls, v):
        """Sanitize wedding ID to prevent injection"""
        # Remove any potentially dangerous characters
        sanitized = re.sub(r'[^a-zA-Z0-9_-]', '', v)
        if not sanitized:
            raise ValueError('Invalid wedding ID')
        return sanitized

class VerifyOTPRequest(BaseModel):
    wedding_id: str = Field(..., description="Wedding ID", min_length=1, max_length=100)
    contact: str = Field(..., description="Phone number or email that received OTP", min_length=5, max_length=255)
    otp_code: str = Field(..., description="6-digit OTP code", min_length=6, max_length=6, pattern="^[0-9]{6}$")
    
    @validator('otp_code')
    def validate_otp_code(cls, v):
        """Ensure OTP code is exactly 6 digits"""
        if not v.isdigit() or len(v) != 6:
            raise ValueError('OTP must be exactly 6 digits')
        return v
    
    @validator('contact')
    def sanitize_contact(cls, v):
        """Sanitize contact to prevent injection"""
        return v.strip()
    
    @validator('wedding_id')
    def sanitize_wedding_id(cls, v):
        """Sanitize wedding ID to prevent injection"""
        # Remove any potentially dangerous characters
        sanitized = re.sub(r'[^a-zA-Z0-9_-]', '', v)
        if not sanitized:
            raise ValueError('Invalid wedding ID')
        return sanitized

@router.post("/send", response_model=dict)
async def send_otp(request: SendOTPRequest):
    """
    Send OTP to a guest's phone or email for wedding access verification
    """
    try:
        # Additional security check (redundant but defense in depth)
        if request.contact_type not in ["phone", "email"]:
            raise HTTPException(
                status_code=400, 
                detail="Invalid contact type"
            )
        
        # Validate request size (defense against oversized payloads)
        if len(request.contact) > 255 or len(request.wedding_id) > 100:
            raise HTTPException(
                status_code=400,
                detail="Invalid request parameters"
            )
        
        # Initialize OTP service
        otp_service = OTPService()
        
        # Send OTP
        result = otp_service.send_otp_for_guest_verification(
            wedding_id=request.wedding_id,
            contact=request.contact,
            contact_type=request.contact_type
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending OTP: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to send verification code")

@router.post("/verify", response_model=dict)
async def verify_otp(request: VerifyOTPRequest):
    """
    Verify OTP code and grant access if valid
    """
    try:
        # Initialize OTP service
        otp_service = OTPService()
        
        # Verify OTP
        result = otp_service.verify_otp(
            wedding_id=request.wedding_id,
            contact=request.contact,
            otp_code=request.otp_code
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying OTP: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to verify code")

@router.delete("/cleanup", response_model=dict)
async def cleanup_expired_otps(current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """
    Clean up expired OTP codes from database (admin endpoint)
    Requires ROOT_ADMIN authentication
    """
    try:
        otp_service = OTPService()
        deleted_count = otp_service.cleanup_expired_otps()
        
        return {
            "success": True,
            "deleted_count": deleted_count,
            "message": f"Cleaned up {deleted_count} expired OTP codes"
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up OTPs: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to clean up expired codes")