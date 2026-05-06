"""Calendar and task models for planner scheduling features."""

from __future__ import annotations

from datetime import datetime, timezone
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

    PENDING_APPROVAL = "pending_approval"
    SCHEDULED = "scheduled"
    RESCHEDULED = "rescheduled"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


def attach_timezone_if_naive(
    value: Optional[datetime],
    timezone_name: str,
) -> Optional[datetime]:
    """Attach the requested IANA timezone when an incoming datetime is naive."""
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=ZoneInfo(timezone_name))


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
    sync_target_override_enabled: bool = Field(
        default=False,
        description="Whether explicit connection targets should override default sync resolution",
    )
    sync_target_connection_ids: list[str] = Field(default_factory=list)
    external_sync_requested: bool = Field(
        default=False,
        description="Canonical request to project this internal item onto external calendars",
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

    # Snapshot of last seen external state — written by calendar_webhook_service
    # when an external change is detected. Canonical fields (start_date,
    # end_date, title, description, etc.) are NOT silently overwritten; the
    # planner UI reads external_conflict_status to render a "modified
    # externally" badge until accepted or rejected.
    external_start_date: Optional[datetime] = None
    external_end_date: Optional[datetime] = None
    external_title: Optional[str] = None
    external_description: Optional[str] = None
    external_location: Optional[str] = None
    external_last_modified_at: Optional[datetime] = None
    external_conflict_status: str = Field(default="none")
    external_conflict_source: Optional[str] = None
    external_conflict_detected_at: Optional[datetime] = None

    # True when the row was created by a couple's self-service booking from
    # the couples portal, false (default) for planner-initiated items.
    created_by_couple: bool = Field(default=False)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = Field(default=1, ge=1)
    completed_at: Optional[datetime] = Field(
        None, description="When task was completed"
    )

    class Config:
        populate_by_name = True


class ExternalConflictStatus(str, Enum):
    """Status of an externally detected change against canonical task state."""

    NONE = "none"
    PENDING_REVIEW = "pending_review"
    AUTO_ACCEPTED = "auto_accepted"


class ExternalConflictSource(str, Enum):
    """Where an external change was learned from."""

    WEBHOOK = "webhook"
    POLL = "poll"


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
    sync_target_override_enabled: bool = False
    sync_target_connection_ids: list[str] = Field(default_factory=list)
    external_sync_requested: Optional[bool] = Field(
        default=None,
        description="Explicit request to project this task onto external calendars",
    )

    @model_validator(mode="before")
    @classmethod
    def reject_legacy_sync_to_google(cls, data: object) -> object:
        if isinstance(data, dict) and "sync_to_google" in data:
            raise ValueError(
                "sync_to_google is no longer supported; use external_sync_requested"
            )
        return data

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
        start_date = attach_timezone_if_naive(self.start_date, self.timezone)
        if start_date is None:
            raise ValueError("start_date is required")
        self.start_date = start_date
        self.end_date = attach_timezone_if_naive(self.end_date, self.timezone)
        self.due_date = attach_timezone_if_naive(self.due_date, self.timezone)
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be greater than or equal to start_date")
        if self.is_recurring and not self.recurrence_rule:
            raise ValueError("recurrence_rule is required when is_recurring is true")
        if self.invite_delivery_mode == InviteDeliveryMode.GOOGLE_ATTENDEE.value:
            raise ValueError(
                "invite_delivery_mode='google_attendee' is not available in v1"
            )
        if self.schedule_item_type == ScheduleItemType.MEETING.value:
            self.meeting_status = (
                self.meeting_status or MeetingLifecycleStatus.SCHEDULED.value
            )
        if not self.sync_target_override_enabled:
            self.sync_target_connection_ids = []
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
    sync_target_override_enabled: Optional[bool] = None
    sync_target_connection_ids: Optional[list[str]] = None
    external_sync_requested: Optional[bool] = Field(
        default=None,
        description="Canonical request to project this task onto external calendars",
    )
    expected_version: Optional[int] = Field(None, ge=1)

    @model_validator(mode="before")
    @classmethod
    def reject_legacy_sync_to_google(cls, data: object) -> object:
        if isinstance(data, dict) and "sync_to_google" in data:
            raise ValueError(
                "sync_to_google is no longer supported; use external_sync_requested"
            )
        return data

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
        timezone_name = self.timezone or "UTC"
        self.start_date = attach_timezone_if_naive(self.start_date, timezone_name)
        self.end_date = attach_timezone_if_naive(self.end_date, timezone_name)
        self.due_date = attach_timezone_if_naive(self.due_date, timezone_name)
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be greater than or equal to start_date")
        if self.invite_delivery_mode == InviteDeliveryMode.GOOGLE_ATTENDEE.value:
            raise ValueError(
                "invite_delivery_mode='google_attendee' is not available in v1"
            )
        if self.sync_target_override_enabled is False:
            self.sync_target_connection_ids = []
        return self


class CalendarSyncStatus(BaseModel):
    """Status of the user's external calendar connection (via Aurinko)."""

    connected: bool = Field(
        ..., description="Whether an external calendar is connected"
    )
    calendar_id: Optional[str] = Field(None, description="Connected calendar ID")
    last_sync: Optional[datetime] = Field(None, description="Last sync timestamp")
    sync_enabled: bool = Field(
        default=False, description="Whether auto-sync is enabled"
    )
    events_synced: int = Field(default=0, description="Number of events synced")
