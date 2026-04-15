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
    def __init__(self, planner: dict):
        self.planner = planner
        self.updates: list[dict] = []

    async def find_one(self, query):
        return dict(self.planner)

    async def update_one(self, query, update):
        self.updates.append({"query": query, "update": update})
        self.planner = {
            **self.planner,
            **update.get("$set", {}),
        }


def test_toggle_planner_status_restores_lifecycle_when_reactivating(monkeypatch):
    planner_id = "507f1f77bcf86cd799439011"
    users_collection = FakeUsersCollection(
        {
            "_id": planner_id,
            "email": "planner@example.com",
            "is_active": False,
            "subscription_status": "active",
        }
    )
    restore_mock = AsyncMock(return_value={"errors": []})
    suspend_mock = AsyncMock()

    monkeypatch.setattr(
        saas_config_module.mongo, "get_users_collection", lambda: users_collection
    )
    monkeypatch.setattr(
        saas_config_module.planner_access_lifecycle_service,
        "restore_planner_access",
        restore_mock,
    )
    monkeypatch.setattr(
        saas_config_module.planner_access_lifecycle_service,
        "suspend_planner_access",
        suspend_mock,
    )

    result = asyncio.run(
        saas_config_module.toggle_planner_status(
            planner_id,
            current_user=SimpleNamespace(email="root@example.com"),
        )
    )

    assert result["new_status"] is True
    assert result["lifecycle_sync"] == {"errors": []}
    assert users_collection.updates[0]["update"]["$set"]["is_active"] is True
    restore_mock.assert_awaited_once_with(
        planner_id=planner_id,
        planner_email="planner@example.com",
    )
    suspend_mock.assert_not_called()


def test_toggle_planner_status_suspends_lifecycle_when_deactivating(monkeypatch):
    planner_id = "507f1f77bcf86cd799439011"
    users_collection = FakeUsersCollection(
        {
            "_id": planner_id,
            "email": "planner@example.com",
            "is_active": True,
            "subscription_status": "active",
        }
    )
    restore_mock = AsyncMock()
    suspend_mock = AsyncMock(return_value={"errors": []})

    monkeypatch.setattr(
        saas_config_module.mongo, "get_users_collection", lambda: users_collection
    )
    monkeypatch.setattr(
        saas_config_module.planner_access_lifecycle_service,
        "restore_planner_access",
        restore_mock,
    )
    monkeypatch.setattr(
        saas_config_module.planner_access_lifecycle_service,
        "suspend_planner_access",
        suspend_mock,
    )

    result = asyncio.run(
        saas_config_module.toggle_planner_status(
            planner_id,
            current_user=SimpleNamespace(email="root@example.com"),
        )
    )

    assert result["new_status"] is False
    assert result["lifecycle_sync"] == {"errors": []}
    assert users_collection.updates[0]["update"]["$set"]["is_active"] is False
    suspend_mock.assert_awaited_once_with(
        planner_id=planner_id,
        planner_email="planner@example.com",
        team_reason="root_admin_deactivated",
    )
    restore_mock.assert_not_called()


def test_toggle_planner_status_skips_restore_when_subscription_is_still_blocked(
    monkeypatch,
):
    planner_id = "507f1f77bcf86cd799439011"
    users_collection = FakeUsersCollection(
        {
            "_id": planner_id,
            "email": "planner@example.com",
            "is_active": False,
            "subscription_status": "cancelled",
        }
    )
    restore_mock = AsyncMock()
    suspend_mock = AsyncMock()

    monkeypatch.setattr(
        saas_config_module.mongo, "get_users_collection", lambda: users_collection
    )
    monkeypatch.setattr(
        saas_config_module.planner_access_lifecycle_service,
        "restore_planner_access",
        restore_mock,
    )
    monkeypatch.setattr(
        saas_config_module.planner_access_lifecycle_service,
        "suspend_planner_access",
        suspend_mock,
    )

    result = asyncio.run(
        saas_config_module.toggle_planner_status(
            planner_id,
            current_user=SimpleNamespace(email="root@example.com"),
        )
    )

    assert result["new_status"] is True
    assert result["lifecycle_sync"]["skipped"] is True
    assert result["lifecycle_sync"]["reason"] == "planner_subscription_not_restored"
    restore_mock.assert_not_called()
    suspend_mock.assert_not_called()
