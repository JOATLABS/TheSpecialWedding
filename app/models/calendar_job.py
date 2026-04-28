"""Queue models for background calendar work."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class CalendarJobType(str, Enum):
    """Supported background calendar job types."""

    MEETING_INVITE = "meeting_invite"


class CalendarJobStatus(str, Enum):
    """Lifecycle state for queued calendar jobs."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class CalendarJobModel(BaseModel):
    """One queued background calendar job."""

    id: str = Field(..., alias="_id")
    job_type: str = Field(default=CalendarJobType.MEETING_INVITE.value)
    status: str = Field(default=CalendarJobStatus.QUEUED.value)
    dedupe_key: str
    task_id: Optional[str] = None
    owner_planner_id: Optional[str] = None
    owner_planner_email: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)
    run_at: datetime
    attempts: int = 0
    max_attempts: int = 5
    last_error: Optional[str] = None
    last_error_category: Optional[str] = None
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True
