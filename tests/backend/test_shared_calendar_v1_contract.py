from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import ANY, AsyncMock

import jwt
import pytest
from fastapi import HTTPException

from app.api import planner_calendar as planner_calendar_api
from app.api.planner_calendar import (
    _build_scoped_meeting_query,
    _coerce_event_datetime,
    _connection_matches_owner_scope,
)
from app.core import database_indexes as database_indexes_module
from app.dependencies.auth_extended import (
    ExtendedAuthUser,
    require_calendar_permission,
    resolve_owner_scoped_user_assignments,
)
from app.models.calendar import CalendarEventCreate, CalendarEventUpdate
from app.models.team_member import ROLE_PRESETS, resolve_team_permissions
from app.services.calendar_aggregation_service import CalendarAggregationService
from app.services.calendar_sync_service import CalendarSyncService
from app.services.google_calendar_service import (
    GoogleCalendarService,
    google_calendar_service,
)
from app.services.meeting_invite_service import MeetingInviteService


class _FakeCursor:
    def __init__(self, rows: list[dict]):
        self.rows = rows

    def sort(self, *_args, **_kwargs):
        return self

    async def to_list(self, length: int | None = None) -> list[dict]:
        if length is None:
            return list(self.rows)
        return list(self.rows[:length])

    def __aiter__(self):
        self._iter = iter(self.rows)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


class _FakeTasksCollection:
    def __init__(self, rows: list[dict]):
        self.rows = rows

    def find(self, _query: dict):
        return _FakeCursor(self.rows)


class _RecordingCollection:
    def __init__(self, *, count: int = 1, find_one_result: dict | None = None):
        self.count = count
        self.find_one_result = find_one_result
        self.update_many_calls: list[tuple[dict, dict]] = []
        self.delete_one_calls: list[dict] = []
        self.update_one_calls: list[tuple[dict, dict]] = []
        self.delete_many_calls: list[dict] = []
        self.create_index_calls: list[tuple[list[tuple[str, int]], dict[str, Any]]] = []
        self.aggregate_rows: list[dict[str, Any]] = []

    async def count_documents(self, _query: dict) -> int:
        return self.count

    async def update_many(self, query: dict, update: dict) -> None:
        self.update_many_calls.append((query, update))

    async def delete_one(self, query: dict) -> None:
        self.delete_one_calls.append(query)

    async def find_one(self, _query: dict) -> dict | None:
        return self.find_one_result

    async def update_one(self, query: dict, update: dict) -> None:
        self.update_one_calls.append((query, update))

    async def delete_many(self, query: dict) -> None:
        self.delete_many_calls.append(query)

    async def create_index(self, keys: list[tuple[str, int]], **kwargs: Any) -> str:
        self.create_index_calls.append((keys, kwargs))
        return kwargs.get("name", "idx")

    def aggregate(self, _pipeline: list[dict[str, Any]]) -> _FakeCursor:
        return _FakeCursor(self.aggregate_rows)


def test_google_oauth_state_round_trip_and_token_encryption() -> None:
    state = google_calendar_service._build_state(
        user_id="user-1",
        user_email="planner@example.com",
        owner_id="owner-1",
        owner_email="owner@example.com",
    )

    assert state != "planner@example.com"

    payload = google_calendar_service._decode_state(state)
    assert payload["sub"] == "user-1"
    assert payload["user_email"] == "planner@example.com"
    assert payload["owner_id"] == "owner-1"

    encrypted = google_calendar_service._encrypt_token("refresh-token-value")
    assert encrypted
    assert encrypted != "refresh-token-value"
    assert google_calendar_service._decrypt_token(encrypted) == "refresh-token-value"


def test_google_oauth_state_rejects_tampering() -> None:
    state = google_calendar_service._build_state(
        user_id="user-1",
        user_email="planner@example.com",
        owner_id="owner-1",
        owner_email="owner@example.com",
    )
    header, payload, signature = state.split(".")
    tampered_signature = f"{'a' if signature[0] != 'a' else 'b'}{signature[1:]}"
    tampered = ".".join((header, payload, tampered_signature))

    with pytest.raises(HTTPException) as exc_info:
        google_calendar_service._decode_state(tampered)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid OAuth state"


def test_google_oauth_state_rejects_expired_token() -> None:
    now = datetime.now(UTC)
    expired_state = jwt.encode(
        {
            "sub": "user-1",
            "user_email": "planner@example.com",
            "owner_id": "owner-1",
            "owner_email": "owner@example.com",
            "iat": int((now - timedelta(minutes=30)).timestamp()),
            "exp": int((now - timedelta(minutes=5)).timestamp()),
        },
        google_calendar_service._get_state_signing_key(),
        algorithm="HS256",
    )

    with pytest.raises(HTTPException) as exc_info:
        google_calendar_service._decode_state(expired_state)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "OAuth state has expired"


def test_editor_role_includes_generic_calendar_task_permissions() -> None:
    assert ROLE_PRESETS["editor"]["manage_calendar_tasks"] is True
    assert ROLE_PRESETS["editor"]["sync_calendar_tasks"] is True
    assert ROLE_PRESETS["viewer"]["manage_calendar_tasks"] is False
    assert ROLE_PRESETS["viewer"]["sync_calendar_tasks"] is False


