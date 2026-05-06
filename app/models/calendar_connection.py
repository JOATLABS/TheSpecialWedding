"""Calendar connection models for external provider integrations via Aurinko."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.models.calendar import VisibilityMode


class CalendarProvider(str, Enum):
    """Underlying calendar providers exposed through the Aurinko aggregator.

    Stored on each connection for UI badges, audit logs, and support — never
    used for routing. Aurinko owns the per-provider OAuth flow and unified API.
    """

    GOOGLE = "google"
    OFFICE365 = "office365"
    OUTLOOK = "outlook"
    EXCHANGE = "exchange"
    ICLOUD = "icloud"
    ZOHO = "zoho"
    UNKNOWN = "unknown"


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
    """A single connected external calendar row.

    One row per calendar (an Aurinko account exposing N calendars yields N
    rows). Database uniqueness is the compound index
    ``(owner_planner_id, user_id, aurinko_account_id, aurinko_calendar_id)``.
    """

    id: str = Field(..., alias="_id")
    owner_planner_id: str
    owner_planner_email: str
    user_id: str
    user_email: str
    # Underlying provider returned by Aurinko — informational only.
    provider: str = Field(default=CalendarProvider.UNKNOWN.value)
    provider_account_email: str
    provider_account_name: Optional[str] = None
    # Aurinko-side identifiers. Aurinko owns the per-provider OAuth tokens
    # (Google/Microsoft/etc.) — we never store those. Aurinko issues us a
    # per-account bearer token during OAuth callback that we use for
    # subsequent API calls; that token is stored encrypted.
    aurinko_account_id: str
    aurinko_calendar_id: str
    aurinko_access_token_encrypted: Optional[str] = None
    # Aurinko-side webhook subscription id, populated when we register a
    # /calendars/events subscription so we can unsubscribe on disconnect.
    aurinko_subscription_id: Optional[str] = None
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
    couple_booking_auto_confirm: bool = True
    connection_status: str = Field(default=CalendarConnectionStatus.ACTIVE.value)
    last_sync_at: Optional[datetime] = None
    last_healthcheck_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

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
    couple_booking_auto_confirm: Optional[bool] = None
