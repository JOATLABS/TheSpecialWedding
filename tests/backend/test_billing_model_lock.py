"""Regression tests for the production billing-model decision.

The May 2026 billing decision is explicit: canonical public plans are metered
on the ``wedding_active`` Stripe Meter, while billing-model flips for existing
flat subscriptions remain guarded. These tests keep seed, admin API, and Stripe
sync behavior from drifting back into a half-configured state.
"""

from __future__ import annotations

import ast
import os
import sys
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_unit")


def _matches(document: dict, query: dict) -> bool:
    for key, expected in query.items():
        actual = document.get(key)
        if isinstance(expected, dict):
            if "$in" in expected and actual not in expected["$in"]:
                return False
            continue
        if actual != expected:
            return False
    return True


class FakeCollection:
    def __init__(self, docs: list[dict] | None = None):
        self.docs = [deepcopy(doc) for doc in docs or []]
        self.inserted: list[dict] = []
        self.updated: list[tuple[dict, dict]] = []

    async def find_one(self, query: dict, projection: dict | None = None):
        for doc in self.docs:
            if _matches(doc, query):
                if projection:
                    return {key: doc.get(key) for key in projection}
                return deepcopy(doc)
        return None

    async def count_documents(self, query: dict) -> int:
        return sum(1 for doc in self.docs if _matches(doc, query))

    async def insert_one(self, document: dict):
        self.inserted.append(deepcopy(document))
        self.docs.append(deepcopy(document))
        return type("InsertResult", (), {"inserted_id": document.get("_id")})()

    async def update_one(self, query: dict, update: dict):
        self.updated.append((deepcopy(query), deepcopy(update)))
        for doc in self.docs:
            if _matches(doc, query):
                doc.update(update.get("$set", {}))
                return type("UpdateResult", (), {"modified_count": 1})()
        return type("UpdateResult", (), {"modified_count": 0})()

    async def delete_one(self, query: dict):
        for index, doc in enumerate(self.docs):
            if _matches(doc, query):
                del self.docs[index]
                return type("DeleteResult", (), {"deleted_count": 1})()
        return type("DeleteResult", (), {"deleted_count": 0})()


def _service(
    *, plans: list[dict] | None = None, subscriptions: list[dict] | None = None
):
    from app.services.subscription_service import SubscriptionService

    service = SubscriptionService.__new__(SubscriptionService)
    service.plans_collection = FakeCollection(plans)
    service.subscriptions_collection = FakeCollection(subscriptions)
    service.usage_collection = FakeCollection([])
    service.users_collection = FakeCollection([])
    service.weddings_collection = FakeCollection([])
    return service


def _seed_plan_fields() -> list[dict]:
    seed_path = Path(PROJECT_ROOT) / "scripts" / "seed_subscription_plans.py"
    tree = ast.parse(seed_path.read_text())

    plans_node = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "plans"
            for target in node.targets
        ):
            plans_node = node.value
            break

    assert isinstance(plans_node, ast.List), "Expected module-level `plans = [...]`"

    fields: list[dict] = []
    for plan_node in plans_node.elts:
        assert isinstance(plan_node, ast.Dict)
        plan: dict = {}
        for key_node, value_node in zip(plan_node.keys, plan_node.values):
            if not isinstance(key_node, ast.Constant):
                continue
            key = key_node.value
            if key not in {"_id", "is_metered", "billing_model", "meter_event_name"}:
                continue
            if isinstance(value_node, ast.Name):
                plan[key] = value_node.id
            else:
                plan[key] = ast.literal_eval(value_node)
        fields.append(plan)
    return fields


def test_canonical_public_billing_model_is_metered():
    from app.constants.billing import (
        BILLING_MODEL_METERED,
        CANONICAL_PUBLIC_PLAN_BILLING_MODEL,
        CANONICAL_PUBLIC_PLAN_IDS,
        CANONICAL_PUBLIC_PLAN_METER_EVENT_NAME,
    )

    assert CANONICAL_PUBLIC_PLAN_BILLING_MODEL == BILLING_MODEL_METERED
    assert CANONICAL_PUBLIC_PLAN_METER_EVENT_NAME == "wedding_active"
    assert CANONICAL_PUBLIC_PLAN_IDS == frozenset(
        {"plan_boutique", "plan_signature", "plan_enterprise"}
    )


