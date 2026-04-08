"""Meeting invite lifecycle models for couple-facing delivery."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class MeetingInviteDeliveryStatus(str, Enum):
    """Delivery state for a couple invite."""

    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MeetingInviteResponseStatus(str, Enum):
    """Response status from the invite recipient."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    TENTATIVE = "tentative"


class MeetingInviteModel(BaseModel):
    """Outbound couple invite tied to one canonical meeting."""

    id: str = Field(..., alias="_id")
    task_id: str
    wedding_id: str
    owner_planner_id: str
    owner_planner_email: str
    recipient_email: str
    recipient_name: Optional[str] = None
    delivery_mode: str
    delivery_status: str = Field(default=MeetingInviteDeliveryStatus.QUEUED.value)
    response_status: str = Field(default=MeetingInviteResponseStatus.PENDING.value)
    response_source: Optional[str] = None
    message_id: Optional[str] = None
    ics_uid: Optional[str] = None
    last_sent_at: Optional[datetime] = None
    response_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
