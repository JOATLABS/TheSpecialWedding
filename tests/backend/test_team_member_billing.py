"""Tests for the team-member billing gate.

Covers:
  1. Unit tests for ``compute_owner_subscription_block`` — the helper that
     decides whether a team member should inherit the subscription block
     from their owning planner.
  2. Integration tests that drive ``get_current_user_extended`` end-to-end
     with a team-member token whose owning planner is in each blocked
     state, asserting that feature routes return 402 and whitelist routes
     return the user unchanged.

This mirrors the planner-side pattern in ``test_invited_planner_billing.py``.
"""

from __future__ import annotations

import asyncio
import os
import sys
from copy import deepcopy
from types import SimpleNamespace
from typing import Any

import pytest
from bson import ObjectId
from fastapi import HTTPException, status

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import app.dependencies.auth_extended as auth_extended  # noqa: E402
from app.models.subscription import (  # noqa: E402
    PLANNER_BLOCKED_SUBSCRIPTION_STATUSES,
)


# ─────────────────────────────────────────────────────────────────────────────
# FakeMongo scaffolding (ObjectId-aware variant of the planner tests')
# ─────────────────────────────────────────────────────────────────────────────


def _values_equal(actual: Any, expected: Any) -> bool:
    """Compare two values allowing ObjectId/str equivalence.

    The real Mongo accepts an ObjectId-typed _id matching a document whose
    _id is also an ObjectId. In tests we sometimes store strings for easier
    assertions. Treat ObjectId and its string form as equal for query matching.
    """
    if isinstance(actual, ObjectId) and isinstance(expected, ObjectId):
        return actual == expected
    if isinstance(actual, ObjectId) and isinstance(expected, str):
        return str(actual) == expected
    if isinstance(actual, str) and isinstance(expected, ObjectId):
        return actual == str(expected)
    return actual == expected


def _matches(document: dict, query: dict) -> bool:
    for key, expected in query.items():
        actual = document.get(key)
        if isinstance(expected, dict):
            if "$in" in expected and not any(
                _values_equal(actual, v) for v in expected["$in"]
            ):
                return False
            continue
        if not _values_equal(actual, expected):
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

    async def update_one(self, query, update, **_kwargs):
        class R:
            modified_count = 0

        for document in self.storage:
            if _matches(document, query):
                for k, v in update.get("$set", {}).items():
                    document[k] = v
                R.modified_count = 1
                break
        return R()


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


# Stable ObjectIds used across the test suite
OWNER_OID = ObjectId("507f1f77bcf86cd799439011")
TEAM_USER_OID = ObjectId("507f1f77bcf86cd799439012")
TEAM_MEMBER_OID = ObjectId("507f1f77bcf86cd799439013")


@pytest.fixture
def fake_storage():
    return {
        "users": [],
        "user_subscriptions": [],
        "team_members": [],
    }


@pytest.fixture
def patched_mongo(monkeypatch, fake_storage):
    fake_mongo = FakeMongo(fake_storage)
    monkeypatch.setattr(auth_extended, "mongo", fake_mongo)
    return fake_mongo, fake_storage


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests: compute_owner_subscription_block
# ─────────────────────────────────────────────────────────────────────────────


def _run(coro):
    return asyncio.run(coro)


def test_helper_returns_not_blocked_when_owner_is_active(patched_mongo):
    _, storage = patched_mongo
    storage["users"].append(
        {
            "_id": OWNER_OID,
            "email": "owner@example.com",
            "subscription_status": "active",
        }
    )
    is_blocked, status_value = _run(
        auth_extended.compute_owner_subscription_block(
            owner_id=str(OWNER_OID), owner_email="owner@example.com"
        )
    )
    assert is_blocked is False
    assert status_value == "active"


@pytest.mark.parametrize(
    "blocked_status", sorted(PLANNER_BLOCKED_SUBSCRIPTION_STATUSES)
)
def test_helper_returns_blocked_for_every_planner_blocked_status(
    patched_mongo, blocked_status
):
    """Every status in PLANNER_BLOCKED_SUBSCRIPTION_STATUSES must block team members
    identically to how it blocks the owning planner."""
    _, storage = patched_mongo
    storage["users"].append(
        {
            "_id": OWNER_OID,
            "email": "owner@example.com",
            "subscription_status": blocked_status,
        }
    )
    is_blocked, status_value = _run(
        auth_extended.compute_owner_subscription_block(
            owner_id=str(OWNER_OID), owner_email="owner@example.com"
        )
    )
    assert is_blocked is True, f"Status '{blocked_status}' should block team members"
    assert status_value == blocked_status


