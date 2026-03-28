# app/services/reminder_service_twilio.py

import os
import asyncio
from typing import Optional
from twilio.rest import Client  # type: ignore
from fastapi import HTTPException
from datetime import datetime, timezone
from app.core.database import mongo
from app.utils.contact_sanitizer import normalize_phone_e164
from app.utils.wedding_event_types import normalize_event_type
import logging

# ---------------------------------------------------------------------------
# Throttling configuration
# ---------------------------------------------------------------------------
# Twilio enforces MPS (messages-per-second) limits that depend on your sender
# type.  Limits for US destinations:
#   - Toll-free:        3 MPS (default) – upgradeable to 25+ MPS via Sales
#   - 10DLC long code:  1 MPS (default) – up to ~75 MPS at highest trust
#   - Short code:     100 MPS
#
# Even though Twilio queues messages internally, firing API requests in a
# tight loop risks 429 rate-limit errors and may cause carriers to flag the
# traffic pattern.  The delay below is applied between each Twilio API call
# in bulk send loops.  Override via the SMS_THROTTLE_DELAY_MS env var.
#
# Default 350 ms ≈ ~2.8 req/s – safely under the toll-free 3 MPS limit
# with headroom for Twilio's internal queue processing.  At this rate,
# 7,500 messages would take ~44 minutes to enqueue.
#
# To increase (e.g. after upgrading to high-throughput toll-free):
#   SMS_THROTTLE_DELAY_MS=100  →  10 req/s  (for 25+ MPS toll-free)
#   SMS_THROTTLE_DELAY_MS=50   →  20 req/s  (for short codes)
# ---------------------------------------------------------------------------
SMS_THROTTLE_DELAY_S = float(os.getenv("SMS_THROTTLE_DELAY_MS", "350")) / 1000.0

logger = logging.getLogger(__name__)

try:
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    MESSAGING_SERVICE_SID = os.getenv("TWILIO_MESSAGING_SERVICE_SID")

    missing = [k for k, v in {
        "TWILIO_ACCOUNT_SID": account_sid,
        "TWILIO_AUTH_TOKEN": auth_token,
        "TWILIO_MESSAGING_SERVICE_SID": MESSAGING_SERVICE_SID
    }.items() if not v]

    if missing:
        raise RuntimeError(f"Missing Twilio env vars: {', '.join(missing)}")

    twilio_client = Client(account_sid, auth_token)
    twilio_configured = True
except Exception as e:
    logger.error(f"Failed to initialize Twilio client: {e}")
    twilio_client = None
    MESSAGING_SERVICE_SID = None
    twilio_configured = False


