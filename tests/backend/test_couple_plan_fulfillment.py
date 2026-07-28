"""Couple Plan — One Wedding webhook fulfillment tests.

Mirrors the fake-mongo pattern of test_stripe_checkout_lifecycle.py.

Covers:
- paid couple-price session → wedding workspace + portal account + payment
  record + welcome email (routed through StripeService's mode=payment branch)
- duplicate delivery → idempotent (no second wedding/couple/payment/email)
- unmatched one-time price → acknowledged no-op, zero writes
- email already backing an existing couple portal → support path, payment
  never dropped
- welcome email failure → raises (Stripe retries), retry resends email only
- self-serve couples are never owner-blocked by the couple lifecycle service
"""

import asyncio
import os
import sys
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from bson import ObjectId

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import app.services.couple_lifecycle_service as couple_lifecycle_module  # noqa: E402
import app.services.couple_plan_fulfillment_service as fulfillment_module  # noqa: E402
import app.services.stripe_service as stripe_service_module  # noqa: E402

COUPLE_PRICE_ID = "price_couple_199_test"
OTHER_PRICE_ID = "price_vendor_milestone_test"


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
            if "$gt" in expected and not (
                actual is not None and actual > expected["$gt"]
            ):
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
                return SimpleNamespace(modified_count=1)
        return SimpleNamespace(modified_count=0)


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

    def get_weddings_collection(self):
        self.storage_map.setdefault("weddings", [])
        return AsyncCollection(self.storage_map["weddings"])


class DummyEmailService:
    def __init__(self):
        self.configured = True
        self.sent = []
        self.fail_next = False

    async def send_email(self, **kwargs):
        if self.fail_next:
            self.fail_next = False
            return {"success": False, "error": "simulated resend outage"}
        self.sent.append(kwargs)
        return {"success": True, "id": f"email_{len(self.sent)}"}


def _couple_session(session_id="cs_couple_1", email="amara.jide@example.com"):
    return {
        "id": session_id,
        "mode": "payment",
        "payment_status": "paid",
        "amount_total": 19900,
        "currency": "usd",
        "payment_intent": "pi_couple_1",
        "customer": "cus_couple_1",
        "customer_details": {"email": email, "name": "Amara Obi"},
        "custom_fields": [
            {
                "key": "partnernames",
                "type": "text",
                "text": {"value": "Amara & Jide"},
            },
            {
                "key": "weddingdate",
                "type": "text",
                "text": {
                    "value": (datetime.now(UTC) + timedelta(days=200)).strftime(
                        "%Y-%m-%d"
                    )
                },
            },
        ],
        "metadata": {},
    }


@pytest.fixture
def fulfillment_env(monkeypatch):
    storage = {
        "couple_users": [],
        "weddings": [],
        "payment_records": [],
        "couple_plan_fulfillment_issues": [],
        "users": [],
        "user_subscriptions": [],
        "subscription_plans": [],
        "stripe_customers": [],
    }
    fake_mongo = FakeMongo(storage)
    monkeypatch.setattr(fulfillment_module, "mongo", fake_mongo)
    monkeypatch.setattr(stripe_service_module, "mongo", fake_mongo)
    monkeypatch.setattr(
        fulfillment_module.settings,
        "frontend_url",
        "https://thespecialwedding.io",
        raising=False,
    )
    monkeypatch.setenv("STRIPE_COUPLE_LIFETIME_PRICE_ID", COUPLE_PRICE_ID)
    monkeypatch.setenv("RESEND_TO_EMAIL", "support@thespecialwedding.io")

    email_service = DummyEmailService()
    monkeypatch.setattr(
        fulfillment_module.couple_plan_fulfillment_service,
        "email_service",
        email_service,
    )

    stripe_service = stripe_service_module.StripeService()
    monkeypatch.setattr(stripe_service, "_ensure_stripe_enabled", lambda: None)

    def fake_list_line_items(session_id, limit=100):
        return SimpleNamespace(data=[{"price": {"id": COUPLE_PRICE_ID}}])

    monkeypatch.setattr(
        stripe_service_module.stripe.checkout.Session,
        "list_line_items",
        staticmethod(fake_list_line_items),
    )

    return stripe_service, storage, email_service, monkeypatch