def test_helper_detects_webhook_race_when_user_subscriptions_lags_users(patched_mongo):
    """If users.subscription_status is stale-active but user_subscriptions has a
    blocked status, trust user_subscriptions (matches the planner-side prong-1
    race-condition fix)."""
    _, storage = patched_mongo
    storage["users"].append(
        {
            "_id": OWNER_OID,
            "email": "owner@example.com",
            "subscription_status": "active",
        }
    )
    storage["user_subscriptions"].append(
        {"user_id": str(OWNER_OID), "status": "past_due"}
    )
    is_blocked, status_value = _run(
        auth_extended.compute_owner_subscription_block(
            owner_id=str(OWNER_OID), owner_email="owner@example.com"
        )
    )
    assert is_blocked is True
    assert status_value == "past_due"


def test_helper_returns_not_blocked_when_owner_document_missing(patched_mongo):
    """Orphaned team member (owner doc removed) falls open; the
    team-deactivation lifecycle handles this elsewhere."""
    is_blocked, status_value = _run(
        auth_extended.compute_owner_subscription_block(
            owner_id=str(OWNER_OID), owner_email="ghost@example.com"
        )
    )
    assert is_blocked is False
    assert status_value is None


def test_helper_returns_not_blocked_when_both_inputs_missing(patched_mongo):
    is_blocked, status_value = _run(
        auth_extended.compute_owner_subscription_block(owner_id=None, owner_email=None)
    )
    assert is_blocked is False
    assert status_value is None


def test_helper_falls_back_to_email_lookup_when_id_missing(patched_mongo):
    _, storage = patched_mongo
    storage["users"].append(
        {
            "_id": OWNER_OID,
            "email": "owner@example.com",
            "subscription_status": "past_due",
        }
    )
    is_blocked, status_value = _run(
        auth_extended.compute_owner_subscription_block(
            owner_id=None, owner_email="owner@example.com"
        )
    )
    assert is_blocked is True
    assert status_value == "past_due"


def test_helper_normalizes_stripe_alias_statuses(patched_mongo):
    """Stripe aliases like 'canceled' normalize to 'cancelled' and should block."""
    _, storage = patched_mongo
    storage["users"].append(
        {
            "_id": OWNER_OID,
            "email": "owner@example.com",
            "subscription_status": "canceled",  # Stripe alias
        }
    )
    is_blocked, status_value = _run(
        auth_extended.compute_owner_subscription_block(
            owner_id=str(OWNER_OID), owner_email="owner@example.com"
        )
    )
    assert is_blocked is True
    assert status_value == "cancelled"


def test_helper_does_not_escalate_when_user_subscriptions_still_active(patched_mongo):
    """When both users and user_subscriptions agree the planner is active,
    we must not block."""
    _, storage = patched_mongo
    storage["users"].append(
        {
            "_id": OWNER_OID,
            "email": "owner@example.com",
            "subscription_status": "active",
        }
    )
    storage["user_subscriptions"].append(
        {"user_id": str(OWNER_OID), "status": "active"}
    )
    is_blocked, status_value = _run(
        auth_extended.compute_owner_subscription_block(
            owner_id=str(OWNER_OID), owner_email="owner@example.com"
        )
    )
    assert is_blocked is False
    assert status_value == "active"


# ─────────────────────────────────────────────────────────────────────────────
# Integration tests: full get_current_user_extended path for a team member
# ─────────────────────────────────────────────────────────────────────────────


def _seed_team_member(
    storage: dict,
    *,
    owner_status: str,
    team_member_email: str = "teammember@example.com",
    owner_email: str = "owner@example.com",
):
    """Seed users + team_members for a blocked-owner scenario."""
    storage["users"].append(
        {
            "_id": OWNER_OID,
            "email": owner_email,
            "subscription_status": owner_status,
            "is_active": True,
            "email_verified": True,
            "role": "wedding_planner",
        }
    )
    storage["users"].append(
        {
            "_id": TEAM_USER_OID,
            "email": team_member_email,
            "is_active": True,
            "email_verified": True,
            "role": "team_member",
            "team_member_id": str(TEAM_MEMBER_OID),
        }
    )
    storage["team_members"].append(
        {
            "_id": TEAM_MEMBER_OID,
            "email": team_member_email,
            "status": "active",
            "role": "assistant",
            "custom_permissions": {},
            "wedding_access": "all",
            "assigned_wedding_ids": [],
            "owner_email": owner_email,
            "owner_id": str(OWNER_OID),
        }
    )


def _patch_token(monkeypatch, email: str):
    monkeypatch.setattr(
        auth_extended,
        "verify_token",
        lambda token: {"sub": email, "role": "team_member"},
    )


