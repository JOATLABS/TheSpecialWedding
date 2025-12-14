# app/services/reminder_service_twilio.py

import os
from typing import Optional
from twilio.rest import Client  # type: ignore
from fastapi import HTTPException
from datetime import datetime
from app.core.database import mongo
import logging

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
        if event_type not in {"traditional", "white_wedding", "reception"}:
            raise HTTPException(status_code=400, detail="Invalid event type")
        if target_group not in {"guests", "plus-ones", "all"}:
            raise HTTPException(status_code=400, detail="Invalid target group")

        logs = []
        now = datetime.utcnow()

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

        return {"sent": len(logs), "provider": "twilio"}

    def _send_sms(self, to: str, body: str) -> str:
        try:
            if not self.client:
                raise RuntimeError("Twilio client is not initialized")

            # Ensure phone number is in E.164 format
            if not to.startswith('+'):
                to = f"+1{to}"  # Assume US number if no country code

            # Get from number from env
            from_number = os.getenv("TWILIO_FROM_NUMBER") or os.getenv("TWILIO_PHONE_NUMBER")

            # Create message with Twilio using direct phone number
            # Try messaging service first, fallback to direct number if it fails
            try:
                message = self.client.messages.create(
                    messaging_service_sid=self.messaging_service_sid,
                    body=body,
                    to=to
                )
            except Exception as msg_service_error:
                logger.warning(f"Messaging service failed, trying direct number: {str(msg_service_error)}")
                # Fallback to direct phone number
                message = self.client.messages.create(
                    from_=from_number,
                    body=body,
                    to=to
                )

            logger.info(f"Twilio SMS sent to {to}, SID: {message.sid}")
            return "success"

        except Exception as e:
            logger.error(f"Twilio SMS failed to {to}: {str(e)}")
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
            "provider": "twilio"
        }

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
        wedding = await self.wedding_collection.find_one({"slug": slug})
        if not wedding:
            logger.error(f"Wedding not found with slug: {slug}")
            return {"sent": 0, "failed": 0, "error": "Wedding not found", "provider": "twilio"}

        wedding_id = wedding.get("_id")

        # Get guests for this specific wedding only
        sent_count = 0
        failed_count = 0
        logs = []

        async for guest in self.guest_collection.find({"wedding_id": wedding_id}):
            token = guest.get("token")
            phone = guest.get("phone")
            guest_id = guest.get("_id")
            now = datetime.utcnow()

            # Skip if no token or phone
            if not token or not phone:
                continue

            sms_opt_in = guest.get("sms_opt_in", None)
            if sms_opt_in is False:  # Explicitly opted out
                logger.info(f"Skipping {guest.get('name')} - opted out of SMS")
                continue

            url = f"{self.base_url}/{slug}/invite/{token}"

            if custom_message:
                message = custom_message.replace("{url}", url).replace("{name}", guest.get("name", ""))
            else:
                message = f"You're invited! RSVP here: {url}"

            if not phone.startswith('+'):
                phone = f"+1{phone}"

            try:
                if not self.client:
                    raise RuntimeError("Twilio client is not initialized")

                twilio_message = self.client.messages.create(
                    messaging_service_sid=self.messaging_service_sid,
                    body=message,
                    to=phone
                )
                logger.info(f"Twilio invite sent to {phone}, SID: {twilio_message.sid}")
                status = "success"
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to send Twilio invite to {phone}: {str(e)}")
                status = f"failed: {str(e)}"
                failed_count += 1

            logs.append({
                "phone": phone,
                "guest_id": str(guest_id),
                "message": message,
                "target_type": "guest",
                "event_type": "rsvp_invite",
                "status": status,
                "sent_at": now,
                "provider": "twilio"
            })

        if logs:
            await self.log_collection.insert_many(logs)

        return {
            "sent": sent_count,
            "failed": failed_count,
            "provider": "twilio"
        }
