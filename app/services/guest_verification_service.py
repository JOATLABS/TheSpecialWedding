from fastapi import HTTPException
from app.core.database import mongo
from typing import Optional, Dict, Any
from datetime import datetime
import re
import secrets
import logging
from app.services.guest_service import GuestService
from app.services.wedding_service import WeddingService
from app.services.otp_service import OTPService

# Configure security logging
security_logger = logging.getLogger("guest_verification_security")
security_logger.setLevel(logging.INFO)

class GuestVerificationService:
    def __init__(self):
        self.guest_service = GuestService()
        self.wedding_service = WeddingService()
        self.otp_service = OTPService()
        self.weddings_collection = mongo.db["weddings"]
        self.guests_collection = mongo.get_guest_collection()

        # Security configuration
        self._failed_attempts = {}  # In-memory rate limiting (use Redis in production)
        self._max_attempts = 5
        self._lockout_duration = 300  # 5 minutes in seconds

    def _sanitize_input(self, value: str, field_name: str, max_length: int = 255) -> str:
        """Sanitize user input to prevent injection attacks"""
        if not value or not isinstance(value, str):
            return ""

        # Trim and limit length
        sanitized = value.strip()[:max_length]

        # Remove potentially dangerous characters for NoSQL injection
        # Allow alphanumeric, spaces, and common punctuation
        if field_name in ["name", "slug"]:
            # More restrictive for names and slugs
            sanitized = re.sub(r'[^\w\s\-\.]', '', sanitized)

        return sanitized

    def _check_rate_limit(self, identifier: str) -> bool:
        """Check if request is rate limited. Returns True if allowed."""
        current_time = datetime.utcnow()

        if identifier in self._failed_attempts:
            attempt_data = self._failed_attempts[identifier]
            last_attempt_time = attempt_data.get("last_attempt")
            attempt_count = attempt_data.get("count", 0)

            # Check if still in lockout period
            if attempt_count >= self._max_attempts:
                time_since_last = (current_time - last_attempt_time).total_seconds()
                if time_since_last < self._lockout_duration:
                    security_logger.warning(f"Rate limit exceeded for {identifier[:20]}...")
                    return False
                else:
                    # Lockout expired, reset counter
                    self._failed_attempts[identifier] = {"count": 0, "last_attempt": current_time}

        return True

    def _record_failed_attempt(self, identifier: str):
        """Record a failed authentication attempt"""
        current_time = datetime.utcnow()

        if identifier in self._failed_attempts:
            self._failed_attempts[identifier]["count"] += 1
            self._failed_attempts[identifier]["last_attempt"] = current_time
        else:
            self._failed_attempts[identifier] = {"count": 1, "last_attempt": current_time}

    def _reset_failed_attempts(self, identifier: str):
        """Reset failed attempts after successful authentication"""
        if identifier in self._failed_attempts:
            del self._failed_attempts[identifier]

    def _log_security_event(self, event_type: str, details: Dict[str, Any]):
        """Log security events for monitoring"""
        try:
            log_entry = {
                "event_type": event_type,
                "timestamp": datetime.utcnow(),
                "details": details
            }
            security_logger.info(f"Security Event: {event_type} - {details}")

            # Also store in database for audit trail
            mongo.db["security_audit_logs"].insert_one(log_entry)
        except Exception as e:
            # Don't fail the main flow if logging fails
            security_logger.error(f"Failed to log security event: {str(e)}")

    def verify_guest_access(self, slug: str, verification_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verify guest access to a wedding based on different authentication methods.
        Returns wedding data and guest info if access is granted.

        Enhanced with security features:
        - Input sanitization
        - Rate limiting
        - Security logging
        - Constant-time password comparison
        """
        # Sanitize inputs
        slug = self._sanitize_input(slug, "slug", max_length=100)

        # Check rate limiting
        rate_limit_key = f"{slug}:{verification_data.get('phone', verification_data.get('name', 'unknown'))}"
        if not self._check_rate_limit(rate_limit_key):
            self._log_security_event("RATE_LIMIT_EXCEEDED", {"slug": slug})
            raise HTTPException(
                status_code=429,
                detail="Too many failed attempts. Please try again later."
            )

        try:
            # Get wedding by slug
            wedding = self.wedding_service.get_wedding_by_slug(slug)
            if not wedding:
                raise HTTPException(status_code=404, detail="Wedding not found")

            # Check privacy settings
            privacy_settings = wedding.get("privacy_settings", {})
            privacy_mode = privacy_settings.get("privacy_mode", "private")

            # If wedding is public, grant access immediately
            if privacy_mode == "public":
                return {
                    "access": True,
                    "wedding": wedding,
                    "guest": None,
                    "auth_method": "public"
                }

            # If password protected, check password
            if privacy_mode == "password":
                provided_password = verification_data.get("password", "")
                stored_password = privacy_settings.get("password_protection", "")

                # Use constant-time comparison to prevent timing attacks
                if provided_password and stored_password and \
                   secrets.compare_digest(str(provided_password), str(stored_password)):
                    self._reset_failed_attempts(rate_limit_key)
                    self._log_security_event("PASSWORD_AUTH_SUCCESS", {
                        "slug": slug,
                        "wedding_id": str(wedding.get("_id"))
                    })
                    return {
                        "access": True,
                        "wedding": wedding,
                        "guest": None,
                        "auth_method": "password"
                    }
                elif provided_password:
                    # Password was provided but incorrect
                    self._record_failed_attempt(rate_limit_key)
                    self._log_security_event("PASSWORD_AUTH_FAILED", {"slug": slug})

            # For private mode, try different verification methods
            if privacy_mode == "private":
                guest = None

                # Method 1: Token-based verification (highest priority)
                token = verification_data.get("token")
                if token:
                    # Sanitize token
                    token = self._sanitize_input(token, "token", max_length=255)
                    try:
                        guest = self.guest_service.get_guest_by_token(token, wedding["_id"])
                        if guest:
                            self._reset_failed_attempts(rate_limit_key)
                            self._log_security_event("TOKEN_AUTH_SUCCESS", {
                                "slug": slug,
                                "wedding_id": str(wedding.get("_id")),
                                "guest_id": str(guest.get("_id"))
                            })
                            return {
                                "access": True,
                                "wedding": wedding,
                                "guest": guest,
                                "auth_method": "token"
                            }
                        else:
                            self._record_failed_attempt(rate_limit_key)
                            self._log_security_event("TOKEN_AUTH_FAILED", {"slug": slug})
                    except Exception as e:
                        security_logger.warning(f"Token verification error: {str(e)}")
                        self._record_failed_attempt(rate_limit_key)

                # Method 2: OTP verification (replaces name/phone verification)
                # Check if this is an OTP verification
                otp_code = verification_data.get("otp_code")
                contact = verification_data.get("contact", "").strip()

                if otp_code and contact:
                    # Sanitize inputs
                    otp_code = self._sanitize_input(otp_code, "otp", max_length=10)
                    contact = self._sanitize_input(contact, "contact", max_length=100)

                    # Verify OTP
                    try:
                        otp_result = self.otp_service.verify_otp(
                            wedding_id=wedding["_id"],
                            contact=contact,
                            otp_code=otp_code
                        )
                        if otp_result.get("success"):
                            self._reset_failed_attempts(rate_limit_key)
                            self._log_security_event("OTP_AUTH_SUCCESS", {
                                "slug": slug,
                                "wedding_id": str(wedding.get("_id")),
                                "contact_type": otp_result.get("auth_method", "otp")
                            })
                            return {
                                "access": True,
                                "wedding": wedding,
                                "guest": otp_result.get("guest"),
                                "auth_method": otp_result.get("auth_method", "otp")
                            }
                        else:
                            self._record_failed_attempt(rate_limit_key)
                            self._log_security_event("OTP_AUTH_FAILED", {"slug": slug})
                    except Exception as e:
                        security_logger.warning(f"OTP verification error: {str(e)}")
                        self._record_failed_attempt(rate_limit_key)

                # Method 3: Request OTP (when phone/email provided without code)
                phone = verification_data.get("phone", "").strip()
                email = verification_data.get("email", "").strip()

                if phone or email:
                    # Return special response indicating OTP should be sent
                    return {
                        "access": False,
                        "wedding": None,
                        "guest": None,
                        "otp_required": True,
                        "contact": phone if phone else email,
                        "contact_type": "phone" if phone else "email",
                        "message": "Verification code will be sent to your contact"
                    }

            # Access denied
            return {
                "access": False,
                "wedding": None,
                "guest": None,
                "required_auth": privacy_mode,
                "privacy_settings": {
                    "require_phone_verification": privacy_settings.get("require_phone_verification", True),
                    "require_name_verification": privacy_settings.get("require_name_verification", True),
                    "allow_guest_sharing": privacy_settings.get("allow_guest_sharing", False)
                }
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error verifying guest access: {str(e)}")

    def _find_guest_by_verification(self, wedding_id: str, name: str, phone: str, privacy_settings: Dict) -> Optional[Dict]:
        """
        DEPRECATED: This method is replaced by OTP verification.
        Keeping for backward compatibility but should not be used for new implementations.
        All guest verification should use the OTP flow for better security.
        """
        # This method is intentionally disabled for security
        # Direct name/phone matching is vulnerable to social engineering
        return None

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number for comparison"""
        if not phone:
            return ""

        # Remove all non-digit characters
        digits_only = re.sub(r'\D', '', phone)

        # Handle US phone numbers
        if len(digits_only) == 10:
            return f"+1{digits_only}"
        elif len(digits_only) == 11 and digits_only.startswith('1'):
            return f"+{digits_only}"
        elif digits_only.startswith('1') and len(digits_only) > 11:
            return f"+{digits_only}"

        # For other formats, just prepend + if not present
        if not phone.startswith('+'):
            return f"+{digits_only}"

        return phone

    def _log_guest_verification(self, wedding_id: str, guest_id: str, method: str):
        """Log guest verification for analytics"""
        try:
            log_entry = {
                "wedding_id": wedding_id,
                "guest_id": guest_id,
                "verification_method": method,
                "timestamp": datetime.utcnow(),
                "type": "guest_verification"
            }
            mongo.db["access_logs"].insert_one(log_entry)
        except Exception:
            # Silently fail - logging shouldn't break the main flow
            pass

    async def get_wedding_privacy_info(self, slug: str) -> Dict[str, Any]:
        """Get privacy information about a wedding without granting access"""
        try:
            wedding = await self.wedding_service.get_wedding_by_slug(slug)
            if not wedding:
                raise HTTPException(status_code=404, detail="Wedding not found")

            privacy_settings = wedding.get("privacy_settings", {})
            return {
                "couple_names": wedding.get("couple_names"),
                "privacy_mode": privacy_settings.get("privacy_mode", "private"),
                "requires_password": privacy_settings.get("privacy_mode") == "password",
                "requires_guest_verification": privacy_settings.get("privacy_mode") == "private",
                "verification_requirements": {
                    "otp_enabled": True,
                    "supports_phone": True,
                    "supports_email": True
                }
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error getting wedding privacy info: {str(e)}")

    async def update_wedding_privacy_settings(self, wedding_id: str, privacy_settings: Dict[str, Any]) -> Dict[str, Any]:
        """Update privacy settings for a wedding (admin only)"""
        try:
            # Validate privacy mode
            valid_modes = ["public", "password", "private"]
            privacy_mode = privacy_settings.get("privacy_mode", "private")
            if privacy_mode not in valid_modes:
                raise HTTPException(status_code=400, detail=f"Invalid privacy mode. Must be one of: {valid_modes}")

            # If password mode, ensure password is provided
            if privacy_mode == "password" and not privacy_settings.get("password_protection"):
                raise HTTPException(status_code=400, detail="Password is required for password-protected weddings")

            # Update wedding with new privacy settings
            result = await self.weddings_collection.update_one(
                {"_id": wedding_id},
                {
                    "$set": {
                        "privacy_settings": privacy_settings,
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="Wedding not found")

            return {"message": "Privacy settings updated successfully"}

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error updating privacy settings: {str(e)}")