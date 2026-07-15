from __future__ import annotations

import hashlib
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, ClassVar, Dict, Optional

from fastapi import HTTPException

from app.core.cache import CacheKeys, cache
from app.core.database import mongo
from app.constants.support_conversations import (
    CONVERSATION_KIND_FIELD,
    GUEST_SMS_KIND,
    guest_sms_ticket_scope,
)
from app.services.sms_service import SMSService
from app.utils.contact_sanitizer import sanitize_phone
from app.utils.support_inbox_links import build_support_inbox_path

logger = logging.getLogger(__name__)


class GuestHelpRequestService:
    """Creates guest help requests in the planner SMS support inbox."""

    _memory_rate_limits: ClassVar[dict[str, list[float]]] = {}

    max_help_requests_per_window = 3
    rate_limit_window_seconds = 600

    def __init__(self) -> None:
        self.weddings_collection = mongo.db["weddings"]
        self.guests_collection = mongo.get_guest_collection()
        self.support_tickets_collection = mongo.db["support_tickets"]
        self.sms_service_factory = SMSService
        self.notification_service_factory = self._default_notification_service

    @staticmethod
    def _default_notification_service():
        from app.services.planner_notification_service import (
            planner_notification_service,
        )

        return planner_notification_service

    @staticmethod
    def _normalize_phone_e164(phone: str) -> Optional[str]:
        sanitized = sanitize_phone(phone)
        if not sanitized:
            return None
        digits_only = "".join(ch for ch in sanitized if ch.isdigit())
        if sanitized.startswith("+") and 10 <= len(digits_only) <= 15:
            return f"+{digits_only}"
        if len(digits_only) == 10:
            return f"+1{digits_only}"
        if len(digits_only) == 11 and digits_only.startswith("1"):
            return f"+{digits_only}"
        if 10 <= len(digits_only) <= 15:
            return f"+{digits_only}"
        return None

    @staticmethod
    def _clean_text(value: str, *, max_length: int) -> str:
        cleaned = re.sub(r"[\x00-\x1f\x7f]", " ", value or "")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned[:max_length]

    @staticmethod
    def _phone_lookup_variants(phone: str) -> list[str]:
        sanitized = sanitize_phone(phone)
        if not sanitized:
            return []

        digits_only = "".join(ch for ch in sanitized if ch.isdigit())
        variants = {sanitized, digits_only, f"+{digits_only}"}

        if len(digits_only) == 10:
            variants.add(f"+1{digits_only}")
            variants.add(f"1{digits_only}")
        elif len(digits_only) == 11 and digits_only.startswith("1"):
            variants.add(digits_only[1:])
            variants.add(f"+{digits_only}")

        return [variant for variant in variants if variant]

    @staticmethod
    def _rate_limit_identifier(slug: str, phone: str) -> str:
        raw_identifier = f"{slug.lower()}:{phone}"
        return hashlib.sha256(raw_identifier.encode("utf-8")).hexdigest()[:32]

    def _check_memory_rate_limit(self, identifier: str) -> bool:
        now = time.time()
        window_start = now - self.rate_limit_window_seconds
        attempts = [
            timestamp
            for timestamp in self._memory_rate_limits.get(identifier, [])
            if timestamp >= window_start
        ]
        if len(attempts) >= self.max_help_requests_per_window:
            self._memory_rate_limits[identifier] = attempts
            return False
        attempts.append(now)
        self._memory_rate_limits[identifier] = attempts
        return True

    async def _check_rate_limit(self, slug: str, phone: str) -> None:
        identifier = self._rate_limit_identifier(slug, phone)
        cache_key = CacheKeys.rate_limit(identifier, "guest_help_request_contact")

        if cache.enabled and cache.redis_client:
            count = await cache.increment(
                cache_key, expire=self.rate_limit_window_seconds
            )
            if count is not None:
                if count > self.max_help_requests_per_window:
                    raise HTTPException(
                        status_code=429,
                        detail="Please wait before requesting help again.",
                    )
                return

        if not self._check_memory_rate_limit(identifier):
            raise HTTPException(
                status_code=429,
                detail="Please wait before requesting help again.",
            )

    async def _find_guest(
        self, wedding_id: str, phone: str, full_name: str
    ) -> Optional[dict[str, Any]]:
        phone_variants = self._phone_lookup_variants(phone)
        if not phone_variants:
            return None

        guest = await self.guests_collection.find_one(
            {
                "wedding_id": wedding_id,
                "$or": [{"phone": variant} for variant in phone_variants],
            }
        )
        if guest:
            return guest

        return await self.guests_collection.find_one(
            {
                "wedding_id": wedding_id,
                "name": {"$regex": f"^{re.escape(full_name)}$", "$options": "i"},
            }
        )

    async def create_help_request(
        self,
        *,
        slug: str,
        full_name: str,
        phone: str,
        relationship_to_couple: str,
    ) -> Dict[str, Any]:
        slug = self._clean_text(slug, max_length=100)
        full_name = self._clean_text(full_name, max_length=100)
        relationship_to_couple = self._clean_text(
            relationship_to_couple, max_length=120
        )
        normalized_phone = self._normalize_phone_e164(phone)

        if not slug:
            raise HTTPException(status_code=422, detail="Wedding slug is required.")
        if len(full_name) < 2:
            raise HTTPException(status_code=422, detail="Full name is required.")
        if not normalized_phone:
            raise HTTPException(
                status_code=422, detail="A valid phone number is required."
            )
        if len(relationship_to_couple) < 2:
            raise HTTPException(
                status_code=422,
                detail="Relationship to the couple is required.",
            )

        await self._check_rate_limit(slug, normalized_phone)

        wedding = await self.weddings_collection.find_one(
            {"slug": slug},
            {
                "_id": 1,
                "couple_names": 1,
                "assigned_planner_email": 1,
            },
        )
        if not wedding:
            raise HTTPException(status_code=404, detail="Wedding not found.")

        assigned_to = (wedding.get("assigned_planner_email") or "").strip()
        if not wedding.get("_id") or not assigned_to:
            raise HTTPException(
                status_code=409,
                detail="Guest help is not configured for this wedding.",
            )

        wedding_id = str(wedding.get("_id"))
        couple_names = wedding.get("couple_names") or "the couple"
        guest = await self._find_guest(wedding_id, normalized_phone, full_name)
        now = datetime.now(timezone.utc)

        message = (
            f"Public help request from {full_name} "
            f"({relationship_to_couple}). The guest was asked to reply by SMS "
            "with their question so the planner can respond from the inbox."
        )

        sms_service = self.sms_service_factory()
        provider = sms_service.get_provider_name()
        ticket: Dict[str, Any] = {
            "phone": normalized_phone,
            "message": message,
            "guest_id": str(guest["_id"]) if guest and guest.get("_id") else None,
            "guest_name": guest.get("name") if guest else full_name,
            "relationship_to_couple": relationship_to_couple,
            "wedding_id": wedding_id,
            "wedding_name": couple_names,
            "assigned_to": assigned_to,
            "status": "new",
            "created_at": now,
            "updated_at": now,
            "source": "sms",
            CONVERSATION_KIND_FIELD: GUEST_SMS_KIND,
            "origin": "public_help_form",
            "provider": provider if provider in {"twilio", "telnyx"} else "twilio",
            "message_sid": None,
            "is_read": False,
            "priority": "high",
            "type": "help_request",
            "acknowledgment_sms": {"status": "pending", "sent_at": None},
        }

        insert_result = await self.support_tickets_collection.insert_one(ticket)
        ticket_id = insert_result.inserted_id

        ack_message = (
            f"Thanks {full_name}. Reply to this text with your question for "
            f"{couple_names}'s planner. They will respond from the wedding inbox."
        )
        sms_result = sms_service.send_sms(normalized_phone, ack_message)
        ack_status: Dict[str, Any]
        if sms_result.get("success"):
            ack_status = {
                "status": "sent",
                "sent_at": datetime.now(timezone.utc),
                "provider": sms_result.get("provider"),
                "message_id": sms_result.get("message_id"),
            }
        else:
            ack_status = {
                "status": "failed",
                "sent_at": datetime.now(timezone.utc),
                "provider": sms_result.get("provider"),
                "error": sms_result.get("error", "Unknown SMS error"),
            }

        await self.support_tickets_collection.update_one(
            guest_sms_ticket_scope({"_id": ticket_id}),
            {
                "$set": {
                    "acknowledgment_sms": ack_status,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

        if ack_status["status"] == "failed":
            logger.warning(
                "Guest help acknowledgment SMS failed for ticket %s: %s",
                ticket_id,
                ack_status.get("error"),
            )

        try:
            from app.models.planner_notification import PlannerNotificationTypes

            action_url = build_support_inbox_path(
                conversation="sms_support",
                ticket_id=str(ticket_id),
                wedding_id=wedding_id,
            )
            notification_service = self.notification_service_factory()
            await notification_service.create_notification(
                planner_id=assigned_to,
                notification_type=PlannerNotificationTypes.GUEST_MESSAGE,
                title="Guest Requested Help",
                message=f"{full_name} requested help for {couple_names}.",
                wedding_id=wedding_id,
                metadata={
                    "guest_name": full_name,
                    "guest_id": ticket.get("guest_id"),
                    "ticket_id": str(ticket_id),
                    "origin": "public_help_form",
                    "source": "sms_support",
                },
                priority="high",
                action_url=action_url,
            )
        except Exception as exc:
            logger.warning(
                "Guest help notification failed for ticket %s: %s",
                ticket_id,
                exc,
            )

        return {
            "success": True,
            "message": "Thanks. We sent you a text so the planner can help from the wedding inbox.",
            "ticket_id": str(ticket_id),
        }
