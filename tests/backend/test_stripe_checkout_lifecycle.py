import asyncio
import os
import sys
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from bson import ObjectId

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import app.services.stripe_service as stripe_service_module
import app.services.subscription_service as subscription_service_module


def _matches(document, query):
    for key, expected in query.items():
        actual = document.get(key)
        if isinstance(expected, dict):
            if "$exists" in expected and ((key in document) != expected["$exists"]):
                return False
            if "$lt" in expected and not (
                actual is not None and actual < expected["$lt"]
            ):
                return False
            if "$in" in expected and actual not in expected["$in"]:
                return False
            if "$or" in expected:
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

    async def insert_one(self, document):
        stored = deepcopy(document)
        stored.setdefault("_id", ObjectId())
        self.storage.append(stored)
        return SimpleNamespace(inserted_id=stored["_id"])

    async def update_one(self, query, update, upsert=False, **_kwargs):
        for document in self.storage:
            if _matches(document, query):
                for key, value in update.get("$set", {}).items():
                    document[key] = value
                for key, value in update.get("$setOnInsert", {}).items():
                    document.setdefault(key, value)
                for key in update.get("$unset", {}).keys():
                    document.pop(key, None)
                return SimpleNamespace(modified_count=1)

        if upsert:
            document = {}
            for key, value in query.items():
                if not isinstance(value, dict):
                    document[key] = value
            for key, value in update.get("$setOnInsert", {}).items():
                document[key] = value
            for key, value in update.get("$set", {}).items():
                document[key] = value
            document.setdefault("_id", ObjectId())
            self.storage.append(document)
            return SimpleNamespace(modified_count=1, upserted_id=document["_id"])

        return SimpleNamespace(modified_count=0)

    async def delete_one(self, query):
        for index, document in enumerate(self.storage):
            if _matches(document, query):
                del self.storage[index]
                return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)

    async def find_one_and_update(
        self, query, update, upsert=False, return_document=True, **_kwargs
    ):
        for document in self.storage:
            if _matches(document, query):
                for key, value in update.get("$set", {}).items():
                    document[key] = value
                for key, value in update.get("$setOnInsert", {}).items():
                    document.setdefault(key, value)
                return deepcopy(document)

        if not upsert:
            return None

        new_document = {}
        for key, value in query.items():
            if isinstance(value, dict):
                continue
            new_document[key] = value
        for key, value in update.get("$setOnInsert", {}).items():
            new_document[key] = value
        for key, value in update.get("$set", {}).items():
            new_document[key] = value
        new_document.setdefault("_id", ObjectId())
        self.storage.append(new_document)
        return deepcopy(new_document)


class AsyncDatabase:
    def __init__(self, storage_map):
        self.storage_map = storage_map

    def __getitem__(self, name):
        self.storage_map.setdefault(name, [])
        return AsyncCollection(self.storage_map[name])


class FakeSessionContext:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def start_transaction(self):
        return self


class FakeMongoClient:
    async def start_session(self):
        return FakeSessionContext()


class FakeMongo:
    def __init__(self, storage_map):
        self.storage_map = storage_map
        self.db = AsyncDatabase(storage_map)
        self.client = FakeMongoClient()

    def get_users_collection(self):
        self.storage_map.setdefault("users", [])
        return AsyncCollection(self.storage_map["users"])


class DummyEmailService:
    def __init__(self):
        self.configured = True
        self.sent = []

    async def send_email(self, **kwargs):
        self.sent.append(kwargs)
        return {"success": True, "id": "email_123"}


@pytest.fixture
def stripe_service(monkeypatch):
    storage = {
        "users": [],
        "user_subscriptions": [],
        "subscription_plans": [],
        "stripe_customers": [],
        "notifications": [],
    }
    fake_mongo = FakeMongo(storage)
    monkeypatch.setattr(stripe_service_module, "mongo", fake_mongo)
    monkeypatch.setattr(
        stripe_service_module.settings,
        "frontend_url",
        "http://localhost:3000",
        raising=False,
    )
    monkeypatch.setattr(
        stripe_service_module.settings,
        "resend_billing_email",
        "billing@thespecialwedding.io",
        raising=False,
    )

    service = stripe_service_module.StripeService()
    service.users_collection = fake_mongo.get_users_collection()
    service.subscriptions_collection = fake_mongo.db["user_subscriptions"]
    service.plans_collection = fake_mongo.db["subscription_plans"]
    service.stripe_customers_collection = fake_mongo.db["stripe_customers"]
    service.email_service = DummyEmailService()
    monkeypatch.setattr(service, "_ensure_stripe_enabled", lambda: None)

    return service, storage


