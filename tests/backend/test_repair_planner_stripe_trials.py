from datetime import datetime, timedelta, timezone
import os
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.models.subscription import SubscriptionStatus  # noqa: E402
import app.scripts.repair_planner_stripe_trials as repair_script  # noqa: E402
from app.scripts.repair_planner_stripe_trials import (  # noqa: E402
    archive_orphan_subscriptions,
    build_plan_snapshot,
    can_create_missing_trial_subscription,
    choose_local_subscription,
    determine_trial_days,
    local_trial_already_expired,
    patch_legacy_user_trial_fields,
    is_repair_candidate,
    sync_existing_stripe_subscription,
)


def _matches(doc, query):
    for key, expected in query.items():
        actual = doc.get(key)
        if isinstance(expected, dict):
            if "$exists" in expected and ((key in doc) != expected["$exists"]):
                return False
            continue
        if actual != expected:
            return False
    return True


class FakeCursor:
    def __init__(self, docs):
        self.docs = list(docs)

    def sort(self, *_args, **_kwargs):
        return self

    def limit(self, limit):
        self.docs = self.docs[:limit]
        return self

    async def to_list(self, length=None):
        if length is None:
            return list(self.docs)
        return list(self.docs[:length])


class FakeCollection:
    def __init__(self, docs):
        self.docs = docs
        self.updates = []

    async def find_one(self, query, projection=None):
        for doc in self.docs:
            if _matches(doc, query):
                if projection:
                    return {key: doc[key] for key in projection if key in doc}
                return doc
        return None

    def find(self, query):
        return FakeCursor(doc for doc in self.docs if _matches(doc, query))

    async def update_one(self, query, update, **_kwargs):
        self.updates.append((query, update))
        for doc in self.docs:
            if _matches(doc, query):
                for key, value in update.get("$set", {}).items():
                    doc[key] = value
                return


def test_repair_candidate_skips_root_admin_and_non_planner_roles():
    root_email = "root@example.com"

    assert not is_repair_candidate(
        {"email": root_email, "role": "ROOT_ADMIN"}, root_email
    )
    assert not is_repair_candidate(
        {"email": root_email.upper(), "role": "wedding_planner"}, root_email
    )
    assert not is_repair_candidate(
        {"email": "team@example.com", "role": "team_member"}, root_email
    )
    assert is_repair_candidate(
        {"email": "planner@example.com", "role": "wedding_planner"}, root_email
    )


def test_determine_trial_days_preserves_remaining_local_trial_window():
    now = datetime(2026, 4, 30, tzinfo=timezone.utc)
    user = {
        "subscription_status": "trial",
        "trial_end_date": now + timedelta(days=9, hours=2),
    }
    plan = {"trial_days": 30}

    assert determine_trial_days(user, plan, now) == 10


def test_determine_trial_days_uses_plan_trial_when_user_is_not_in_trial():
    now = datetime(2026, 4, 30, tzinfo=timezone.utc)
    user = {"subscription_status": "pending_payment", "trial_end_date": None}
    plan = {"trial_days": 30}

    assert determine_trial_days(user, plan, now) == 30
    assert determine_trial_days(user, plan, now, override_trial_days=14) == 14


def test_missing_subscription_creation_is_not_allowed_for_paid_or_expired_accounts():
    assert can_create_missing_trial_subscription(
        {"subscription_status": SubscriptionStatus.PENDING_PAYMENT.value}
    )
    assert can_create_missing_trial_subscription(
        {"subscription_status": SubscriptionStatus.TRIAL.value}
    )
    assert not can_create_missing_trial_subscription(
        {"subscription_status": SubscriptionStatus.ACTIVE.value}
    )
    assert not can_create_missing_trial_subscription(
        {"subscription_status": SubscriptionStatus.EXPIRED.value}
    )
    assert can_create_missing_trial_subscription(
        {"subscription_status": SubscriptionStatus.EXPIRED.value},
        include_expired=True,
    )


def test_choose_local_subscription_prefers_stripe_backed_record():
    older_without_stripe = {
        "status": "trial",
        "updated_at": datetime(2026, 4, 29, tzinfo=timezone.utc),
    }
    newer_without_stripe = {
        "status": "pending_payment",
        "updated_at": datetime(2026, 4, 30, tzinfo=timezone.utc),
    }
    stripe_backed = {
        "status": "expired",
        "stripe_subscription_id": "sub_123",
        "updated_at": datetime(2026, 4, 28, tzinfo=timezone.utc),
    }

    assert (
        choose_local_subscription(
            [older_without_stripe, newer_without_stripe, stripe_backed]
        )
        is stripe_backed
    )


