"""Batch 5 of the pre-merge UX gap closeout.

When a root admin bulk-onboards a wedding planner via POST
/saas-admin/wedding-planners, the catalog of pre-built form templates
must be seeded so the planner doesn't see an empty Forms tab on first
login. The seed runs unconditionally on the admin-create path
(idempotent via Phase D's seeded_from_catalog markers).
"""

from __future__ import annotations

import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import app.api.saas_config as saas_config_module  # noqa: E402


class FakeUsersCollection:
    def __init__(self, existing_email: str | None = None):
        self.existing_email = existing_email
        self.inserted: list[dict] = []

    async def find_one(self, query, *_args, **_kwargs):
        if self.existing_email and query.get("email") == self.existing_email:
            return {"_id": "existing", "email": self.existing_email}
        return None

    async def insert_one(self, document):
        self.inserted.append(document)
        return SimpleNamespace(inserted_id="planner-1")


def _patch_users_collection(monkeypatch, users_collection):
    monkeypatch.setattr(
        saas_config_module.mongo, "get_users_collection", lambda: users_collection
    )


def _patch_form_service(monkeypatch, *, raises: bool = False):
    seed_calls: list[str] = []

    class StubFormService:
        async def seed_catalog_templates_for_planner(self, email):
            seed_calls.append(email)
            if raises:
                raise RuntimeError("simulated seed failure")
            return {"seeded": 9, "skipped": 0}

    import app.services.form_service as form_service_module

    monkeypatch.setattr(form_service_module, "FormService", StubFormService)
    return seed_calls


def test_admin_create_wedding_planner_seeds_catalog(monkeypatch):
    users_collection = FakeUsersCollection()
    _patch_users_collection(monkeypatch, users_collection)
    seed_calls = _patch_form_service(monkeypatch)

    result = asyncio.run(
        saas_config_module.create_wedding_planner(
            planner_data={
                "email": "new-planner@example.com",
                "company_name": "New Planner Co",
            },
            current_user=SimpleNamespace(email="root@example.com"),
        )
    )

    assert result["user_id"] == "planner-1"
    assert seed_calls == ["new-planner@example.com"], (
        f"FormService seeder must be called once with the new planner's "
        f"email; got {seed_calls!r}"
    )


def test_admin_create_wedding_planner_succeeds_when_seed_raises(monkeypatch):
    """Seeder failure must not roll back the user-insertion or surface a 500."""
    users_collection = FakeUsersCollection()
    _patch_users_collection(monkeypatch, users_collection)
    seed_calls = _patch_form_service(monkeypatch, raises=True)

    result = asyncio.run(
        saas_config_module.create_wedding_planner(
            planner_data={"email": "shaky-mongo@example.com"},
            current_user=SimpleNamespace(email="root@example.com"),
        )
    )
    assert result["user_id"] == "planner-1"
    assert seed_calls == ["shaky-mongo@example.com"]
    assert users_collection.inserted, (
        "User must remain inserted even when the seed step blows up"
    )


def test_admin_create_wedding_planner_does_not_seed_when_email_collides(monkeypatch):
    """If the email already exists, we 400 before insert and must not seed."""
    users_collection = FakeUsersCollection(existing_email="taken@example.com")
    _patch_users_collection(monkeypatch, users_collection)
    seed_calls = _patch_form_service(monkeypatch)

    from fastapi import HTTPException

    try:
        asyncio.run(
            saas_config_module.create_wedding_planner(
                planner_data={"email": "taken@example.com"},
                current_user=SimpleNamespace(email="root@example.com"),
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 400
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected 400 collision response")

    assert seed_calls == [], (
        "Collision path must not invoke the seeder "
        f"(seed_calls={seed_calls!r})"
    )
