# app/services/reminder_service_telnyx.py

import os
import telnyx
from fastapi import HTTPException
from datetime import datetime, timezone
from app.core.database import mongo
from app.utils.contact_sanitizer import normalize_phone_e164
import logging

logger = logging.getLogger(__name__)

class TelnyxReminderService:
    def __init__(self):
        # 1. Load and validate Telnyx credentials
        api_key = os.getenv("TELNYX_API_KEY")
        from_phone = os.getenv("TELNYX_PHONE_NUMBER")
        profile_id = os.getenv("TELNYX_PROFILE_ID")
        
        missing = [k for k, v in {
            "TELNYX_API_KEY": api_key,
            "TELNYX_PHONE_NUMBER": from_phone
        }.items() if not v]
        
        if missing:
            raise RuntimeError(f"Missing Telnyx env vars: {', '.join(missing)}")
        
        # 2. Configure Telnyx
        telnyx.api_key = api_key
        self.from_phone = from_phone
        self.profile_id = profile_id
        
        # 3. Mongo collections
        self.guest_collection = mongo.get_guest_collection()
        self.rsvp_collection = mongo.db["rsvps"]
        self.plus_one_collection = mongo.db["plus_ones"]
        self.log_collection = mongo.db["reminders_sent"]
    
    async def send_reminders(self, event_type: str, message: str, target_group: str):
        if event_type not in {"traditional", "white_wedding", "reception"}:
            raise HTTPException(status_code=400, detail="Invalid event type")
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
            "provider": "telnyx"
        }
    
    def _send_sms(self, to: str, body: str) -> str:
        try:
            # Sanitize and normalize phone to E.164 format
            to = normalize_phone_e164(to) or to

            # Create message with Telnyx
            message = telnyx.Message.create(
                from_=self.from_phone,
                to=to,
                text=body,
                messaging_profile_id=self.profile_id,
                type="SMS"
            )
            
            logger.info(f"Telnyx SMS sent to {to}, ID: {message.id}")
            return "success"
            
        except Exception as e:
            logger.error(f"Telnyx SMS failed to {to}: {str(e)}")
            return f"failed: {str(e)}"
    
    def _log(self, phone, guest_id, message, target_type, event_type, status, timestamp):
        return {
            "phone": phone,
            "guest_id": str(guest_id),
            "message": message,
            "target_type": target_type,
            "event_type": event_type,
            "status": status,
            "sent_at": timestamp,
            "provider": "telnyx"
        }
    
    def get_logs(self):
        return list(self.log_collection.find({"provider": "telnyx"}, {"_id": 0}))