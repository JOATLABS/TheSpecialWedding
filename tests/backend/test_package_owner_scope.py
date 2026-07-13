from __future__ import annotations

from unittest.mock import AsyncMock

import mongomock
import pytest
from bson import ObjectId
from fastapi import HTTPException

from app.api import packages as packages_api
from app.api.packages import (
    CoupleInfoRequest,
    CreatePackageRequest,
    SendPackageRequest,
    UpdatePackageRequest,
)
from app.dependencies.auth_extended import ExtendedAuthUser
from app.services import contract_email_service as contract_email_module
from app.services.package_service import PackageService


OWNER_ID = "507f1f77bcf86cd799439011"
TEAM_MEMBER_ID = "507f1f77bcf86cd799439012"
OTHER_OWNER_ID = "507f1f77bcf86cd799439013"


class AsyncCursor:
    def __init__(self, cursor):
        self._cursor = cursor

    def sort(self, *args, **kwargs):
        self._cursor = self._cursor.sort(*args, **kwargs)
        return self

    def skip(self, *args, **kwargs):
        self._cursor = self._cursor.skip(*args, **kwargs)
        return self

    def limit(self, *args, **kwargs):
        self._cursor = self._cursor.limit(*args, **kwargs)
        return self

    async def to_list(self, length=None):
        documents = list(self._cursor)
        return documents if length is None else documents[:length]


class AsyncCollection:
    def __init__(self, collection):
        self.raw = collection

    async def find_one(self, *args, **kwargs):
        return self.raw.find_one(*args, **kwargs)

    def find(self, *args, **kwargs):
        return AsyncCursor(self.raw.find(*args, **kwargs))

    def aggregate(self, *args, **kwargs):
        return AsyncCursor(self.raw.aggregate(*args, **kwargs))

    async def insert_one(self, *args, **kwargs):
        return self.raw.insert_one(*args, **kwargs)

    async def update_one(self, *args, **kwargs):
        return self.raw.update_one(*args, **kwargs)

    async def delete_one(self, *args, **kwargs):
        return self.raw.delete_one(*args, **kwargs)

    async def count_documents(self, *args, **kwargs):
        return self.raw.count_documents(*args, **kwargs)


class PackageServiceSpy:
    def __init__(self):
        self.list_packages = AsyncMock(return_value=[])
        self.create_package = AsyncMock(return_value={"id": "created"})
        self.get_package_stats = AsyncMock(return_value={"total_packages": 0})
        self.get_package = AsyncMock(return_value={"id": "package-1"})
        self.update_package = AsyncMock(return_value={"id": "package-1"})
        self.delete_package = AsyncMock(return_value=True)
        self.duplicate_package = AsyncMock(return_value={"id": "copy-1"})
        self.send_to_couple = AsyncMock(return_value={"id": "contract-1"})


class OwnerUsers:
    def __init__(self, owner: dict):
        self.owner = owner
        self.queries: list[dict] = []

    async def find_one(self, query: dict, *_args, **_kwargs):
        self.queries.append(query)
        expected = {
            "_id": ObjectId(OWNER_ID),
            "role": "wedding_planner",
            "is_active": {"$ne": False},
        }
        return self.owner if query == expected else None


class OwnerMongo:
    def __init__(self, owner: dict):
        self.users = OwnerUsers(owner)

    def get_users_collection(self):
        return self.users


def _team_member() -> ExtendedAuthUser:
    user = ExtendedAuthUser(
        email="member@example.test",
        role="team_member",
        user_data={"_id": ObjectId(TEAM_MEMBER_ID), "role": "team_member"},
    )
    user.parent_planner_id = OWNER_ID
    user.team_owner_email = "owner@example.test"
    user.team_permissions = {"manage_contracts": True}
    user.team_wedding_access = "all"
    return user


