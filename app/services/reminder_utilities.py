# Module 11: RSVP Reminder Utilities (SMS Link Template + RSVP Tester)

from datetime import datetime
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
        self.twilio_client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
        self.from_phone = os.getenv("TWILIO_PHONE_NUMBER")
        self.base_url = os.getenv("FRONTEND_URL", "https://yourdomain.com")

    def send_personalized_rsvp_links(self, slug: str, event_type: str = "traditional"):
        guests = self.guest_collection.find({})
        sent = 0
        for guest in guests:
            token = guest.get("token")
            phone = guest.get("phone")
            if not token or not phone:
                continue
            url = f"{self.base_url}/{slug}/invite/{token}"
            message = f"You're invited! RSVP here: {url}"
            try:
                self.twilio_client.messages.create(to=phone, from_=self.from_phone, body=message)
                sent += 1
            except Exception as e:
                print(f"Failed to send to {phone}: {e}")
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
