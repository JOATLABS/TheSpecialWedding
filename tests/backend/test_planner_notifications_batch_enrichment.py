"""Batch enrichment for planner notification listing.

Verifies that `PlannerNotificationService.get_notifications` does ONE
weddings-collection lookup per page (a single `$in` query), instead of
one `find_one` per row. This protects the notifications list endpoint
from N+1 wedding lookups when a planner has many active weddings.

Control cases:
- notifications without `wedding_id` (no extra query at all)
- notifications whose `wedding_id` doesn't match any wedding row (no
  enrichment, but we still emit the notification)
"""

from __future__ import annotations

import asyncio
import os
import sys
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest
from bson import ObjectId

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import app.services.planner_notification_service as pns_module  # noqa: E402


# ----------------------------- fakes ---------------------------------


def _matches(document: dict, query: dict) -> bool:
    for key, expected in query.items():
        actual = document.get(key)
        if isinstance(expected, dict):
            if "$in" in expected:
                if actual not in expected["$in"]:
                    return False
                continue
            continue
        if actual != expected:
            return False
    return True


class _AsyncCursor:
    """Minimal async cursor over a python list with sort/skip/limit chain."""

    def __init__(self, documents: list[dict]):
        self._docs = documents

    def sort(self, *_args, **_kwargs):
        # Tests don't rely on sort ordering.
        return self

    def skip(self, n: int):
        self._docs = self._docs[n:]
        return self

    def limit(self, n: int):
        self._docs = self._docs[:n]
        return self

    def __aiter__(self):
        async def _gen():
            for doc in self._docs:
                yield deepcopy(doc)

        return _gen()


class FakeNotificationsCollection:
    def __init__(self, documents: list[dict]):
        self.documents = documents

    def find(self, query):
        return _AsyncCursor([d for d in self.documents if _matches(d, query)])

    async def count_documents(self, query):
        return len([d for d in self.documents if _matches(d, query)])


class SpyWeddingsCollection:
    """Wraps a list of wedding rows and counts find()-with-$in calls."""

    def __init__(self, weddings: list[dict]):
        self.weddings = weddings
        self.find_calls: list[dict] = []

    def find(self, query, projection=None):
        self.find_calls.append(query)
        matched = [w for w in self.weddings if _matches(w, query)]
        return _AsyncCursor(matched)

    async def find_one(self, *_args, **_kwargs):
        # If anyone falls back to find_one, fail loudly: the refactor
        # should have routed everything through `find`.
        raise AssertionError(
            "find_one should not be called on the weddings collection during get_notifications"
        )


# --------------------------- fixtures --------------------------------


def _make_notification(planner_id: str, wedding_id: str | None) -> dict:
    return {
        "_id": ObjectId(),
        "planner_id": planner_id,
        "wedding_id": wedding_id,
        "type": "form_response",
        "title": "Some title",
        "message": "Some message",
        "metadata": {},
        "priority": "medium",
        "action_url": None,
        "is_read": False,
        "created_at": datetime.now(timezone.utc),
        "read_at": None,
    }


def _build_service(
    monkeypatch, notifications: list[dict], weddings: list[dict]
) -> tuple[Any, SpyWeddingsCollection]:
    fake_notifications = FakeNotificationsCollection(notifications)
    spy_weddings = SpyWeddingsCollection(weddings)

    service = pns_module.PlannerNotificationService()
    monkeypatch.setattr(service, "collection", fake_notifications)
    monkeypatch.setattr(service, "weddings_collection", spy_weddings)
    return service, spy_weddings


# ----------------------------- tests ---------------------------------


def test_get_notifications_uses_one_wedding_lookup_per_page(monkeypatch):
    """5 notifications referencing 3 unique wedding_ids -> 1 batched find()."""
    planner = "planner-a@example.com"
    notifications = [
        _make_notification(planner, "wedding-1"),
        _make_notification(planner, "wedding-2"),
        _make_notification(planner, "wedding-1"),
        _make_notification(planner, "wedding-3"),
        _make_notification(planner, "wedding-2"),
    ]
    weddings = [
        {"wedding_id": "wedding-1", "title": "Avery & Jordan"},
        {"wedding_id": "wedding-2", "title": "Maya & Sam"},
        {"wedding_id": "wedding-3", "title": "Riley & Quinn"},
    ]
    service, spy = _build_service(monkeypatch, notifications, weddings)

    result = asyncio.run(service.get_notifications(planner_id=planner, limit=20))

    assert len(spy.find_calls) == 1, (
        f"expected exactly 1 weddings.find() call, got {len(spy.find_calls)}: {spy.find_calls}"
    )
    in_clause = spy.find_calls[0]["wedding_id"]["$in"]
    assert sorted(in_clause) == ["wedding-1", "wedding-2", "wedding-3"]

    titles = {n["wedding_id"]: n["wedding_name"] for n in result["notifications"]}
    assert titles["wedding-1"] == "Avery & Jordan"
    assert titles["wedding-2"] == "Maya & Sam"
    assert titles["wedding-3"] == "Riley & Quinn"
    assert result["total"] == 5


def test_get_notifications_handles_notifications_without_wedding_id(monkeypatch):
    """If no row has a wedding_id, we skip the weddings find() entirely."""
    planner = "planner-b@example.com"
    notifications = [
        _make_notification(planner, None),
        _make_notification(planner, None),
    ]
    service, spy = _build_service(monkeypatch, notifications, weddings=[])

    result = asyncio.run(service.get_notifications(planner_id=planner, limit=20))

    assert len(spy.find_calls) == 0, "no rows have wedding_id -> no batch lookup"
    assert all(n["wedding_name"] is None for n in result["notifications"])
    assert all(n["wedding_id"] is None for n in result["notifications"])
    assert result["total"] == 2


def test_get_notifications_handles_unknown_wedding_id(monkeypatch):
    """An orphan wedding_id (no matching weddings row) yields wedding_name=None."""
    planner = "planner-c@example.com"
    notifications = [
        _make_notification(planner, "wedding-known"),
        _make_notification(planner, "wedding-orphan"),
    ]
    weddings = [{"wedding_id": "wedding-known", "title": "Known Couple"}]
    service, spy = _build_service(monkeypatch, notifications, weddings)

    result = asyncio.run(service.get_notifications(planner_id=planner, limit=20))

    assert len(spy.find_calls) == 1
    assert sorted(spy.find_calls[0]["wedding_id"]["$in"]) == [
        "wedding-known",
        "wedding-orphan",
    ]

    by_id = {n["wedding_id"]: n["wedding_name"] for n in result["notifications"]}
    assert by_id["wedding-known"] == "Known Couple"
    assert by_id["wedding-orphan"] is None
