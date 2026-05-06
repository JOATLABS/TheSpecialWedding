"""Aurinko webhook handling for external calendar changes.

Aurinko delivers a notification when an event in a connected calendar is
created, modified, or deleted from the provider side. This service:

1. Verifies the HMAC signature on each delivery (rejecting forgeries).
2. Rejects deliveries older than CALENDAR_WEBHOOK_REPLAY_WINDOW_SECONDS or
   already-seen delivery IDs (replay protection via the idempotency store).
3. Resolves the connection that owns the changed calendar.
4. Maps the change onto the internal planner_task by way of
   calendar_event_syncs (one row per (planner_task, connection) pair carrying
   the external_event_id we wrote when the task was first synced out).
5. Writes the snapshot to ``planner_tasks.external_*`` fields and sets
   ``external_conflict_status='pending_review'`` — canonical fields are NOT
   silently overwritten. The planner UI surfaces a "modified externally"
   badge until accept/reject is invoked.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import UTC, datetime
from typing import Any, Optional

from app.core.config import settings
from app.core.database import mongo
from app.models.calendar import (
    ExternalConflictSource,
    ExternalConflictStatus,
)
from app.services.calendar_idempotency_service import calendar_idempotency_service

logger = logging.getLogger(__name__)


def _coerce_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


class CalendarWebhookService:
    """Verify and apply external calendar change notifications from Aurinko."""

    def __init__(self) -> None:
        self.connections_collection = mongo.get_calendar_connections_collection()
        self.syncs_collection = mongo.get_calendar_event_syncs_collection()
        self.tasks_collection = mongo.get_planner_tasks_collection()

    def verify_signature(
        self, raw_body: bytes, signature_header: Optional[str]
    ) -> bool:
        """Verify Aurinko HMAC signature on a webhook delivery."""
        secret = settings.AURINKO_WEBHOOK_SECRET
        if not secret:
            return False
        if not signature_header:
            return False
        expected = hmac.new(
            secret.encode("utf-8"), raw_body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature_header.strip())

    def is_within_replay_window(self, delivery_timestamp: Optional[datetime]) -> bool:
        if delivery_timestamp is None:
            return True
        now = datetime.now(UTC)
        if delivery_timestamp.tzinfo is None:
            delivery_timestamp = delivery_timestamp.replace(tzinfo=UTC)
        delta = abs((now - delivery_timestamp).total_seconds())
        return delta <= settings.CALENDAR_WEBHOOK_REPLAY_WINDOW_SECONDS

    async def is_duplicate_delivery(self, delivery_id: str) -> bool:
        """Use the idempotency store to dedupe Aurinko deliveries by ID."""
        request_hash = calendar_idempotency_service.build_request_hash(
            action="aurinko_webhook_delivery",
            payload={"delivery_id": delivery_id},
        )
        resolution = await calendar_idempotency_service.begin(
            scope_key="aurinko_webhook",
            idempotency_key=delivery_id,
            request_hash=request_hash,
        )
        if resolution.state in {"replay", "in_progress"}:
            return True
        return False

    async def mark_delivery_processed(self, delivery_id: str) -> None:
        await calendar_idempotency_service.complete(
            scope_key="aurinko_webhook",
            idempotency_key=delivery_id,
            response_payload={"processed": True},
            response_status_code=200,
        )

    async def handle_event_change(
        self,
        *,
        aurinko_account_id: str,
        aurinko_calendar_id: str,
        external_event_id: str,
        change_type: str,
        snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply an external change to the matching planner_task, if any.

        Returns a small status dict for logging/observability.
        """
        connection = await self.connections_collection.find_one(
            {
                "aurinko_account_id": aurinko_account_id,
                "aurinko_calendar_id": aurinko_calendar_id,
            }
        )
        if not connection:
            return {"matched": False, "reason": "connection_not_found"}

        sync_row = await self.syncs_collection.find_one(
            {
                "calendar_connection_id": str(connection["_id"]),
                "external_event_id": external_event_id,
            }
        )
        if not sync_row:
            return {"matched": False, "reason": "sync_row_not_found"}

        task_id = sync_row.get("planner_task_id")
        if not task_id:
            return {"matched": False, "reason": "task_id_missing"}

        if change_type == "deleted":
            await self.tasks_collection.update_one(
                {"_id": task_id},
                {
                    "$set": {
                        "external_conflict_status": ExternalConflictStatus.PENDING_REVIEW.value,
                        "external_conflict_source": ExternalConflictSource.WEBHOOK.value,
                        "external_conflict_detected_at": datetime.now(UTC),
                        "external_last_modified_at": datetime.now(UTC),
                        "updated_at": datetime.now(UTC),
                    }
                },
            )
            return {"matched": True, "task_id": str(task_id), "change": "deleted"}

        external_start = _coerce_datetime(snapshot.get("start"))
        external_end = _coerce_datetime(snapshot.get("end"))
        external_last_modified = _coerce_datetime(
            snapshot.get("last_modified") or snapshot.get("updated")
        )

        update_doc = {
            "external_start_date": external_start,
            "external_end_date": external_end,
            "external_title": snapshot.get("title") or snapshot.get("summary"),
            "external_description": snapshot.get("description"),
            "external_location": snapshot.get("location"),
            "external_last_modified_at": external_last_modified or datetime.now(UTC),
            "external_conflict_status": ExternalConflictStatus.PENDING_REVIEW.value,
            "external_conflict_source": ExternalConflictSource.WEBHOOK.value,
            "external_conflict_detected_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
        await self.tasks_collection.update_one({"_id": task_id}, {"$set": update_doc})
        return {"matched": True, "task_id": str(task_id), "change": change_type}


calendar_webhook_service = CalendarWebhookService()
