# app/services/reminder_service.py

import os
from fastapi import HTTPException
from twilio.rest import Client
from twilio.http.http_client import TwilioHttpClient
from datetime import datetime, timezone
from app.core.database import mongo
from app.utils.contact_sanitizer import normalize_phone_e164
from app.utils.wedding_event_types import normalize_event_type


class ReminderService:
    def __init__(
        self,
        http_client: TwilioHttpClient | None = None,
    ):
        # 1. Load and validate credentials & config
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token  = os.getenv("TWILIO_AUTH_TOKEN")
        from_phone  = os.getenv("TWILIO_PHONE_NUMBER")
        region      = os.getenv("TWILIO_REGION")
        edge        = os.getenv("TWILIO_EDGE")

        missing = [k for k in ("TWILIO_ACCOUNT_SID","TWILIO_AUTH_TOKEN","TWILIO_PHONE_NUMBER")
                   if not os.getenv(k)]
        if missing:
            raise RuntimeError(f"Missing Twilio env vars: {', '.join(missing)}")

        # 2. Configure HTTP client (allow custom or default with no pooling)
        if http_client is None:
            http_client = TwilioHttpClient(pool_connections=False)

        # 3. Init Twilio client
        self.twilio_client = Client(
            username=account_sid,
            password=auth_token,
            http_client=http_client,
            region=region,
            edge=edge,
        )
        self.from_phone = from_phone

        # 4. Mongo collections
        self.guest_collection    = mongo.get_guest_collection()
        self.rsvp_collection     = mongo.db["rsvps"]
        self.plus_one_collection = mongo.db["plus_ones"]
        self.log_collection      = mongo.db["reminders_sent"]

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

        if logs:
            await self.log_collection.insert_many(logs)

        return {
            "sent": len(logs),
            "skipped_no_phone": skipped_no_phone,
            "skipped_opted_out": skipped_opted_out,
        }

    def _send_sms(self, to: str, body: str) -> str:
        try:
            # Sanitize and normalize phone to E.164 format
            normalized = normalize_phone_e164(to)
            if not normalized:
                return f"failed: Invalid phone number: {to!r}"
            self.twilio_client.messages.create(
                to=normalized,
                from_=self.from_phone,
                body=body,
            )
            return "success"
        except Exception as e:
            # you could also log e here
            return f"failed: {e}"

    def _log(self, phone, guest_id, message, target_type, event_type, status, timestamp):
        return {
            "phone":        phone,
            "guest_id":     str(guest_id),
            "message":      message,
            "target_type":  target_type,
            "event_type":   event_type,
            "status":       status,
            "sent_at":      timestamp,
        }

    async def get_logs(self):
        cursor = self.log_collection.find({}, {"_id": 0})
        return await cursor.to_list(length=500)
