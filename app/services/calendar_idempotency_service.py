"""Idempotency storage for calendar mutations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any

from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.core.database import mongo


@dataclass(slots=True)
class CalendarIdempotencyResolution:
    """Result of opening an idempotent calendar command."""

    state: str
    response_payload: dict[str, Any] | None = None
    response_status_code: int | None = None


class CalendarIdempotencyService:
    """Persist and replay idempotent calendar command responses."""

    def __init__(self) -> None:
        self.collection = mongo.get_calendar_idempotency_collection()

    def build_request_hash(
        self,
        *,
        action: str,
        payload: Any,
    ) -> str:
        canonical_payload = self._canonicalize(payload)
        body = json.dumps(
            {
                "action": action,
                "payload": canonical_payload,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return sha256(body.encode("utf-8")).hexdigest()

    def _canonicalize(self, value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(key): self._canonicalize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._canonicalize(item) for item in value]
        if hasattr(value, "model_dump"):
            return self._canonicalize(value.model_dump(mode="json"))
        return value

    async def begin(
        self,
        *,
        scope_key: str,
        idempotency_key: str,
        request_hash: str,
    ) -> CalendarIdempotencyResolution:
        now = datetime.now(UTC)
        expires_at = now + timedelta(hours=settings.CALENDAR_IDEMPOTENCY_TTL_HOURS)
        record = {
            "scope_key": scope_key,
            "idempotency_key": idempotency_key,
            "request_hash": request_hash,
            "status": "in_progress",
            "response_payload": None,
            "response_status_code": None,
            "error_detail": None,
            "created_at": now,
            "updated_at": now,
            "expires_at": expires_at,
        }

        try:
            await self.collection.insert_one(record)
            return CalendarIdempotencyResolution(state="started")
        except DuplicateKeyError:
            existing = await self.collection.find_one(
                {
                    "scope_key": scope_key,
                    "idempotency_key": idempotency_key,
                }
            )
            if not isinstance(existing, dict):
                return CalendarIdempotencyResolution(state="started")

            if existing.get("request_hash") != request_hash:
                return CalendarIdempotencyResolution(state="conflict")

            status = existing.get("status")
            updated_at = existing.get("updated_at")
            stale_cutoff = now - timedelta(
                seconds=settings.CALENDAR_IDEMPOTENCY_IN_PROGRESS_TIMEOUT_SECONDS
            )
            is_stale = isinstance(updated_at, datetime) and updated_at < stale_cutoff

            if status == "completed":
                return CalendarIdempotencyResolution(
                    state="replay",
                    response_payload=existing.get("response_payload"),
                    response_status_code=existing.get("response_status_code"),
                )

            if status == "failed" or is_stale:
                await self.collection.update_one(
                    {
                        "_id": existing["_id"],
                        "request_hash": request_hash,
                    },
                    {
                        "$set": {
                            "status": "in_progress",
                            "error_detail": None,
                            "updated_at": now,
                            "expires_at": expires_at,
                        }
                    },
                )
                return CalendarIdempotencyResolution(state="started")

            return CalendarIdempotencyResolution(state="in_progress")

    async def complete(
        self,
        *,
        scope_key: str,
        idempotency_key: str,
        response_payload: dict[str, Any],
        response_status_code: int = 200,
    ) -> None:
        now = datetime.now(UTC)
        await self.collection.update_one(
            {
                "scope_key": scope_key,
                "idempotency_key": idempotency_key,
            },
            {
                "$set": {
                    "status": "completed",
                    "response_payload": response_payload,
                    "response_status_code": response_status_code,
                    "error_detail": None,
                    "updated_at": now,
                    "expires_at": now
                    + timedelta(hours=settings.CALENDAR_IDEMPOTENCY_TTL_HOURS),
                }
            },
        )

    async def fail(
        self,
        *,
        scope_key: str,
        idempotency_key: str,
        error_detail: str,
    ) -> None:
        now = datetime.now(UTC)
        await self.collection.update_one(
            {
                "scope_key": scope_key,
                "idempotency_key": idempotency_key,
            },
            {
                "$set": {
                    "status": "failed",
                    "error_detail": error_detail,
                    "updated_at": now,
                    "expires_at": now
                    + timedelta(hours=settings.CALENDAR_IDEMPOTENCY_TTL_HOURS),
                }
            },
        )


calendar_idempotency_service = CalendarIdempotencyService()
