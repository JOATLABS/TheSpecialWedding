"""Queue models for background calendar work."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

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
    task_id: str | None = None
    owner_planner_id: str | None = None
    owner_planner_email: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    run_at: datetime
    attempts: int = 0
    max_attempts: int = 5
    last_error: str | None = None
    last_error_category: str | None = None
    completed_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Config:
        populate_by_name = True
