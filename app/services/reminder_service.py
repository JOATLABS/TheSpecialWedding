# Module 8: SMS Reminder System (FastAPI + Twilio)

# 1. File: app/services/reminder_service.py
import os
from fastapi import HTTPException
from twilio.rest import Client
from datetime import datetime
from app.core.database import mongo

class ReminderService:
    def __init__(self):
        self.guest_collection = mongo.get_guest_collection()
        self.rsvp_collection = mongo.db["rsvps"]
        self.plus_one_collection = mongo.db["plus_ones"]
        self.log_collection = mongo.db["reminders_sent"]
        self.twilio_client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
        self.from_phone = os.getenv("TWILIO_PHONE_NUMBER")

    def send_reminders(self, event_type: str, message: str, target_group: str):
        if event_type not in {"traditional", "white_wedding", "reception"}:
            raise HTTPException(status_code=400, detail="Invalid event type")
        if target_group not in {"guests", "plus-ones", "all"}:
            raise HTTPException(status_code=400, detail="Invalid target group")

        logs = []
        now = datetime.utcnow()

        if target_group in {"guests", "all"}:
            guests = self.guest_collection.find({})
            for guest in guests:
                rsvp = self.rsvp_collection.find_one({"guest_id": guest["_id"]})
                if rsvp and event_type in rsvp.get("attending", []):
                    phone = guest.get("phone")
                    if phone:
                        status = self._send_sms(phone, message)
                        logs.append(self._log(phone, guest["_id"], message, "guest", event_type, status, now))

        if target_group in {"plus-ones", "all"}:
            plus_ones = self.plus_one_collection.find({})
            for po in plus_ones:
                if event_type in po.get("attending", []):
                    phone = po.get("phone")
                    if phone:
                        status = self._send_sms(phone, message)
                        logs.append(self._log(phone, po["guest_id"], message, "plus-one", event_type, status, now))

        if logs:
            self.log_collection.insert_many(logs)
        return {"sent": len(logs)}

    def _send_sms(self, to: str, body: str):
        try:
            self.twilio_client.messages.create(
                to=to,
                from_=self.from_phone,
                body=body
            )
            return "success"
        except Exception as e:
            return f"failed: {str(e)}"

    def _log(self, phone, guest_id, message, target_type, event_type, status, timestamp):
        return {
            "phone": phone,
            "guest_id": str(guest_id),
            "message": message,
            "target_type": target_type,
            "event_type": event_type,
            "status": status,
            "sent_at": timestamp
        }

    def get_logs(self):
        return list(self.log_collection.find({}, {"_id": 0}))
