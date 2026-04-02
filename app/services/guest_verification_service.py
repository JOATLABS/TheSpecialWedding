from fastapi import HTTPException
from app.core.database import mongo
from app.core.cache import cache, CacheKeys
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from bson.objectid import ObjectId
import re
import secrets
import logging
import hashlib
import os
from app.services.guest_service import GuestService
from app.services.wedding_service import WeddingService
from app.services.otp_service import OTPService

# Configure security logging
security_logger = logging.getLogger("guest_verification_security")
security_logger.setLevel(logging.INFO)


class GuestVerificationService:
    _failed_attempts: Dict[str, Dict[str, Any]] = {}
    _attempt_locks: Dict[str, Dict[str, Any]] = {}
    _default_max_attempts = 5
    _default_lockout_duration = 300  # 5 minutes
    _rsvp_link_max_attempts = 3
    _rsvp_link_lockout_duration = 600  # 10 minutes
    _attempt_lock_duration = 15

    def __init__(self):
        self.guest_service = GuestService()
        self.wedding_service = WeddingService()
        self.otp_service = OTPService()
        self.weddings_collection = mongo.db["weddings"]
        self.guests_collection = mongo.get_guest_collection()
        self.rsvp_collection = mongo.db["rsvps"]
        self.plus_ones_collection = mongo.db["plus_ones"]

    @staticmethod
    def _serialize_wedding_response(wedding: Dict[str, Any]) -> Dict[str, Any]:
        return {
            **wedding,
            "id": str(wedding.get("_id")),
        }

    @staticmethod
    def _serialize_guest_response(guest: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not guest:
            return None

        guest_response = guest.copy()
        guest_id = guest_response.get("id") or guest_response.get("_id")
        if guest_id is not None:
            guest_response["id"] = str(guest_id)
        guest_response.pop("_id", None)
        guest_response.pop("token", None)
        return guest_response

    async def _load_rsvp_data(self, guest_id: str) -> Optional[Dict[str, Any]]:
        existing_rsvp = await self.rsvp_collection.find_one({
            "$or": [
                {"guest_id": guest_id},
                {"guest_id": ObjectId(guest_id) if ObjectId.is_valid(guest_id) else guest_id},
            ]
        })

        if not existing_rsvp:
            return None

        plus_ones_cursor = self.plus_ones_collection.find({"guest_id": guest_id})
        plus_ones = await plus_ones_cursor.to_list(length=20)
        for plus_one in plus_ones:
            plus_one["id"] = str(plus_one.pop("_id", ""))

        return {
            "has_rsvp": True,
            "submitted_at": existing_rsvp.get("submitted_at"),
            "attending": existing_rsvp.get("attending", []),
            "dietary": existing_rsvp.get("dietary"),
            "plus_ones": plus_ones,
        }

    async def get_session_access(
        self,
        *,
        slug: str,
        wedding_id: str,
        auth_method: str,
        guest_id: Optional[str] = None,
        otp_verified: bool = False,
    ) -> Dict[str, Any]:
        slug = self._sanitize_input(slug, "slug", max_length=100)

        wedding = await self.wedding_service.get_wedding_by_slug(slug)
        if not wedding:
            raise HTTPException(status_code=404, detail="Wedding not found")

        if str(wedding.get("_id")) != str(wedding_id):
            raise HTTPException(status_code=403, detail="Guest access session does not match this wedding")

        guest_response = None
        rsvp_data = None

        if guest_id:
            guest = await self.guests_collection.find_one({"_id": ObjectId(guest_id)})
            if not guest:
                raise HTTPException(status_code=404, detail="Guest not found")

            guest_response = self._serialize_guest_response(guest)
            rsvp_data = await self._load_rsvp_data(str(guest_response["id"]))

        return {
            "access": True,
            "wedding": self._serialize_wedding_response(wedding),
            "guest": guest_response,
            "rsvp": rsvp_data,
            "auth_method": auth_method,
            "otp_verified": otp_verified,
        }

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

    @staticmethod
    def _hash_rate_limit_identifier(identifier: str) -> str:
        return hashlib.sha256(identifier.encode("utf-8")).hexdigest()[:24]

    def _build_rate_limit_key(self, namespace: str, identifier: str) -> str:
        hashed_identifier = self._hash_rate_limit_identifier(identifier)
        return CacheKeys.rate_limit(hashed_identifier, namespace)

    def _build_attempt_lock_key(self, namespace: str, identifier: str) -> str:
        hashed_identifier = self._hash_rate_limit_identifier(identifier)
        return CacheKeys.rate_limit(hashed_identifier, f"{namespace}:lock")

    def _build_verification_identifiers(
        self,
        slug: str,
        verification_data: Dict[str, Any],
    ) -> tuple[str, str]:
        rate_limit_identifier = (
            verification_data.get("phone")
            or verification_data.get("email")
            or verification_data.get("contact")
            or (
                f"token:{verification_data.get('token')}"
                if verification_data.get("token")
                else None
            )
            or (
                "password_attempt"
                if verification_data.get("password")
                else None
            )
            or "anonymous"
        )

        scoped_identifier = f"{slug}:{rate_limit_identifier}"
        return scoped_identifier, scoped_identifier

    def _check_memory_rate_limit(self, rate_limit_key: str, max_attempts: int, window_seconds: int) -> bool:
        current_time = datetime.now(timezone.utc)
        attempts = self.__class__._failed_attempts
        attempt_data = attempts.get(rate_limit_key)

        if not attempt_data:
            return True

        time_since_last = (current_time - attempt_data["last_attempt"]).total_seconds()
        if time_since_last >= window_seconds:
            attempts.pop(rate_limit_key, None)
            return True

        if attempt_data.get("count", 0) >= max_attempts:
            security_logger.warning("Rate limit exceeded for namespace key: %s", rate_limit_key.rsplit(":", 1)[-1])
            return False

        return True

    def _record_memory_failed_attempt(self, rate_limit_key: str, window_seconds: int):
        current_time = datetime.now(timezone.utc)
        attempts = self.__class__._failed_attempts
        attempt_data = attempts.get(rate_limit_key)

        if attempt_data:
            time_since_last = (current_time - attempt_data["last_attempt"]).total_seconds()
            if time_since_last >= window_seconds:
                attempts[rate_limit_key] = {"count": 1, "last_attempt": current_time}
                return

            attempt_data["count"] += 1
            attempt_data["last_attempt"] = current_time
        else:
            attempts[rate_limit_key] = {"count": 1, "last_attempt": current_time}

    def _acquire_memory_lock(self, lock_key: str, lock_token: str, lock_seconds: int) -> bool:
        current_time = datetime.now(timezone.utc)
        locks = self.__class__._attempt_locks
        lock_data = locks.get(lock_key)

        if lock_data and lock_data["expires_at"] > current_time:
            return False

        locks[lock_key] = {
            "token": lock_token,
            "expires_at": current_time + timedelta(seconds=lock_seconds),
        }
        return True

    def _release_memory_lock(self, lock_key: str, lock_token: str):
        current_time = datetime.now(timezone.utc)
        lock_data = self.__class__._attempt_locks.get(lock_key)

        if not lock_data:
            return

        if lock_data["expires_at"] <= current_time or lock_data["token"] == lock_token:
            self.__class__._attempt_locks.pop(lock_key, None)

    async def _acquire_attempt_lock(
        self,
        identifier: str,
        namespace: str = "guest_access",
        lock_seconds: int = None,
    ) -> Optional[str]:
        duration = lock_seconds or self._attempt_lock_duration
        lock_key = self._build_attempt_lock_key(namespace, identifier)
        lock_token = secrets.token_hex(16)

        if cache.enabled and cache.redis_client:
            redis_result = await cache.acquire_lock(lock_key, lock_token, expire=duration)
            if redis_result is not None:
                return lock_token if redis_result else None

        if self._acquire_memory_lock(lock_key, lock_token, duration):
            return lock_token

        return None

    async def _release_attempt_lock(
        self,
        identifier: str,
        lock_token: str,
        namespace: str = "guest_access",
    ):
        lock_key = self._build_attempt_lock_key(namespace, identifier)

        if cache.enabled and cache.redis_client:
            redis_result = await cache.release_lock(lock_key, lock_token)
            if redis_result is not None:
                return

        self._release_memory_lock(lock_key, lock_token)

    async def _check_rate_limit(
        self,
        identifier: str,
        namespace: str = "guest_access",
        max_attempts: int = None,
        window_seconds: int = None,
    ) -> bool:
        """Check if request is rate limited. Returns True if allowed."""
        limit = max_attempts or self._default_max_attempts
        window = window_seconds or self._default_lockout_duration
        rate_limit_key = self._build_rate_limit_key(namespace, identifier)

        if cache.enabled and cache.redis_client:
            try:
                current_count = await cache.get(rate_limit_key, default=0)
                if int(current_count or 0) >= limit:
                    security_logger.warning("Rate limit exceeded for namespace: %s", namespace)
                    return False
                return True
            except Exception as exc:
                security_logger.warning("Redis rate limit check failed for %s: %s", namespace, exc)

        return self._check_memory_rate_limit(rate_limit_key, limit, window)

    async def _record_failed_attempt(
        self,
        identifier: str,
        namespace: str = "guest_access",
        max_attempts: int = None,
        window_seconds: int = None,
    ):
        """Record a failed authentication attempt"""
        window = window_seconds or self._default_lockout_duration
        rate_limit_key = self._build_rate_limit_key(namespace, identifier)

        if cache.enabled and cache.redis_client:
            current_count = await cache.increment(rate_limit_key, expire=window)
            if current_count is not None:
                return

        self._record_memory_failed_attempt(rate_limit_key, window)

    async def _reset_failed_attempts(self, identifier: str, namespace: str = "guest_access"):
        """Reset failed attempts after successful authentication"""
        rate_limit_key = self._build_rate_limit_key(namespace, identifier)

        if cache.enabled and cache.redis_client:
            await cache.delete(rate_limit_key)

        self.__class__._failed_attempts.pop(rate_limit_key, None)

    async def _log_security_event(self, event_type: str, details: Dict[str, Any]):
        """Log security events for monitoring - database only, no console logging of sensitive data"""
        try:
            log_entry = {
                "event_type": event_type,
                "timestamp": datetime.now(timezone.utc),
                "details": details
            }
            # Only log event type to console, not the sensitive details
            security_logger.info(f"Security Event: {event_type}")

            # Store full details in database for audit trail (not exposed to logs)
            await mongo.db["security_audit_logs"].insert_one(log_entry)
        except Exception:
            # Don't fail the main flow if logging fails
            security_logger.error("Failed to log security event")

    # =========================================================================
    # RSVP TOKEN ACCESS - Simple token lookup, NO privacy checks needed
    # Used by: GET /weddings/guest-access/{slug}/{token}
    # Purpose: Guest has a personalized invite link with token - just validate it
    # =========================================================================
    async def get_rsvp_access_by_token(
        self,
        slug: str,
        token: str,
    ) -> Dict[str, Any]:
        """
        Get wedding and guest data for RSVP using invite token.

        This is a DIRECT token lookup - the token IS the authorization.
        No privacy mode checks needed because:
        - Guest received a personalized invite link
        - Token proves they are an invited guest
        - Privacy mode only matters for anonymous visitors

        Returns:
            - wedding: Full wedding data
            - guest: Guest data (name, phone, plus_one_allowed, etc.)
        """
        # Sanitize inputs
        slug = self._sanitize_input(slug, "slug", max_length=100)
        token = self._sanitize_input(token, "token", max_length=255)

        if not token:
            raise HTTPException(status_code=400, detail="Token is required")

        # Rate limiting by token
        rate_limit_identifier = f"{slug}:{token}"
        lock_identifier = f"{slug}:{token}"
        lock_token = await self._acquire_attempt_lock(lock_identifier, namespace="rsvp_token_access")
        if not lock_token:
            raise HTTPException(status_code=429, detail="Verification already in progress. Please try again.")

        try:
            if not await self._check_rate_limit(rate_limit_identifier, namespace="rsvp_token_access"):
                await self._log_security_event("RSVP_TOKEN_RATE_LIMIT", {"slug": slug})
                raise HTTPException(
                    status_code=429,
                    detail="Too many attempts. Please try again later."
                )

            # Get wedding by slug
            wedding = await self.wedding_service.get_wedding_by_slug(slug)
            if not wedding:
                raise HTTPException(status_code=404, detail="Wedding not found")

            # Look up guest by token - this is the ONLY check needed
            guest = await self.guest_service.get_guest_by_token(token, wedding["_id"])

            if not guest:
                await self._record_failed_attempt(rate_limit_identifier, namespace="rsvp_token_access")
                await self._log_security_event("RSVP_TOKEN_INVALID", {"slug": slug})
                raise HTTPException(status_code=403, detail="Invalid invite token")

            # Success - reset rate limit and log
            await self._reset_failed_attempts(rate_limit_identifier, namespace="rsvp_token_access")
            await self._log_security_event("RSVP_TOKEN_SUCCESS", {
                "slug": slug,
                "wedding_id": str(wedding.get("_id")),
                "guest_id": str(guest.get("id"))
            })

            guest = self._serialize_guest_response(guest)
            guest_id_str = str(guest.get("id"))
            rsvp_data = await self._load_rsvp_data(guest_id_str)

            return {
                "access": True,
                "wedding": self._serialize_wedding_response(wedding),
                "guest": guest,
                "rsvp": rsvp_data,
                "auth_method": "token"
            }

        except HTTPException:
            raise
        except Exception as e:
            security_logger.error(f"RSVP token access error: {type(e).__name__}")
            raise HTTPException(status_code=500, detail="Error accessing RSVP")
        finally:
            await self._release_attempt_lock(lock_identifier, lock_token, namespace="rsvp_token_access")

    # =========================================================================
    # WEDDING PAGE ACCESS - Privacy-based verification for viewing wedding page
    # Used by: POST /weddings/verify-guest-access/{slug}
    # Purpose: Verify visitor is on guest list before showing wedding page
    # =========================================================================
    async def verify_wedding_page_access(
        self,
        slug: str,
        verification_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Verify visitor access to view a wedding page based on privacy settings.

        Privacy modes:
        - public: Anyone can view the wedding page
        - password: Anyone with the correct password can view
        - private: ONLY guests on the guest list can view. They must:
          1. Enter their phone/email (must match a guest record for this wedding)
          2. Receive OTP to that contact via SMS/email
          3. Verify OTP to prove they control that contact

        For RSVP with invite token, use get_rsvp_access_by_token() instead.
        """
        # Sanitize inputs
        slug = self._sanitize_input(slug, "slug", max_length=100)
        verification_data = verification_data or {}

        # Check rate limiting
        rate_limit_identifier, lock_identifier = self._build_verification_identifiers(
            slug=slug,
            verification_data=verification_data,
        )
        lock_token = await self._acquire_attempt_lock(lock_identifier, namespace="guest_page_access")
        if not lock_token:
            raise HTTPException(status_code=429, detail="Verification already in progress. Please try again.")

        try:
            if not await self._check_rate_limit(rate_limit_identifier, namespace="guest_page_access"):
                await self._log_security_event("RATE_LIMIT_EXCEEDED", {"slug": slug})
                raise HTTPException(
                    status_code=429,
                    detail="Too many failed attempts. Please try again later."
                )

            # Get wedding by slug
            wedding = await self.wedding_service.get_wedding_by_slug(slug)
            if not wedding:
                raise HTTPException(status_code=404, detail="Wedding not found")

            # Check privacy settings
            privacy_settings = wedding.get("privacy_settings", {})
            privacy_mode = privacy_settings.get("privacy_mode", "private")

            # If wedding is public, grant access immediately (no token was provided or token failed)
            if privacy_mode == "public":
                return {
                    "access": True,
                    "wedding": self._serialize_wedding_response(wedding),
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
                    await self._reset_failed_attempts(rate_limit_identifier, namespace="guest_page_access")
                    await self._log_security_event("PASSWORD_AUTH_SUCCESS", {
                        "slug": slug,
                        "wedding_id": str(wedding.get("_id"))
                    })
                    return {
                        "access": True,
                        "wedding": self._serialize_wedding_response(wedding),
                        "guest": None,
                        "auth_method": "password"
                    }
                elif provided_password:
                    # Password was provided but incorrect
                    await self._record_failed_attempt(rate_limit_identifier, namespace="guest_page_access")
                    await self._log_security_event("PASSWORD_AUTH_FAILED", {"slug": slug})

            # For private mode, try different verification methods
            # Note: Token verification is handled above (before privacy mode checks)
            # If we reach here with a token, it means the token lookup failed
            if privacy_mode == "private":
                # OTP verification (replaces name/phone verification)
                # Check if this is an OTP verification
                otp_code = verification_data.get("otp_code")
                contact = verification_data.get("contact", "").strip()

                if otp_code and contact:
                    # Sanitize inputs
                    otp_code = self._sanitize_input(otp_code, "otp", max_length=10)
                    contact = self._sanitize_input(contact, "contact", max_length=100)

                    # Verify OTP
                    try:
                        otp_result = await self.otp_service.verify_otp(
                            wedding_id=wedding["_id"],
                            contact=contact,
                            otp_code=otp_code
                        )
                        if otp_result.get("success"):
                            await self._reset_failed_attempts(rate_limit_identifier, namespace="guest_page_access")
                            await self._log_security_event("OTP_AUTH_SUCCESS", {
                                "slug": slug,
                                "wedding_id": str(wedding.get("_id")),
                                "contact_type": otp_result.get("auth_method", "otp")
                            })
                            guest_response = self._serialize_guest_response(otp_result.get("guest"))
                            return {
                                "access": True,
                                "wedding": self._serialize_wedding_response(wedding),
                                "guest": guest_response,
                                "auth_method": otp_result.get("auth_method", "otp")
                            }
                        else:
                            await self._record_failed_attempt(rate_limit_identifier, namespace="guest_page_access")
                            await self._log_security_event("OTP_AUTH_FAILED", {"slug": slug})
                    except Exception:
                        security_logger.warning("OTP verification error")
                        await self._record_failed_attempt(rate_limit_identifier, namespace="guest_page_access")

                # Method 3: Request OTP (when phone/email provided without code)
                phone = verification_data.get("phone", "").strip()
                email = verification_data.get("email", "").strip()

                if phone or email:
                    # Return special response indicating OTP should be sent
                    return {
                        "access": False,
                        "wedding_id": str(wedding.get("_id")),
                        "wedding": None,
                        "guest": None,
                        "otp_required": True,
                        "contact": phone if phone else email,
                        "contact_type": "phone" if phone else "email",
                        "message": "Verification code will be sent to your contact"
                    }

            # Access denied - log why
            security_logger.warning(f"Access denied for slug: {slug}")

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
        finally:
            await self._release_attempt_lock(lock_identifier, lock_token, namespace="guest_page_access")

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

    async def _log_guest_verification(self, wedding_id: str, guest_id: str, method: str):
        """Log guest verification for analytics"""
        try:
            log_entry = {
                "wedding_id": wedding_id,
                "guest_id": guest_id,
                "verification_method": method,
                "timestamp": datetime.now(timezone.utc),
                "type": "guest_verification"
            }
            await mongo.db["access_logs"].insert_one(log_entry)
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
            privacy_mode = privacy_settings.get("privacy_mode", "private")

            # Log privacy mode for debugging - don't expose settings (may contain password)
            security_logger.debug(f"Privacy info request for slug: {slug}")

            # Base response with privacy info
            response = {
                "id": str(wedding.get("_id")),
                "couple_names": wedding.get("couple_names"),
                "date": wedding.get("date"),
                "privacy_mode": privacy_mode,
                "requires_password": privacy_mode == "password",
                "requires_guest_verification": privacy_mode == "private",
                "featured_image": wedding.get("featured_image"),
                "theme_config": wedding.get("theme_config"),
                "rsvp_config": wedding.get("rsvp_config"),
                "events": wedding.get("events", []),
                "verification_requirements": {
                    "otp_enabled": True,
                    "supports_phone": True,
                    "supports_email": True
                }
            }

            # For public weddings, include full wedding data since no verification needed
            if privacy_mode == "public":
                response.update({
                    "registries": wedding.get("registries", []),
                    "faqs": wedding.get("faqs", []),
                    "our_story": wedding.get("our_story"),
                    "venue": wedding.get("venue"),
                    "wedding_party": wedding.get("wedding_party", []),
                })

            return response

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
                        "updated_at": datetime.now(timezone.utc)
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

    # =========================================================================
    # REQUEST RSVP LINK - Guest lookup and RSVP link delivery
    # Used by: POST /guests/request-rsvp-link
    # Purpose: Allow guests to request their RSVP link via phone/email
    # =========================================================================
    async def request_and_send_rsvp_link(
        self,
        slug: str,
        contact: str,
        contact_type: str,
    ) -> Dict[str, Any]:
        """
        Look up guest by contact (phone or email) and send their RSVP link.

        Security:
        - Rate limited: 3 requests per contact per 10 minutes
        - Always returns generic success message (prevents guest enumeration)
        - Only sends to the provided contact type (no cross-channel leakage)

        Args:
            slug: Wedding slug
            contact: Phone number or email address
            contact_type: "phone" or "email"
        Returns:
            Dict with success=True and generic message (regardless of whether guest found)
        """
        # Sanitize inputs
        slug = self._sanitize_input(slug, "slug", max_length=100)
        contact = self._sanitize_input(contact, "contact", max_length=100)

        if not contact or contact_type not in ["phone", "email"]:
            return {
                "success": True,
                "message": "If you're on the guest list, you'll receive your RSVP link shortly."
            }

        # Rate limiting by contact hash (more restrictive for this feature)
        contact_hash = hashlib.sha256(contact.encode()).hexdigest()[:16]
        rate_limit_key = f"{slug}:{contact_hash}"
        lock_identifier = rate_limit_key
        lock_token = await self._acquire_attempt_lock(lock_identifier, namespace="rsvp_link_request")

        if not lock_token:
            return {
                "success": True,
                "message": "If you're on the guest list, you'll receive your RSVP link shortly."
            }

        try:
            if not await self._check_rate_limit(
                rate_limit_key,
                namespace="rsvp_link_request",
                max_attempts=self._rsvp_link_max_attempts,
                window_seconds=self._rsvp_link_lockout_duration,
            ):
                await self._log_security_event("RSVP_LINK_RATE_LIMITED", {
                    "slug": slug,
                    "contact_type": contact_type
                })
                # Return success to prevent enumeration
                return {
                    "success": True,
                    "message": "If you're on the guest list, you'll receive your RSVP link shortly."
                }

            # Get wedding by slug
            wedding = await self.wedding_service.get_wedding_by_slug(slug)
            if not wedding:
                return {
                    "success": True,
                    "message": "If you're on the guest list, you'll receive your RSVP link shortly."
                }

            wedding_id = wedding.get("_id")

            # Look up guest by contact
            guest = None
            if contact_type == "phone":
                # Phones may be stored in various formats, try multiple lookups
                # Extract digits only from input
                digits_only = re.sub(r'\D', '', contact)

                # Try different phone formats that might be in the database
                phone_variants = [
                    contact.strip(),  # Original input
                    digits_only,  # Just digits
                    f"+1{digits_only}" if len(digits_only) == 10 else digits_only,  # E.164 format
                    f"+{digits_only}" if digits_only.startswith('1') and len(digits_only) == 11 else digits_only,
                ]
                # Remove duplicates while preserving order
                phone_variants = list(dict.fromkeys(phone_variants))

                for phone_variant in phone_variants:
                    guest = await self.guests_collection.find_one({
                        "wedding_id": wedding_id,
                        "phone": phone_variant
                    })
                    if guest:
                        break
            else:
                # Email lookup - try case-insensitive with regex
                email_cleaned = contact.strip()
                guest = await self.guests_collection.find_one({
                    "wedding_id": wedding_id,
                    "email": {"$regex": f"^{re.escape(email_cleaned)}$", "$options": "i"}
                })

            if not guest:
                # Log but return success to prevent enumeration
                await self._log_security_event("RSVP_LINK_GUEST_NOT_FOUND", {
                    "slug": slug,
                    "contact_type": contact_type
                })
                return {
                    "success": True,
                    "message": "If you're on the guest list, you'll receive your RSVP link shortly."
                }

            # Guest found - build RSVP URL
            token = guest.get("token")
            if not token:
                security_logger.warning(f"Guest found but missing token for wedding {slug}")
                return {
                    "success": True,
                    "message": "If you're on the guest list, you'll receive your RSVP link shortly."
                }

            frontend_url = os.getenv("FRONTEND_URL", "https://thespecialwedding.io")
            rsvp_url = f"{frontend_url}/{slug}/invite/{token}"
            couple_names = wedding.get("couple_names", "the couple")
            guest_name = guest.get("name", "Guest")

            # Send via appropriate channel
            send_success = False
            if contact_type == "phone":
                try:
                    from app.services.reminder_service_twilio import TwilioReminderService
                    twilio_service = TwilioReminderService()
                    message = f"Hi {guest_name}! Here's your personal RSVP link for {couple_names}'s wedding: {rsvp_url}"
                    # Use digits_only for Twilio - it will add +1 prefix for E.164 format
                    result = twilio_service._send_sms(digits_only, message)
                    send_success = result.get("status") == "success"
                except Exception as e:
                    security_logger.error(f"Failed to send SMS: {str(e)}")
            else:
                try:
                    from app.services.email_service_resend import ResendEmailService
                    email_service = ResendEmailService()
                    html_content = self._generate_rsvp_link_email_html(
                        guest_name=guest_name,
                        rsvp_url=rsvp_url,
                        couple_names=couple_names
                    )
                    result = await email_service.send_email(
                        to_email=contact,
                        subject=f"Your RSVP Link - {couple_names}'s Wedding",
                        html_content=html_content,
                        wedding_id=str(wedding_id),
                        email_type="rsvp_link_request"
                    )
                    send_success = result.get("success", False)
                except Exception as e:
                    security_logger.error(f"Failed to send email: {str(e)}")

            # Log success/failure
            if send_success:
                await self._log_security_event("RSVP_LINK_SENT", {
                    "slug": slug,
                    "contact_type": contact_type,
                    "wedding_id": str(wedding_id),
                    "guest_id": str(guest.get("_id"))
                })
            else:
                await self._log_security_event("RSVP_LINK_SEND_FAILED", {
                    "slug": slug,
                    "contact_type": contact_type
                })

            # Always return success message
            return {
                "success": True,
                "message": "If you're on the guest list, you'll receive your RSVP link shortly."
            }

        except Exception as e:
            security_logger.error(f"Error in request_and_send_rsvp_link: {str(e)}")
            return {
                "success": True,
                "message": "If you're on the guest list, you'll receive your RSVP link shortly."
            }
        finally:
            await self._release_attempt_lock(lock_identifier, lock_token, namespace="rsvp_link_request")

    def _generate_rsvp_link_email_html(
        self,
        guest_name: str,
        rsvp_url: str,
        couple_names: str
    ) -> str:
        """Generate HTML email content for RSVP link request."""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="margin: 0; padding: 0; font-family: 'Helvetica Neue', Arial, sans-serif; background-color: #f8f9fa;">
            <table role="presentation" style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 40px 20px;">
                        <table role="presentation" style="max-width: 600px; margin: 0 auto; background-color: white; border-radius: 12px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                            <tr>
                                <td style="padding: 40px; text-align: center;">
                                    <h1 style="color: #1e3a5f; margin: 0 0 20px; font-size: 28px;">
                                        Your RSVP Link
                                    </h1>
                                    <p style="color: #64748b; font-size: 16px; line-height: 1.6; margin: 0 0 30px;">
                                        Hi {guest_name},<br><br>
                                        You requested your personal RSVP link for {couple_names}'s wedding.
                                        Click the button below to RSVP:
                                    </p>
                                    <a href="{rsvp_url}" style="display: inline-block; background-color: #c8847e; color: white; text-decoration: none; padding: 14px 32px; border-radius: 8px; font-weight: 600; font-size: 16px;">
                                        RSVP Now
                                    </a>
                                    <p style="color: #94a3b8; font-size: 14px; margin: 30px 0 0;">
                                        Or copy this link: <br>
                                        <a href="{rsvp_url}" style="color: #64748b; word-break: break-all;">{rsvp_url}</a>
                                    </p>
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 20px 40px; background-color: #f8fafc; border-radius: 0 0 12px 12px;">
                                    <p style="color: #94a3b8; font-size: 12px; text-align: center; margin: 0;">
                                        This is your personal invitation link. Please do not share it with others.
                                        <br><br>
                                        Sent by TheSpecialWedding
                                    </p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """

    # =========================================================================
    # BACKWARD COMPATIBILITY WRAPPER
    # Routes to appropriate method based on whether token is provided
    # =========================================================================
    async def verify_guest_access(self, slug: str, verification_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        DEPRECATED: Use get_rsvp_access_by_token() for RSVP or
        verify_wedding_page_access() for wedding page viewing.

        This wrapper maintains backward compatibility by routing to the
        appropriate method based on whether a token is provided.
        """
        token = verification_data.get("token")

        if token:
            # Token provided - use RSVP token access (no privacy checks needed)
            return await self.get_rsvp_access_by_token(slug, token)
        else:
            # No token - use privacy-based wedding page access
            return await self.verify_wedding_page_access(slug, verification_data)
