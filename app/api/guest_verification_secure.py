"""
Secure Guest Verification API - Enterprise-Grade Security Implementation
Completely replaces vulnerable guest verification endpoints with comprehensive security controls.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Optional
from pydantic import BaseModel, Field, validator
from app.services.guest_verification_service_secure import secure_guest_verification_service
from app.dependencies.auth_extended import require_admin_or_planner, ExtendedAuthUser, check_wedding_access
from app.utils.security_validator import security_validator
from app.utils.secure_error_handler import secure_error_handler
from app.utils.exceptions import WeddingAppException
import logging

# Configure router
router = APIRouter()

# Configure security logging
security_logger = logging.getLogger("wedding_security_api")

class SecureGuestVerificationRequest(BaseModel):
    """Secure request model with comprehensive validation"""
    token: Optional[str] = Field(None, description="Guest invitation token", max_length=255)
    name: Optional[str] = Field(None, description="Guest name for verification", max_length=100)
    phone: Optional[str] = Field(None, description="Guest phone number for verification", max_length=50)
    password: Optional[str] = Field(None, description="Password for password-protected weddings", max_length=128)
    
    @validator('token')
    def validate_token(cls, v):
        if v is not None:
            if not security_validator.validate_token_format(v):
                raise ValueError("Invalid token format")
        return v
    
    @validator('name')
    def validate_name(cls, v):
        if v is not None:
            valid, sanitized = security_validator.validate_input_security(v, "name", "api_request")
            if not valid:
                raise ValueError("Invalid name format")
            return sanitized
        return v
    
    @validator('phone')
    def validate_phone(cls, v):
        if v is not None:
            valid, sanitized = security_validator.validate_input_security(v, "phone", "api_request")
            if not valid:
                raise ValueError("Invalid phone format")
            return sanitized
        return v
    
    @validator('password')
    def validate_password(cls, v):
        if v is not None:
            valid, sanitized = security_validator.validate_input_security(v, "password", "api_request")
            if not valid:
                raise ValueError("Invalid password format")
            return sanitized
        return v

class SecurePrivacySettingsUpdate(BaseModel):
    """Secure privacy settings model with validation"""
    privacy_mode: str = Field(..., description="Privacy mode: public, password, private")
    guest_auth_required: bool = Field(default=True)
    password_protection: Optional[str] = Field(None, description="Password for password mode", max_length=128)
    allow_guest_sharing: bool = Field(default=False)
    require_phone_verification: bool = Field(default=True)
    require_name_verification: bool = Field(default=True)
    
    @validator('privacy_mode')
    def validate_privacy_mode(cls, v):
        allowed_modes = ["public", "password", "private"]
        if v not in allowed_modes:
            raise ValueError(f"Privacy mode must be one of: {allowed_modes}")
        return v
    
    @validator('password_protection')
    def validate_password_protection(cls, v, values):
        privacy_mode = values.get('privacy_mode')
        if privacy_mode == 'password':
            if not v:
                raise ValueError("Password is required for password-protected weddings")
            valid, sanitized = security_validator.validate_input_security(v, "password", "privacy_settings")
            if not valid:
                raise ValueError("Invalid password format")
            return sanitized
        return v

def get_client_ip(request: Request) -> str:
    """Securely extract client IP address"""
    # Try various headers for real IP (in order of preference)
    ip_headers = [
        "X-Forwarded-For",
        "X-Real-IP", 
        "X-Client-IP",
        "CF-Connecting-IP",
        "True-Client-IP"
    ]
    
    for header in ip_headers:
        ip = request.headers.get(header)
        if ip:
            # Take first IP if comma-separated and validate
            first_ip = ip.split(",")[0].strip()
            # Basic IP validation
            if first_ip and len(first_ip) <= 45:  # IPv6 max length
                return first_ip
    
    # Fallback to request client
    client_host = getattr(request.client, 'host', 'unknown')
    return client_host if client_host else 'unknown'

@router.post("/weddings/verify-guest-access/{slug}", tags=["Guest"])
async def verify_guest_access_secure(
    slug: str, 
    verification: SecureGuestVerificationRequest,
    request: Request
):
    """
    Securely verify guest access to a wedding using various authentication methods.
    
    This endpoint implements comprehensive security controls including:
    - Input validation and sanitization  
    - Injection attack prevention
    - Brute force protection
    - Rate limiting
    - Security logging
    - Information disclosure prevention
    """
    client_ip = get_client_ip(request)
    
    try:
        # Log access attempt
        security_logger.info(f"Guest verification attempt from {client_ip} for slug: {slug}")
        
        # Validate slug format
        slug_valid, sanitized_slug = security_validator.validate_input_security(
            slug, "slug", f"guest_verification from {client_ip}"
        )
        if not slug_valid:
            raise WeddingAppException("INVALID_INPUT", "Invalid wedding slug", 400)
        
        # Convert Pydantic model to dict for processing
        verification_data = verification.dict(exclude_none=True)
        
        # Call secure verification service
        result = secure_guest_verification_service.verify_guest_access(
            slug=sanitized_slug,
            verification_data=verification_data,
            client_ip=client_ip
        )
        
        if not result.get("access"):
            # Return structured access denied response
            raise WeddingAppException(
                "GUEST_VERIFICATION_FAILED",
                "Guest verification failed",
                403,
                field="verification",
                headers={
                    "X-Auth-Required": result.get("required_auth", "private"),
                    "X-Privacy-Settings": str(result.get("privacy_settings", {}))
                }
            )
        
        # Log successful access
        security_logger.info(
            f"Guest access granted from {client_ip} for wedding {result.get('wedding', {}).get('id')} "
            f"via {result.get('auth_method')}"
        )
        
        return {
            "access": True,
            "wedding": result["wedding"],
            "guest": result.get("guest"),
            "auth_method": result.get("auth_method")
        }
        
    except WeddingAppException:
        raise
    except Exception as e:
        # Use secure error handler
        response = secure_error_handler.handle_exception(request, e)
        raise HTTPException(
            status_code=response.status_code,
            detail=response.body.decode() if hasattr(response.body, 'decode') else str(response.body)
        )

@router.get("/weddings/privacy-info/{slug}", tags=["Guest"])
async def get_wedding_privacy_info_secure(slug: str, request: Request):
    """
    Securely get privacy information about a wedding without granting access.
    Used to show appropriate authentication form to guests.
    """
    client_ip = get_client_ip(request)
    
    try:
        # Log privacy info request
        security_logger.info(f"Privacy info request from {client_ip} for slug: {slug}")
        
        return secure_guest_verification_service.get_wedding_privacy_info_secure(
            slug=slug,
            client_ip=client_ip
        )
        
    except WeddingAppException:
        raise
    except Exception as e:
        response = secure_error_handler.handle_exception(request, e)
        raise HTTPException(
            status_code=response.status_code,
            detail=response.body.decode() if hasattr(response.body, 'decode') else str(response.body)
        )

@router.get("/weddings/guest-access/{slug}/{token}", tags=["Guest"])
async def get_wedding_with_token_access_secure(
    slug: str, 
    token: str, 
    request: Request
):
    """
    Securely get wedding details using token-based authentication.
    This is for direct token-based access (legacy support).
    """
    client_ip = get_client_ip(request)
    
    try:
        # Log token access attempt
        security_logger.info(f"Token access attempt from {client_ip} for slug: {slug}")
        
        # Validate inputs
        slug_valid, sanitized_slug = security_validator.validate_input_security(
            slug, "slug", f"token_access from {client_ip}"
        )
        if not slug_valid:
            raise WeddingAppException("INVALID_INPUT", "Invalid wedding slug", 400)
        
        token_valid, sanitized_token = security_validator.validate_input_security(
            token, "token", f"token_access from {client_ip}"
        )
        if not token_valid:
            raise WeddingAppException("INVALID_INPUT", "Invalid token format", 400)
        
        # Use verification service with token
        result = secure_guest_verification_service.verify_guest_access(
            slug=sanitized_slug,
            verification_data={"token": sanitized_token},
            client_ip=client_ip
        )
        
        if not result.get("access"):
            raise WeddingAppException("INVALID_TOKEN", "Invalid guest token", 403)
        
        return {
            "wedding": result["wedding"],
            "guest": result.get("guest")
        }
        
    except WeddingAppException:
        raise
    except Exception as e:
        response = secure_error_handler.handle_exception(request, e)
        raise HTTPException(
            status_code=response.status_code,
            detail=response.body.decode() if hasattr(response.body, 'decode') else str(response.body)
        )

@router.put("/weddings/{wedding_id}/privacy-settings", tags=["Admin"])
async def update_wedding_privacy_settings_secure(
    wedding_id: str, 
    privacy_settings: SecurePrivacySettingsUpdate,
    request: Request,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Securely update privacy settings for a wedding - Admin only with comprehensive access control
    """
    client_ip = get_client_ip(request)
    
    try:
        # Validate wedding access
        if not check_wedding_access(current_user, wedding_id):
            security_logger.warning(
                f"Unauthorized privacy settings access attempt from {current_user.email} "
                f"({client_ip}) for wedding {wedding_id}"
            )
            raise WeddingAppException("ACCESS_DENIED", "Access to this wedding denied", 403)
        
        # Log privacy settings update attempt
        security_logger.info(
            f"Privacy settings update by {current_user.email} ({client_ip}) "
            f"for wedding {wedding_id}"
        )
        
        # Convert Pydantic model to dict
        settings_data = privacy_settings.dict()
        
        # Call secure update service
        result = secure_guest_verification_service.update_wedding_privacy_settings_secure(
            wedding_id=wedding_id,
            privacy_settings=settings_data,
            admin_user_id=current_user.email,
            client_ip=client_ip
        )
        
        return result
        
    except WeddingAppException:
        raise
    except Exception as e:
        response = secure_error_handler.handle_exception(request, e)
        raise HTTPException(
            status_code=response.status_code,
            detail=response.body.decode() if hasattr(response.body, 'decode') else str(response.body)
        )

