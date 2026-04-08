from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import couple_invite as couple_invite_api
from app.api import couple_portal as couple_portal_api
from app.api import team_management as team_management_api
from app.dependencies.auth_extended import ExtendedAuthUser
from app.models.team_member import ROLE_PRESETS


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
