"""Calendar and task models for planner scheduling features."""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum


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


class CalendarTokenModel(BaseModel):
    """Stored Google Calendar OAuth tokens for a planner."""

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
    """Tasks created by planners for wedding planning."""

    id: str = Field(..., alias="_id")
    planner_email: str = Field(..., description="Planner who owns this task")
    wedding_id: Optional[str] = Field(None, description="Associated wedding (optional)")
    title: str = Field(..., description="Task title")
    description: Optional[str] = Field(None, description="Detailed task description")
    category: str = Field(default="other", description="Task category")
    priority: str = Field(default="medium", description="Priority level")
    status: str = Field(default="pending", description="Current status")

    # Scheduling fields
    start_date: datetime = Field(..., description="Task start date/time")
    end_date: Optional[datetime] = Field(
        None, description="Task end date/time (for events)"
    )
    all_day: bool = Field(default=False, description="Whether this is an all-day event")
    due_date: Optional[datetime] = Field(None, description="Due date for the task")

    # Reminders
    reminder_minutes: Optional[int] = Field(
        None,
        description="Minutes before to send reminder (e.g., 30, 60, 1440 for 1 day)",
    )

    # Google Calendar sync
    google_event_id: Optional[str] = Field(
        None, description="Google Calendar event ID if synced"
    )
    synced_to_google: bool = Field(
        default=False, description="Whether synced to Google Calendar"
    )
    last_google_sync: Optional[datetime] = Field(
        None, description="Last sync with Google"
    )

    # Recurrence (optional)
    is_recurring: bool = Field(default=False, description="Whether task repeats")
    recurrence_rule: Optional[str] = Field(
        None, description="iCal RRULE string (e.g., 'FREQ=WEEKLY;BYDAY=MO')"
    )

    # Metadata
    color: Optional[str] = Field(None, description="Display color (hex code)")
    notes: Optional[str] = Field(None, description="Additional notes")
    attachments: List[str] = Field(
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
    category: str = Field(default="other")
    priority: str = Field(default="medium")
    start_date: datetime
    end_date: Optional[datetime] = None
    all_day: bool = False
    due_date: Optional[datetime] = None
    reminder_minutes: Optional[int] = Field(None, ge=0, le=40320)  # Max 4 weeks
    is_recurring: bool = False
    recurrence_rule: Optional[str] = None
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    notes: Optional[str] = None
    sync_to_google: bool = Field(
        default=True, description="Sync this event to Google Calendar"
    )


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


class CalendarSyncStatus(BaseModel):
    """Status of Google Calendar connection for a user."""

    connected: bool = Field(..., description="Whether Google Calendar is connected")
    calendar_id: Optional[str] = Field(None, description="Connected calendar ID")
    last_sync: Optional[datetime] = Field(None, description="Last sync timestamp")
    sync_enabled: bool = Field(
        default=False, description="Whether auto-sync is enabled"
    )
    events_synced: int = Field(default=0, description="Number of events synced")
