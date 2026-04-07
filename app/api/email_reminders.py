# app/api/email_reminders.py

from fastapi import APIRouter, HTTPException, Depends, Query, Form, UploadFile, File
from app.services.email_service_resend import ResendEmailService
from app.dependencies.auth_extended import (
    require_wedding_planner_only,
    ExtendedAuthUser,
    check_wedding_access,
    require_admin_or_planner,
    enforce_team_permission,
)
from app.services.wedding_service import WeddingService
from app.core.config import settings
from app.utils.response import dict_response
from pydantic import BaseModel
from typing import Optional
from app.services.sse_manager import sse_manager
import base64
import logging

logger = logging.getLogger(__name__)

router = APIRouter()
wedding_service = WeddingService()

# Initialize email service
email_service: Optional[ResendEmailService] = None
try:
    email_service = ResendEmailService()
    email_available = email_service.configured
except Exception as e:
    logger.error(f"Email service not available: {e}")
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
    return dict_response(
        data={
            "available": email_available,
            "provider": "resend",
        },
        message="Email service configured and ready"
        if email_available
        else "Email service not configured (RESEND_API_KEY missing)",
    )


@router.post("/email/send-invites", tags=["Admin"])
async def send_email_invites(
    payload: EmailInviteModel,
    current_user: ExtendedAuthUser = Depends(require_wedding_planner_only),
):
    """Send RSVP invitation emails (JSON endpoint)"""
    enforce_team_permission(current_user, "send_rsvp")
    if not email_available or email_service is None:
        raise HTTPException(status_code=503, detail="Email service not configured")

    # Get wedding and verify access
    wedding = await wedding_service.get_wedding_by_slug(payload.wedding_slug)
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")

    if not await check_wedding_access(current_user, wedding["_id"]):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    result = await email_service.send_rsvp_invitations(
        wedding_slug=payload.wedding_slug,
        custom_html=payload.custom_html,
        custom_subject=payload.custom_subject,
        attachments=[],
    )

    # Broadcast invite status change so planner UI refreshes guest list
    await sse_manager.broadcast_data_change(
        current_user.email,
        "invite",
        "created",
        wedding_id=wedding["_id"],
    )

    return result