def test_create_checkout_session_respects_explicit_zero_trial(
    monkeypatch, stripe_service
):
    service, storage = stripe_service
    user_id = ObjectId()
    storage["users"].append({"_id": user_id, "email": "planner@example.com"})
    storage["subscription_plans"].append(
        {
            "_id": "plan_boutique",
            "name": "Boutique",
            "trial_days": 30,
            "stripe_price_id_monthly": "price_monthly",
            "is_active": True,
        }
    )

    captured = {}

    def fake_checkout_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            id="cs_123", url="https://checkout.test/session", expires_at=1234
        )

    monkeypatch.setattr(
        service,
        "get_or_create_customer",
        lambda **_kwargs: asyncio.sleep(0, result="cus_123"),
    )
    monkeypatch.setattr(
        stripe_service_module.stripe.checkout.Session, "create", fake_checkout_create
    )

    asyncio.run(
        service.create_checkout_session(
            user_id=str(user_id),
            plan_id="plan_boutique",
            billing_interval="monthly",
            success_url="http://localhost:3000/success",
            cancel_url="http://localhost:3000/cancel",
            trial_days=0,
        )
    )

    assert captured["subscription_data"]["metadata"]["trial_days"] == 0
    assert "trial_period_days" not in captured["subscription_data"]


def test_create_checkout_session_uses_plan_trial_when_unspecified(
    monkeypatch, stripe_service
):
    service, storage = stripe_service
    user_id = ObjectId()
    storage["users"].append({"_id": user_id, "email": "planner@example.com"})
    storage["subscription_plans"].append(
        {
            "_id": "plan_boutique",
            "name": "Boutique",
            "trial_days": 30,
            "stripe_price_id_monthly": "price_monthly",
            "is_active": True,
        }
    )

    captured = {}

    def fake_checkout_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            id="cs_123", url="https://checkout.test/session", expires_at=1234
        )

    monkeypatch.setattr(
        service,
        "get_or_create_customer",
        lambda **_kwargs: asyncio.sleep(0, result="cus_123"),
    )
    monkeypatch.setattr(
        stripe_service_module.stripe.checkout.Session, "create", fake_checkout_create
    )

    asyncio.run(
        service.create_checkout_session(
            user_id=str(user_id),
            plan_id="plan_boutique",
            billing_interval="monthly",
            success_url="http://localhost:3000/success",
            cancel_url="http://localhost:3000/cancel",
            trial_days=None,
        )
    )

    assert captured["subscription_data"]["metadata"]["trial_days"] == 30
    assert captured["subscription_data"]["trial_period_days"] == 30


