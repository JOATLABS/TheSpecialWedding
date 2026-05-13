"""Adversarial tests for ``StripeService.sync_plan_to_stripe`` metered flow.

Pins:
* Flat → metered transition deactivates old flat price + creates new metered.
* Metered → flat transition does the inverse.
* Idempotent re-sync (same shape) does NOT call Price.create.
* meter_id auto-resolve via Meter.list when only event_name is set.
* preflight (assert_meter_config) raises HTTPException 400 on misconfig.
* recurring config carries usage_type=metered + meter=<id> for metered plans.

**Sandbox limitation:** these tests import StripeService, which chains
through app.core.database and hits PyOpenSSL/cryptography mismatch in the
cowork sandbox. They pass on local Python with compatible deps.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_unit")
os.environ.setdefault("STRIPE_ENABLED", "true")


def _build_service():
    from app.services.stripe_service import StripeService

    service = StripeService.__new__(StripeService)
    service._ensure_stripe_enabled = lambda: None
    return service


def _mk_meter_obj(formula="sum", customer_key="stripe_customer_id", value_key="value"):
    m = MagicMock()
    m.id = "mtr_test"
    m.event_name = "wedding_active"
    m.default_aggregation = MagicMock()
    m.default_aggregation.formula = formula
    m.customer_mapping = MagicMock()
    m.customer_mapping.event_payload_key = customer_key
    m.value_settings = MagicMock()
    m.value_settings.event_payload_key = value_key
    return m


def _mk_price(
    price_id, amount_cents, interval, usage_type=None, meter_id=None, active=True
):
    p = MagicMock()
    p.id = price_id
    p.active = active
    p.unit_amount = amount_cents
    p.currency = "usd"
    p.recurring = MagicMock()
    p.recurring.interval = interval
    p.recurring.usage_type = usage_type or "licensed"
    p.recurring.meter = meter_id if meter_id else None
    return p


def test_sync_recreates_price_when_existing_one_is_archived():
    """An archived Stripe price (active=False) must NOT be reused even if all
    other fields match. Stripe rejects Subscription.create with an inactive
    price (400 'The price specified is inactive'), so reusing an archived id
    here produces a stale-Mongo state that breaks every new subscription.
    Regression caught 2026-05-12 via testbed/verify_aurinko_*.py."""
    from unittest.mock import MagicMock as _MM, patch as _patch

    service = _build_service()
    plan = {
        "_id": "plan_signature",
        "name": "Signature",
        "description": "Most popular",
        "price_monthly": 59,
        "price_yearly": 590,
        "stripe_product_id": "prod_existing",
        "stripe_price_id_monthly": "price_ARCHIVED_MO",
        "stripe_price_id_yearly": "price_ARCHIVED_YR",
        "is_metered": False,
    }

    # All fields match the desired config except ``active=False``. Pre-fix
    # this would return the archived id; post-fix it must create a new price.
    archived_monthly = _mk_price("price_ARCHIVED_MO", 5900, "month", active=False)
    archived_yearly = _mk_price("price_ARCHIVED_YR", 59000, "year", active=False)
    new_monthly = _mk_price("price_FRESH_MO", 5900, "month")
    new_yearly = _mk_price("price_FRESH_YR", 59000, "year")

    with (
        _patch(
            "app.services.stripe_service.stripe.Product.retrieve",
            return_value=_MM(id="prod_existing"),
        ),
        _patch("app.services.stripe_service.stripe.Product.modify"),
        _patch(
            "app.services.stripe_service.stripe.Price.retrieve",
            side_effect=[archived_monthly, archived_yearly],
        ),
        _patch(
            "app.services.stripe_service.stripe.Price.create",
            side_effect=[new_monthly, new_yearly],
        ) as mock_price_create,
        _patch("app.services.stripe_service.stripe.Price.modify") as mock_price_modify,
    ):
        result = service.sync_plan_to_stripe(plan)

    # New prices were created (one for monthly, one for yearly)
    assert mock_price_create.call_count == 2
    # And the stale Mongo price ids were rotated to the new active ones
    assert result["stripe_price_id_monthly"] == "price_FRESH_MO"
    assert result["stripe_price_id_yearly"] == "price_FRESH_YR"
    # The archived prices got Price.modify(active=False) called against them
    # (a no-op on an already-archived price, but the code path still runs).
    deactivated = {call.args[0] for call in mock_price_modify.call_args_list}
    assert "price_ARCHIVED_MO" in deactivated
    assert "price_ARCHIVED_YR" in deactivated


def test_sync_flat_to_metered_deactivates_old_price_and_creates_new_metered():
    service = _build_service()
    plan = {
        "_id": "plan_signature",
        "name": "Signature",
        "description": "Most popular",
        "price_monthly": 59,
        "price_yearly": 590,
        "stripe_product_id": "prod_existing",
        "stripe_price_id_monthly": "price_OLD_FLAT_MO",
        "stripe_price_id_yearly": "price_OLD_FLAT_YR",
        "is_metered": True,
        "meter_event_name": "wedding_active",
        "meter_id": "mtr_test",
    }

    old_flat_monthly = _mk_price(
        "price_OLD_FLAT_MO", 5900, "month", usage_type="licensed"
    )
    old_flat_yearly = _mk_price(
        "price_OLD_FLAT_YR", 59000, "year", usage_type="licensed"
    )
    new_metered_monthly = _mk_price(
        "price_NEW_METERED_MO", 5900, "month", usage_type="metered", meter_id="mtr_test"
    )
    new_metered_yearly = _mk_price(
        "price_NEW_METERED_YR", 59000, "year", usage_type="metered", meter_id="mtr_test"
    )

    with (
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
            return_value=_mk_meter_obj(),
        ),
        patch(
            "app.services.stripe_service.stripe.Product.retrieve",
            return_value=MagicMock(id="prod_existing"),
        ),
        patch("app.services.stripe_service.stripe.Product.modify"),
        patch(
            "app.services.stripe_service.stripe.Price.retrieve",
            side_effect=[old_flat_monthly, old_flat_yearly],
        ),
        patch(
            "app.services.stripe_service.stripe.Price.create",
            side_effect=[new_metered_monthly, new_metered_yearly],
        ) as mock_price_create,
        patch("app.services.stripe_service.stripe.Price.modify") as mock_price_modify,
    ):
        result = service.sync_plan_to_stripe(plan)

    assert mock_price_create.call_count == 2
    for call in mock_price_create.call_args_list:
        rec = call.kwargs["recurring"]
        assert rec["usage_type"] == "metered"
        assert rec["meter"] == "mtr_test"

    deactivation_targets = {c.args[0] for c in mock_price_modify.call_args_list}
    assert "price_OLD_FLAT_MO" in deactivation_targets
    assert "price_OLD_FLAT_YR" in deactivation_targets
    assert result["stripe_price_id_monthly"] == "price_NEW_METERED_MO"
    assert result["stripe_price_id_yearly"] == "price_NEW_METERED_YR"


def test_sync_metered_to_flat_deactivates_metered_price_and_creates_flat():
    service = _build_service()
    plan = {
        "_id": "plan_signature",
        "name": "Signature",
        "description": "Most popular",
        "price_monthly": 59,
        "price_yearly": 590,
        "stripe_product_id": "prod_existing",
        "stripe_price_id_monthly": "price_OLD_METERED_MO",
        "stripe_price_id_yearly": "price_OLD_METERED_YR",
        "is_metered": False,
        "meter_event_name": None,
        "meter_id": None,
    }

    old_metered_monthly = _mk_price(
        "price_OLD_METERED_MO", 5900, "month", usage_type="metered", meter_id="mtr_test"
    )
    old_metered_yearly = _mk_price(
        "price_OLD_METERED_YR", 59000, "year", usage_type="metered", meter_id="mtr_test"
    )
    new_flat_monthly = _mk_price(
        "price_NEW_FLAT_MO", 5900, "month", usage_type="licensed"
    )
    new_flat_yearly = _mk_price(
        "price_NEW_FLAT_YR", 59000, "year", usage_type="licensed"
    )

    with (
        patch(
            "app.services.stripe_service.stripe.Product.retrieve",
            return_value=MagicMock(id="prod_existing"),
        ),
        patch("app.services.stripe_service.stripe.Product.modify"),
        patch(
            "app.services.stripe_service.stripe.Price.retrieve",
            side_effect=[old_metered_monthly, old_metered_yearly],
        ),
        patch(
            "app.services.stripe_service.stripe.Price.create",
            side_effect=[new_flat_monthly, new_flat_yearly],
        ) as mock_price_create,
        patch("app.services.stripe_service.stripe.Price.modify") as mock_price_modify,
    ):
        service.sync_plan_to_stripe(plan)

    for call in mock_price_create.call_args_list:
        rec = call.kwargs["recurring"]
        assert "usage_type" not in rec or rec.get("usage_type") != "metered"
        assert "meter" not in rec

    deactivation_targets = {c.args[0] for c in mock_price_modify.call_args_list}
    assert "price_OLD_METERED_MO" in deactivation_targets
    assert "price_OLD_METERED_YR" in deactivation_targets


def test_sync_idempotent_when_metered_config_already_matches():
    """Re-sync with no changes: no new prices, no deactivations."""
    service = _build_service()
    plan = {
        "_id": "plan_signature",
        "name": "Signature",
        "description": "Most popular",
        "price_monthly": 59,
        "price_yearly": 590,
        "stripe_product_id": "prod_existing",
        "stripe_price_id_monthly": "price_METERED_MO",
        "stripe_price_id_yearly": "price_METERED_YR",
        "is_metered": True,
        "meter_event_name": "wedding_active",
        "meter_id": "mtr_test",
    }

    existing_monthly = _mk_price(
        "price_METERED_MO", 5900, "month", usage_type="metered", meter_id="mtr_test"
    )
    existing_yearly = _mk_price(
        "price_METERED_YR", 59000, "year", usage_type="metered", meter_id="mtr_test"
    )

    with (
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
            return_value=_mk_meter_obj(),
        ),
        patch(
            "app.services.stripe_service.stripe.Product.retrieve",
            return_value=MagicMock(id="prod_existing"),
        ),
        patch("app.services.stripe_service.stripe.Product.modify"),
        patch(
            "app.services.stripe_service.stripe.Price.retrieve",
            side_effect=[existing_monthly, existing_yearly],
        ),
        patch("app.services.stripe_service.stripe.Price.create") as mock_price_create,
        patch("app.services.stripe_service.stripe.Price.modify") as mock_price_modify,
    ):
        result = service.sync_plan_to_stripe(plan)

    mock_price_create.assert_not_called()
    mock_price_modify.assert_not_called()
    assert result["stripe_price_id_monthly"] == "price_METERED_MO"
    assert result["stripe_price_id_yearly"] == "price_METERED_YR"


def test_sync_raises_400_when_meter_aggregation_is_not_sum():
    """Wrong-formula meter must fail-fast BEFORE any product/price creation."""
    from fastapi import HTTPException

    service = _build_service()
    plan = {
        "_id": "plan_signature",
        "name": "Signature",
        "price_monthly": 59,
        "price_yearly": 590,
        "is_metered": True,
        "meter_event_name": "wedding_active",
        "meter_id": "mtr_test",
    }

    with (
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
            return_value=_mk_meter_obj(formula="count"),
        ),
        patch(
            "app.services.stripe_service.stripe.Product.create"
        ) as mock_product_create,
    ):
        with pytest.raises(HTTPException) as exc_info:
            service.sync_plan_to_stripe(plan)

    assert exc_info.value.status_code == 400
    assert "must be 'sum'" in str(exc_info.value.detail)
    mock_product_create.assert_not_called()


def test_sync_raises_400_when_meter_id_does_not_exist():
    """Stale meter_id surfaces clearly."""
    from fastapi import HTTPException
    from stripe import InvalidRequestError

    service = _build_service()
    plan = {
        "_id": "plan_signature",
        "name": "Signature",
        "price_monthly": 59,
        "price_yearly": 590,
        "is_metered": True,
        "meter_event_name": "wedding_active",
        "meter_id": "mtr_DELETED",
    }

    with patch(
        "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
        side_effect=InvalidRequestError("No such billing meter", "meter_id"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            service.sync_plan_to_stripe(plan)

    assert exc_info.value.status_code == 400
    assert "not found" in str(exc_info.value.detail)


def test_sync_raises_400_when_meter_id_unresolvable():
    """is_metered=True but no meter_id and no list match → 400."""
    from fastapi import HTTPException

    service = _build_service()
    plan = {
        "_id": "plan_signature",
        "name": "Signature",
        "price_monthly": 59,
        "price_yearly": 590,
        "is_metered": True,
        "meter_event_name": "wedding_active",
    }

    listing = MagicMock()
    listing.data = []

    with patch(
        "app.services.stripe_service.stripe.billing.Meter.list",
        return_value=listing,
    ):
        with pytest.raises(HTTPException) as exc_info:
            service.sync_plan_to_stripe(plan)

    assert exc_info.value.status_code == 400
    assert "meter_id" in str(exc_info.value.detail).lower()


def test_sync_auto_resolves_meter_id_from_event_name():
    """Existing fallback: meter_id missing, found via event_name lookup."""
    service = _build_service()
    plan = {
        "_id": "plan_signature",
        "name": "Signature",
        "description": "Most popular",
        "price_monthly": 59,
        "price_yearly": 590,
        "is_metered": True,
        "meter_event_name": "wedding_active",
    }

    existing_meter = MagicMock()
    existing_meter.id = "mtr_auto_resolved"
    existing_meter.event_name = "wedding_active"
    listing = MagicMock()
    listing.data = [existing_meter]

    new_metered_monthly = _mk_price(
        "price_NEW_MO",
        5900,
        "month",
        usage_type="metered",
        meter_id="mtr_auto_resolved",
    )
    new_metered_yearly = _mk_price(
        "price_NEW_YR",
        59000,
        "year",
        usage_type="metered",
        meter_id="mtr_auto_resolved",
    )

    with (
        patch(
            "app.services.stripe_service.stripe.billing.Meter.list",
            return_value=listing,
        ),
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
            return_value=_mk_meter_obj(),
        ),
        patch(
            "app.services.stripe_service.stripe.Product.create",
            return_value=MagicMock(id="prod_new"),
        ),
        patch(
            "app.services.stripe_service.stripe.Price.create",
            side_effect=[new_metered_monthly, new_metered_yearly],
        ) as mock_price_create,
    ):
        result = service.sync_plan_to_stripe(plan)

    assert result["meter_id"] == "mtr_auto_resolved"
    for call in mock_price_create.call_args_list:
        assert call.kwargs["recurring"]["meter"] == "mtr_auto_resolved"


def test_metered_price_create_carries_usage_type_metered():
    """Metered plan's Price MUST carry usage_type=metered + meter=<id>."""
    service = _build_service()
    plan = {
        "_id": "plan_signature",
        "name": "Signature",
        "description": "Most popular",
        "price_monthly": 59,
        "price_yearly": 590,
        "is_metered": True,
        "meter_event_name": "wedding_active",
        "meter_id": "mtr_test",
    }

    new_monthly = _mk_price(
        "price_M", 5900, "month", usage_type="metered", meter_id="mtr_test"
    )
    new_yearly = _mk_price(
        "price_Y", 59000, "year", usage_type="metered", meter_id="mtr_test"
    )

    with (
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
            return_value=_mk_meter_obj(),
        ),
        patch(
            "app.services.stripe_service.stripe.Product.create",
            return_value=MagicMock(id="prod_new"),
        ),
        patch(
            "app.services.stripe_service.stripe.Price.create",
            side_effect=[new_monthly, new_yearly],
        ) as mock_price_create,
    ):
        service.sync_plan_to_stripe(plan)

    monthly_call = mock_price_create.call_args_list[0]
    yearly_call = mock_price_create.call_args_list[1]
    for call, interval in [(monthly_call, "month"), (yearly_call, "year")]:
        rec = call.kwargs["recurring"]
        assert rec["interval"] == interval
        assert rec["usage_type"] == "metered"
        assert rec["meter"] == "mtr_test"


def test_flat_price_create_does_not_carry_metered_fields():
    """Flat plan Price must NOT have usage_type=metered or meter field."""
    service = _build_service()
    plan = {
        "_id": "plan_boutique",
        "name": "Boutique",
        "description": "Onboarding",
        "price_monthly": 29,
        "price_yearly": 290,
        "is_metered": False,
    }

    new_monthly = _mk_price("price_FLAT_MO", 2900, "month", usage_type="licensed")
    new_yearly = _mk_price("price_FLAT_YR", 29000, "year", usage_type="licensed")

    with (
        patch(
            "app.services.stripe_service.stripe.Product.create",
            return_value=MagicMock(id="prod_new"),
        ),
        patch(
            "app.services.stripe_service.stripe.Price.create",
            side_effect=[new_monthly, new_yearly],
        ) as mock_price_create,
    ):
        service.sync_plan_to_stripe(plan)

    for call in mock_price_create.call_args_list:
        rec = call.kwargs["recurring"]
        assert rec.get("usage_type") != "metered"
        assert "meter" not in rec