def test_seed_canonical_plans_declare_metered_billing_model():
    from app.constants.billing import BILLING_MODEL_METERED

    plans = _seed_plan_fields()
    assert len(plans) >= 3

    for plan in plans:
        assert plan["is_metered"] is True
        assert plan["meter_event_name"] in {
            "wedding_active",
            "CANONICAL_PUBLIC_PLAN_METER_EVENT_NAME",
        }
        assert plan.get("billing_model") in {
            BILLING_MODEL_METERED,
            "CANONICAL_PUBLIC_PLAN_BILLING_MODEL",
        }, f"Seed plan {plan.get('_id')} must declare metered billing explicitly"

    seed_src = (
        Path(PROJECT_ROOT) / "scripts" / "seed_subscription_plans.py"
    ).read_text()
    assert '"billing_model"' in seed_src, (
        "The canonical seed upsert must write billing_model so redeploys keep "
        "Mongo aligned with the metered product decision."
    )
    assert "PLAN_BILLING_MODEL_MIGRATION_FLAG" in seed_src, (
        "Seed must fail closed when changing an existing flat plan to metered "
        "while active subscriptions still point at old flat Stripe prices."
    )


def test_system_plan_sync_routes_through_guarded_subscription_service():
    source = (Path(PROJECT_ROOT) / "app/api/subscription_management.py").read_text()

    assert "stripe_service.sync_plan_to_stripe(plan)" not in source, (
        "/system/sync-plans-to-stripe must not bypass "
        "SubscriptionService.update_plan. Otherwise an already-flipped Mongo "
        "plan could be synced to metered Stripe prices even while admin "
        "metering writes are disabled."
    )
    assert 'update_plan(plan["_id"], {})' in source


@pytest.mark.asyncio
async def test_create_plan_defaults_to_metered_wedding_active(monkeypatch):
    service = _service()

    with patch(
        "app.services.subscription_service.stripe_service.sync_plan_to_stripe",
        return_value={"stripe_price_id_monthly": "price_metered"},
    ) as sync_plan:
        await service.create_plan(
            {
                "name": "Metered Experiment",
                "price_monthly": 59,
                "max_weddings": 10,
            },
            "root@example.com",
        )

    synced_plan = sync_plan.call_args.args[0]
    assert synced_plan["billing_model"] == "metered"
    assert synced_plan["is_metered"] is True
    assert synced_plan["meter_event_name"] == "wedding_active"


@pytest.mark.asyncio
async def test_metered_plan_requires_meter_event_name(monkeypatch):
    service = _service()

    with patch(
        "app.services.subscription_service.stripe_service.sync_plan_to_stripe",
        return_value={},
    ) as sync_plan:
        with pytest.raises(HTTPException) as exc_info:
            await service.create_plan(
                {
                    "name": "Metered Experiment",
                    "price_monthly": 59,
                    "is_metered": True,
                    "meter_event_name": "   ",
                    "max_weddings": 10,
                },
                "root@example.com",
            )

    assert exc_info.value.status_code == 400
    assert "meter_event_name" in str(exc_info.value.detail)
    sync_plan.assert_not_called()