def test_checkout_completed_sends_activation_notification(monkeypatch, stripe_service):
    service, storage = stripe_service
    user_id = ObjectId()
    storage["users"].append(
        {
            "_id": user_id,
            "email": "planner@example.com",
            "first_name": "Planner",
            "email_verified": True,
        }
    )
    storage["subscription_plans"].append(
        {
            "_id": "plan_boutique",
            "name": "Boutique",
        }
    )
    storage["user_subscriptions"].append(
        {
            "_id": ObjectId(),
            "user_id": str(user_id),
            "plan_id": "plan_boutique",
            "stripe_subscription_id": "sub_123",
        }
    )

    async def fake_sync_subscription_state(**_kwargs):
        return {"status": "active", "stripe_status": "active"}

    class FakeSubscriptionService:
        async def initialize_usage_tracking(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(
        service, "_sync_subscription_state", fake_sync_subscription_state
    )
    monkeypatch.setattr(
        stripe_service_module.stripe.Subscription,
        "retrieve",
        lambda subscription_id: {
            "id": subscription_id,
            "status": "active",
            "customer": "cus_123",
            "metadata": {"user_id": str(user_id), "plan_id": "plan_boutique"},
            "items": {"data": []},
        },
    )
    monkeypatch.setattr(
        subscription_service_module, "SubscriptionService", FakeSubscriptionService
    )

    result = asyncio.run(
        service._handle_checkout_completed(
            {
                "id": "cs_123",
                "subscription": "sub_123",
                "customer": "cus_123",
                "payment_status": "paid",
                "amount_total": 2900,
                "currency": "usd",
                "metadata": {"user_id": str(user_id), "plan_id": "plan_boutique"},
            }
        )
    )

    assert result["status"] == "success"
    assert len(storage["notifications"]) == 1
    assert (
        storage["notifications"][0]["metadata"]["notification_type"]
        == "subscription_activation"
    )
    assert service.email_service.sent[0]["email_type"] == "subscription_activation"
    assert (
        service.email_service.sent[0]["from_email"]
        == stripe_service_module.settings.resend_billing_email
    )


def test_billing_notifications_use_dedicated_billing_sender(
    monkeypatch, stripe_service
):
    service, storage = stripe_service
    user_id = ObjectId()
    storage["users"].append(
        {
            "_id": user_id,
            "email": "planner@example.com",
            "first_name": "Planner",
        }
    )
    storage["subscription_plans"].append(
        {
            "_id": "plan_boutique",
            "name": "Boutique",
        }
    )
    storage["user_subscriptions"].append(
        {
            "_id": ObjectId(),
            "user_id": str(user_id),
            "plan_id": "plan_boutique",
            "stripe_subscription_id": "sub_123",
        }
    )

    monkeypatch.setattr(
        stripe_service_module.settings,
        "resend_billing_email",
        "billing@thespecialwedding.io",
        raising=False,
    )

    asyncio.run(
        service._send_payment_notification(
            subscription_id="sub_123",
            notification_type="payment_success",
            invoice={
                "amount_paid": 2900,
                "currency": "usd",
                "invoice_pdf": "https://example.com/invoice.pdf",
            },
        )
    )

    assert service.email_service.sent[0]["email_type"] == "billing_notification"
    assert service.email_service.sent[0]["from_email"] == "billing@thespecialwedding.io"


def test_invoice_paid_skips_initial_subscription_notification(
    monkeypatch, stripe_service
):
    service, storage = stripe_service
    user_id = ObjectId()
    storage["users"].append({"_id": user_id, "email": "planner@example.com"})
    storage["user_subscriptions"].append(
        {
            "_id": ObjectId(),
            "user_id": str(user_id),
            "plan_id": "plan_boutique",
            "stripe_subscription_id": "sub_123",
        }
    )

    async def fake_sync_subscription_state(**_kwargs):
        return {"status": "active"}

    notification_calls = []

    async def fake_send_payment_notification(**kwargs):
        notification_calls.append(kwargs)

    monkeypatch.setattr(
        service, "_sync_subscription_state", fake_sync_subscription_state
    )
    monkeypatch.setattr(
        service, "_send_payment_notification", fake_send_payment_notification
    )
    monkeypatch.setattr(
        stripe_service_module.stripe.Subscription,
        "retrieve",
        lambda subscription_id: {
            "id": subscription_id,
            "status": "active",
            "customer": "cus_123",
            "metadata": {"user_id": str(user_id), "plan_id": "plan_boutique"},
            "items": {"data": []},
        },
    )

    result = asyncio.run(
        service._handle_invoice_paid(
            {
                "id": "in_123",
                "subscription": "sub_123",
                "billing_reason": "subscription_create",
            }
        )
    )

    assert result["notification_skipped"] is True
    assert notification_calls == []


def test_checkout_expired_marks_pending_checkout_records(monkeypatch, stripe_service):
    service, storage = stripe_service
    user_id = ObjectId()
    checkout_created_at = datetime.now(timezone.utc)
    storage["users"].append(
        {
            "_id": user_id,
            "email": "planner@example.com",
            "subscription_status": "pending_checkout",
        }
    )
    storage["user_subscriptions"].append(
        {
            "_id": ObjectId(),
            "user_id": str(user_id),
            "status": "pending_checkout",
            "stripe_checkout_session_id": "cs_expired",
            "stripe_checkout_created_at": checkout_created_at,
        }
    )

    monkeypatch.setattr(
        stripe_service_module.stripe.Subscription,
        "list",
        lambda **_kwargs: SimpleNamespace(data=[]),
    )
    deleted_customers: list[str] = []
    monkeypatch.setattr(
        stripe_service_module.stripe.Customer,
        "delete",
        lambda customer_id: deleted_customers.append(customer_id),
    )

    result = asyncio.run(
        service._handle_checkout_expired(
            {
                "id": "cs_expired",
                "customer": "cus_expired",
                "metadata": {"user_id": str(user_id)},
            }
        )
    )

    assert result["status"] == "processed"
    assert storage["user_subscriptions"][0]["status"] == "expired"
    assert (
        storage["user_subscriptions"][0]["expired_reason"] == "checkout_session_expired"
    )
    assert storage["users"][0]["subscription_status"] == "expired"
    assert deleted_customers == ["cus_expired"]


@pytest.mark.parametrize(
    ("stripe_status", "expected"),
    [
        ("trialing", "trial"),
        ("past_due", "past_due"),
        ("incomplete", "pending_payment"),
        ("incomplete_expired", "expired"),
        ("unpaid", "suspended"),
    ],
)
def test_map_stripe_status_uses_canonical_internal_values(
    stripe_service, stripe_status, expected
):
    service, _storage = stripe_service

    assert service._map_stripe_status(stripe_status) == expected