def test_paid_couple_session_provisions_workspace(fulfillment_env):
    stripe_service, storage, email_service, _ = fulfillment_env

    result = asyncio.run(
        stripe_service._handle_checkout_completed(_couple_session())
    )

    assert result["status"] == "success"

    weddings = storage["weddings"]
    assert len(weddings) == 1
    wedding = weddings[0]
    assert wedding["self_serve_couple"] is True
    assert wedding["couple_portal_enabled"] is True
    assert wedding["couple_names"] == "Amara & Jide"
    assert wedding["status"] == "active"
    assert wedding["assigned_planner_id"] is None
    assert wedding["stripe_checkout_session_id"] == "cs_couple_1"
    assert wedding["wedding_date_confirmed"] is True

    couples = storage["couple_users"]
    assert len(couples) == 1
    couple = couples[0]
    assert couple["email"] == "amara.jide@example.com"
    assert couple["self_serve"] is True
    assert couple["wedding_id"] == str(wedding["_id"])
    assert couple["access_state"] == "pending_setup"
    assert couple["setup_completed"] is False
    assert couple["invite_token"]
    assert couple["welcome_email_sent"] is True
    assert couple["partner1_name"] == "Amara"
    assert couple["partner2_name"] == "Jide"

    payments = storage["payment_records"]
    assert len(payments) == 1
    payment = payments[0]
    assert payment["amount"] == 199.0
    assert payment["purpose"] == "couple_plan_purchase"
    assert payment["category_id"] == "platform:couple_plan"
    assert payment["status"] == "completed"
    assert payment["stripe_checkout_session_id"] == "cs_couple_1"

    assert len(email_service.sent) == 1
    welcome = email_service.sent[0]
    assert welcome["to_email"] == "amara.jide@example.com"
    assert f"/couple/setup/{couple['invite_token']}" in welcome["html_content"]
    # No lifetime-access claims in the welcome email.
    assert "lifetime" not in welcome["html_content"].lower()
    assert "90 days after your wedding" in welcome["html_content"]

    # No support issue was opened.
    assert storage["couple_plan_fulfillment_issues"] == []


def test_duplicate_delivery_is_idempotent(fulfillment_env):
    stripe_service, storage, email_service, _ = fulfillment_env

    first = asyncio.run(stripe_service._handle_checkout_completed(_couple_session()))
    second = asyncio.run(stripe_service._handle_checkout_completed(_couple_session()))

    assert first["status"] == "success"
    assert second["status"] == "already_fulfilled"
    assert len(storage["weddings"]) == 1
    assert len(storage["couple_users"]) == 1
    assert len(storage["payment_records"]) == 1
    assert len(email_service.sent) == 1


def test_unmatched_one_time_price_is_noop(fulfillment_env):
    stripe_service, storage, email_service, monkeypatch = fulfillment_env

    def other_price_line_items(session_id, limit=100):
        return SimpleNamespace(data=[{"price": {"id": OTHER_PRICE_ID}}])

    monkeypatch.setattr(
        stripe_service_module.stripe.checkout.Session,
        "list_line_items",
        staticmethod(other_price_line_items),
    )

    result = asyncio.run(
        stripe_service._handle_checkout_completed(
            _couple_session(session_id="cs_vendor_1")
        )
    )

    assert result["status"] == "ignored_unmatched_one_time_price"
    assert result["price_ids"] == [OTHER_PRICE_ID]
    assert storage["weddings"] == []
    assert storage["couple_users"] == []
    assert storage["payment_records"] == []
    assert email_service.sent == []


