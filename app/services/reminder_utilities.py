# Module 11: RSVP Reminder Utilities (SMS Link Template + RSVP Tester)

from datetime import datetime, timezone
from fastapi import HTTPException
from app.core.database import mongo
from app.models.rsvp import RSVPModel
from app.models.plus_one import PlusOneModel
from bson import ObjectId
from twilio.rest import Client
import os

class RSVPReminderHelper:
    def __init__(self):
        self.guest_collection = mongo.get_guest_collection()
        self.rsvp_collection = mongo.db["rsvps"]
        self.plus_one_collection = mongo.db["plus_ones"]
        self.log_collection = mongo.db["reminders_sent"]  # Add logging collection
        self.twilio_client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
        self.from_phone = os.getenv("TWILIO_PHONE_NUMBER")
        self.base_url = os.getenv("FRONTEND_URL")
        if not self.base_url:
            raise ValueError("FRONTEND_URL environment variable is required")

    async def send_personalized_rsvp_links(self, slug: str, custom_message: str = None, event_type: str = "traditional"):
        # First, get the wedding by slug to find its ID
        wedding = await mongo.db["weddings"].find_one({"slug": slug})
        if not wedding:
            raise HTTPException(status_code=404, detail=f"Wedding with slug '{slug}' not found")

        wedding_id = wedding.get("_id")

        # Get guests for this specific wedding
        guests_cursor = self.guest_collection.find({"wedding_id": wedding_id})
        guests = await guests_cursor.to_list(length=None)
        sent = 0
        for guest in guests:
            token = guest.get("token")
            phone = guest.get("phone")
            if not token or not phone:
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

            try:
                self.twilio_client.messages.create(to=phone, from_=self.from_phone, body=message)
                sent += 1
                # Log successful send
                await self.log_collection.insert_one({
                    "wedding_id": wedding_id,
                    "wedding_slug": slug,
                    "guest_id": str(guest.get("_id")),
                    "guest_name": guest.get("name"),
                    "recipient": phone,
                    "message": message,
                    "status": "sent",
                    "provider": "twilio",
                    "type": "sms",
                    "sent_at": datetime.now(timezone.utc)
                })
            except Exception as e:
                print(f"Failed to send to {phone}: {e}")
                # Log failed send
                await self.log_collection.insert_one({
                    "wedding_id": wedding_id,
                    "wedding_slug": slug,
                    "guest_id": str(guest.get("_id")),
                    "guest_name": guest.get("name"),
                    "recipient": phone,
                    "message": message,
                    "status": "failed",
                    "error": str(e),
                    "provider": "twilio",
                    "type": "sms",
                    "sent_at": datetime.now(timezone.utc)
                })
        return {"sent": sent}

    def simulate_rsvp_for_guest(self, token: str, attending=None, dietary=None, phone=None, plus_one=None):
        if attending is None:
            attending = ["traditional"]
        guest = self.guest_collection.find_one({"token": token})
        if not guest:
            raise HTTPException(status_code=404, detail="Guest not found")

        guest_id = guest["_id"]
        self.rsvp_collection.update_one(
            {"guest_id": guest_id},
            {"$set": {
                "guest_id": guest_id,
                "attending": attending,
                "dietary": dietary,
                "submitted_at": datetime.utcnow()
            }},
            upsert=True
        )
        if phone:
            self.guest_collection.update_one({"_id": guest_id}, {"$set": {"phone": phone}})

        if plus_one:
            if not guest.get("plus_one_allowed"):
                raise HTTPException(status_code=403, detail="Plus-one not allowed")
            if self.plus_one_collection.find_one({"guest_id": ObjectId(guest_id)}):
                raise HTTPException(status_code=400, detail="Plus-one already submitted")

            plus_one_obj = PlusOneModel(
                guest_id=str(ObjectId(guest_id)),
                name=plus_one["name"],
                phone=plus_one.get("phone"),
                attending=plus_one.get("attending", []),
                dietary=plus_one.get("dietary")
            )
            self.plus_one_collection.insert_one(plus_one_obj.dict(by_alias=True))
            self.guest_collection.update_one({"_id": guest_id}, {"$set": {"plus_one_submitted": True}})

        return {"message": "RSVP simulated successfully"}
