from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.api import couple_invite as couple_invite_api
from app.api import couple_portal as couple_portal_api
from app.api import team_management as team_management_api
from app.dependencies.auth_extended import ExtendedAuthUser
from app.models.team_member import ROLE_PRESETS, resolve_team_permissions


@pytest.mark.asyncio
async def test_list_couples_requires_manage_couple_portal_permission() -> None:
    user = ExtendedAuthUser("team@example.com", "team_member", {})
    user.team_permissions = {"manage_couple_portal": False}

    with pytest.raises(HTTPException) as exc_info:
        await couple_invite_api.list_couples(current_user=user)

    assert exc_info.value.status_code == 403
    assert "manage couple portal" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_planner_conversations_require_message_couples_permission() -> None:
    user = ExtendedAuthUser("team@example.com", "team_member", {})
    user.team_permissions = {"message_couples": False}

    with pytest.raises(HTTPException) as exc_info:
        await couple_portal_api.planner_list_conversations(current_user=user)

    assert exc_info.value.status_code == 403
    assert "message couples" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_owner_permission_payload_includes_new_couple_permissions() -> None:
    user = ExtendedAuthUser("planner@example.com", "wedding_planner", {"_id": "owner-1"})

    result = await team_management_api.get_my_permissions(current_user=user)

    assert result["permissions"]["manage_couple_portal"] is True
    assert result["permissions"]["message_couples"] is True


@pytest.mark.asyncio
async def test_message_broadcast_recipients_only_include_message_capable_team_members(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeWeddingsCollection:
        async def find_one(self, query, projection=None):
            assert query == {"_id": "wedding-1"}
            return {
                "_id": "wedding-1",
                "assigned_planner_id": "owner-1",
                "assigned_planner_email": "owner@example.com",
            }

    class FakeCursor:
        def __init__(self, docs):
            self._docs = iter(docs)

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self._docs)
            except StopIteration as exc:
                raise StopAsyncIteration from exc

    class FakeTeamMembersCollection:
        def find(self, query, projection=None):
            assert query["status"] == "active"
            assert query["custom_permissions.message_couples"] is True
            return FakeCursor(
                [
                    {
                        "email": "messenger@example.com",
                        "wedding_access": "assigned",
                        "assigned_wedding_ids": ["wedding-1"],
                    }
                ]
            )

    fake_mongo = SimpleNamespace(
        get_weddings_collection=lambda: FakeWeddingsCollection(),
        db={"team_members": FakeTeamMembersCollection()},
    )

    monkeypatch.setattr(couple_portal_api, "mongo", fake_mongo)

    recipients = await couple_portal_api._get_message_broadcast_recipients("wedding-1")

    assert recipients == {"owner@example.com", "messenger@example.com"}


def test_editor_role_preserves_couple_portal_management_but_not_messaging() -> None:
    assert ROLE_PRESETS["editor"]["manage_couple_portal"] is True
    assert ROLE_PRESETS["editor"]["message_couples"] is False


def test_legacy_permission_blobs_inherit_new_role_defaults() -> None:
    resolved = resolve_team_permissions("editor", {"manage_guests": True})

    assert resolved["manage_guests"] is True
    assert resolved["manage_couple_portal"] is True
    assert resolved["message_couples"] is False


@pytest.mark.asyncio
async def test_couple_meetings_are_scoped_by_wedding_not_planner_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_query: dict[str, object] = {}

    class FakeCursor:
        def __init__(self, docs):
            self._docs = iter(docs)

        def sort(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self._docs)
            except StopIteration as exc:
                raise StopAsyncIteration from exc

    class FakeTasksCollection:
        def find(self, query):
            captured_query.update(query)
            return FakeCursor(
                [
                    {
                        "_id": "meeting-1",
                        "title": "Planning Call",
                        "description": "Review checklist",
                        "start_date": None,
                        "end_date": None,
                        "is_recurring": False,
                        "status": "pending",
                    }
                ]
            )

    fake_mongo = SimpleNamespace(
        get_planner_tasks_collection=lambda: FakeTasksCollection(),
    )

    monkeypatch.setattr(couple_portal_api, "mongo", fake_mongo)

    result = await couple_portal_api.list_meetings_couple(
        couple={"wedding_id": "wedding-1", "wedding_archived": False}
    )

    assert captured_query["wedding_id"] == "wedding-1"
    assert captured_query["category"] == "meeting"
    assert "planner_email" not in captured_query
    assert result["count"] == 1


