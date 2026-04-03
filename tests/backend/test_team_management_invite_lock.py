from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from bson import ObjectId
from fastapi import HTTPException

from app.models.team_member import TeamMemberStatus
from app.services.team_management_service import TeamManagementService


class FakeTeamCollection:
    def __init__(self, doc: dict):
        self.doc = deepcopy(doc)

    async def find_one_and_update(self, query, update, return_document=True):
        if self.doc.get("invite_token") != query.get("invite_token"):
            return None
        if self.doc.get("status") != query.get("status"):
            return None
        self._apply_update(update)
        return deepcopy(self.doc)

    async def find_one(self, query):
        for key, value in query.items():
            if self.doc.get(key) != value:
                return None
        return deepcopy(self.doc)

    async def update_one(self, query, update):
        for key, value in query.items():
            if self.doc.get(key) != value:
                return SimpleNamespace(modified_count=0)
        self._apply_update(update)
        return SimpleNamespace(modified_count=1)

    def _apply_update(self, update):
        for key, value in update.get("$set", {}).items():
            self.doc[key] = value
        for key in update.get("$unset", {}):
            self.doc.pop(key, None)


class FakeUsersCollection:
    def __init__(self):
        self.deleted_ids = []

    async def find_one(self, _query):
        return None

    async def delete_one(self, query):
        self.deleted_ids.append(query["_id"])
        return SimpleNamespace(deleted_count=1)


@pytest.mark.asyncio
async def test_accept_invite_restores_pending_status_when_validation_raises_http_error():
    now = datetime.now(timezone.utc)
    invite_doc = {
        "_id": ObjectId(),
        "owner_id": "planner_123",
        "owner_email": "planner@example.com",
        "email": "team@example.com",
        "role": "viewer",
        "status": TeamMemberStatus.PENDING.value,
        "invite_token": "invite-token",
        "invite_token_expires_at": now + timedelta(days=1),
        "updated_at": now,
    }

    service = object.__new__(TeamManagementService)
    service.team_collection = FakeTeamCollection(invite_doc)
    service.users_collection = FakeUsersCollection()

    def fail_password_validation(_password: str):
        raise HTTPException(status_code=400, detail="Password must contain at least one number")

    service._validate_password = fail_password_validation

    with pytest.raises(HTTPException) as exc_info:
        await service.accept_invite(
            token="invite-token",
            first_name="Taylor",
            last_name="Planner",
            password="BadPassword!",
        )

    assert exc_info.value.status_code == 400
    assert service.team_collection.doc["status"] == TeamMemberStatus.PENDING.value
    assert service.team_collection.doc["invite_token"] == "invite-token"
