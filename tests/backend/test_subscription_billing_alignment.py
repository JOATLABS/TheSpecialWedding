from copy import deepcopy
from datetime import datetime, timezone

import pytest

from app.services.subscription_service import SubscriptionService


def _matches(document, query):
    for key, expected in query.items():
        actual = document.get(key)
        if isinstance(expected, dict):
            if "$exists" in expected and ((key in document) != expected["$exists"]):
                return False
            if "$ne" in expected and actual == expected["$ne"]:
                return False
            if "$in" in expected and actual not in expected["$in"]:
                return False
            continue
        if actual != expected:
            return False
    return True


class FakeCursor:
    def __init__(self, docs):
        self.docs = [deepcopy(doc) for doc in docs]

    async def to_list(self, length=None):
        if length is None:
            return self.docs
        return self.docs[:length]


class FakeCollection:
    def __init__(self, docs):
        self.docs = docs

    def find(self, query):
        return FakeCursor(doc for doc in self.docs if _matches(doc, query))

    async def count_documents(self, query):
        return sum(1 for doc in self.docs if _matches(doc, query))

    def aggregate(self, _pipeline):
        return FakeCursor([])


@pytest.mark.asyncio
async def test_list_all_subscriptions_excludes_orphans_and_archived_by_default():
    service = SubscriptionService.__new__(SubscriptionService)
    service.users_collection = FakeCollection(
        [
            {
                "_id": "user_1",
                "email": "planner@example.com",
                "company_name": "Planner Co",
            }
        ]
    )
    service.plans_collection = FakeCollection(
        [
            {
                "_id": "plan_signature",
                "name": "Signature",
                "price_monthly": 59,
                "price_yearly": 590,
            }
        ]
    )
    service.subscriptions_collection = FakeCollection(
        [
            {
                "_id": "sub_live",
                "user_id": "user_1",
                "plan_id": "plan_signature",
                "status": "trial",
                "billing_interval": "monthly",
                "current_period_end": datetime(2026, 5, 30, tzinfo=timezone.utc),
            },
            {
                "_id": "sub_orphan",
                "user_id": "missing_user",
                "user_email": "unknown@migration.backfill",
                "plan_id": "missing_plan",
                "status": "unknown",
                "billing_interval": "monthly",
            },
            {
                "_id": "sub_archived",
                "user_id": "user_1",
                "plan_id": "plan_signature",
                "status": "expired",
                "billing_interval": "monthly",
                "archived_at": datetime(2026, 4, 30, tzinfo=timezone.utc),
            },
        ]
    )

    subscriptions = await service.list_all_subscriptions()

    assert [sub["_id"] for sub in subscriptions] == ["sub_live"]
    assert subscriptions[0]["user_email"] == "planner@example.com"
    assert subscriptions[0]["plan_name"] == "Signature"
    assert subscriptions[0]["amount"] == 59


@pytest.mark.asyncio
async def test_list_all_subscriptions_archived_filter_is_explicit():
    service = SubscriptionService.__new__(SubscriptionService)
    service.users_collection = FakeCollection(
        [
            {
                "_id": "user_1",
                "email": "planner@example.com",
                "company_name": "Planner Co",
            }
        ]
    )
    service.plans_collection = FakeCollection(
        [{"_id": "plan_signature", "name": "Signature", "price_monthly": 59}]
    )
    service.subscriptions_collection = FakeCollection(
        [
            {
                "_id": "sub_live",
                "user_id": "user_1",
                "plan_id": "plan_signature",
                "status": "trial",
            },
            {
                "_id": "sub_archived",
                "user_id": "user_1",
                "plan_id": "plan_signature",
                "status": "expired",
                "archived_at": datetime(2026, 4, 30, tzinfo=timezone.utc),
            },
        ]
    )

    subscriptions = await service.list_all_subscriptions(status_filter="archived")

    assert [sub["_id"] for sub in subscriptions] == ["sub_archived"]
