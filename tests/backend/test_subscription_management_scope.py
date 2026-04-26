from __future__ import annotations

import asyncio
import os
import sys
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("API_KEY", "test-api-key")

from app.api import subscription_management as subscription_management_api  # noqa: E402
from app.dependencies.auth_extended import ExtendedAuthUser  # noqa: E402


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _build_team_member(*, team_id: str = "team_1", owner_id: str = "planner_123"):
    return ExtendedAuthUser(
        email="team@example.com",
        role="team_member",
        user_data={
            "_id": team_id,
            "parent_planner_id": owner_id,
        },
    )


def test_team_member_can_check_owner_usage_limits(monkeypatch):
    fake_check = AsyncMock(
        return_value={"allowed": True, "current_usage": 2, "limit": 3}
    )
    monkeypatch.setattr(
        subscription_management_api.subscription_service,
        "check_usage_limits",
        fake_check,
    )

    current_user = _build_team_member()
    result = _run(
        subscription_management_api.check_usage_limits(
            user_id="planner_123",
            resource_type="weddings",
            amount=1,
            current_user=current_user,
        )
    )

    assert result["allowed"] is True
    assert result["current_usage"] == 2
    fake_check.assert_awaited_once_with("planner_123", "weddings", 1)


def test_team_member_can_fetch_owner_usage_stats(monkeypatch):
    fake_get = AsyncMock(return_value={"weddings_count": 4})
    monkeypatch.setattr(
        subscription_management_api.subscription_service, "get_usage_stats", fake_get
    )

    current_user = _build_team_member()
    result = _run(
        subscription_management_api.get_user_usage_stats(
            user_id="planner_123",
            current_user=current_user,
        )
    )

    assert result == {"weddings_count": 4}
    fake_get.assert_awaited_once_with("planner_123")


def test_team_member_cannot_read_unrelated_owner_usage(monkeypatch):
    fake_check = AsyncMock()
    monkeypatch.setattr(
        subscription_management_api.subscription_service,
        "check_usage_limits",
        fake_check,
    )

    current_user = _build_team_member(owner_id="planner_123")

    with pytest.raises(HTTPException) as exc_info:
        _run(
            subscription_management_api.check_usage_limits(
                user_id="planner_999",
                resource_type="weddings",
                amount=1,
                current_user=current_user,
            )
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Can only check your own limits"
    fake_check.assert_not_called()