def _planner() -> ExtendedAuthUser:
    return ExtendedAuthUser(
        email="owner@example.test",
        role="wedding_planner",
        user_data={
            "_id": ObjectId(OWNER_ID),
            "role": "wedding_planner",
            "stripe_connect_id": "acct_owner",
            "stripe_connect_charges_enabled": True,
            "stripe_connect_details_submitted": True,
        },
    )


def _package_service(raw_db) -> PackageService:
    service = PackageService.__new__(PackageService)
    service.packages = AsyncCollection(raw_db["packages"])
    service.contracts = AsyncCollection(raw_db["contracts"])
    service.users = AsyncCollection(raw_db["users"])
    service.weddings = AsyncCollection(raw_db["weddings"])
    service.scheduled_payments = AsyncCollection(raw_db["scheduled_payments"])
    return service


@pytest.mark.asyncio
async def test_team_member_package_entry_points_use_canonical_owner_id(monkeypatch):
    service = PackageServiceSpy()
    monkeypatch.setattr(packages_api, "package_service", service)
    user = _team_member()

    await packages_api.list_packages(False, None, 50, 0, user)
    await packages_api.create_package(
        CreatePackageRequest(name="Owner package", total_amount=1250, status="active"),
        user,
    )
    await packages_api.get_package_stats(user)
    await packages_api.get_package("package-1", user)
    await packages_api.update_package(
        "package-1", UpdatePackageRequest(description="Updated"), user
    )
    await packages_api.delete_package("package-1", user)
    await packages_api.duplicate_package("package-1", "Copy", True, user)

    assert service.list_packages.await_args.kwargs["planner_id"] == OWNER_ID
    assert service.create_package.await_args.kwargs["planner_id"] == OWNER_ID
    assert service.get_package_stats.await_args.args == (OWNER_ID,)
    assert service.get_package.await_args.args == ("package-1", OWNER_ID)
    assert service.update_package.await_args.kwargs["planner_id"] == OWNER_ID
    assert service.delete_package.await_args.args == ("package-1", OWNER_ID)
    assert service.duplicate_package.await_args.kwargs["planner_id"] == OWNER_ID


@pytest.mark.asyncio
async def test_team_member_send_uses_owner_scope_and_owner_payment_readiness(
    monkeypatch,
):
    service = PackageServiceSpy()
    owner = {
        "_id": ObjectId(OWNER_ID),
        "role": "wedding_planner",
        "stripe_connect_id": "acct_owner",
        "stripe_connect_charges_enabled": True,
        "stripe_connect_details_submitted": True,
    }
    owner_mongo = OwnerMongo(owner)
    monkeypatch.setattr(packages_api, "package_service", service)
    monkeypatch.setattr(packages_api, "mongo", owner_mongo, raising=False)

    await packages_api.send_package_to_couple(
        "package-1",
        SendPackageRequest(
            couple=CoupleInfoRequest(partner1_name="Ada", email="couple@example.test")
        ),
        _team_member(),
    )

    assert owner_mongo.users.queries == [
        {
            "_id": ObjectId(OWNER_ID),
            "role": "wedding_planner",
            "is_active": {"$ne": False},
        }
    ]
    assert service.send_to_couple.await_args.kwargs["planner_id"] == OWNER_ID


@pytest.mark.asyncio
async def test_planner_cannot_send_package_against_foreign_wedding(monkeypatch):
    service = PackageServiceSpy()
    wedding_access = AsyncMock(return_value=False)
    monkeypatch.setattr(packages_api, "package_service", service)
    monkeypatch.setattr(
        packages_api,
        "check_wedding_access",
        wedding_access,
        raising=False,
    )

    with pytest.raises(HTTPException) as exc_info:
        await packages_api.send_package_to_couple(
            "package-1",
            SendPackageRequest(
                couple=CoupleInfoRequest(
                    partner1_name="Ada", email="couple@example.test"
                ),
                wedding_id="foreign-wedding",
            ),
            _planner(),
        )

    assert exc_info.value.status_code == 403
    wedding_access.assert_awaited_once()
    service.send_to_couple.assert_not_awaited()


