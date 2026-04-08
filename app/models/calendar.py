"""Calendar and task models for planner scheduling features."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, field_validator, model_validator


class TaskPriority(str, Enum):
    """Task priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TaskStatus(str, Enum):
    """Task status options."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskCategory(str, Enum):
    """Predefined task categories for wedding planning."""

    VENUE = "venue"
    CATERING = "catering"
    PHOTOGRAPHY = "photography"
    VIDEOGRAPHY = "videography"
    MUSIC = "music"
    FLOWERS = "flowers"
    ATTIRE = "attire"
    INVITATIONS = "invitations"
    TRANSPORTATION = "transportation"
    ACCOMMODATION = "accommodation"
    CEREMONY = "ceremony"
    RECEPTION = "reception"
    HONEYMOON = "honeymoon"
    LEGAL = "legal"
    BUDGET = "budget"
    GUEST_MANAGEMENT = "guest_management"
    MEETING = "meeting"
    OTHER = "other"


class ScheduleItemType(str, Enum):
    """Canonical schedule item types stored in planner_tasks."""

    TASK = "task"
    MEETING = "meeting"
    BLOCKED_TIME = "blocked_time"


class VisibilityMode(str, Enum):
    """Visibility mode for shared calendar rendering."""

    DETAILS = "details"
    BUSY_ONLY = "busy_only"


class CalendarSyncPolicy(str, Enum):
    """Rules that decide which external calendars receive an event."""

    OWNER_ONLY = "owner_only"
    ASSIGNED_ONLY = "assigned_only"
    OWNER_AND_ASSIGNED = "owner_and_assigned"
    CUSTOM = "custom"


class InviteDeliveryMode(str, Enum):
    """Supported invite delivery modes."""

    NONE = "none"
    EMAIL_ICS = "email_ics"
    GOOGLE_ATTENDEE = "google_attendee"
    PORTAL_ONLY = "portal_only"


class MeetingLifecycleStatus(str, Enum):
    """Lifecycle state for canonical meeting records."""

    SCHEDULED = "scheduled"
    RESCHEDULED = "rescheduled"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class CalendarTokenModel(BaseModel):
    """Legacy Google Calendar OAuth tokens keyed by planner email."""

    id: str = Field(..., alias="_id")
    user_email: str = Field(..., description="Planner's email address")
    access_token: str = Field(..., description="Google OAuth access token")
    refresh_token: str = Field(
        ..., description="Google OAuth refresh token for renewal"
    )
    token_expiry: datetime = Field(..., description="When the access token expires")
    calendar_id: Optional[str] = Field(
        None, description="Primary calendar ID to sync with (defaults to 'primary')"
    )
    sync_enabled: bool = Field(
        default=True, description="Whether calendar sync is active"
    )
    last_sync_at: Optional[datetime] = Field(
        None, description="Last successful sync timestamp"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


class PlannerTaskModel(BaseModel):
    """Canonical planner schedule item stored in planner_tasks."""

    id: str = Field(..., alias="_id")
    planner_email: str = Field(..., description="Legacy planner owner email")
    owner_planner_id: Optional[str] = Field(
        None, description="Canonical planner owner user id"
    )
    owner_planner_email: Optional[str] = Field(
        None, description="Canonical planner owner email"
    )
    created_by_user_id: Optional[str] = Field(
        None, description="Internal user id that created the item"
    )
    created_by_email: Optional[str] = Field(
        None, description="Internal email that created the item"
    )
    assigned_user_ids: list[str] = Field(default_factory=list)
    assigned_user_emails: list[str] = Field(default_factory=list)
    wedding_id: Optional[str] = Field(None, description="Associated wedding (optional)")
    title: str = Field(..., description="Task title")
    description: Optional[str] = Field(None, description="Detailed task description")
    category: str = Field(default=TaskCategory.OTHER.value, description="Task category")
    priority: str = Field(default=TaskPriority.MEDIUM.value, description="Priority")
    status: str = Field(default=TaskStatus.PENDING.value, description="Task status")
    schedule_item_type: str = Field(
        default=ScheduleItemType.TASK.value, description="Canonical schedule item type"
    )
    visibility_mode: str = Field(
        default=VisibilityMode.DETAILS.value,
        description="Shared-calendar detail visibility",
    )
    calendar_sync_policy: str = Field(
        default=CalendarSyncPolicy.OWNER_ONLY.value,
        description="How external sync targets are resolved",
    )

    # Scheduling fields
    start_date: datetime = Field(..., description="Task start date/time")
    end_date: Optional[datetime] = Field(
        None, description="Task end date/time (for events)"
    )
    all_day: bool = Field(default=False, description="Whether this is an all-day event")
    due_date: Optional[datetime] = Field(None, description="Due date for the task")
    timezone: str = Field(default="UTC", description="IANA timezone identifier")

    # Planner/couple participants
    couple_attendee_emails: list[str] = Field(default_factory=list)
    external_attendees: list[dict] = Field(default_factory=list)

    # Meeting metadata
    conference_provider: Optional[str] = Field(
        None, description="Conference provider label"
    )
    conference_url: Optional[str] = Field(None, description="Join URL")
    invite_delivery_mode: str = Field(
        default=InviteDeliveryMode.NONE.value, description="Invite delivery mode"
    )
    meeting_status: Optional[str] = Field(
        default=None, description="Lifecycle state for meetings"
    )

    # Reminders
    reminder_minutes: Optional[int] = Field(
        None,
        description="Minutes before to send reminder (e.g., 30, 60, 1440 for 1 day)",
    )

    # Legacy Google Calendar sync fields
    google_event_id: Optional[str] = Field(
        None, description="Legacy Google Calendar event ID if synced"
    )
    synced_to_google: bool = Field(
        default=False, description="Legacy flag for Google Calendar sync"
    )
    last_google_sync: Optional[datetime] = Field(
        None, description="Legacy timestamp for last Google sync"
    )

    # Recurrence (optional)
    is_recurring: bool = Field(default=False, description="Whether task repeats")
    recurrence_rule: Optional[str] = Field(
        None, description="iCal RRULE string (e.g., 'FREQ=WEEKLY;BYDAY=MO')"
    )

    # Metadata
    color: Optional[str] = Field(None, description="Display color (hex code)")
    notes: Optional[str] = Field(None, description="Additional notes")
    attachments: list[str] = Field(
        default_factory=list, description="File attachment URLs"
    )

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(
        None, description="When task was completed"
    )

    class Config:
        populate_by_name = True


class CalendarEventCreate(BaseModel):
    """Schema for creating a new calendar event/task."""

    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    wedding_id: Optional[str] = None
    category: str = Field(default=TaskCategory.OTHER.value)
    priority: str = Field(default=TaskPriority.MEDIUM.value)
    start_date: datetime
    end_date: Optional[datetime] = None
    all_day: bool = False
    due_date: Optional[datetime] = None
    reminder_minutes: Optional[int] = Field(None, ge=0, le=40320)  # Max 4 weeks
    is_recurring: bool = False
    recurrence_rule: Optional[str] = None
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    notes: Optional[str] = None
    schedule_item_type: str = Field(default=ScheduleItemType.TASK.value)
    timezone: str = Field(default="UTC")
    visibility_mode: str = Field(default=VisibilityMode.DETAILS.value)
    calendar_sync_policy: str = Field(default=CalendarSyncPolicy.OWNER_ONLY.value)
    assigned_user_ids: list[str] = Field(default_factory=list)
    assigned_user_emails: list[str] = Field(default_factory=list)
    couple_attendee_emails: list[str] = Field(default_factory=list)
    conference_provider: Optional[str] = None
    conference_url: Optional[str] = None
    invite_delivery_mode: str = Field(default=InviteDeliveryMode.NONE.value)
    meeting_status: Optional[str] = None
    sync_to_google: bool = Field(
        default=True, description="Legacy compatibility toggle for task sync"
    )
    sync_target_connection_ids: list[str] = Field(default_factory=list)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except Exception as exc:  # pragma: no cover - zoneinfo error type varies
            raise ValueError("Invalid timezone") from exc
        return value

    @field_validator("recurrence_rule")
    @classmethod
    def validate_recurrence_rule(cls, value: Optional[str]) -> Optional[str]:
        if value and "FREQ=" not in value:
            raise ValueError("recurrence_rule must include FREQ=")
        return value

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be greater than or equal to start_date")
        if self.is_recurring and not self.recurrence_rule:
            raise ValueError("recurrence_rule is required when is_recurring is true")
        if self.schedule_item_type == ScheduleItemType.MEETING.value:
            self.meeting_status = self.meeting_status or MeetingLifecycleStatus.SCHEDULED.value
        return self


class CalendarEventUpdate(BaseModel):
    """Schema for updating an existing calendar event/task."""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    wedding_id: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    all_day: Optional[bool] = None
    due_date: Optional[datetime] = None
    reminder_minutes: Optional[int] = Field(None, ge=0, le=40320)
    is_recurring: Optional[bool] = None
    recurrence_rule: Optional[str] = None
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    notes: Optional[str] = None
    schedule_item_type: Optional[str] = None
    timezone: Optional[str] = None
    visibility_mode: Optional[str] = None
    calendar_sync_policy: Optional[str] = None
    assigned_user_ids: Optional[list[str]] = None
    assigned_user_emails: Optional[list[str]] = None
    couple_attendee_emails: Optional[list[str]] = None
    conference_provider: Optional[str] = None
    conference_url: Optional[str] = None
    invite_delivery_mode: Optional[str] = None
    meeting_status: Optional[str] = None
    sync_target_connection_ids: Optional[list[str]] = None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        try:
            ZoneInfo(value)
        except Exception as exc:  # pragma: no cover - zoneinfo error type varies
            raise ValueError("Invalid timezone") from exc
        return value

    @field_validator("recurrence_rule")
    @classmethod
    def validate_recurrence_rule(cls, value: Optional[str]) -> Optional[str]:
        if value and "FREQ=" not in value:
            raise ValueError("recurrence_rule must include FREQ=")
        return value

    @model_validator(mode="after")
    def validate_dates(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be greater than or equal to start_date")
        return self


class CalendarSyncStatus(BaseModel):
    """Status of Google Calendar connection for a user."""

    connected: bool = Field(..., description="Whether Google Calendar is connected")
    calendar_id: Optional[str] = Field(None, description="Connected calendar ID")
    last_sync: Optional[datetime] = Field(None, description="Last sync timestamp")
    sync_enabled: bool = Field(
        default=False, description="Whether auto-sync is enabled"
    )
    events_synced: int = Field(default=0, description="Number of events synced")
