import json
from types import SimpleNamespace

import pytest

from app.api.admin_auth import get_current_user_profile
from app.dependencies.auth_extended import ExtendedAuthUser
from app.utils.migrations import (
    Migration003,
    migration_008_strip_non_planner_billing_fields,
)
from app.utils.planner_billing_scope import (
    PLANNER_BILLING_USER_FIELDS,
    planner_billing_unset_fields,
    strip_planner_billing_fields,
)


def test_strip_planner_billing_fields_removes_planner_only_state():
    user_data = {
        "email": "root@example.com",
        "role": "ROOT_ADMIN",
        "subscription_status": "inactive",
        "subscription_tier": "free",
        "plan_id": "plan_signature",
        "trial_end_date": "2026-04-30T00:00:00Z",
        "stripe_customer_id": "cus_123",
        "first_name": "Root",
    }

    sanitized = strip_planner_billing_fields(user_data)

    assert sanitized == {
        "email": "root@example.com",
        "role": "ROOT_ADMIN",
        "first_name": "Root",
    }


@pytest.mark.asyncio
async def test_root_admin_profile_omits_planner_billing_fields(monkeypatch):
    monkeypatch.setenv("ROOT_ADMIN_EMAIL", "root@example.com")
    current_user = ExtendedAuthUser(
        email="root@example.com",
        role="ROOT_ADMIN",
        user_data={
            "_id": "user_root",
            "email": "root@example.com",
            "role": "ROOT_ADMIN",
            "subscription_status": "inactive",
            "subscription_tier": "free",
            "plan_id": "plan_signature",
            "trial_end_date": "2026-04-30T00:00:00Z",
            "first_name": "Root",
        },
    )

    response = await get_current_user_profile(current_user)
    payload = json.loads(response.body)

    assert payload["is_root_admin"] is True
    assert payload["subscription_status"] is None
    assert payload["trial_end_date"] is None
    assert payload["user_data"]["first_name"] == "Root"
    for field in (
        "subscription_status",
        "subscription_tier",
        "plan_id",
        "trial_end_date",
    ):
        assert field not in payload["user_data"]


class _FakeCollection:
    def __init__(self):
        self.calls = []

    async def update_many(self, query, update):
        self.calls.append((query, update))
        return SimpleNamespace(modified_count=0)


class _FakeDb(dict):
    def __getitem__(self, key):
        return super().__getitem__(key)


@pytest.mark.asyncio
async def test_migration_003_backfills_only_planners():
    users = _FakeCollection()
    db = _FakeDb(users=users)

    await Migration003.up(db)

    assert len(users.calls) == 1
    query, update = users.calls[0]
    assert query == {
        "role": "wedding_planner",
        "subscription_status": {"$exists": False},
    }
    assert update["$set"]["subscription_status"] == "inactive"
    assert update["$set"]["subscription_tier"] == "free"


@pytest.mark.asyncio
async def test_migration_008_strips_billing_fields_from_non_planners():
    users = _FakeCollection()
    db = _FakeDb(users=users)

    await migration_008_strip_non_planner_billing_fields(db)

    assert len(users.calls) == 1
    query, update = users.calls[0]
    assert query["role"] == {"$ne": "wedding_planner"}
    assert len(query["$or"]) == len(PLANNER_BILLING_USER_FIELDS)
    assert update == {"$unset": planner_billing_unset_fields()}
