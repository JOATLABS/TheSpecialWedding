import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.subscription_service import SubscriptionService  # noqa: E402


def _plan(plan_id: str = "legacy_solo", *, is_active: bool = False) -> dict:
    return {
        "_id": plan_id,
        "name": "Solo",
        "description": "Historical Solo terms",
        "price_monthly": 19,
        "price_yearly": 190,
        "max_weddings": 1,
        "max_guests_per_wedding": 250,
        "ai_credits_monthly": 50,
        "storage_gb": 5,
        "staff_seats": 1,
        "features_list": ["Modern feature not in the grandfathered snapshot"],
        "is_active": is_active,
    }


@pytest.mark.asyncio
async def test_authenticated_owner_can_read_retained_billing_plan(monkeypatch):
    from app.api import subscription_management

    class FakeService:
        async def get_user_billing_plan(self, user_id):
            assert user_id == "user_123"
            return _plan()

    monkeypatch.setattr(
        subscription_management,
        "subscription_service",
        FakeService(),
    )
    current_user = SimpleNamespace(
        is_root_admin=False,
        user_data={"_id": "user_123"},
    )

    response = await subscription_management.get_user_subscription_plan(
        "user_123",
        current_user,
    )

    assert response["id"] == "legacy_solo"
    assert response["price_monthly"] == 19
    assert response["is_active"] is False
    assert "stripe_product_id" not in response


