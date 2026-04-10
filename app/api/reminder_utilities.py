# app/api/reminder_utilities.py

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.dependencies.auth_extended import (
    ExtendedAuthUser,
    check_wedding_access,
    enforce_team_permission,
    require_admin_or_planner,
)
from app.services.reminder_utilities import RSVPReminderHelper
from app.services.sse_manager import sse_manager
from app.services.wedding_service import WeddingService

router = APIRouter()

reminder_helper = RSVPReminderHelper()
wedding_service = WeddingService()


class RSVPRequestModel(BaseModel):
    token: str
    attending: List[str] = Field(default_factory=lambda: ["traditional"])
    dietary: Optional[str] = None
    phone: Optional[str] = None
    plus_one: Optional[dict] = None


class SlugModel(BaseModel):
    slug: str
    custom_message: Optional[str] = None


@router.post("/reminders/send-personalized-links", tags=["Admin"])
async def send_invite_links(
    payload: SlugModel,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    enforce_team_permission(current_user, "send_rsvp")
    wedding = await wedding_service.get_wedding_by_slug(payload.slug)
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")
    if not await check_wedding_access(current_user, wedding["_id"]):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    result = await reminder_helper.send_personalized_rsvp_links(
        slug=payload.slug, custom_message=payload.custom_message or ""
    )

    # Broadcast invite status change so planner UI refreshes
    await sse_manager.broadcast_data_change(
        current_user.email,
        "invite",
        "created",
        wedding_id=str(wedding["_id"]),
    )

    return result


@router.post(
    "/reminders/simulate-rsvp",
    tags=["Admin"],
    dependencies=[Depends(require_admin_or_planner)],
)
async def simulate_rsvp(payload: RSVPRequestModel):
    return await reminder_helper.simulate_rsvp_for_guest(
        token=payload.token,
        attending=payload.attending,
        dietary=payload.dietary,
        phone=payload.phone,
        plus_one=payload.plus_one,
    )
