# app/api/reminder_telnyx.py

from fastapi import APIRouter, HTTPException, Depends, Query
from app.services.reminder_service_telnyx import TelnyxReminderService
from app.services.reminder_utilities_telnyx import TelnyxRSVPReminderHelper
from app.dependencies.auth_extended import require_wedding_planner_only, ExtendedAuthUser, check_wedding_access
from app.services.wedding_service import WeddingService
from pydantic import BaseModel
from typing import Optional

router = APIRouter()
wedding_service = WeddingService()

# Initialize Telnyx services
try:
    telnyx_reminder_service = TelnyxReminderService()
    telnyx_helper = TelnyxRSVPReminderHelper()
    telnyx_available = True
except Exception as e:
    print(f"Telnyx services not available: {str(e)}")
    telnyx_available = False
    telnyx_reminder_service = None
    telnyx_helper = None

class SlugModel(BaseModel):
    slug: str
    custom_message: Optional[str] = None

class TelnyxReminderModel(BaseModel):
    wedding_slug: str
    event_type: str
    message: str
    target_group: str = "all"

@router.get("/reminders/telnyx/status", tags=["Admin"])
def get_telnyx_status():
    """Check if Telnyx services are configured and available"""
    return {
        "available": telnyx_available,
        "message": "Telnyx configured and ready" if telnyx_available else "Telnyx not configured"
    }

@router.post("/reminders/telnyx/send", tags=["Admin"])
def send_reminder_telnyx(payload: TelnyxReminderModel, current_user: ExtendedAuthUser = Depends(require_wedding_planner_only)):
    """Send SMS reminders using Telnyx"""
    if not telnyx_available:
        raise HTTPException(status_code=503, detail="Telnyx service not configured")
    
    # Get wedding and verify access
    wedding = wedding_service.get_wedding_by_slug(payload.wedding_slug)
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")

    if not check_wedding_access(current_user, wedding["_id"]):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    return telnyx_reminder_service.send_reminders(payload.event_type, payload.message, payload.target_group)

@router.post("/reminders/telnyx/send-invites", tags=["Admin"])
def send_invites_telnyx(payload: SlugModel, current_user: ExtendedAuthUser = Depends(require_wedding_planner_only)):
    """Send RSVP invite links using Telnyx"""
    if not telnyx_available:
        raise HTTPException(status_code=503, detail="Telnyx service not configured")
    
    # Get wedding and verify access
    wedding = wedding_service.get_wedding_by_slug(payload.slug)
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")

    if not check_wedding_access(current_user, wedding["_id"]):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    return telnyx_helper.send_personalized_rsvp_links(
        slug=payload.slug, 
        custom_message=payload.custom_message
    )

@router.get("/reminders/telnyx/logs", tags=["Admin"])
def get_telnyx_logs(current_user: ExtendedAuthUser = Depends(require_wedding_planner_only), wedding_slug: Optional[str] = Query(None)):
    """Get SMS logs for messages sent via Telnyx"""
    if not telnyx_available:
        raise HTTPException(status_code=503, detail="Telnyx service not configured")
    
    # If wedding_slug is provided, verify access to that wedding
    if wedding_slug:
        wedding = wedding_service.get_wedding_by_slug(wedding_slug)
        if not wedding:
            raise HTTPException(status_code=404, detail="Wedding not found")

        if not check_wedding_access(current_user, wedding["_id"]):
            raise HTTPException(status_code=403, detail="Access to this wedding denied")

    # For non-root admin users, they should only see logs for their weddings
    # This would require modification of the get_logs method to filter by user
    return telnyx_reminder_service.get_logs()