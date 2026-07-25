"""Per-target sync records for external calendar projections."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

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
    target_user_id: str | None = None
    target_user_email: str | None = None
    calendar_connection_id: str | None = None
    # Default to UNKNOWN, not GOOGLE — Aurinko fans out to four+ providers and
    # a sync row may be written before the provider id is known. The drift-
    # check job backfills the real provider id from the owning connection.
    provider: str = Field(default=CalendarProvider.UNKNOWN.value)
    calendar_id: str | None = None
    external_event_id: str | None = None
    sync_direction: str = Field(default=CalendarSyncDirection.OUTBOUND.value)
    sync_status: str = Field(default=CalendarSyncStatusValue.PENDING.value)
    last_sync_at: datetime | None = None
    last_error: str | None = None
    last_error_category: str | None = None
    retryable_error: bool = False
    retry_count: int = 0
    next_retry_at: datetime | None = None
    last_retry_at: datetime | None = None
    last_drift_check_at: datetime | None = None
    etag: str | None = None
    external_updated_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Config:
        populate_by_name = True
