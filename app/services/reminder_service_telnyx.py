# app/services/reminder_service_telnyx.py

import os
import telnyx
from fastapi import HTTPException
from datetime import datetime, timezone
from app.core.database import mongo
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

        # Guests
        if target_group in {"guests", "all"}:
            async for guest in self.guest_collection.find({}):
                rsvp = await self.rsvp_collection.find_one({"guest_id": guest["_id"]})
                if rsvp and event_type in rsvp.get("attending", []):
                    phone = guest.get("phone")
                    # Check if guest has opted in for SMS reminders
                    sms_opt_in = guest.get("sms_opt_in", False)
                    if phone and sms_opt_in:
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
                    if phone:
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

        return {"sent": len(logs), "provider": "telnyx"}
    
    def _send_sms(self, to: str, body: str) -> str:
        try:
            # Ensure phone number is in E.164 format
            if not to.startswith('+'):
                to = f"+1{to}"  # Assume US number if no country code
            
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