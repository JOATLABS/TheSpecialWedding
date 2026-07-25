"""Couple-booking + external-edit resolution service.

Wraps planner_tasks state transitions for the four lifecycle events
the planner UI surfaces: approve/decline a couple-initiated booking,
and accept/reject an external-edit detected by the Aurinko webhook
pipeline. Each transition is optimistic-concurrency gated by
``planner_tasks.version``.

Also exposes:
* ``create_booking_request`` -- couple submits an open meeting request
* ``propose_slots``         -- planner pushes 3-5 slots into the
                               request (still PENDING_APPROVAL until
                               couple picks)
* ``accept_booking_slot``   -- couple picks a planner-proposed slot
                               (auto-confirm flips it to SCHEDULED;
                               otherwise stays PENDING_APPROVAL waiting
                               on planner approve)

Returns:
* ``BookingResult`` dataclass with {task, conflict (Optional[409 detail])}
* Raises ``HTTPException`` 404/409/400 for invariant violations

Phase-3 TODOs:
* Wire the four stub endpoints in ``app/api/planner_calendar.py``
  (accept_meeting_external_change, reject_meeting_external_change,
  approve_couple_booking, decline_couple_booking) to call into this
  service.
* Add ``schedule_item_type='meeting'`` filter to the booking-requests
  inbox aggregation so the new ``request_pending_planner`` /
  ``slots_proposed`` rows surface in the planner UI.
* The Aurinko booking call after ``approve_meeting`` is owned by
  ``calendar_sync_service``; this service intentionally does NOT
  import calendar_provider_service to keep the dependency graph
  one-way.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from fastapi import HTTPException

from app.core.database import mongo
from app.models.calendar import (
    ExternalConflictStatus,
    MeetingLifecycleStatus,
    ScheduleItemType,
)
from app.models.planner_notification import (
    PlannerNotificationTypes,
)

logger = logging.getLogger(__name__)


# Custom meeting_status values used by the couple-booking flow that sit
# BEFORE the canonical ``MeetingLifecycleStatus`` enum members. They live
# as raw strings (not in the enum) so we don't churn existing consumers
# that switch on the enum; the planner inbox aggregation matches them
# explicitly.
MEETING_STATUS_REQUEST_PENDING_PLANNER = "request_pending_planner"
MEETING_STATUS_SLOTS_PROPOSED = "slots_proposed"


@dataclass
class BookingResult:
    """Return shape for state-transition methods.

    ``task`` is the post-transition planner_task doc (already version-
    bumped). ``conflict`` is None on success; on 409 the caller raises
    with this as the detail body.
    """

    task: dict[str, Any]
    conflict: dict[str, Any] | None = None


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _coerce_object_id(task_id: str) -> Any:
    """Best-effort ObjectId coercion; falls back to the raw string so
    tests using string ids still match. Mirrors the convention used by
    the calendar aggregation surface."""
    try:
        return ObjectId(task_id)
    except Exception:
        return task_id


def _normalize_datetime(value: Any) -> datetime | None:
    """Coerce slot ``start``/``end`` inputs to timezone-aware UTC.

    Strings are parsed via ``fromisoformat`` (accepting trailing ``Z``);
    naive datetimes are localized to UTC; aware datetimes are converted
    to UTC. Storing as aware datetimes matches the rest of the calendar
    surface which round-trips through Motor with ``tz_aware=True``.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    if isinstance(value, str):
        text = value.replace("Z", "+00:00") if value.endswith("Z") else value
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    raise ValueError(f"Cannot coerce {value!r} to datetime")


