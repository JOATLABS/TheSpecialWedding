import logging

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies.auth_extended import (
    ExtendedAuthUser,
    check_wedding_access,
    enforce_team_permission,
    require_communication_capability,
)
from app.services.reminder_service import ReminderService
from app.services.wedding_service import WeddingService
from app.utils.communication_access import CommunicationCapability

router = APIRouter()
logger = logging.getLogger(__name__)
wedding_service = WeddingService()


def get_reminder_service() -> ReminderService:
    """Lazily construct the SMS reminder service for configured environments only."""
    try:
        return ReminderService()
    except RuntimeError as exc:
        logger.warning("Reminder service unavailable: %s", exc)
        raise HTTPException(
            status_code=503, detail="SMS reminders are not configured"
        ) from exc


@router.post("/reminders/send", tags=["Admin"])
async def send_reminder(
    wedding_slug: str,
    event_type: str,
    message: str,
    target_group: str,
    current_user: ExtendedAuthUser = Depends(
        require_communication_capability(CommunicationCapability.REMINDERS)
    ),
    reminder_service: ReminderService = Depends(get_reminder_service),
):
    enforce_team_permission(current_user, "send_reminders")
    wedding = await wedding_service.get_wedding_by_slug(wedding_slug)
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")
    if not await check_wedding_access(current_user, wedding["_id"]):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")
    return await reminder_service.send_reminders(
        event_type, message, target_group, str(wedding["_id"])
    )


@router.get("/reminders/logs", tags=["Admin"])
async def get_logs(
    current_user: ExtendedAuthUser = Depends(
        require_communication_capability(CommunicationCapability.HISTORY)
    ),
    reminder_service: ReminderService = Depends(get_reminder_service),
):
    return await reminder_service.get_logs()


# NOTE: `/admin/reminders/sms-callback` (GET + POST) used to live here as a
# deprecation shim that delegated Twilio webhooks to /webhook/twilio/incoming
# and handled Telnyx STOP/HELP/START messages inline. Removed 2026-04-27.
# - The GET was a 200-OK liveness probe; no caller was hitting it.
# - The POST's Telnyx path is dead — Telnyx is not in active use.
# - The POST's Twilio path was a redirect to /webhook/twilio/incoming, and
#   Twilio is configured to hit that endpoint directly now.
# If a Telnyx integration is ever revived, restore from git history at
# 2026-04-27 and re-evaluate whether the path belongs in this module or in
# a dedicated Telnyx webhook router.
