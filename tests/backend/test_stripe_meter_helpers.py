"""Unit tests for ``app/services/stripe_meter_helpers``.

Pins the contract that the seed script and ``stripe_service`` both depend on.
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


def _meter_obj(
    meter_id: str = "mtr_test_123",
    event_name: str = "wedding_active",
    formula: str = "sum",
    customer_key: str = "stripe_customer_id",
    value_key: str = "value",
) -> MagicMock:
    meter = MagicMock()
    meter.id = meter_id
    meter.event_name = event_name
    meter.default_aggregation = MagicMock()
    meter.default_aggregation.formula = formula
    meter.customer_mapping = MagicMock()
    meter.customer_mapping.event_payload_key = customer_key
    meter.value_settings = MagicMock()
    meter.value_settings.event_payload_key = value_key
    return meter


def test_ensure_stripe_meter_returns_existing_when_event_name_matches():
    """If a matching meter exists AND is valid, return its id without
    calling Meter.create. Post-C2: the match is validated via
    Meter.retrieve before being returned."""
    from app.services.stripe_meter_helpers import ensure_stripe_meter

    existing = _meter_obj(meter_id="mtr_existing")
    listing = MagicMock()
    listing.auto_paging_iter = MagicMock(return_value=iter([existing]))

    with (
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.list",
            return_value=listing,
        ) as mock_list,
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
            return_value=existing,
        ),
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.create"
        ) as mock_create,
    ):
        result = ensure_stripe_meter("wedding_active")

    assert result == "mtr_existing"
    mock_list.assert_called_once_with(status="active", limit=100)
    mock_create.assert_not_called()


def test_ensure_stripe_meter_creates_when_no_match():
    """No existing match → create with canonical config."""
    from app.services.stripe_meter_helpers import ensure_stripe_meter

    listing = MagicMock()
    listing.auto_paging_iter = MagicMock(return_value=iter([]))
    new_meter = _meter_obj(meter_id="mtr_new")

    with (
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.list",
            return_value=listing,
        ),
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.create",
            return_value=new_meter,
        ) as mock_create,
    ):
        result = ensure_stripe_meter("wedding_active", display_name="Wedding Active")

    assert result == "mtr_new"
    kwargs = mock_create.call_args.kwargs
    assert kwargs["event_name"] == "wedding_active"
    assert kwargs["display_name"] == "Wedding Active"
    assert kwargs["default_aggregation"] == {"formula": "sum"}
    assert kwargs["customer_mapping"] == {
        "type": "by_id",
        "event_payload_key": "stripe_customer_id",
    }
    assert kwargs["value_settings"] == {"event_payload_key": "value"}


def test_ensure_stripe_meter_default_display_name():
    """Title-case derivation when display_name omitted."""
    from app.services.stripe_meter_helpers import ensure_stripe_meter

    listing = MagicMock()
    listing.auto_paging_iter = MagicMock(return_value=iter([]))

    with (
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.list",
            return_value=listing,
        ),
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.create",
            return_value=_meter_obj(),
        ) as mock_create,
    ):
        ensure_stripe_meter("wedding_active")

    assert mock_create.call_args.kwargs["display_name"] == "Wedding Active"


def test_ensure_stripe_meter_falls_through_to_create_when_list_errors():
    """Transient list error → fall through to create."""
    from stripe import StripeError

    from app.services.stripe_meter_helpers import ensure_stripe_meter

    with (
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.list",
            side_effect=StripeError("transient list failure"),
        ),
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.create",
            return_value=_meter_obj(meter_id="mtr_after_list_failure"),
        ) as mock_create,
    ):
        result = ensure_stripe_meter("wedding_active")

    assert result == "mtr_after_list_failure"
    mock_create.assert_called_once()


def test_assert_meter_config_passes_on_canonical_meter():
    from app.services.stripe_meter_helpers import assert_meter_config

    with patch(
        "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
        return_value=_meter_obj(),
    ):
        assert_meter_config("mtr_test_123")


def test_assert_meter_config_raises_on_count_aggregation():
    from app.services.stripe_meter_helpers import assert_meter_config

    with patch(
        "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
        return_value=_meter_obj(formula="count"),
    ):
        with pytest.raises(ValueError, match="aggregation='count'"):
            assert_meter_config("mtr_bad")


def test_assert_meter_config_raises_on_last_aggregation():
    from app.services.stripe_meter_helpers import assert_meter_config

    with patch(
        "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
        return_value=_meter_obj(formula="last"),
    ):
        with pytest.raises(ValueError, match="must be 'sum'"):
            assert_meter_config("mtr_bad")


def test_assert_meter_config_raises_on_wrong_customer_mapping_key():
    from app.services.stripe_meter_helpers import assert_meter_config

    with patch(
        "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
        return_value=_meter_obj(customer_key="customer_id"),
    ):
        with pytest.raises(ValueError, match="customer_mapping.event_payload_key"):
            assert_meter_config("mtr_bad")


def test_assert_meter_config_raises_on_wrong_value_key():
    from app.services.stripe_meter_helpers import assert_meter_config

    with patch(
        "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
        return_value=_meter_obj(value_key="quantity"),
    ):
        with pytest.raises(ValueError, match="value_settings.event_payload_key"):
            assert_meter_config("mtr_bad")


def test_assert_meter_config_raises_on_missing_meter():
    from stripe import InvalidRequestError

    from app.services.stripe_meter_helpers import assert_meter_config

    with patch(
        "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
        side_effect=InvalidRequestError("No such billing meter", "meter_id"),
    ):
        with pytest.raises(ValueError, match="not found"):
            assert_meter_config("mtr_does_not_exist")


def test_canonical_constants_are_locked():
    from app.services.stripe_meter_helpers import (
        METER_AGGREGATION_FORMULA,
        METER_CUSTOMER_MAPPING_KEY,
        METER_EVENT_NAME_WEDDING_ACTIVE,
        METER_VALUE_KEY,
    )

    assert METER_AGGREGATION_FORMULA == "sum"
    assert METER_CUSTOMER_MAPPING_KEY == "stripe_customer_id"
    assert METER_VALUE_KEY == "value"
    assert METER_EVENT_NAME_WEDDING_ACTIVE == "wedding_active"
