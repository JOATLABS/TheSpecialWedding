"""
Twilio Status Callback webhook handler for SMS delivery tracking.

Twilio sends StatusCallback webhooks for message state changes.
This module processes delivery events and updates the reminders_sent collection.

Status Flow: accepted -> queued -> sending -> sent -> delivered/failed/undelivered
"""

from fastapi import APIRouter, Request, HTTPException, Header
from typing import Optional
from datetime import datetime, timezone
from app.core.database import mongo
import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter()


# Twilio error code to human-readable message mapping
TWILIO_ERROR_MESSAGES = {
    "30001": "Queue overflow - message queue is full",
    "30002": "Account suspended",
    "30003": "Unreachable destination handset",
    "30004": "Message blocked",
    "30005": "Unknown destination handset",
    "30006": "Landline or unreachable carrier",
    "30007": "Carrier violation",
    "30008": "Unknown error",
    "30009": "Missing segment",
    "30010": "Message price exceeds max price",
    "21211": "Invalid phone number format",
    "21408": "Permission denied",
    "21610": "Attempt to send to unsubscribed recipient",
    "21612": "The 'To' number is not a valid phone number",
    "21614": "Invalid mobile number"
}


@router.get("/webhook/twilio/status", tags=["Webhooks"])
async def verify_twilio_status_webhook():
    """
    Webhook verification endpoint for Twilio.
    Returns 200 OK to confirm the endpoint is active.
    """
    return {"status": "ok", "message": "Twilio status webhook endpoint active"}


@router.post("/webhook/twilio/status", tags=["Webhooks"])
async def handle_twilio_status_callback(
    request: Request,
    x_twilio_signature: Optional[str] = Header(None, alias="X-Twilio-Signature")
):
    """
    Handle Twilio StatusCallback events for SMS delivery tracking.

    Twilio sends these status updates:
    - accepted: Message accepted by Twilio
    - queued: Message queued for delivery
    - sending: Message currently being sent
    - sent: Message sent to carrier
    - delivered: Carrier confirmed delivery
    - failed: Message could not be delivered
    - undelivered: Carrier could not deliver

    Payload Fields (form-encoded):
    - MessageSid: Unique message identifier
    - AccountSid: Twilio account
    - MessagingServiceSid: If using messaging service
    - From: Sender phone number
    - To: Recipient phone number
    - MessageStatus: Current delivery status
    - ErrorCode: Error code if failed (optional)
    """
    try:
        # Get form data (Twilio sends form-encoded data, not JSON)
        form_data = await request.form()
        data = dict(form_data)

        # Validate webhook signature
        if not _validate_twilio_signature(request, x_twilio_signature, data):
            logger.warning("Invalid Twilio webhook signature")
            raise HTTPException(status_code=401, detail="Invalid signature")

        # Extract payload fields
        message_sid = data.get("MessageSid")
        message_status = data.get("MessageStatus")
        error_code = data.get("ErrorCode")
        to_number = data.get("To")

        if not message_sid or not message_status:
            logger.warning(f"Missing required fields in Twilio callback: {data}")
            return {"status": "ignored", "reason": "Missing required fields"}

        logger.info(f"Received Twilio status callback: SID={message_sid}, Status={message_status}")

        # Update the reminders_sent record
        log_collection = mongo.db["reminders_sent"]

        now = datetime.now(timezone.utc)

        # Build the status event for history
        status_event = {
            "status": message_status,
            "timestamp": now,
            "error_code": int(error_code) if error_code else None
        }

        # Prepare update operation
        update_data = {
            "$set": {
                "delivery_status": message_status,
                "delivery_status_updated_at": now
            },
            "$push": {
                "delivery_events": status_event
            }
        }

        # Add error details if present
        if error_code:
            error_message = TWILIO_ERROR_MESSAGES.get(
                str(error_code),
                f"Unknown error (code: {error_code})"
            )
            update_data["$set"]["error_code"] = int(error_code)
            update_data["$set"]["error_message"] = error_message

        # Find and update by message_sid
        result = await log_collection.update_one(
            {"message_sid": message_sid},
            update_data
        )

        if result.matched_count == 0:
            # Log but don't fail - message might have been sent before we added tracking
            logger.warning(f"No record found for MessageSid: {message_sid}")
            return {"status": "not_found", "message_sid": message_sid}

        logger.info(f"Updated delivery status for {message_sid}: {message_status}")

        return {
            "status": "success",
            "message_sid": message_sid,
            "delivery_status": message_status
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing Twilio status callback: {str(e)}")
        # Return 200 to prevent Twilio retries for unrecoverable errors
        return {"status": "error", "message": str(e)}


def _validate_twilio_signature(
    request: Request,
    signature: Optional[str],
    params: dict
) -> bool:
    """
    Validate Twilio webhook signature using RequestValidator.

    Twilio signs webhooks with HMAC-SHA1 using your Auth Token.
    The signature is in the X-Twilio-Signature header.
    """
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")

    if not auth_token:
        logger.warning("TWILIO_AUTH_TOKEN not configured - skipping signature verification")
        return True  # Allow in development, but log warning

    if not signature:
        # In production, require signature. In development, allow without.
        environment = os.getenv("ENVIRONMENT", "development")
        if environment == "production":
            logger.warning("No X-Twilio-Signature header present in production")
            return False
        logger.warning("No X-Twilio-Signature header present - allowing in non-production")
        return True

    try:
        from twilio.request_validator import RequestValidator

        validator = RequestValidator(auth_token)

        # Construct the full URL (Twilio validates against the exact URL)
        url = str(request.url)

        # Validate the request
        return validator.validate(url, params, signature)

    except ImportError:
        logger.warning("twilio package not available for signature validation")
        return True
    except Exception as e:
        logger.error(f"Signature validation error: {str(e)}")
        return False
