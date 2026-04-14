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


class CalendarSchedulerRole(str, Enum):
    """Workspace roles that can be allowed to schedule onto a connection."""

    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


class CalendarSchedulerAccessMode(str, Enum):
    """Base actor-eligibility policy for scheduling onto a connection."""

    WORKSPACE_DEFAULT = "workspace_default"
    OWNER_ONLY = "owner_only"
    OWNER_AND_CONNECTION_USER = "owner_and_connection_user"
    WORKSPACE_PERMITTED = "workspace_permitted"


class CalendarSyncTargetingMode(str, Enum):
    """Whether a connection can be auto-targeted or only used by explicit override."""

    AUTOMATIC_AND_MANUAL = "automatic_and_manual"
    MANUAL_ONLY = "manual_only"


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
    scheduler_access_mode: str = Field(
        default=CalendarSchedulerAccessMode.WORKSPACE_DEFAULT.value
    )
    sync_targeting_mode: str = Field(
        default=CalendarSyncTargetingMode.AUTOMATIC_AND_MANUAL.value
    )
    allowed_scheduler_user_ids: list[str] = Field(default_factory=list)
    allowed_scheduler_roles: list[str] = Field(default_factory=list)
    allowed_schedule_item_types: list[str] = Field(default_factory=list)
    allowed_wedding_ids: list[str] = Field(default_factory=list)
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
    scheduler_access_mode: Optional[str] = None
    sync_targeting_mode: Optional[str] = None
    allowed_scheduler_user_ids: Optional[list[str]] = None
    allowed_scheduler_roles: Optional[list[str]] = None
    allowed_schedule_item_types: Optional[list[str]] = None
    allowed_wedding_ids: Optional[list[str]] = None
    is_shared_in_team_view: Optional[bool] = None
    details_visibility: Optional[str] = None
    sync_enabled: Optional[bool] = None
