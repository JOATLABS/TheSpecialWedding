import asyncio
import os
import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, status

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import app.dependencies.auth_extended as auth_extended
import app.services.user_management_service as user_management_service_module


class DummyEmailService:
    configured = False


def _matches(document, query):
    for key, expected in query.items():
        actual = document.get(key)
        if isinstance(expected, dict):
            if "$gt" in expected and not (
                actual is not None and actual > expected["$gt"]
            ):
                return False
            if "$exists" in expected and ((key in document) != expected["$exists"]):
                return False
            if "$in" in expected and actual not in expected["$in"]:
                return False
            continue
        if actual != expected:
            return False
    return True


class InsertOneResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class UpdateOneResult:
    def __init__(self, modified_count):
        self.modified_count = modified_count


class AsyncCollection:
    def __init__(self, storage):
        self.storage = storage
        self._counter = 0

    async def find_one(self, query, *_args, **_kwargs):
        for document in self.storage:
            if _matches(document, query):
                return deepcopy(document)
        return None

    async def insert_one(self, document):
        stored = deepcopy(document)
        stored.setdefault("_id", f"doc-{len(self.storage) + 1}")
        self.storage.append(stored)
        return InsertOneResult(stored["_id"])

    async def update_one(self, query, update, **_kwargs):
        for document in self.storage:
            if _matches(document, query):
                for key, value in update.get("$set", {}).items():
                    document[key] = value
                for key in update.get("$unset", {}).keys():
                    document.pop(key, None)
                return UpdateOneResult(1)
        return UpdateOneResult(0)

    async def delete_one(self, query):
        for index, document in enumerate(self.storage):
            if _matches(document, query):
                del self.storage[index]
                return UpdateOneResult(1)
        return UpdateOneResult(0)

    async def create_index(self, *_args, **_kwargs):
        return "idx"


class AsyncDatabase:
    def __init__(self, storage_map):
        self.storage_map = storage_map

    def __getitem__(self, name):
        self.storage_map.setdefault(name, [])
        return AsyncCollection(self.storage_map[name])

    def get(self, name, default=None):
        if name not in self.storage_map:
            return default
        return AsyncCollection(self.storage_map[name])


class FakeMongo:
    def __init__(self, storage_map):
        self.storage_map = storage_map
        self.db = AsyncDatabase(storage_map)

    def get_users_collection(self):
        self.storage_map.setdefault("users", [])
        return AsyncCollection(self.storage_map["users"])

    def get_admin_users_collection(self):
        self.storage_map.setdefault("admin_users", [])
        return AsyncCollection(self.storage_map["admin_users"])


@pytest.fixture
def fake_storage():
    return {
        "users": [],
        "admin_users": [],
        "user_invitations": [],
    }


@pytest.fixture
def user_management_service(monkeypatch, fake_storage):
    fake_mongo = FakeMongo(fake_storage)
    monkeypatch.setattr(user_management_service_module, "mongo", fake_mongo)
    monkeypatch.setattr(
        user_management_service_module,
        "ResendEmailService",
        lambda: DummyEmailService(),
    )
    return user_management_service_module.UserManagementService(), fake_storage


def test_zero_day_invited_planner_requires_payment_after_setup(user_management_service):
    service, storage = user_management_service
    token = "setup-token-zero-day"

    storage["user_invitations"].append(
        {
            "_id": "invite-1",
            "token": token,
            "email": "invited-planner@example.com",
            "role": "wedding_planner",
            "status": "pending",
            "expires_at": datetime.now(timezone.utc) + timedelta(days=2),
            "invited_by": "root@example.com",
            "invite_data": {
                "trial_days": 0,
                "plan_id": "plan_boutique",
                "company_name": "Planner Studio",
            },
        }
    )

    result = asyncio.run(
        service.complete_account_setup(
            token=token,
            password="ValidPass123!",
            first_name="Invited",
            last_name="Planner",
        )
    )

    assert result["subscription_status"] == "pending_payment"

    stored_user = storage["users"][0]
    assert stored_user["email"] == "invited-planner@example.com"
    assert stored_user["subscription_status"] == "pending_payment"
    assert stored_user["is_active"] is True
    assert stored_user["email_verified"] is True
    assert stored_user["plan_id"] == "plan_boutique"

    stored_invitation = storage["user_invitations"][0]
    assert stored_invitation["status"] == "completed"
    assert "expires_at" not in stored_invitation


@pytest.mark.parametrize(
    ("status_value", "request_path"),
    [
        ("pending_payment", "/admin/planner"),
        ("pending_checkout", "/admin/planner"),
        ("past_due", "/admin/planner"),
        ("inactive", "/admin/planner"),
        ("pending", "/admin/weddings"),
    ],
)
def test_unpaid_planner_statuses_are_blocked_from_feature_routes(
    monkeypatch,
    fake_storage,
    status_value,
    request_path,
):
    fake_mongo = FakeMongo(fake_storage)
    monkeypatch.setattr(auth_extended, "mongo", fake_mongo)
    monkeypatch.setattr(
        auth_extended,
        "verify_token",
        lambda token: {"sub": "planner@example.com", "role": "wedding_planner"},
    )

    fake_storage["users"].append(
        {
            "_id": "planner-1",
            "email": "planner@example.com",
            "role": "wedding_planner",
            "subscription_status": status_value,
            "is_active": True,
            "email_verified": True,
        }
    )

    credentials = SimpleNamespace(credentials="token")
    request = SimpleNamespace(url=SimpleNamespace(path=request_path), cookies={})

    with pytest.raises(HTTPException) as exc:
        asyncio.run(auth_extended.get_current_user_extended(credentials, request))

    assert exc.value.status_code == status.HTTP_402_PAYMENT_REQUIRED


@pytest.mark.parametrize(
    "status_value", ["pending_payment", "pending_checkout", "past_due"]
)
def test_unpaid_planner_statuses_can_still_access_billing(
    monkeypatch, fake_storage, status_value
):
    fake_mongo = FakeMongo(fake_storage)
    monkeypatch.setattr(auth_extended, "mongo", fake_mongo)
    monkeypatch.setattr(
        auth_extended,
        "verify_token",
        lambda token: {"sub": "planner@example.com", "role": "wedding_planner"},
    )

    fake_storage["users"].append(
        {
            "_id": "planner-1",
            "email": "planner@example.com",
            "role": "wedding_planner",
            "subscription_status": status_value,
            "is_active": True,
            "email_verified": True,
        }
    )

    credentials = SimpleNamespace(credentials="token")
    request = SimpleNamespace(
        url=SimpleNamespace(path="/stripe/subscription"), cookies={}
    )

    user = asyncio.run(auth_extended.get_current_user_extended(credentials, request))

    assert user.email == "planner@example.com"
    assert user.user_data["_subscription_blocked"] is True
