"""
Twilio webhook handlers for SMS delivery tracking and incoming messages.

This module handles all Twilio webhooks:
1. StatusCallback - Delivery status updates (delivered/failed/undelivered)
2. Incoming Messages - STOP/HELP/START and guest support messages

These are webhook endpoints called by Twilio, NOT admin operations.
"""

from fastapi import APIRouter, Request, HTTPException, Header
from typing import Any, Optional
from datetime import datetime, timezone
from bson import ObjectId
from starlette.datastructures import FormData, UploadFile
from app.core.database import mongo
import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook/twilio")

TwilioWebhookParams = dict[str, str]


def _to_object_id(id_value: str):
    """Safely convert a string to a BSON ObjectId, falling back to the original value."""
    try:
        return ObjectId(id_value)
    except Exception:
        return id_value


def _normalize_twilio_form_data(form_data: FormData) -> TwilioWebhookParams:
    """Convert Starlette form data into the string-only payload Twilio documents."""
    payload: TwilioWebhookParams = {}
    for key, value in form_data.items():
        if isinstance(value, str):
            payload[key] = value
            continue

        if isinstance(value, UploadFile):
            logger.warning(
                "Ignoring unexpected uploaded file for Twilio webhook field %s (filename=%s)",
                key,
                value.filename,
            )
            continue

        logger.warning(
            "Ignoring unexpected non-string Twilio webhook field %s of type %s",
            key,
            type(value).__name__,
        )

    return payload


def _parse_optional_int(raw_value: Optional[str], field_name: str) -> Optional[int]:
    """Parse optional integer webhook fields without failing the webhook request."""
    if raw_value is None:
        return None

    normalized = raw_value.strip()
    if not normalized:
        return None

    try:
        return int(normalized)
    except ValueError:
        logger.warning(
            "Ignoring invalid integer value for Twilio webhook field %s: %r",
            field_name,
            raw_value,
        )
        return None


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
    "21614": "Invalid mobile number",
}


@router.get("/status", tags=["Webhooks"])
async def verify_twilio_status_webhook():
    """
    Webhook verification endpoint for Twilio delivery status callbacks.
    Returns 200 OK to confirm the endpoint is active.
    """
    return {"status": "ok", "message": "Twilio status webhook endpoint active"}


