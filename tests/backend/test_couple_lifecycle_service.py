import asyncio
import os
import sys
from unittest.mock import AsyncMock

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import app.services.couple_lifecycle_service as couple_lifecycle_module  # noqa: E402
from app.models.team_member import TeamMemberStatus  # noqa: E402
from app.services.couple_lifecycle_service import (  # noqa: E402
    COUPLE_PORTAL_STATE_ACTIVE,
    COUPLE_PORTAL_STATE_OWNER_CANCELLED,
    COUPLE_PORTAL_STATE_PENDING_SETUP,
    COUPLE_PORTAL_STATE_REVOKED,
    CoupleLifecycleService,
)


def test_owner_cancelled_team_status_is_declared_on_the_model():
    assert (
        TeamMemberStatus.SUSPENDED_OWNER_CANCELLED.value == "suspended_owner_cancelled"
    )


def test_build_owner_cancelled_update_skips_manually_revoked_couples():
    service = CoupleLifecycleService()

    update = service.build_owner_cancelled_update(
        {
            "access_state": COUPLE_PORTAL_STATE_REVOKED,
            "setup_completed": True,
            "is_active": False,
        },
        planner_id="planner-1",
        planner_email="planner@example.com",
    )

    assert update is None


def test_build_owner_restore_update_returns_pending_setup_for_unset_up_couple():
    service = CoupleLifecycleService()

    update = service.build_owner_restore_update(
        {
            "access_state": COUPLE_PORTAL_STATE_OWNER_CANCELLED,
            "setup_completed": False,
            "is_active": False,
        }
    )

    assert update is not None
    assert update["access_state"] == COUPLE_PORTAL_STATE_PENDING_SETUP
    assert update["is_active"] is False
    assert update["owner_cancelled_at"] is None


def test_resolve_effective_state_keeps_owner_cancelled_blocked_until_restored():
    service = CoupleLifecycleService()
    service._owner_is_blocked = AsyncMock(return_value=False)

    result = asyncio.run(
        service.resolve_effective_state(
            {
                "access_state": COUPLE_PORTAL_STATE_OWNER_CANCELLED,
                "setup_completed": True,
                "is_active": False,
            }
        )
    )

    assert result["state"] == COUPLE_PORTAL_STATE_OWNER_CANCELLED
    assert result["blocked"] is True


def test_resolve_effective_state_marks_active_couple_owner_cancelled_when_owner_blocked():
    service = CoupleLifecycleService()
    service._owner_is_blocked = AsyncMock(return_value=True)

    result = asyncio.run(
        service.resolve_effective_state(
            {
                "access_state": COUPLE_PORTAL_STATE_ACTIVE,
                "setup_completed": True,
                "is_active": True,
            }
        )
    )

    assert result["state"] == COUPLE_PORTAL_STATE_OWNER_CANCELLED
    assert result["blocked"] is True


@pytest.mark.asyncio
async def test_owner_identity_resolution_uses_canonical_wedding_owner(
    monkeypatch: pytest.MonkeyPatch,
):
    service = CoupleLifecycleService()

    class FakeWeddingsCollection:
        async def find_one(self, query, projection=None):
            assert query == {"_id": "wedding-1"}
            return {
                "assigned_planner_id": "owner-1",
                "assigned_planner_email": "owner@example.com",
            }

    captured: dict[str, str | None] = {}

    async def fake_resolve(planner_id, planner_email):
        captured["planner_id"] = planner_id
        captured["planner_email"] = planner_email
        return {"planner_id": planner_id, "planner_email": planner_email}

    service.weddings_collection = FakeWeddingsCollection()
    monkeypatch.setattr(couple_lifecycle_module, "resolve_planner_identity", fake_resolve)

    result = await service._resolve_owner_identity(
        {
            "wedding_id": "wedding-1",
            "planner_id": "stale-planner",
            "planner_email": "stale@example.com",
        }
    )

    assert captured == {
        "planner_id": "owner-1",
        "planner_email": "owner@example.com",
    }
    assert result == {
        "planner_id": "owner-1",
        "planner_email": "owner@example.com",
    }


@pytest.mark.asyncio
async def test_owner_identity_resolution_does_not_fallback_to_couple_mirrors(
    monkeypatch: pytest.MonkeyPatch,
):
    service = CoupleLifecycleService()

    class FakeWeddingsCollection:
        async def find_one(self, query, projection=None):
            assert query == {"_id": "wedding-2"}
            return {}

    captured: dict[str, str | None] = {}

    async def fake_resolve(planner_id, planner_email):
        captured["planner_id"] = planner_id
        captured["planner_email"] = planner_email
        return {"planner_id": planner_id, "planner_email": planner_email}

    service.weddings_collection = FakeWeddingsCollection()
    monkeypatch.setattr(couple_lifecycle_module, "resolve_planner_identity", fake_resolve)

    result = await service._resolve_owner_identity(
        {
            "wedding_id": "wedding-2",
            "planner_id": "stale-planner",
            "planner_email": "stale@example.com",
        }
    )

    assert captured == {
        "planner_id": None,
        "planner_email": None,
    }
    assert result == {
        "planner_id": None,
        "planner_email": None,
    }
