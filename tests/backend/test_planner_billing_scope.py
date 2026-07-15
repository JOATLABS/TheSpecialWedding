import json
from types import SimpleNamespace

import pytest

from app.api.admin_auth import get_current_user_profile
from app.dependencies.auth_extended import ExtendedAuthUser
from app.utils.migrations import (
    Migration003,
    migration_008_strip_non_planner_billing_fields,
    migration_009_classify_support_conversations,
    migration_010_support_ticket_read_states,
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


@pytest.mark.asyncio
async def test_advertising_vendor_profile_exposes_onboarding_fields():
    current_user = ExtendedAuthUser(
        email="vendor@example.com",
        role="advertising_vendor",
        user_data={
            "_id": "vendor_user",
            "email": "vendor@example.com",
            "role": "advertising_vendor",
            "business_name": "Floral Atelier",
            "vendor_account_status": "active",
            "must_change_password": True,
            "logo_url": "https://ads.example.com/vendor-profiles/vendor_user/logo/logo.png",
        },
    )

    response = await get_current_user_profile(current_user)
    payload = json.loads(response.body)

    assert payload["role"] == "advertising_vendor"
    assert payload["business_name"] == "Floral Atelier"
    assert payload["vendor_account_status"] == "active"
    assert payload["must_change_password"] is True
    assert payload["logo_url"] == (
        "https://ads.example.com/vendor-profiles/vendor_user/logo/logo.png"
    )
    assert payload["user_data"]["must_change_password"] is True


class _FakeCollection:
    def __init__(self):
        self.calls = []

    async def update_many(self, query, update):
        self.calls.append((query, update))
        return SimpleNamespace(modified_count=0)

    async def create_index(self, keys, **kwargs):
        self.calls.append(("create_index", keys, kwargs))
        return "index"


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


@pytest.mark.asyncio
async def test_migration_009_classifies_support_and_sms_conversations_fail_closed():
    tickets = _FakeCollection()
    db = _FakeDb(support_tickets=tickets)

    await migration_009_classify_support_conversations(db)

    updates = [call for call in tickets.calls if call[0] != "create_index"]
    assert updates == [
        (
            {
                "conversation_kind": {"$exists": False},
                "source": "sms",
            },
            {"$set": {"conversation_kind": "guest_sms"}},
        ),
        (
            {
                "conversation_kind": {"$exists": False},
                "ticket_number": {"$exists": True, "$nin": [None, ""]},
                "created_by": {"$exists": True, "$nin": [None, ""]},
                "$or": [
                    {"source": {"$exists": False}},
                    {"source": {"$ne": "sms"}},
                ],
            },
            {"$set": {"conversation_kind": "platform_support"}},
        ),
        (
            {"conversation_kind": {"$exists": False}},
            {"$set": {"conversation_kind": "unknown"}},
        ),
    ]
    index_calls = [call for call in tickets.calls if call[0] == "create_index"]
    assert any(call[1] == "conversation_kind" for call in index_calls)
    assert any(
        call[1] == [("conversation_kind", 1), ("status", 1), ("updated_at", -1)]
        for call in index_calls
    )


@pytest.mark.asyncio
async def test_migration_010_indexes_participant_specific_support_read_states():
    read_states = _FakeCollection()
    db = _FakeDb(support_ticket_read_states=read_states)

    await migration_010_support_ticket_read_states(db)

    index_calls = [call for call in read_states.calls if call[0] == "create_index"]
    assert (
        "create_index",
        [("ticket_id", 1), ("actor_key", 1)],
        {"unique": True},
    ) in index_calls
    assert any(
        call[1] == [("actor_key", 1), ("last_read_at", -1)] for call in index_calls
    )