def test_legacy_permission_blobs_inherit_generic_calendar_task_defaults() -> None:
    resolved = resolve_team_permissions("editor", {"manage_guests": True})

    assert resolved["manage_calendar_tasks"] is True
    assert resolved["sync_calendar_tasks"] is True


@pytest.mark.asyncio
async def test_manage_calendar_tasks_permission_requires_calendar_task_access() -> None:
    checker = require_calendar_permission("manage_calendar_tasks")
    user = ExtendedAuthUser("team@example.com", "team_member", {})
    user.team_permissions = {
        "view_shared_calendar": True,
        "manage_calendar_tasks": False,
    }

    with pytest.raises(HTTPException) as exc_info:
        await checker(current_user=user)

    assert exc_info.value.status_code == 403
    assert "manage calendar tasks" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_sync_calendar_tasks_permission_requires_calendar_task_access() -> None:
    checker = require_calendar_permission("sync_calendar_tasks")
    user = ExtendedAuthUser("team@example.com", "team_member", {})
    user.team_permissions = {
        "view_shared_calendar": True,
        "sync_calendar_tasks": False,
    }

    with pytest.raises(HTTPException) as exc_info:
        await checker(current_user=user)

    assert exc_info.value.status_code == 403
    assert "sync calendar tasks" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_calendar_indexes_make_meeting_invite_task_recipient_unique(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    planner_tasks = _RecordingCollection()
    calendar_connections = _RecordingCollection()
    calendar_event_syncs = _RecordingCollection()
    meeting_invites = _RecordingCollection()
    meeting_invites.aggregate_rows = [
        {
            "_id": {
                "task_id": "task-1",
                "recipient_email": "couple@example.com",
            },
            "ids": ["invite-2", "invite-1"],
            "count": 2,
        }
    ]

    fake_mongo = SimpleNamespace(
        get_planner_tasks_collection=lambda: planner_tasks,
        get_calendar_connections_collection=lambda: calendar_connections,
        get_calendar_event_syncs_collection=lambda: calendar_event_syncs,
        get_meeting_invites_collection=lambda: meeting_invites,
    )
    monkeypatch.setattr(database_indexes_module, "mongo", fake_mongo)

    await database_indexes_module.create_calendar_indexes()

    assert meeting_invites.delete_many_calls == [{"_id": {"$in": ["invite-1"]}}]
    assert [
        call
        for call in meeting_invites.create_index_calls
        if call[1].get("name") == "idx_meeting_invites_task_recipient"
    ][0][1]["unique"] is True


def test_google_service_requires_explicit_security_keys_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = GoogleCalendarService.__new__(GoogleCalendarService)
    monkeypatch.setattr("app.core.config.settings.ENVIRONMENT", "production")
    monkeypatch.setattr("app.core.config.settings.GOOGLE_CLIENT_ID", "client-id")
    monkeypatch.setattr(
        "app.core.config.settings.GOOGLE_CLIENT_SECRET", "client-secret"
    )
    monkeypatch.setattr("app.core.config.settings.GOOGLE_OAUTH_STATE_SIGNING_KEY", None)
    monkeypatch.setattr("app.core.config.settings.TOKEN_ENCRYPTION_KEY", None)

    with pytest.raises(RuntimeError) as exc_info:
        service._validate_security_configuration()

    assert "GOOGLE_OAUTH_STATE_SIGNING_KEY" in str(exc_info.value)
    assert "TOKEN_ENCRYPTION_KEY" in str(exc_info.value)


@pytest.mark.asyncio
async def test_sync_targets_prefer_explicit_allowed_override() -> None:
    service = CalendarSyncService.__new__(CalendarSyncService)
    allowed_connections = [
        {
            "_id": "assigned-default",
            "user_id": "staff-1",
            "is_default_write_target": True,
        },
        {"_id": "owner-default", "user_id": "owner-1", "is_default_write_target": True},
        {
            "_id": "explicit-choice",
            "user_id": "staff-1",
            "is_default_write_target": False,
        },
    ]

    async def fake_get_connection_docs(_query: dict) -> list[dict]:
        return allowed_connections

    setattr(service, "_get_connection_docs", fake_get_connection_docs)

    task = {
        "owner_planner_id": "owner-1",
        "assigned_user_ids": ["staff-1"],
        "calendar_sync_policy": "owner_and_assigned",
    }

    result = await service.resolve_sync_targets(
        task,
        explicit_connection_ids=["explicit-choice"],
        actor_is_owner=True,
    )

    assert [str(row["_id"]) for row in result] == ["explicit-choice"]


@pytest.mark.asyncio
async def test_sync_targets_fail_closed_when_explicit_override_is_not_allowed() -> None:
    service = CalendarSyncService.__new__(CalendarSyncService)

    async def fake_get_connection_docs(_query: dict) -> list[dict]:
        return [
            {
                "_id": "assigned-default",
                "user_id": "staff-1",
                "is_default_write_target": True,
            },
            {
                "_id": "owner-default",
                "user_id": "owner-1",
                "is_default_write_target": True,
            },
        ]

    setattr(service, "_get_connection_docs", fake_get_connection_docs)

    task = {
        "owner_planner_id": "owner-1",
        "assigned_user_ids": ["staff-1"],
        "calendar_sync_policy": "owner_and_assigned",
    }

    result = await service.resolve_sync_targets(
        task,
        explicit_connection_ids=["disallowed"],
        actor_is_owner=True,
    )

    assert result == []


@pytest.mark.asyncio
async def test_sync_targets_use_persisted_override_selection() -> None:
    service = CalendarSyncService.__new__(CalendarSyncService)

    async def fake_get_connection_docs(_query: dict) -> list[dict]:
        return [
            {
                "_id": "owner-default",
                "user_id": "owner-1",
                "is_default_write_target": True,
            },
            {
                "_id": "explicit-choice",
                "user_id": "staff-1",
                "is_default_write_target": False,
            },
        ]

    setattr(service, "_get_connection_docs", fake_get_connection_docs)

    task = {
        "owner_planner_id": "owner-1",
        "assigned_user_ids": ["staff-1"],
        "calendar_sync_policy": "owner_and_assigned",
        "sync_target_override_enabled": True,
        "sync_target_connection_ids": ["explicit-choice"],
    }

    result = await service.resolve_sync_targets(task, actor_is_owner=True)

    assert [str(row["_id"]) for row in result] == ["explicit-choice"]


@pytest.mark.asyncio
async def test_sync_targets_custom_policy_without_explicit_ids_stays_internal_only() -> (
    None
):
    service = CalendarSyncService.__new__(CalendarSyncService)

    async def fake_get_connection_docs(_query: dict) -> list[dict]:
        return [
            {
                "_id": "owner-default",
                "user_id": "owner-1",
                "is_default_write_target": True,
            },
            {
                "_id": "assigned-default",
                "user_id": "staff-1",
                "is_default_write_target": True,
            },
        ]

    setattr(service, "_get_connection_docs", fake_get_connection_docs)

    task = {
        "owner_planner_id": "owner-1",
        "assigned_user_ids": ["staff-1"],
        "calendar_sync_policy": "custom",
    }

    result = await service.resolve_sync_targets(task, actor_is_owner=True)

    assert result == []


@pytest.mark.asyncio
async def test_sync_targets_block_unlisted_staff_calendar_for_team_scheduler() -> None:
    service = CalendarSyncService.__new__(CalendarSyncService)

    async def fake_get_connection_docs(_query: dict) -> list[dict]:
        return [
            {
                "_id": "staff-2-default",
                "user_id": "staff-2",
                "owner_planner_id": "owner-1",
                "is_default_write_target": True,
            }
        ]

    setattr(service, "_get_connection_docs", fake_get_connection_docs)

    task = {
        "owner_planner_id": "owner-1",
        "assigned_user_ids": ["staff-2"],
        "calendar_sync_policy": "assigned_only",
    }

    result = await service.resolve_sync_targets(
        task,
        actor_user_id="staff-1",
        actor_is_owner=False,
    )

    assert result == []


@pytest.mark.asyncio
async def test_sync_targets_require_allowed_scheduler_role_when_configured() -> None:
    service = CalendarSyncService.__new__(CalendarSyncService)

    async def fake_get_connection_docs(_query: dict) -> list[dict]:
        return [
            {
                "_id": "staff-1-default",
                "user_id": "staff-1",
                "owner_planner_id": "owner-1",
                "is_default_write_target": True,
                "allowed_scheduler_roles": ["editor"],
            }
        ]

    setattr(service, "_get_connection_docs", fake_get_connection_docs)

    task = {
        "owner_planner_id": "owner-1",
        "assigned_user_ids": ["staff-1"],
        "calendar_sync_policy": "assigned_only",
    }

    blocked = await service.resolve_sync_targets(
        task,
        actor_user_id="staff-1",
        actor_is_owner=False,
        actor_role_scope="viewer",
    )
    allowed = await service.resolve_sync_targets(
        task,
        actor_user_id="staff-1",
        actor_is_owner=False,
        actor_role_scope="editor",
    )

    assert blocked == []
    assert [str(row["_id"]) for row in allowed] == ["staff-1-default"]


@pytest.mark.asyncio
async def test_sync_targets_block_disallowed_schedule_item_types() -> None:
    service = CalendarSyncService.__new__(CalendarSyncService)

    async def fake_get_connection_docs(_query: dict) -> list[dict]:
        return [
            {
                "_id": "owner-default",
                "user_id": "owner-1",
                "owner_planner_id": "owner-1",
                "is_default_write_target": True,
                "allowed_schedule_item_types": ["task"],
            }
        ]

    setattr(service, "_get_connection_docs", fake_get_connection_docs)

    task = {
        "_id": "meeting-1",
        "owner_planner_id": "owner-1",
        "category": "meeting",
        "schedule_item_type": "meeting",
        "calendar_sync_policy": "owner_only",
    }

    result = await service.resolve_sync_targets(task, actor_is_owner=True)

    assert result == []


@pytest.mark.asyncio
async def test_sync_targets_block_disallowed_wedding_scope() -> None:
    service = CalendarSyncService.__new__(CalendarSyncService)

    async def fake_get_connection_docs(_query: dict) -> list[dict]:
        return [
            {
                "_id": "owner-default",
                "user_id": "owner-1",
                "owner_planner_id": "owner-1",
                "is_default_write_target": True,
                "allowed_wedding_ids": ["wedding-1"],
            }
        ]

    setattr(service, "_get_connection_docs", fake_get_connection_docs)

    task = {
        "_id": "meeting-1",
        "owner_planner_id": "owner-1",
        "category": "meeting",
        "schedule_item_type": "meeting",
        "wedding_id": "wedding-2",
        "calendar_sync_policy": "owner_only",
    }

    result = await service.resolve_sync_targets(task, actor_is_owner=True)

    assert result == []


@pytest.mark.asyncio
async def test_sync_targets_fall_back_to_owner_default_when_staff_calendar_is_not_allowed() -> (
    None
):
    service = CalendarSyncService.__new__(CalendarSyncService)

    async def fake_get_connection_docs(_query: dict) -> list[dict]:
        return [
            {
                "_id": "staff-2-default",
                "user_id": "staff-2",
                "owner_planner_id": "owner-1",
                "is_default_write_target": True,
            },
            {
                "_id": "owner-default",
                "user_id": "owner-1",
                "owner_planner_id": "owner-1",
                "is_default_write_target": True,
            },
        ]

    setattr(service, "_get_connection_docs", fake_get_connection_docs)

    task = {
        "owner_planner_id": "owner-1",
        "assigned_user_ids": ["staff-2"],
        "calendar_sync_policy": "owner_and_assigned",
    }

    result = await service.resolve_sync_targets(
        task,
        actor_user_id="staff-1",
        actor_is_owner=False,
    )

    assert [str(row["_id"]) for row in result] == ["owner-default"]


@pytest.mark.asyncio
async def test_sync_targets_prefer_assigned_default_before_owner_default() -> None:
    service = CalendarSyncService.__new__(CalendarSyncService)

    async def fake_get_connection_docs(_query: dict) -> list[dict]:
        return [
            {
                "_id": "owner-default",
                "user_id": "owner-1",
                "is_default_write_target": True,
            },
            {
                "_id": "assigned-default",
                "user_id": "staff-1",
                "is_default_write_target": True,
            },
        ]

    setattr(service, "_get_connection_docs", fake_get_connection_docs)

    task = {
        "owner_planner_id": "owner-1",
        "assigned_user_ids": ["staff-1"],
        "calendar_sync_policy": "owner_and_assigned",
    }

    result = await service.resolve_sync_targets(task, actor_is_owner=True)

    assert [str(row["_id"]) for row in result] == ["assigned-default"]


@pytest.mark.asyncio
async def test_sync_targets_fall_back_to_owner_default_when_assigned_default_missing() -> (
    None
):
    service = CalendarSyncService.__new__(CalendarSyncService)

    async def fake_get_connection_docs(_query: dict) -> list[dict]:
        return [
            {
                "_id": "owner-default",
                "user_id": "owner-1",
                "is_default_write_target": True,
            },
            {
                "_id": "staff-secondary",
                "user_id": "staff-1",
                "is_default_write_target": False,
            },
        ]

    setattr(service, "_get_connection_docs", fake_get_connection_docs)

    task = {
        "owner_planner_id": "owner-1",
        "assigned_user_ids": ["staff-1"],
        "calendar_sync_policy": "owner_and_assigned",
    }

    result = await service.resolve_sync_targets(task, actor_is_owner=True)

    assert [str(row["_id"]) for row in result] == ["owner-default"]


def test_calendar_event_create_attaches_timezone_to_naive_datetimes() -> None:
    payload = CalendarEventCreate(
        title="Planning Call",
        description=None,
        start_date=datetime(2026, 4, 8, 9, 0, 0),
        end_date=datetime(2026, 4, 8, 10, 0, 0),
        reminder_minutes=None,
        color=None,
        timezone="America/Chicago",
        schedule_item_type="meeting",
    )

    assert payload.start_date.tzinfo is not None
    assert payload.end_date is not None
    assert payload.end_date.tzinfo is not None
    assert payload.start_date.utcoffset() == timedelta(hours=-5)


def test_calendar_event_create_rejects_google_attendee_delivery_mode() -> None:
    with pytest.raises(ValueError) as exc_info:
        CalendarEventCreate(
            title="Planning Call",
            description=None,
            start_date=datetime(2026, 4, 8, 9, 0, 0),
            end_date=datetime(2026, 4, 8, 10, 0, 0),
            reminder_minutes=None,
            color=None,
            timezone="America/Chicago",
            schedule_item_type="meeting",
            invite_delivery_mode="google_attendee",
        )

    assert "not available in v1" in str(exc_info.value)


@pytest.mark.asyncio
async def test_create_meeting_normalizes_owner_scope_for_team_members(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inserted_docs: list[dict[str, object]] = []
    sync_schedule_item = AsyncMock(return_value=[])

    class FakeTasksCollection:
        async def insert_one(self, document: dict[str, object]) -> SimpleNamespace:
            inserted_docs.append(document.copy())
            return SimpleNamespace(inserted_id="meeting-1")

        async def update_one(self, *_args: object, **_kwargs: object) -> None:
            return None

    fake_mongo = SimpleNamespace(
        get_planner_tasks_collection=lambda: FakeTasksCollection(),
    )

    monkeypatch.setattr(planner_calendar_api, "mongo", fake_mongo)
    monkeypatch.setattr(
        planner_calendar_api,
        "check_wedding_access",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        planner_calendar_api,
        "_resolve_couple_attendee_emails",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        planner_calendar_api.calendar_sync_service,
        "sync_schedule_item",
        sync_schedule_item,
    )
    monkeypatch.setattr(
        planner_calendar_api,
        "_begin_meeting_idempotency",
        AsyncMock(return_value=("test-key", None)),
    )
    monkeypatch.setattr(
        planner_calendar_api,
        "_complete_meeting_idempotency",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        planner_calendar_api,
        "_fail_meeting_idempotency",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        planner_calendar_api.calendar_audit_service,
        "log",
        AsyncMock(return_value=None),
    )

    current_user = ExtendedAuthUser(
        "team@example.com",
        "team_member",
        {"_id": "team-1", "parent_planner_id": "owner-1"},
    )
    current_user.team_permissions = {"schedule_meetings": True}
    current_user.team_owner_email = "owner@example.com"

    response = await planner_calendar_api.create_meeting(
        planner_calendar_api.CalendarEventCreate(
            wedding_id="wedding-1",
            title="Planning Call",
            description="Review checklist",
            start_date=datetime(2026, 4, 8, 12, 0, tzinfo=UTC),
            end_date=datetime(2026, 4, 8, 13, 0, tzinfo=UTC),
            reminder_minutes=None,
            color=None,
            timezone="UTC",
        ),
        idempotency_key="create-meeting-1",
        current_user=current_user,
    )

    assert inserted_docs
    assert inserted_docs[0]["planner_email"] == "owner@example.com"
    assert inserted_docs[0]["owner_planner_email"] == "owner@example.com"
    assert inserted_docs[0]["created_by_email"] == "team@example.com"
    assert inserted_docs[0]["external_sync_requested"] is True
    assert "google_event_id" not in inserted_docs[0]
    assert "synced_to_google" not in inserted_docs[0]
    assert "last_google_sync" not in inserted_docs[0]
    sync_schedule_item.assert_awaited_once()
    assert sync_schedule_item.await_args is not None
    assert sync_schedule_item.await_args.kwargs["actor_role_scope"] == "viewer"
    assert response.meeting["owner_planner_email"] == "owner@example.com"


@pytest.mark.asyncio
async def test_update_meeting_sends_updated_ics_for_material_email_ics_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_task = {
        "_id": "meeting-1",
        "owner_planner_id": "owner-1",
        "owner_planner_email": "owner@example.com",
        "planner_email": "owner@example.com",
        "wedding_id": "wedding-1",
        "title": "Planning Call",
        "description": "Original details",
        "start_date": datetime(2026, 4, 8, 12, 0, tzinfo=UTC),
        "end_date": datetime(2026, 4, 8, 13, 0, tzinfo=UTC),
        "timezone": "UTC",
        "version": 1,
        "invite_delivery_mode": "email_ics",
        "couple_attendee_emails": ["couple@example.com"],
    }
    updated_task = {
        **original_task,
        "start_date": datetime(2026, 4, 8, 14, 0, tzinfo=UTC),
        "end_date": datetime(2026, 4, 8, 15, 0, tzinfo=UTC),
        "updated_at": datetime.now(UTC),
        "version": 2,
    }

    class FakeTasksCollection:
        async def update_one(self, *_args: object, **_kwargs: object) -> Any:
            return SimpleNamespace(matched_count=1)

        async def find_one(self, _query: dict) -> dict[str, Any]:
            return updated_task

    monkeypatch.setattr(
        planner_calendar_api,
        "check_wedding_access",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        planner_calendar_api,
        "_get_scoped_meeting",
        AsyncMock(return_value=original_task),
    )
    monkeypatch.setattr(
        planner_calendar_api,
        "mongo",
        SimpleNamespace(get_planner_tasks_collection=lambda: FakeTasksCollection()),
    )
    sync_schedule_item = AsyncMock(return_value=[])
    monkeypatch.setattr(
        planner_calendar_api.calendar_sync_service,
        "sync_schedule_item",
        sync_schedule_item,
    )
    enqueue_invite_job = AsyncMock(return_value=[{"success": True, "status": "queued"}])
    monkeypatch.setattr(
        planner_calendar_api.calendar_job_service,
        "enqueue_invite_job",
        enqueue_invite_job,
    )
    monkeypatch.setattr(
        planner_calendar_api,
        "_begin_meeting_idempotency",
        AsyncMock(return_value=("test-key", None)),
    )
    monkeypatch.setattr(
        planner_calendar_api,
        "_complete_meeting_idempotency",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        planner_calendar_api,
        "_fail_meeting_idempotency",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        planner_calendar_api.calendar_audit_service,
        "log",
        AsyncMock(return_value=None),
    )

    current_user = ExtendedAuthUser(
        "owner@example.com",
        "wedding_planner",
        {"_id": "owner-1"},
    )

    response = await planner_calendar_api.update_meeting(
        "507f1f77bcf86cd799439011",
        cast(
            Any,
            CalendarEventUpdate.model_validate(
                {
                    "start_date": datetime(2026, 4, 8, 14, 0, tzinfo=UTC),
                    "end_date": datetime(2026, 4, 8, 15, 0, tzinfo=UTC),
                    "expected_version": 1,
                }
            ),
        ),
        idempotency_key="update-meeting-1",
        current_user=current_user,
    )

    enqueue_invite_job.assert_awaited_once_with(
        updated_task,
        method="REQUEST",
        reason="meeting_updated",
    )
    sync_schedule_item.assert_awaited_once()
    assert sync_schedule_item.await_args is not None
    assert sync_schedule_item.await_args.kwargs["actor_role_scope"] == "owner"
    assert response.invite_status == [{"success": True, "status": "queued"}]


@pytest.mark.asyncio
async def test_delete_meeting_sends_cancellation_ics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = {
        "_id": "meeting-1",
        "owner_planner_id": "owner-1",
        "owner_planner_email": "owner@example.com",
        "planner_email": "owner@example.com",
        "wedding_id": "wedding-1",
        "title": "Planning Call",
        "description": "Original details",
        "start_date": datetime(2026, 4, 8, 12, 0, tzinfo=UTC),
        "end_date": datetime(2026, 4, 8, 13, 0, tzinfo=UTC),
        "timezone": "UTC",
        "version": 1,
        "invite_delivery_mode": "email_ics",
        "couple_attendee_emails": ["couple@example.com"],
    }

    class FakeTasksCollection:
        def __init__(self) -> None:
            self.deleted_queries: list[dict[str, Any]] = []

        async def delete_one(self, query: dict[str, Any]) -> Any:
            self.deleted_queries.append(query)
            return SimpleNamespace(deleted_count=1)

    fake_tasks = FakeTasksCollection()

    monkeypatch.setattr(
        planner_calendar_api,
        "check_wedding_access",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        planner_calendar_api,
        "_get_scoped_meeting",
        AsyncMock(return_value=task),
    )
    monkeypatch.setattr(
        planner_calendar_api,
        "mongo",
        SimpleNamespace(get_planner_tasks_collection=lambda: fake_tasks),
    )
    delete_syncs = AsyncMock(return_value=None)
    enqueue_invite_job = AsyncMock(return_value=[{"success": True, "status": "queued"}])
    monkeypatch.setattr(
        planner_calendar_api.calendar_sync_service,
        "delete_schedule_item_syncs",
        delete_syncs,
    )
    monkeypatch.setattr(
        planner_calendar_api.calendar_job_service,
        "enqueue_invite_job",
        enqueue_invite_job,
    )
    monkeypatch.setattr(
        planner_calendar_api,
        "_begin_meeting_idempotency",
        AsyncMock(return_value=("test-key", None)),
    )
    monkeypatch.setattr(
        planner_calendar_api,
        "_complete_meeting_idempotency",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        planner_calendar_api,
        "_fail_meeting_idempotency",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        planner_calendar_api.calendar_audit_service,
        "log",
        AsyncMock(return_value=None),
    )

    current_user = ExtendedAuthUser(
        "owner@example.com",
        "wedding_planner",
        {"_id": "owner-1"},
    )

    result = await planner_calendar_api.delete_meeting(
        "507f1f77bcf86cd799439011",
        expected_version=1,
        idempotency_key="delete-meeting-1",
        current_user=current_user,
    )

    delete_syncs.assert_awaited_once_with("507f1f77bcf86cd799439011")
    enqueue_invite_job.assert_awaited_once()
    assert result["invite_status"] == [{"success": True, "status": "queued"}]


def test_connection_scope_requires_matching_owner_identity() -> None:
    planner = ExtendedAuthUser(
        email="owner@example.com",
        role="wedding_planner",
        user_data={"_id": "owner-1"},
    )
    assert _connection_matches_owner_scope(
        {
            "owner_planner_id": "owner-1",
            "owner_planner_email": "owner@example.com",
        },
        planner,
    )
    assert not _connection_matches_owner_scope(
        {
            "owner_planner_id": "other-owner",
            "owner_planner_email": "other@example.com",
        },
        planner,
    )


def test_date_only_events_are_coerced_to_aware_datetimes() -> None:
    coerced = _coerce_event_datetime("2026-04-08")

    assert coerced is not None
    assert coerced.tzinfo is not None
    assert coerced.isoformat() == "2026-04-08T00:00:00+00:00"


@pytest.mark.asyncio
async def test_owner_scoped_assignees_reject_out_of_scope_users(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeUsersCollection:
        async def find_one(
            self, query: dict, projection: dict | None = None
        ) -> dict | None:
            if query["_id"] == "staff-1":
                return {
                    "_id": "staff-1",
                    "email": "staff1@example.com",
                    "role": "team_member",
                    "parent_planner_id": "owner-1",
                    "is_active": True,
                }
            if query["_id"] == "outside-user":
                return {
                    "_id": "outside-user",
                    "email": "outside@example.com",
                    "role": "wedding_planner",
                    "parent_planner_id": None,
                    "is_active": True,
                }
            return None

    monkeypatch.setattr(
        "app.dependencies.auth_extended.mongo",
        type(
            "FakeMongo",
            (),
            {"get_users_collection": lambda self=None: FakeUsersCollection()},
        )(),
    )

    with pytest.raises(HTTPException) as exc_info:
        await resolve_owner_scoped_user_assignments(
            "owner-1",
            "owner@example.com",
            ["staff-1", "outside-user"],
        )

    assert exc_info.value.status_code == 400
    assert "planner business owner scope" in exc_info.value.detail.lower()


def test_scoped_meeting_query_enforces_owner_scope() -> None:
    planner = ExtendedAuthUser(
        email="owner@example.com",
        role="wedding_planner",
        user_data={"_id": "owner-1"},
    )

    query = _build_scoped_meeting_query(planner, cast(Any, "meeting-1"))

    assert query["$and"][0] == {"_id": "meeting-1"}
    assert query["$and"][1] == {
        "$or": [{"schedule_item_type": "meeting"}, {"category": "meeting"}]
    }
    assert query["$and"][2] == {
        "$or": [
            {"owner_planner_email": "owner@example.com"},
            {"planner_email": "owner@example.com"},
        ]
    }


def test_shared_calendar_query_intersects_requested_and_accessible_weddings() -> None:
    service = CalendarAggregationService.__new__(CalendarAggregationService)

    query = service._build_internal_query(
        owner_email="owner@example.com",
        wedding_ids=["wedding-2"],
        staff_ids=None,
        start=datetime(2026, 4, 8, 0, 0, tzinfo=UTC),
        end=datetime(2026, 4, 9, 0, 0, tzinfo=UTC),
        source_types=None,
        accessible_wedding_ids=["wedding-1"],
    )

    assert query["wedding_id"] == {"$in": []}


@pytest.mark.asyncio
async def test_disconnect_connection_orphans_sync_rows() -> None:
    service = GoogleCalendarService.__new__(GoogleCalendarService)
    cast(Any, service).connections_collection = _RecordingCollection(
        count=1, find_one_result=None
    )
    cast(Any, service).syncs_collection = _RecordingCollection()

    async def fake_get_connection_doc(_connection_id: str) -> dict:
        return {
            "_id": "mongo-connection-id",
            "user_id": "user-1",
            "user_email": "planner@example.com",
            "provider_account_email": "planner@example.com",
        }

    revoked: list[str] = []

    async def fake_revoke(_connection_doc: dict) -> None:
        revoked.append("revoked")

    setattr(service, "_get_connection_doc", fake_get_connection_doc)
    setattr(service, "_revoke_provider_account", fake_revoke)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        "app.services.google_calendar_service.calendar_audit_service.log",
        AsyncMock(return_value=None),
    )

    result = await service.disconnect_connection("connection-1")

    assert result["disconnected"] is True
    assert service.syncs_collection.update_many_calls == [
        (
            {"calendar_connection_id": "connection-1"},
            {
                "$set": {
                    "sync_status": "orphaned",
                    "last_error": "Calendar connection disconnected",
                    "last_error_category": "connection_disconnected",
                    "retryable_error": False,
                    "next_retry_at": None,
                    "updated_at": ANY,
                },
                "$unset": {
                    "calendar_connection_id": "",
                    "calendar_id": "",
                },
            },
        )
    ]
    assert revoked == ["revoked"]
    monkeypatch.undo()


@pytest.mark.asyncio
async def test_update_connection_rejects_non_writable_default_target() -> None:
    service = GoogleCalendarService.__new__(GoogleCalendarService)
    cast(Any, service).connections_collection = _RecordingCollection()

    async def fake_get_connection_doc(_connection_id: str) -> dict:
        return {
            "_id": "mongo-connection-id",
            "user_id": "staff-1",
            "provider_account_email": "staff1@example.com",
            "is_writable": False,
            "sync_enabled": True,
        }

    setattr(service, "_get_connection_doc", fake_get_connection_doc)

    with pytest.raises(HTTPException) as exc_info:
        await service.update_connection(
            "connection-1",
            {"is_default_write_target": True},
        )

    assert exc_info.value.status_code == 400
    assert "writable" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_delete_schedule_item_syncs_preserves_rows_when_provider_delete_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = CalendarSyncService.__new__(CalendarSyncService)

    class FakeSyncCollection:
        def __init__(self) -> None:
            self.delete_many_calls: list[dict] = []
            self.update_one_calls: list[tuple[dict, dict]] = []

        def find(self, _query: dict) -> _FakeCursor:
            return _FakeCursor(
                [
                    {
                        "_id": "sync-1",
                        "calendar_connection_id": "connection-1",
                        "external_event_id": "event-1",
                    }
                ]
            )

        async def delete_many(self, query: dict) -> None:
            self.delete_many_calls.append(query)

        async def update_one(self, query: dict, update: dict, **_kwargs: Any) -> None:
            self.update_one_calls.append((query, update))

    fake_syncs = FakeSyncCollection()
    cast(Any, service).syncs_collection = fake_syncs

    async def fake_delete_google_event_for_connection(
        _connection_id: str, _external_event_id: str
    ) -> bool:
        return False

    monkeypatch.setattr(
        google_calendar_service,
        "delete_google_event_for_connection",
        fake_delete_google_event_for_connection,
    )
    with pytest.raises(HTTPException) as exc_info:
        await service.delete_schedule_item_syncs("task-1")

    assert exc_info.value.status_code == 502
    assert fake_syncs.delete_many_calls == []


@pytest.mark.asyncio
async def test_removed_target_cleanup_does_not_orphan_when_provider_delete_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = CalendarSyncService.__new__(CalendarSyncService)

    class FakeSyncCollection:
        def __init__(self) -> None:
            self.update_one_calls: list[tuple[dict, dict]] = []

        def find(self, _query: dict) -> _FakeCursor:
            return _FakeCursor(
                [
                    {
                        "_id": "sync-1",
                        "task_id": "task-1",
                        "calendar_connection_id": "connection-1",
                        "external_event_id": "event-1",
                    }
                ]
            )

        async def update_one(self, query: dict, update: dict, **_kwargs: Any) -> None:
            self.update_one_calls.append((query, update))

        async def delete_many(self, _query: dict) -> None:
            return None

    fake_syncs = FakeSyncCollection()
    cast(Any, service).syncs_collection = fake_syncs

    monkeypatch.setattr(
        service,
        "resolve_sync_targets",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        service,
        "get_sync_status",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        google_calendar_service,
        "delete_google_event_for_connection",
        AsyncMock(return_value=False),
    )

    await service.sync_schedule_item({"_id": "task-1", "owner_planner_id": "owner-1"})

    assert fake_syncs.update_one_calls[0][1]["$set"]["sync_status"] == "failed"
    assert fake_syncs.update_one_calls[0][1]["$set"]["last_error"] == (
        "Failed to remove provider event for deselected calendar"
    )


def test_meeting_invite_ics_uid_is_stable_for_same_task() -> None:
    service = MeetingInviteService.__new__(MeetingInviteService)
    task = {
        "_id": "meeting-1",
        "title": "Planning Call",
        "start_date": datetime(2026, 4, 8, 9, 0, tzinfo=UTC),
        "end_date": datetime(2026, 4, 8, 10, 0, tzinfo=UTC),
        "updated_at": datetime(2026, 4, 7, 18, 0, tzinfo=UTC),
    }

    first = service._build_ics_attachment(task, None)
    second = service._build_ics_attachment(task, None)

    assert first["uid"] == "meeting-1@thespecialwedding.io"
    assert second["uid"] == first["uid"]


@pytest.mark.asyncio
async def test_shared_calendar_view_filters_external_connections_by_staff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = CalendarAggregationService.__new__(CalendarAggregationService)
    cast(Any, service).tasks_collection = _FakeTasksCollection([])

    async def fake_list_connections(**_kwargs) -> list[dict]:
        return [
            {
                "id": "conn-owner",
                "user_id": "owner-1",
                "user_email": "owner@example.com",
                "owner_planner_email": "owner@example.com",
                "calendar_name": "Owner Calendar",
                "provider_account_email": "owner@example.com",
                "is_shared_in_team_view": True,
                "details_visibility": "details",
            },
            {
                "id": "conn-staff-1",
                "user_id": "staff-1",
                "user_email": "staff1@example.com",
                "owner_planner_email": "owner@example.com",
                "calendar_name": "Staff Calendar",
                "provider_account_email": "staff1@example.com",
                "is_shared_in_team_view": True,
                "details_visibility": "details",
            },
        ]

    async def fake_fetch_google_events_for_connection(
        connection_id: str, **_kwargs
    ) -> list[dict]:
        return [
            {
                "id": connection_id,
                "summary": connection_id,
                "start": {"dateTime": "2026-04-08T10:00:00+00:00"},
                "end": {"dateTime": "2026-04-08T11:00:00+00:00"},
            }
        ]

    monkeypatch.setattr(
        google_calendar_service,
        "list_connections",
        fake_list_connections,
    )
    monkeypatch.setattr(
        google_calendar_service,
        "fetch_google_events_for_connection",
        fake_fetch_google_events_for_connection,
    )

    events = await service.build_shared_view(
        owner_id="owner-1",
        owner_email="owner@example.com",
        current_user_id="owner-1",
        include_all_owner_connections=True,
        can_view_details=True,
        accessible_wedding_ids=None,
        start=datetime(2026, 4, 8, 0, 0, tzinfo=UTC),
        end=datetime(2026, 4, 9, 0, 0, tzinfo=UTC),
        staff_ids=["staff-1"],
    )

    external_events = [
        event for event in events if event["source_type"] == "external_google"
    ]
    assert [event["id"] for event in external_events] == ["conn-staff-1"]