@pytest.mark.asyncio
async def test_retained_billing_plan_rejects_cross_user_read(monkeypatch):
    from app.api import subscription_management

    class FakeService:
        async def get_user_billing_plan(self, _user_id):
            raise AssertionError("authorization must fail before the plan lookup")

    monkeypatch.setattr(
        subscription_management,
        "subscription_service",
        FakeService(),
    )
    current_user = SimpleNamespace(
        is_root_admin=False,
        user_data={"_id": "user_123"},
    )

    with pytest.raises(HTTPException) as exc:
        await subscription_management.get_user_subscription_plan(
            "user_456",
            current_user,
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_public_plan_detail_hides_inactive_retained_alias(monkeypatch):
    from app.api import subscription_management

    class FakeService:
        async def get_plan(self, plan_id):
            assert plan_id == "legacy_solo"
            return _plan()

    monkeypatch.setattr(
        subscription_management,
        "subscription_service",
        FakeService(),
    )

    with pytest.raises(HTTPException) as exc:
        await subscription_management.get_public_subscription_plan("legacy_solo")

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_billing_plan_service_prefers_active_subscription_identity():
    class FakeSubscriptions:
        async def find_one(self, query, projection):
            assert query == {
                "user_id": "user_123",
                "status": {"$in": ["active", "trial", "trial_expiring"]},
            }
            assert projection == {"plan_id": 1, "plan_snapshot": 1}
            return {
                "plan_id": "legacy_solo",
                "plan_snapshot": {
                    "plan_name": "Solo (grandfathered)",
                    "price_monthly": 9,
                    "max_weddings": 1,
                    "max_weddings_lifetime": True,
                    "storage_gb": 2,
                    "features": {"vendor_management": False},
                },
            }

    class FakeUsers:
        async def find_one(self, *_args, **_kwargs):
            raise AssertionError("active subscription identity must win")

    class FakePlans:
        async def find_one(self, query):
            assert query == {"_id": "legacy_solo"}
            return _plan(is_active=True)

    service = SubscriptionService.__new__(SubscriptionService)
    service.subscriptions_collection = FakeSubscriptions()
    service.users_collection = FakeUsers()
    service.plans_collection = FakePlans()

    plan = await service.get_user_billing_plan("user_123")

    assert plan is not None
    assert plan["_id"] == "legacy_solo"
    assert plan["name"] == "Solo (grandfathered)"
    assert plan["price_monthly"] == 9
    assert plan["max_weddings"] == 1
    assert plan["storage_gb"] == 2
    assert plan["features"] == {"vendor_management": False}
    assert plan["description"] == (
        "Your saved Solo (grandfathered) subscription terms."
    )
    assert plan["features_list"] == [
        "1 wedding (lifetime)",
        "250 guests per wedding",
        "1 staff seat",
        "50 AI credits/month",
        "2GB guest memories storage",
    ]


@pytest.mark.asyncio
async def test_inactive_subscription_without_snapshot_uses_safe_retained_copy():
    class FakeSubscriptions:
        async def find_one(self, _query, _projection):
            return {"plan_id": "legacy_solo"}

    class FakeUsers:
        async def find_one(self, *_args, **_kwargs):
            raise AssertionError("existing subscription must remain authoritative")

    class FakePlans:
        async def find_one(self, _query):
            return _plan()

    service = SubscriptionService.__new__(SubscriptionService)
    service.subscriptions_collection = FakeSubscriptions()
    service.users_collection = FakeUsers()
    service.plans_collection = FakePlans()

    plan = await service.get_user_billing_plan("user_123")

    assert plan is not None
    assert plan["description"] == "Your retained Solo subscription terms."
    assert "Modern feature" not in " ".join(plan["features_list"])
    assert plan["features_list"] == [
        "1 wedding",
        "250 guests per wedding",
        "1 staff seat",
        "50 AI credits/month",
        "5GB guest memories storage",
    ]


@pytest.mark.asyncio
async def test_billing_plan_service_uses_active_profile_only_as_last_resort():
    class FakeSubscriptions:
        async def find_one(self, _query, _projection):
            return None

    class FakeUsers:
        async def find_one(self, query, projection):
            assert query == {"_id": "user_123"}
            assert projection == {"plan_id": 1, "subscription_status": 1}
            return {"plan_id": "legacy_solo", "subscription_status": "trialing"}

    class FakePlans:
        async def find_one(self, query):
            assert query == {"_id": "legacy_solo"}
            return _plan()

    service = SubscriptionService.__new__(SubscriptionService)
    service.subscriptions_collection = FakeSubscriptions()
    service.users_collection = FakeUsers()
    service.plans_collection = FakePlans()

    plan = await service.get_user_billing_plan("user_123")

    assert plan is not None
    assert plan["price_monthly"] == 19


@pytest.mark.asyncio
async def test_billing_plan_service_keeps_trial_expiring_snapshot_authoritative():
    class FakeSubscriptions:
        async def find_one(self, query, projection):
            assert query["status"] == {"$in": ["active", "trial", "trial_expiring"]}
            assert projection == {"plan_id": 1, "plan_snapshot": 1}
            return {
                "plan_id": "legacy_solo",
                "plan_snapshot": {"price_monthly": 7},
            }

    class FakeUsers:
        async def find_one(self, *_args, **_kwargs):
            raise AssertionError("trial_expiring must not use profile fallback")

    class FakePlans:
        async def find_one(self, _query):
            return _plan()

    service = SubscriptionService.__new__(SubscriptionService)
    service.subscriptions_collection = FakeSubscriptions()
    service.users_collection = FakeUsers()
    service.plans_collection = FakePlans()

    plan = await service.get_user_billing_plan("user_123")

    assert plan is not None
    assert plan["price_monthly"] == 7


@pytest.mark.asyncio
async def test_billing_plan_service_fails_closed_on_corrupt_subscription_identity():
    class FakeSubscriptions:
        async def find_one(self, _query, _projection):
            return {"status": "active"}

    class FakeUsers:
        async def find_one(self, *_args, **_kwargs):
            raise AssertionError("corrupt subscription must not borrow profile plan_id")

    service = SubscriptionService.__new__(SubscriptionService)
    service.subscriptions_collection = FakeSubscriptions()
    service.users_collection = FakeUsers()

    assert await service.get_user_billing_plan("user_123") is None
