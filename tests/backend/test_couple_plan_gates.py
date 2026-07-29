"""Couple-plan feature gates (operator ruling 2026-07-28).

The self-serve couple-plan purchaser uses the PLANNER dashboard for their own
single wedding. Exactly FOUR things are gated — nothing else (operator
rejected every additional gate proposal: no CRM, analytics, templates,
branding, or usage-cap gating):

1. couple-portal surfaces (they ARE the couple — no couple invitations),
2. packaging/storefront (package management AND the storefront surfaces
   that present/sell planner packages — operator clarification 2026-07-28),
3. team member seats (staff_seats=0 fails the existing team gate closed),
4. a second wedding (max_weddings=1 with the lifetime-style count; the
   user-facing copy is "the couple plan covers one wedding" — never
   "lifetime").

All gates are backend-enforced; hidden UI is a courtesy, not the barrier.
Planner tiers must be COMPLETELY unaffected: the include-by-default gate
polarity means plans that never declare the ``packages``/``couple_portal``
feature keys keep access.
"""

import asyncio
import inspect
import os
import sys
from copy import deepcopy
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.params import Depends as DependsParam

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import app.dependencies.feature_gates as feature_gates_module
import app.services.subscription_service as subscription_service_module
from app.api.couple_invite import router as couple_invite_router
from app.api.packages import router as packages_router
from app.constants.billing import (
    COUPLE_PLAN_ID,
    COUPLE_PLAN_SEED,
)
from app.dependencies.feature_gates import (
    require_couple_portal_feature,
    require_packages_feature,
    require_team_management,
)


def _matches(document, query):
    for key, expected in query.items():
        actual = document.get(key)
        if isinstance(expected, dict):
            if "$in" in expected and actual not in expected["$in"]:
                return False
            continue
        if actual != expected:
            return False
    return True


class AsyncCollection:
    def __init__(self, storage):
        self.storage = storage

    async def find_one(self, query, *_args, **_kwargs):
        for document in self.storage:
            if _matches(document, query):
                return deepcopy(document)
        return None


class AsyncDatabase:
    def __init__(self, storage_map):
        self.storage_map = storage_map

    def __getitem__(self, name):
        self.storage_map.setdefault(name, [])
        return AsyncCollection(self.storage_map[name])


class FakeMongo:
    def __init__(self, storage_map):
        self.storage_map = storage_map
        self.db = AsyncDatabase(storage_map)

    def get_users_collection(self):
        self.storage_map.setdefault("users", [])
        return AsyncCollection(self.storage_map["users"])