def test_existing_couple_email_routes_to_support(fulfillment_env):
    stripe_service, storage, email_service, _ = fulfillment_env
    storage["couple_users"].append(
        {
            "_id": ObjectId(),
            "email": "amara.jide@example.com",
            "wedding_id": "wedding_existing_1",
            "setup_completed": True,
        }
    )

    result = asyncio.run(stripe_service._handle_checkout_completed(_couple_session()))

    assert result["status"] == "flagged_for_support"
    assert result["reason"] == "email_already_linked_to_couple_portal"

    # The paid session is never dropped: payment recorded + issue opened.
    assert len(storage["payment_records"]) == 1
    assert storage["payment_records"][0]["flagged_for_support"] is True
    issues = storage["couple_plan_fulfillment_issues"]
    assert len(issues) == 1
    assert issues[0]["stripe_checkout_session_id"] == "cs_couple_1"
    assert issues[0]["existing_wedding_id"] == "wedding_existing_1"
    assert issues[0]["resolved"] is False

    # No second portal / workspace was created.
    assert len(storage["couple_users"]) == 1
    assert storage["weddings"] == []

    # Support alert + customer acknowledgement both went out.
    recipients = [m["to_email"] for m in email_service.sent]
    assert "support@thespecialwedding.io" in recipients
    assert "amara.jide@example.com" in recipients

    # Replay of the same session stays idempotent.
    replay = asyncio.run(stripe_service._handle_checkout_completed(_couple_session()))
    assert replay["status"] == "already_flagged_for_support"
    assert len(storage["couple_plan_fulfillment_issues"]) == 1
    assert len(storage["payment_records"]) == 1


def test_welcome_email_failure_raises_then_retry_resends(fulfillment_env):
    stripe_service, storage, email_service, _ = fulfillment_env
    email_service.fail_next = True

    with pytest.raises(RuntimeError):
        asyncio.run(stripe_service._handle_checkout_completed(_couple_session()))

    # Workspace was provisioned but the email is still owed.
    assert len(storage["couple_users"]) == 1
    assert storage["couple_users"][0]["welcome_email_sent"] is False
    assert email_service.sent == []

    # Stripe retry: same session id → resend the email, no duplicate writes.
    retry = asyncio.run(stripe_service._handle_checkout_completed(_couple_session()))
    assert retry["status"] == "already_fulfilled"
    assert len(email_service.sent) == 1
    assert storage["couple_users"][0]["welcome_email_sent"] is True
    assert len(storage["weddings"]) == 1
    assert len(storage["payment_records"]) == 1


def test_self_serve_couple_is_never_owner_blocked(monkeypatch):
    storage = {
        "couple_users": [],
        "weddings": [],
        "users": [],
        "user_subscriptions": [],
    }
    fake_mongo = FakeMongo(storage)
    monkeypatch.setattr(couple_lifecycle_module, "mongo", fake_mongo)

    service = couple_lifecycle_module.CoupleLifecycleService()

    self_serve_couple = {
        "email": "amara.jide@example.com",
        "wedding_id": "wedding_self_serve_1",
        "self_serve": True,
        "setup_completed": False,
        "access_state": "pending_setup",
    }

    # Without the self-serve short-circuit a missing planner owner blocks the
    # portal as "owner cancelled" — a self-serve couple must instead resolve
    # to plain pending_setup so /couple/setup/{token} lets them through.
    access = asyncio.run(service.resolve_effective_state(self_serve_couple))
    assert access["state"] == "pending_setup"

    # And once setup completes, the portal is fully active.
    active_couple = {
        **self_serve_couple,
        "setup_completed": True,
        "is_active": True,
        "access_state": "active",
    }
    access = asyncio.run(service.resolve_effective_state(active_couple))
    assert access["state"] == "active"
    assert access["blocked"] is False

    # Wedding-level flag alone is honored too (couple doc predates the flag).
    flagless_couple = {**active_couple}
    flagless_couple.pop("self_serve")
    wedding = {"_id": "wedding_self_serve_1", "self_serve_couple": True}
    access = asyncio.run(
        service.resolve_effective_state(flagless_couple, wedding=wedding)
    )
    assert access["state"] == "active"
