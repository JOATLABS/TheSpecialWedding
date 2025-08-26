"""
Secure Guest Verification Service - Enterprise-Grade Security Implementation
Completely replaces the vulnerable guest verification system with comprehensive security controls.
"""

from fastapi import HTTPException
from app.core.database import mongo
from typing import Optional, Dict, Any, Tuple, List
from datetime import datetime, timedelta
import re
import logging
import secrets
import hashlib
from bson import ObjectId
from bson.errors import InvalidId
from app.services.guest_service import GuestService
from app.services.wedding_service import WeddingService
from app.utils.security_validator import security_validator
from app.utils.secure_error_handler import secure_error_handler
from app.utils.exceptions import WeddingAppException

# Configure security logging
security_logger = logging.getLogger("wedding_security_verification")
security_logger.setLevel(logging.INFO)

class SecureGuestVerificationService:
    """
    Secure Guest Verification Service with enterprise-grade security controls.
    
    Security Features:
    - Comprehensive input validation and sanitization
    - NoSQL injection prevention
    - Brute force protection with progressive delays
    - Secure token validation with expiration
    - Privacy enforcement with access logging
    - Information disclosure prevention
    - Security event logging and monitoring
    """
    
    def __init__(self):
        self.guest_service = GuestService()
        self.wedding_service = WeddingService()
        self.weddings_collection = mongo.db["weddings"]
        self.guests_collection = mongo.get_guest_collection()
        self.security_validator = security_validator
        
        # Security configuration
        self.max_verification_attempts = 5
        self.verification_lockout_duration = 300  # 5 minutes
        self.token_expiry_hours = 24
        self.token_cleanup_interval = 3600  # 1 hour
        self.max_input_length = 1000
        self.allowed_privacy_modes = ["public", "password", "private"]
        
        # Initialize security state
        self._last_cleanup = datetime.utcnow()
    
    def verify_guest_access(self, slug: str, verification_data: Dict[str, Any], client_ip: str = "unknown") -> Dict[str, Any]:
        """
        Securely verify guest access to a wedding using various authentication methods.
        
        Args:
            slug: Wedding slug identifier
            verification_data: Dictionary containing verification information
            client_ip: Client IP address for rate limiting
            
        Returns:
            Dictionary with access result and sanitized data
            
        Raises:
            WeddingAppException: For security violations or validation errors
        """
        try:
            # 1. Validate and sanitize all inputs
            validation_result = self._validate_verification_inputs(slug, verification_data, client_ip)
            if not validation_result["valid"]:
                raise WeddingAppException(
                    "INVALID_INPUT",
                    validation_result["error"],
                    400
                )
            
            sanitized_slug = validation_result["sanitized_slug"]
            sanitized_data = validation_result["sanitized_data"]
            
            # 2. Check brute force protection
            rate_limit_key = f"{client_ip}:{sanitized_slug}"
            is_allowed, delay = self.security_validator.check_brute_force_protection(
                rate_limit_key, "guest_verification"
            )
            
            if not is_allowed:
                self._log_security_event("BRUTE_FORCE_BLOCKED", {
                    "client_ip": client_ip,
                    "slug": sanitized_slug,
                    "delay": delay
                })
                raise WeddingAppException(
                    "RATE_LIMIT_EXCEEDED",
                    f"Too many failed attempts. Try again in {delay} seconds.",
                    429,
                    retry_after=delay
                )
            
            # 3. Get wedding with secure query
            wedding = self._get_wedding_by_slug_secure(sanitized_slug)
            if not wedding:
                self.security_validator.record_failed_attempt(rate_limit_key, "wedding_not_found")
                self._log_security_event("WEDDING_NOT_FOUND_ATTEMPT", {
                    "client_ip": client_ip,
                    "slug": sanitized_slug
                })
                raise WeddingAppException("WEDDING_NOT_FOUND", "Wedding not found", 404)
            
            # 4. Validate and enforce privacy settings
            privacy_settings = wedding.get("privacy_settings", {})
            privacy_mode = self._validate_privacy_mode(privacy_settings.get("privacy_mode", "private"))
            
            # Log access attempt for monitoring
            self._log_security_event("GUEST_ACCESS_ATTEMPT", {
                "client_ip": client_ip,
                "wedding_id": str(wedding["_id"]),
                "slug": sanitized_slug,
                "privacy_mode": privacy_mode,
                "auth_methods_attempted": list(sanitized_data.keys())
            })
            
            # 5. Handle different privacy modes securely
            if privacy_mode == "public":
                return self._handle_public_access(wedding, client_ip, rate_limit_key)
            elif privacy_mode == "password":
                return self._handle_password_access(wedding, sanitized_data, client_ip, rate_limit_key)
            elif privacy_mode == "private":
                return self._handle_private_access(wedding, sanitized_data, privacy_settings, client_ip, rate_limit_key)
            else:
                raise WeddingAppException("INVALID_PRIVACY_MODE", "Invalid wedding privacy configuration", 400)
                
        except WeddingAppException:
            raise
        except HTTPException:
            raise
        except Exception as e:
            # Log error securely without exposing details
            error_id = secrets.token_hex(8)
            security_logger.error(f"Guest verification error {error_id}: {type(e).__name__}")
            
            self._log_security_event("GUEST_VERIFICATION_ERROR", {
                "client_ip": client_ip,
                "error_id": error_id,
                "error_type": type(e).__name__
            })
            
            raise WeddingAppException(
                "VERIFICATION_ERROR",
                "Unable to verify guest access. Please try again.",
                500
            )
    
    def _validate_verification_inputs(self, slug: str, verification_data: Dict[str, Any], client_ip: str) -> Dict[str, Any]:
        """Validate and sanitize all verification inputs"""
        
        # Validate IP address format
        if not self._is_valid_ip(client_ip):
            return {"valid": False, "error": "Invalid client IP address"}
        
        # Validate slug
        slug_valid, sanitized_slug = self.security_validator.validate_input_security(
            slug, "slug", f"verification from {client_ip}"
        )
        if not slug_valid:
            return {"valid": False, "error": "Invalid wedding slug"}
        
        # Validate verification data structure
        if not isinstance(verification_data, dict):
            return {"valid": False, "error": "Invalid verification data format"}
        
        sanitized_data = {}
        
        # Validate each field in verification data
        for field_name, value in verification_data.items():
            if value is not None and value != "":
                valid, sanitized_value = self.security_validator.validate_input_security(
                    value, field_name, f"verification from {client_ip}"
                )
                if not valid:
                    return {"valid": False, "error": f"Invalid {field_name}"}
                sanitized_data[field_name] = sanitized_value
        
        return {
            "valid": True,
            "sanitized_slug": sanitized_slug,
            "sanitized_data": sanitized_data
        }
    
    def _get_wedding_by_slug_secure(self, slug: str) -> Optional[Dict[str, Any]]:
        """Securely retrieve wedding by slug with proper validation"""
        try:
            # Use parameterized query to prevent injection
            wedding = self.weddings_collection.find_one({"slug": {"$eq": slug}})
            
            if wedding:
                # Convert ObjectId to string for safe handling
                wedding["id"] = str(wedding["_id"])
                return wedding
            return None
            
        except Exception as e:
            security_logger.error(f"Error retrieving wedding by slug: {type(e).__name__}")
            return None
    
    def _validate_privacy_mode(self, privacy_mode: str) -> str:
        """Validate privacy mode against allowed values"""
        if privacy_mode not in self.allowed_privacy_modes:
            security_logger.warning(f"Invalid privacy mode attempted: {privacy_mode}")
            return "private"  # Default to most secure mode
        return privacy_mode
    
    def _handle_public_access(self, wedding: Dict[str, Any], client_ip: str, rate_limit_key: str) -> Dict[str, Any]:
        """Handle public wedding access"""
        
        self.security_validator.record_successful_attempt(rate_limit_key, "public_access")
        
        self._log_security_event("GUEST_ACCESS_GRANTED", {
            "client_ip": client_ip,
            "wedding_id": str(wedding["_id"]),
            "auth_method": "public"
        })
        
        return {
            "access": True,
            "wedding": self._sanitize_wedding_data(wedding),
            "guest": None,
            "auth_method": "public"
        }
    
    def _handle_password_access(self, wedding: Dict[str, Any], sanitized_data: Dict[str, Any], 
                               client_ip: str, rate_limit_key: str) -> Dict[str, Any]:
        """Handle password-protected wedding access"""
        
        privacy_settings = wedding.get("privacy_settings", {})
        provided_password = sanitized_data.get("password")
        stored_password = privacy_settings.get("password_protection")
        
        if not provided_password:
            return self._access_denied_response(wedding, "password", privacy_settings)
        
        if not stored_password:
            self._log_security_event("MISSING_PASSWORD_PROTECTION", {
                "client_ip": client_ip,
                "wedding_id": str(wedding["_id"])
            })
            raise WeddingAppException("CONFIGURATION_ERROR", "Wedding password not configured", 500)
        
        # Use constant-time comparison to prevent timing attacks
        if secrets.compare_digest(str(provided_password), str(stored_password)):
            self.security_validator.record_successful_attempt(rate_limit_key, "password_verification")
            
            self._log_security_event("GUEST_ACCESS_GRANTED", {
                "client_ip": client_ip,
                "wedding_id": str(wedding["_id"]),
                "auth_method": "password"
            })
            
            return {
                "access": True,
                "wedding": self._sanitize_wedding_data(wedding),
                "guest": None,
                "auth_method": "password"
            }
        else:
            # Record failed password attempt
            self.security_validator.record_failed_attempt(rate_limit_key, "invalid_password")
            
            self._log_security_event("PASSWORD_VERIFICATION_FAILED", {
                "client_ip": client_ip,
                "wedding_id": str(wedding["_id"])
            })
            
            return self._access_denied_response(wedding, "password", privacy_settings)
    
    def _handle_private_access(self, wedding: Dict[str, Any], sanitized_data: Dict[str, Any],
                              privacy_settings: Dict[str, Any], client_ip: str, rate_limit_key: str) -> Dict[str, Any]:
        """Handle private wedding access with token or verification"""
        
        verification_success = False
        guest = None
        
        # Method 1: Token-based verification (highest priority)
        token = sanitized_data.get("token")
        if token:
            guest = self._verify_token_access(token, wedding, client_ip, rate_limit_key)
            if guest:
                verification_success = True
                return {
                    "access": True,
                    "wedding": self._sanitize_wedding_data(wedding),
                    "guest": self._sanitize_guest_data(guest),
                    "auth_method": "token"
                }
        
        # Method 2: Name and phone verification
        name = sanitized_data.get("name", "")
        phone = sanitized_data.get("phone", "")
        
        if name or phone:
            guest = self._verify_guest_credentials(
                wedding["_id"], name, phone, privacy_settings, client_ip
            )
            if guest:
                verification_success = True
                self.security_validator.record_successful_attempt(rate_limit_key, "credential_verification")
                
                self._log_security_event("GUEST_ACCESS_GRANTED", {
                    "client_ip": client_ip,
                    "wedding_id": str(wedding["_id"]),
                    "guest_id": str(guest.get("_id")),
                    "auth_method": "verification"
                })
                
                return {
                    "access": True,
                    "wedding": self._sanitize_wedding_data(wedding),
                    "guest": self._sanitize_guest_data(guest),
                    "auth_method": "verification"
                }
        
        # If no verification method succeeded
        if not verification_success:
            self.security_validator.record_failed_attempt(rate_limit_key, "verification_failed")
            
            self._log_security_event("GUEST_VERIFICATION_FAILED", {
                "client_ip": client_ip,
                "wedding_id": str(wedding["_id"]),
                "attempted_methods": [k for k in sanitized_data.keys() if sanitized_data[k]]
            })
        
        return self._access_denied_response(wedding, "private", privacy_settings)
    
    def _verify_token_access(self, token: str, wedding: Dict[str, Any], client_ip: str, rate_limit_key: str) -> Optional[Dict[str, Any]]:
        """Securely verify token-based access"""
        try:
            # Validate token format
            if not self.security_validator.validate_token_format(token, expected_length=None):
                self._log_security_event("INVALID_TOKEN_FORMAT", {
                    "client_ip": client_ip,
                    "wedding_id": str(wedding["_id"]),
                    "token_length": len(token)
                })
                return None
            
            # Get guest by token with secure query
            guest = self._get_guest_by_token_secure(token, wedding["_id"])
            
            if guest:
                # Verify token expiration
                if self._is_token_expired(guest):
                    self._log_security_event("EXPIRED_TOKEN_USED", {
                        "client_ip": client_ip,
                        "wedding_id": str(wedding["_id"]),
                        "guest_id": str(guest.get("_id"))
                    })
                    return None
                
                self.security_validator.record_successful_attempt(rate_limit_key, "token_verification")
                
                self._log_security_event("TOKEN_ACCESS_GRANTED", {
                    "client_ip": client_ip,
                    "wedding_id": str(wedding["_id"]),
                    "guest_id": str(guest.get("_id"))
                })
                
                return guest
            else:
                self._log_security_event("INVALID_TOKEN_USED", {
                    "client_ip": client_ip,
                    "wedding_id": str(wedding["_id"])
                })
                return None
                
        except Exception as e:
            security_logger.error(f"Token verification error: {type(e).__name__}")
            return None
    
    def _get_guest_by_token_secure(self, token: str, wedding_id: ObjectId) -> Optional[Dict[str, Any]]:
        """Securely retrieve guest by token"""
        try:
            # Use exact match to prevent injection
            guest = self.guests_collection.find_one({
                "wedding_id": {"$eq": str(wedding_id)},
                "invitation_token": {"$eq": token}
            })
            
            return guest
            
        except Exception as e:
            security_logger.error(f"Error retrieving guest by token: {type(e).__name__}")
            return None
    
    def _verify_guest_credentials(self, wedding_id: ObjectId, name: str, phone: str, 
                                 privacy_settings: Dict[str, Any], client_ip: str) -> Optional[Dict[str, Any]]:
        """Securely verify guest by name and/or phone"""
        try:
            require_name = privacy_settings.get("require_name_verification", True)
            require_phone = privacy_settings.get("require_phone_verification", True)
            
            # Build secure query
            base_query = {"wedding_id": {"$eq": str(wedding_id)}}
            
            if require_name and require_phone:
                if not name or not phone:
                    return None
                
                # Both name and phone required
                normalized_phone = self._normalize_phone_secure(phone)
                guest = self.guests_collection.find_one({
                    **base_query,
                    "$and": [
                        {"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}},
                        {"$or": [
                            {"phone": {"$eq": phone}},
                            {"phone": {"$eq": normalized_phone}}
                        ]}
                    ]
                })
                
            elif require_name and not require_phone:
                if not name:
                    return None
                guest = self.guests_collection.find_one({
                    **base_query,
                    "name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}
                })
                
            elif require_phone and not require_name:
                if not phone:
                    return None
                normalized_phone = self._normalize_phone_secure(phone)
                guest = self.guests_collection.find_one({
                    **base_query,
                    "$or": [
                        {"phone": {"$eq": phone}},
                        {"phone": {"$eq": normalized_phone}}
                    ]
                })
                
            else:
                # Either name or phone
                conditions = []
                if name:
                    conditions.append({"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}})
                if phone:
                    normalized_phone = self._normalize_phone_secure(phone)
                    conditions.append({
                        "$or": [
                            {"phone": {"$eq": phone}},
                            {"phone": {"$eq": normalized_phone}}
                        ]
                    })
                
                if not conditions:
                    return None
                
                guest = self.guests_collection.find_one({
                    **base_query,
                    "$or": conditions
                })
            
            if guest:
                # Log successful verification
                self._log_guest_verification_secure(str(wedding_id), str(guest.get("_id")), "credential_verification", client_ip)
            
            return guest
            
        except Exception as e:
            security_logger.error(f"Error verifying guest credentials: {type(e).__name__}")
            return None
    
    def _normalize_phone_secure(self, phone: str) -> str:
        """Securely normalize phone number"""
        if not phone:
            return ""
        
        # Remove all non-digit characters
        digits_only = re.sub(r'[^\d]', '', phone)
        
        # Validate phone number length
        if len(digits_only) < 10 or len(digits_only) > 15:
            return phone  # Return original if invalid length
        
        # Handle US phone numbers
        if len(digits_only) == 10:
            return f"+1{digits_only}"
        elif len(digits_only) == 11 and digits_only.startswith('1'):
            return f"+{digits_only}"
        
        # For international numbers, prepend + if not present
        if not phone.startswith('+'):
            return f"+{digits_only}"
        
        return phone
    
    def _is_token_expired(self, guest: Dict[str, Any]) -> bool:
        """Check if guest token is expired"""
        try:
            token_created = guest.get("token_created_at")
            if not token_created:
                # If no creation time, consider expired
                return True
            
            if isinstance(token_created, str):
                token_created = datetime.fromisoformat(token_created.replace('Z', '+00:00'))
            
            expiry_time = token_created + timedelta(hours=self.token_expiry_hours)
            return datetime.utcnow() > expiry_time
            
        except Exception:
            # If we can't determine expiration, consider it expired for security
            return True
    
    def _sanitize_wedding_data(self, wedding: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize wedding data for response"""
        
        # Only include safe fields
        safe_fields = [
            "id", "_id", "couple_names", "wedding_date", "venue_name", 
            "venue_address", "theme", "slug", "description", "created_at"
        ]
        
        sanitized = {}
        for field in safe_fields:
            if field in wedding:
                value = wedding[field]
                # Convert ObjectId to string
                if isinstance(value, ObjectId):
                    sanitized[field] = str(value)
                else:
                    sanitized[field] = value
        
        return sanitized
    
    def _sanitize_guest_data(self, guest: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize guest data for response"""
        
        # Only include safe fields
        safe_fields = [
            "id", "_id", "name", "email", "rsvp_status", "plus_one_count",
            "dietary_restrictions", "created_at"
        ]
        
        sanitized = {}
        for field in safe_fields:
            if field in guest:
                value = guest[field]
                # Convert ObjectId to string
                if isinstance(value, ObjectId):
                    sanitized[field] = str(value)
                else:
                    sanitized[field] = value
        
        # Ensure ID field exists
        if "_id" in guest and "id" not in sanitized:
            sanitized["id"] = str(guest["_id"])
        
        return sanitized
    
    def _access_denied_response(self, wedding: Dict[str, Any], privacy_mode: str, privacy_settings: Dict[str, Any]) -> Dict[str, Any]:
        """Return access denied response with minimal information"""
        
        return {
            "access": False,
            "wedding": None,
            "guest": None,
            "required_auth": privacy_mode,
            "privacy_settings": self._get_safe_privacy_settings(privacy_settings)
        }
    
    def _get_safe_privacy_settings(self, privacy_settings: Dict[str, Any]) -> Dict[str, Any]:
        """Return safe privacy settings without sensitive information"""
        
        return {
            "require_phone_verification": privacy_settings.get("require_phone_verification", True),
            "require_name_verification": privacy_settings.get("require_name_verification", True),
            "allow_guest_sharing": privacy_settings.get("allow_guest_sharing", False)
        }
    
    def _log_guest_verification_secure(self, wedding_id: str, guest_id: str, method: str, client_ip: str):
        """Securely log guest verification"""
        try:
            log_entry = {
                "wedding_id": wedding_id,
                "guest_id": guest_id,
                "verification_method": method,
                "client_ip": client_ip,
                "timestamp": datetime.utcnow(),
                "type": "guest_verification_success"
            }
            mongo.db["security_audit_logs"].insert_one(log_entry)
            
        except Exception as e:
            security_logger.error(f"Failed to log guest verification: {type(e).__name__}")
    
    def _log_security_event(self, event_type: str, details: Dict[str, Any]):
        """Log security events"""
        self.security_validator.log_security_event(event_type, details, "INFO")
    
    def _is_valid_ip(self, ip: str) -> bool:
        """Validate IP address format"""
        if not ip or ip == "unknown":
            return True  # Allow unknown IPs for backward compatibility
        
        # Simple IP validation
        ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        if re.match(ip_pattern, ip):
            parts = ip.split('.')
            return all(0 <= int(part) <= 255 for part in parts)
        
        # Allow IPv6 addresses (basic validation)
        ipv6_pattern = r'^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$'
        return bool(re.match(ipv6_pattern, ip))
    
    def get_wedding_privacy_info_secure(self, slug: str, client_ip: str = "unknown") -> Dict[str, Any]:
        """Securely get privacy information about a wedding"""
        try:
            # Validate slug
            slug_valid, sanitized_slug = self.security_validator.validate_input_security(
                slug, "slug", f"privacy_info from {client_ip}"
            )
            if not slug_valid:
                raise WeddingAppException("INVALID_INPUT", "Invalid wedding slug", 400)
            
            # Get wedding securely
            wedding = self._get_wedding_by_slug_secure(sanitized_slug)
            if not wedding:
                self._log_security_event("PRIVACY_INFO_NOT_FOUND", {
                    "client_ip": client_ip,
                    "slug": sanitized_slug
                })
                raise WeddingAppException("WEDDING_NOT_FOUND", "Wedding not found", 404)
            
            privacy_settings = wedding.get("privacy_settings", {})
            privacy_mode = self._validate_privacy_mode(privacy_settings.get("privacy_mode", "private"))
            
            # Log privacy info request
            self._log_security_event("PRIVACY_INFO_REQUEST", {
                "client_ip": client_ip,
                "wedding_id": str(wedding["_id"]),
                "privacy_mode": privacy_mode
            })
            
            return {
                "couple_names": wedding.get("couple_names"),
                "privacy_mode": privacy_mode,
                "requires_password": privacy_mode == "password",
                "requires_guest_verification": privacy_mode == "private",
                "verification_requirements": {
                    "require_phone": privacy_settings.get("require_phone_verification", True),
                    "require_name": privacy_settings.get("require_name_verification", True)
                }
            }
            
        except WeddingAppException:
            raise
        except Exception as e:
            error_id = secrets.token_hex(8)
            security_logger.error(f"Privacy info error {error_id}: {type(e).__name__}")
            
            raise WeddingAppException(
                "PRIVACY_INFO_ERROR",
                "Unable to retrieve wedding privacy information",
                500
            )
    
    def update_wedding_privacy_settings_secure(self, wedding_id: str, privacy_settings: Dict[str, Any], 
                                              admin_user_id: str, client_ip: str = "unknown") -> Dict[str, Any]:
        """Securely update privacy settings for a wedding"""
        try:
            # Validate wedding ID
            id_valid, validated_id = self.security_validator.validate_object_id(wedding_id)
            if not id_valid:
                raise WeddingAppException("INVALID_INPUT", "Invalid wedding ID", 400)
            
            # Validate privacy settings
            validated_settings = self._validate_privacy_settings_secure(privacy_settings)
            
            # Update with secure query
            result = self.weddings_collection.update_one(
                {"_id": ObjectId(validated_id)},
                {
                    "$set": {
                        "privacy_settings": validated_settings,
                        "updated_at": datetime.utcnow(),
                        "updated_by": admin_user_id
                    }
                }
            )
            
            if result.matched_count == 0:
                raise WeddingAppException("WEDDING_NOT_FOUND", "Wedding not found", 404)
            
            # Log privacy settings update
            self._log_security_event("PRIVACY_SETTINGS_UPDATED", {
                "client_ip": client_ip,
                "wedding_id": validated_id,
                "admin_user_id": admin_user_id,
                "privacy_mode": validated_settings.get("privacy_mode")
            })
            
            return {"message": "Privacy settings updated successfully"}
            
        except WeddingAppException:
            raise
        except Exception as e:
            error_id = secrets.token_hex(8)
            security_logger.error(f"Privacy update error {error_id}: {type(e).__name__}")
            
            raise WeddingAppException(
                "PRIVACY_UPDATE_ERROR", 
                "Unable to update privacy settings",
                500
            )
    
    def _validate_privacy_settings_secure(self, privacy_settings: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize privacy settings"""
        
        validated = {}
        
        # Validate privacy mode
        privacy_mode = privacy_settings.get("privacy_mode", "private")
        if privacy_mode not in self.allowed_privacy_modes:
            raise WeddingAppException("INVALID_INPUT", "Invalid privacy mode", 400)
        validated["privacy_mode"] = privacy_mode
        
        # Validate password protection if needed
        if privacy_mode == "password":
            password = privacy_settings.get("password_protection")
            if not password:
                raise WeddingAppException("INVALID_INPUT", "Password required for password-protected weddings", 400)
            
            # Validate password
            password_valid, sanitized_password = self.security_validator.validate_input_security(
                password, "password", "privacy_settings_update"
            )
            if not password_valid:
                raise WeddingAppException("INVALID_INPUT", "Invalid password format", 400)
            
            validated["password_protection"] = sanitized_password
        
        # Validate boolean settings
        bool_settings = [
            "require_phone_verification", "require_name_verification", 
            "allow_guest_sharing", "guest_auth_required"
        ]
        
        for setting in bool_settings:
            if setting in privacy_settings:
                value = privacy_settings[setting]
                if isinstance(value, bool):
                    validated[setting] = value
                elif isinstance(value, str):
                    validated[setting] = value.lower() in ['true', '1', 'yes']
                else:
                    validated[setting] = bool(value)
        
        return validated


# Create secure service instance
secure_guest_verification_service = SecureGuestVerificationService()