@pytest.mark.asyncio
async def test_metered_plan_preserves_stripe_meter_validation_error(monkeypatch):
    service = _service()

    stripe_error = HTTPException(
        status_code=400,
        detail="Metered plan 'plan_metered_experiment' requires a valid Stripe meter_id or meter_event_name",
    )
    with patch(
        "app.services.subscription_service.stripe_service.sync_plan_to_stripe",
        side_effect=stripe_error,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await service.create_plan(
                {
                    "name": "Metered Experiment",
                    "price_monthly": 59,
                    "is_metered": True,
                    "meter_event_name": "wedding_active",
                    "max_weddings": 10,
                },
                "root@example.com",
            )

    assert exc_info.value.status_code == 400
    assert "valid Stripe meter" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_update_plan_rejects_billing_model_flip_with_active_subscriptions(
    monkeypatch,
):
    monkeypatch.delenv("TSW_ALLOW_PLAN_BILLING_MODEL_MIGRATION", raising=False)
    service = _service(
        plans=[
            {
                "_id": "plan_signature",
                "name": "Signature",
                "price_monthly": 59,
                "is_metered": False,
                "billing_model": "flat_rate",
            }
        ],
        subscriptions=[
            {
                "_id": "sub_live",
                "plan_id": "plan_signature",
                "status": "active",
                "stripe_subscription_id": "sub_stripe_live",
            }
        ],
    )

    with patch(
        "app.services.subscription_service.stripe_service.sync_plan_to_stripe",
        return_value={"stripe_price_id_monthly": "price_metered"},
    ) as sync_plan:
        with pytest.raises(HTTPException) as exc_info:
            await service.update_plan(
                "plan_signature",
                {
                    "is_metered": True,
                    "meter_event_name": "wedding_active",
                    "meter_id": "mtr_valid",
                },
            )

    assert exc_info.value.status_code == 409
    assert "active subscriptions" in str(exc_info.value.detail)
    assert "old Stripe prices" in str(exc_info.value.detail)
    sync_plan.assert_not_called()


@pytest.mark.asyncio
async def test_root_admin_can_edit_existing_metered_plan_price_features_and_visibility():
    service = _service(
        plans=[
            {
                "_id": "plan_signature",
                "name": "Signature",
                "price_monthly": 59,
                "price_yearly": 590,
                "is_metered": True,
                "billing_model": "metered",
                "meter_event_name": "wedding_active",
                "features": {"guest_management": True},
                "features_list": ["Guest management"],
                "display_order": 2,
                "sort_order": 2,
            }
        ],
        subscriptions=[
            {
                "_id": "sub_live",
                "plan_id": "plan_signature",
                "status": "active",
                "stripe_subscription_id": "sub_metered_live",
            }
        ],
    )

    with patch(
        "app.services.subscription_service.stripe_service.sync_plan_to_stripe",
        return_value={"stripe_price_id_monthly": "price_metered_79"},
    ) as sync_plan:
        await service.update_plan(
            "plan_signature",
            {
                "price_monthly": 79,
                "features": {"guest_management": True, "qr_checkin": True},
                "features_list": ["Guest management", "QR check-in"],
                "is_active": False,
                "display_order": 4,
                "sort_order": 4,
            },
        )

    synced_plan = sync_plan.call_args.args[0]
    assert synced_plan["billing_model"] == "metered"
    assert synced_plan["is_metered"] is True
    assert synced_plan["meter_event_name"] == "wedding_active"
    assert synced_plan["price_monthly"] == 79

    update = service.plans_collection.updated[0][1]["$set"]
    assert update["price_monthly"] == 79
    assert update["features"] == {"guest_management": True, "qr_checkin": True}
    assert update["features_list"] == ["Guest management", "QR check-in"]
    assert update["is_active"] is False
    assert update["display_order"] == 4


@pytest.mark.asyncio
async def test_delete_canonical_plan_soft_archives_so_admin_removal_survives_seed():
    service = _service(
        plans=[
            {
                "_id": "plan_boutique",
                "name": "Boutique",
                "price_monthly": 29,
                "is_metered": True,
                "billing_model": "metered",
                "meter_event_name": "wedding_active",
                "stripe_product_id": "prod_boutique",
            }
        ],
        subscriptions=[],
    )

    with patch(
        "app.services.subscription_service.stripe_service.archive_stripe_product",
        return_value=None,
    ) as archive_product:
        result = await service.delete_plan("plan_boutique")

    archive_product.assert_called_once_with("prod_boutique")
    assert result["message"] == "Subscription plan archived successfully"
    update = service.plans_collection.updated[0][1]["$set"]
    assert update["is_active"] is False
    assert "deleted_at" in update
