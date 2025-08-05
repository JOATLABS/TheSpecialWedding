# app/api/reminder_telnyx.py

from fastapi import APIRouter, HTTPException, Depends, Query
from app.services.reminder_service_telnyx import TelnyxReminderService
from app.services.reminder_utilities_telnyx import TelnyxRSVPReminderHelper
from app.dependencies.auth import require_admin
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

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

@router.get("/reminders/telnyx/status", tags=["Admin"])
def get_telnyx_status():
    """Check if Telnyx services are configured and available"""
    return {
        "available": telnyx_available,
        "message": "Telnyx configured and ready" if telnyx_available else "Telnyx not configured"
    }

@router.post("/reminders/telnyx/send", tags=["Admin"], dependencies=[Depends(require_admin)])
def send_reminder_telnyx(
    event_type: str = Query(..., description="Event type: traditional, white_wedding, or reception"),
    message: str = Query(..., description="Message to send"),
    target_group: str = Query(..., description="Target group: guests, plus-ones, or all")
):
    """Send SMS reminders using Telnyx"""
    if not telnyx_available:
        raise HTTPException(status_code=503, detail="Telnyx service not configured")
    
    return telnyx_reminder_service.send_reminders(event_type, message, target_group)

@router.post("/reminders/telnyx/send-invites", tags=["Admin"], dependencies=[Depends(require_admin)])
def send_invites_telnyx(payload: SlugModel):
    """Send RSVP invite links using Telnyx"""
    if not telnyx_available:
        raise HTTPException(status_code=503, detail="Telnyx service not configured")
    
    return telnyx_helper.send_personalized_rsvp_links(
        slug=payload.slug, 
        custom_message=payload.custom_message
    )

@router.get("/reminders/telnyx/logs", tags=["Admin"], dependencies=[Depends(require_admin)])
def get_telnyx_logs():
    """Get SMS logs for messages sent via Telnyx"""
    if not telnyx_available:
        raise HTTPException(status_code=503, detail="Telnyx service not configured")
    
    return telnyx_reminder_service.get_logs()