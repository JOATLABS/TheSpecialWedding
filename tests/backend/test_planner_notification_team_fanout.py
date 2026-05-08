"""Batch 14 of the pre-merge UX gap closeout (R10 audit).

The two-stage wedding-checklist toast must reach team members who
operate that flow on the planner's behalf — coordinators with
``manage_couple_portal`` for Stage 1 (invite the couple) and
coordinators with ``manage_forms`` for Stage 2 (send the checklist).

Each recipient gets their own notification document so per-session
SSE channels and bell counts stay independent. Team members without
the relevant permission do NOT see the toast.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("API_KEY", "test-api-key")


class _FakeFindCursor:
    def __init__(self, docs):
        self.docs = docs

    async def to_list(self, length=None):
        return list(self.docs)


class _FakeTeamCollection:
    def __init__(self, docs):
        self.docs = docs

    def find(self, query, *_args, **_kwargs):
        owner = query.get("owner_email")
        status = query.get("status")
        matched = []
        for doc in self.docs:
            if owner is not None and doc.get("owner_email") != owner:
                continue
            if status is not None and doc.get("status") != status:
                continue
            matched.append(doc)
        return _FakeFindCursor(matched)


class _FakeDB:
    def __init__(self, team_docs):
        self._team = _FakeTeamCollection(team_docs)

    def __getitem__(self, name):
        if name == "team_members":
            return self._team
        raise KeyError(name)


class _FakeMongo:
    def __init__(self, team_docs):
        self.db = _FakeDB(team_docs)


@pytest.fixture
def fanout_service(monkeypatch):
    """Returns (service, recipient_log) where recipient_log captures
    every planner_id passed to create_notification."""
    import app.core.database as database_module
    import app.services.planner_notification_service as svc_module

    recipient_log: list[str] = []

    async def fake_create(self, **kwargs):
        recipient_log.append(kwargs["planner_id"])
        return {"id": f"notif-{len(recipient_log)}", "message": "ok"}

    monkeypatch.setattr(
        svc_module.PlannerNotificationService,
        "create_notification",
        fake_create,
    )

    def _patch_team_docs(team_docs):
        fake_mongo = _FakeMongo(team_docs)
        monkeypatch.setattr(database_module, "mongo", fake_mongo)

    service = svc_module.PlannerNotificationService()
    return service, recipient_log, _patch_team_docs


def test_notify_wedding_created_fans_out_to_couple_portal_team_members(
    fanout_service,
):
    service, recipients, patch_team = fanout_service
    patch_team(
        [
            {
                "owner_email": "planner@example.com",
                "email": "coord-portal@example.com",
                "role": "coordinator",
                "custom_permissions": {"manage_couple_portal": True},
                "status": "active",
            },
            {
                "owner_email": "planner@example.com",
                "email": "viewer@example.com",
                "role": "viewer",
                "custom_permissions": {},
                "status": "active",
            },
            {
                "owner_email": "planner@example.com",
                "email": "inactive@example.com",
                "role": "coordinator",
                "custom_permissions": {"manage_couple_portal": True},
                "status": "deactivated",
            },
        ]
    )

    asyncio.run(
        service.notify_wedding_created(
            planner_id="planner@example.com",
            wedding_id="wed-1",
            couple_names="Alex & Sam",
        )
    )

    # Planner + the active coordinator with manage_couple_portal.
    # Viewer (no permission) and deactivated row are excluded.
    assert recipients == ["planner@example.com", "coord-portal@example.com"]


def test_notify_couple_portal_accepted_fans_out_to_manage_forms_members(
    fanout_service,
):
    service, recipients, patch_team = fanout_service
    patch_team(
        [
            {
                "owner_email": "planner@example.com",
                "email": "coord-forms@example.com",
                "role": "coordinator",
                "custom_permissions": {"manage_forms": True},
                "status": "active",
            },
            {
                "owner_email": "planner@example.com",
                "email": "coord-portal-only@example.com",
                "role": "coordinator",
                "custom_permissions": {
                    "manage_couple_portal": True,
                    "manage_forms": False,
                },
                "status": "active",
            },
            {
                "owner_email": "another-planner@example.com",
                "email": "stranger@example.com",
                "role": "coordinator",
                "custom_permissions": {"manage_forms": True},
                "status": "active",
            },
        ]
    )

    asyncio.run(
        service.notify_couple_portal_accepted(
            planner_id="planner@example.com",
            wedding_id="wed-1",
            couple_email="couple@example.com",
            couple_names="Alex & Sam",
            seeded_form_id="form-xyz",
        )
    )

    # Planner + the active forms-permitted coordinator. The
    # portal-only coordinator and the stranger from another planner's
    # team are excluded.
    assert recipients == ["planner@example.com", "coord-forms@example.com"]


def test_notify_team_fanout_swallows_team_lookup_failure(monkeypatch):
    """If team_members lookup blows up, fall back to planner-only."""
    import app.core.database as database_module
    import app.services.planner_notification_service as svc_module

    recipient_log: list[str] = []

    async def fake_create(self, **kwargs):
        recipient_log.append(kwargs["planner_id"])
        return {"id": f"notif-{len(recipient_log)}", "message": "ok"}

    monkeypatch.setattr(
        svc_module.PlannerNotificationService,
        "create_notification",
        fake_create,
    )

    class ExplodingDB:
        def __getitem__(self, name):
            raise RuntimeError("db unavailable")

    class ExplodingMongo:
        db = ExplodingDB()

    monkeypatch.setattr(database_module, "mongo", ExplodingMongo())

    service = svc_module.PlannerNotificationService()
    asyncio.run(
        service.notify_wedding_created(
            planner_id="planner@example.com",
            wedding_id="wed-1",
        )
    )

    assert recipient_log == ["planner@example.com"], (
        "Team-lookup failure must fall back to planner-only delivery, "
        f"got {recipient_log!r}"
    )


def test_resolve_team_recipients_dedupes_planner_in_team_table(fanout_service):
    """Defensive: if the planner's own email is somehow in team_members
    too, we still emit exactly one notification per recipient."""
    service, recipients, patch_team = fanout_service
    patch_team(
        [
            {
                "owner_email": "planner@example.com",
                "email": "planner@example.com",  # self-row, defensive
                "role": "admin",
                "custom_permissions": {"manage_couple_portal": True},
                "status": "active",
            },
            {
                "owner_email": "planner@example.com",
                "email": "coord@example.com",
                "role": "coordinator",
                "custom_permissions": {"manage_couple_portal": True},
                "status": "active",
            },
        ]
    )

    asyncio.run(
        service.notify_wedding_created(
            planner_id="planner@example.com",
            wedding_id="wed-1",
        )
    )

    assert recipients == ["planner@example.com", "coord@example.com"]
