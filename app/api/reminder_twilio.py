# app/api/reminder_twilio.py

from fastapi import APIRouter, HTTPException, Depends, Query
from app.services.reminder_service_twilio import (
    TwilioReminderService,
    TwilioRSVPReminderHelper,
    twilio_configured
)
from app.dependencies.auth_extended import require_root_admin, require_admin_or_planner
from pydantic import BaseModel
from typing import Optional

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

@router.get("/reminders/twilio/logs", tags=["Admin"], dependencies=[Depends(require_root_admin)])
def get_twilio_logs():
    """Get SMS logs for messages sent via Twilio (Root Admin only)"""
    if not twilio_configured or not twilio_reminder_service:
        raise HTTPException(status_code=503, detail="Twilio service not configured")

    return twilio_reminder_service.get_logs()

@router.get("/reminders/logs", tags=["Admin"], dependencies=[Depends(require_admin_or_planner)])
def get_all_logs():
    """Get all SMS logs (for planners)"""
    # This endpoint will return all logs for planners. Since we only have Twilio logs,
    # we can return them for now. In the future, this can be expanded to include other providers.
    if not twilio_configured or not twilio_reminder_service:
        return []

    # For now, we return the same logs as the root admin.
    # The frontend will differentiate based on the user's role.
    return twilio_reminder_service.get_logs()