def _clear_team_cache():
    """The team-member LRU is process-global; clear between tests."""
    auth_extended._team_cache.clear()


@pytest.fixture(autouse=True)
def _reset_cache():
    _clear_team_cache()
    yield
    _clear_team_cache()


@pytest.mark.parametrize(
    ("owner_status", "request_path"),
    [
        ("past_due", "/admin/planner"),
        ("suspended", "/admin/weddings"),
        ("cancelled", "/admin/weddings/123/timeline"),
        ("expired", "/admin/vendors"),
        ("pending_checkout", "/admin/planner"),
        ("pending_payment", "/admin/planner"),
        ("inactive", "/admin/weddings"),
        ("pending", "/admin/planner"),
    ],
)
def test_team_member_is_blocked_when_owner_has_any_blocked_status(
    monkeypatch, patched_mongo, owner_status, request_path
):
    """Cross-product: every blocked owner status × representative feature route
    must return 402 for the team member."""
    _, storage = patched_mongo
    _seed_team_member(storage, owner_status=owner_status)
    _patch_token(monkeypatch, "teammember@example.com")

    credentials = SimpleNamespace(credentials="token")
    request = SimpleNamespace(url=SimpleNamespace(path=request_path), cookies={})

    with pytest.raises(HTTPException) as exc:
        _run(auth_extended.get_current_user_extended(credentials, request))
    assert exc.value.status_code == status.HTTP_402_PAYMENT_REQUIRED
    # Reason should point at the planner, not imply the team member can pay.
    assert "contact your planner" in exc.value.detail.lower()


@pytest.mark.parametrize(
    "whitelist_path",
    [
        "/admin/profile",
        "/admin/logout",
        "/admin/team/permissions",
        "/stripe/subscription",
    ],
)
def test_team_member_with_blocked_owner_can_reach_whitelist_routes(
    monkeypatch, patched_mongo, whitelist_path
):
    """Whitelist must let blocked team members log out, read profile/permissions,
    and hit billing-adjacent routes without 402."""
    _, storage = patched_mongo
    _seed_team_member(storage, owner_status="past_due")
    _patch_token(monkeypatch, "teammember@example.com")

    credentials = SimpleNamespace(credentials="token")
    request = SimpleNamespace(url=SimpleNamespace(path=whitelist_path), cookies={})

    user = _run(auth_extended.get_current_user_extended(credentials, request))
    assert user.email == "teammember@example.com"
    assert user.is_team_member is True
    # Flag must still be set — the gate just skipped the 402 for whitelist paths.
    assert user.user_data.get("_subscription_blocked") is True
    assert user.user_data.get("_blocked_reason_source") == "owner_subscription"
    assert user.user_data.get("_owner_email") == "owner@example.com"


def test_team_member_with_active_owner_is_not_blocked(monkeypatch, patched_mongo):
    _, storage = patched_mongo
    _seed_team_member(storage, owner_status="active")
    _patch_token(monkeypatch, "teammember@example.com")

    credentials = SimpleNamespace(credentials="token")
    request = SimpleNamespace(url=SimpleNamespace(path="/admin/planner"), cookies={})

    user = _run(auth_extended.get_current_user_extended(credentials, request))
    assert user.email == "teammember@example.com"
    assert user.user_data.get("_subscription_blocked") is not True


def test_team_member_with_trial_owner_is_not_blocked(monkeypatch, patched_mongo):
    """Trial is a valid, paying-grace state — must not cascade a block."""
    _, storage = patched_mongo
    _seed_team_member(storage, owner_status="trial")
    _patch_token(monkeypatch, "teammember@example.com")

    credentials = SimpleNamespace(credentials="token")
    request = SimpleNamespace(url=SimpleNamespace(path="/admin/planner"), cookies={})

    user = _run(auth_extended.get_current_user_extended(credentials, request))
    assert user.user_data.get("_subscription_blocked") is not True


def test_team_member_with_orphaned_owner_is_not_blocked(monkeypatch, patched_mongo):
    """If the owner user doc has been deleted (rare edge case), fail open.
    Team deactivation lifecycle handles the cleanup elsewhere."""
    _, storage = patched_mongo
    _seed_team_member(storage, owner_status="active")
    # Remove the owner doc to simulate orphan
    storage["users"] = [u for u in storage["users"] if u["_id"] != OWNER_OID]
    _patch_token(monkeypatch, "teammember@example.com")

    credentials = SimpleNamespace(credentials="token")
    request = SimpleNamespace(url=SimpleNamespace(path="/admin/planner"), cookies={})

    user = _run(auth_extended.get_current_user_extended(credentials, request))
    assert user.user_data.get("_subscription_blocked") is not True
