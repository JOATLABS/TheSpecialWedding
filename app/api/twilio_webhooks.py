"""
Twilio webhook handlers for SMS delivery tracking and incoming messages.

This module handles all Twilio webhooks:
1. StatusCallback - Delivery status updates (delivered/failed/undelivered)
2. Incoming Messages - STOP/HELP/START and guest support messages

These are webhook endpoints called by Twilio, NOT admin operations.
"""

from fastapi import APIRouter, Request, HTTPException, Header
from typing import Optional
from datetime import datetime, timezone
from app.core.database import mongo
import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook/twilio")


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


# ==================== INCOMING MESSAGE WEBHOOK ====================

@router.get("/incoming", tags=["Webhooks"])
async def verify_twilio_incoming_webhook():
    """
    Webhook verification endpoint for Twilio incoming messages.
    Returns 200 OK to confirm the endpoint is active.
    """
    return {"status": "ok", "message": "Twilio incoming message webhook endpoint active"}


@router.post("/incoming", tags=["Webhooks"])
async def handle_twilio_incoming_message(
    request: Request,
    x_twilio_signature: Optional[str] = Header(None, alias="X-Twilio-Signature")
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
        data = dict(form_data)

        # Validate webhook signature
        if not _validate_twilio_signature(request, x_twilio_signature, data):
            logger.warning("Invalid Twilio webhook signature for incoming message")
            raise HTTPException(status_code=401, detail="Invalid signature")

        from_number = data.get("From", "")
        body = data.get("Body", "").strip().upper()
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
        guest = await guest_collection.find_one({
            "$or": [
                {"phone": from_number},
                {"phone": normalized_number},
                {"phone": f"1{normalized_number}"}
            ]
        })

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
                    planner = await mongo.get_users_collection().find_one({"email": assigned_planner_email})
                    if planner:
                        planner_name = planner.get("company_name") or planner.get("email")
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
                        {"phone": f"1{normalized_number}"}
                    ]
                },
                {
                    "$set": {
                        "sms_opt_in": False,
                        "sms_opt_out_date": datetime.now(timezone.utc)
                    }
                }
            )
            logger.info(f"Opted out {result.modified_count} guests with phone {from_number}")

            # Send confirmation
            confirmation_msg = f"You have been unsubscribed from {wedding_name} SMS notifications. Reply START to resubscribe."
            sms_service.send_sms(from_number, confirmation_msg)

            return {"status": "ok", "action": "opt_out", "modified": result.modified_count}

        # Handle START messages (opt-in)
        elif body in ["START", "UNSTOP", "YES", "SUBSCRIBE"]:
            result = await guest_collection.update_many(
                {
                    "$or": [
                        {"phone": from_number},
                        {"phone": normalized_number},
                        {"phone": f"1{normalized_number}"}
                    ]
                },
                {
                    "$set": {
                        "sms_opt_in": True,
                        "sms_opt_in_date": datetime.now(timezone.utc)
                    },
                    "$unset": {
                        "sms_opt_out_date": ""
                    }
                }
            )
            logger.info(f"Re-subscribed {result.modified_count} guests with phone {from_number}")

            # Send welcome message
            welcome_msg = f"Welcome back! You're subscribed to reminders for {wedding_name}. Reply STOP to opt out. Msg&data rates may apply."
            sms_service.send_sms(from_number, welcome_msg)

            return {"status": "ok", "action": "opt_in", "modified": result.modified_count}

        # Handle HELP messages
        elif body in ["HELP", "INFO"]:
            # Build HELP response
            if planner_support_phone:
                help_msg = f"Wedding reminders from {wedding_name}. Reply STOP to unsubscribe. For support, call {planner_support_phone}. Msg&data rates may apply."
            else:
                help_msg = f"Wedding reminders from {wedding_name}. Reply STOP to unsubscribe. For support, visit thespecialwedding.com/support. Msg&data rates may apply."
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
                    "type": "help_request"
                }
                await mongo.db["support_tickets"].insert_one(help_ticket)
                await _notify_planner_help_request(help_ticket, assigned_planner_email, wedding_name)
                logger.info(f"HELP request from {from_number} - planner {assigned_planner_email} notified")

            return {"status": "ok", "action": "help"}

        # Handle any other message (support ticket)
        else:
            # Create support ticket routed to wedding planner
            support_ticket = {
                "phone": from_number,
                "message": data.get("Body", ""),
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
                "priority": "normal"
            }
            await mongo.db["support_tickets"].insert_one(support_ticket)
            logger.info(f"Support ticket created from {from_number} for planner {assigned_planner_email}")

            # Send acknowledgment
            contact_info = f"your wedding planner at {planner_name}" if planner_name else "us"
            if planner_support_phone:
                support_msg = f"Thanks for your message! {contact_info.capitalize()} will respond soon. For urgent matters, call {planner_support_phone}."
            else:
                support_msg = f"Thanks for your message! {contact_info.capitalize()} will respond soon."
            sms_service.send_sms(from_number, support_msg)

            # Notify wedding planner
            if assigned_planner_email:
                await _notify_planner_support_ticket(support_ticket, assigned_planner_email)
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
                <p><strong>Wedding:</strong> {ticket['wedding_name']}</p>
                <p><strong>From:</strong> {ticket['phone']}</p>
                <p><strong>Received:</strong> {ticket['created_at'].strftime('%B %d, %Y at %I:%M %p UTC')}</p>
            </div>

            <div style="background-color: #fff; padding: 20px; border-left: 4px solid #2c3e50; margin: 20px 0;">
                <p style="margin: 0;"><em>"{ticket['message']}"</em></p>
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
                This notification was sent because you are the wedding planner for {ticket['wedding_name']}.
            </p>
        </div>
        """

        await email_service.send_email(
            to_email=planner_email,
            subject=subject,
            html_content=html_content,
            wedding_id=ticket.get('wedding_id'),
            email_type="support_notification"
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
        root_admin_email = os.getenv("ROOT_ADMIN_EMAIL", "thedeveloper@thespecialwedding.com")

        # Log to errors collection for dashboard visibility
        error_record = {
            "error_id": f"unassigned_ticket_{ticket.get('message_sid', datetime.now(timezone.utc).timestamp())}",
            "error_type": "UnassignedSupportTicket",
            "message": f"SMS from {ticket['phone']} has no assigned planner - wedding: {ticket.get('wedding_name', 'Unknown')}",
            "severity": "warning",
            "timestamp": datetime.now(timezone.utc),
            "acknowledged": False,
            "context": {
                "phone": ticket['phone'],
                "wedding_name": ticket.get('wedding_name'),
                "wedding_id": ticket.get('wedding_id'),
                "sms_message": ticket['message'],
                "source": "twilio_incoming_sms"
            }
        }
        await mongo.db["errors"].insert_one(error_record)
        logger.info("Unassigned ticket logged to errors collection")

        # Send email to ROOT_ADMIN
        await _notify_planner_support_ticket(ticket, root_admin_email)

    except Exception as e:
        logger.error(f"Failed to send ROOT_ADMIN notification: {str(e)}")


async def _notify_planner_help_request(ticket: dict, planner_email: str, wedding_name: str):
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
                <p><strong>From:</strong> {ticket['phone']}</p>
                <p><strong>Received:</strong> {ticket['created_at'].strftime('%B %d, %Y at %I:%M %p UTC')}</p>
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
            wedding_id=ticket.get('wedding_id'),
            email_type="help_request_notification"
        )
        logger.info(f"HELP request notification sent to planner {planner_email}")
    except Exception as e:
        logger.error(f"Failed to send HELP request notification to planner: {str(e)}")
