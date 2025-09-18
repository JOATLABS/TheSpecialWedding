# app/services/reminder_service.py

import os
from fastapi import HTTPException
from twilio.rest import Client
from twilio.http.http_client import TwilioHttpClient
from datetime import datetime
from app.core.database import mongo

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

    def send_reminders(self, event_type: str, message: str, target_group: str):
        if event_type not in {"traditional", "white_wedding", "reception"}:
            raise HTTPException(status_code=400, detail="Invalid event type")
        if target_group not in {"guests", "plus-ones", "all"}:
            raise HTTPException(status_code=400, detail="Invalid target group")

        logs = []
        now = datetime.utcnow()

        # Guests
        if target_group in {"guests", "all"}:
            for guest in self.guest_collection.find({}):
                rsvp = self.rsvp_collection.find_one({"guest_id": guest["_id"]})
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
            for po in self.plus_one_collection.find({}):
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
            self.log_collection.insert_many(logs)

        return {"sent": len(logs)}

    def _send_sms(self, to: str, body: str) -> str:
        try:
            self.twilio_client.messages.create(
                to=to,
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

    def get_logs(self):
        return list(self.log_collection.find({}, {"_id": 0}))

    def get_logs_for_weddings(self, wedding_ids: list):
        """Get logs filtered by wedding IDs. Since logs only store guest_id,
        we need to join with guests collection to filter by wedding."""
        if not wedding_ids:
            return {"sms_logs": [], "email_logs": []}

        try:
            # Get guest IDs for the specified weddings
            guests = list(self.guest_collection.find(
                {"wedding_id": {"$in": wedding_ids}},
                {"_id": 1}
            ))
            guest_ids = [str(guest["_id"]) for guest in guests]

            if not guest_ids:
                return {"sms_logs": [], "email_logs": []}

            # Filter logs by guest IDs
            logs = list(self.log_collection.find(
                {"guest_id": {"$in": guest_ids}},
                {"_id": 0}
            ))

            # For now, return all as sms_logs since the current structure doesn't differentiate
            return {"sms_logs": logs, "email_logs": []}
        except Exception as e:
            # Return empty logs if anything fails
            return {"sms_logs": [], "email_logs": []}