@router.get("/weddings/{wedding_id}/access-logs", tags=["Admin"])
async def get_wedding_access_logs_secure(
    wedding_id: str,
    request: Request,
    limit: int = 100,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Securely get access logs for a wedding - Admin only with enhanced security logging
    """
    client_ip = get_client_ip(request)
    
    try:
        # Validate wedding access
        if not check_wedding_access(current_user, wedding_id):
            security_logger.warning(
                f"Unauthorized access logs request from {current_user.email} "
                f"({client_ip}) for wedding {wedding_id}"
            )
            raise WeddingAppException("ACCESS_DENIED", "Access to this wedding denied", 403)
        
        # Validate wedding ID format
        id_valid, validated_id = security_validator.validate_object_id(wedding_id)
        if not id_valid:
            raise WeddingAppException("INVALID_INPUT", "Invalid wedding ID", 400)
        
        # Validate limit parameter
        if not isinstance(limit, int) or limit < 1 or limit > 1000:
            limit = 100
        
        # Log access logs request
        security_logger.info(
            f"Access logs requested by {current_user.email} ({client_ip}) "
            f"for wedding {wedding_id}"
        )
        
        from app.core.database import mongo
        from bson import ObjectId
        
        # Secure query for access logs
        logs = list(mongo.db["security_audit_logs"].find(
            {"wedding_id": {"$eq": validated_id}},
            {
                "_id": 0,
                "wedding_id": 1,
                "guest_id": 1,
                "verification_method": 1,
                "client_ip": 1,
                "timestamp": 1,
                "type": 1
            }
        ).sort("timestamp", -1).limit(limit))
        
        # Sanitize IP addresses for privacy (keep only first 3 octets)
        for log in logs:
            if "client_ip" in log and log["client_ip"] != "unknown":
                ip_parts = log["client_ip"].split(".")
                if len(ip_parts) == 4:
                    log["client_ip"] = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.xxx"
        
        return {"logs": logs, "total": len(logs)}
        
    except WeddingAppException:
        raise
    except Exception as e:
        response = secure_error_handler.handle_exception(request, e)
        raise HTTPException(
            status_code=response.status_code,
            detail=response.body.decode() if hasattr(response.body, 'decode') else str(response.body)
        )

@router.get("/admin/security/verification-stats", tags=["Admin"])
async def get_verification_security_stats(
    request: Request,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Get security statistics for guest verification system - ROOT_ADMIN only
    """
    client_ip = get_client_ip(request)
    
    try:
        # Only ROOT_ADMIN can access security stats
        if not current_user.is_root_admin:
            security_logger.warning(
                f"Non-admin user {current_user.email} ({client_ip}) "
                f"attempted to access security stats"
            )
            raise WeddingAppException("ACCESS_DENIED", "Root admin access required", 403)
        
        # Log security stats request
        security_logger.info(
            f"Security stats requested by {current_user.email} ({client_ip})"
        )
        
        from app.core.database import mongo
        from datetime import datetime, timedelta
        
        # Get stats from the last 24 hours
        last_24h = datetime.utcnow() - timedelta(hours=24)
        
        # Security event statistics
        pipeline = [
            {"$match": {"timestamp": {"$gte": last_24h}}},
            {"$group": {
                "_id": "$type",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}}
        ]
        
        event_stats = list(mongo.db["security_audit_logs"].aggregate(pipeline))
        
        # Failed attempt statistics
        failed_attempts_stats = mongo.db["security_audit_logs"].count_documents({
            "timestamp": {"$gte": last_24h},
            "type": {"$regex": "failed|blocked", "$options": "i"}
        })
        
        # Successful access statistics  
        successful_access_stats = mongo.db["security_audit_logs"].count_documents({
            "timestamp": {"$gte": last_24h},
            "type": "guest_verification_success"
        })
        
        return {
            "period": "last_24_hours",
            "event_statistics": event_stats,
            "failed_attempts": failed_attempts_stats,
            "successful_access": successful_access_stats,
            "security_health": "operational"
        }
        
    except WeddingAppException:
        raise
    except Exception as e:
        response = secure_error_handler.handle_exception(request, e)
        raise HTTPException(
            status_code=response.status_code,
            detail=response.body.decode() if hasattr(response.body, 'decode') else str(response.body)
        )