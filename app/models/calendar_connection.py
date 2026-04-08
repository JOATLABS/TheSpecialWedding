"""Calendar connection models for external provider integrations."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.models.calendar import VisibilityMode


class CalendarProvider(str, Enum):
    """Supported external calendar providers."""

    GOOGLE = "google"


class CalendarConnectionStatus(str, Enum):
    """Lifecycle state for a connected external calendar."""

    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    ERROR = "error"


class CalendarConnectionModel(BaseModel):
    """A single connected external calendar row."""

    id: str = Field(..., alias="_id")
    owner_planner_id: str
    owner_planner_email: str
    user_id: str
    user_email: str
    provider: str = Field(default=CalendarProvider.GOOGLE.value)
    provider_account_email: str
    provider_account_name: Optional[str] = None
    calendar_id: str
    calendar_name: str
    access_role: Optional[str] = None
    is_writable: bool = False
    is_primary: bool = False
    is_default_write_target: bool = False
    is_shared_in_team_view: bool = False
    details_visibility: str = Field(default=VisibilityMode.BUSY_ONLY.value)
    sync_enabled: bool = True
    connection_status: str = Field(default=CalendarConnectionStatus.ACTIVE.value)
    access_token_encrypted: str
    refresh_token_encrypted: Optional[str] = None
    token_expiry: Optional[datetime] = None
    scope_version: Optional[str] = None
    last_sync_at: Optional[datetime] = None
    last_healthcheck_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


class CalendarConnectionUpdateRequest(BaseModel):
    """Allowed mutable fields for a calendar connection."""

    is_default_write_target: Optional[bool] = None
    is_shared_in_team_view: Optional[bool] = None
    details_visibility: Optional[str] = None
    sync_enabled: Optional[bool] = None
