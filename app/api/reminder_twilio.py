# app/api/reminder_twilio.py

from fastapi import APIRouter, HTTPException, Depends, Query
from app.services.reminder_service_twilio import (
    TwilioReminderService,
    TwilioRSVPReminderHelper,
    twilio_configured,
    twilio_client,
    MESSAGING_SERVICE_SID
)
from app.services.activity_log_service import activity_log_service
from app.dependencies.auth_extended import require_root_admin, require_admin_or_planner, ExtendedAuthUser
from app.core.database import mongo
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
import logging
import os

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize services only if Twilio is configured
twilio_reminder_service: Optional[TwilioReminderService] = None
twilio_helper: Optional[TwilioRSVPReminderHelper] = None

if twilio_configured:
    twilio_reminder_service = TwilioReminderService()
    twilio_helper = TwilioRSVPReminderHelper()


class SlugModel(BaseModel):
    slug: str
    custom_message: Optional[str] = None


class IndividualReminderRequest(BaseModel):
    """Request model for sending reminders to specific guests by their tokens"""
    guest_tokens: List[str]
    message: str


@router.get("/reminders/twilio/status", tags=["Admin"])
def get_twilio_status():
    """Check if Twilio services are configured and available"""
    return {
        "available": twilio_configured,
        "message": "Twilio configured and ready" if twilio_configured else "Twilio not configured"
    }


@router.post("/reminders/twilio/send", tags=["Admin"], dependencies=[Depends(require_admin_or_planner)])
async def send_reminder_twilio(
    event_type: str = Query(..., description="Event type: traditional, white_wedding, or reception"),
    message: str = Query(..., description="Message to send"),
    target_group: str = Query(..., description="Target group: guests, plus-ones, or all")
):
    """Send SMS reminders using Twilio"""
    if not twilio_configured or not twilio_reminder_service:
        raise HTTPException(status_code=503, detail="Twilio service not configured")

    return await twilio_reminder_service.send_reminders(event_type, message, target_group)


