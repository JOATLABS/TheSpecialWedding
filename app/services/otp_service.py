# app/services/otp_service.py

import os
import random
from datetime import datetime, timedelta
from pymongo import IndexModel, ASCENDING
from bson.objectid import ObjectId
from app.core.database import mongo
from app.services.reminder_service_twilio import TwilioReminderService
import logging

logger = logging.getLogger(__name__)

class OTPService:
    def __init__(self):
        self.otp_collection = mongo.db["otps"]
        self.guest_collection = mongo.get_guest_collection()
        self.twilio_service = TwilioReminderService()

        # Create a TTL index on the 'expires_at' field
        self.otp_collection.create_indexes([
            IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0)
        ])

    def generate_otp(self, guest_id: str) -> str:
        """Generate a 6-digit OTP and store it."""
        otp = str(random.randint(100000, 999999))
        expires_at = datetime.utcnow() + timedelta(minutes=5)

        self.otp_collection.update_one(
            {"guest_id": guest_id},
            {"$set": {"otp": otp, "expires_at": expires_at}},
            upsert=True
        )
        return otp

    def send_otp(self, guest_id: str) -> bool:
        """Send an OTP to the guest's phone."""
        if not ObjectId.is_valid(guest_id):
            return False

        # Rate limit OTP requests to one per minute
        last_otp = self.otp_collection.find_one({"guest_id": guest_id})
        if last_otp and last_otp.get("expires_at") > datetime.utcnow() - timedelta(minutes=4):
            # This is a simple way to prevent spamming OTP requests.
            # A more robust solution would use a dedicated rate-limiting library.
            return False

        guest = self.guest_collection.find_one({"_id": ObjectId(guest_id)})
        if not guest or not guest.get("phone"):
            return False

        otp = self.generate_otp(guest_id)
        message = f"Your verification code is: {otp}"

        status = self.twilio_service._send_sms(guest["phone"], message)
        return status == "success"

    def verify_otp(self, guest_id: str, otp: str) -> bool:
        """Verify the provided OTP."""
        record = self.otp_collection.find_one({
            "guest_id": guest_id,
            "otp": otp,
            "expires_at": {"$gt": datetime.utcnow()}
        })

        if record:
            self.otp_collection.delete_one({"_id": record["_id"]})
            return True
        return False