def test_build_plan_snapshot_contains_stripe_price_ids():
    now = datetime(2026, 4, 30, tzinfo=timezone.utc)
    plan = {
        "name": "Signature",
        "max_weddings": 10,
        "max_guests_per_wedding": 350,
        "ai_credits_monthly": 300,
        "storage_gb": 50,
        "staff_seats": 3,
        "features": {"guest_management": True},
        "price_monthly": 59,
        "price_yearly": 590,
        "stripe_price_id_monthly": "price_month",
        "stripe_price_id_yearly": "price_year",
    }

    snapshot = build_plan_snapshot(plan, now)

    assert snapshot["plan_name"] == "Signature"
    assert snapshot["stripe_price_id_monthly"] == "price_month"
    assert snapshot["stripe_price_id_yearly"] == "price_year"
    assert snapshot["snapshot_date"] == now


async def test_patch_legacy_user_trial_fields_seeds_trial_cron_shape():
    now = datetime(2026, 4, 30, tzinfo=timezone.utc)
    user = {
        "_id": "user_123",
        "email": "planner@example.com",
        "role": "wedding_planner",
        "created_at": now - timedelta(days=20),
    }
    sub = {
        "user_id": "user_123",
        "status": "trial",
        "current_period_end": now + timedelta(days=5),
    }
    plan = {"trial_days": 30}
    users = FakeCollection([user])
    db = {"users": users}
    actions = []
    warnings = []

    await patch_legacy_user_trial_fields(
        db,
        user,
        sub,
        plan,
        apply=True,
        actions=actions,
        warnings=warnings,
    )

    assert user["subscription_status"] == "trial"
    assert user["trial_end_date"] == sub["current_period_end"]
    assert user["trial_warning_sent"] is False
    assert user["is_active"] is True
    assert actions == ["patch legacy users trial fields for trial maintenance"]
    assert users.updates
    assert warnings == []


async def test_patch_legacy_user_trial_fields_warns_for_unverified_public_signup():
    now = datetime(2026, 4, 30, tzinfo=timezone.utc)
    user = {
        "_id": "user_123",
        "email": "planner@example.com",
        "role": "wedding_planner",
        "subscription_status": "trial",
        "trial_end_date": now + timedelta(days=5),
        "email_verified": False,
        "registration_source": "public_signup",
    }
    users = FakeCollection([user])
    warnings = []

    await patch_legacy_user_trial_fields(
        {"users": users},
        user,
        {"status": "trial", "current_period_end": now + timedelta(days=5)},
        {"trial_days": 30},
        apply=False,
        actions=[],
        warnings=warnings,
    )

    assert "public signup email_verified is not true" in warnings[0]


async def test_archive_orphan_subscriptions_marks_missing_user_rows():
    existing_user_id = "507f1f77bcf86cd799439011"
    orphan_user_id = "507f1f77bcf86cd799439012"
    orphan_sub = {
        "_id": "sub_orphan",
        "user_id": orphan_user_id,
        "user_email": "unknown@migration.backfill",
        "status": "unknown",
    }
    active_sub = {
        "_id": "sub_active",
        "user_id": existing_user_id,
        "user_email": "planner@example.com",
        "status": "trial",
    }
    db = {
        "users": FakeCollection(
            [{"_id": existing_user_id, "email": "planner@example.com"}]
        ),
        "user_subscriptions": FakeCollection([orphan_sub, active_sub]),
    }

    results = await archive_orphan_subscriptions(db, apply=True)

    assert len(results) == 1
    assert results[0].email == "unknown@migration.backfill"
    assert orphan_sub["archived_reason"] == "orphan_user_subscription"
    assert orphan_sub["archived_by"] == "system:stripe_trial_repair"
    assert "archived_at" in orphan_sub
    assert "archived_at" not in active_sub


def test_local_expired_legacy_trial_does_not_get_new_stripe_trial_window():
    now = datetime(2026, 4, 30, tzinfo=timezone.utc)
    user = {
        "subscription_status": "trial",
        "trial_end_date": now - timedelta(days=1),
    }
    sub = {"status": "trial"}
    plan = {"trial_days": 30}

    assert local_trial_already_expired(user, sub, plan, now)


async def test_existing_stripe_subscription_sync_fails_closed_on_owner_mismatch(
    monkeypatch,
):
    monkeypatch.setattr(
        repair_script.stripe.Subscription,
        "retrieve",
        lambda _: {
            "id": "sub_123",
            "customer": "cus_123",
            "metadata": {"user_id": "user_a"},
        },
    )
    db = {
        "user_subscriptions": FakeCollection(
            [{"stripe_subscription_id": "sub_123", "user_id": "user_b"}]
        ),
        "stripe_customers": FakeCollection([]),
    }

    with pytest.raises(ValueError, match="mapped to user user_b"):
        await sync_existing_stripe_subscription(
            None,
            db,
            {"_id": "user_a"},
            "plan_signature",
            "sub_123",
            apply=False,
            actions=[],
        )
