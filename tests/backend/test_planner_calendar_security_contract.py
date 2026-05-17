from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from bson import ObjectId
from fastapi import HTTPException

from app.api import planner_calendar as planner_calendar_api
from app.dependencies.auth_extended import ExtendedAuthUser
from app.models.calendar import CalendarEventCreate, CalendarEventUpdate


class _TaskCursor:
    def __init__(self, docs: list[dict]) -> None:
        self.docs = docs

    def sort(self, *args, **kwargs) -> "_TaskCursor":
        return self

    def limit(self, *args, **kwargs) -> "_TaskCursor":
        return self

    async def to_list(self, length: int | None = None) -> list[dict]:
        return self.docs[:length] if length is not None else self.docs


class _TaskCollection:
    def __init__(self, docs: list[dict]) -> None:
        self.docs = docs

    def find(self, query: dict) -> _TaskCursor:
        return _TaskCursor(self.docs)


def _team_user() -> ExtendedAuthUser:
    user = ExtendedAuthUser(
        "team@example.com",
        "team_member",
        {"_id": "team-1", "parent_planner_id": "owner-1"},
    )
    user.team_owner_email = "owner@example.com"
    user.team_permissions = {
        "manage_calendar_tasks": True,
        "connect_personal_calendar": True,
    }
    user.team_wedding_access = "assigned"
    user.team_assigned_wedding_ids = ["allowed-wedding"]
    return user


@pytest.mark.asyncio
async def test_create_task_rejects_inaccessible_wedding_before_insert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    insert_one = AsyncMock(side_effect=AssertionError("insert must not run"))
    monkeypatch.setattr(
        planner_calendar_api,
        "mongo",
        SimpleNamespace(
            get_planner_tasks_collection=lambda: SimpleNamespace(insert_one=insert_one)
        ),
    )
    monkeypatch.setattr(
        planner_calendar_api,
        "check_wedding_access",
        AsyncMock(return_value=False),
    )

    with pytest.raises(HTTPException) as exc_info:
        await planner_calendar_api.create_task(
            CalendarEventCreate(
                wedding_id="forbidden-wedding",
                title="Blocked task",
                start_date=datetime(2026, 5, 17, 14, 0, tzinfo=UTC),
            ),
            current_user=_team_user(),
        )

    assert exc_info.value.status_code == 403
    insert_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_task_rejects_inaccessible_wedding_before_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task_id = ObjectId()
    update_one = AsyncMock(side_effect=AssertionError("update must not run"))
    task_doc = {
        "_id": task_id,
        "planner_email": "owner@example.com",
        "owner_planner_id": "owner-1",
        "owner_planner_email": "owner@example.com",
        "created_by_user_id": "team-1",
        "created_by_email": "team@example.com",
        "wedding_id": "allowed-wedding",
        "title": "Existing task",
        "status": "pending",
        "schedule_item_type": "task",
    }
    monkeypatch.setattr(
        planner_calendar_api,
        "mongo",
        SimpleNamespace(
            get_planner_tasks_collection=lambda: SimpleNamespace(
                find_one=AsyncMock(return_value=task_doc),
                update_one=update_one,
            )
        ),
    )
    monkeypatch.setattr(
        planner_calendar_api,
        "check_wedding_access",
        AsyncMock(return_value=False),
    )

    with pytest.raises(HTTPException) as exc_info:
        await planner_calendar_api.update_task(
            str(task_id),
            CalendarEventUpdate(wedding_id="forbidden-wedding"),
            current_user=_team_user(),
        )

    assert exc_info.value.status_code == 403
    update_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_tasklists_require_connection_owner_or_manage_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection_doc = {
        "_id": ObjectId(),
        "owner_planner_id": "owner-1",
        "owner_planner_email": "owner@example.com",
        "user_id": "other-team-user",
        "user_email": "other@example.com",
        "aurinko_account_id": "acct-1",
    }
    fake_provider = SimpleNamespace(
        get_connection_doc=AsyncMock(return_value=connection_doc),
        _account_token_for_connection=AsyncMock(
            side_effect=AssertionError("provider token must not be used")
        ),
    )
    monkeypatch.setattr(
        planner_calendar_api, "calendar_provider_service", fake_provider
    )

    user = _team_user()
    user.team_permissions = {"manage_calendar_connections": False}

    with pytest.raises(HTTPException) as exc_info:
        await planner_calendar_api.list_connection_tasklists(
            str(connection_doc["_id"]),
            current_user=user,
        )

    assert exc_info.value.status_code == 403
    fake_provider._account_token_for_connection.assert_not_awaited()


@pytest.mark.asyncio
async def test_legacy_google_status_is_owner_scoped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    status = AsyncMock(
        return_value={
            "connected": False,
            "calendar_id": None,
            "last_sync": None,
            "sync_enabled": False,
            "events_synced": 0,
        }
    )
    monkeypatch.setattr(
        planner_calendar_api.google_calendar_service,
        "get_connection_status",
        status,
    )

    await planner_calendar_api.get_google_calendar_status(current_user=_team_user())

    assert status.await_args.kwargs["owner_planner_id"] == "owner-1"


@pytest.mark.asyncio
async def test_legacy_google_disconnect_is_owner_scoped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    disconnect = AsyncMock(return_value={"disconnected": True})
    monkeypatch.setattr(
        planner_calendar_api.google_calendar_service,
        "disconnect",
        disconnect,
    )

    await planner_calendar_api.disconnect_google_calendar(current_user=_team_user())

    assert disconnect.await_args.kwargs["owner_planner_id"] == "owner-1"


@pytest.mark.asyncio
async def test_month_and_upcoming_routes_do_not_hydrate_inaccessible_wedding_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task_doc = {
        "_id": ObjectId(),
        "planner_email": "owner@example.com",
        "owner_planner_id": "owner-1",
        "owner_planner_email": "owner@example.com",
        "created_by_user_id": "team-1",
        "created_by_email": "team@example.com",
        "wedding_id": "forbidden-wedding",
        "title": "Scoped task with stale wedding reference",
        "status": "pending",
        "start_date": datetime(2026, 5, 17, 14, 0, tzinfo=UTC),
        "end_date": datetime(2026, 5, 17, 15, 0, tzinfo=UTC),
        "schedule_item_type": "task",
        "visibility_mode": "details",
    }
    wedding_lookup = AsyncMock(side_effect=AssertionError("wedding lookup blocked"))
    monkeypatch.setattr(
        planner_calendar_api,
        "mongo",
        SimpleNamespace(
            get_planner_tasks_collection=lambda: _TaskCollection([task_doc]),
            get_weddings_collection=lambda: SimpleNamespace(find_one=wedding_lookup),
        ),
    )
    monkeypatch.setattr(
        planner_calendar_api,
        "check_wedding_access",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        planner_calendar_api,
        "_load_task_sync_summary_map",
        AsyncMock(return_value={}),
    )

    month_rows = await planner_calendar_api.get_month_tasks(
        2026,
        5,
        current_user=_team_user(),
    )
    upcoming_rows = await planner_calendar_api.get_upcoming_tasks(
        current_user=_team_user(),
        days=7,
        limit=20,
    )

    assert month_rows[0].wedding_name is None
    assert upcoming_rows[0].wedding_name is None
    wedding_lookup.assert_not_awaited()