@router.post("/status", tags=["Webhooks"])
async def handle_twilio_status_callback(
    request: Request,
    x_twilio_signature: Optional[str] = Header(None, alias="X-Twilio-Signature"),
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
        data = _normalize_twilio_form_data(form_data)

        # Validate webhook signature
        if not _validate_twilio_signature(request, x_twilio_signature, data):
            logger.warning("Invalid Twilio webhook signature")
            raise HTTPException(status_code=401, detail="Invalid signature")

        # Extract payload fields
        message_sid = data.get("MessageSid")
        message_status = data.get("MessageStatus")
        error_code = data.get("ErrorCode")
        parsed_error_code = _parse_optional_int(error_code, "ErrorCode")
        to_number = data.get("To")

        if not message_sid or not message_status:
            logger.warning(f"Missing required fields in Twilio callback: {data}")
            return {"status": "ignored", "reason": "Missing required fields"}

        logger.info(
            f"Received Twilio status callback: SID={message_sid}, Status={message_status}"
        )

        # Update the reminders_sent record
        log_collection = mongo.db["reminders_sent"]

        now = datetime.now(timezone.utc)

        # Build the status event for history
        status_event = {
            "status": message_status,
            "timestamp": now,
            "error_code": parsed_error_code,
        }

        # Prepare update operation
        update_data: dict[str, dict[str, Any]] = {
            "$set": {
                "delivery_status": message_status,
                "delivery_status_updated_at": now,
            },
            "$push": {"delivery_events": status_event},
        }

        # Add error details if present
        if parsed_error_code is not None:
            error_code_key = error_code or str(parsed_error_code)
            error_message = TWILIO_ERROR_MESSAGES.get(
                error_code_key, f"Unknown error (code: {error_code_key})"
            )
            update_data["$set"]["error_code"] = parsed_error_code
            update_data["$set"]["error_message"] = error_message

        # Find and update by message_sid
        result = await log_collection.update_one(
            {"message_sid": message_sid}, update_data
        )

        if result.matched_count == 0:
            # Log but don't fail - message might have been sent before we added tracking
            logger.warning(f"No record found for MessageSid: {message_sid}")
            return {"status": "not_found", "message_sid": message_sid}

        logger.info(f"Updated delivery status for {message_sid}: {message_status}")

        # Take error-based actions for failed/undelivered messages
        if message_status in ("failed", "undelivered") and parsed_error_code is not None:
            await _handle_delivery_failure(
                message_sid=message_sid,
                error_code=parsed_error_code,
                to_number=to_number,
                log_collection=log_collection,
            )

        return {
            "status": "success",
            "message_sid": message_sid,
            "delivery_status": message_status,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing Twilio status callback: {str(e)}")
        # Return 200 to prevent Twilio retries for unrecoverable errors
        return {"status": "error", "message": str(e)}


def _get_public_webhook_url(request: Request) -> str:
    """
    Reconstruct the public-facing URL for Twilio signature validation.

    Behind a reverse proxy (Coolify/Caddy/Nginx), request.url returns the
    internal container URL (e.g. http://localhost:8000/...) but Twilio signs
    against the public URL (e.g. https://thespecialwedding.io/...).

    Priority:
    1. TWILIO_WEBHOOK_BASE_URL env var (most reliable)
    2. X-Forwarded-Proto + X-Forwarded-Host headers from reverse proxy
    3. FRONTEND_URL env var as a fallback
    4. request.url as last resort
    """
    # Option 1: Explicit webhook base URL
    webhook_base = os.getenv("TWILIO_WEBHOOK_BASE_URL")
    if webhook_base:
        return webhook_base.rstrip("/") + str(request.url.path)

    # Option 2: Use forwarded headers from the reverse proxy
    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host")
    if forwarded_proto and forwarded_host:
        return f"{forwarded_proto}://{forwarded_host}{request.url.path}"

    # Option 3: Derive from FRONTEND_URL or NEXT_PUBLIC_API_BASE_URL
    for env_var in ("NEXT_PUBLIC_API_BASE_URL", "FRONTEND_URL"):
        base = os.getenv(env_var)
        if base:
            # Strip any trailing path like /admin
            from urllib.parse import urlparse

            parsed = urlparse(base)
            origin = f"{parsed.scheme}://{parsed.netloc}"
            return origin + str(request.url.path)

    # Option 4: Fall back to request.url (works when not behind a proxy)
    return str(request.url)


def _validate_twilio_signature(
    request: Request, signature: Optional[str], params: TwilioWebhookParams
) -> bool:
    """
    Validate Twilio webhook signature using RequestValidator.

    Twilio signs webhooks with HMAC-SHA1 using your Auth Token.
    The signature is in the X-Twilio-Signature header.
    """
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")

    if not auth_token:
        logger.warning(
            "TWILIO_AUTH_TOKEN not configured - skipping signature verification"
        )
        return True  # Allow in development, but log warning

    if not signature:
        # In production, require signature. In development, allow without.
        environment = os.getenv("ENVIRONMENT", "development")
        if environment == "production":
            logger.warning("No X-Twilio-Signature header present in production")
            return False
        logger.warning(
            "No X-Twilio-Signature header present - allowing in non-production"
        )
        return True

    try:
        from twilio.request_validator import RequestValidator  # type: ignore[import-untyped]

        validator = RequestValidator(auth_token)

        # Use the public-facing URL (not the internal container URL)
        url = _get_public_webhook_url(request)

        logger.debug(f"Twilio signature validation URL: {url}")

        # Validate the request
        is_valid = validator.validate(url, params, signature)

        if not is_valid:
            # Log for debugging — show both URLs so we can diagnose mismatches
            internal_url = str(request.url)
            logger.warning(
                f"Twilio signature mismatch | public_url={url} | "
                f"internal_url={internal_url} | "
                f"x-forwarded-proto={request.headers.get('x-forwarded-proto')} | "
                f"x-forwarded-host={request.headers.get('x-forwarded-host')}"
            )

        return is_valid

    except ImportError:
        logger.warning("twilio package not available for signature validation")
        return True
    except Exception as e:
        logger.error(f"Signature validation error: {str(e)}")
        return False


# ==================== DELIVERY FAILURE HANDLER ====================


async def _handle_delivery_failure(
    message_sid: str,
    error_code: int,
    to_number: Optional[str],
    log_collection,
):
    """
    Take action based on the type of delivery failure.

    Actions by error category:
    - account_level: Log critical error + alert ROOT_ADMIN
    - permanent_recipient: Flag guest phone as unverified
    - compliance: Update guest sms_opt_in to False
    - temporary: Queue for retry
    """
    from app.utils.sms_error_classifier import (
        classify_error,
        is_account_level,
        is_permanent_recipient,
        is_compliance,
        should_retry,
    )

    category = classify_error(error_code)
    error_message = TWILIO_ERROR_MESSAGES.get(
        str(error_code), f"Unknown error (code: {error_code})"
    )

    # Look up the original log record to get guest_id and wedding_id
    log_record = await log_collection.find_one({"message_sid": message_sid})
    guest_id = log_record.get("guest_id") if log_record else None
    wedding_id = log_record.get("wedding_id") if log_record else None

    try:
        if is_account_level(error_code):
            # Critical: account suspended, permission denied, etc.
            # Log to errors collection for ROOT_ADMIN dashboard visibility
            await mongo.db["errors"].insert_one(
                {
                    "error_id": f"twilio_account_{error_code}_{message_sid}",
                    "error_type": "TwilioAccountError",
                    "message": f"Twilio account-level error: {error_message}",
                    "severity": "critical",
                    "timestamp": datetime.now(timezone.utc),
                    "acknowledged": False,
                    "context": {
                        "error_code": error_code,
                        "message_sid": message_sid,
                        "to_number": to_number,
                        "source": "twilio_status_callback",
                    },
                }
            )
            logger.critical(f"ACCOUNT-LEVEL Twilio error {error_code}: {error_message}")

            # Email ROOT_ADMIN about account-level issue
            await _notify_root_admin_twilio_error(
                error_code, error_message, message_sid
            )

        elif is_permanent_recipient(error_code):
            # Phone number is permanently unreachable — flag it
            if guest_id:
                guest_collection = mongo.get_guest_collection()
                guest_oid = _to_object_id(guest_id)

                # Determine phone_status based on specific error code
                if error_code == 30006:
                    phone_status = "landline"
                elif error_code in (30003, 30005):
                    phone_status = "unreachable"
                else:
                    phone_status = "invalid"

                await guest_collection.update_one(
                    {"_id": guest_oid},
                    {
                        "$set": {
                            "phone_status": phone_status,
                            "phone_status_updated_at": datetime.now(timezone.utc),
                            "phone_error": error_message,
                        }
                    },
                )
                logger.info(
                    f"Flagged guest {guest_id} phone_status={phone_status}: {error_message}"
                )

        elif is_compliance(error_code):
            # Recipient has opted out or is blocked
            if guest_id:
                guest_collection = mongo.get_guest_collection()
                guest_oid = _to_object_id(guest_id)

                update_fields = {
                    "sms_opt_in": False,
                    "sms_opt_out_date": datetime.now(timezone.utc),
                    "phone_status": "unsubscribed",
                    "phone_status_updated_at": datetime.now(timezone.utc),
                }

                if error_code == 21610:
                    update_fields["sms_opt_out_reason"] = "twilio_unsubscribed"
                elif error_code == 30004:
                    update_fields["sms_opt_out_reason"] = "carrier_blocked"
                elif error_code == 30007:
                    update_fields["sms_opt_out_reason"] = "carrier_violation"

                await guest_collection.update_one(
                    {"_id": guest_oid}, {"$set": update_fields}
                )
                logger.info(
                    f"Set sms_opt_in=False, phone_status=unsubscribed for guest {guest_id} due to Twilio {error_code}"
                )

        elif should_retry(error_code):
            # Queue for retry (temporary error)
            await _queue_for_retry(message_sid, log_record, error_code)

        # Email fallback: if SMS failed and guest has an email, try email
        # Skip fallback for compliance errors (guest opted out) and temporary errors (will be retried)
        if category not in ("compliance", "temporary"):
            await _attempt_email_fallback(
                guest_id=guest_id,
                message_sid=message_sid,
                log_record=log_record,
                log_collection=log_collection,
            )

        # Check hourly delivery rate and alert ROOT_ADMIN if degraded
        await _check_delivery_rate_alert()

        # Notify planner about the failure (for all categories)
        if wedding_id:
            await _notify_planner_delivery_failure(
                wedding_id=wedding_id,
                guest_id=guest_id,
                to_number=to_number,
                error_code=error_code,
                error_message=error_message,
                category=category,
                message_sid=message_sid,
            )

    except Exception as e:
        # Don't let failure handling errors break the webhook response
        logger.error(f"Error in delivery failure handler: {str(e)}")


async def _notify_root_admin_twilio_error(
    error_code: int, error_message: str, message_sid: str
):
    """Email ROOT_ADMIN about an account-level Twilio error."""
    try:
        from app.services.email_service_resend import ResendEmailService

        email_service = ResendEmailService()

        root_admin_email = os.getenv(
            "ROOT_ADMIN_EMAIL", "thedeveloper@thespecialwedding.io"
        )
        subject = f"CRITICAL: Twilio Account Error ({error_code})"

        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #dc2626;">Twilio Account-Level Error</h2>
            <div style="background-color: #fef2f2; padding: 20px; border-radius: 8px; margin: 20px 0; border: 1px solid #fecaca;">
                <p><strong>Error Code:</strong> {error_code}</p>
                <p><strong>Message:</strong> {error_message}</p>
                <p><strong>Message SID:</strong> {message_sid}</p>
                <p><strong>Time:</strong> {datetime.now(timezone.utc).strftime("%B %d, %Y at %I:%M %p UTC")}</p>
            </div>
            <p style="color: #dc2626; font-weight: bold;">
                This error affects ALL SMS sends. Please check the Twilio dashboard immediately.
            </p>
        </div>
        """

        await email_service.send_email(
            to_email=root_admin_email,
            subject=subject,
            html_content=html_content,
            email_type="critical_alert",
        )
        logger.info(f"ROOT_ADMIN alerted about Twilio error {error_code}")
    except Exception as e:
        logger.error(f"Failed to send ROOT_ADMIN Twilio error alert: {str(e)}")


async def _attempt_email_fallback(
    guest_id: Optional[str],
    message_sid: str,
    log_record: Optional[dict],
    log_collection,
):
    """
    Attempt to send the failed SMS message via email as a fallback.
    Only sends if the guest has an email address and hasn't opted out of email.
    """
    if not guest_id or not log_record:
        return

    try:
        guest_collection = mongo.get_guest_collection()
        guest_oid = _to_object_id(guest_id)

        guest = await guest_collection.find_one({"_id": guest_oid})
        if not guest:
            return

        email = guest.get("email")
        if not email:
            return

        # Don't send if guest explicitly opted out of email
        if guest.get("email_opt_in") is False:
            return

        # Check if a fallback was already sent for this message
        existing_fallback = await log_collection.find_one(
            {
                "message_sid": message_sid,
                "fallback_channel": "email",
            }
        )
        if existing_fallback:
            return

        # Send the original message content via email
        from app.services.email_service_resend import ResendEmailService

        email_service = ResendEmailService()

        guest_name = guest.get("name", "Guest")
        original_message = log_record.get("message", "")

        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <p>Dear {guest_name},</p>
                <p>{original_message}</p>
            </div>
            <p style="color: #666; font-size: 12px;">
                This message was originally sent via SMS but could not be delivered.
            </p>
        </div>
        """

        result = await email_service.send_email(
            to_email=email,
            subject="Wedding Update",
            html_content=html_content,
            wedding_id=log_record.get("wedding_id"),
            email_type="sms_fallback",
        )

        # Update the original SMS log record with fallback info
        fallback_status = "sent" if result.get("success") else "failed"
        await log_collection.update_one(
            {"message_sid": message_sid},
            {
                "$set": {
                    "fallback_channel": "email",
                    "fallback_status": fallback_status,
                    "fallback_email": email,
                    "fallback_at": datetime.now(timezone.utc),
                }
            },
        )

        if result.get("success"):
            logger.info(f"Email fallback sent to {email} for failed SMS {message_sid}")
        else:
            logger.warning(
                f"Email fallback also failed for {email}: {result.get('error')}"
            )

    except Exception as e:
        logger.error(f"Error attempting email fallback for {message_sid}: {str(e)}")


async def _check_delivery_rate_alert():
    """
    Check the last 1-hour SMS delivery rate.
    If it drops below 80%, alert ROOT_ADMIN (rate-limited to once per hour).
    """
    from datetime import timedelta

    try:
        now = datetime.now(timezone.utc)
        one_hour_ago = now - timedelta(hours=1)

        # Check if we already sent an alert in the last hour
        recent_alert = await mongo.db["errors"].find_one(
            {"error_type": "SMSDeliveryRateDrop", "timestamp": {"$gte": one_hour_ago}}
        )
        if recent_alert:
            return  # Already alerted recently

        # Calculate delivery rate for the last hour
        pipeline = [
            {"$match": {"provider": "twilio", "sent_at": {"$gte": one_hour_ago}}},
            {
                "$group": {
                    "_id": None,
                    "total": {"$sum": 1},
                    "delivered": {
                        "$sum": {
                            "$cond": [{"$eq": ["$delivery_status", "delivered"]}, 1, 0]
                        }
                    },
                    "failed": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$in": [
                                        "$delivery_status",
                                        ["failed", "undelivered"],
                                    ]
                                },
                                1,
                                0,
                            ]
                        }
                    },
                }
            },
        ]

        cursor = mongo.db["reminders_sent"].aggregate(pipeline)
        stats = await cursor.to_list(length=1)

        if not stats:
            return  # No messages in the last hour

        total = stats[0].get("total", 0)
        delivered = stats[0].get("delivered", 0)
        failed = stats[0].get("failed", 0)

        # Only check if there are enough completed messages to be meaningful
        completed = delivered + failed
        if completed < 5:
            return

        delivery_rate = (delivered / completed * 100) if completed > 0 else 100.0

        threshold = float(os.getenv("SMS_DELIVERY_RATE_ALERT_THRESHOLD", "80"))
        if delivery_rate >= threshold:
            return  # Delivery rate is fine

        # Alert ROOT_ADMIN
        error_record = {
            "error_id": f"delivery_rate_drop_{now.timestamp()}",
            "error_type": "SMSDeliveryRateDrop",
            "message": f"SMS delivery rate dropped to {delivery_rate:.1f}% in the last hour ({delivered}/{completed} delivered, {failed} failed)",
            "severity": "critical",
            "timestamp": now,
            "acknowledged": False,
            "context": {
                "total_sent": total,
                "delivered": delivered,
                "failed": failed,
                "delivery_rate": round(delivery_rate, 1),
                "threshold": threshold,
                "source": "twilio_status_callback_monitor",
            },
        }
        await mongo.db["errors"].insert_one(error_record)

        # Email ROOT_ADMIN
        from app.services.email_service_resend import ResendEmailService

        email_service = ResendEmailService()
        root_admin_email = os.getenv(
            "ROOT_ADMIN_EMAIL", "thedeveloper@thespecialwedding.io"
        )

        await email_service.send_email(
            to_email=root_admin_email,
            subject=f"WARNING: SMS Delivery Rate Drop ({delivery_rate:.1f}%)",
            html_content=f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #f59e0b;">SMS Delivery Rate Alert</h2>
                <div style="background-color: #fffbeb; padding: 20px; border-radius: 8px; border: 1px solid #fde68a;">
                    <p><strong>Delivery Rate:</strong> {delivery_rate:.1f}% (threshold: {threshold}%)</p>
                    <p><strong>Last Hour Stats:</strong></p>
                    <ul>
                        <li>Total sent: {total}</li>
                        <li>Delivered: {delivered}</li>
                        <li>Failed: {failed}</li>
                    </ul>
                    <p><strong>Time:</strong> {now.strftime("%B %d, %Y at %I:%M %p UTC")}</p>
                </div>
                <p>Please check the platform metrics dashboard for details.</p>
            </div>
            """,
            email_type="delivery_rate_alert",
        )
        logger.warning(
            f"ROOT_ADMIN alerted: SMS delivery rate dropped to {delivery_rate:.1f}%"
        )

    except Exception as e:
        logger.error(f"Error checking delivery rate: {str(e)}")


async def _queue_for_retry(
    message_sid: str, log_record: Optional[dict], error_code: int
):
    """Queue a failed message for retry with exponential backoff."""
    from datetime import timedelta

    if not log_record:
        logger.warning(f"Cannot queue retry for {message_sid}: no log record found")
        return

    retry_collection = mongo.db["sms_retry_queue"]

    # Check how many retries have already been attempted
    existing = await retry_collection.find_one({"message_sid": message_sid})
    retry_count = existing.get("retry_count", 0) if existing else 0

    max_retries = 3
    if retry_count >= max_retries:
        logger.info(f"Max retries ({max_retries}) reached for {message_sid}")
        return

    # Exponential backoff: 1min, 5min, 15min
    delays = [60, 300, 900]
    delay_seconds = delays[min(retry_count, len(delays) - 1)]
    retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)

    await retry_collection.update_one(
        {"message_sid": message_sid},
        {
            "$set": {
                "message_sid": message_sid,
                "phone": log_record.get("phone"),
                "message": log_record.get("message"),
                "guest_id": log_record.get("guest_id"),
                "wedding_id": log_record.get("wedding_id"),
                "target_type": log_record.get("target_type"),
                "event_type": log_record.get("event_type"),
                "retry_at": retry_at,
                "retry_count": retry_count + 1,
                "last_error_code": error_code,
                "status": "pending",
                "updated_at": datetime.now(timezone.utc),
            },
            "$setOnInsert": {
                "created_at": datetime.now(timezone.utc),
            },
        },
        upsert=True,
    )
    logger.info(f"Queued retry #{retry_count + 1} for {message_sid} at {retry_at}")


async def _notify_planner_delivery_failure(
    wedding_id: str,
    guest_id: Optional[str],
    to_number: Optional[str],
    error_code: int,
    error_message: str,
    category: str,
    message_sid: str,
):
    """Create a planner notification for an SMS delivery failure."""
    try:
        from app.models.planner_notification import create_notification_document

        wedding_collection = mongo.db["weddings"]

        # Look up the wedding to find the assigned planner
        wedding_oid = _to_object_id(wedding_id)
        wedding = await wedding_collection.find_one({"_id": wedding_oid})
        if not wedding:
            return

        assigned_planner_email = wedding.get("assigned_planner_email")
        if not assigned_planner_email:
            return

        # Look up guest name
        guest_name = "Unknown Guest"
        if guest_id:
            guest_collection = mongo.get_guest_collection()
            guest_oid = _to_object_id(guest_id)
            guest = await guest_collection.find_one({"_id": guest_oid})
            if guest:
                guest_name = guest.get("name", "Unknown Guest")

        # Create in-app notification using the standard document builder
        notification = create_notification_document(
            planner_id=assigned_planner_email,
            notification_type="delivery_failure",
            title=f"SMS delivery failed for {guest_name}",
            message=f"SMS to {to_number or 'unknown'} failed: {error_message}",
            wedding_id=wedding_id,
            metadata={
                "guest_id": guest_id,
                "guest_name": guest_name,
                "phone": to_number,
                "error_code": error_code,
                "error_category": category,
                "message_sid": message_sid,
            },
            priority="high" if category == "account_level" else "medium",
            action_url="/admin/communications/history",
        )

        await mongo.db["planner_notifications"].insert_one(notification)
        logger.info(
            f"Planner notification created for delivery failure: {guest_name} ({to_number})"
        )

    except Exception as e:
        logger.error(
            f"Failed to create planner delivery failure notification: {str(e)}"
        )


# ==================== INCOMING MESSAGE WEBHOOK ====================


@router.get("/incoming", tags=["Webhooks"])
async def verify_twilio_incoming_webhook():
    """
    Webhook verification endpoint for Twilio incoming messages.
    Returns 200 OK to confirm the endpoint is active.
    """
    return {
        "status": "ok",
        "message": "Twilio incoming message webhook endpoint active",
    }


@router.post("/incoming", tags=["Webhooks"])
async def handle_twilio_incoming_message(
    request: Request,
    x_twilio_signature: Optional[str] = Header(None, alias="X-Twilio-Signature"),
):
    """
    Handle incoming SMS messages from Twilio.

    This webhook processes:
    - STOP/UNSUBSCRIBE/CANCEL/END/QUIT - Opt-out from SMS
    - START/UNSTOP/YES/SUBSCRIBE - Opt back into SMS
    - HELP/INFO - Request support information
    - Any other message - Creates a support ticket for the wedding planner

    Twilio sends form-encoded data with fields:
    - MessageSid: Unique message identifier
    - From: Sender phone number
    - To: Recipient phone number (your Twilio number)
    - Body: Message text
    """
    try:
        # Twilio sends form-encoded data
        form_data = await request.form()
        data = _normalize_twilio_form_data(form_data)

        # Validate webhook signature
        if not _validate_twilio_signature(request, x_twilio_signature, data):
            logger.warning("Invalid Twilio webhook signature for incoming message")
            raise HTTPException(status_code=401, detail="Invalid signature")

        from_number = data.get("From", "")
        body_text = data.get("Body", "")
        body = body_text.strip().upper()
        message_sid = data.get("MessageSid")

        if not from_number:
            logger.warning(f"Missing From number in Twilio incoming webhook: {data}")
            return {"status": "ignored", "reason": "Missing From number"}

        logger.info(f"Received incoming SMS from {from_number}: {body[:50]}...")

        guest_collection = mongo.get_guest_collection()
        wedding_collection = mongo.db["weddings"]

        # Normalize phone number for lookup
        normalized_number = from_number.replace("+1", "").replace("+", "")

        # Find guest by phone number
        guest = await guest_collection.find_one(
            {
                "$or": [
                    {"phone": from_number},
                    {"phone": normalized_number},
                    {"phone": f"1{normalized_number}"},
                ]
            }
        )

        # Get wedding name if guest found
        wedding_name = "the wedding"
        wedding_id = None
        assigned_planner_email = None
        planner_name = None
        planner_support_phone = None

        if guest and guest.get("wedding_id"):
            wedding_id = guest["wedding_id"]
            wedding = await wedding_collection.find_one({"_id": wedding_id})
            if wedding:
                wedding_name = wedding.get("couple_names", "the wedding")
                assigned_planner_email = wedding.get("assigned_planner_email")

                if assigned_planner_email:
                    planner = await mongo.get_users_collection().find_one(
                        {"email": assigned_planner_email}
                    )
                    if planner:
                        planner_name = planner.get("company_name") or planner.get(
                            "email"
                        )
                        planner_support_phone = planner.get("support_phone")

        # Import Twilio SMS service for sending responses
        from app.services.sms_service import SMSService

        sms_service = SMSService()

        # Handle STOP messages (opt-out)
        if body in ["STOP", "UNSUBSCRIBE", "CANCEL", "END", "QUIT"]:
            result = await guest_collection.update_many(
                {
                    "$or": [
                        {"phone": from_number},
                        {"phone": normalized_number},
                        {"phone": f"1{normalized_number}"},
                    ]
                },
                {
                    "$set": {
                        "sms_opt_in": False,
                        "sms_opt_out_date": datetime.now(timezone.utc),
                    }
                },
            )
            logger.info(
                f"Opted out {result.modified_count} guests with phone {from_number}"
            )

            # Send confirmation
            confirmation_msg = f"You have been unsubscribed from {wedding_name} SMS notifications. Reply START to resubscribe."
            sms_service.send_sms(from_number, confirmation_msg)

            return {
                "status": "ok",
                "action": "opt_out",
                "modified": result.modified_count,
            }

        # Handle START messages (opt-in)
        elif body in ["START", "UNSTOP", "YES", "SUBSCRIBE"]:
            result = await guest_collection.update_many(
                {
                    "$or": [
                        {"phone": from_number},
                        {"phone": normalized_number},
                        {"phone": f"1{normalized_number}"},
                    ]
                },
                {
                    "$set": {
                        "sms_opt_in": True,
                        "sms_opt_in_date": datetime.now(timezone.utc),
                    },
                    "$unset": {"sms_opt_out_date": ""},
                },
            )
            logger.info(
                f"Re-subscribed {result.modified_count} guests with phone {from_number}"
            )

            # Send welcome message
            welcome_msg = f"Welcome back! You're subscribed to reminders for {wedding_name}. Reply STOP to opt out. Msg&data rates may apply."
            sms_service.send_sms(from_number, welcome_msg)

            return {
                "status": "ok",
                "action": "opt_in",
                "modified": result.modified_count,
            }

        # Handle HELP messages
        elif body in ["HELP", "INFO"]:
            # Build HELP response
            if planner_support_phone:
                help_msg = f"Wedding reminders from {wedding_name}. Reply STOP to unsubscribe. For support, call {planner_support_phone}. Msg&data rates may apply."
            else:
                help_msg = f"Wedding reminders from {wedding_name}. Reply STOP to unsubscribe. For support, visit thespecialwedding.io/support. Msg&data rates may apply."
            sms_service.send_sms(from_number, help_msg)

            # Create help ticket for planner
            if assigned_planner_email:
                help_ticket = {
                    "phone": from_number,
                    "message": "HELP request - Guest requested assistance",
                    "guest_id": str(guest["_id"]) if guest else None,
                    "wedding_id": str(wedding_id) if wedding_id else None,
                    "wedding_name": wedding_name,
                    "assigned_to": assigned_planner_email,
                    "status": "new",
                    "created_at": datetime.now(timezone.utc),
                    "source": "sms",
                    "provider": "twilio",
                    "message_sid": message_sid,
                    "is_read": False,
                    "priority": "high",
                    "type": "help_request",
                }
                await mongo.db["support_tickets"].insert_one(help_ticket)
                await _notify_planner_help_request(
                    help_ticket, assigned_planner_email, wedding_name
                )
                logger.info(
                    f"HELP request from {from_number} - planner {assigned_planner_email} notified"
                )

            return {"status": "ok", "action": "help"}

        # Handle any other message (support ticket)
        else:
            # Create support ticket routed to wedding planner
            support_ticket = {
                "phone": from_number,
                "message": body_text,
                "guest_id": str(guest["_id"]) if guest else None,
                "wedding_id": str(wedding_id) if wedding_id else None,
                "wedding_name": wedding_name,
                "assigned_to": assigned_planner_email,
                "planner_name": planner_name,
                "status": "new",
                "created_at": datetime.now(timezone.utc),
                "source": "sms",
                "provider": "twilio",
                "message_sid": message_sid,
                "is_read": False,
                "priority": "medium",
            }
            await mongo.db["support_tickets"].insert_one(support_ticket)
            logger.info(
                f"Support ticket created from {from_number} for planner {assigned_planner_email}"
            )

            # Send acknowledgment
            contact_info = (
                f"your wedding planner at {planner_name}" if planner_name else "us"
            )
            if planner_support_phone:
                support_msg = f"Thanks for your message! {contact_info.capitalize()} will respond soon. For urgent matters, call {planner_support_phone}."
            else:
                support_msg = f"Thanks for your message! {contact_info.capitalize()} will respond soon."
            sms_service.send_sms(from_number, support_msg)

            # Notify wedding planner
            if assigned_planner_email:
                await _notify_planner_support_ticket(
                    support_ticket, assigned_planner_email
                )
            else:
                await _notify_root_admin_support_ticket(support_ticket)

            return {"status": "ok", "action": "support_ticket"}

    except HTTPException:
        raise
    except Exception as e:
        import traceback

        logger.error(f"Error processing Twilio incoming message: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Return 200 to prevent Twilio retries for unrecoverable errors
        return {"status": "error", "message": str(e)}


# ==================== HELPER FUNCTIONS ====================


async def _notify_planner_support_ticket(ticket: dict, planner_email: str):
    """Send email notification to wedding planner about new support ticket"""
    try:
        from app.services.email_service_resend import ResendEmailService
        from app.core.config import settings

        email_service = ResendEmailService()

        frontend_url = settings.get_required_url("FRONTEND_URL")
        subject = f"New Guest Message: {ticket['wedding_name']}"

        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2c3e50;">New Message from Guest</h2>

            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <p><strong>Wedding:</strong> {ticket["wedding_name"]}</p>
                <p><strong>From:</strong> {ticket["phone"]}</p>
                <p><strong>Received:</strong> {ticket["created_at"].strftime("%B %d, %Y at %I:%M %p UTC")}</p>
            </div>

            <div style="background-color: #fff; padding: 20px; border-left: 4px solid #2c3e50; margin: 20px 0;">
                <p style="margin: 0;"><em>"{ticket["message"]}"</em></p>
            </div>

            <p>Please respond to your guest as soon as possible.</p>

            <div style="margin: 30px 0;">
                <a href="{frontend_url}/admin/support"
                   style="background-color: #2c3e50; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; display: inline-block;">
                    View & Respond in Dashboard
                </a>
            </div>

            <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">

            <p style="color: #666; font-size: 12px;">
                This notification was sent because you are the wedding planner for {ticket["wedding_name"]}.
            </p>
        </div>
        """

        await email_service.send_email(
            to_email=planner_email,
            subject=subject,
            html_content=html_content,
            wedding_id=ticket.get("wedding_id"),
            email_type="support_notification",
        )
        logger.info(f"Email notification sent to planner {planner_email}")
    except Exception as e:
        logger.error(f"Failed to send email notification to planner: {str(e)}")


async def _notify_root_admin_support_ticket(ticket: dict):
    """
    Send notification to ROOT_ADMIN for tickets without assigned planner.
    Logs to errors collection so it appears in the platform monitoring dashboard.
    """
    try:
        root_admin_email = os.getenv(
            "ROOT_ADMIN_EMAIL", "thedeveloper@thespecialwedding.io"
        )

        # Log to errors collection for dashboard visibility
        error_record = {
            "error_id": f"unassigned_ticket_{ticket.get('message_sid', datetime.now(timezone.utc).timestamp())}",
            "error_type": "UnassignedSupportTicket",
            "message": f"SMS from {ticket['phone']} has no assigned planner - wedding: {ticket.get('wedding_name', 'Unknown')}",
            "severity": "warning",
            "timestamp": datetime.now(timezone.utc),
            "acknowledged": False,
            "context": {
                "phone": ticket["phone"],
                "wedding_name": ticket.get("wedding_name"),
                "wedding_id": ticket.get("wedding_id"),
                "sms_message": ticket["message"],
                "source": "twilio_incoming_sms",
            },
        }
        await mongo.db["errors"].insert_one(error_record)
        logger.info("Unassigned ticket logged to errors collection")

        # Send email to ROOT_ADMIN
        await _notify_planner_support_ticket(ticket, root_admin_email)

    except Exception as e:
        logger.error(f"Failed to send ROOT_ADMIN notification: {str(e)}")


async def _notify_planner_help_request(
    ticket: dict, planner_email: str, wedding_name: str
):
    """Send email notification to wedding planner about a HELP request"""
    try:
        from app.services.email_service_resend import ResendEmailService
        from app.core.config import settings

        email_service = ResendEmailService()

        frontend_url = settings.get_required_url("FRONTEND_URL")
        subject = f"Guest Needs Help: {wedding_name}"

        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #dc2626;">Guest Requested Help</h2>

            <div style="background-color: #fef2f2; padding: 20px; border-radius: 8px; margin: 20px 0; border: 1px solid #fecaca;">
                <p><strong>A guest has texted HELP and may need assistance.</strong></p>
                <p><strong>Wedding:</strong> {wedding_name}</p>
                <p><strong>From:</strong> {ticket["phone"]}</p>
                <p><strong>Received:</strong> {ticket["created_at"].strftime("%B %d, %Y at %I:%M %p UTC")}</p>
            </div>

            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <p style="margin: 0;">The guest received an automated response with your support information.
                They may be reaching out to you directly.</p>
            </div>

            <div style="margin: 30px 0;">
                <a href="{frontend_url}/admin/support"
                   style="background-color: #dc2626; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; display: inline-block;">
                    View in Dashboard
                </a>
            </div>

            <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">

            <p style="color: #666; font-size: 12px;">
                This notification was sent because a guest for {wedding_name} requested help via SMS.
            </p>
        </div>
        """

        await email_service.send_email(
            to_email=planner_email,
            subject=subject,
            html_content=html_content,
            wedding_id=ticket.get("wedding_id"),
            email_type="help_request_notification",
        )
        logger.info(f"HELP request notification sent to planner {planner_email}")
    except Exception as e:
        logger.error(f"Failed to send HELP request notification to planner: {str(e)}")
