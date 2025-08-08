# app/api/email_reminders.py

from fastapi import APIRouter, HTTPException, Depends, Query, Form, UploadFile, File
from app.services.email_service_resend import ResendEmailService
from app.dependencies.auth import require_admin
from pydantic import BaseModel
from typing import Optional, List
import base64

router = APIRouter()

# Initialize email service
try:
    email_service = ResendEmailService()
    email_available = email_service.configured
except Exception as e:
    print(f"Email service not available: {str(e)}")
    email_available = False
    email_service = None

class EmailInviteModel(BaseModel):
    wedding_slug: str
    custom_subject: Optional[str] = None
    custom_html: Optional[str] = None

class EmailReminderModel(BaseModel):
    wedding_slug: str
    event_type: str
    custom_subject: Optional[str] = None
    custom_html: Optional[str] = None
    target_group: str = "all"  # guests, plus-ones, or all

@router.get("/email/status", tags=["Admin"])
def get_email_status():
    """Check if email service is configured and available"""
    return {
        "available": email_available,
        "provider": "resend",
        "message": "Email service configured and ready" if email_available else "Email service not configured (RESEND_API_KEY missing)"
    }

@router.post("/email/send-invites", tags=["Admin"], dependencies=[Depends(require_admin)])
async def send_email_invites(payload: EmailInviteModel):
    """Send RSVP invitation emails (JSON endpoint)"""
    if not email_available:
        raise HTTPException(status_code=503, detail="Email service not configured")
    
    result = email_service.send_rsvp_invitations(
        wedding_slug=payload.wedding_slug,
        custom_html=payload.custom_html,
        custom_subject=payload.custom_subject,
        attachments=[]
    )
    
    return result

@router.post("/email/send-invites-with-attachment", tags=["Admin"], dependencies=[Depends(require_admin)])
async def send_email_invites_with_attachment(
    wedding_slug: str = Form(...),
    custom_subject: Optional[str] = Form(None),
    custom_html: Optional[str] = Form(None),
    attachment: UploadFile = File(...)
):
    """Send RSVP invitation emails with attachment (multipart/form-data endpoint)"""
    if not email_available:
        raise HTTPException(status_code=503, detail="Email service not configured")
    
    # Handle attachment
    attachments = []
    try:
        content = await attachment.read()
        attachments.append({
            "filename": attachment.filename,
            "content": base64.b64encode(content).decode('utf-8')
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process attachment: {str(e)}")
    
    result = email_service.send_rsvp_invitations(
        wedding_slug=wedding_slug,
        custom_html=custom_html,
        custom_subject=custom_subject,
        attachments=attachments
    )
    
    return result

@router.post("/email/send-reminders", tags=["Admin"], dependencies=[Depends(require_admin)])
def send_email_reminders(payload: EmailReminderModel):
    """Send event reminder emails"""
    if not email_available:
        raise HTTPException(status_code=503, detail="Email service not configured")
    
    result = email_service.send_reminders(
        wedding_slug=payload.wedding_slug,
        event_type=payload.event_type,
        custom_html=payload.custom_html,
        custom_subject=payload.custom_subject,
        target_group=payload.target_group
    )
    
    return result

@router.get("/email/logs", tags=["Admin"], dependencies=[Depends(require_admin)])
def get_email_logs(
    wedding_id: Optional[str] = Query(None, description="Filter by wedding ID"),
    limit: int = Query(100, description="Number of logs to return")
):
    """Get email send logs"""
    if not email_available:
        raise HTTPException(status_code=503, detail="Email service not configured")
    
    logs = email_service.get_email_logs(wedding_id=wedding_id, limit=limit)
    return {"logs": logs, "count": len(logs)}

@router.get("/email/preview-invitation", tags=["Admin"], dependencies=[Depends(require_admin)])
def preview_invitation_email(
    guest_name: str = Query("John Doe", description="Guest name for preview"),
    couple_names: str = Query("Jane & John", description="Couple names"),
    wedding_date: str = Query("2024-12-25", description="Wedding date")
):
    """Preview the default invitation email template"""
    if not email_available:
        raise HTTPException(status_code=503, detail="Email service not configured")
    
    html = email_service._generate_default_invitation_html(
        guest_name=guest_name,
        couple_names=couple_names,
        wedding_date=wedding_date,
        rsvp_url="https://thespecialwedding.com/wedding/invite/preview-token"
    )
    
    return {"html": html}

@router.get("/email/preview-reminder", tags=["Admin"], dependencies=[Depends(require_admin)])
def preview_reminder_email(
    guest_name: str = Query("John Doe", description="Guest name for preview"),
    event_type: str = Query("white_wedding", description="Event type"),
    event_date: str = Query("2024-12-25", description="Event date"),
    venue_name: str = Query("Grand Ballroom", description="Venue name"),
    location: str = Query("123 Main St, City", description="Location"),
    time: str = Query("3:00 PM", description="Event time"),
    couple_names: str = Query("Jane & John", description="Couple names")
):
    """Preview the default reminder email template"""
    if not email_available:
        raise HTTPException(status_code=503, detail="Email service not configured")
    
    event_details = {
        "venue_name": venue_name,
        "location": location,
        "time": time
    }
    
    html = email_service._generate_default_reminder_html(
        guest_name=guest_name,
        event_type=event_type,
        event_date=event_date,
        event_details=event_details,
        couple_names=couple_names
    )
    
    return {"html": html}