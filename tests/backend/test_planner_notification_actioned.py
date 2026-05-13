"""Batch 6 of the pre-merge UX gap closeout.

Adds a 'mark actioned' marker to planner notifications, distinct from
'mark as read'. Action toasts (Send checklist, Invite couple) POST
here on success so the bell stops re-prompting and the next bell-click
that re-opens the toast lands on a read-only state.

Idempotent: a second call on an already-actioned notification still
returns 200.
Ownership: a planner cannot mark another planner's notification.
"""

from __future__ import annotations

import asyncio
import os
import sys
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from unittest.mock import patch

import pytest
from bson import ObjectId

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import app.services.planner_notification_service as pns_module  # noqa: E402


def _matches(document: dict, query: dict) -> bool:
    for key, expected in query.items():
        actual = document.get(key)
        if isinstance(expected, dict):
            if "$ne" in expected and actual == expected["$ne"]:
                return False
            continue
        if actual != expected:
            return False
    return True


class FakeUpdateResult:
    def __init__(self, matched_count: int):
        self.matched_count = matched_count
        self.modified_count = matched_count


class FakeNotificationsCollection:
    def __init__(self, documents: list[dict]):
        self.documents = documents

    async def find_one(self, query):
        for doc in self.documents:
            if _matches(doc, query):
                return deepcopy(doc)
        return None

    async def update_one(self, query, update):
        for doc in self.documents:
            if _matches(doc, query):
                for key, value in update.get("$set", {}).items():
                    doc[key] = value
                return FakeUpdateResult(1)
        return FakeUpdateResult(0)

    async def count_documents(self, *_args, **_kwargs):
        return 0


@pytest.fixture
def service_with_doc(monkeypatch):
    notif_id = ObjectId()
    documents = [
        {
            "_id": notif_id,
            "planner_id": "planner-a@example.com",
            "type": "couple_portal_accepted",
            "is_read": False,
            "actioned_at": None,
        },
        {
            "_id": ObjectId(),
            "planner_id": "planner-b@example.com",
            "type": "couple_portal_accepted",
            "is_read": False,
        },
    ]
    fake_collection = FakeNotificationsCollection(documents)
    service = pns_module.PlannerNotificationService()
    monkeypatch.setattr(service, "collection", fake_collection)

    # No-op SSE
    import app.services.sse_manager as sse_module

    async def _noop_broadcast(*_a, **_kw):
        return None

    monkeypatch.setattr(sse_module.sse_manager, "broadcast_to_user", _noop_broadcast)

    return service, str(notif_id), documents


def test_mark_action_completed_sets_actioned_at(service_with_doc):
    service, notif_id, documents = service_with_doc

    result = asyncio.run(
        service.mark_action_completed(
            notification_id=notif_id, planner_id="planner-a@example.com"
        )
    )
    assert result == {"message": "Notification marked as actioned"}

    target = next(doc for doc in documents if str(doc["_id"]) == notif_id)
    assert isinstance(target["actioned_at"], datetime)
    assert target["actioned_via_action_button"] is True
    assert target["is_read"] is True


def test_mark_action_completed_requires_planner_ownership(service_with_doc):
    service, notif_id, documents = service_with_doc

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(
            service.mark_action_completed(
                notification_id=notif_id,
                planner_id="someone-else@example.com",
            )
        )
    assert excinfo.value.status_code == 404

    target = next(doc for doc in documents if str(doc["_id"]) == notif_id)
    assert target["actioned_at"] is None, (
        "Cross-planner mark must not mutate the document"
    )


def test_mark_action_completed_is_idempotent(service_with_doc):
    service, notif_id, documents = service_with_doc

    asyncio.run(
        service.mark_action_completed(
            notification_id=notif_id, planner_id="planner-a@example.com"
        )
    )
    target = next(doc for doc in documents if str(doc["_id"]) == notif_id)
    first_actioned_at = target["actioned_at"]

    # Second call: should still return success (200) and the field
    # remains set. Document timestamp may update but the call must not
    # raise or 4xx.
    result = asyncio.run(
        service.mark_action_completed(
            notification_id=notif_id, planner_id="planner-a@example.com"
        )
    )
    assert result == {"message": "Notification marked as actioned"}
    assert target["actioned_at"] is not None
    assert target["actioned_at"] >= first_actioned_at


def test_mark_action_completed_rejects_invalid_id():
    service = pns_module.PlannerNotificationService()
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(
            service.mark_action_completed(
                notification_id="not-an-objectid",
                planner_id="planner-a@example.com",
            )
        )
    assert excinfo.value.status_code == 400
