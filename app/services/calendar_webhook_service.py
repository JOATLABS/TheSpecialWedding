"""Aurinko webhook handling for external calendar changes.

Aurinko delivers a notification when an event in a connected calendar is
created, modified, or deleted from the provider side. The notification body
carries only ``{id, changeType}`` per change — there is no event snapshot.
This service:

1. Verifies the signature on each delivery (rejects forgeries).
2. Rejects deliveries older than CALENDAR_WEBHOOK_REPLAY_WINDOW_SECONDS or
   already-seen delivery IDs (replay protection via the idempotency store).
3. For each change in the delivery, asynchronously:
   a. Resolves the connection that owns the changed calendar.
   b. Fetches the event from Aurinko to get full snapshot detail.
   c. Maps the change onto the internal planner_task by way of
      calendar_event_syncs (one row per (planner_task, connection) pair
      carrying the external_event_id we wrote when the task was first
      synced out).
   d. Writes the snapshot to ``planner_tasks.external_*`` fields and sets
      ``external_conflict_status='pending_review'`` — canonical fields are
      NOT silently overwritten. The planner UI surfaces a "modified
      externally" badge until accept/reject is invoked.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import UTC, datetime
from typing import Any, Optional

from bson import ObjectId

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


def _verify_signature_hmac_sha256_hex(
    *, raw_body: bytes, signature_header: str, secret: str
) -> bool:
    """Default verifier — HMAC-SHA256 of the raw body, hex-encoded.

    This is a STRATEGY SEAM. Aurinko's actual notification-validation spec
    lives at docs.aurinko.io/unified-apis/webhooks-api in the "Notification
    Validation" section. Once that spec is read, swap this function (or
    replace ``CalendarWebhookService.verify_signature`` to call a different
    one) without touching the rest of the file.

    Common alternatives to plan for:
    * Base64 digest instead of hex.
    * "v1=...,t=..." composite header (Stripe-style) → split + verify.
    * Concatenation of timestamp + body before HMAC (replay-protected).
    """
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header.strip())


class CalendarWebhookService:
    """Verify and apply external calendar change notifications from Aurinko."""

    def __init__(self) -> None:
        self.connections_collection = mongo.get_calendar_connections_collection()
        self.syncs_collection = mongo.get_calendar_event_syncs_collection()
        self.tasks_collection = mongo.get_planner_tasks_collection()

    # -------- signature ---------------------------------------------------

    def verify_signature(
        self, raw_body: bytes, signature_header: Optional[str]
    ) -> bool:
        """Verify Aurinko signature on a webhook delivery.

        Delegates to a strategy function so the algorithm can be swapped
        once Aurinko's exact spec is known. See module-level docstring on
        ``_verify_signature_hmac_sha256_hex``.
        """
        secret = settings.AURINKO_WEBHOOK_SECRET
        if not secret:
            return False
        if not signature_header:
            return False
        return _verify_signature_hmac_sha256_hex(
            raw_body=raw_body,
            signature_header=signature_header,
            secret=secret,
        )

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

    # -------- background dispatch (called from FastAPI BackgroundTasks) ---

    async def process_event_change_async(
        self,
        *,
        aurinko_account_id: str,
        aurinko_calendar_id: str,
        external_event_id: str,
        change_type: str,
    ) -> None:
        """Background entry point: fetch snapshot from Aurinko, then apply.

        Runs *after* the webhook handler has returned 200 to Aurinko.
        Failures are logged and swallowed — Aurinko has already been ack'd
        and will not retry. A polling drift-check job covers any missed
        snapshot updates.
        """
        snapshot: dict[str, Any] = {}
        if change_type != "deleted":
            try:
                snapshot = await self._fetch_event_snapshot(
                    aurinko_account_id=aurinko_account_id,
                    aurinko_calendar_id=aurinko_calendar_id,
                    external_event_id=external_event_id,
                )
            except Exception as exc:
                logger.warning(
                    "Aurinko snapshot fetch failed for account=%s calendar=%s "
                    "event=%s; applying change with empty snapshot: %s",
                    aurinko_account_id,
                    aurinko_calendar_id,
                    external_event_id,
                    exc,
                )

        try:
            await self.handle_event_change(
                aurinko_account_id=aurinko_account_id,
                aurinko_calendar_id=aurinko_calendar_id,
                external_event_id=external_event_id,
                change_type=change_type,
                snapshot=snapshot,
            )
        except Exception as exc:
            logger.exception(
                "Aurinko webhook background dispatch failed: account=%s calendar=%s "
                "event=%s change=%s err=%s",
                aurinko_account_id,
                aurinko_calendar_id,
                external_event_id,
                change_type,
                exc,
            )

    async def _fetch_event_snapshot(
        self,
        *,
        aurinko_account_id: str,
        aurinko_calendar_id: str,
        external_event_id: str,
    ) -> dict[str, Any]:
        """Pull full event detail from Aurinko using the owning connection's token.

        Imported lazily to avoid a circular import at module load time —
        ``calendar_provider_service`` imports from this module's siblings.
        """
        from app.services.calendar_provider_service import (
            calendar_provider_service,
        )

        connection = await self.connections_collection.find_one(
            {
                "aurinko_account_id": aurinko_account_id,
                "aurinko_calendar_id": aurinko_calendar_id,
            }
        )
        if not connection:
            return {}

        token = calendar_provider_service._decrypt_token(
            connection.get("aurinko_access_token_encrypted")
        )
        if not token:
            return {}

        raw = await calendar_provider_service.client.get_event(
            account_token=token,
            calendar_id=aurinko_calendar_id,
            external_event_id=external_event_id,
        )
        return raw or {}

    # -------- direct apply (also used by the polling drift-check job) ----

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

        Returns a small status dict for logging/observability. Snapshot may
        be empty (provider fetch failed, or change_type=deleted) — in that
        case ``external_*`` snapshot fields are left untouched and only the
        conflict-status fields are set so the planner UI shows the badge.
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

        task_id = sync_row.get("task_id")
        if not task_id:
            return {"matched": False, "reason": "task_id_missing"}

        try:
            task_object_id = ObjectId(task_id)
        except Exception:
            return {"matched": False, "reason": "task_id_invalid"}

        now = datetime.now(UTC)
        if change_type == "deleted":
            await self.tasks_collection.update_one(
                {"_id": task_object_id},
                {
                    "$set": {
                        "external_conflict_status": ExternalConflictStatus.PENDING_REVIEW.value,
                        "external_conflict_source": ExternalConflictSource.WEBHOOK.value,
                        "external_conflict_detected_at": now,
                        "external_last_modified_at": now,
                        "updated_at": now,
                    }
                },
            )
            return {"matched": True, "task_id": str(task_object_id), "change": "deleted"}

        update_doc: dict[str, Any] = {
            "external_conflict_status": ExternalConflictStatus.PENDING_REVIEW.value,
            "external_conflict_source": ExternalConflictSource.WEBHOOK.value,
            "external_conflict_detected_at": now,
            "updated_at": now,
        }

        if snapshot:
            # Aurinko event shape mirrors what list_events returns; reuse the
            # same field projection so external_* fields stay consistent
            # whether populated by webhook fetch or by drift-check polling.
            when = snapshot.get("when") or {}
            external_start = _coerce_datetime(
                (when.get("start") if isinstance(when, dict) else None)
                or snapshot.get("start")
            )
            external_end = _coerce_datetime(
                (when.get("end") if isinstance(when, dict) else None)
                or snapshot.get("end")
            )
            external_last_modified = _coerce_datetime(
                snapshot.get("lastModifiedDateTime")
                or snapshot.get("last_modified")
                or snapshot.get("updated")
            )
            location = snapshot.get("location")
            if isinstance(location, dict):
                location = location.get("displayName")

            update_doc.update(
                {
                    "external_start_date": external_start,
                    "external_end_date": external_end,
                    "external_title": snapshot.get("subject")
                    or snapshot.get("title")
                    or snapshot.get("summary"),
                    "external_description": snapshot.get("description")
                    or snapshot.get("bodyPreview"),
                    "external_location": location,
                    "external_last_modified_at": external_last_modified or now,
                }
            )
        else:
            update_doc["external_last_modified_at"] = now

        await self.tasks_collection.update_one({"_id": task_object_id}, {"$set": update_doc})
        return {"matched": True, "task_id": str(task_object_id), "change": change_type}


calendar_webhook_service = CalendarWebhookService()
