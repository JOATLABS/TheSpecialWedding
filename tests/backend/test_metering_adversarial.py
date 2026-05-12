"""Adversarial unit tests for the Stripe metering pipeline.

Six false-positive/false-negative axes:
1. False-positive billing (delete fires +1 instead of -1, retry past 24h)
2. False-negative billing (event_name mismatch silently drops events)
3. False-positive validation (case mismatch, whitespace, None attrs)
4. False-negative validation (rejects valid meter)
5. False-positive provisioning (creates duplicate when one exists)
6. False-negative provisioning (returns stale id, prefix collision)

References:
* docs/analysis/METERING_REVIEW_2026-05-04_PART2.md §5 (CC1, CC2)
* docs/analysis/METERING_GAP_SCENARIOS_2026-05-04.md
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


def _meter(
    meter_id="mtr_test",
    event_name="wedding_active",
    formula="sum",
    customer_key="stripe_customer_id",
    value_key="value",
    status="active",
):
    m = MagicMock()
    m.id = meter_id
    m.event_name = event_name
    m.status = status
    m.default_aggregation = MagicMock()
    m.default_aggregation.formula = formula
    m.customer_mapping = MagicMock()
    m.customer_mapping.event_payload_key = customer_key
    m.value_settings = MagicMock()
    m.value_settings.event_payload_key = value_key
    return m


def _listing(*meters):
    listing = MagicMock()
    listing.auto_paging_iter = MagicMock(return_value=iter(meters))
    return listing


# ===========================================================================
# AXIS 4: False-negative validation
# ===========================================================================


def test_assert_meter_config_accepts_canonical_meter_no_extras():
    from app.services.stripe_meter_helpers import assert_meter_config

    with patch(
        "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
        return_value=_meter(),
    ):
        assert_meter_config("mtr_test")


def test_assert_meter_config_accepts_meter_with_extra_attributes():
    """Extra Stripe fields shouldn't trip the check."""
    from app.services.stripe_meter_helpers import assert_meter_config

    m = _meter()
    m.future_field_we_dont_know_about = "whatever"
    m.metadata = {"team": "billing"}

    with patch(
        "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
        return_value=m,
    ):
        assert_meter_config("mtr_test")


# ===========================================================================
# AXIS 3: False-positive validation (rejects misconfigured meters)
# ===========================================================================


def test_assert_meter_config_rejects_uppercase_formula():
    from app.services.stripe_meter_helpers import assert_meter_config

    with patch(
        "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
        return_value=_meter(formula="SUM"),
    ):
        with pytest.raises(ValueError, match="must be 'sum'"):
            assert_meter_config("mtr_bad")


def test_assert_meter_config_rejects_whitespace_formula():
    from app.services.stripe_meter_helpers import assert_meter_config

    with patch(
        "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
        return_value=_meter(formula="sum "),
    ):
        with pytest.raises(ValueError, match="must be 'sum'"):
            assert_meter_config("mtr_bad")


def test_assert_meter_config_rejects_none_formula():
    from app.services.stripe_meter_helpers import assert_meter_config

    with patch(
        "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
        return_value=_meter(formula=None),
    ):
        with pytest.raises(ValueError, match="must be 'sum'"):
            assert_meter_config("mtr_bad")


def test_assert_meter_config_rejects_missing_default_aggregation():
    from app.services.stripe_meter_helpers import assert_meter_config

    bad = _meter()
    bad.default_aggregation = None

    with patch(
        "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
        return_value=bad,
    ):
        with pytest.raises(ValueError, match="must be 'sum'"):
            assert_meter_config("mtr_bad")


def test_assert_meter_config_rejects_missing_customer_mapping():
    from app.services.stripe_meter_helpers import assert_meter_config

    bad = _meter()
    bad.customer_mapping = None

    with patch(
        "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
        return_value=bad,
    ):
        with pytest.raises(ValueError, match="customer_mapping.event_payload_key"):
            assert_meter_config("mtr_bad")


def test_assert_meter_config_rejects_missing_value_settings():
    from app.services.stripe_meter_helpers import assert_meter_config

    bad = _meter()
    bad.value_settings = None

    with patch(
        "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
        return_value=bad,
    ):
        with pytest.raises(ValueError, match="value_settings.event_payload_key"):
            assert_meter_config("mtr_bad")


def test_assert_meter_config_rejects_customer_id_typo():
    from app.services.stripe_meter_helpers import assert_meter_config

    with patch(
        "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
        return_value=_meter(customer_key="customer_id"),
    ):
        with pytest.raises(ValueError, match="stripe_customer_id"):
            assert_meter_config("mtr_bad")


# ===========================================================================
# AXIS 5: False-positive provisioning (creates duplicate)
# ===========================================================================


def test_ensure_stripe_meter_match_is_exact_not_prefix():
    """``wedding_active`` must NOT match ``wedding_active_v2``."""
    from app.services.stripe_meter_helpers import ensure_stripe_meter

    not_a_match = _meter(meter_id="mtr_v2", event_name="wedding_active_v2")
    new_meter = _meter(meter_id="mtr_brand_new", event_name="wedding_active")

    with (
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.list",
            return_value=_listing(not_a_match),
        ),
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.create",
            return_value=new_meter,
        ) as mock_create,
    ):
        result = ensure_stripe_meter("wedding_active")

    assert result == "mtr_brand_new"
    mock_create.assert_called_once()