class TwilioReminderService:
    def __init__(self):
        if not twilio_configured:
            raise RuntimeError("Twilio is not configured.")

        self.client = twilio_client
        self.messaging_service_sid = MESSAGING_SERVICE_SID

        # 3. Mongo collections
        self.guest_collection = mongo.get_guest_collection()
        self.rsvp_collection = mongo.db["rsvps"]
        self.plus_one_collection = mongo.db["plus_ones"]
        self.log_collection = mongo.db["reminders_sent"]

    async def send_reminders(self, event_type: str, message: str, target_group: str):
        try:
            event_type = normalize_event_type(event_type)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        if target_group not in {"guests", "plus-ones", "all"}:
            raise HTTPException(status_code=400, detail="Invalid target group")

        logs = []
        now = datetime.now(timezone.utc)
        skipped_no_phone = 0
        skipped_opted_out = 0

        # Pre-fetch all RSVPs attending this event type to avoid N+1 queries
        rsvp_lookup = {}
        async for rsvp in self.rsvp_collection.find({"attending": event_type}):
            rsvp_lookup[rsvp["guest_id"]] = rsvp

        # Guests
        if target_group in {"guests", "all"}:
            async for guest in self.guest_collection.find({}):
                rsvp = rsvp_lookup.get(guest["_id"])
                if rsvp:
                    phone = guest.get("phone")
                    sms_opt_in = guest.get("sms_opt_in", False)
                    if not phone:
                        skipped_no_phone += 1
                        continue
                    if not sms_opt_in:
                        skipped_opted_out += 1
                        continue
                    status = self._send_sms(phone, message)
                    logs.append(self._log(
                        phone,
                        guest["_id"],
                        message,
                        "guest",
                        event_type,
                        status,
                        now,
                    ))
                    # Throttle to stay within Twilio MPS / API rate limits
                    if SMS_THROTTLE_DELAY_S > 0:
                        await asyncio.sleep(SMS_THROTTLE_DELAY_S)

        # Plus-ones
        if target_group in {"plus-ones", "all"}:
            async for po in self.plus_one_collection.find({}):
                if event_type in po.get("attending", []):
                    phone = po.get("phone")
                    sms_opt_in = po.get("sms_opt_in", None)
                    if sms_opt_in is False:  # Explicitly opted out
                        skipped_opted_out += 1
                        continue
                    if not phone:
                        skipped_no_phone += 1
                        continue
                    status = self._send_sms(phone, message)
                    logs.append(self._log(
                        phone,
                        po["guest_id"],
                        message,
                        "plus-one",
                        event_type,
                        status,
                        now,
                    ))
                    # Throttle to stay within Twilio MPS / API rate limits
                    if SMS_THROTTLE_DELAY_S > 0:
                        await asyncio.sleep(SMS_THROTTLE_DELAY_S)

        if logs:
            await self.log_collection.insert_many(logs)

        return {
            "sent": len(logs),
            "skipped_no_phone": skipped_no_phone,
            "skipped_opted_out": skipped_opted_out,
            "provider": "twilio"
        }

    def _send_sms(self, to: str, body: str, max_retries: int = 2) -> dict:
        """
        Send SMS and return both status and message_sid for delivery tracking.
        Includes automatic retry for transient failures (network errors, 5xx).

        Returns:
            dict with "status", "message_sid", "initial_status", and "error_code" keys.
            error_code values: "rate_limited", "invalid_number", "not_configured",
                               "daily_limit", "service_unavailable", "network_error", None
        """
        import time

        if not self.client:
            return {
                "status": "failed: Twilio client is not initialized",
                "message_sid": None,
                "initial_status": None,
                "error_code": "not_configured",
                "retryable": False
            }

        # Sanitize and normalize phone to E.164 format
        normalized = normalize_phone_e164(to)
        if not normalized:
            return {
                "status": f"failed: Invalid phone number: {to!r}",
                "message_sid": None,
                "initial_status": None,
                "error_code": "invalid_number",
                "retryable": False
            }
        to = normalized
        status_callback_url = os.getenv("TWILIO_STATUS_CALLBACK_URL")
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                # Prefer Messaging Service SID; if not set, require a valid from number
                if self.messaging_service_sid:
                    message = self.client.messages.create(
                        messaging_service_sid=self.messaging_service_sid,
                        body=body,
                        to=to,
                        status_callback=status_callback_url
                    )
                else:
                    from_number = os.getenv("TWILIO_FROM_NUMBER") or os.getenv("TWILIO_PHONE_NUMBER")
                    if not from_number:
                        return {
                            "status": "failed: No Twilio sending number configured",
                            "message_sid": None,
                            "initial_status": None,
                            "error_code": "not_configured",
                            "retryable": False
                        }
                    message = self.client.messages.create(
                        from_=from_number,
                        body=body,
                        to=to,
                        status_callback=status_callback_url
                    )

                logger.info(f"Twilio SMS sent to {to}, SID: {message.sid}")
                return {
                    "status": "success",
                    "message_sid": message.sid,
                    "initial_status": message.status,
                    "error_code": None,
                    "retryable": False
                }

            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                error_code_int = getattr(e, 'code', None) or getattr(e, 'status', None)

                # Classify the error
                error_code, retryable = self._classify_twilio_error(error_str, error_code_int)

                if retryable and attempt < max_retries:
                    wait_time = (attempt + 1) * 1.5  # 1.5s, 3s backoff
                    logger.warning(f"Twilio SMS attempt {attempt + 1} failed (retryable), retrying in {wait_time}s: {str(e)}")
                    time.sleep(wait_time)
                    continue

                logger.error(f"Twilio SMS failed to {to} after {attempt + 1} attempt(s): {str(e)}")
                return {
                    "status": f"failed: {str(e)}",
                    "message_sid": None,
                    "initial_status": None,
                    "error_code": error_code,
                    "retryable": retryable
                }

        # Should not reach here, but safety fallback
        return {
            "status": f"failed: {str(last_error)}",
            "message_sid": None,
            "initial_status": None,
            "error_code": "unknown",
            "retryable": False
        }

    @staticmethod
    def _classify_twilio_error(error_str: str, error_code_int) -> tuple:
        """
        Classify a Twilio error into a category and determine if retryable.
        Returns (error_code: str, retryable: bool)
        """
        # Rate limited (429 or Twilio code 20429)
        if '429' in error_str or 'rate limit' in error_str or 'too many requests' in error_str:
            return ("rate_limited", False)

        # Daily message limit exceeded (Twilio code 14101)
        if '14101' in error_str or 'daily' in error_str and 'limit' in error_str:
            return ("daily_limit", False)

        # Invalid phone number (Twilio codes 21211, 21214, 21217, 21612)
        if any(code in error_str for code in ['21211', '21214', '21217', '21612']):
            return ("invalid_number", False)
        if 'not a valid phone' in error_str or 'unverified' in error_str:
            return ("invalid_number", False)

        # Number blocked or unreachable (Twilio codes 21408, 21610, 21611)
        if any(code in error_str for code in ['21408', '21610', '21611']):
            return ("number_blocked", False)

        # Service unavailable (5xx, network issues)
        if '500' in error_str or '502' in error_str or '503' in error_str or '504' in error_str:
            return ("service_unavailable", True)
        if 'timeout' in error_str or 'connection' in error_str or 'network' in error_str:
            return ("network_error", True)

        # Authentication error (won't fix on retry)
        if '401' in error_str or 'authenticate' in error_str:
            return ("auth_error", False)

        return ("unknown", False)

    def _log(self, phone, guest_id, message, target_type, event_type, send_result, timestamp, wedding_id=None):
        """
        Create log record with MessageSid for delivery tracking.

        Args:
            send_result: Either a string (legacy) or dict with status/message_sid/initial_status
        """
        # Handle both old string format and new dict format
        if isinstance(send_result, dict):
            status = send_result.get("status", "unknown")
            message_sid = send_result.get("message_sid")
            initial_status = send_result.get("initial_status")
        else:
            status = send_result
            message_sid = None
            initial_status = None

        log_record = {
            "phone": phone,
            "guest_id": str(guest_id),
            "wedding_id": str(wedding_id) if wedding_id else None,
            "message": message,
            "target_type": target_type,
            "event_type": event_type,
            "status": status,
            "sent_at": timestamp,
            "provider": "twilio",
            # Delivery tracking fields
            "delivery_status": initial_status,
            "delivery_status_updated_at": timestamp if message_sid else None,
        }

        # Only include message_sid when present — omitting it lets the
        # sparse unique index skip failed records instead of colliding on null.
        if message_sid:
            log_record["message_sid"] = message_sid
            if initial_status:
                log_record["delivery_events"] = [{
                    "status": initial_status,
                    "timestamp": timestamp,
                    "error_code": None
                }]
            else:
                log_record["delivery_events"] = []
        else:
            log_record["delivery_events"] = []

        return log_record

    async def get_logs(self):
        return await self.log_collection.find({"provider": "twilio"}, {"_id": 0}).to_list(length=None)


