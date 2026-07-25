import hashlib
import logging
import os
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

from bson.objectid import ObjectId
from fastapi import HTTPException

from app.constants.marketing_capture_media import MARKETING_CAPTURE_GALLERY_URLS
from app.core.cache import CacheKeys, cache
from app.core.database import mongo
from app.services.gallery_media_service import GalleryUploadService
from app.services.guest_service import GuestService
from app.services.otp_service import OTPService
from app.services.wedding_projection_cache_service import (
    invalidate_wedding_projection_caches,
)
from app.services.wedding_service import WeddingService

# Configure security logging
security_logger = logging.getLogger("guest_verification_security")
security_logger.setLevel(logging.INFO)


class GuestVerificationService:
    _repository_static_media_prefix = "/demo-gallery/"
    _public_wedding_scalar_fields = {
        "slug": str,
        "couple_names": str,
        "date": str,
        "timezone": str,
    }
    _public_event_fields = {
        "type": str,
        "custom_type_label": str,
        "date": str,
    }
    _public_event_detail_fields = {
        "venue_name": str,
        "location": str,
        "time": str,
        "attire": str,
        "timezone": str,
    }
    _public_rsvp_fields = {
        "greeting": str,
        "help_text": str,
        "help_button_label": str,
    }
    _public_registry_fields = {"name": str, "url": str, "color": str}
    _public_faq_fields = {
        "question": str,
        "answer": str,
        "link_url": str,
        "link_label": str,
    }
    _public_theme_fields = {
        "primary_color": str,
        "secondary_color": str,
        "accent_color": str,
        "background_style": str,
        "font_style": str,
    }
    _public_story_fields = {
        "text": str,
        "image_url": str,
        "image_shape": str,
    }
    _public_venue_fields = {"name": str, "address": str}
    _public_wedding_party_fields = {
        "id": str,
        "name": str,
        "role": str,
        "image_url": str,
        "display_order": int,
        "side": str,
    }
    _guest_response_fields = {
        "name": str,
        "phone": str,
        "email": str,
        "plus_one_allowed": bool,
        "number_of_plus_ones_allowed": int,
        "sms_opt_in": bool,
        "email_opt_in": bool,
    }
    _rsvp_plus_one_fields = {
        "name": str,
        "phone": str,
        "email": str,
        "dietary": str,
        "sms_opt_in": bool,
        "email_opt_in": bool,
    }
    _failed_attempts: dict[str, dict[str, Any]] = {}
    _attempt_locks: dict[str, dict[str, Any]] = {}
    _default_max_attempts = 5
    _default_lockout_duration = 300  # 5 minutes
    _rsvp_link_max_attempts = 3
    _rsvp_link_lockout_duration = 600  # 10 minutes
    _attempt_lock_duration = 15
    _privacy_info_cache_ttl = 30
    _privacy_info_cache_schema_version = 1

    def __init__(self):
        self.guest_service = GuestService()
        self.wedding_service = WeddingService()
        self.otp_service = OTPService()
        self.gallery_service = GalleryUploadService()
        self.weddings_collection = mongo.db["weddings"]
        self.guests_collection = mongo.get_guest_collection()
        self.rsvp_collection = mongo.db["rsvps"]
        self.plus_ones_collection = mongo.db["plus_ones"]

    def _get_gallery_service(self) -> GalleryUploadService:
        gallery_service = getattr(self, "gallery_service", None)
        if gallery_service is None:
            gallery_service = GalleryUploadService()
            self.gallery_service = gallery_service
        return gallery_service

    def _resolve_guest_media_url(self, value: Any) -> Any:
        if not isinstance(value, str):
            return value

        normalized = value.strip()
        if not normalized:
            return normalized

        if re.match(r"^[a-z][a-z0-9+\-.]*://", normalized, re.IGNORECASE):
            return normalized
        if normalized.startswith(self._repository_static_media_prefix):
            return normalized if normalized in MARKETING_CAPTURE_GALLERY_URLS else None
        if (
            normalized.startswith("//")
            or normalized.startswith("data:")
            or normalized.startswith("blob:")
        ):
            return normalized

        return self._get_gallery_service().build_public_url(normalized.lstrip("/"))

    def _normalize_guest_media_fields(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized_payload = {**payload}
        if "featured_image" in normalized_payload:
            normalized_payload["featured_image"] = self._resolve_guest_media_url(
                normalized_payload.get("featured_image")
            )

        our_story = normalized_payload.get("our_story")
        if isinstance(our_story, dict) and "image_url" in our_story:
            normalized_payload["our_story"] = {
                **our_story,
                "image_url": self._resolve_guest_media_url(our_story.get("image_url")),
            }

        wedding_party = normalized_payload.get("wedding_party")
        if isinstance(wedding_party, list):
            normalized_payload["wedding_party"] = [
                {
                    **member,
                    "image_url": self._resolve_guest_media_url(member.get("image_url")),
                }
                if isinstance(member, dict) and "image_url" in member
                else member
                for member in wedding_party
            ]

        return normalized_payload

    @staticmethod
    def _project_typed_fields(
        value: Any,
        allowed_fields: dict[str, type],
    ) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None

        return {
            field: value[field]
            for field, expected_type in allowed_fields.items()
            if field in value and isinstance(value[field], expected_type)
        }

    def _project_public_events(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []

        projected_events = []
        for event in value:
            projected_event = self._project_typed_fields(
                event,
                self._public_event_fields,
            )
            if projected_event is None:
                continue

            details = self._project_typed_fields(
                event.get("details"),
                self._public_event_detail_fields,
            )
            if details:
                projected_event["details"] = details

            if projected_event:
                projected_events.append(projected_event)

        return projected_events

    def _project_public_rsvp_config(self, value: Any) -> dict[str, Any] | None:
        projected = self._project_typed_fields(value, self._public_rsvp_fields)
        if projected is None:
            return None

        hide_phone_numbers = value.get("hide_phone_numbers") is not False
        projected["hide_phone_numbers"] = hide_phone_numbers

        phone_numbers = value.get("phone_numbers")
        if not hide_phone_numbers and isinstance(phone_numbers, list):
            projected["phone_numbers"] = [
                phone.strip()
                for phone in phone_numbers
                if isinstance(phone, str) and phone.strip()
            ]

        return projected

    def _project_public_dict_list(
        self,
        value: Any,
        allowed_fields: dict[str, type],
    ) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []

        projected_items = []
        for item in value:
            projected_item = self._project_typed_fields(item, allowed_fields)
            if projected_item:
                projected_items.append(projected_item)
        return projected_items

    def _project_guest_facing_wedding(
        self,
        wedding: dict[str, Any],
    ) -> dict[str, Any]:
        """Build the explicit wedding contract used by every guest access path."""

        projected = (
            self._project_typed_fields(
                wedding,
                self._public_wedding_scalar_fields,
            )
            or {}
        )

        wedding_id = wedding.get("_id") or wedding.get("id")
        if wedding_id is not None:
            projected["id"] = str(wedding_id)

        if isinstance(wedding.get("events"), list):
            projected["events"] = self._project_public_events(wedding["events"])

        rsvp_config = self._project_public_rsvp_config(wedding.get("rsvp_config"))
        if rsvp_config is not None:
            projected["rsvp_config"] = rsvp_config

        for field, allowed_fields in (
            ("registries", self._public_registry_fields),
            ("faqs", self._public_faq_fields),
            ("wedding_party", self._public_wedding_party_fields),
        ):
            if isinstance(wedding.get(field), list):
                projected[field] = self._project_public_dict_list(
                    wedding[field],
                    allowed_fields,
                )

        for field, allowed_fields in (
            ("theme_config", self._public_theme_fields),
            ("our_story", self._public_story_fields),
        ):
            projected_value = self._project_typed_fields(
                wedding.get(field),
                allowed_fields,
            )
            if projected_value:
                projected[field] = projected_value

        featured_image = wedding.get("featured_image")
        if isinstance(featured_image, str):
            projected["featured_image"] = featured_image

        venue = wedding.get("venue")
        if isinstance(venue, str):
            projected["venue"] = venue
        else:
            projected_venue = self._project_typed_fields(
                venue,
                self._public_venue_fields,
            )
            if projected_venue:
                projected["venue"] = projected_venue

        projected["privacy_mode"] = self._resolve_privacy_mode(wedding)
        return projected

    def _serialize_wedding_response(self, wedding: dict[str, Any]) -> dict[str, Any]:
        return self._normalize_guest_media_fields(
            self._project_guest_facing_wedding(wedding)
        )

    @staticmethod
    def _resolve_privacy_mode(wedding: dict[str, Any]) -> str:
        """Resolve one fail-closed mode for serialization and authorization."""

        privacy_settings = wedding.get("privacy_settings")
        nested_mode = (
            privacy_settings.get("privacy_mode")
            if isinstance(privacy_settings, dict)
            else None
        )
        return (
            nested_mode
            if nested_mode in {"public", "password", "private"}
            else "private"
        )

    @classmethod
    def _serialize_guest_response(
        cls,
        guest: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not guest:
            return None

        guest_response = (
            cls._project_typed_fields(
                guest,
                cls._guest_response_fields,
            )
            or {}
        )
        guest_id = guest.get("id") or guest.get("_id")
        if guest_id is not None:
            guest_response["id"] = str(guest_id)
        # Keep a final defense at the serialization boundary even though the
        # explicit allowlist above cannot select the invite credential.
        guest_response.pop("token", None)
        return guest_response

    @staticmethod
    def _mongo_identifier_variants(identifier: Any) -> list[Any]:
        """Return string/ObjectId variants for legacy mixed-ID collections."""

        normalized = str(identifier)
        variants: list[Any] = [normalized]
        if ObjectId.is_valid(normalized):
            variants.append(ObjectId(normalized))
        return variants

    def _serialize_rsvp_plus_one(self, plus_one: dict[str, Any]) -> dict[str, Any]:
        projected = (
            self._project_typed_fields(plus_one, self._rsvp_plus_one_fields) or {}
        )
        attending = plus_one.get("attending")
        projected["attending"] = (
            [event for event in attending if isinstance(event, str)]
            if isinstance(attending, list)
            else []
        )
        return projected

    async def invalidate_wedding_privacy_info(self, slug: str | None) -> None:
        """Invalidate cached privacy bootstrap data for a wedding slug."""
        normalized_slug = self._sanitize_input(slug or "", "slug", max_length=100)
        if not normalized_slug:
            return

        await cache.delete(CacheKeys.wedding_privacy_info(normalized_slug))

    async def _load_rsvp_data(
        self,
        guest_id: str,
        wedding_id: str,
    ) -> dict[str, Any] | None:
        guest_id_variants = self._mongo_identifier_variants(guest_id)
        wedding_id_variants = self._mongo_identifier_variants(wedding_id)
        existing_rsvp = await self.rsvp_collection.find_one(
            {
                "guest_id": {"$in": guest_id_variants},
                "wedding_id": {"$in": wedding_id_variants},
            }
        )

        if not existing_rsvp:
            return None

        plus_ones_cursor = self.plus_ones_collection.find(
            {
                "guest_id": {"$in": guest_id_variants},
                "$or": [
                    {"wedding_id": {"$in": wedding_id_variants}},
                    # Older plus-one rows predate wedding_id. Guest IDs are
                    # globally unique and ownership was verified before this
                    # read, so this is the narrow compatibility fallback.
                    {"wedding_id": {"$exists": False}},
                ],
            }
        )
        plus_ones = [
            self._serialize_rsvp_plus_one(plus_one)
            for plus_one in await plus_ones_cursor.to_list(length=20)
            if isinstance(plus_one, dict)
        ]
        attending = existing_rsvp.get("attending")

        response: dict[str, Any] = {
            "has_rsvp": True,
            "attending": (
                [event for event in attending if isinstance(event, str)]
                if isinstance(attending, list)
                else []
            ),
            "plus_ones": plus_ones,
        }
        submitted_at = existing_rsvp.get("submitted_at")
        if isinstance(submitted_at, (str, datetime)):
            response["submitted_at"] = submitted_at
        if isinstance(existing_rsvp.get("dietary"), str):
            response["dietary"] = existing_rsvp["dietary"]
        return response

    async def get_session_access(
        self,
        *,
        slug: str,
        wedding_id: str,
        auth_method: str,
        guest_id: str | None = None,
        otp_verified: bool = False,
    ) -> dict[str, Any]:
        slug = self._sanitize_input(slug, "slug", max_length=100)

        wedding = await self.wedding_service.get_wedding_by_slug(slug)
        if not wedding:
            raise HTTPException(status_code=404, detail="Wedding not found")

        if str(wedding.get("_id")) != str(wedding_id):
            raise HTTPException(
                status_code=403,
                detail="Guest access session does not match this wedding",
            )

        guest_response = None
        rsvp_data = None

        if guest_id:
            guest = await self.guests_collection.find_one(
                {
                    "_id": {"$in": self._mongo_identifier_variants(guest_id)},
                    "wedding_id": {"$in": self._mongo_identifier_variants(wedding_id)},
                }
            )
            if not guest:
                raise HTTPException(
                    status_code=403,
                    detail="Guest access session does not match this wedding",
                )
            if str(guest.get("wedding_id")) != str(wedding_id):
                raise HTTPException(
                    status_code=403,
                    detail="Guest access session does not match this wedding",
                )

            guest_response = self._serialize_guest_response(guest)
            if guest_response is not None:
                rsvp_data = await self._load_rsvp_data(
                    str(guest_response["id"]),
                    str(wedding_id),
                )

        return {
            "access": True,
            "wedding": self._serialize_wedding_response(wedding),
            "guest": guest_response,
            "rsvp": rsvp_data,
            "auth_method": auth_method,
            "otp_verified": otp_verified,
        }

    def _sanitize_input(
        self, value: str, field_name: str, max_length: int = 255
    ) -> str:
        """Sanitize user input to prevent injection attacks"""
        if not value or not isinstance(value, str):
            return ""

        # Trim and limit length
        sanitized = value.strip()[:max_length]

        # Remove potentially dangerous characters for NoSQL injection
        # Allow alphanumeric, spaces, and common punctuation
        if field_name in ["name", "slug"]:
            # More restrictive for names and slugs
            sanitized = re.sub(r"[^\w\s\-\.]", "", sanitized)

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
        verification_data: dict[str, Any],
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
            or ("password_attempt" if verification_data.get("password") else None)
            or "anonymous"
        )

        scoped_identifier = f"{slug}:{rate_limit_identifier}"
        return scoped_identifier, scoped_identifier

    def _check_memory_rate_limit(
        self, rate_limit_key: str, max_attempts: int, window_seconds: int
    ) -> bool:
        current_time = datetime.now(UTC)
        attempts = self.__class__._failed_attempts
        attempt_data = attempts.get(rate_limit_key)

        if not attempt_data:
            return True

        time_since_last = (current_time - attempt_data["last_attempt"]).total_seconds()
        if time_since_last >= window_seconds:
            attempts.pop(rate_limit_key, None)
            return True

        if attempt_data.get("count", 0) >= max_attempts:
            security_logger.warning(
                "Rate limit exceeded for namespace key: %s",
                rate_limit_key.rsplit(":", 1)[-1],
            )
            return False

        return True

    def _record_memory_failed_attempt(self, rate_limit_key: str, window_seconds: int):
        current_time = datetime.now(UTC)
        attempts = self.__class__._failed_attempts
        attempt_data = attempts.get(rate_limit_key)

        if attempt_data:
            time_since_last = (
                current_time - attempt_data["last_attempt"]
            ).total_seconds()
            if time_since_last >= window_seconds:
                attempts[rate_limit_key] = {"count": 1, "last_attempt": current_time}
                return

            attempt_data["count"] += 1
            attempt_data["last_attempt"] = current_time
        else:
            attempts[rate_limit_key] = {"count": 1, "last_attempt": current_time}

    def _acquire_memory_lock(
        self, lock_key: str, lock_token: str, lock_seconds: int
    ) -> bool:
        current_time = datetime.now(UTC)
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
        current_time = datetime.now(UTC)
        lock_data = self.__class__._attempt_locks.get(lock_key)

        if not lock_data:
            return

        if lock_data["expires_at"] <= current_time or lock_data["token"] == lock_token:
            self.__class__._attempt_locks.pop(lock_key, None)

    async def _acquire_attempt_lock(
        self,
        identifier: str,
        namespace: str = "guest_access",
        lock_seconds: int = 0,
    ) -> str | None:
        duration = lock_seconds or self._attempt_lock_duration
        lock_key = self._build_attempt_lock_key(namespace, identifier)
        lock_token = secrets.token_hex(16)

        if cache.enabled and cache.redis_client:
            redis_result = await cache.acquire_lock(
                lock_key, lock_token, expire=duration
            )
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
        max_attempts: int | None = None,
        window_seconds: int | None = None,
    ) -> bool:
        """Check if request is rate limited. Returns True if allowed."""
        limit = max_attempts or self._default_max_attempts
        window = window_seconds or self._default_lockout_duration
        rate_limit_key = self._build_rate_limit_key(namespace, identifier)

        if cache.enabled and cache.redis_client:
            try:
                current_count = await cache.get(rate_limit_key, default=0)
                if int(current_count or 0) >= limit:
                    security_logger.warning(
                        "Rate limit exceeded for namespace: %s", namespace
                    )
                    return False
                return True
            except Exception as exc:
                security_logger.warning(
                    "Redis rate limit check failed for %s: %s", namespace, exc
                )

        return self._check_memory_rate_limit(rate_limit_key, limit, window)

    async def _record_failed_attempt(
        self,
        identifier: str,
        namespace: str = "guest_access",
        max_attempts: int | None = None,
        window_seconds: int | None = None,
    ):
        """Record a failed authentication attempt"""
        window = window_seconds or self._default_lockout_duration
        rate_limit_key = self._build_rate_limit_key(namespace, identifier)

        if cache.enabled and cache.redis_client:
            current_count = await cache.increment(rate_limit_key, expire=window)
            if current_count is not None:
                return

        self._record_memory_failed_attempt(rate_limit_key, window)

    async def _reset_failed_attempts(
        self, identifier: str, namespace: str = "guest_access"
    ):
        """Reset failed attempts after successful authentication"""
        rate_limit_key = self._build_rate_limit_key(namespace, identifier)

        if cache.enabled and cache.redis_client:
            await cache.delete(rate_limit_key)

        self.__class__._failed_attempts.pop(rate_limit_key, None)

    async def _log_security_event(self, event_type: str, details: dict[str, Any]):
        """Log security events for monitoring - database only, no console logging of sensitive data"""
        try:
            log_entry = {
                "event_type": event_type,
                "timestamp": datetime.now(UTC),
                "details": details,
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
    ) -> dict[str, Any]:
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
        lock_token = await self._acquire_attempt_lock(
            lock_identifier, namespace="rsvp_token_access"
        )
        if not lock_token:
            raise HTTPException(
                status_code=429,
                detail="Verification already in progress. Please try again.",
            )

        try:
            if not await self._check_rate_limit(
                rate_limit_identifier, namespace="rsvp_token_access"
            ):
                await self._log_security_event("RSVP_TOKEN_RATE_LIMIT", {"slug": slug})
                raise HTTPException(
                    status_code=429, detail="Too many attempts. Please try again later."
                )

            # Get wedding by slug
            wedding = await self.wedding_service.get_wedding_by_slug(slug)
            if not wedding:
                raise HTTPException(status_code=404, detail="Wedding not found")

            # Look up guest by token - this is the ONLY check needed
            guest = await self.guest_service.get_guest_by_token(token, wedding["_id"])

            if not guest:
                await self._record_failed_attempt(
                    rate_limit_identifier, namespace="rsvp_token_access"
                )
                await self._log_security_event("RSVP_TOKEN_INVALID", {"slug": slug})
                raise HTTPException(status_code=403, detail="Invalid invite token")

            # Success - reset rate limit and log
            await self._reset_failed_attempts(
                rate_limit_identifier, namespace="rsvp_token_access"
            )
            await self._log_security_event(
                "RSVP_TOKEN_SUCCESS",
                {
                    "slug": slug,
                    "wedding_id": str(wedding.get("_id")),
                    "guest_id": str(guest.get("id")),
                },
            )

            guest = self._serialize_guest_response(guest)
            if not guest:
                raise HTTPException(status_code=404, detail="Guest not found")
            guest_id_str = str(guest.get("id"))
            rsvp_data = await self._load_rsvp_data(
                guest_id_str,
                str(wedding.get("_id")),
            )

            return {
                "access": True,
                "wedding": self._serialize_wedding_response(wedding),
                "guest": guest,
                "rsvp": rsvp_data,
                "auth_method": "token",
            }

        except HTTPException:
            raise
        except Exception as e:
            security_logger.error(f"RSVP token access error: {type(e).__name__}")
            raise HTTPException(status_code=500, detail="Error accessing RSVP")
        finally:
            await self._release_attempt_lock(
                lock_identifier, lock_token, namespace="rsvp_token_access"
            )

    # =========================================================================
    # WEDDING PAGE ACCESS - Privacy-based verification for viewing wedding page
    # Used by: POST /weddings/verify-guest-access/{slug}
    # Purpose: Verify visitor is on guest list before showing wedding page
    # =========================================================================
    async def verify_wedding_page_access(
        self,
        slug: str,
        verification_data: dict[str, Any],
    ) -> dict[str, Any]:
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
        lock_token = await self._acquire_attempt_lock(
            lock_identifier, namespace="guest_page_access"
        )
        if not lock_token:
            raise HTTPException(
                status_code=429,
                detail="Verification already in progress. Please try again.",
            )

        try:
            if not await self._check_rate_limit(
                rate_limit_identifier, namespace="guest_page_access"
            ):
                await self._log_security_event("RATE_LIMIT_EXCEEDED", {"slug": slug})
                raise HTTPException(
                    status_code=429,
                    detail="Too many failed attempts. Please try again later.",
                )

            # Get wedding by slug
            wedding = await self.wedding_service.get_wedding_by_slug(slug)
            if not wedding:
                raise HTTPException(status_code=404, detail="Wedding not found")

            # Check privacy settings
            privacy_settings = wedding.get("privacy_settings")
            if not isinstance(privacy_settings, dict):
                privacy_settings = {}
            privacy_mode = self._resolve_privacy_mode(wedding)

            # If wedding is public, grant access immediately (no token was provided or token failed)
            if privacy_mode == "public":
                return {
                    "access": True,
                    "wedding": self._serialize_wedding_response(wedding),
                    "guest": None,
                    "auth_method": "public",
                }

            # If password protected, check password
            if privacy_mode == "password":
                provided_password = verification_data.get("password", "")
                stored_password = privacy_settings.get("password_protection", "")

                # Use constant-time comparison to prevent timing attacks
                if (
                    provided_password
                    and stored_password
                    and secrets.compare_digest(
                        str(provided_password), str(stored_password)
                    )
                ):
                    await self._reset_failed_attempts(
                        rate_limit_identifier, namespace="guest_page_access"
                    )
                    await self._log_security_event(
                        "PASSWORD_AUTH_SUCCESS",
                        {"slug": slug, "wedding_id": str(wedding.get("_id"))},
                    )
                    return {
                        "access": True,
                        "wedding": self._serialize_wedding_response(wedding),
                        "guest": None,
                        "auth_method": "password",
                    }
                elif provided_password:
                    # Password was provided but incorrect
                    await self._record_failed_attempt(
                        rate_limit_identifier, namespace="guest_page_access"
                    )
                    await self._log_security_event(
                        "PASSWORD_AUTH_FAILED", {"slug": slug}
                    )

            # For private mode, try different verification methods
            # Note: Token verification is handled above (before privacy mode checks)
            # If we reach here with a token, it means the token lookup failed
            if privacy_mode == "private":
                # OTP verification (replaces name/phone verification)
                # Check if this is an OTP verification
                otp_code = self._sanitize_input(
                    verification_data.get("otp_code") or "", "otp", max_length=10
                )
                contact = self._sanitize_input(
                    verification_data.get("contact") or "",
                    "contact",
                    max_length=100,
                )

                if otp_code and contact:
                    # Verify OTP
                    try:
                        otp_result = await self.otp_service.verify_otp(
                            wedding_id=wedding["_id"],
                            contact=contact,
                            otp_code=otp_code,
                        )
                        if otp_result.get("success"):
                            await self._reset_failed_attempts(
                                rate_limit_identifier, namespace="guest_page_access"
                            )
                            await self._log_security_event(
                                "OTP_AUTH_SUCCESS",
                                {
                                    "slug": slug,
                                    "wedding_id": str(wedding.get("_id")),
                                    "contact_type": otp_result.get(
                                        "auth_method", "otp"
                                    ),
                                },
                            )
                            guest_response = self._serialize_guest_response(
                                otp_result.get("guest")
                            )
                            return {
                                "access": True,
                                "wedding": self._serialize_wedding_response(wedding),
                                "guest": guest_response,
                                "auth_method": otp_result.get("auth_method", "otp"),
                            }
                        else:
                            await self._record_failed_attempt(
                                rate_limit_identifier, namespace="guest_page_access"
                            )
                            await self._log_security_event(
                                "OTP_AUTH_FAILED", {"slug": slug}
                            )
                    except Exception:
                        security_logger.warning("OTP verification error")
                        await self._record_failed_attempt(
                            rate_limit_identifier, namespace="guest_page_access"
                        )

                # Method 3: Request OTP (when phone/email provided without code)
                phone = self._sanitize_input(
                    verification_data.get("phone") or "",
                    "contact",
                    max_length=100,
                )
                email = self._sanitize_input(
                    verification_data.get("email") or "",
                    "contact",
                    max_length=100,
                )

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
                        "message": "Verification code will be sent to your contact",
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
                    "require_phone_verification": privacy_settings.get(
                        "require_phone_verification", True
                    ),
                    "require_name_verification": privacy_settings.get(
                        "require_name_verification", True
                    ),
                    "allow_guest_sharing": privacy_settings.get(
                        "allow_guest_sharing", False
                    ),
                },
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error verifying guest access: {e!s}"
            )
        finally:
            await self._release_attempt_lock(
                lock_identifier, lock_token, namespace="guest_page_access"
            )

    def _find_guest_by_verification(
        self, wedding_id: str, name: str, phone: str, privacy_settings: dict
    ) -> dict | None:
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
        digits_only = re.sub(r"\D", "", phone)

        # Handle US phone numbers
        if len(digits_only) == 10:
            return f"+1{digits_only}"
        elif (
            len(digits_only) == 11
            and digits_only.startswith("1")
            or digits_only.startswith("1")
            and len(digits_only) > 11
        ):
            return f"+{digits_only}"

        # For other formats, just prepend + if not present
        if not phone.startswith("+"):
            return f"+{digits_only}"

        return phone

    async def _log_guest_verification(
        self, wedding_id: str, guest_id: str, method: str
    ):
        """Log guest verification for analytics"""
        try:
            log_entry = {
                "wedding_id": wedding_id,
                "guest_id": guest_id,
                "verification_method": method,
                "timestamp": datetime.now(UTC),
                "type": "guest_verification",
            }
            await mongo.db["access_logs"].insert_one(log_entry)
        except Exception:
            # Silently fail - logging shouldn't break the main flow
            pass

    async def get_wedding_privacy_info(self, slug: str) -> dict[str, Any]:
        """Get privacy information about a wedding without granting access"""
        try:
            cache_key = CacheKeys.wedding_privacy_info(slug)
            cached_response = await cache.get(cache_key)
            if (
                isinstance(cached_response, dict)
                and cached_response.get("schema_version")
                == self._privacy_info_cache_schema_version
                and isinstance(cached_response.get("response"), dict)
            ):
                return cached_response["response"]

            wedding = await self.weddings_collection.find_one(
                {"slug": slug},
                {
                    "couple_names": 1,
                    "date": 1,
                    "privacy_settings": 1,
                    "featured_image": 1,
                    "theme_config": 1,
                    "rsvp_config": 1,
                    "events": 1,
                    "registries": 1,
                    "faqs": 1,
                    "our_story": 1,
                    "venue": 1,
                    "wedding_party": 1,
                },
            )
            if not wedding:
                raise HTTPException(status_code=404, detail="Wedding not found")

            privacy_mode = self._resolve_privacy_mode(wedding)

            # Log privacy mode for debugging - don't expose settings (may contain password)
            security_logger.debug(f"Privacy info request for slug: {slug}")

            # Use the same explicit guest-facing contract as verified access
            # responses so nested planner and tenant data cannot escape via
            # the unauthenticated privacy bootstrap route.
            resolved_wedding = self._serialize_wedding_response(wedding)

            # Base response with privacy info
            response = {
                "id": resolved_wedding.get("id"),
                "couple_names": resolved_wedding.get("couple_names"),
                "privacy_mode": privacy_mode,
                "requires_password": privacy_mode == "password",
                "requires_guest_verification": privacy_mode == "private",
                "verification_requirements": {
                    "otp_enabled": True,
                    "supports_phone": True,
                    "supports_email": True,
                },
            }

            # For public weddings, include full wedding data since no verification needed
            if privacy_mode == "public":
                response.update(
                    {
                        "date": resolved_wedding.get("date"),
                        "timezone": resolved_wedding.get("timezone"),
                        "featured_image": resolved_wedding.get("featured_image"),
                        "theme_config": resolved_wedding.get("theme_config"),
                        "rsvp_config": resolved_wedding.get("rsvp_config"),
                        "events": resolved_wedding.get("events", []),
                        "registries": resolved_wedding.get("registries", []),
                        "faqs": resolved_wedding.get("faqs", []),
                        "our_story": resolved_wedding.get("our_story"),
                        "venue": resolved_wedding.get("venue"),
                        "wedding_party": resolved_wedding.get("wedding_party", []),
                    }
                )

            response = self._normalize_guest_media_fields(response)
            await cache.set(
                cache_key,
                {
                    "schema_version": self._privacy_info_cache_schema_version,
                    "response": response,
                },
                expire=self._privacy_info_cache_ttl,
            )
            return response

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error getting wedding privacy info: {e!s}"
            )

    async def update_wedding_privacy_settings(
        self, wedding_id: str, privacy_settings: dict[str, Any]
    ) -> dict[str, Any]:
        """Update privacy settings for a wedding (admin only)"""
        try:
            # Validate privacy mode
            valid_modes = ["public", "password", "private"]
            privacy_mode = privacy_settings.get("privacy_mode", "private")
            if privacy_mode not in valid_modes:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid privacy mode. Must be one of: {valid_modes}",
                )

            # If password mode, ensure password is provided
            if privacy_mode == "password" and not privacy_settings.get(
                "password_protection"
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Password is required for password-protected weddings",
                )

            existing_wedding = await self.weddings_collection.find_one(
                {"_id": wedding_id}, {"slug": 1}
            )

            # Update wedding with new privacy settings
            result = await self.weddings_collection.update_one(
                {"_id": wedding_id},
                {
                    "$set": {
                        "privacy_settings": privacy_settings,
                        "updated_at": datetime.now(UTC),
                    }
                },
            )

            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="Wedding not found")

            await invalidate_wedding_projection_caches(
                wedding_id,
                previous_slug=(
                    existing_wedding.get("slug") if existing_wedding else None
                ),
            )

            return {"message": "Privacy settings updated successfully"}

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error updating privacy settings: {e!s}"
            )

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
    ) -> dict[str, Any]:
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
                "message": "If you're on the guest list, you'll receive your RSVP link shortly.",
            }

        # Rate limiting by contact hash (more restrictive for this feature)
        contact_hash = hashlib.sha256(contact.encode()).hexdigest()[:16]
        rate_limit_key = f"{slug}:{contact_hash}"
        lock_identifier = rate_limit_key
        lock_token = await self._acquire_attempt_lock(
            lock_identifier, namespace="rsvp_link_request"
        )

        if not lock_token:
            return {
                "success": True,
                "message": "If you're on the guest list, you'll receive your RSVP link shortly.",
            }

        try:
            if not await self._check_rate_limit(
                rate_limit_key,
                namespace="rsvp_link_request",
                max_attempts=self._rsvp_link_max_attempts,
                window_seconds=self._rsvp_link_lockout_duration,
            ):
                await self._log_security_event(
                    "RSVP_LINK_RATE_LIMITED",
                    {"slug": slug, "contact_type": contact_type},
                )
                # Return success to prevent enumeration
                return {
                    "success": True,
                    "message": "If you're on the guest list, you'll receive your RSVP link shortly.",
                }

            # Get wedding by slug
            wedding = await self.wedding_service.get_wedding_by_slug(slug)
            if not wedding:
                return {
                    "success": True,
                    "message": "If you're on the guest list, you'll receive your RSVP link shortly.",
                }

            wedding_id = wedding.get("_id")

            # Look up guest by contact
            guest = None
            digits_only = ""  # Initialize for use in sending phase
            if contact_type == "phone":
                # Phones may be stored in various formats, try multiple lookups
                # Extract digits only from input
                digits_only = re.sub(r"\D", "", contact)

                # Try different phone formats that might be in the database
                phone_variants = [
                    contact.strip(),  # Original input
                    digits_only,  # Just digits
                    (
                        f"+1{digits_only}" if len(digits_only) == 10 else digits_only
                    ),  # E.164 format
                    (
                        f"+{digits_only}"
                        if digits_only.startswith("1") and len(digits_only) == 11
                        else digits_only
                    ),
                ]
                # Remove duplicates while preserving order
                phone_variants = list(dict.fromkeys(phone_variants))

                for phone_variant in phone_variants:
                    guest = await self.guests_collection.find_one(
                        {"wedding_id": wedding_id, "phone": phone_variant}
                    )
                    if guest:
                        break
            else:
                # Email lookup - try case-insensitive with regex
                email_cleaned = contact.strip()
                guest = await self.guests_collection.find_one(
                    {
                        "wedding_id": wedding_id,
                        "email": {
                            "$regex": f"^{re.escape(email_cleaned)}$",
                            "$options": "i",
                        },
                    }
                )

            if not guest:
                # Log but return success to prevent enumeration
                await self._log_security_event(
                    "RSVP_LINK_GUEST_NOT_FOUND",
                    {"slug": slug, "contact_type": contact_type},
                )
                return {
                    "success": True,
                    "message": "If you're on the guest list, you'll receive your RSVP link shortly.",
                }

            # Guest found - build RSVP URL
            token = guest.get("token")
            if not token:
                security_logger.warning(
                    f"Guest found but missing token for wedding {slug}"
                )
                return {
                    "success": True,
                    "message": "If you're on the guest list, you'll receive your RSVP link shortly.",
                }

            frontend_url = os.getenv(
                "FRONTEND_URL", "https://thespecialwedding.io"
            ).rstrip("/")
            rsvp_url = (
                f"{frontend_url}/otp/verify"
                f"?slug={quote(slug, safe='')}"
                f"&token={quote(token, safe='')}"
            )
            couple_names = wedding.get("couple_names", "the couple")
            guest_name = guest.get("name", "Guest")

            # Send via appropriate channel
            send_success = False
            if contact_type == "phone":
                try:
                    from app.services.reminder_service_twilio import (
                        TwilioReminderService,
                    )

                    twilio_service = TwilioReminderService()
                    message = (
                        f"Hi {guest_name}! Here's your personal RSVP link for "
                        f"{couple_names}'s wedding: {rsvp_url} Need help? Reply HELP "
                        "to this text or use Get Help on the wedding website."
                    )
                    # Use digits_only for Twilio - it will add +1 prefix for E.164 format
                    result = twilio_service._send_sms(digits_only, message)
                    send_success = result.get("status") == "success"
                except Exception as e:
                    security_logger.error(f"Failed to send SMS: {e!s}")
            else:
                try:
                    from app.services.email_service_resend import ResendEmailService

                    email_service = ResendEmailService()
                    html_content = self._generate_rsvp_link_email_html(
                        guest_name=guest_name,
                        rsvp_url=rsvp_url,
                        couple_names=couple_names,
                    )
                    result = await email_service.send_email(
                        to_email=contact,
                        subject=f"Your RSVP Link - {couple_names}'s Wedding",
                        html_content=html_content,
                        wedding_id=str(wedding_id),
                        email_type="rsvp_link_request",
                    )
                    send_success = result.get("success", False)
                except Exception as e:
                    security_logger.error(f"Failed to send email: {e!s}")

            # Log success/failure
            if send_success:
                await self._log_security_event(
                    "RSVP_LINK_SENT",
                    {
                        "slug": slug,
                        "contact_type": contact_type,
                        "wedding_id": str(wedding_id),
                        "guest_id": str(guest.get("_id")),
                    },
                )
            else:
                await self._log_security_event(
                    "RSVP_LINK_SEND_FAILED",
                    {"slug": slug, "contact_type": contact_type},
                )

            # Always return success message
            return {
                "success": True,
                "message": "If you're on the guest list, you'll receive your RSVP link shortly.",
            }

        except Exception as e:
            security_logger.error(f"Error in request_and_send_rsvp_link: {e!s}")
            return {
                "success": True,
                "message": "If you're on the guest list, you'll receive your RSVP link shortly.",
            }
        finally:
            await self._release_attempt_lock(
                lock_identifier, lock_token, namespace="rsvp_link_request"
            )

    def _generate_rsvp_link_email_html(
        self, guest_name: str, rsvp_url: str, couple_names: str
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
                                    <p style="color: #64748b; font-size: 14px; line-height: 1.6; margin: 30px 0 0;">
                                        Need help with your invitation? Reply <strong>HELP</strong> to a wedding text message,
                                        or use the <strong>Get Help</strong> button on the wedding website so the planner can text you from the message inbox.
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
    async def verify_guest_access(
        self, slug: str, verification_data: dict[str, Any]
    ) -> dict[str, Any]:
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
