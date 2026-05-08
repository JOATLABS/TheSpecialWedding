"""Batch 3 of the pre-merge UX gap closeout (P8 audit).

Verifies that when a wedding planner changes their email, the catalog
templates are (re)seeded under the NEW email so admin-onboarded planners
who never went through verify_email get the catalog at email-change time.
The seeder itself is idempotent via Phase D's `seeded_from_catalog`
markers, so repeat seeds for already-seeded planners are no-ops.
"""

from __future__ import annotations

import asyncio
import os
import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import app.services.user_management_service as user_management_service_module


class DummyEmailService:
    configured = False


def _matches(document, query):
    for key, expected in query.items():
        actual = document.get(key)
        if isinstance(expected, dict):
            if "$ne" in expected and actual == expected["$ne"]:
                return False
            if "$gt" in expected and not (actual is not None and actual > expected["$gt"]):
                return False
            continue
        if actual != expected:
            return False
    return True


class InsertOneResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class UpdateOneResult:
    def __init__(self, modified_count):
        self.modified_count = modified_count
        self.matched_count = modified_count


class AsyncCollection:
    def __init__(self, storage):
        self.storage = storage

    async def find_one(self, query, *_args, **_kwargs):
        for document in self.storage:
            if _matches(document, query):
                return deepcopy(document)
        return None

    async def update_one(self, query, update, **_kwargs):
        for document in self.storage:
            if _matches(document, query):
                for key, value in update.get("$set", {}).items():
                    document[key] = value
                for key in update.get("$unset", {}).keys():
                    document.pop(key, None)
                return UpdateOneResult(1)
        return UpdateOneResult(0)

    async def update_many(self, *_args, **_kwargs):
        return UpdateOneResult(0)


class AsyncDatabase:
    def __init__(self, storage_map):
        self.storage_map = storage_map

    def __getitem__(self, name):
        self.storage_map.setdefault(name, [])
        return AsyncCollection(self.storage_map[name])


class FakeMongo:
    def __init__(self, storage_map):
        self.storage_map = storage_map
        self.db = AsyncDatabase(storage_map)

    def get_users_collection(self):
        self.storage_map.setdefault("users", [])
        return AsyncCollection(self.storage_map["users"])


@pytest.fixture
def fake_storage():
    return {"users": []}


@pytest.fixture
def service(monkeypatch, fake_storage):
    fake_mongo = FakeMongo(fake_storage)
    monkeypatch.setattr(user_management_service_module, "mongo", fake_mongo)
    monkeypatch.setattr(
        user_management_service_module,
        "ResendEmailService",
        lambda: DummyEmailService(),
    )

    async def _noop_invalidate(*_a, **_kw):
        return None

    async def _noop_publish(*_a, **_kw):
        return None

    monkeypatch.setattr(
        user_management_service_module, "invalidate_auth_cache", _noop_invalidate
    )
    monkeypatch.setattr(
        user_management_service_module.event_bus, "publish", _noop_publish
    )
    return user_management_service_module.UserManagementService(), fake_storage


def _seed_pending_change(storage, *, role: str, old_email: str, new_email: str):
    storage["users"].append(
        {
            "_id": "user-1",
            "email": old_email,
            "role": role,
            "pending_email": new_email,
            "email_change_token": "tok-good",
            "email_change_token_expires": datetime.now(timezone.utc)
            + timedelta(hours=1),
        }
    )


def test_verify_email_change_seeds_catalog_for_new_email_when_planner(
    service, monkeypatch, fake_storage
):
    svc, storage = service
    _seed_pending_change(
        storage,
        role="wedding_planner",
        old_email="planner-old@example.com",
        new_email="planner-new@example.com",
    )

    seed_calls = []

    class StubFormService:
        async def seed_catalog_templates_for_planner(self, email):
            seed_calls.append(email)
            return {"seeded": 9, "skipped": 0}

    async def _noop_cascade(*_a, **_kw):
        return {"forms": 0}

    async def _noop_invalidate_caches(*_a, **_kw):
        return None

    monkeypatch.setattr(svc, "_cascade_planner_email_change", _noop_cascade)
    monkeypatch.setattr(svc, "_invalidate_planner_email_caches", _noop_invalidate_caches)

    import app.services.form_service as form_service_module

    monkeypatch.setattr(form_service_module, "FormService", StubFormService)

    result = asyncio.run(svc.verify_email_change("tok-good"))
    assert result["new_email"] == "planner-new@example.com"
    assert seed_calls == ["planner-new@example.com"], (
        f"FormService.seed_catalog_templates_for_planner should have been "
        f"called once with the new planner email; got {seed_calls!r}"
    )


def test_verify_email_change_does_not_seed_for_non_planner_role(
    service, monkeypatch, fake_storage
):
    svc, storage = service
    _seed_pending_change(
        storage,
        role="couple",
        old_email="couple-old@example.com",
        new_email="couple-new@example.com",
    )

    seed_calls = []

    class StubFormService:
        async def seed_catalog_templates_for_planner(self, email):
            seed_calls.append(email)
            return {"seeded": 9, "skipped": 0}

    async def _noop_cascade(*_a, **_kw):
        return {}

    async def _noop_invalidate_caches(*_a, **_kw):
        return None

    monkeypatch.setattr(svc, "_cascade_planner_email_change", _noop_cascade)
    monkeypatch.setattr(svc, "_invalidate_planner_email_caches", _noop_invalidate_caches)

    import app.services.form_service as form_service_module

    monkeypatch.setattr(form_service_module, "FormService", StubFormService)

    asyncio.run(svc.verify_email_change("tok-good"))
    assert seed_calls == [], (
        "Non-planner roles must not trigger a catalog seed on email change "
        f"(seed_calls={seed_calls!r})"
    )


def test_verify_email_change_swallows_seed_failure(service, monkeypatch, fake_storage):
    svc, storage = service
    _seed_pending_change(
        storage,
        role="wedding_planner",
        old_email="planner-old@example.com",
        new_email="planner-new@example.com",
    )

    class ExplodingFormService:
        async def seed_catalog_templates_for_planner(self, email):
            raise RuntimeError("simulated mongo blip")

    async def _noop_cascade(*_a, **_kw):
        return {}

    async def _noop_invalidate_caches(*_a, **_kw):
        return None

    monkeypatch.setattr(svc, "_cascade_planner_email_change", _noop_cascade)
    monkeypatch.setattr(svc, "_invalidate_planner_email_caches", _noop_invalidate_caches)

    import app.services.form_service as form_service_module

    monkeypatch.setattr(form_service_module, "FormService", ExplodingFormService)

    # Must not raise — the email change is the user-visible action and a
    # seed failure is logged-and-swallowed.
    result = asyncio.run(svc.verify_email_change("tok-good"))
    assert result["new_email"] == "planner-new@example.com"
