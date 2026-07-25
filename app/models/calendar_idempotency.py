"""Idempotency record models for calendar mutations."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CalendarIdempotencyStatus(str, Enum):
    """Lifecycle state for an idempotent calendar command."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class CalendarIdempotencyModel(BaseModel):
    """Stored idempotency record for a calendar mutation."""

    id: str = Field(..., alias="_id")
    scope_key: str
    idempotency_key: str
    request_hash: str
    status: str = Field(default=CalendarIdempotencyStatus.IN_PROGRESS.value)
    response_payload: dict[str, Any] | None = None
    response_status_code: int | None = None
    error_detail: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime

    class Config:
        populate_by_name = True