def _normalize_slot(slot: dict[str, Any]) -> dict[str, Any]:
    """Canonicalize a proposed-slot dict for Mongo storage.

    Expected input keys: ``start``, ``end``, optional ``duration_minutes``.
    Outputs aware-UTC datetimes plus a derived duration when missing.
    """
    start = _normalize_datetime(slot.get("start"))
    end = _normalize_datetime(slot.get("end"))
    if start is None or end is None:
        raise HTTPException(
            status_code=400,
            detail="proposed slot must include start and end",
        )
    if end <= start:
        raise HTTPException(
            status_code=400,
            detail="proposed slot end must be after start",
        )
    duration = slot.get("duration_minutes")
    if duration is None:
        duration = int((end - start).total_seconds() // 60)
    return {
        "start": start,
        "end": end,
        "duration_minutes": int(duration),
    }


class CoupleBookingService:
    """State-machine driver for couple-booking + external-edit flows."""

    def __init__(self) -> None:
        self.tasks_collection = mongo.get_planner_tasks_collection()
        self.connections_collection = mongo.get_calendar_connections_collection()
        # The PlannerNotificationService uses ``mongo.db["planner_notifications"]``
        # directly; mirror that here so we can write notification docs
        # without circular-importing the notification service.
        self.notifications_collection = mongo.db["planner_notifications"]

    # ---------------- helpers ----------------

    async def _get_task_or_404(self, task_id: str) -> dict[str, Any]:
        oid = _coerce_object_id(task_id)
        task = await self.tasks_collection.find_one({"_id": oid})
        if task is None and isinstance(oid, ObjectId):
            # Some legacy fixtures store _id as a plain string.
            task = await self.tasks_collection.find_one({"_id": task_id})
        if task is None:
            raise HTTPException(status_code=404, detail="Meeting not found")
        return task

    def _assert_owner(self, task: dict[str, Any], owner_planner_id: str) -> None:
        if (
            task.get("owner_planner_id")
            and task["owner_planner_id"] != owner_planner_id
        ):
            raise HTTPException(
                status_code=404,
                detail="Meeting not found",
            )

    async def _conflict_detail(
        self, task_id: str, expected_version: int, message: str
    ) -> dict[str, Any]:
        """Build the 409 detail body with the freshly-read current version."""
        current_task = await self.tasks_collection.find_one(
            {"_id": _coerce_object_id(task_id)}
        )
        if current_task is None and isinstance(_coerce_object_id(task_id), ObjectId):
            current_task = await self.tasks_collection.find_one({"_id": task_id})
        actual_version = int((current_task or {}).get("version") or 1)
        return {
            "expected_version": expected_version,
            "actual_version": actual_version,
            "message": message,
        }

    async def _versioned_update(
        self,
        task_id: str,
        expected_version: int,
        set_doc: dict[str, Any],
        owner_filter: str | None = None,
        message: str = "This meeting was changed by another user. Refresh and try again.",
    ) -> dict[str, Any]:
        """Run a versioned find_one_and_update; 409 on miss, return doc on hit."""
        oid = _coerce_object_id(task_id)
        filter_doc: dict[str, Any] = {"_id": oid, "version": expected_version}
        if owner_filter is not None:
            filter_doc["owner_planner_id"] = owner_filter
        set_doc = {**set_doc, "updated_at": _utcnow()}
        update_doc = {"$set": set_doc, "$inc": {"version": 1}}
        updated = await self.tasks_collection.find_one_and_update(
            filter_doc,
            update_doc,
            return_document=True,
        )
        if updated is None:
            # find_one_and_update returned None either because the
            # version didn't match or the task doesn't exist. Surface a
            # 409 with the most-recent actual version so the UI can
            # re-fetch.
            raise HTTPException(
                status_code=409,
                detail=await self._conflict_detail(task_id, expected_version, message),
            )
        return updated

    async def _write_notification(
        self,
        *,
        planner_id: str,
        notification_type: str,
        title: str,
        message: str,
        task_id: str,
        wedding_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Persist a planner-notification document.

        Kept minimal — schema mirrors what
        ``PlannerNotificationService.create_notification`` writes so the
        existing planner notification listing aggregation picks it up.
        """
        try:
            doc = {
                "_id": ObjectId(),
                "planner_id": planner_id,
                "wedding_id": wedding_id,
                "type": notification_type,
                "title": title,
                "message": message,
                "metadata": {
                    "task_id": task_id,
                    **(payload or {}),
                },
                "priority": "medium",
                "action_url": (
                    f"/admin/planner/calendar?tab=requests&task_id={task_id}"
                ),
                "is_read": False,
                "created_at": _utcnow(),
                "read_at": None,
            }
            await self.notifications_collection.insert_one(doc)
        except Exception:  # pragma: no cover - best-effort notification write
            logger.exception(
                "couple_booking_service: failed to write notification",
            )

    # ---------- couple-initiated booking ----------

    async def create_booking_request(
        self,
        *,
        owner_planner_id: str,
        owner_planner_email: str,
        couple_user_id: str,
        couple_email: str,
        wedding_id: str,
        topic: str,
        duration_minutes: int,
        preferred_window_start: datetime | None = None,
        preferred_window_end: datetime | None = None,
        notes: str | None = None,
        target_calendar_connection_id: str | None = None,
    ) -> dict[str, Any]:
        """Couple submits an open booking request.

        Writes a planner_task with:
          * ``schedule_item_type='meeting'``
          * ``meeting_status='request_pending_planner'``  (sits BEFORE
            PENDING_APPROVAL -- planner hasn't proposed slots yet)
          * ``proposed_slots=[]``
          * version=1
        Also fires a ``MEETING_BOOKING_REQUEST`` planner notification.

        ``start_date``/``end_date`` are left NULL until the planner
        proposes slots -- the aggregation surface tolerates this shape
        because the booking-request badge is driven by
        ``details.meeting_status``.
        """
        now = _utcnow()
        task_id = ObjectId()
        sync_targets: list[str] = []
        if target_calendar_connection_id:
            sync_targets = [target_calendar_connection_id]
        doc: dict[str, Any] = {
            "_id": task_id,
            "planner_email": owner_planner_email,
            "owner_planner_id": owner_planner_id,
            "owner_planner_email": owner_planner_email,
            "created_by_user_id": couple_user_id,
            "created_by_email": couple_email,
            "couple_attendee_emails": [couple_email] if couple_email else [],
            "wedding_id": wedding_id,
            "title": f"Meeting request: {topic}",
            "description": notes,
            "schedule_item_type": ScheduleItemType.MEETING.value,
            "meeting_status": MEETING_STATUS_REQUEST_PENDING_PLANNER,
            "proposed_slots": [],
            "booking_topic": topic,
            "booking_duration_minutes": int(duration_minutes),
            "booking_preferred_window_start": _normalize_datetime(
                preferred_window_start
            ),
            "booking_preferred_window_end": _normalize_datetime(preferred_window_end),
            "booking_notes": notes,
            "sync_target_override_enabled": bool(sync_targets),
            "sync_target_connection_ids": sync_targets,
            "external_conflict_status": ExternalConflictStatus.NONE.value,
            "start_date": None,
            "end_date": None,
            "created_at": now,
            "updated_at": now,
            "version": 1,
        }
        await self.tasks_collection.insert_one(doc)
        await self._write_notification(
            planner_id=owner_planner_email,
            notification_type=PlannerNotificationTypes.MEETING_BOOKING_REQUEST,
            title="New booking request",
            message=f"{couple_email or 'A couple'} requested: {topic}",
            task_id=str(task_id),
            wedding_id=wedding_id,
            payload={
                "status": "request_pending_planner",
                "couple_user_id": couple_user_id,
                "couple_email": couple_email,
                "topic": topic,
                "duration_minutes": int(duration_minutes),
            },
        )
        return doc

    async def propose_slots(
        self,
        *,
        owner_planner_id: str,
        task_id: str,
        slots: list[dict[str, Any]],
        expected_version: int,
        proposed_by_email: str | None = None,
    ) -> BookingResult:
        """Planner pushes proposed slots into the request.

        Validates: task exists, owned by planner, current
        meeting_status='request_pending_planner', version matches.
        Replaces (does NOT append to) ``proposed_slots`` -- a second
        proposal supersedes the first.
        """
        if not slots:
            raise HTTPException(
                status_code=400,
                detail="At least one proposed slot is required",
            )
        normalized = [_normalize_slot(slot) for slot in slots]
        task = await self._get_task_or_404(task_id)
        self._assert_owner(task, owner_planner_id)
        current_status = task.get("meeting_status")
        if current_status != MEETING_STATUS_REQUEST_PENDING_PLANNER:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Slots can only be proposed on a pending booking request "
                    f"(current status: {current_status!r})"
                ),
            )
        updated = await self._versioned_update(
            task_id,
            expected_version,
            {
                "proposed_slots": normalized,
                "meeting_status": MEETING_STATUS_SLOTS_PROPOSED,
                "proposed_at": _utcnow(),
                "proposed_by_email": proposed_by_email,
            },
            owner_filter=owner_planner_id,
            message="This booking request was changed by another user.",
        )
        # Notify the couple-side stream that slots are available. We
        # write to the planner notifications collection keyed by the
        # couple's email so the couple-portal listing endpoint picks it
        # up (the couple-portal notification listing already filters by
        # planner_id == couple email — see the couple_portal handlers).
        couple_attendees = task.get("couple_attendee_emails") or []
        if couple_attendees:
            await self._write_notification(
                planner_id=couple_attendees[0],
                notification_type=PlannerNotificationTypes.MEETING_BOOKING_REQUEST,
                title="Your planner proposed times",
                message=(
                    f"{len(normalized)} time(s) available for "
                    f"{task.get('booking_topic') or 'your meeting'}"
                ),
                task_id=str(task.get("_id")),
                wedding_id=task.get("wedding_id"),
                payload={"status": "slots_proposed"},
            )
        return BookingResult(task=updated)

    async def accept_booking_slot(
        self,
        *,
        couple_user_id: str,
        task_id: str,
        slot_index: int,
        expected_version: int,
    ) -> BookingResult:
        """Couple picks one of the planner-proposed slots.

        Validates: task exists, couple is the requesting party,
        meeting_status='slots_proposed', slot_index in range, version
        matches.

        Writes:
          * start_date / end_date from the chosen slot
          * proposed_slots stripped to just the chosen one
          * meeting_status:
              - SCHEDULED if the target connection's
                ``couple_booking_auto_confirm`` is True
              - PENDING_APPROVAL otherwise
        """
        task = await self._get_task_or_404(task_id)
        # Couple-side authorization: the request must have been created
        # by this couple_user_id (or it must list the couple's email in
        # couple_attendee_emails). Defense-in-depth -- the couple-portal
        # route layer also enforces this.
        if task.get("created_by_user_id") != couple_user_id and couple_user_id not in (
            task.get("couple_attendee_emails") or []
        ):
            raise HTTPException(status_code=404, detail="Meeting not found")
        if task.get("meeting_status") != MEETING_STATUS_SLOTS_PROPOSED:
            raise HTTPException(
                status_code=400,
                detail=("Cannot accept a slot: no slots have been proposed yet."),
            )
        slots = task.get("proposed_slots") or []
        if slot_index < 0 or slot_index >= len(slots):
            raise HTTPException(status_code=400, detail="Invalid slot index")
        chosen = slots[slot_index]

        # Resolve auto-confirm from the target connection (if any).
        auto_confirm = False
        sync_targets = task.get("sync_target_connection_ids") or []
        if sync_targets:
            try:
                conn_oid = _coerce_object_id(sync_targets[0])
                connection = await self.connections_collection.find_one(
                    {"_id": conn_oid}
                )
                if connection is None and isinstance(conn_oid, ObjectId):
                    connection = await self.connections_collection.find_one(
                        {"_id": sync_targets[0]}
                    )
                if connection is not None:
                    auto_confirm = bool(
                        connection.get("couple_booking_auto_confirm", True)
                    )
            except Exception:  # pragma: no cover
                logger.exception(
                    "couple_booking_service: connection lookup failed",
                )

        new_status = (
            MeetingLifecycleStatus.SCHEDULED.value
            if auto_confirm
            else MeetingLifecycleStatus.PENDING_APPROVAL.value
        )
        updated = await self._versioned_update(
            task_id,
            expected_version,
            {
                "start_date": chosen["start"],
                "end_date": chosen["end"],
                "proposed_slots": [chosen],
                "meeting_status": new_status,
                "external_sync_requested": (
                    new_status == MeetingLifecycleStatus.SCHEDULED.value
                ),
                "slot_accepted_at": _utcnow(),
                "slot_accepted_by_user_id": couple_user_id,
            },
            message="This booking request was changed by another user.",
        )
        if new_status == MeetingLifecycleStatus.PENDING_APPROVAL.value:
            await self._write_notification(
                planner_id=task.get("owner_planner_email") or "",
                notification_type=PlannerNotificationTypes.MEETING_BOOKING_REQUEST,
                title="Booking ready for your approval",
                message=(
                    f"{couple_user_id} picked a time for "
                    f"{task.get('booking_topic') or 'a meeting'}"
                ),
                task_id=str(task.get("_id")),
                wedding_id=task.get("wedding_id"),
                payload={"status": "ready_for_approval"},
            )
        return BookingResult(task=updated)

    # ---------- planner approval ----------

    async def approve_meeting(
        self,
        *,
        owner_planner_id: str,
        task_id: str,
        expected_version: int,
    ) -> BookingResult:
        """Planner approves a PENDING_APPROVAL meeting.

        DOES NOT call Aurinko here -- ``calendar_sync_service`` watches
        for the SCHEDULED transition and books on the planner's
        calendar separately.
        """
        task = await self._get_task_or_404(task_id)
        self._assert_owner(task, owner_planner_id)
        current_status = task.get("meeting_status")
        if current_status != MeetingLifecycleStatus.PENDING_APPROVAL.value:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Only pending_approval meetings can be approved "
                    f"(current status: {current_status!r})"
                ),
            )
        updated = await self._versioned_update(
            task_id,
            expected_version,
            {
                "meeting_status": MeetingLifecycleStatus.SCHEDULED.value,
                "external_sync_requested": True,
                "approved_at": _utcnow(),
                "approved_by_planner_id": owner_planner_id,
            },
            owner_filter=owner_planner_id,
        )
        return BookingResult(task=updated)

    async def decline_meeting(
        self,
        *,
        owner_planner_id: str,
        task_id: str,
        expected_version: int,
        reason: str | None = None,
    ) -> BookingResult:
        """Planner declines a PENDING_APPROVAL meeting.

        Writes ``meeting_status=CANCELLED``, captures the free-text
        ``decline_reason`` (rendered in the couple portal), and bumps
        version. Fires a couple-side notification with the reason.
        """
        task = await self._get_task_or_404(task_id)
        self._assert_owner(task, owner_planner_id)
        current_status = task.get("meeting_status")
        if current_status != MeetingLifecycleStatus.PENDING_APPROVAL.value:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Only pending_approval meetings can be declined "
                    f"(current status: {current_status!r})"
                ),
            )
        updated = await self._versioned_update(
            task_id,
            expected_version,
            {
                "meeting_status": MeetingLifecycleStatus.CANCELLED.value,
                "status": "cancelled",
                "external_sync_requested": False,
                "decline_reason": reason,
                "declined_at": _utcnow(),
                "declined_by_planner_id": owner_planner_id,
            },
            owner_filter=owner_planner_id,
        )
        couple_attendees = task.get("couple_attendee_emails") or []
        if couple_attendees:
            await self._write_notification(
                planner_id=couple_attendees[0],
                notification_type=PlannerNotificationTypes.MEETING_BOOKING_REQUEST,
                title="Booking declined",
                message=(
                    reason or "Your planner could not accommodate the requested time."
                ),
                task_id=str(task.get("_id")),
                wedding_id=task.get("wedding_id"),
                payload={"status": "declined", "reason": reason},
            )
        return BookingResult(task=updated)

    # ---------- external-edit resolution ----------

    async def accept_external_change(
        self,
        *,
        owner_planner_id: str,
        task_id: str,
        expected_version: int,
    ) -> BookingResult:
        """Planner accepts an external-edit as the new canonical.

        Copies ``external_*`` fields back onto canonical, clears
        ``external_*`` (so the badge dismisses), sets
        ``external_conflict_status='resolved'``, and bumps version.
        ``meeting_status`` is unchanged.

        Does NOT push to Aurinko -- the external side already has the
        canonical version.
        """
        task = await self._get_task_or_404(task_id)
        self._assert_owner(task, owner_planner_id)
        if (
            task.get("external_conflict_status")
            != ExternalConflictStatus.PENDING_REVIEW.value
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "No pending external change to accept "
                    f"(status: {task.get('external_conflict_status')!r})"
                ),
            )
        set_doc: dict[str, Any] = {
            "external_conflict_status": ExternalConflictStatus.RESOLVED.value,
            "external_conflict_resolved_at": _utcnow(),
            "external_conflict_resolved_by": owner_planner_id,
            "external_conflict_resolution": "accept",
            # Clear the external snapshot so the badge dismisses cleanly.
            "external_title": None,
            "external_description": None,
            "external_location": None,
            "external_start_date": None,
            "external_end_date": None,
        }
        # Copy ONLY the external_* fields that were populated; leaving a
        # field untouched preserves canonical if Aurinko didn't include
        # it in the change payload.
        if task.get("external_title") is not None:
            set_doc["title"] = task["external_title"]
        if task.get("external_description") is not None:
            set_doc["description"] = task["external_description"]
        if task.get("external_location") is not None:
            set_doc["location"] = task["external_location"]
        if task.get("external_start_date") is not None:
            set_doc["start_date"] = task["external_start_date"]
        if task.get("external_end_date") is not None:
            set_doc["end_date"] = task["external_end_date"]

        updated = await self._versioned_update(
            task_id,
            expected_version,
            set_doc,
            owner_filter=owner_planner_id,
        )
        return BookingResult(task=updated)

    async def reject_external_change(
        self,
        *,
        owner_planner_id: str,
        task_id: str,
        expected_version: int,
    ) -> BookingResult:
        """Planner rejects the external edit -- canonical wins.

        Clears ``external_*`` (sets to None). Sets
        ``external_conflict_status='resolved'``, bumps version. Does
        NOT mutate canonical fields.

        The ``calendar_sync_service`` drift-check job will pick up the
        external/canonical mismatch on the next cycle and push canonical
        TO Aurinko, keeping the re-sync logic in one place.
        """
        task = await self._get_task_or_404(task_id)
        self._assert_owner(task, owner_planner_id)
        if (
            task.get("external_conflict_status")
            != ExternalConflictStatus.PENDING_REVIEW.value
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "No pending external change to reject "
                    f"(status: {task.get('external_conflict_status')!r})"
                ),
            )
        set_doc: dict[str, Any] = {
            "external_conflict_status": ExternalConflictStatus.RESOLVED.value,
            "external_conflict_resolved_at": _utcnow(),
            "external_conflict_resolved_by": owner_planner_id,
            "external_conflict_resolution": "reject",
            "external_title": None,
            "external_description": None,
            "external_location": None,
            "external_start_date": None,
            "external_end_date": None,
        }
        updated = await self._versioned_update(
            task_id,
            expected_version,
            set_doc,
            owner_filter=owner_planner_id,
        )
        return BookingResult(task=updated)


couple_booking_service = CoupleBookingService()
