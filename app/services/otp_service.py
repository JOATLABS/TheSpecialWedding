# app/services/otp_service.py

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

        async def init_indexes(self):
            # Create a TTL index on the 'expires_at' field
            await self.otp_collection.create_indexes([
                IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0)
            ])

    async def generate_otp(self, guest_id: str) -> str:
        """Generate a 6-digit OTP and store it."""
        otp = str(random.randint(100000, 999999))
        expires_at = datetime.utcnow() + timedelta(minutes=5)

        await self.otp_collection.update_one(
            {"guest_id": guest_id},
            {"$set": {"otp": otp, "expires_at": expires_at}},
            upsert=True
        )
        return otp

    async def send_otp(self, guest_id: str) -> bool:
        """Send an OTP to the guest's phone."""
        if not ObjectId.is_valid(guest_id):
            return False

        # Rate limit OTP requests to one per minute
        last_otp = await self.otp_collection.find_one({"guest_id": guest_id})
        if last_otp and last_otp.get("expires_at") > datetime.utcnow() - timedelta(minutes=4):
            # This is a simple way to prevent spamming OTP requests.
            # A more robust solution would use a dedicated rate-limiting library.
            return False

        guest = await self.guest_collection.find_one({"_id": ObjectId(guest_id)})
        if not guest or not guest.get("phone"):
            return False

        otp = await self.generate_otp(guest_id)
        message = f"Your verification code is: {otp}"

        status = self.twilio_service._send_sms(guest["phone"], message)
        return status == "success"

    async def verify_otp(self, wedding_id: str, contact: str, otp_code: str) -> dict:
        """
        Verify OTP by contact (phone/email) for a specific wedding.
        Returns dict with success status, guest info, and auth method.
        """
        # Normalize phone number for comparison
        normalized_contact = contact.strip()
        if normalized_contact.startswith('+'):
            # Also try without the + prefix
            contact_variants = [normalized_contact, normalized_contact[1:]]
            # Try with and without country code
            if normalized_contact.startswith('+1'):
                contact_variants.append(normalized_contact[2:])
        else:
            contact_variants = [normalized_contact, f'+{normalized_contact}', f'+1{normalized_contact}']

        # Find guest by contact (phone or email) and wedding_id
        guest = await self.guest_collection.find_one({
            "wedding_id": wedding_id,
            "$or": [
                {"phone": {"$in": contact_variants}},
                {"email": normalized_contact}
            ]
        })

        if not guest:
            logger.warning(f"Guest not found for contact: {contact} in wedding: {wedding_id}")
            return {"success": False, "error": "Guest not found"}

        guest_id = str(guest["_id"])

        # Verify OTP code
        record = await self.otp_collection.find_one({
            "guest_id": guest_id,
            "otp": otp_code,
            "expires_at": {"$gt": datetime.utcnow()}
        })

        if record:
            # OTP is valid, delete it
            await self.otp_collection.delete_one({"_id": record["_id"]})

            # Convert guest ObjectId to string for JSON serialization
            guest["id"] = str(guest["_id"])
            guest.pop("_id", None)

            # Determine auth method
            auth_method = "phone_otp" if guest.get("phone") in contact_variants else "email_otp"

            return {
                "success": True,
                "guest": guest,
                "auth_method": auth_method
            }

        logger.warning(f"Invalid or expired OTP for guest: {guest_id}")
        return {"success": False, "error": "Invalid or expired OTP"}

    async def verify_otp_by_guest_id(self, guest_id: str, otp: str) -> bool:
        """Legacy method: Verify OTP by guest_id. Use verify_otp() instead."""
        record = await self.otp_collection.find_one({
            "guest_id": guest_id,
            "otp": otp,
            "expires_at": {"$gt": datetime.utcnow()}
        })

        if record:
            await self.otp_collection.delete_one({"_id": record["_id"]})
            return True
        return False

    async def send_otp_by_contact(self, wedding_id: str, contact: str) -> dict:
        """
        Send OTP to a guest by their contact info (phone/email) for a specific wedding.
        Returns dict with success status and contact type.
        """
        # Normalize phone number for comparison
        normalized_contact = contact.strip()
        if normalized_contact.startswith('+'):
            contact_variants = [normalized_contact, normalized_contact[1:]]
            if normalized_contact.startswith('+1'):
                contact_variants.append(normalized_contact[2:])
        else:
            contact_variants = [normalized_contact, f'+{normalized_contact}', f'+1{normalized_contact}']

        # Find guest by contact (phone or email) and wedding_id
        guest = await self.guest_collection.find_one({
            "wedding_id": wedding_id,
            "$or": [
                {"phone": {"$in": contact_variants}},
                {"email": normalized_contact}
            ]
        })

        if not guest:
            logger.warning(f"Guest not found for contact: {contact} in wedding: {wedding_id}")
            return {"success": False, "error": "Guest not found for this wedding"}

        guest_id = str(guest["_id"])

        # Generate and store OTP
        otp = await self.generate_otp(guest_id)

        # Send SMS or email
        message = f"Your wedding RSVP verification code is: {otp}. Valid for 5 minutes."

        # Determine contact type and send appropriately
        if guest.get("phone") and guest.get("phone") in contact_variants:
            # Send via SMS
            phone = guest.get("phone")
            if not phone.startswith('+'):
                phone = f"+1{phone}"

            status = self.twilio_service._send_sms(phone, message)
            if status == "success":
                return {"success": True, "contact_type": "phone"}
            else:
                return {"success": False, "error": f"Failed to send SMS: {status}"}

        elif guest.get("email") == normalized_contact:
            # TODO: Implement email sending
            logger.info(f"Email OTP not yet implemented for: {normalized_contact}")
            return {"success": False, "error": "Email OTP not yet implemented"}

        return {"success": False, "error": "No valid contact method found"}
