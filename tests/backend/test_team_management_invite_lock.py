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


class FakeCursor:
    def __init__(self, docs: list[dict]):
        self.docs = deepcopy(docs)

    async def to_list(self, length: int | None = None):
        if length is None:
            return deepcopy(self.docs)
        return deepcopy(self.docs[:length])


class FakeWeddingsCollection:
    def __init__(self, docs: list[dict]):
        self.docs = deepcopy(docs)

    async def count_documents(self, query):
        expected_ids = set(query["_id"]["$in"])
        owner_id = query.get("assigned_planner_id")
        owner_email = query.get("assigned_planner_email")
        count = 0
        for doc in self.docs:
            if doc["_id"] not in expected_ids:
                continue
            if owner_id is not None and doc.get("assigned_planner_id") != owner_id:
                continue
            if (
                owner_email is not None
                and doc.get("assigned_planner_email") != owner_email
            ):
                continue
            count += 1
        return count

    def find(self, query, _projection):
        expected_ids = set(query["_id"]["$in"])
        owner_id = query.get("assigned_planner_id")
        owner_email = query.get("assigned_planner_email")
        docs = []
        for doc in self.docs:
            if doc["_id"] not in expected_ids:
                continue
            if owner_id is not None and doc.get("assigned_planner_id") != owner_id:
                continue
            if (
                owner_email is not None
                and doc.get("assigned_planner_email") != owner_email
            ):
                continue
            docs.append({"_id": doc["_id"]})
        return FakeCursor(docs)


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
        raise HTTPException(
            status_code=400, detail="Password must contain at least one number"
        )

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


@pytest.mark.asyncio
async def test_validate_wedding_ownership_accepts_string_wedding_ids():
    service = object.__new__(TeamManagementService)
    service.weddings_collection = FakeWeddingsCollection(
        [
            {
                "_id": "wedding_alpha",
                "assigned_planner_id": "planner_123",
                "assigned_planner_email": "planner@example.com",
            }
        ]
    )

    await service._validate_wedding_ownership(
        owner_id="planner_123",
        owner_email="planner@example.com",
        wedding_ids=["wedding_alpha"],
    )


@pytest.mark.asyncio
async def test_validate_wedding_ownership_rejects_unknown_string_wedding_ids():
    service = object.__new__(TeamManagementService)
    service.weddings_collection = FakeWeddingsCollection(
        [
            {
                "_id": "wedding_alpha",
                "assigned_planner_id": "planner_123",
                "assigned_planner_email": "planner@example.com",
            }
        ]
    )

    with pytest.raises(HTTPException) as exc_info:
        await service._validate_wedding_ownership(
            owner_id="planner_123",
            owner_email="planner@example.com",
            wedding_ids=["wedding_missing"],
        )

    assert exc_info.value.status_code == 400
    assert "wedding_missing" in exc_info.value.detail