class TwilioRSVPReminderHelper:
    def __init__(self):
        if not twilio_configured:
            raise RuntimeError("Twilio is not configured.")

        self.guest_collection = mongo.get_guest_collection()
        self.wedding_collection = mongo.get_weddings_collection()
        self.log_collection = mongo.db["reminders_sent"]
        self.client = twilio_client
        self.messaging_service_sid = MESSAGING_SERVICE_SID
        self.base_url = os.getenv("FRONTEND_URL")
        if not self.base_url:
            raise ValueError("FRONTEND_URL environment variable is required")
        
    async def send_personalized_rsvp_links(self, slug: str, custom_message: Optional[str] = None):
        # Get wedding by slug first
        wedding = await self.wedding_collection.find_one({"slug": slug})
        if not wedding:
            logger.error(f"Wedding not found with slug: {slug}")
            return {"sent": 0, "failed": 0, "error": "Wedding not found", "provider": "twilio"}

        wedding_id = wedding.get("_id")

        # Get guests for this specific wedding only
        sent_count = 0
        failed_count = 0
        skipped_no_phone = 0
        skipped_no_token = 0
        skipped_opted_out = 0
        unreachable_guests = []  # Guests with neither phone nor email
        logs = []

        async for guest in self.guest_collection.find({"wedding_id": wedding_id}):
            token = guest.get("token")
            phone = guest.get("phone")
            email = guest.get("email")
            guest_id = guest.get("_id")
            now = datetime.now(timezone.utc)

            # Skip if no token or phone, but track the reason
            if not token:
                skipped_no_token += 1
                continue
            if not phone:
                skipped_no_phone += 1
                logger.info(f"Skipping {guest.get('name')} - no phone number")
                # Track guests with no contact info at all
                if not email:
                    unreachable_guests.append({
                        "name": guest.get("name", "Unknown"),
                        "guest_id": str(guest_id),
                    })
                continue

            sms_opt_in = guest.get("sms_opt_in", None)
            if sms_opt_in is False:  # Explicitly opted out
                skipped_opted_out += 1
                logger.info(f"Skipping {guest.get('name')} - opted out of SMS")
                continue

            url = f"{self.base_url}/{slug}/invite/{token}"

            if custom_message:
                message = custom_message.replace("{url}", url).replace("{name}", guest.get("name", ""))
            else:
                message = f"You're invited! RSVP here: {url}"

            # Sanitize and normalize phone to E.164 format
            phone = normalize_phone_e164(phone)
            if not phone:
                skipped_no_phone += 1
                logger.warning(f"Skipping {guest.get('name')} - phone sanitized to empty")
                continue

            # Delivery tracking fields
            message_sid = None
            initial_status = None

            try:
                if not self.client:
                    raise RuntimeError("Twilio client is not initialized")

                # Get the StatusCallback URL for delivery tracking
                status_callback_url = os.getenv("TWILIO_STATUS_CALLBACK_URL")

                twilio_message = self.client.messages.create(
                    messaging_service_sid=self.messaging_service_sid,
                    body=message,
                    to=phone,
                    status_callback=status_callback_url
                )
                logger.info(f"Twilio invite sent to {phone}, SID: {twilio_message.sid}")
                status = "success"
                message_sid = twilio_message.sid
                initial_status = twilio_message.status  # "queued" or "accepted"
                sent_count += 1

                # Mark guest as having received an invite
                await self.guest_collection.update_one(
                    {"_id": guest_id},
                    {"$set": {"invite_sent": True, "invite_sent_date": now}}
                )
            except Exception as e:
                logger.error(f"Failed to send Twilio invite to {phone}: {str(e)}")
                status = f"failed: {str(e)}"
                failed_count += 1

            # Build log record with delivery tracking
            log_record = {
                "phone": phone,
                "guest_id": str(guest_id),
                "wedding_id": str(wedding_id),
                "message": message,
                "target_type": "guest",
                "event_type": "rsvp_invite",
                "status": status,
                "sent_at": now,
                "provider": "twilio",
                # Delivery tracking fields
                "delivery_status": initial_status,
                "delivery_status_updated_at": now if message_sid else None,
            }

            # Only include message_sid when present — omitting it lets the
            # sparse unique index skip failed records instead of colliding on null.
            if message_sid:
                log_record["message_sid"] = message_sid
                if initial_status:
                    log_record["delivery_events"] = [{
                        "status": initial_status,
                        "timestamp": now,
                        "error_code": None
                    }]
                else:
                    log_record["delivery_events"] = []
            else:
                log_record["delivery_events"] = []

            logs.append(log_record)

            # Throttle to stay within Twilio MPS / API rate limits
            if SMS_THROTTLE_DELAY_S > 0:
                await asyncio.sleep(SMS_THROTTLE_DELAY_S)

        if logs:
            await self.log_collection.insert_many(logs)

        return {
            "sent": sent_count,
            "failed": failed_count,
            "skipped_no_phone": skipped_no_phone,
            "skipped_no_token": skipped_no_token,
            "skipped_opted_out": skipped_opted_out,
            "unreachable_guests": unreachable_guests if unreachable_guests else None,
            "provider": "twilio"
        }
