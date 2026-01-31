# app/services/otp_service.py

import random
from datetime import datetime, timedelta, timezone
from pymongo import ASCENDING, ReturnDocument
from bson.objectid import ObjectId
from app.core.database import mongo
from app.services.reminder_service_twilio import TwilioReminderService
import logging

logger = logging.getLogger(__name__)


class OTPService:
    _indexes_initialized = False

    def __init__(self):
        self.otp_collection = mongo.db["otps"]
        self.guest_collection = mongo.get_guest_collection()
        self.twilio_service = TwilioReminderService()

    async def _ensure_indexes(self):
        """Create TTL index on expires_at field if not already created."""
        if not OTPService._indexes_initialized:
            try:
                await self.otp_collection.create_index(
                    [("expires_at", ASCENDING)],
                    expireAfterSeconds=0
                )
                OTPService._indexes_initialized = True
                logger.info("OTP TTL index created successfully")
            except Exception as e:
                # Index might already exist, that's fine
                logger.debug(f"OTP index creation: {e}")
                OTPService._indexes_initialized = True

    async def generate_otp(self, guest_id: str) -> str:
        """Generate a 6-digit OTP and store it."""
        otp = str(random.randint(100000, 999999))
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

        # Get fresh collection reference to ensure database is connected
        otp_collection = mongo.db["otps"]

        # Delete any existing OTP for this guest first
        delete_result = await otp_collection.delete_many({"guest_id": guest_id})
        logger.info(f"Deleted {delete_result.deleted_count} existing OTP(s) for guest_id: {guest_id}")

        # Insert new OTP document
        otp_doc = {
            "guest_id": guest_id,
            "otp": otp,
            "expires_at": expires_at,
            "created_at": datetime.now(timezone.utc)
        }
        insert_result = await otp_collection.insert_one(otp_doc)

        if not insert_result.inserted_id:
            raise Exception(f"Failed to insert OTP to database for guest_id: {guest_id}")

        # Verify by reading back
        saved_doc = await otp_collection.find_one({"_id": insert_result.inserted_id})
        if not saved_doc:
            raise Exception(f"OTP inserted but cannot be read back for guest_id: {guest_id}")

        logger.info(f"OTP saved successfully for guest_id: {guest_id}, doc_id: {insert_result.inserted_id}")
        return otp

    async def send_otp(self, guest_id: str) -> dict:
        """
        Send an OTP to the guest's phone.

        Returns:
            dict with "success" (bool) and "error" (str) if failed
        """
        if not ObjectId.is_valid(guest_id):
            logger.warning(f"Invalid ObjectId format: {guest_id}")
            return {"success": False, "error": "Invalid guest ID format"}

        # Ensure TTL index exists
        await self._ensure_indexes()

        # Check for existing OTP and handle rate limiting
        last_otp = await self.otp_collection.find_one({"guest_id": guest_id})
        if last_otp:
            expires_at = last_otp.get("expires_at")
            if expires_at:
                # If OTP has expired, delete it and allow new request
                if expires_at <= datetime.now(timezone.utc):
                    await self.otp_collection.delete_one({"_id": last_otp["_id"]})
                    logger.debug(f"Deleted expired OTP for guest_id: {guest_id}")
                # If OTP was sent within last minute (expires_at > now + 4min), rate limit
                elif expires_at > datetime.now(timezone.utc) + timedelta(minutes=4):
                    logger.info(f"Rate limited OTP request for guest_id: {guest_id}")
                    return {"success": False, "error": "Please wait before requesting another code"}

        guest = await self.guest_collection.find_one({"_id": ObjectId(guest_id)})
        if not guest:
            logger.warning(f"Guest not found for guest_id: {guest_id}")
            return {"success": False, "error": "Guest not found"}
        if not guest.get("phone"):
            logger.warning(f"Guest has no phone number: {guest_id}")
            return {"success": False, "error": "No phone number on file. Please contact the wedding planner."}

        try:
            otp = await self.generate_otp(guest_id)
        except Exception as e:
            logger.error(f"Failed to save OTP for guest_id {guest_id}: {str(e)}")
            return {"success": False, "error": "Failed to generate verification code. Please try again."}

        message = f"Your verification code is: {otp}"

        result = self.twilio_service._send_sms(guest["phone"], message)
        # _send_sms now returns a dict with "status", "message_sid", "initial_status"
        status = result.get("status") if isinstance(result, dict) else result
        if status != "success":
            logger.error(f"Failed to send OTP SMS to guest_id {guest_id}: {status}")
            return {"success": False, "error": "Failed to send SMS. Please try again later."}

        return {"success": True}

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

        # Verify OTP code (strip whitespace from input)
        otp_clean = otp_code.strip()
        record = await self.otp_collection.find_one({
            "guest_id": guest_id,
            "otp": otp_clean,
            "expires_at": {"$gt": datetime.now(timezone.utc)}
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
        otp_clean = otp.strip()

        # Get fresh collection reference (same as generate_otp)
        otp_collection = mongo.db["otps"]

        # First check if ANY OTP exists for this guest (for debugging)
        any_record = await otp_collection.find_one({"guest_id": guest_id})
        if any_record:
            logger.info(f"Found OTP record for guest_id {guest_id}: otp={any_record.get('otp')}, expires_at={any_record.get('expires_at')}")
        else:
            logger.warning(f"No OTP record found for guest_id: {guest_id}")

        record = await otp_collection.find_one({
            "guest_id": guest_id,
            "otp": otp_clean,
            "expires_at": {"$gt": datetime.now(timezone.utc)}
        })

        if record:
            await otp_collection.delete_one({"_id": record["_id"]})
            logger.info(f"OTP verified and deleted for guest_id: {guest_id}")
            return True

        logger.warning(f"OTP verification failed for guest_id: {guest_id}, otp_provided: {otp_clean}")
        return False

    async def send_otp_by_contact(self, wedding_id: str, contact: str) -> dict:
        """
        Send OTP to a guest by their contact info (phone/email) for a specific wedding.
        Returns dict with success status and contact type.

        Security: Rate limited to prevent OTP spam attacks.
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

        # Ensure TTL index exists
        await self._ensure_indexes()

        # Check for existing OTP and handle rate limiting
        last_otp = await self.otp_collection.find_one({"guest_id": guest_id})
        if last_otp:
            expires_at = last_otp.get("expires_at")
            if expires_at:
                # If OTP has expired, delete it and allow new request
                if expires_at <= datetime.now(timezone.utc):
                    await self.otp_collection.delete_one({"_id": last_otp["_id"]})
                    logger.debug(f"Deleted expired OTP for guest_id: {guest_id}")
                # If OTP was sent within last minute (expires_at > now + 4min), rate limit
                elif expires_at > datetime.now(timezone.utc) + timedelta(minutes=4):
                    logger.info(f"Rate limited OTP request for guest_id: {guest_id}")
                    return {"success": False, "error": "Please wait before requesting another code"}

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

            result = self.twilio_service._send_sms(phone, message)
            # _send_sms now returns a dict with "status", "message_sid", "initial_status"
            status = result.get("status") if isinstance(result, dict) else result
            if status == "success":
                return {"success": True, "contact_type": "phone"}
            else:
                return {"success": False, "error": f"Failed to send SMS: {status}"}

        elif guest.get("email") == normalized_contact:
            # TODO: Implement email sending
            logger.info(f"Email OTP not yet implemented for: {normalized_contact}")
            return {"success": False, "error": "Email OTP not yet implemented"}

        return {"success": False, "error": "No valid contact method found"}
