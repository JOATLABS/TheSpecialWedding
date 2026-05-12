"""Regression tests for the production billing-model decision.

The 2026-05-09 pricing strategy refresh ships all canonical public plans as
FLAT (``is_metered=False``). The metering hardening infrastructure
(``stripe_meter_helpers``, ``ensure_stripe_meter``, ``assert_meter_config``)
stays available — flipping a single plan to metered is a deliberate
per-plan edit + redeploy. The guard against changing an existing plan's
billing model while active subscriptions still point at old Stripe prices
also stays in place.

These tests keep seed, admin API, and Stripe sync behavior from drifting
back into a half-configured state.
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


def test_canonical_public_billing_model_is_flat_rate():
    """Pin the 2026-05-09 strategy: canonical public plans ship FLAT.

    The metering infrastructure remains available — a plan can still be
    flipped to metered by setting is_metered=True + meter_event_name on
    that specific plan and redeploying. But the default reflects what we
    actually ship today: a 4-tier flat catalog (Solo / Boutique /
    Signature / Enterprise).
    """
    from app.constants.billing import (
        BILLING_MODEL_FLAT_RATE,
        CANONICAL_PUBLIC_PLAN_BILLING_MODEL,
        CANONICAL_PUBLIC_PLAN_IDS,
        CANONICAL_PUBLIC_PLAN_METER_EVENT_NAME,
    )

    assert CANONICAL_PUBLIC_PLAN_BILLING_MODEL == BILLING_MODEL_FLAT_RATE
    # meter_event_name constant stays "wedding_active" — it's the event
    # name a plan would use if/when it flips to metered, not a statement
    # that any current plan is metered.
    assert CANONICAL_PUBLIC_PLAN_METER_EVENT_NAME == "wedding_active"
    assert CANONICAL_PUBLIC_PLAN_IDS == frozenset(
        {"plan_solo", "plan_boutique", "plan_signature", "plan_enterprise"}
    )


def test_seed_canonical_plans_declare_flat_billing_model():
    """Every default plan in the seed script ships with FLAT billing.

    Solo (the free tier) omits the ``billing_model`` key entirely and
    relies on the seed pipeline's ``_build_effective_seed_plan`` default
    (which resolves to ``CANONICAL_PUBLIC_PLAN_BILLING_MODEL`` → flat).
    Boutique / Signature / Enterprise set it explicitly through the
    same constant. Either way: no metered seed plan, ever.

    If this test fails, either:
    - A plan was intentionally flipped to metered → update this test and
      docs/analysis/METERING_IMPLEMENTATION_2026-05-04.md together, OR
    - A plan was accidentally flipped to metered → revert before merge.
    """
    from app.constants.billing import BILLING_MODEL_FLAT_RATE

    plans = _seed_plan_fields()
    assert len(plans) >= 4, (
        f"Seed catalog shrank below the 4-plan baseline (Solo / Boutique / "
        f"Signature / Enterprise). Got {len(plans)} plans."
    )

    metered_drift = [p for p in plans if p.get("is_metered") is True]
    assert metered_drift == [], (
        f"Seed plans drifted to metered billing: "
        f"{[p.get('_id') for p in metered_drift]}. The 2026-05-09 strategy "
        "ships all plans flat."
    )

    for plan in plans:
        assert plan.get("is_metered") is False, (
            f"Seed plan {plan.get('_id')!r} must ship is_metered=False; "
            f"got {plan.get('is_metered')!r}"
        )
        # Flat plans must NOT carry a meter_event_name — that combination
        # is a half-configured trap (see test_metering_gating.py).
        assert plan.get("meter_event_name") in (None, ""), (
            f"Flat seed plan {plan.get('_id')!r} carries "
            f"meter_event_name={plan.get('meter_event_name')!r}. Either "
            "finish the metered setup or clear the field."
        )
        # billing_model is allowed to be absent on free tiers (Solo);
        # when present it must be flat_rate (or the constant reference
        # that resolves to flat_rate).
        bm = plan.get("billing_model")
        assert bm in (
            None,
            BILLING_MODEL_FLAT_RATE,
            "CANONICAL_PUBLIC_PLAN_BILLING_MODEL",
        ), (
            f"Seed plan {plan.get('_id')!r} declared billing_model={bm!r}; "
            f"expected flat_rate, the canonical constant reference, or omitted."
        )

    seed_src = (
        Path(PROJECT_ROOT) / "scripts" / "seed_subscription_plans.py"
    ).read_text()
    assert '"billing_model"' in seed_src, (
        "The canonical seed upsert must write billing_model so redeploys keep "
        "Mongo aligned with the flat-rate product decision."
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
async def test_create_plan_defaults_to_flat(monkeypatch):
    """Admin creates a plan without specifying is_metered → defaults to FLAT.

    Matches the 2026-05-09 strategy: new plans are flat unless deliberately
    opted in to metering. The Pydantic ``CreateSubscriptionPlanRequest``
    model defaults ``is_metered`` to False; the service's
    ``_normalize_plan_billing_fields`` also defaults to False so dict-based
    callsites stay aligned.
    """
    service = _service()

    with patch(
        "app.services.subscription_service.stripe_service.sync_plan_to_stripe",
        return_value={"stripe_price_id_monthly": "price_flat"},
    ) as sync_plan:
        await service.create_plan(
            {
                "name": "Default Plan",
                "price_monthly": 59,
                "max_weddings": 10,
            },
            "root@example.com",
        )

    synced_plan = sync_plan.call_args.args[0]
    assert synced_plan["billing_model"] == "flat_rate"
    assert synced_plan["is_metered"] is False
    # Flat plans must not carry a meter_event_name — half-configured trap.
    assert synced_plan.get("meter_event_name") in (None, "")


@pytest.mark.asyncio
async def test_create_plan_metered_opt_in_still_works(monkeypatch):
    """Counter-case: admin explicitly opts a plan into metered billing.

    The infrastructure stays available — a single plan can still be flipped
    to metered by passing ``is_metered=True`` + ``meter_event_name`` at
    create time. This protects against a future refactor that accidentally
    forces all plans flat.
    """
    service = _service()

    with patch(
        "app.services.subscription_service.stripe_service.sync_plan_to_stripe",
        return_value={"stripe_price_id_monthly": "price_metered"},
    ) as sync_plan:
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
    """Deleting a canonical plan must soft-archive so the next container
    boot's seed doesn't resurrect it. Behavior is independent of billing
    model; fixture mirrors the post-2026-05-09 flat catalog.
    """
    service = _service(
        plans=[
            {
                "_id": "plan_boutique",
                "name": "Boutique",
                "price_monthly": 49,
                "is_metered": False,
                "billing_model": "flat_rate",
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
