# app/api/reminder_utilities.py

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from app.services.reminder_utilities import RSVPReminderHelper
from app.dependencies.auth import require_admin

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

@router.post("/admin/reminders/send-personalized-links", tags=["Admin"], dependencies=[Depends(require_admin)])
def send_invite_links(payload: SlugModel):
    return reminder_helper.send_personalized_rsvp_links(slug=payload.slug)

@router.post("/admin/reminders/simulate-rsvp", tags=["Admin"], dependencies=[Depends(require_admin)])
def simulate_rsvp(payload: RSVPRequestModel):
    return reminder_helper.simulate_rsvp_for_guest(
        token=payload.token,
        attending=payload.attending,
        dietary=payload.dietary,
        phone=payload.phone,
        plus_one=payload.plus_one
    )