@router.post("/email/send-invites-with-attachment", tags=["Admin"])
async def send_email_invites_with_attachment(
    wedding_slug: str = Form(...),
    custom_subject: Optional[str] = Form(None),
    custom_html: Optional[str] = Form(None),
    attachment: UploadFile = File(...),
    current_user: ExtendedAuthUser = Depends(require_wedding_planner_only),
):
    """Send RSVP invitation emails with attachment (multipart/form-data endpoint)"""
    enforce_team_permission(current_user, "send_rsvp")
    if not email_available or email_service is None:
        raise HTTPException(status_code=503, detail="Email service not configured")

    # Get wedding and verify access
    wedding = await wedding_service.get_wedding_by_slug(wedding_slug)
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")

    if not await check_wedding_access(current_user, wedding["_id"]):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    # Handle attachment
    attachments = []
    try:
        content = await attachment.read()
        attachments.append(
            {
                "filename": attachment.filename,
                "content": base64.b64encode(content).decode("utf-8"),
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Failed to process attachment: {str(e)}"
        )

    result = await email_service.send_rsvp_invitations(
        wedding_slug=wedding_slug,
        custom_html=custom_html,
        custom_subject=custom_subject,
        attachments=attachments,
    )

    # Broadcast invite status change so planner UI refreshes guest list
    await sse_manager.broadcast_data_change(
        current_user.email,
        "invite",
        "created",
        wedding_id=wedding["_id"],
    )

    return result


@router.post("/email/send-reminders", tags=["Admin"])
async def send_email_reminders(
    payload: EmailReminderModel,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """Send event reminder emails"""
    enforce_team_permission(current_user, "send_reminders")
    if not email_available or email_service is None:
        raise HTTPException(status_code=503, detail="Email service not configured")

    # Get wedding and verify access
    wedding = await wedding_service.get_wedding_by_slug(payload.wedding_slug)
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")

    if not await check_wedding_access(current_user, wedding["_id"]):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    result = await email_service.send_reminders(
        wedding_slug=payload.wedding_slug,
        event_type=payload.event_type,
        custom_html=payload.custom_html,
        custom_subject=payload.custom_subject,
        target_group=payload.target_group,
    )

    return result


class IndividualEmailReminderModel(BaseModel):
    wedding_slug: str
    guest_email: str
    guest_name: str
    guest_token: str
    custom_message: Optional[str] = None
    custom_subject: Optional[str] = None


@router.post("/email/send-reminder-individual", tags=["Admin"])
async def send_individual_email_reminder(
    payload: IndividualEmailReminderModel,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """Send an email reminder to a specific guest (used for guests without phone numbers)."""
    enforce_team_permission(current_user, "send_reminders")
    if not email_available or email_service is None:
        raise HTTPException(status_code=503, detail="Email service not configured")

    # Get wedding and verify access
    from app.core.database import mongo

    wedding = await mongo.db["weddings"].find_one({"slug": payload.wedding_slug})
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")

    if not await check_wedding_access(current_user, wedding["_id"]):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    try:
        frontend_url = settings.get_required_url("FRONTEND_URL")
        couple_names = wedding.get("couple_names", "the couple")
        rsvp_url = f"{frontend_url}/{payload.wedding_slug}/invite/{payload.guest_token}"

        subject = payload.custom_subject or f"Reminder: {couple_names}'s Wedding"

        # Build HTML email with the custom message
        html_content = f"""
        <div style="font-family: Georgia, 'Times New Roman', serif; max-width: 600px; margin: 0 auto; padding: 40px 20px;">
            <div style="text-align: center; margin-bottom: 30px;">
                <h1 style="color: #2c3e50; font-size: 24px; margin: 0;">Wedding Reminder</h1>
                <p style="color: #7f8c8d; font-size: 14px;">{couple_names}</p>
            </div>

            <div style="background-color: #faf9f7; padding: 30px; border-radius: 8px; margin: 20px 0;">
                <p style="color: #2c3e50; font-size: 16px; line-height: 1.6;">
                    Dear {payload.guest_name},
                </p>
                <p style="color: #2c3e50; font-size: 16px; line-height: 1.6;">
                    {payload.custom_message or f"This is a friendly reminder about {couple_names}'s upcoming wedding. We would love for you to join us!"}
                </p>
            </div>

            <div style="text-align: center; margin: 30px 0;">
                <a href="{rsvp_url}"
                   style="background-color: #D4A5A5; color: white; padding: 14px 32px; text-decoration: none; border-radius: 6px; font-size: 16px; display: inline-block;">
                    RSVP Now
                </a>
            </div>

            <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

            <p style="color: #999; font-size: 12px; text-align: center;">
                This reminder was sent on behalf of {couple_names}.<br>
                Powered by The Special Wedding
            </p>
        </div>
        """

        result = await email_service.send_email(
            to_email=payload.guest_email,
            subject=subject,
            html_content=html_content,
            wedding_id=str(wedding["_id"]),
            email_type="individual_reminder",
        )

        if result.get("success"):
            # Mark guest as having received an invite if not already set
            guest_collection = mongo.get_guest_collection()
            guest = await guest_collection.find_one(
                {"token": payload.guest_token, "wedding_id": wedding["_id"]}
            )
            if guest and not guest.get("invite_sent"):
                from datetime import datetime, timezone

                await guest_collection.update_one(
                    {"_id": guest["_id"]},
                    {
                        "$set": {
                            "invite_sent": True,
                            "invite_sent_date": datetime.now(timezone.utc),
                        }
                    },
                )
                logger.info(
                    f"Set invite_sent=True for guest {payload.guest_name} (email reminder)"
                )

            # Broadcast invite status change
            await sse_manager.broadcast_data_change(
                current_user.email,
                "invite",
                "created",
                wedding_id=str(wedding["_id"]),
            )
            return {"sent": 1, "success": True}
        else:
            return {
                "sent": 0,
                "success": False,
                "error": result.get("error", "Unknown error"),
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")


@router.get("/email/logs", tags=["Admin"])
async def get_email_logs(
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
    wedding_id: Optional[str] = Query(None, description="Filter by wedding ID"),
    limit: int = Query(100, description="Number of logs to return"),
):
    """Get email send logs - filtered by wedding for planners"""
    if not email_available or email_service is None:
        raise HTTPException(status_code=503, detail="Email service not configured")

    # Root admin can see all logs or filter by specific wedding
    if current_user.is_root_admin:
        logs = await email_service.get_email_logs(wedding_id=wedding_id, limit=limit)
        return {"logs": logs, "count": len(logs)}

    # Wedding planners can only see logs for their assigned weddings
    if current_user.is_wedding_planner:
        from app.core.database import mongo

        # Get weddings assigned to this planner (safety cap: typical planner has <1k weddings)
        MAX_PLANNER_WEDDINGS = 1000
        weddings_cursor = mongo.db["weddings"].find(
            {"assigned_planner_email": current_user.email}, {"_id": 1}
        )
        weddings = await weddings_cursor.to_list(length=MAX_PLANNER_WEDDINGS)
        wedding_ids = [w["_id"] for w in weddings]

        if not wedding_ids:
            return {"logs": [], "count": 0}

        # Filter by wedding_id if provided, but ensure it's one of planner's weddings
        if wedding_id:
            if wedding_id not in wedding_ids:
                return {"logs": [], "count": 0}
            logs = await email_service.get_email_logs(
                wedding_id=wedding_id, limit=limit
            )
        else:
            # Get logs for all planner's weddings
            logs = await email_service.get_email_logs_for_weddings(
                wedding_ids=wedding_ids, limit=limit
            )

        return {"logs": logs, "count": len(logs)}

    return {"logs": [], "count": 0}


@router.get("/email/preview-invitation", tags=["Admin"])
def preview_invitation_email(
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
    guest_name: str = Query("John Doe", description="Guest name for preview"),
    couple_names: str = Query("Jane & John", description="Couple names"),
    wedding_date: str = Query("2024-12-25", description="Wedding date"),
):
    """Preview the default invitation email template"""
    if not email_available or email_service is None:
        raise HTTPException(status_code=503, detail="Email service not configured")

    frontend_url = settings.get_required_url("FRONTEND_URL")
    html = email_service._generate_default_invitation_html(
        guest_name=guest_name,
        couple_names=couple_names,
        wedding_date=wedding_date,
        rsvp_url=f"{frontend_url}/wedding/invite/preview-token" if frontend_url else "",
    )

    return {"html": html}


@router.get("/email/preview-reminder", tags=["Admin"])
def preview_reminder_email(
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
    guest_name: str = Query("John Doe", description="Guest name for preview"),
    event_type: str = Query("white_wedding", description="Event type"),
    event_date: str = Query("2024-12-25", description="Event date"),
    venue_name: str = Query("Grand Ballroom", description="Venue name"),
    location: str = Query("123 Main St, City", description="Location"),
    time: str = Query("3:00 PM", description="Event time"),
    couple_names: str = Query("Jane & John", description="Couple names"),
):
    """Preview the default reminder email template"""
    if not email_available or email_service is None:
        raise HTTPException(status_code=503, detail="Email service not configured")

    event_details = {"venue_name": venue_name, "location": location, "time": time}

    html = email_service._generate_default_reminder_html(
        guest_name=guest_name,
        event_type=event_type,
        event_date=event_date,
        event_details=event_details,
        couple_names=couple_names,
    )

    return {"html": html}
