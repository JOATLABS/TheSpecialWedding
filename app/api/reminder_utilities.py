# app/api/reminder_utilities.py

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from app.services.reminder_utilities import RSVPReminderHelper
from app.dependencies.auth_extended import require_admin_or_planner

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

@router.post("/reminders/send-personalized-links", tags=["Admin"], dependencies=[Depends(require_admin_or_planner)])
async def send_invite_links(payload: SlugModel):
    return await reminder_helper.send_personalized_rsvp_links(slug=payload.slug, custom_message=payload.custom_message)

@router.post("/reminders/simulate-rsvp", tags=["Admin"], dependencies=[Depends(require_admin_or_planner)])
async def simulate_rsvp(payload: RSVPRequestModel):
    return await reminder_helper.simulate_rsvp_for_guest(
        token=payload.token,
        attending=payload.attending,
        dietary=payload.dietary,
        phone=payload.phone,
        plus_one=payload.plus_one
    )
