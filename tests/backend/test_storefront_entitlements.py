from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from bson import ObjectId
from fastapi import HTTPException

from app.constants.storefront import (
    CUSTOM_DOMAIN_FEATURE,
    STOREFRONT_FEATURE,
)
from app.dependencies.auth_extended import ExtendedAuthUser
from app.dependencies.storefront_access import (
    require_storefront_feature,
    require_storefront_owner,
)
from app.services.storefront_entitlement_service import (
    StorefrontEntitlementResolutionError,
    StorefrontEntitlementService,
)


OWNER_ID = "507f1f77bcf86cd799439011"


def _matches(document: dict, query: dict) -> bool:
    for key, expected in query.items():
        actual = document.get(key)
        if isinstance(expected, dict) and "$in" in expected:
            if actual not in expected["$in"]:
                return False
            continue
        if str(actual) != str(expected):
            return False
    return True


class AsyncCursor:
    def __init__(self, documents: list[dict]):
        self._documents = documents
        self._limit: int | None = None

    def limit(self, count: int):
        self._limit = count
        return self

    async def to_list(self, length: int | None = None):
        limit = self._limit if self._limit is not None else length
        documents = self._documents if limit is None else self._documents[:limit]
        return deepcopy(documents)


class AsyncCollection:
    def __init__(self, documents: list[dict]):
        self.documents = documents
        self.write_calls: list[str] = []

    def find(self, query: dict, *_args, **_kwargs):
        return AsyncCursor(
            [document for document in self.documents if _matches(document, query)]
        )

    async def find_one(self, query: dict, *_args, **_kwargs):
        for document in self.documents:
            if _matches(document, query):
                return deepcopy(document)
        return None

    async def insert_one(self, *_args, **_kwargs):
        self.write_calls.append("insert_one")
        raise AssertionError("entitlement resolution must be read-only")

    async def update_one(self, *_args, **_kwargs):
        self.write_calls.append("update_one")
        raise AssertionError("entitlement resolution must be read-only")

    async def replace_one(self, *_args, **_kwargs):
        self.write_calls.append("replace_one")
        raise AssertionError("entitlement resolution must be read-only")


class AsyncDatabase:
    def __init__(self, collections: dict[str, AsyncCollection]):
        self._collections = collections

    def __getitem__(self, name: str) -> AsyncCollection:
        return self._collections[name]


class FakeMongo:
    def __init__(
        self,
        *,
        users: list[dict],
        subscriptions: list[dict],
        plans: list[dict],
    ):
        self.collections = {
            "users": AsyncCollection(users),
            "user_subscriptions": AsyncCollection(subscriptions),
            "subscription_plans": AsyncCollection(plans),
        }
        self.db = AsyncDatabase(self.collections)

    def get_users_collection(self) -> AsyncCollection:
        return self.collections["users"]

    def get_subscription_plans_collection(self) -> AsyncCollection:
        return self.collections["subscription_plans"]


def _service(
    *,
    plan_id: str = "plan_signature",
    subscription_status: str = "active",
    features: dict | None = None,
    snapshot_features: dict | None = None,
) -> tuple[StorefrontEntitlementService, FakeMongo]:
    plan_features = (
        {
            STOREFRONT_FEATURE: True,
            CUSTOM_DOMAIN_FEATURE: True,
        }
        if features is None
        else features
    )
    fake_mongo = FakeMongo(
        users=[
            {
                "_id": ObjectId(OWNER_ID),
                "role": "wedding_planner",
                "is_active": True,
            }
        ],
        subscriptions=[
            {
                "_id": "subscription-1",
                "user_id": OWNER_ID,
                "plan_id": plan_id,
                "status": subscription_status,
                "plan_snapshot": {"features": snapshot_features or {}},
            }
        ],
        plans=[{"_id": plan_id, "features": plan_features}],
    )
    return StorefrontEntitlementService(fake_mongo), fake_mongo


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("plan_id", "enabled"),
    [
        ("plan_solo", False),
        ("plan_boutique", False),
        ("plan_signature", True),
        ("plan_enterprise", True),
    ],
)
async def test_resolves_the_four_plan_matrix_from_current_catalog(
    plan_id: str, enabled: bool
):
    service, fake_mongo = _service(
        plan_id=plan_id,
        features={
            STOREFRONT_FEATURE: enabled,
            CUSTOM_DOMAIN_FEATURE: enabled,
        },
    )

    result = await service.resolve_for_owner(
        {"_id": ObjectId(OWNER_ID), "role": "wedding_planner"}
    )

    assert result.owner_id == OWNER_ID
    assert result.plan_id == plan_id
    assert result.storefront_enabled is enabled
    assert result.custom_domain_enabled is enabled
    assert all(
        not collection.write_calls for collection in fake_mongo.collections.values()
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["active", "trial", "trial_expiring"])
async def test_accepts_every_canonical_active_subscription_status(status: str):
    service, _ = _service(subscription_status=status)

    result = await service.resolve_for_owner(
        {"_id": OWNER_ID, "role": "wedding_planner"}
    )

    assert result.storefront_enabled is True
    assert result.custom_domain_enabled is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [
        "pending_checkout",
        "pending_payment",
        "past_due",
        "cancelled",
        "expired",
        "suspended",
        "inactive",
    ],
)
async def test_inactive_subscription_statuses_fail_closed(status: str):
    service, _ = _service(subscription_status=status)

    result = await service.resolve_for_owner(
        {"_id": OWNER_ID, "role": "wedding_planner"}
    )

    assert result.plan_id is None
    assert result.storefront_enabled is False
    assert result.custom_domain_enabled is False


