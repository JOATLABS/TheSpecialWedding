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


def _ensure_utc(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware (UTC).

    MongoDB may return naive datetimes depending on driver version and
    codec settings.  This helper normalises them so comparisons with
    ``datetime.now(timezone.utc)`` never raise
    ``TypeError: can't compare offset-naive and offset-aware datetimes``.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class OTPService:
    _indexes_initialized = False

    def __init__(self):
        self.otp_collection = mongo.db["otps"]
        self.guest_collection = mongo.get_guest_collection()
        self.email_service = ResendEmailService()
        self.twilio_service = None
        self._twilio_unavailable_error: str | None = None

    def _get_twilio_service(self) -> TwilioReminderService | None:
        """Lazily initialize Twilio so read-only flows don't crash app startup."""
        if self.twilio_service is not None:
            return self.twilio_service

        if self._twilio_unavailable_error is not None:
            return None

        try:
            self.twilio_service = TwilioReminderService()
        except RuntimeError as exc:
            self._twilio_unavailable_error = str(exc)
            logger.warning("OTP SMS unavailable: %s", exc)
            return None

        return self.twilio_service

    @staticmethod
    def _serialize_guest_response(guest: dict | None) -> dict | None:
        if not guest:
            return None

        guest_response = guest.copy()
        guest_response["id"] = str(
            guest_response.get("_id") or guest_response.get("id")
        )
        guest_response.pop("_id", None)
        guest_response.pop("token", None)
        return guest_response

    async def _ensure_indexes(self):
        """Create TTL index on expires_at field if not already created."""
        if not OTPService._indexes_initialized:
            try:
                await self.otp_collection.create_index(
                    [("expires_at", ASCENDING)], expireAfterSeconds=0
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
        logger.info(
            f"Deleted {delete_result.deleted_count} existing OTP(s) for guest_id: {guest_id}"
        )

        # Insert new OTP document with contact_type for auth method tracking
        otp_doc = {
            "guest_id": guest_id,
            "otp": otp,
            "contact_type": contact_type,
            "expires_at": expires_at,
            "created_at": datetime.now(timezone.utc),
        }
        insert_result = await otp_collection.insert_one(otp_doc)

        if not insert_result.inserted_id:
            raise Exception(
                f"Failed to insert OTP to database for guest_id: {guest_id}"
            )

        # Verify by reading back
        saved_doc = await otp_collection.find_one({"_id": insert_result.inserted_id})
        if not saved_doc:
            raise Exception(
                f"OTP inserted but cannot be read back for guest_id: {guest_id}"
            )

        logger.info(
            f"OTP saved successfully for guest_id: {guest_id}, doc_id: {insert_result.inserted_id}"
        )
        return otp

    async def send_otp(self, guest_id: str) -> dict:
        """
        Send an OTP to the guest's phone (preferred) or email (fallback).

        Returns:
            dict with:
                - "success" (bool)
                - "contact_type" ("phone" | "email") on success
                - "error" (str) on failure — user-friendly message
                - "error_code" (str) on failure — machine-readable code for frontend
                - "retry_after" (int) — seconds to wait before retrying (optional)
                - "fallback_used" (bool) — True if email was used because SMS failed
        """
        if not ObjectId.is_valid(guest_id):
            logger.warning(f"Invalid ObjectId format: {guest_id}")
            return {
                "success": False,
                "error": "Invalid guest ID format",
                "error_code": "invalid_input",
            }

        # Ensure TTL index exists
        await self._ensure_indexes()

        # Check for existing OTP and handle rate limiting
        last_otp = await self.otp_collection.find_one({"guest_id": guest_id})
        if last_otp:
            expires_at = _ensure_utc(last_otp.get("expires_at"))
            created_at = _ensure_utc(last_otp.get("created_at"))
            if expires_at:
                # If OTP has expired, delete it and allow new request
                if expires_at <= datetime.now(timezone.utc):
                    await self.otp_collection.delete_one({"_id": last_otp["_id"]})
                    logger.debug(f"Deleted expired OTP for guest_id: {guest_id}")
                # Rate limit using settings.rate_limit_auth_period (default 60 seconds)
                elif created_at:
                    seconds_since_created = (
                        datetime.now(timezone.utc) - created_at
                    ).total_seconds()
                    if seconds_since_created < settings.rate_limit_auth_period:
                        remaining = int(
                            settings.rate_limit_auth_period - seconds_since_created
                        )
                        logger.info(
                            f"Rate limited OTP request for guest_id: {guest_id} (sent {seconds_since_created:.0f}s ago)"
                        )
                        return {
                            "success": False,
                            "error": f"Please wait {remaining} seconds before requesting another code",
                            "error_code": "rate_limited",
                            "retry_after": remaining,
                        }

        guest = await self.guest_collection.find_one({"_id": ObjectId(guest_id)})
        if not guest:
            logger.warning(f"Guest not found for guest_id: {guest_id}")
            return {
                "success": False,
                "error": "Guest not found",
                "error_code": "guest_not_found",
            }

        # Check available contact methods
        has_phone = guest.get("phone") and guest.get("phone").strip()
        has_email = guest.get("email") and guest.get("email").strip()

        if not has_phone and not has_email:
            logger.warning(f"Guest has no phone or email: {guest_id}")
            return {
                "success": False,
                "error": "No contact method on file. Please contact the wedding planner.",
                "error_code": "no_contact",
            }

        # Determine primary contact method for OTP record
        primary_contact_type = "phone" if has_phone else "email"

        try:
            otp = await self.generate_otp(guest_id, contact_type=primary_contact_type)
        except Exception as e:
            logger.error(f"Failed to save OTP for guest_id {guest_id}: {str(e)}")
            return {
                "success": False,
                "error": "Failed to generate verification code. Please try again.",
                "error_code": "generation_failed",
            }

        # Try phone first (preferred method)
        sms_error_code = None
        if has_phone:
            message = f"Your verification code is: {otp}"
            twilio_service = self._get_twilio_service()
            if twilio_service:
                result = twilio_service._send_sms(guest["phone"], message)
                status = result.get("status") if isinstance(result, dict) else result
                sms_error_code = (
                    result.get("error_code") if isinstance(result, dict) else None
                )

                if status == "success":
                    return {
                        "success": True,
                        "contact_type": "phone",
                        "fallback_used": False,
                    }

                logger.error(
                    "Failed to send OTP SMS to guest_id %s: %s (error_code: %s)",
                    guest_id,
                    status,
                    sms_error_code,
                )
            else:
                sms_error_code = "not_configured"
                logger.info(
                    "SMS OTP skipped for guest_id %s because Twilio is not configured",
                    guest_id,
                )

            # If SMS fails and we have email, try email fallback
            if has_email:
                logger.info(
                    "SMS failed (%s), attempting email fallback for guest_id: %s",
                    sms_error_code,
                    guest_id,
                )
                # Update OTP record with correct contact_type for fallback
                otp_collection = mongo.db["otps"]
                await otp_collection.update_one(
                    {"guest_id": guest_id}, {"$set": {"contact_type": "email"}}
                )
            else:
                # No email fallback — return specific error based on SMS failure type
                user_error = self._get_user_friendly_sms_error(sms_error_code)
                return {
                    "success": False,
                    "error": user_error,
                    "error_code": sms_error_code or "sms_failed",
                    "retry_after": 30
                    if sms_error_code
                    in ("rate_limited", "daily_limit", "service_unavailable")
                    else None,
                }

        # Send via email (either as primary or fallback)
        if has_email:
            html_content = self._generate_otp_email_html(
                otp, guest.get("name", "Guest")
            )
            result = await self.email_service.send_email(
                to_email=guest["email"],
                subject="Your RSVP Verification Code",
                html_content=html_content,
                email_type="otp",
            )
            if result.get("success"):
                fallback_used = has_phone and sms_error_code is not None
                return {
                    "success": True,
                    "contact_type": "email",
                    "fallback_used": fallback_used,
                    "sms_error_code": sms_error_code if fallback_used else None,
                }
            else:
                logger.error(
                    f"Failed to send OTP email to guest_id {guest_id}: {result.get('error')}"
                )
                return {
                    "success": False,
                    "error": "We couldn't send your verification code by text or email. Please try again in a few minutes, or contact the wedding planner for help.",
                    "error_code": "all_channels_failed",
                }

        return {
            "success": False,
            "error": "We couldn't send your verification code. Please try again in a few minutes.",
            "error_code": "send_failed",
        }

    @staticmethod
    def _get_user_friendly_sms_error(error_code: str) -> str:
        """Return a guest-friendly error message based on the Twilio error code."""
        messages = {
            "rate_limited": "Our text message service is temporarily busy. Please try again in about 30 seconds.",
            "daily_limit": "We've reached our daily text message limit. Please try again tomorrow, or contact the wedding planner for help.",
            "invalid_number": "We couldn't send a text to the phone number on file. Please contact the wedding planner to update your contact info.",
            "number_blocked": "Text messages can't be delivered to this phone number. Please contact the wedding planner for help.",
            "service_unavailable": "Our text message service is temporarily unavailable. Please try again in a few minutes.",
            "network_error": "We're having trouble connecting to our text message service. Please try again in a moment.",
            "not_configured": "Text messaging is not set up yet. Please contact the wedding planner for help.",
            "auth_error": "There's a configuration issue with our text service. The wedding planner has been notified.",
        }
        return messages.get(
            error_code,
            "We couldn't send your verification code. Please try again in a few minutes.",
        )

    async def verify_otp(self, wedding_id: str, contact: str, otp_code: str) -> dict:
        """
        Verify OTP by contact (phone/email) for a specific wedding.
        Returns dict with success status, guest info, and auth method.
        """
        # Normalize phone number for comparison
        normalized_contact = contact.strip()
        if normalized_contact.startswith("+"):
            # Also try without the + prefix
            contact_variants = [normalized_contact, normalized_contact[1:]]
            # Try with and without country code
            if normalized_contact.startswith("+1"):
                contact_variants.append(normalized_contact[2:])
        else:
            contact_variants = [
                normalized_contact,
                f"+{normalized_contact}",
                f"+1{normalized_contact}",
            ]

        # Find guest by contact (phone or email) and wedding_id
        guest = await self.guest_collection.find_one(
            {
                "wedding_id": wedding_id,
                "$or": [
                    {"phone": {"$in": contact_variants}},
                    {"email": normalized_contact},
                ],
            }
        )

        if not guest:
            logger.warning(
                f"Guest not found for contact: {contact} in wedding: {wedding_id}"
            )
            return {"success": False, "error": "Guest not found"}

        guest_id = str(guest["_id"])

        # Verify OTP code (strip whitespace from input)
        otp_clean = otp_code.strip()
        record = await self.otp_collection.find_one(
            {
                "guest_id": guest_id,
                "otp": otp_clean,
                "expires_at": {"$gt": datetime.now(timezone.utc)},
            }
        )

        if record:
            # OTP is valid, delete it
            await self.otp_collection.delete_one({"_id": record["_id"]})

            # Determine auth method
            auth_method = (
                "phone_otp" if guest.get("phone") in contact_variants else "email_otp"
            )

            return {
                "success": True,
                "guest": self._serialize_guest_response(guest),
                "auth_method": auth_method,
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
            logger.info(
                f"Found OTP record for guest_id {guest_id}: otp={any_record.get('otp')}, expires_at={any_record.get('expires_at')}"
            )
        else:
            logger.warning(f"No OTP record found for guest_id: {guest_id}")
            return {"success": False, "error": "Invalid or expired OTP"}

        # Find valid OTP record
        record = await otp_collection.find_one(
            {
                "guest_id": guest_id,
                "otp": otp_clean,
                "expires_at": {"$gt": datetime.now(timezone.utc)},
            }
        )

        if not record:
            logger.warning(
                f"OTP verification failed for guest_id: {guest_id}, otp_provided: {otp_clean}"
            )
            return {"success": False, "error": "Invalid or expired OTP"}

        # OTP is valid - delete it
        await otp_collection.delete_one({"_id": record["_id"]})
        logger.info(f"OTP verified and deleted for guest_id: {guest_id}")

        # Fetch guest data
        guest = await self.guest_collection.find_one({"_id": ObjectId(guest_id)})
        if not guest:
            logger.error(f"Guest not found after OTP verification: {guest_id}")
            return {"success": False, "error": "Guest not found"}

        # Determine auth method from OTP record's contact_type
        contact_type = record.get("contact_type", "phone")
        auth_method = f"{contact_type}_otp"

        return {
            "success": True,
            "guest": self._serialize_guest_response(guest),
            "auth_method": auth_method,
        }

    async def send_otp_by_contact(self, wedding_id: str, contact: str) -> dict:
        """
        Send OTP to a guest by their contact info (phone/email) for a specific wedding.
        Returns dict with success status and contact type.

        Security: Rate limited to prevent OTP spam attacks.
        """
        # Normalize phone number for comparison
        normalized_contact = contact.strip()
        if normalized_contact.startswith("+"):
            contact_variants = [normalized_contact, normalized_contact[1:]]
            if normalized_contact.startswith("+1"):
                contact_variants.append(normalized_contact[2:])
        else:
            contact_variants = [
                normalized_contact,
                f"+{normalized_contact}",
                f"+1{normalized_contact}",
            ]

        # Find guest by contact (phone or email) and wedding_id
        guest = await self.guest_collection.find_one(
            {
                "wedding_id": wedding_id,
                "$or": [
                    {"phone": {"$in": contact_variants}},
                    {"email": normalized_contact},
                ],
            }
        )

        if not guest:
            logger.warning(
                f"Guest not found for contact: {contact} in wedding: {wedding_id}"
            )
            return {"success": False, "error": "Guest not found for this wedding"}

        guest_id = str(guest["_id"])

        # Ensure TTL index exists
        await self._ensure_indexes()

        # Check for existing OTP and handle rate limiting
        last_otp = await self.otp_collection.find_one({"guest_id": guest_id})
        if last_otp:
            expires_at = _ensure_utc(last_otp.get("expires_at"))
            created_at = _ensure_utc(last_otp.get("created_at"))
            if expires_at:
                # If OTP has expired, delete it and allow new request
                if expires_at <= datetime.now(timezone.utc):
                    await self.otp_collection.delete_one({"_id": last_otp["_id"]})
                    logger.debug(f"Deleted expired OTP for guest_id: {guest_id}")
                # Rate limit using settings.rate_limit_auth_period (default 60 seconds)
                elif created_at:
                    seconds_since_created = (
                        datetime.now(timezone.utc) - created_at
                    ).total_seconds()
                    if seconds_since_created < settings.rate_limit_auth_period:
                        remaining = int(
                            settings.rate_limit_auth_period - seconds_since_created
                        )
                        logger.info(
                            f"Rate limited OTP request for guest_id: {guest_id} (sent {seconds_since_created:.0f}s ago)"
                        )
                        return {
                            "success": False,
                            "error": f"Please wait {remaining} seconds before requesting another code",
                            "error_code": "rate_limited",
                            "retry_after": remaining,
                        }

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
            if not phone.startswith("+"):
                phone = f"+1{phone}"

            twilio_service = self._get_twilio_service()
            if not twilio_service:
                return {
                    "success": False,
                    "error": self._get_user_friendly_sms_error("not_configured"),
                    "error_code": "not_configured",
                }

            result = twilio_service._send_sms(phone, message)
            status = result.get("status") if isinstance(result, dict) else result
            sms_error_code = (
                result.get("error_code") if isinstance(result, dict) else None
            )
            if status == "success":
                return {
                    "success": True,
                    "contact_type": "phone",
                    "fallback_used": False,
                }
            else:
                user_error = self._get_user_friendly_sms_error(sms_error_code)
                return {
                    "success": False,
                    "error": user_error,
                    "error_code": sms_error_code or "sms_failed",
                    "retry_after": 30
                    if sms_error_code
                    in ("rate_limited", "daily_limit", "service_unavailable")
                    else None,
                }

        elif guest.get("email") == normalized_contact:
            # Send via email
            html_content = self._generate_otp_email_html(
                otp, guest.get("name", "Guest")
            )
            result = await self.email_service.send_email(
                to_email=normalized_contact,
                subject="Your RSVP Verification Code",
                html_content=html_content,
                email_type="otp",
            )
            if result.get("success"):
                return {"success": True, "contact_type": "email"}
            else:
                logger.error(f"Failed to send OTP email: {result.get('error')}")
                return {
                    "success": False,
                    "error": f"Failed to send email: {result.get('error')}",
                }

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
