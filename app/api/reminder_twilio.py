# app/api/reminder_twilio.py

from fastapi import APIRouter, HTTPException, Depends, Query
from app.services.reminder_service_twilio import (
    TwilioReminderService,
    TwilioRSVPReminderHelper,
    twilio_configured,
    twilio_client,
    MESSAGING_SERVICE_SID
)
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
if twilio_configured:
    twilio_reminder_service = TwilioReminderService()
    twilio_helper = TwilioRSVPReminderHelper()
else:
    twilio_reminder_service = None
    twilio_helper = None

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
def send_reminder_twilio(
    event_type: str = Query(..., description="Event type: traditional, white_wedding, or reception"),
    message: str = Query(..., description="Message to send"),
    target_group: str = Query(..., description="Target group: guests, plus-ones, or all")
):
    """Send SMS reminders using Twilio"""
    if not twilio_configured or not twilio_reminder_service:
        raise HTTPException(status_code=503, detail="Twilio service not configured")

    return twilio_reminder_service.send_reminders(event_type, message, target_group)

@router.post("/reminders/twilio/send-invites", tags=["Admin"], dependencies=[Depends(require_admin_or_planner)])
def send_invites_twilio(payload: SlugModel):
    """Send RSVP invite links using Twilio"""
    if not twilio_configured or not twilio_helper:
        raise HTTPException(status_code=503, detail="Twilio service not configured")

    return twilio_helper.send_personalized_rsvp_links(
        slug=payload.slug,
        custom_message=payload.custom_message
    )

@router.post("/reminders/send-to-guests", tags=["Admin"], dependencies=[Depends(require_admin_or_planner)])
async def send_individual_reminders(payload: IndividualReminderRequest):
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
    logs = []
    now = datetime.now(timezone.utc)

    from_number = os.getenv("TWILIO_FROM_NUMBER") or os.getenv("TWILIO_PHONE_NUMBER")

    for token in payload.guest_tokens:
        # Find guest by token
        guest = await guest_collection.find_one({"token": token})

        if not guest:
            logger.warning(f"Guest not found for token: {token}")
            failed_count += 1
            continue

        phone = guest.get("phone")
        if not phone:
            logger.warning(f"Guest {guest.get('name')} has no phone number")
            failed_count += 1
            continue

        # Check if guest has explicitly opted out
        if guest.get("sms_opt_in") == False:
            logger.info(f"Guest {guest.get('name')} has opted out of SMS")
            failed_count += 1
            continue

        # Ensure phone is in E.164 format
        if not phone.startswith('+'):
            phone = f"+1{phone}"

        # Send SMS
        status = "failed"
        try:
            # Try messaging service first, fallback to direct number
            try:
                message = twilio_client.messages.create(
                    messaging_service_sid=MESSAGING_SERVICE_SID,
                    body=payload.message,
                    to=phone
                )
            except Exception as msg_service_error:
                logger.warning(f"Messaging service failed, trying direct number: {msg_service_error}")
                message = twilio_client.messages.create(
                    from_=from_number,
                    body=payload.message,
                    to=phone
                )

            logger.info(f"SMS sent to {phone}, SID: {message.sid}")
            sent_count += 1
            status = "success"
        except Exception as e:
            logger.error(f"Failed to send SMS to {phone}: {e}")
            failed_count += 1
            status = f"failed: {str(e)}"

        # Log the attempt
        logs.append({
            "phone": phone,
            "guest_id": str(guest["_id"]),
            "wedding_id": str(guest.get("wedding_id")) if guest.get("wedding_id") else None,
            "message": payload.message,
            "target_type": "guest",
            "event_type": "individual_reminder",
            "status": status,
            "sent_at": now,
            "provider": "twilio"
        })

    # Save logs
    if logs:
        await log_collection.insert_many(logs)

    return {
        "sent": sent_count,
        "failed": failed_count,
        "total": len(payload.guest_tokens),
        "provider": "twilio"
    }


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