def _user(email="planner@example.com", **overrides):
    defaults = {
        "email": email,
        "is_root_admin": False,
        "is_team_member": False,
        "team_owner_email": None,
        "parent_planner_id": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _couple_snapshot():
    return {
        "plan_name": COUPLE_PLAN_SEED["name"],
        "max_weddings": 1,
        "max_weddings_lifetime": True,
        "staff_seats": 0,
        "features": deepcopy(COUPLE_PLAN_SEED["features"]),
    }


def _storage_with_subscription(email, plan_id, snapshot):
    return {
        "user_subscriptions": [
            {
                "_id": f"sub_{plan_id}",
                "user_id": "64b000000000000000000001",
                "user_email": email,
                "plan_id": plan_id,
                "status": "active",
                "plan_snapshot": snapshot,
            }
        ],
        "subscription_plans": [],
        "users": [],
    }


# ── Gate 1 + 2: couple portal & packages (plan feature flags) ──────────────


def test_couple_plan_is_blocked_from_packages_and_couple_portal(monkeypatch):
    email = "couple@example.com"
    storage = _storage_with_subscription(email, COUPLE_PLAN_ID, _couple_snapshot())
    monkeypatch.setattr(feature_gates_module, "mongo", FakeMongo(storage))

    for gate, feature in (
        (require_packages_feature, "packages"),
        (require_couple_portal_feature, "couple_portal"),
    ):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(gate(current_user=_user(email)))
        assert exc.value.status_code == 403
        detail = exc.value.detail
        assert detail["error"] == "feature_not_available"
        assert detail["feature"] == feature
        assert "included with planner plans" in detail["message"].lower()
        # Locked copy rule: never user-facing "lifetime" language.
        assert "lifetime" not in detail["message"].lower()


def test_planner_plans_without_feature_keys_keep_access(monkeypatch):
    """Include-by-default polarity: legacy planner plans never declare the
    ``packages``/``couple_portal`` keys and must be completely unaffected."""
    email = "planner@example.com"
    snapshot = {
        "plan_name": "Solo Founding",
        "max_weddings": -1,
        "staff_seats": 1,
        # Real planner snapshots carry feature dicts WITHOUT the new keys.
        "features": {"vendor_management": True, "ai_features": True},
    }
    storage = _storage_with_subscription(email, "plan_boutique", snapshot)
    monkeypatch.setattr(feature_gates_module, "mongo", FakeMongo(storage))

    user = _user(email)
    assert asyncio.run(require_packages_feature(current_user=user)) is user
    assert asyncio.run(require_couple_portal_feature(current_user=user)) is user


def test_planner_without_snapshot_falls_back_to_plan_document(monkeypatch):
    email = "planner@example.com"
    storage = _storage_with_subscription(email, "plan_boutique", None)
    storage["user_subscriptions"][0].pop("plan_snapshot")
    storage["subscription_plans"] = [
        {"_id": "plan_boutique", "features": {"vendor_management": True}}
    ]
    monkeypatch.setattr(feature_gates_module, "mongo", FakeMongo(storage))

    user = _user(email)
    assert asyncio.run(require_packages_feature(current_user=user)) is user


def test_root_admin_bypasses_couple_plan_gates(monkeypatch):
    storage = _storage_with_subscription(
        "root@example.com", COUPLE_PLAN_ID, _couple_snapshot()
    )
    monkeypatch.setattr(feature_gates_module, "mongo", FakeMongo(storage))

    admin = _user("root@example.com", is_root_admin=True)
    assert asyncio.run(require_packages_feature(current_user=admin)) is admin


def test_team_member_resolves_owner_plan_for_included_features(monkeypatch):
    """Team sessions bill against the owner plan — the gate must follow the
    owner identity, and a planner-owner's team member keeps access."""
    owner_email = "owner@example.com"
    storage = _storage_with_subscription(
        owner_email,
        "plan_boutique",
        {"plan_name": "Solo Founding", "features": {}},
    )
    monkeypatch.setattr(feature_gates_module, "mongo", FakeMongo(storage))

    member = _user(
        "member@example.com",
        is_team_member=True,
        team_owner_email=owner_email,
        parent_planner_id="64b000000000000000000001",
    )
    assert asyncio.run(require_packages_feature(current_user=member)) is member


# ── Gate 2 (storefront half): entitlements fail closed for the couple plan ─


def test_couple_plan_storefront_entitlements_are_disabled():
    """Storefront capabilities require a literal ``features.<key> is True``
    (fail-closed — see require_storefront_feature); the couple plan ships
    both keys explicitly False, so every storefront endpoint 403s through
    the existing entitlement machinery."""
    from app.services.storefront_entitlement_service import (
        StorefrontEntitlementService,
    )

    owner_id = "64b000000000000000000001"

    class _Cursor:
        def __init__(self, docs):
            self._docs = docs

        def limit(self, n):
            self._docs = self._docs[:n]
            return self

        async def to_list(self, length):
            return self._docs[:length]

    class _Subscriptions:
        def find(self, _query, _projection=None):
            return _Cursor(
                [
                    {
                        "user_id": owner_id,
                        "plan_id": COUPLE_PLAN_ID,
                        "status": "active",
                    }
                ]
            )

    class _Plans:
        async def find_one(self, _query, _projection=None):
            return {
                "_id": COUPLE_PLAN_ID,
                "features": deepcopy(COUPLE_PLAN_SEED["features"]),
            }

    class _Mongo:
        db = {"user_subscriptions": _Subscriptions()}

        def get_subscription_plans_collection(self):
            return _Plans()

    service = StorefrontEntitlementService(mongo_client=_Mongo())
    entitlements = asyncio.run(
        service.resolve_for_owner(
            {"_id": owner_id, "role": "wedding_planner", "is_active": True}
        )
    )

    assert entitlements.plan_id == COUPLE_PLAN_ID
    assert entitlements.storefront_enabled is False
    assert entitlements.custom_domain_enabled is False


# ── Gate 3: team seats (existing staff_seats gate, couple plan = 0) ─────────


def test_couple_plan_fails_team_management_gate(monkeypatch):
    email = "couple@example.com"
    storage = _storage_with_subscription(email, COUPLE_PLAN_ID, _couple_snapshot())
    monkeypatch.setattr(feature_gates_module, "mongo", FakeMongo(storage))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(require_team_management(current_user=_user(email)))
    assert exc.value.status_code == 403
    assert exc.value.detail["feature"] == "team_management"


# ── Gate 4: exactly one wedding, locked copy ────────────────────────────────


def _limits_service(monkeypatch, storage, *, live_count):
    fake_mongo = FakeMongo(storage)
    monkeypatch.setattr(subscription_service_module, "mongo", fake_mongo)
    service = subscription_service_module.SubscriptionService()

    async def _fake_usage(user_id):
        return {"weddings_count": live_count}

    async def _fake_live(user_id):
        return live_count

    monkeypatch.setattr(service, "get_usage_stats", _fake_usage)
    monkeypatch.setattr(service, "_live_wedding_count", _fake_live)
    monkeypatch.setattr(service, "_live_wedding_count_lifetime", _fake_live)
    return service


def test_couple_plan_second_wedding_blocked_with_locked_copy(monkeypatch):
    storage = _storage_with_subscription(
        "couple@example.com", COUPLE_PLAN_ID, _couple_snapshot()
    )
    service = _limits_service(monkeypatch, storage, live_count=1)

    result = asyncio.run(
        service.check_usage_limits("64b000000000000000000001", "weddings")
    )

    assert result["allowed"] is False
    assert result["limit"] == 1
    assert result["message"] == (
        "The couple plan covers one wedding — your workspace already includes it."
    )
    # Locked copy rule: the cap is lifetime-style internally, but the word
    # "lifetime" must never reach the user (workspace closes 90 days
    # post-wedding).
    assert "lifetime" not in result["message"].lower()


def test_couple_plan_first_wedding_is_allowed(monkeypatch):
    """The cap is exactly one wedding — the wedding itself must fit."""
    storage = _storage_with_subscription(
        "couple@example.com", COUPLE_PLAN_ID, _couple_snapshot()
    )
    service = _limits_service(monkeypatch, storage, live_count=0)

    result = asyncio.run(
        service.check_usage_limits("64b000000000000000000001", "weddings")
    )
    assert result.get("allowed", True) is not False


def test_couple_plan_billing_features_list_never_says_lifetime(monkeypatch):
    """get_user_billing_plan rebuilds features_list for inactive/snapshot
    plans — the couple plan's lifetime-style cap must not leak the word."""
    storage = _storage_with_subscription(
        "couple@example.com", COUPLE_PLAN_ID, _couple_snapshot()
    )
    storage["subscription_plans"] = [deepcopy(COUPLE_PLAN_SEED)]
    fake_mongo = FakeMongo(storage)
    monkeypatch.setattr(subscription_service_module, "mongo", fake_mongo)
    service = subscription_service_module.SubscriptionService()

    billing_plan = asyncio.run(
        service.get_user_billing_plan("64b000000000000000000001")
    )

    assert billing_plan is not None
    for line in billing_plan["features_list"]:
        assert "lifetime" not in line.lower()
    assert "One wedding workspace" in billing_plan["features_list"]


def test_planner_plan_wedding_limit_message_is_unchanged(monkeypatch):
    storage = _storage_with_subscription(
        "planner@example.com",
        "plan_capped",
        {"plan_name": "Legacy Capped", "max_weddings": 3, "features": {}},
    )
    service = _limits_service(monkeypatch, storage, live_count=3)

    result = asyncio.run(
        service.check_usage_limits("64b000000000000000000001", "weddings")
    )

    assert result["allowed"] is False
    assert result["message"] == (
        "Wedding limit exceeded. Plan allows 3 weddings, you have 3"
    )


# ── Route wiring: the gates are actually attached to the endpoints ──────────


def _route_gate_deps(router):
    wiring = {}
    for route in router.routes:
        deps = []
        for param in inspect.signature(route.endpoint).parameters.values():
            if isinstance(param.default, DependsParam):
                deps.append(param.default.dependency)
        wiring[(next(iter(route.methods)), route.path)] = deps
    return wiring


def test_every_packages_endpoint_is_gated():
    wiring = _route_gate_deps(packages_router)
    assert wiring, "packages router has no routes?"
    for key, deps in wiring.items():
        assert require_packages_feature in deps, (
            f"packages endpoint {key} is missing require_packages_feature"
        )


def test_couple_portal_planner_endpoints_are_gated():
    wiring = _route_gate_deps(couple_invite_router)
    gated = {
        ("POST", "/couple-portal/invite"),
        ("POST", "/couple-portal/resend-invite"),
        ("GET", "/couple-portal/couples"),
    }
    for key in gated:
        assert key in wiring, f"expected couple-portal route {key} missing"
        assert require_couple_portal_feature in wiring[key], (
            f"couple-portal endpoint {key} is missing require_couple_portal_feature"
        )


# ── Catalog safety: the couple plan can never leak onto public pricing ──────


def test_couple_plan_seed_is_internal_only():
    assert COUPLE_PLAN_SEED["_id"] == COUPLE_PLAN_ID
    # /public/subscription-plans returns every ACTIVE plan; the couple plan
    # must stay inactive forever to remain off the planner pricing page.
    assert COUPLE_PLAN_SEED["is_active"] is False
    assert COUPLE_PLAN_SEED["max_weddings"] == 1
    assert COUPLE_PLAN_SEED["max_weddings_lifetime"] is True
    assert COUPLE_PLAN_SEED["staff_seats"] == 0
    assert COUPLE_PLAN_SEED["features"]["packages"] is False
    assert COUPLE_PLAN_SEED["features"]["couple_portal"] is False
    # Storefront half of the packaging/storefront gate — these keys are
    # fail-closed (literal True required), so explicit False locks them.
    assert COUPLE_PLAN_SEED["features"]["planner_storefront"] is False
    assert COUPLE_PLAN_SEED["features"]["custom_domain"] is False
    # No user-facing "lifetime" language in catalog copy.
    assert "lifetime" not in COUPLE_PLAN_SEED["description"].lower()
    for line in COUPLE_PLAN_SEED["features_list"]:
        assert "lifetime" not in line.lower()
