"""Per-target sync records for external calendar projections."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.models.calendar_connection import CalendarProvider


class CalendarSyncDirection(str, Enum):
    """Supported sync directions."""

    OUTBOUND = "outbound"
    INBOUND = "inbound"
    BIDIRECTIONAL = "bidirectional"


class CalendarSyncStatusValue(str, Enum):
    """State of a per-target sync mapping."""

    PENDING = "pending"
    SYNCED = "synced"
    FAILED = "failed"
    ORPHANED = "orphaned"
    NOT_CONFIGURED = "not_configured"


class CalendarEventSyncModel(BaseModel):
    """One internal schedule item mapped to one external calendar event."""

    id: str = Field(..., alias="_id")
    task_id: str
    owner_planner_id: str
    owner_planner_email: str
    target_user_id: Optional[str] = None
    target_user_email: Optional[str] = None
    calendar_connection_id: Optional[str] = None
    provider: str = Field(default=CalendarProvider.GOOGLE.value)
    calendar_id: Optional[str] = None
    external_event_id: Optional[str] = None
    sync_direction: str = Field(default=CalendarSyncDirection.OUTBOUND.value)
    sync_status: str = Field(default=CalendarSyncStatusValue.PENDING.value)
    last_sync_at: Optional[datetime] = None
    last_error: Optional[str] = None
    etag: Optional[str] = None
    external_updated_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
