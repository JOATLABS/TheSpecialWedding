# app/services/reminder_utilities_telnyx.py

from datetime import datetime, timezone
from fastapi import HTTPException
from app.core.database import mongo
from app.models.rsvp import RSVPModel
from app.models.plus_one import PlusOneModel
from bson import ObjectId
import telnyx
import os
import logging

logger = logging.getLogger(__name__)

class TelnyxRSVPReminderHelper:
    def __init__(self):
        self.guest_collection = mongo.get_guest_collection()
        self.rsvp_collection = mongo.db["rsvps"]
        self.plus_one_collection = mongo.db["plus_ones"]

        # Configure Telnyx
        telnyx.api_key = os.getenv("TELNYX_API_KEY")
        self.from_phone = os.getenv("TELNYX_PHONE_NUMBER")
        self.profile_id = os.getenv("TELNYX_PROFILE_ID")
        self.base_url = os.getenv("FRONTEND_URL")
        if not self.base_url:
            raise ValueError("FRONTEND_URL environment variable is required")

    async def send_personalized_rsvp_links(self, slug: str, custom_message: str = None, event_type: str = "traditional"):
        # Get the wedding by slug to filter guests properly
        wedding = await mongo.db["weddings"].find_one({"slug": slug})
        if not wedding:
            raise HTTPException(status_code=404, detail=f"Wedding with slug '{slug}' not found")

        wedding_id = wedding.get("_id")

        guests_cursor = self.guest_collection.find({"wedding_id": wedding_id})
        guests = await guests_cursor.to_list(length=None)
        sent = 0
        failed = 0

        for guest in guests:
            token = guest.get("token")
            phone = guest.get("phone")

            # Skip if no token or phone
            if not token or not phone:
                continue

            # Check if guest has opted in for SMS (for existing guests)
            # New guests without opt-in status will receive invites
            sms_opt_in = guest.get("sms_opt_in", None)
            if sms_opt_in is False:  # Explicitly opted out
                logger.info(f"Skipping {guest.get('name')} - opted out of SMS")
                continue

            url = f"{self.base_url}/{slug}/invite/{token}"

            # Use custom message if provided, otherwise use default
            if custom_message:
                # Replace {url} placeholder with actual URL
                message = custom_message.replace("{url}", url)
                # Replace {name} placeholder with guest name if present
                message = message.replace("{name}", guest.get("name", ""))
            else:
                message = f"You're invited! RSVP here: {url}"

            # Ensure phone number is in E.164 format
            if not phone.startswith('+'):
                phone = f"+1{phone}"  # Assume US number if no country code

            try:
                # Send via Telnyx
                telnyx_message = telnyx.Message.create(
                    from_=self.from_phone,
                    to=phone,
                    text=message,
                    messaging_profile_id=self.profile_id,
                    type="SMS"
                )

                logger.info(f"Telnyx invite sent to {phone}, ID: {telnyx_message.id}")
                sent += 1

            except Exception as e:
                logger.error(f"Failed to send Telnyx invite to {phone}: {str(e)}")
                failed += 1

        return {
            "sent": sent,
            "failed": failed,
            "provider": "telnyx"
        }

    async def simulate_rsvp_for_guest(self, token: str, attending=None, dietary=None, phone=None, plus_one=None):
        if attending is None:
            attending = ["traditional"]
        guest = await self.guest_collection.find_one({"token": token})
        if not guest:
            raise HTTPException(status_code=404, detail="Guest not found")

        guest_id = ObjectId(guest["_id"])

        # Insert RSVP
        await self.rsvp_collection.update_one(
            {"guest_id": guest_id},
            {"$set": {
                "guest_id": guest_id,
                "attending": attending,
                "dietary": dietary,
                "submitted_at": datetime.now(timezone.utc)
            }},
            upsert=True
        )

        # Update guest phone if provided
        if phone:
            await self.guest_collection.update_one(
                {"_id": guest_id},
                {"$set": {"phone": phone}}
            )

        # Handle plus-one if provided
        if plus_one and guest.get("plus_one_allowed", False):
            await self.plus_one_collection.insert_one({
                "guest_id": str(guest_id),
                "name": plus_one.get("name"),
                "phone": plus_one.get("phone"),
                "attending": plus_one.get("attending", attending),
                "dietary": plus_one.get("dietary")
            })

        return {"message": "Test RSVP submitted successfully"}
