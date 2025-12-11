# app/api/reminder_twilio.py

from fastapi import APIRouter, HTTPException, Depends, Query
from app.services.reminder_service_twilio import (
    TwilioReminderService,
    TwilioRSVPReminderHelper,
    twilio_configured
)
from app.dependencies.auth_extended import require_root_admin, require_admin_or_planner, ExtendedAuthUser
from app.core.database import mongo
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