@pytest.mark.asyncio
async def test_save_form_template_uses_owner_scope_for_team_members(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inserted_docs: list[dict[str, object]] = []

    class FakeFormsCollection:
        async def find_one(self, query):
            assert query == {"_id": couple_portal_api.ObjectId("507f1f77bcf86cd799439011")}
            return {
                "_id": "form-1",
                "created_by": "owner@example.com",
                "wedding_id": "wedding-1",
                "fields": [{"id": "field-1"}],
                "settings": {"title": "Questionnaire", "wedding_id": "wedding-1"},
            }

    class FakeCursor:
        def __init__(self, docs):
            self._docs = docs

        async def to_list(self, length=None):
            return list(self._docs)

    class FakeTeamMembersCollection:
        def find(self, query, projection=None):
            assert query["$or"][0]["owner_id"] == "owner-1"
            return FakeCursor([{"email": "team@example.com"}])

    class FakeTemplatesCollection:
        async def update_many(self, *_args, **_kwargs):
            return SimpleNamespace(modified_count=0)

        async def insert_one(self, document):
            inserted_docs.append(document.copy())
            return SimpleNamespace(inserted_id="template-1")

    fake_mongo = SimpleNamespace(
        db={
            "forms": FakeFormsCollection(),
            "team_members": FakeTeamMembersCollection(),
            "custom_form_templates": FakeTemplatesCollection(),
        }
    )

    monkeypatch.setattr(couple_portal_api, "mongo", fake_mongo)
    monkeypatch.setattr(couple_portal_api, "check_wedding_access", AsyncMock(return_value=True))

    current_user = ExtendedAuthUser("team@example.com", "team_member", {})
    current_user.team_permissions = {"manage_couple_portal": True}
    current_user.team_owner_email = "owner@example.com"
    current_user.parent_planner_id = "owner-1"

    await couple_portal_api.save_form_as_template(
        couple_portal_api.SaveAsTemplateRequest(
            form_id="507f1f77bcf86cd799439011",
            template_name="Shared Questionnaire",
            description=None,
            category=None,
        ),
        current_user=current_user,
    )

    assert inserted_docs
    assert inserted_docs[0]["planner_email"] == "owner@example.com"
    assert inserted_docs[0]["created_by_email"] == "team@example.com"


@pytest.mark.asyncio
async def test_list_custom_templates_migrates_legacy_team_scoped_templates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    template_id = couple_portal_api.ObjectId("507f1f77bcf86cd799439099")
    docs = [
        {
            "_id": template_id,
            "planner_email": "team@example.com",
            "name": "Legacy Template",
            "description": "Created before owner normalization",
            "category": "questionnaire",
            "fields": [{"id": "field-1"}],
            "created_at": datetime.now(timezone.utc),
        }
    ]
    migration_calls: list[tuple[dict[str, object], dict[str, object]]] = []

    class FakeCursor:
        def __init__(self, rows):
            self._rows = rows

        def sort(self, *_args, **_kwargs):
            return self

        def __aiter__(self):
            self._iter = iter(self._rows)
            return self

        async def __anext__(self):
            try:
                return next(self._iter)
            except StopIteration as exc:
                raise StopAsyncIteration from exc

        async def to_list(self, length=None):
            return list(self._rows)

    class FakeTeamMembersCollection:
        def find(self, query, projection=None):
            assert query["$or"][0]["owner_id"] == "owner-1"
            return FakeCursor([{"email": "team@example.com"}])

    class FakeTemplatesCollection:
        async def update_many(self, query, update):
            migration_calls.append((query, update))
            target_emails = set(query["planner_email"]["$in"])
            for doc in docs:
                if doc["planner_email"] in target_emails:
                    doc["planner_email"] = update["$set"]["planner_email"]
            return SimpleNamespace(modified_count=1)

        def find(self, query):
            filtered = [
                doc.copy()
                for doc in docs
                if doc["planner_email"] == query["planner_email"]
            ]
            return FakeCursor(filtered)

    fake_mongo = SimpleNamespace(
        db={
            "team_members": FakeTeamMembersCollection(),
            "custom_form_templates": FakeTemplatesCollection(),
        }
    )

    monkeypatch.setattr(couple_portal_api, "mongo", fake_mongo)

    current_user = ExtendedAuthUser(
        "owner@example.com",
        "wedding_planner",
        {"_id": "owner-1"},
    )

    result = await couple_portal_api.list_custom_templates(current_user=current_user)

    assert migration_calls
    assert migration_calls[0][0] == {"planner_email": {"$in": ["team@example.com"]}}
    assert result["templates"][0]["name"] == "Legacy Template"
