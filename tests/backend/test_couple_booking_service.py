"""Unit tests for ``app.services.couple_booking_service``.

These tests run against in-memory dict fakes for the three Mongo
collections the service touches (planner_tasks, calendar_connections,
planner_notifications). They cover:

* the state-machine transitions (create -> propose -> couple-accept ->
  planner approve/decline)
* optimistic-concurrency 409s on stale ``expected_version``
* the external-edit accept/reject pair
* the auto-confirm branch on ``accept_booking_slot``

The fakes are intentionally minimal — just enough surface area for the
service's ``find_one``, ``insert_one``, and ``find_one_and_update``
calls. Storage uses python dict copies so a write doesn't leak into the
"already read" snapshot the service holds.
"""

from __future__ import annotations

import os
import sys
from copy import deepcopy
from datetime import datetime, timezone
from typing import Optional

import pytest
from bson import ObjectId
from fastapi import HTTPException

os.environ.setdefault(
    "SECRET_KEY",
    "test-secret-key-this-is-long-enough-for-validation-testing-purposes-2026",
)
os.environ.setdefault("AURINKO_CLIENT_ID", "test-client-id")
os.environ.setdefault("AURINKO_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("AURINKO_OAUTH_STATE_SIGNING_KEY", "test-state-signing-key")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "test-token-encryption-key")
os.environ.setdefault("ENVIRONMENT", "test")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ---------------------------- fakes --------------------------------


def _matches(document: dict, query: dict) -> bool:
    for key, expected in query.items():
        actual = document.get(key)
        if actual != expected:
            return False
    return True


def _apply_update(doc: dict, update: dict) -> dict:
    if "$set" in update:
        for key, value in update["$set"].items():
            doc[key] = value
    if "$inc" in update:
        for key, value in update["$inc"].items():
            doc[key] = (doc.get(key) or 0) + value
    return doc


class FakeCollection:
    """In-memory dict fake supporting the small Motor surface the
    couple-booking service uses: find_one, insert_one, and
    find_one_and_update (with version-filter semantics)."""

    def __init__(self) -> None:
        self.documents: list[dict] = []

    async def find_one(self, query: dict, *_args, **_kwargs):
        for doc in self.documents:
            if _matches(doc, query):
                return deepcopy(doc)
        return None

    async def insert_one(self, doc: dict):
        self.documents.append(deepcopy(doc))

        class _Result:
            inserted_id = doc.get("_id")

        return _Result()

    async def find_one_and_update(
        self,
        query: dict,
        update: dict,
        return_document: bool = False,
        **_kwargs,
    ):
        for doc in self.documents:
            if _matches(doc, query):
                _apply_update(doc, update)
                return deepcopy(doc) if return_document else None
        return None


@pytest.fixture
def service(monkeypatch):
    """Build a CoupleBookingService with all three collections swapped
    out for in-memory fakes."""
    from app.services import couple_booking_service as module

    tasks = FakeCollection()
    connections = FakeCollection()
    notifications = FakeCollection()

    svc = module.CoupleBookingService.__new__(module.CoupleBookingService)
    svc.tasks_collection = tasks
    svc.connections_collection = connections
    svc.notifications_collection = notifications
    return svc


# ----------------------- helpers / factories ------------------------


def _seed_pending_request(
    svc,
    *,
    owner: str = "owner-1",
    owner_email: str = "owner@example.com",
    couple_id: str = "couple@example.com",
    version: int = 1,
) -> dict:
    task_id = ObjectId()
    doc = {
        "_id": task_id,
        "planner_email": owner_email,
        "owner_planner_id": owner,
        "owner_planner_email": owner_email,
        "created_by_user_id": couple_id,
        "created_by_email": couple_id,
        "couple_attendee_emails": [couple_id],
        "schedule_item_type": "meeting",
        "meeting_status": "request_pending_planner",
        "proposed_slots": [],
        "booking_topic": "Final walkthrough",
        "version": version,
        "wedding_id": "wedding-1",
    }
    svc.tasks_collection.documents.append(deepcopy(doc))
    return doc


def _seed_pending_approval(svc, *, owner: str = "owner-1") -> dict:
    task_id = ObjectId()
    doc = {
        "_id": task_id,
        "owner_planner_id": owner,
        "owner_planner_email": "owner@example.com",
        "couple_attendee_emails": ["couple@example.com"],
        "schedule_item_type": "meeting",
        "meeting_status": "pending_approval",
        "title": "Final walkthrough",
        "start_date": datetime(2026, 6, 4, 14, 0, tzinfo=timezone.utc),
        "end_date": datetime(2026, 6, 4, 15, 0, tzinfo=timezone.utc),
        "version": 3,
        "wedding_id": "wedding-1",
    }
    svc.tasks_collection.documents.append(deepcopy(doc))
    return doc


def _seed_slots_proposed(
    svc,
    *,
    owner: str = "owner-1",
    connection_id: Optional[str] = None,
    couple_id: str = "couple@example.com",
) -> dict:
    task_id = ObjectId()
    slot = {
        "start": datetime(2026, 6, 4, 10, 0, tzinfo=timezone.utc),
        "end": datetime(2026, 6, 4, 11, 0, tzinfo=timezone.utc),
        "duration_minutes": 60,
    }
    second_slot = {
        "start": datetime(2026, 6, 4, 13, 0, tzinfo=timezone.utc),
        "end": datetime(2026, 6, 4, 14, 0, tzinfo=timezone.utc),
        "duration_minutes": 60,
    }
    doc = {
        "_id": task_id,
        "owner_planner_id": owner,
        "owner_planner_email": "owner@example.com",
        "created_by_user_id": couple_id,
        "couple_attendee_emails": [couple_id],
        "schedule_item_type": "meeting",
        "meeting_status": "slots_proposed",
        "proposed_slots": [slot, second_slot],
        "sync_target_connection_ids": [connection_id] if connection_id else [],
        "booking_topic": "Walkthrough",
        "version": 2,
        "wedding_id": "wedding-1",
    }
    svc.tasks_collection.documents.append(deepcopy(doc))
    return doc


def _seed_external_pending(svc, *, owner: str = "owner-1") -> dict:
    task_id = ObjectId()
    doc = {
        "_id": task_id,
        "owner_planner_id": owner,
        "owner_planner_email": "owner@example.com",
        "schedule_item_type": "meeting",
        "title": "Canonical title",
        "description": "Canonical desc",
        "location": "Canonical loc",
        "start_date": datetime(2026, 6, 3, 14, 0, tzinfo=timezone.utc),
        "end_date": datetime(2026, 6, 3, 15, 0, tzinfo=timezone.utc),
        "meeting_status": "scheduled",
        "external_conflict_status": "pending_review",
        "external_title": "External title",
        "external_description": "External desc",
        "external_location": "External loc",
        "external_start_date": datetime(2026, 6, 3, 15, 0, tzinfo=timezone.utc),
        "external_end_date": datetime(2026, 6, 3, 16, 0, tzinfo=timezone.utc),
        "version": 4,
    }
    svc.tasks_collection.documents.append(deepcopy(doc))
    return doc


# ----------------------------- tests --------------------------------


@pytest.mark.asyncio
async def test_create_booking_request_writes_task_and_notification(service):
    """A booking request lands as a planner_task with the right meta and
    fires a MEETING_BOOKING_REQUEST notification for the planner."""
    await service.create_booking_request(
        owner_planner_id="owner-1",
        owner_planner_email="owner@example.com",
        couple_user_id="couple@example.com",
        couple_email="couple@example.com",
        wedding_id="wedding-1",
        topic="Final walkthrough",
        duration_minutes=60,
        notes="bring the tasting menu",
    )
    assert len(service.tasks_collection.documents) == 1
    task = service.tasks_collection.documents[0]
    assert task["schedule_item_type"] == "meeting"
    assert task["meeting_status"] == "request_pending_planner"
    assert task["proposed_slots"] == []
    assert task["version"] == 1
    assert task["title"].startswith("Meeting request:")
    assert task["start_date"] is None
    assert task["end_date"] is None

    assert len(service.notifications_collection.documents) == 1
    notif = service.notifications_collection.documents[0]
    assert notif["type"] == "meeting_booking_request"
    assert notif["planner_id"] == "owner@example.com"
    assert notif["metadata"]["task_id"] == str(task["_id"])


@pytest.mark.asyncio
async def test_approve_meeting_bumps_version_and_sets_scheduled(service):
    task = _seed_pending_approval(service)
    result = await service.approve_meeting(
        owner_planner_id="owner-1",
        task_id=str(task["_id"]),
        expected_version=3,
    )
    assert result.task["meeting_status"] == "scheduled"
    assert result.task["version"] == 4
    persisted = service.tasks_collection.documents[0]
    assert persisted["meeting_status"] == "scheduled"
    assert persisted["version"] == 4


@pytest.mark.asyncio
async def test_approve_meeting_rejects_stale_version_409(service):
    task = _seed_pending_approval(service)
    with pytest.raises(HTTPException) as exc_info:
        await service.approve_meeting(
            owner_planner_id="owner-1",
            task_id=str(task["_id"]),
            expected_version=999,  # stale
        )
    assert exc_info.value.status_code == 409
    detail = exc_info.value.detail
    assert detail["expected_version"] == 999
    assert detail["actual_version"] == 3


@pytest.mark.asyncio
async def test_decline_meeting_records_reason(service):
    task = _seed_pending_approval(service)
    result = await service.decline_meeting(
        owner_planner_id="owner-1",
        task_id=str(task["_id"]),
        expected_version=3,
        reason="conflict with vendor sync",
    )
    assert result.task["meeting_status"] == "cancelled"
    assert result.task["decline_reason"] == "conflict with vendor sync"
    assert result.task["version"] == 4
    # The couple gets a decline notification.
    notifs = [
        n
        for n in service.notifications_collection.documents
        if n["type"] == "meeting_booking_request"
    ]
    assert any("conflict" in (n.get("message") or "") for n in notifs)


@pytest.mark.asyncio
async def test_accept_external_change_copies_external_fields_to_canonical(service):
    task = _seed_external_pending(service)
    result = await service.accept_external_change(
        owner_planner_id="owner-1",
        task_id=str(task["_id"]),
        expected_version=4,
    )
    assert result.task["title"] == "External title"
    assert result.task["description"] == "External desc"
    assert result.task["location"] == "External loc"
    assert result.task["start_date"] == datetime(2026, 6, 3, 15, 0, tzinfo=timezone.utc)
    assert result.task["end_date"] == datetime(2026, 6, 3, 16, 0, tzinfo=timezone.utc)
    # External snapshot is cleared and conflict resolved.
    assert result.task["external_conflict_status"] == "resolved"
    assert result.task["external_title"] is None
    assert result.task["external_start_date"] is None
    # meeting_status is unchanged.
    assert result.task["meeting_status"] == "scheduled"
    assert result.task["version"] == 5


@pytest.mark.asyncio
async def test_reject_external_change_keeps_canonical_unchanged_and_resolves_conflict(
    service,
):
    task = _seed_external_pending(service)
    result = await service.reject_external_change(
        owner_planner_id="owner-1",
        task_id=str(task["_id"]),
        expected_version=4,
    )
    # Canonical preserved.
    assert result.task["title"] == "Canonical title"
    assert result.task["description"] == "Canonical desc"
    assert result.task["location"] == "Canonical loc"
    assert result.task["start_date"] == datetime(2026, 6, 3, 14, 0, tzinfo=timezone.utc)
    # External snapshot wiped; conflict resolved.
    assert result.task["external_conflict_status"] == "resolved"
    assert result.task["external_title"] is None
    assert result.task["external_end_date"] is None
    assert result.task["external_conflict_resolution"] == "reject"
    assert result.task["version"] == 5


@pytest.mark.asyncio
async def test_propose_slots_replaces_not_appends(service):
    task = _seed_pending_request(service)
    base_slot = {
        "start": datetime(2026, 6, 4, 14, 0, tzinfo=timezone.utc),
        "end": datetime(2026, 6, 4, 15, 0, tzinfo=timezone.utc),
        "duration_minutes": 60,
    }
    await service.propose_slots(
        owner_planner_id="owner-1",
        task_id=str(task["_id"]),
        slots=[base_slot],
        expected_version=1,
    )
    persisted = service.tasks_collection.documents[0]
    assert len(persisted["proposed_slots"]) == 1
    assert persisted["meeting_status"] == "slots_proposed"
    # Re-propose with a different set; should replace, not append.
    new_slots = [
        {
            "start": datetime(2026, 6, 5, 10, 0, tzinfo=timezone.utc),
            "end": datetime(2026, 6, 5, 11, 0, tzinfo=timezone.utc),
            "duration_minutes": 60,
        },
        {
            "start": datetime(2026, 6, 5, 13, 0, tzinfo=timezone.utc),
            "end": datetime(2026, 6, 5, 14, 0, tzinfo=timezone.utc),
            "duration_minutes": 60,
        },
    ]
    # Reset status so propose_slots can run again (planner could retry
    # after a couple "request different times"). For this test we just
    # verify the second call from request_pending_planner -> slots_proposed
    # replaces rather than appends.
    persisted["meeting_status"] = "request_pending_planner"
    persisted["proposed_slots"] = [base_slot]
    persisted_version = persisted["version"]
    await service.propose_slots(
        owner_planner_id="owner-1",
        task_id=str(task["_id"]),
        slots=new_slots,
        expected_version=persisted_version,
    )
    final_persisted = service.tasks_collection.documents[0]
    assert len(final_persisted["proposed_slots"]) == 2
    starts = {s["start"] for s in final_persisted["proposed_slots"]}
    assert datetime(2026, 6, 5, 10, 0, tzinfo=timezone.utc) in starts
    # The base slot from the first call must NOT have leaked through.
    assert datetime(2026, 6, 4, 14, 0, tzinfo=timezone.utc) not in starts


@pytest.mark.asyncio
async def test_accept_booking_slot_auto_confirms_when_connection_setting_true(
    service,
):
    """When the target connection's couple_booking_auto_confirm is
    True, the couple's slot pick flips the meeting straight to
    SCHEDULED — no planner approval needed."""
    connection_id = ObjectId()
    service.connections_collection.documents.append(
        {
            "_id": connection_id,
            "owner_planner_id": "owner-1",
            "couple_booking_auto_confirm": True,
        }
    )
    task = _seed_slots_proposed(service, connection_id=connection_id)
    result = await service.accept_booking_slot(
        couple_user_id="couple@example.com",
        task_id=str(task["_id"]),
        slot_index=1,
        expected_version=2,
    )
    assert result.task["meeting_status"] == "scheduled"
    assert result.task["start_date"] == datetime(2026, 6, 4, 13, 0, tzinfo=timezone.utc)
    assert result.task["end_date"] == datetime(2026, 6, 4, 14, 0, tzinfo=timezone.utc)
    assert len(result.task["proposed_slots"]) == 1


@pytest.mark.asyncio
async def test_accept_booking_slot_routes_to_pending_approval_when_setting_false(
    service,
):
    """When the target connection's couple_booking_auto_confirm is
    False, the couple's slot pick parks at PENDING_APPROVAL waiting for
    the planner to approve."""
    connection_id = ObjectId()
    service.connections_collection.documents.append(
        {
            "_id": connection_id,
            "owner_planner_id": "owner-1",
            "couple_booking_auto_confirm": False,
        }
    )
    task = _seed_slots_proposed(service, connection_id=connection_id)
    result = await service.accept_booking_slot(
        couple_user_id="couple@example.com",
        task_id=str(task["_id"]),
        slot_index=0,
        expected_version=2,
    )
    assert result.task["meeting_status"] == "pending_approval"
    # A "ready for your approval" notification fires for the planner.
    planner_notifs = [
        n
        for n in service.notifications_collection.documents
        if n.get("planner_id") == "owner@example.com"
    ]
    assert any("approval" in (n.get("title") or "").lower() for n in planner_notifs)