@pytest.mark.asyncio
async def test_current_catalog_wins_over_stale_plan_snapshot():
    service, _ = _service(
        features={STOREFRONT_FEATURE: False, CUSTOM_DOMAIN_FEATURE: True},
        snapshot_features={STOREFRONT_FEATURE: True, CUSTOM_DOMAIN_FEATURE: False},
    )

    result = await service.resolve_for_owner(
        {"_id": OWNER_ID, "role": "wedding_planner"}
    )

    assert result.storefront_enabled is False
    assert result.custom_domain_enabled is True


@pytest.mark.asyncio
async def test_missing_or_malformed_catalog_features_fail_closed():
    service, fake_mongo = _service(
        features={STOREFRONT_FEATURE: "true", CUSTOM_DOMAIN_FEATURE: 1}
    )

    result = await service.resolve_for_owner(
        {"_id": OWNER_ID, "role": "wedding_planner"}
    )
    assert result.storefront_enabled is False
    assert result.custom_domain_enabled is False

    fake_mongo.collections["subscription_plans"].documents.clear()
    missing = await service.resolve_for_owner(
        {"_id": OWNER_ID, "role": "wedding_planner"}
    )
    assert missing.plan_id == "plan_signature"
    assert missing.storefront_enabled is False
    assert missing.custom_domain_enabled is False


@pytest.mark.asyncio
async def test_duplicate_active_subscriptions_fail_closed():
    service, fake_mongo = _service()
    fake_mongo.collections["user_subscriptions"].documents.append(
        {
            "_id": "subscription-2",
            "user_id": OWNER_ID,
            "plan_id": "plan_enterprise",
            "status": "trial",
        }
    )

    result = await service.resolve_for_owner(
        {"_id": OWNER_ID, "role": "wedding_planner"}
    )

    assert result.plan_id is None
    assert result.storefront_enabled is False
    assert result.custom_domain_enabled is False


@pytest.mark.asyncio
async def test_database_failures_are_not_mislabeled_as_upgrade_requirements():
    service, fake_mongo = _service()
    fake_mongo.collections["user_subscriptions"].find = Mock(
        side_effect=RuntimeError("database unavailable")
    )

    with pytest.raises(StorefrontEntitlementResolutionError):
        await service.resolve_for_owner({"_id": OWNER_ID, "role": "wedding_planner"})


@pytest.mark.asyncio
async def test_resolve_for_planner_id_rejects_inactive_and_non_planner_users():
    service, fake_mongo = _service()

    active = await service.resolve_for_planner_id(OWNER_ID)
    assert active.storefront_enabled is True

    fake_mongo.collections["users"].documents[0]["is_active"] = False
    inactive = await service.resolve_for_planner_id(OWNER_ID)
    assert inactive.storefront_enabled is False

    fake_mongo.collections["users"].documents[0]["is_active"] = True
    fake_mongo.collections["users"].documents[0]["role"] = "team_member"
    team_member = await service.resolve_for_planner_id(OWNER_ID)
    assert team_member.storefront_enabled is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "user",
    [
        ExtendedAuthUser("root@example.com", "ROOT_ADMIN", {"_id": OWNER_ID}),
        ExtendedAuthUser("team@example.com", "team_member", {"_id": OWNER_ID}),
        ExtendedAuthUser("vendor@example.com", "advertising_vendor", {"_id": OWNER_ID}),
    ],
)
async def test_owner_dependency_rejects_non_planner_roles(user: ExtendedAuthUser):
    with pytest.raises(HTTPException) as exc_info:
        await require_storefront_owner(user)

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_owner_dependency_accepts_only_a_planner_with_an_owner_id():
    planner = ExtendedAuthUser(
        "planner@example.com",
        "wedding_planner",
        {"_id": ObjectId(OWNER_ID), "role": "wedding_planner"},
    )
    result = await require_storefront_owner(planner)
    assert result is planner

    missing_id = ExtendedAuthUser(
        "planner@example.com", "wedding_planner", {"role": "wedding_planner"}
    )
    with pytest.raises(HTTPException) as exc_info:
        await require_storefront_owner(missing_id)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_feature_dependency_keeps_capabilities_independent(monkeypatch):
    planner = ExtendedAuthUser(
        "planner@example.com",
        "wedding_planner",
        {"_id": OWNER_ID, "role": "wedding_planner"},
    )
    entitlements = SimpleNamespace(
        owner_id=OWNER_ID,
        plan_id="plan_signature",
        storefront_enabled=True,
        custom_domain_enabled=False,
    )
    resolver = AsyncMock(return_value=entitlements)
    monkeypatch.setattr(
        "app.dependencies.storefront_access.storefront_entitlement_service.resolve_for_owner",
        resolver,
    )

    storefront_dependency = require_storefront_feature(STOREFRONT_FEATURE)
    assert await storefront_dependency(planner) is entitlements

    domain_dependency = require_storefront_feature(CUSTOM_DOMAIN_FEATURE)
    with pytest.raises(HTTPException) as exc_info:
        await domain_dependency(planner)
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["feature"] == CUSTOM_DOMAIN_FEATURE

    with pytest.raises(ValueError):
        require_storefront_feature("made_up_feature")


@pytest.mark.asyncio
async def test_feature_dependency_maps_resolution_failure_to_service_unavailable(
    monkeypatch,
):
    planner = ExtendedAuthUser(
        "planner@example.com",
        "wedding_planner",
        {"_id": OWNER_ID, "role": "wedding_planner"},
    )
    monkeypatch.setattr(
        "app.dependencies.storefront_access.storefront_entitlement_service.resolve_for_owner",
        AsyncMock(
            side_effect=StorefrontEntitlementResolutionError("database unavailable")
        ),
    )

    dependency = require_storefront_feature(STOREFRONT_FEATURE)
    with pytest.raises(HTTPException) as exc_info:
        await dependency(planner)

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Storefront eligibility is temporarily unavailable"
