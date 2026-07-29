"""Couple Plan — One Wedding webhook fulfillment tests.

Mirrors the fake-mongo pattern of test_stripe_checkout_lifecycle.py.

Account model (operator ruling 2026-07-28): the couple-plan purchaser uses the
PLANNER dashboard for their own single wedding — fulfillment provisions a
claimable planner-account invitation (``user_invitations``), NOT a
couple-portal login.

Covers:
- paid couple-price session → wedding workspace (unowned, portal disabled) +
  planner-account invitation + internal plan_couple document + payment record
  + welcome email pointing at /setup-account/{token}
- duplicate delivery → idempotent (no second wedding/invitation/payment/email)
- unmatched one-time price → acknowledged no-op, zero writes
- email already backing an existing dashboard account → support path, payment
  never dropped
- email with a pending admin invitation → support path
- email backing a couple-portal login (separate auth surface) → provisioning
  proceeds, annotated
- welcome email failure → raises (Stripe retries), retry resends email only
- claim: complete_account_setup on the couple invitation → ACTIVE planner
  account on plan_couple (no trial, no pending_payment), local subscription
  with the couple caps in plan_snapshot, wedding ownership attached
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

import app.services.couple_lifecycle_service as couple_lifecycle_module
import app.services.couple_plan_fulfillment_service as fulfillment_module
import app.services.stripe_service as stripe_service_module
import app.services.subscription_service as subscription_service_module
import app.services.user_management_service as user_management_module
from app.constants.billing import COUPLE_PLAN_ID

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
                for key in update.get("$unset", {}):
                    document.pop(key, None)
                return SimpleNamespace(modified_count=1)
        if upsert and "$set" in update:
            stored = {**query, **update["$set"]}
            stored.setdefault("_id", ObjectId())
            self.storage.append(stored)
            return SimpleNamespace(modified_count=0, upserted_id=stored["_id"])
        return SimpleNamespace(modified_count=0)

    async def delete_one(self, query):
        for index, document in enumerate(self.storage):
            if _matches(document, query):
                del self.storage[index]
                return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)


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
        "user_invitations": [],
        "users": [],
        "user_subscriptions": [],
        "subscription_plans": [],
        "usage_tracking": [],
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


def test_paid_couple_session_provisions_planner_invitation(fulfillment_env):
    stripe_service, storage, email_service, _ = fulfillment_env

    result = asyncio.run(stripe_service._handle_checkout_completed(_couple_session()))

    assert result["status"] == "success"

    weddings = storage["weddings"]
    assert len(weddings) == 1
    wedding = weddings[0]
    assert wedding["self_serve_couple"] is True
    assert wedding["couple_names"] == "Amara & Jide"
    assert wedding["status"] == "active"
    # Unowned until the buyer claims the account; NO couple portal — the
    # purchaser IS the couple and works in the planner dashboard.
    assert wedding["assigned_planner_id"] is None
    assert wedding["couple_portal_enabled"] is False
    assert wedding["stripe_checkout_session_id"] == "cs_couple_1"
    assert wedding["wedding_date_confirmed"] is True

    # No couple-portal login is created for a couple-plan workspace.
    assert storage["couple_users"] == []

    invitations = storage["user_invitations"]
    assert len(invitations) == 1
    invitation = invitations[0]
    assert invitation["email"] == "amara.jide@example.com"
    assert invitation["role"] == "wedding_planner"
    assert invitation["status"] == "pending"
    assert invitation["token"]
    assert invitation["welcome_email_sent"] is True
    invite_data = invitation["invite_data"]
    assert invite_data["couple_plan"] is True
    assert invite_data["plan_id"] == COUPLE_PLAN_ID
    assert invite_data["trial_days"] == 0
    assert invite_data["wedding_id"] == str(wedding["_id"])
    assert invite_data["partner1_name"] == "Amara"
    assert invite_data["partner2_name"] == "Jide"

    # The internal entitlement plan was seeded with the four couple gates.
    plans = storage["subscription_plans"]
    assert len(plans) == 1
    plan = plans[0]
    assert plan["_id"] == COUPLE_PLAN_ID
    assert plan["is_active"] is False  # never in the public catalog
    assert plan["max_weddings"] == 1
    assert plan["max_weddings_lifetime"] is True
    assert plan["staff_seats"] == 0
    assert plan["features"]["packages"] is False
    assert plan["features"]["couple_portal"] is False

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
    assert f"/setup-account/{invitation['token']}" in welcome["html_content"]
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
    assert len(storage["user_invitations"]) == 1
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
    assert storage["user_invitations"] == []
    assert storage["payment_records"] == []
    assert email_service.sent == []


def test_existing_account_email_routes_to_support(fulfillment_env):
    stripe_service, storage, email_service, _ = fulfillment_env
    storage["users"].append(
        {
            "_id": ObjectId(),
            "email": "amara.jide@example.com",
            "role": "wedding_planner",
        }
    )

    result = asyncio.run(stripe_service._handle_checkout_completed(_couple_session()))

    assert result["status"] == "flagged_for_support"
    assert result["reason"] == "email_already_linked_to_account"

    # The paid session is never dropped: payment recorded + issue opened.
    assert len(storage["payment_records"]) == 1
    assert storage["payment_records"][0]["flagged_for_support"] is True
    issues = storage["couple_plan_fulfillment_issues"]
    assert len(issues) == 1
    assert issues[0]["stripe_checkout_session_id"] == "cs_couple_1"
    assert issues[0]["resolved"] is False

    # No second account / invitation / workspace was created.
    assert len(storage["users"]) == 1
    assert storage["user_invitations"] == []
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


def test_pending_invitation_email_routes_to_support(fulfillment_env):
    stripe_service, storage, _, _ = fulfillment_env
    storage["user_invitations"].append(
        {
            "_id": ObjectId(),
            "email": "amara.jide@example.com",
            "role": "wedding_planner",
            "status": "pending",
            "invited_by": "root@thespecialwedding.io",
            "expires_at": datetime.now(UTC) + timedelta(days=3),
        }
    )

    result = asyncio.run(stripe_service._handle_checkout_completed(_couple_session()))

    assert result["status"] == "flagged_for_support"
    assert result["reason"] == "pending_invitation_exists"
    assert len(storage["payment_records"]) == 1
    assert len(storage["couple_plan_fulfillment_issues"]) == 1
    # The pre-existing admin invitation is untouched; no competing invite.
    assert len(storage["user_invitations"]) == 1
    assert storage["weddings"] == []


def test_couple_portal_email_overlap_still_provisions(fulfillment_env):
    """A couple-portal login is a separate auth surface — not a conflict."""
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

    assert result["status"] == "success"
    assert len(storage["weddings"]) == 1
    assert len(storage["user_invitations"]) == 1
    invitation = storage["user_invitations"][0]
    assert invitation["invite_data"]["email_matches_couple_portal"] is True
    assert storage["couple_plan_fulfillment_issues"] == []
    assert len(email_service.sent) == 1


def test_welcome_email_failure_raises_then_retry_resends(fulfillment_env):
    stripe_service, storage, email_service, _ = fulfillment_env
    email_service.fail_next = True

    with pytest.raises(RuntimeError):
        asyncio.run(stripe_service._handle_checkout_completed(_couple_session()))

    # Invitation was provisioned but the email is still owed.
    assert len(storage["user_invitations"]) == 1
    assert storage["user_invitations"][0]["welcome_email_sent"] is False
    assert email_service.sent == []

    # Stripe retry: same session id → resend the email, no duplicate writes.
    retry = asyncio.run(stripe_service._handle_checkout_completed(_couple_session()))
    assert retry["status"] == "already_fulfilled"
    assert len(email_service.sent) == 1
    assert storage["user_invitations"][0]["welcome_email_sent"] is True
    assert len(storage["weddings"]) == 1
    assert len(storage["payment_records"]) == 1


def test_claim_creates_active_planner_account_on_couple_plan(fulfillment_env):
    """complete_account_setup on the couple invitation → ACTIVE planner account.

    No trial, no pending_payment (they already paid): the account lands on
    plan_couple with a local-only subscription whose plan_snapshot carries the
    couple caps, and the paid wedding is attached to the new owner.
    """
    stripe_service, storage, _, monkeypatch = fulfillment_env

    result = asyncio.run(stripe_service._handle_checkout_completed(_couple_session()))
    assert result["status"] == "success"
    invitation = storage["user_invitations"][0]
    wedding_id = invitation["invite_data"]["wedding_id"]

    fake_mongo = FakeMongo(storage)
    monkeypatch.setattr(user_management_module, "mongo", fake_mongo)
    monkeypatch.setattr(subscription_service_module, "mongo", fake_mongo)
    monkeypatch.setattr(
        subscription_service_module,
        "subscription_service",
        subscription_service_module.SubscriptionService(),
    )

    service = user_management_module.UserManagementService()

    async def _noop_notify(*args, **kwargs):
        return None

    monkeypatch.setattr(service, "_notify_root_admin_account_created", _noop_notify)

    claim = asyncio.run(
        service.complete_account_setup(
            token=invitation["token"],
            password="CoupleStrongPass!42",
            first_name="Amara",
            last_name="Obi",
        )
    )

    assert claim["subscription_status"] == "active"
    assert claim["role"] == "wedding_planner"

    users = storage["users"]
    assert len(users) == 1
    user = users[0]
    assert user["email"] == "amara.jide@example.com"
    assert user["role"] == "wedding_planner"
    assert user["plan_id"] == COUPLE_PLAN_ID
    assert user["subscription_status"] == "active"

    subs = storage["user_subscriptions"]
    assert len(subs) == 1
    sub = subs[0]
    assert sub["plan_id"] == COUPLE_PLAN_ID
    assert sub["status"] == "active"
    assert sub["stripe_subscription_id"] is None  # local-only, already paid
    snapshot = sub["plan_snapshot"]
    assert snapshot["max_weddings"] == 1
    assert snapshot["max_weddings_lifetime"] is True
    assert snapshot["staff_seats"] == 0
    assert snapshot["features"]["packages"] is False
    assert snapshot["features"]["couple_portal"] is False

    # The paid wedding now belongs to the claimed account.
    wedding = storage["weddings"][0]
    assert str(wedding["_id"]) == wedding_id
    assert wedding["assigned_planner_id"] == str(user["_id"])
    assert wedding["assigned_planner_email"] == "amara.jide@example.com"

    # Invitation is consumed.
    assert storage["user_invitations"][0]["status"] == "completed"


def test_handler_error_result_marks_event_failed_and_replayable(fulfillment_env):
    """An error RESULT must mark the webhook event 'failed', not 'processed'.

    Otherwise a manual Stripe-dashboard resend of the same event id (e.g. a
    couple purchase that landed before fulfillment code deployed) would be
    skipped forever by the idempotency check.
    """
    stripe_service, storage, _, monkeypatch = fulfillment_env
    monkeypatch.setattr(
        stripe_service_module.settings,
        "stripe_webhook_secret",
        "whsec_test",
        raising=False,
    )
    event = {
        "id": "evt_gap_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_gap_1",
                "mode": "subscription",
                "metadata": {},
            }
        },
    }
    monkeypatch.setattr(
        stripe_service_module.stripe.Webhook,
        "construct_event",
        staticmethod(lambda payload, sig, secret: event),
    )

    result = asyncio.run(stripe_service.handle_webhook_event(b"{}", "sig"))
    assert result["status"] == "error"

    rows = storage["stripe_webhook_events"]
    assert len(rows) == 1
    assert rows[0]["status"] == "failed"
    assert "Missing user_id" in rows[0]["error_message"]

    # A resend of the same event id re-enters processing (is NOT skipped).
    replay = asyncio.run(stripe_service.handle_webhook_event(b"{}", "sig"))
    assert replay["status"] == "error"
    assert replay["status"] != "already_processed"


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
