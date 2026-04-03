# app/api/reminder_utilities.py

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from app.services.reminder_utilities import RSVPReminderHelper
from app.services.sse_manager import sse_manager
from app.dependencies.auth_extended import require_admin_or_planner, ExtendedAuthUser

router = APIRouter()

reminder_helper = RSVPReminderHelper()

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
async def send_invite_links(payload: SlugModel, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    result = await reminder_helper.send_personalized_rsvp_links(slug=payload.slug, custom_message=payload.custom_message)

    # Broadcast invite status change so planner UI refreshes
    from app.core.database import mongo
    wedding = await mongo.db["weddings"].find_one({"slug": payload.slug}, {"_id": 1})
    if wedding:
        await sse_manager.broadcast_data_change(
            current_user.email, "invite", "created",
            wedding_id=str(wedding["_id"]),
        )

    return result

@router.post("/reminders/simulate-rsvp", tags=["Admin"], dependencies=[Depends(require_admin_or_planner)])
async def simulate_rsvp(payload: RSVPRequestModel):
    return await reminder_helper.simulate_rsvp_for_guest(
        token=payload.token,
        attending=payload.attending,
        dietary=payload.dietary,
        phone=payload.phone,
        plus_one=payload.plus_one
    )