def test_ensure_stripe_meter_match_is_case_sensitive():
    """``Wedding_Active`` must NOT match ``wedding_active``."""
    from app.services.stripe_meter_helpers import ensure_stripe_meter

    not_a_match = _meter(meter_id="mtr_caps", event_name="Wedding_Active")
    new_meter = _meter(meter_id="mtr_lowercase", event_name="wedding_active")

    with (
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.list",
            return_value=_listing(not_a_match),
        ),
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.create",
            return_value=new_meter,
        ) as mock_create,
    ):
        result = ensure_stripe_meter("wedding_active")

    assert result == "mtr_lowercase"
    mock_create.assert_called_once()


def test_ensure_stripe_meter_finds_target_on_paginated_second_page():
    """Pagination via auto_paging_iter — target on page 2 must be found."""
    from app.services.stripe_meter_helpers import ensure_stripe_meter

    page1 = [
        _meter(meter_id=f"mtr_p1_{i}", event_name=f"distractor_{i}") for i in range(100)
    ]
    target = _meter(meter_id="mtr_target", event_name="wedding_active")

    with (
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.list",
            return_value=_listing(*page1, target),
        ),
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
            return_value=target,
        ),
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.create"
        ) as mock_create,
    ):
        result = ensure_stripe_meter("wedding_active")

    assert result == "mtr_target"
    mock_create.assert_not_called()


def test_ensure_stripe_meter_idempotent_across_back_to_back_calls():
    """Two sequential calls return the same id."""
    from app.services.stripe_meter_helpers import ensure_stripe_meter

    existing = _meter(meter_id="mtr_idempotent", event_name="wedding_active")

    with (
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.list",
            side_effect=[_listing(existing), _listing(existing)],
        ),
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
            return_value=existing,
        ),
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.create"
        ) as mock_create,
    ):
        first = ensure_stripe_meter("wedding_active")
        second = ensure_stripe_meter("wedding_active")

    assert first == second == "mtr_idempotent"
    mock_create.assert_not_called()


# ===========================================================================
# AXIS 6: False-negative provisioning (returns stale/wrong id)
# ===========================================================================


def test_ensure_stripe_meter_filters_by_active_status():
    """Meter.list filter must be status='active' so deactivated meters
    don't surface."""
    from app.services.stripe_meter_helpers import ensure_stripe_meter

    new_meter = _meter(meter_id="mtr_fresh_active")

    with (
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.list",
            return_value=_listing(),
        ) as mock_list,
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.create",
            return_value=new_meter,
        ),
    ):
        result = ensure_stripe_meter("wedding_active")

    mock_list.assert_called_once()
    assert mock_list.call_args.kwargs.get("status") == "active"
    assert result == "mtr_fresh_active"


def test_ensure_stripe_meter_creates_fresh_when_list_returns_empty():
    from app.services.stripe_meter_helpers import ensure_stripe_meter

    new_meter = _meter(meter_id="mtr_first_time")

    with (
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.list",
            return_value=_listing(),
        ),
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.create",
            return_value=new_meter,
        ),
    ):
        result = ensure_stripe_meter("wedding_active")

    assert result == "mtr_first_time"


# ===========================================================================
# AXIS 1 + 2: False-positive/negative billing
# ===========================================================================


def test_report_meter_event_with_negative_value_for_reversal():
    """The codebase emits value="-1" for reversals. Pin that the negative
    sign reaches Stripe intact."""
    from app.services.stripe_service import StripeService

    service = StripeService.__new__(StripeService)

    fake_event = MagicMock()
    fake_event.identifier = "wedding_delete_w1_cus_x_2026-04"

    with patch(
        "app.services.stripe_service.stripe.billing.MeterEvent.create",
        return_value=fake_event,
    ) as mock_create:
        result = service.report_meter_event(
            event_name="wedding_active",
            payload={"stripe_customer_id": "cus_x", "value": "-1"},
            identifier="wedding_delete_w1_cus_x_2026-04",
        )

    assert result["status"] == "success"
    payload_sent = mock_create.call_args.kwargs["payload"]
    assert payload_sent["value"] == "-1"


def test_report_meter_event_event_name_is_passed_through_unchanged():
    """event_name must NOT be transformed (case, trim, etc.)."""
    from app.services.stripe_service import StripeService

    service = StripeService.__new__(StripeService)

    fake_event = MagicMock()
    fake_event.identifier = "id_123"

    with patch(
        "app.services.stripe_service.stripe.billing.MeterEvent.create",
        return_value=fake_event,
    ) as mock_create:
        service.report_meter_event(
            event_name="wedding_active",
            payload={"stripe_customer_id": "cus_x", "value": "1"},
            identifier="id_123",
        )

    assert mock_create.call_args.kwargs["event_name"] == "wedding_active"


# ===========================================================================
# Documented caveats — pin current behavior
# ===========================================================================


def test_known_caveat_assert_meter_config_does_not_check_status():
    """Pin: assert_meter_config doesn't fail-closed on inactive meters.
    The seed pre-filters via list(status=active) so this isn't reachable
    from that path, but sync_plan_to_stripe could pass an arbitrary
    meter_id from Mongo. Documented gap (M2 follow-up)."""
    from app.services.stripe_meter_helpers import assert_meter_config

    inactive_but_canonical = _meter(status="inactive")

    with patch(
        "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
        return_value=inactive_but_canonical,
    ):
        # Currently passes. If we tighten this, invert the assertion.
        assert_meter_config("mtr_inactive_canonical")
