# app/services/otp_service.py

import random
from datetime import datetime, timedelta, timezone
from pymongo import ASCENDING
from bson.objectid import ObjectId
from app.core.database import mongo
from app.core.settings import settings
from app.services.reminder_service_twilio import TwilioReminderService
from app.services.email_service_resend import ResendEmailService
import logging

logger = logging.getLogger(__name__)


class OTPService:
    _indexes_initialized = False

    def __init__(self):
        self.otp_collection = mongo.db["otps"]
        self.guest_collection = mongo.get_guest_collection()
        self.twilio_service = TwilioReminderService()
        self.email_service = ResendEmailService()

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

    async def generate_otp(self, guest_id: str, contact_type: str = "phone") -> str:
        """Generate a 6-digit OTP and store it with contact type for auth tracking."""
        otp = str(random.randint(100000, 999999))
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

        # Get fresh collection reference to ensure database is connected
        otp_collection = mongo.db["otps"]

        # Delete any existing OTP for this guest first
        delete_result = await otp_collection.delete_many({"guest_id": guest_id})
        logger.info(f"Deleted {delete_result.deleted_count} existing OTP(s) for guest_id: {guest_id}")

        # Insert new OTP document with contact_type for auth method tracking
        otp_doc = {
            "guest_id": guest_id,
            "otp": otp,
            "contact_type": contact_type,
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
            created_at = last_otp.get("created_at")
            if expires_at:
                # If OTP has expired, delete it and allow new request
                if expires_at <= datetime.now(timezone.utc):
                    await self.otp_collection.delete_one({"_id": last_otp["_id"]})
                    logger.debug(f"Deleted expired OTP for guest_id: {guest_id}")
                # Rate limit using settings.rate_limit_auth_period (default 60 seconds)
                elif created_at:
                    seconds_since_created = (datetime.now(timezone.utc) - created_at).total_seconds()
                    if seconds_since_created < settings.rate_limit_auth_period:
                        logger.info(f"Rate limited OTP request for guest_id: {guest_id} (sent {seconds_since_created:.0f}s ago)")
                        return {"success": False, "error": "Please wait before requesting another code"}

        guest = await self.guest_collection.find_one({"_id": ObjectId(guest_id)})
        if not guest:
            logger.warning(f"Guest not found for guest_id: {guest_id}")
            return {"success": False, "error": "Guest not found"}

        # Check available contact methods
        has_phone = guest.get("phone") and guest.get("phone").strip()
        has_email = guest.get("email") and guest.get("email").strip()

        if not has_phone and not has_email:
            logger.warning(f"Guest has no phone or email: {guest_id}")
            return {"success": False, "error": "No contact method on file. Please contact the wedding planner."}

        # Determine primary contact method for OTP record
        primary_contact_type = "phone" if has_phone else "email"

        try:
            otp = await self.generate_otp(guest_id, contact_type=primary_contact_type)
        except Exception as e:
            logger.error(f"Failed to save OTP for guest_id {guest_id}: {str(e)}")
            return {"success": False, "error": "Failed to generate verification code. Please try again."}

        # Try phone first (preferred method)
        if has_phone:
            message = f"Your verification code is: {otp}"
            result = self.twilio_service._send_sms(guest["phone"], message)
            # _send_sms now returns a dict with "status", "message_sid", "initial_status"
            status = result.get("status") if isinstance(result, dict) else result
            if status == "success":
                return {"success": True, "contact_type": "phone"}
            else:
                logger.error(f"Failed to send OTP SMS to guest_id {guest_id}: {status}")
                # If SMS fails and we have email, try email fallback
                if has_email:
                    logger.info(f"SMS failed, attempting email fallback for guest_id: {guest_id}")
                    # Update OTP record with correct contact_type for fallback
                    otp_collection = mongo.db["otps"]
                    await otp_collection.update_one(
                        {"guest_id": guest_id},
                        {"$set": {"contact_type": "email"}}
                    )
                else:
                    return {"success": False, "error": "Failed to send SMS. Please try again later."}

        # Send via email (either as primary or fallback)
        if has_email:
            html_content = self._generate_otp_email_html(otp, guest.get("name", "Guest"))
            result = await self.email_service.send_email(
                to_email=guest["email"],
                subject="Your RSVP Verification Code",
                html_content=html_content,
                email_type="otp"
            )
            if result.get("success"):
                return {"success": True, "contact_type": "email"}
            else:
                logger.error(f"Failed to send OTP email to guest_id {guest_id}: {result.get('error')}")
                return {"success": False, "error": "Failed to send verification code. Please try again later."}

        return {"success": False, "error": "Failed to send verification code. Please try again later."}

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

    async def verify_otp_by_guest_id(self, guest_id: str, otp: str) -> dict:
        """
        Verify OTP by guest_id and return guest data on success.

        Returns:
            dict with success, guest (on success), auth_method (on success), error (on failure)
        """
        otp_clean = otp.strip()

        # Validate guest_id format
        if not ObjectId.is_valid(guest_id):
            logger.warning(f"Invalid ObjectId format: {guest_id}")
            return {"success": False, "error": "Invalid guest ID format"}

        # Get fresh collection reference (same as generate_otp)
        otp_collection = mongo.db["otps"]

        # First check if ANY OTP exists for this guest (for debugging)
        any_record = await otp_collection.find_one({"guest_id": guest_id})
        if any_record:
            logger.info(f"Found OTP record for guest_id {guest_id}: otp={any_record.get('otp')}, expires_at={any_record.get('expires_at')}")
        else:
            logger.warning(f"No OTP record found for guest_id: {guest_id}")
            return {"success": False, "error": "Invalid or expired OTP"}

        # Find valid OTP record
        record = await otp_collection.find_one({
            "guest_id": guest_id,
            "otp": otp_clean,
            "expires_at": {"$gt": datetime.now(timezone.utc)}
        })

        if not record:
            logger.warning(f"OTP verification failed for guest_id: {guest_id}, otp_provided: {otp_clean}")
            return {"success": False, "error": "Invalid or expired OTP"}

        # OTP is valid - delete it
        await otp_collection.delete_one({"_id": record["_id"]})
        logger.info(f"OTP verified and deleted for guest_id: {guest_id}")

        # Fetch guest data
        guest = await self.guest_collection.find_one({"_id": ObjectId(guest_id)})
        if not guest:
            logger.error(f"Guest not found after OTP verification: {guest_id}")
            return {"success": False, "error": "Guest not found"}

        # Convert ObjectId to string for JSON serialization
        guest["id"] = str(guest["_id"])
        guest.pop("_id", None)

        # Determine auth method from OTP record's contact_type
        contact_type = record.get("contact_type", "phone")
        auth_method = f"{contact_type}_otp"

        return {
            "success": True,
            "guest": guest,
            "auth_method": auth_method
        }

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
            created_at = last_otp.get("created_at")
            if expires_at:
                # If OTP has expired, delete it and allow new request
                if expires_at <= datetime.now(timezone.utc):
                    await self.otp_collection.delete_one({"_id": last_otp["_id"]})
                    logger.debug(f"Deleted expired OTP for guest_id: {guest_id}")
                # Rate limit using settings.rate_limit_auth_period (default 60 seconds)
                elif created_at:
                    seconds_since_created = (datetime.now(timezone.utc) - created_at).total_seconds()
                    if seconds_since_created < settings.rate_limit_auth_period:
                        logger.info(f"Rate limited OTP request for guest_id: {guest_id} (sent {seconds_since_created:.0f}s ago)")
                        return {"success": False, "error": "Please wait before requesting another code"}

        # Determine contact type for OTP record
        is_phone_contact = guest.get("phone") and guest.get("phone") in contact_variants
        contact_type = "phone" if is_phone_contact else "email"

        # Generate and store OTP with contact type
        otp = await self.generate_otp(guest_id, contact_type=contact_type)

        # Send SMS or email
        message = f"Your wedding RSVP verification code is: {otp}. Valid for 5 minutes."

        # Determine contact type and send appropriately
        if is_phone_contact:
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
            # Send via email
            html_content = self._generate_otp_email_html(otp, guest.get("name", "Guest"))
            result = await self.email_service.send_email(
                to_email=normalized_contact,
                subject="Your RSVP Verification Code",
                html_content=html_content,
                email_type="otp"
            )
            if result.get("success"):
                return {"success": True, "contact_type": "email"}
            else:
                logger.error(f"Failed to send OTP email: {result.get('error')}")
                return {"success": False, "error": f"Failed to send email: {result.get('error')}"}

        return {"success": False, "error": "No valid contact method found"}

    def _generate_otp_email_html(self, otp_code: str, guest_name: str) -> str:
        """Generate HTML for OTP verification email."""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }}
                .container {{ max-width: 500px; margin: 0 auto; padding: 30px; }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .header h1 {{ color: #1e3a5f; margin: 0; font-size: 24px; font-weight: 300; }}
                .code-box {{ background: #f8f9fa; padding: 25px; text-align: center; border-radius: 8px; margin: 25px 0; border: 1px solid #e9ecef; }}
                .code {{ font-size: 36px; font-weight: bold; color: #c8847e; letter-spacing: 6px; font-family: monospace; }}
                .footer {{ text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e9ecef; }}
                .footer p {{ color: #999; font-size: 12px; margin: 5px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Wedding RSVP Verification</h1>
                </div>
                <p>Hi {guest_name},</p>
                <p>Here's your verification code for your wedding RSVP:</p>
                <div class="code-box">
                    <div class="code">{otp_code}</div>
                </div>
                <p style="color: #666;">This code expires in 5 minutes.</p>
                <div class="footer">
                    <p>If you didn't request this code, please ignore this email.</p>
                    <p>&copy; TheSpecialWedding</p>
                </div>
            </div>
        </body>
        </html>
        """