@pytest.mark.asyncio
async def test_team_member_cannot_send_package_for_unassigned_wedding(monkeypatch):
    service = PackageServiceSpy()
    owner_mongo = OwnerMongo(
        {
            "_id": ObjectId(OWNER_ID),
            "role": "wedding_planner",
            "stripe_connect_id": "acct_owner",
            "stripe_connect_charges_enabled": True,
            "stripe_connect_details_submitted": True,
        }
    )
    monkeypatch.setattr(packages_api, "package_service", service)
    monkeypatch.setattr(packages_api, "mongo", owner_mongo, raising=False)
    user = _team_member()
    user.team_wedding_access = "assigned"
    user.team_assigned_wedding_ids = ["assigned-wedding"]

    with pytest.raises(HTTPException) as exc_info:
        await packages_api.send_package_to_couple(
            "package-1",
            SendPackageRequest(
                couple=CoupleInfoRequest(
                    partner1_name="Ada", email="couple@example.test"
                ),
                wedding_id="unassigned-wedding",
            ),
            user,
        )

    assert exc_info.value.status_code == 403
    service.send_to_couple.assert_not_awaited()


@pytest.mark.asyncio
async def test_team_member_can_send_package_for_assigned_owner_wedding(monkeypatch):
    service = PackageServiceSpy()
    owner = {
        "_id": ObjectId(OWNER_ID),
        "role": "wedding_planner",
        "stripe_connect_id": "acct_owner",
        "stripe_connect_charges_enabled": True,
        "stripe_connect_details_submitted": True,
    }
    owner_mongo = OwnerMongo(owner)
    monkeypatch.setattr(packages_api, "package_service", service)
    monkeypatch.setattr(packages_api, "mongo", owner_mongo, raising=False)
    user = _team_member()
    user.team_wedding_access = "assigned"
    user.team_assigned_wedding_ids = ["assigned-wedding"]

    await packages_api.send_package_to_couple(
        "package-1",
        SendPackageRequest(
            couple=CoupleInfoRequest(partner1_name="Ada", email="couple@example.test"),
            wedding_id="assigned-wedding",
        ),
        user,
    )

    assert service.send_to_couple.await_args.kwargs["planner_id"] == OWNER_ID
    assert service.send_to_couple.await_args.kwargs["wedding_id"] == (
        "assigned-wedding"
    )


@pytest.mark.asyncio
async def test_package_routes_fail_closed_without_a_planner_owner(monkeypatch):
    service = PackageServiceSpy()
    monkeypatch.setattr(packages_api, "package_service", service)
    orphaned = _team_member()
    orphaned.parent_planner_id = None

    with pytest.raises(HTTPException) as exc_info:
        await packages_api.list_packages(False, None, 50, 0, orphaned)

    assert exc_info.value.status_code == 403
    assert "owner scope" in str(exc_info.value.detail).lower()
    service.list_packages.assert_not_awaited()


@pytest.mark.asyncio
async def test_package_service_rejects_foreign_package_across_all_entry_points():
    raw_db = mongomock.MongoClient()["package_owner_scope"]
    service = _package_service(raw_db)

    foreign_id = ObjectId()
    raw_db.packages.insert_one(
        {
            "_id": foreign_id,
            "planner_id": OTHER_OWNER_ID,
            "name": "Foreign package",
            "status": "draft",
            "is_template": False,
            "services": [],
            "total_amount": 1000,
            "currency": "usd",
            "contracts_count": 0,
        }
    )

    assert await service.list_packages(OWNER_ID, include_templates=True) == []
    assert await service.get_package(str(foreign_id), OWNER_ID) is None
    stats = await service.get_package_stats(OWNER_ID)
    assert stats["total_packages"] == 0

    foreign_mutations = (
        service.update_package(str(foreign_id), OWNER_ID, {"description": "forged"}),
        service.delete_package(str(foreign_id), OWNER_ID),
        service.duplicate_package(str(foreign_id), OWNER_ID),
        service.send_to_couple(
            str(foreign_id),
            OWNER_ID,
            {"partner1_name": "Ada", "email": "couple@example.test"},
        ),
    )
    for mutation in foreign_mutations:
        with pytest.raises(ValueError, match="access denied"):
            await mutation

    untouched = raw_db.packages.find_one({"_id": foreign_id})
    assert untouched.get("description") is None
    assert raw_db.contracts.count_documents({}) == 0