@router.post("/reminders/twilio/send-invites", tags=["Admin"])
async def send_invites_twilio(
    payload: SlugModel,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Send RSVP invite links using Twilio"""
    if not twilio_configured or not twilio_helper:
        raise HTTPException(status_code=503, detail="Twilio service not configured")

    result = await twilio_helper.send_personalized_rsvp_links(
        slug=payload.slug,
        custom_message=payload.custom_message
    )

    # Create bulk send summary notification for the planner
    await _create_bulk_send_summary(
        planner_email=current_user.email,
        wedding_slug=payload.slug,
        channel="sms",
        result=result,
    )

    return result


@router.post("/reminders/send-to-guests", tags=["Admin"])
async def send_individual_reminders(
    payload: IndividualReminderRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Send SMS reminders to specific guests by their tokens.
    Used for individual reminder buttons on guest cards and bulk selections.

    This is a flexible endpoint - planners can send any custom message to selected guests.
    """
    if not twilio_configured or not twilio_client:
        raise HTTPException(status_code=503, detail="SMS service not configured")

    if not payload.guest_tokens:
        raise HTTPException(status_code=400, detail="No guest tokens provided")

    if not payload.message or not payload.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    guest_collection = mongo.get_guest_collection()
    log_collection = mongo.db["reminders_sent"]

    sent_count = 0
    failed_count = 0
    failure_reasons = []
    logs = []
    now = datetime.now(timezone.utc)

    from_number = os.getenv("TWILIO_FROM_NUMBER") or os.getenv("TWILIO_PHONE_NUMBER")
    status_callback_url = os.getenv("TWILIO_STATUS_CALLBACK_URL")

    for token in payload.guest_tokens:
        # Find guest by token
        guest = await guest_collection.find_one({"token": token})

        if not guest:
            logger.warning(f"Guest not found for token: {token}")
            failed_count += 1
            failure_reasons.append(f"Guest not found for token: {token}")
            continue

        guest_name = guest.get("name", "Unknown")
        phone = guest.get("phone")
        if not phone:
            logger.warning(f"Guest {guest_name} has no phone number")
            failed_count += 1
            failure_reasons.append(f"{guest_name} has no phone number")
            continue

        # Check opt-in status for subsequent messages (after invite was sent)
        invite_sent = guest.get("invite_sent", False)
        sms_opt_in = guest.get("sms_opt_in")

        # If invite was already sent, check opt-in status
        if invite_sent:
            # After first invite: only send if explicitly opted in
            if sms_opt_in is not True:
                if sms_opt_in is False:
                    logger.info(f"Guest {guest_name} has opted out of SMS")
                    failure_reasons.append(f"{guest_name} has opted out of SMS notifications")
                else:
                    logger.info(f"Guest {guest_name} hasn't opted in to SMS (status: not set)")
                    failure_reasons.append(f"{guest_name} hasn't opted in to SMS notifications yet (please wait for their RSVP)")
                failed_count += 1
                continue
        else:
            # First message: only block if explicitly opted out
            if sms_opt_in is False:
                logger.info(f"Guest {guest_name} has opted out of SMS")
                failed_count += 1
                failure_reasons.append(f"{guest_name} has opted out of SMS notifications")
                continue

        # Ensure phone is in E.164 format
        if not phone.startswith('+'):
            phone = f"+1{phone}"

        # Send SMS with delivery tracking
        status = "failed"
        message_sid = None
        initial_status = None
        try:
            # Build common kwargs for delivery tracking
            send_kwargs = {"body": payload.message, "to": phone}
            if status_callback_url:
                send_kwargs["status_callback"] = status_callback_url

            # Try messaging service first, fallback to direct number
            try:
                message = twilio_client.messages.create(
                    messaging_service_sid=MESSAGING_SERVICE_SID,
                    **send_kwargs
                )
            except Exception as msg_service_error:
                logger.warning(f"Messaging service failed, trying direct number: {msg_service_error}")
                message = twilio_client.messages.create(
                    from_=from_number,
                    **send_kwargs
                )

            logger.info(f"SMS sent to {phone}, SID: {message.sid}")
            sent_count += 1
            status = "success"
            message_sid = message.sid
            initial_status = message.status  # "queued" or "accepted"

            # Mark guest as having received an invite if not already set
            if not invite_sent:
                await guest_collection.update_one(
                    {"_id": guest["_id"]},
                    {"$set": {"invite_sent": True, "invite_sent_date": now}}
                )
                logger.info(f"Set invite_sent=True for guest {guest_name}")
        except Exception as e:
            logger.error(f"Failed to send SMS to {phone}: {e}")
            failed_count += 1
            status = f"failed: {str(e)}"
            failure_reasons.append(f"SMS to {guest_name} failed: {str(e)}")

        # Log the attempt with delivery tracking fields
        log_record = {
            "phone": phone,
            "guest_id": str(guest["_id"]),
            "wedding_id": str(guest.get("wedding_id")) if guest.get("wedding_id") else None,
            "message": payload.message,
            "target_type": "guest",
            "event_type": "individual_reminder",
            "status": status,
            "sent_at": now,
            "provider": "twilio",
            "message_sid": message_sid,
            "delivery_status": initial_status,
            "delivery_status_updated_at": now if message_sid else None,
        }
        if message_sid and initial_status:
            log_record["delivery_events"] = [{
                "status": initial_status,
                "timestamp": now,
                "error_code": None
            }]
        else:
            log_record["delivery_events"] = []
        logs.append(log_record)

    # Save logs
    if logs:
        await log_collection.insert_many(logs)

    # Log activity for planner dashboard - group by wedding_id
    if sent_count > 0:
        try:
            # Group sent logs by wedding_id
            wedding_sent_counts: dict[str, int] = {}
            for log in logs:
                if log.get("status") == "success" and log.get("wedding_id"):
                    wid = log["wedding_id"]
                    wedding_sent_counts[wid] = wedding_sent_counts.get(wid, 0) + 1

            # Log one activity per wedding
            for wedding_id, count in wedding_sent_counts.items():
                await activity_log_service.log_reminder_sent(
                    wedding_id=wedding_id,
                    recipient_count=count,
                    reminder_type="individual",
                    planner_email=current_user.email,
                    channel="sms"
                )
        except Exception as log_err:
            logger.warning(f"Failed to log SMS activity: {log_err}")

    return {
        "sent": sent_count,
        "failed": failed_count,
        "total": len(payload.guest_tokens),
        "provider": "twilio",
        "failure_reasons": failure_reasons if failure_reasons else None
    }


async def _create_bulk_send_summary(
    planner_email: str,
    wedding_slug: str,
    channel: str,
    result: dict,
):
    """Create a planner notification summarizing a bulk send operation."""
    try:
        from app.models.planner_notification import create_notification_document

        sent = result.get("sent", 0)
        failed = result.get("failed", 0)
        skipped_no_phone = result.get("skipped_no_phone", 0)
        skipped_opted_out = result.get("skipped_opted_out", 0)
        total_skipped = skipped_no_phone + result.get("skipped_no_token", 0) + skipped_opted_out

        # Build human-readable summary
        parts = [f"{sent} sent"]
        if failed > 0:
            parts.append(f"{failed} failed")
        if total_skipped > 0:
            parts.append(f"{total_skipped} skipped")

        title = f"SMS Invites: {', '.join(parts)}"

        details = []
        if skipped_no_phone > 0:
            details.append(f"{skipped_no_phone} guests have no phone number")
        if skipped_opted_out > 0:
            details.append(f"{skipped_opted_out} guests opted out of SMS")

        message = f"Bulk {channel.upper()} send completed for wedding '{wedding_slug}'. "
        message += f"{sent} messages sent successfully."
        if details:
            message += " " + ". ".join(details) + "."

        # Look up wedding_id from slug
        wedding = await mongo.db["weddings"].find_one({"slug": wedding_slug}, {"_id": 1})
        wedding_id = str(wedding["_id"]) if wedding else None

        priority = "high" if failed > 0 else "low"

        notification = create_notification_document(
            planner_id=planner_email,
            notification_type="bulk_send_summary",
            title=title,
            message=message,
            wedding_id=wedding_id,
            metadata={
                "sent": sent,
                "failed": failed,
                "skipped_no_phone": skipped_no_phone,
                "skipped_opted_out": skipped_opted_out,
                "channel": channel,
                "wedding_slug": wedding_slug,
            },
            priority=priority,
            action_url="/admin/reminders?tab=history",
        )

        await mongo.db["planner_notifications"].insert_one(notification)
        logger.info(f"Bulk send summary notification created for {planner_email}: {title}")

    except Exception as e:
        logger.warning(f"Failed to create bulk send summary notification: {str(e)}")


@router.get("/reminders/twilio/logs", tags=["Admin"], dependencies=[Depends(require_root_admin)])
async def get_twilio_logs():
    """Get SMS logs for messages sent via Twilio (Root Admin only)"""
    if not twilio_configured or not twilio_reminder_service:
        raise HTTPException(status_code=503, detail="Twilio service not configured")

    return await twilio_reminder_service.get_logs()


@router.get("/reminders/logs", tags=["Admin"])
async def get_all_logs(current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    """Get SMS logs - filtered by wedding for planners"""
    if not twilio_configured or not twilio_reminder_service:
        return []

    # Root admin can see all logs
    if current_user.is_root_admin:
        return await twilio_reminder_service.get_logs()

    # Wedding planners can only see logs for their assigned weddings
    if current_user.is_wedding_planner:
        # Get weddings assigned to this planner
        weddings_cursor = mongo.db["weddings"].find(
            {"assigned_planner_email": current_user.email},
            {"_id": 1}
        )
        weddings = await weddings_cursor.to_list(length=None)
        wedding_ids = [w["_id"] for w in weddings]

        if not wedding_ids:
            return []

        # Get logs only for those weddings
        logs_cursor = mongo.db["reminders_sent"].find(
            {"wedding_id": {"$in": wedding_ids}},
            {"_id": 0}
        ).sort("sent_at", -1).limit(500)
        return await logs_cursor.to_list(length=500)

    return []
