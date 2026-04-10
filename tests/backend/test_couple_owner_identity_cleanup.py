import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import app.api.couple_portal as couple_portal_module  # noqa: E402
import app.services.couple_lifecycle_service as lifecycle_module  # noqa: E402


def test_resolve_owner_identity_prefers_canonical_wedding_owner(monkeypatch):
    service = lifecycle_module.CoupleLifecycleService()
    service.weddings_collection = SimpleNamespace(
        find_one=AsyncMock(
            return_value={
                "assigned_planner_id": "planner-from-wedding",
                "assigned_planner_email": "owner@example.com",
            }
        )
    )
    resolver = AsyncMock(
        return_value={
            "planner_id": "planner-from-wedding",
            "planner_email": "owner@example.com",
        }
    )
    monkeypatch.setattr(lifecycle_module, "resolve_planner_identity", resolver)

    result = asyncio.run(
        service._resolve_owner_identity(
            {
                "wedding_id": "wedding-1",
                "planner_id": "stale-planner-id",
                "planner_email": "stale@example.com",
            }
        )
    )

    assert result["planner_email"] == "owner@example.com"
    assert resolver.await_args.args == ("planner-from-wedding", "owner@example.com")


def test_resolve_owner_identity_no_longer_falls_back_to_couple_owner_mirrors(
    monkeypatch,
):
    service = lifecycle_module.CoupleLifecycleService()
    service.weddings_collection = SimpleNamespace(find_one=AsyncMock(return_value=None))
    resolver = AsyncMock(return_value={"planner_id": None, "planner_email": None})
    monkeypatch.setattr(lifecycle_module, "resolve_planner_identity", resolver)

    result = asyncio.run(
        service._resolve_owner_identity(
            {
                "wedding_id": "wedding-1",
                "planner_id": "stale-planner-id",
                "planner_email": "stale@example.com",
            }
        )
    )

    assert result == {"planner_id": None, "planner_email": None}
    assert resolver.await_args.args == (None, None)


def test_resolve_couple_planner_email_uses_canonical_wedding_owner(monkeypatch):
    resolver = AsyncMock(return_value={"planner_email": "owner@example.com"})
    monkeypatch.setattr(
        couple_portal_module, "resolve_wedding_owner_identity", resolver
    )

    result = asyncio.run(
        couple_portal_module._resolve_couple_planner_email(
            {"planner_email": "stale@example.com"},
            wedding={"assigned_planner_email": "owner@example.com"},
        )
    )

    assert result == "owner@example.com"


def test_resolve_couple_planner_email_does_not_fall_back_to_couple_mirror(monkeypatch):
    resolver = AsyncMock(return_value={"planner_email": None})
    monkeypatch.setattr(
        couple_portal_module, "resolve_wedding_owner_identity", resolver
    )

    result = asyncio.run(
        couple_portal_module._resolve_couple_planner_email(
            {"planner_email": "stale@example.com"},
            wedding={},
        )
    )

    assert result is None
