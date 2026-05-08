"""Unit tests for ``app/services/stripe_meter_helpers``.

These pin the contract that the seed script and ``stripe_service`` both
depend on:

* ``ensure_stripe_meter`` is idempotent — returns the existing meter id
  if one already matches the event name, otherwise creates a new meter
  with the canonical config.
* ``assert_meter_config`` raises a clear ``ValueError`` on any deviation
  from the required Stripe Meter shape (formula, customer_mapping,
  value_settings).

A deviation in any of those would silently break billing — see
docs/analysis/METERING_REVIEW_2026-05-04_PART2.md §5 (CC1, CC2).
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


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


def _meter_obj(
    meter_id: str = "mtr_test_123",
    event_name: str = "wedding_active",
    formula: str = "sum",
    customer_key: str = "stripe_customer_id",
    value_key: str = "value",
) -> MagicMock:
    """Build a MagicMock that mimics a stripe Meter object's attribute shape."""
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


# ---------------------------------------------------------------------------
# ensure_stripe_meter — idempotency + creation
# ---------------------------------------------------------------------------


def test_ensure_stripe_meter_returns_existing_when_event_name_matches():
    """If a meter with the same event_name exists AND is valid, return
    its id without calling Meter.create. This is the idempotency
    contract every fresh container deploy depends on.

    Post-C2: an existing match is also validated via assert_meter_config
    (which calls Meter.retrieve) before being returned. We patch retrieve
    to return the same valid meter — the realistic case."""
    from app.services.stripe_meter_helpers import ensure_stripe_meter

    existing = _meter_obj(meter_id="mtr_existing", event_name="wedding_active")
    listing = MagicMock()
    listing.auto_paging_iter = MagicMock(return_value=iter([existing]))

    with (
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.list",
            return_value=listing,
        ) as mock_list,
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
            return_value=existing,  # C2: validate-on-return
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
    """If no active meter has the requested event_name, create one with
    the canonical config (sum + by_id + stripe_customer_id + value)."""
    from app.services.stripe_meter_helpers import ensure_stripe_meter

    listing = MagicMock()
    listing.auto_paging_iter = MagicMock(return_value=iter([]))  # empty

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
    mock_create.assert_called_once()
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
    """When display_name is omitted, derive a Title Cased version of
    event_name. Cosmetic but pinned because it shows up in the
    Stripe Dashboard."""
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
        ensure_stripe_meter("wedding_active")  # no display_name

    assert mock_create.call_args.kwargs["display_name"] == "Wedding Active"


def test_ensure_stripe_meter_falls_through_to_create_when_list_errors():
    """A transient list error must NOT block provisioning. The function
    falls through to Meter.create — Stripe will dedupe on its side if a
    matching meter slipped through (it won't, but defense in depth)."""
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


# ---------------------------------------------------------------------------
# assert_meter_config — canonical-config preflight
# ---------------------------------------------------------------------------


def test_assert_meter_config_passes_on_canonical_meter():
    """Happy path: a meter with sum + stripe_customer_id + value passes
    silently. This is the contract the runtime relies on at every
    sync_plan_to_stripe call."""
    from app.services.stripe_meter_helpers import assert_meter_config

    with patch(
        "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
        return_value=_meter_obj(),
    ):
        assert_meter_config("mtr_test_123")  # no exception = pass


def test_assert_meter_config_raises_on_count_aggregation():
    """A meter with formula=count would silently overbill on delete-
    reversals (because value=-1 is treated as +1 event). Reject it."""
    from app.services.stripe_meter_helpers import assert_meter_config

    bad = _meter_obj(formula="count")
    with patch(
        "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
        return_value=bad,
    ):
        with pytest.raises(ValueError, match="aggregation='count'"):
            assert_meter_config("mtr_bad")


def test_assert_meter_config_raises_on_last_aggregation():
    """formula=last would also break the reversal arithmetic."""
    from app.services.stripe_meter_helpers import assert_meter_config

    bad = _meter_obj(formula="last")
    with patch(
        "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
        return_value=bad,
    ):
        with pytest.raises(ValueError, match="must be 'sum'"):
            assert_meter_config("mtr_bad")


def test_assert_meter_config_raises_on_wrong_customer_mapping_key():
    """If the meter expects ``customer_id`` (not ``stripe_customer_id``),
    every event payload would fail customer attribution silently."""
    from app.services.stripe_meter_helpers import assert_meter_config

    bad = _meter_obj(customer_key="customer_id")
    with patch(
        "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
        return_value=bad,
    ):
        with pytest.raises(ValueError, match="customer_mapping.event_payload_key"):
            assert_meter_config("mtr_bad")


def test_assert_meter_config_raises_on_wrong_value_key():
    """Same risk on the value-settings side: if Stripe expects
    ``quantity`` but we send ``value``, the meter aggregates zero."""
    from app.services.stripe_meter_helpers import assert_meter_config

    bad = _meter_obj(value_key="quantity")
    with patch(
        "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
        return_value=bad,
    ):
        with pytest.raises(ValueError, match="value_settings.event_payload_key"):
            assert_meter_config("mtr_bad")


def test_assert_meter_config_raises_on_missing_meter():
    """``Meter.retrieve`` with a nonexistent id raises
    ``InvalidRequestError``; surface that as a clear ValueError so callers
    can convert to HTTP 400 with an actionable message."""
    from stripe import InvalidRequestError

    from app.services.stripe_meter_helpers import assert_meter_config

    with patch(
        "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
        side_effect=InvalidRequestError("No such billing meter", "meter_id"),
    ):
        with pytest.raises(ValueError, match="not found"):
            assert_meter_config("mtr_does_not_exist")


# ---------------------------------------------------------------------------
# Constants pin
# ---------------------------------------------------------------------------


def test_canonical_constants_are_locked():
    """Pin the canonical config values. Changing any of these is a
    coordinated change with app/api/wedding.py (payload shape) — the
    constants module's docstring captures the dependency.
    """
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