@pytest.mark.asyncio
async def test_duplicate_package_executes_without_reusing_persisted_owner_argument():
    raw_db = mongomock.MongoClient()["package_duplicate_positive"]
    service = _package_service(raw_db)
    source_id = raw_db.packages.insert_one(
        {
            "planner_id": OWNER_ID,
            "name": "Signature",
            "status": "active",
            "is_template": False,
            "services": [],
            "total_amount": 2500,
            "currency": "usd",
            "contracts_count": 3,
        }
    ).inserted_id

    duplicate = await service.duplicate_package(
        str(source_id), OWNER_ID, new_name="Signature Copy"
    )

    assert duplicate["planner_id"] == OWNER_ID
    assert duplicate["name"] == "Signature Copy"
    assert duplicate["contracts_count"] == 0
    assert raw_db.packages.count_documents({"planner_id": OWNER_ID}) == 2


@pytest.mark.asyncio
async def test_package_service_rejects_foreign_wedding_before_contract_insert(
    monkeypatch,
):
    raw_db = mongomock.MongoClient()["package_wedding_owner_scope"]
    service = _package_service(raw_db)
    package_id = raw_db.packages.insert_one(
        {
            "planner_id": OWNER_ID,
            "name": "Signature",
            "status": "active",
            "is_template": False,
            "services": [],
            "total_amount": 2500,
            "currency": "usd",
            "contracts_count": 0,
        }
    ).inserted_id
    raw_db.users.insert_one({"_id": ObjectId(OWNER_ID), "email": "owner@example.test"})
    raw_db.weddings.insert_one(
        {
            "_id": "foreign-wedding",
            "assigned_planner_id": OTHER_OWNER_ID,
            "venue": "Foreign private venue",
        }
    )
    monkeypatch.setattr(
        contract_email_module.contract_email_service,
        "send_package_contract_email",
        AsyncMock(return_value=True),
    )

    with pytest.raises(ValueError, match="Wedding not found or access denied"):
        await service.send_to_couple(
            str(package_id),
            OWNER_ID,
            {"partner1_name": "Ada", "email": "couple@example.test"},
            wedding_id="foreign-wedding",
        )

    assert raw_db.contracts.count_documents({}) == 0


@pytest.mark.asyncio
async def test_package_service_copies_only_owner_wedding_context(monkeypatch):
    raw_db = mongomock.MongoClient()["package_wedding_owner_positive"]
    service = _package_service(raw_db)
    package_id = raw_db.packages.insert_one(
        {
            "planner_id": OWNER_ID,
            "name": "Signature",
            "status": "active",
            "is_template": False,
            "services": [],
            "total_amount": 2500,
            "currency": "usd",
            "contracts_count": 0,
        }
    ).inserted_id
    raw_db.users.insert_one({"_id": ObjectId(OWNER_ID), "email": "owner@example.test"})
    raw_db.weddings.insert_one(
        {
            "_id": "owner-wedding",
            "assigned_planner_id": OWNER_ID,
            "venue": "Owner venue",
            "date": "2027-10-12",
        }
    )
    monkeypatch.setattr(
        contract_email_module.contract_email_service,
        "send_package_contract_email",
        AsyncMock(return_value=True),
    )

    contract = await service.send_to_couple(
        str(package_id),
        OWNER_ID,
        {"partner1_name": "Ada", "email": "couple@example.test"},
        wedding_id="owner-wedding",
    )

    assert contract["wedding_id"] == "owner-wedding"
    assert contract["venue"] == "Owner venue"
    assert contract["wedding_date"] == "2027-10-12T00:00:00"
