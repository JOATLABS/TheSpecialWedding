"""Adversarial unit tests for the Stripe metering pipeline.

The companion file ``test_stripe_meter_helpers.py`` covers the happy paths
and the obvious negatives. This file goes hostile — every test maps to one
of six false-positive/false-negative axes that, if they failed silently in
production, would either bill customers wrong or leak meter events into
the void.

Six axes:

1. **False-positive billing** — Stripe charges when we didn't intend.
   - delete fires ``+1`` instead of ``-1``
   - retry past Stripe's 24h dedupe window double-bills
   - reversal on a never-billed wedding emits stray ``-1``

2. **False-negative billing** — Stripe doesn't charge when we should.
   - ``meter_event_name`` mismatch silently drops events
   - half-configured plan (is_metered=True, meter_event_name=None) bypasses
   - customer_mapping_key drift drops events

3. **False-positive validation** — assert_meter_config accepts a meter that
   would actually break billing.
   - case-mismatch (``"SUM"`` vs ``"sum"``)
   - whitespace (``"sum "`` vs ``"sum"``)
   - None / missing nested attributes

4. **False-negative validation** — assert_meter_config rejects a valid
   meter.
   - canonical config passes
   - alternative-but-equivalent attribute access shapes pass

5. **False-positive provisioning** — ensure_stripe_meter creates a
   duplicate when one already exists.
   - exact-match required (``wedding_active`` ≠ ``wedding_active_v2``)
   - case-sensitive match
   - pagination — target meter is on page 2

6. **False-negative provisioning** — ensure_stripe_meter returns a stale
   or wrong id.
   - inactive/deactivated meter is filtered out (status="active")
   - prefix collision doesn't cause spurious match

References:

* docs/analysis/METERING_REVIEW_2026-05-04_PART2.md §5 (CC1, CC2)
* docs/analysis/METERING_REVIEW_2026-05-04.md Part 1 (M2 — stray -1)
* https://docs.stripe.com/api/billing/meter — canonical config
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
# Test helper — build a meter mock with overridable attributes
# ---------------------------------------------------------------------------


def _meter(
    meter_id: str = "mtr_test",
    event_name: str = "wedding_active",
    formula: str = "sum",
    customer_key: str = "stripe_customer_id",
    value_key: str = "value",
    status: str = "active",
) -> MagicMock:
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
# AXIS 4: False-negative validation (rejects a valid meter)
#
# These should pass silently — if they raise, the canonical config check is
# itself broken and assert_meter_config would block legitimate deploys.
# ===========================================================================


def test_assert_meter_config_accepts_canonical_meter_no_extras():
    """Bare canonical config — no extra attributes — must pass.

    A regression in attribute access (e.g., requiring a non-existent
    ``meter.id``-derived check) would trip this.
    """
    from app.services.stripe_meter_helpers import assert_meter_config

    with patch(
        "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
        return_value=_meter(),
    ):
        assert_meter_config("mtr_test")  # no exception


def test_assert_meter_config_accepts_meter_with_extra_attributes():
    """Stripe may add new fields to the Meter object over API versions.
    The check must only validate the three fields it cares about and
    ignore anything else."""
    from app.services.stripe_meter_helpers import assert_meter_config

    m = _meter()
    m.future_field_we_dont_know_about = "whatever"
    m.metadata = {"team": "billing"}

    with patch(
        "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
        return_value=m,
    ):
        assert_meter_config("mtr_test")  # extras are fine


# ===========================================================================
# AXIS 3: False-positive validation (accepts a meter that would break)
#
# These MUST raise — missing them means a misconfigured meter slips through
# preflight and breaks billing silently in prod.
# ===========================================================================


def test_assert_meter_config_rejects_uppercase_formula():
    """Stripe normalizes formula to lowercase, but a future API version
    or manual hack could surface it differently. The codebase assumes
    exactly ``"sum"`` — pin that."""
    from app.services.stripe_meter_helpers import assert_meter_config

    bad = _meter(formula="SUM")
    with patch(
        "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
        return_value=bad,
    ):
        with pytest.raises(ValueError, match="must be 'sum'"):
            assert_meter_config("mtr_bad")


def test_assert_meter_config_rejects_whitespace_formula():
    """Trailing whitespace would slip past a ``startswith`` check; we
    use exact equality, which is the safer default."""
    from app.services.stripe_meter_helpers import assert_meter_config

    bad = _meter(formula="sum ")
    with patch(
        "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
        return_value=bad,
    ):
        with pytest.raises(ValueError, match="must be 'sum'"):
            assert_meter_config("mtr_bad")


def test_assert_meter_config_rejects_none_formula():
    """If Stripe returns ``default_aggregation`` with no ``formula``
    attribute (or formula=None), the check must fail-closed. A missing
    formula means the meter is in some indeterminate state."""
    from app.services.stripe_meter_helpers import assert_meter_config

    bad = _meter(formula=None)
    with patch(
        "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
        return_value=bad,
    ):
        with pytest.raises(ValueError, match="must be 'sum'"):
            assert_meter_config("mtr_bad")


def test_assert_meter_config_rejects_missing_default_aggregation():
    """Adversarial: Stripe response with no default_aggregation block at
    all (malformed). ``getattr`` chain returns None → check rejects."""
    from app.services.stripe_meter_helpers import assert_meter_config

    bad = _meter()
    bad.default_aggregation = None  # missing entire block

    with patch(
        "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
        return_value=bad,
    ):
        with pytest.raises(ValueError, match="must be 'sum'"):
            assert_meter_config("mtr_bad")


def test_assert_meter_config_rejects_missing_customer_mapping():
    """Adversarial: malformed Stripe response with customer_mapping=None."""
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
    """Adversarial: malformed Stripe response with value_settings=None."""
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
    """A common typo: ``customer_id`` instead of ``stripe_customer_id``.
    The codebase always sends ``stripe_customer_id`` — every event would
    fail customer attribution silently."""
    from app.services.stripe_meter_helpers import assert_meter_config

    bad = _meter(customer_key="customer_id")
    with patch(
        "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
        return_value=bad,
    ):
        with pytest.raises(ValueError, match="stripe_customer_id"):
            assert_meter_config("mtr_bad")


# ===========================================================================
# AXIS 5: False-positive provisioning (creates a duplicate)
#
# ensure_stripe_meter must NOT call Meter.create when a matching meter
# exists. Each test below pins a specific failure mode that would result
# in a duplicate meter on the Stripe account.
# ===========================================================================


def test_ensure_stripe_meter_match_is_exact_not_prefix():
    """``wedding_active`` must NOT match ``wedding_active_v2``. A prefix
    or substring match would silently bind the seed to a different
    meter than the operator intended."""
    from app.services.stripe_meter_helpers import ensure_stripe_meter

    not_a_match = _meter(meter_id="mtr_v2", event_name="wedding_active_v2")
    listing = _listing(not_a_match)

    new_meter = _meter(meter_id="mtr_brand_new", event_name="wedding_active")

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
        result = ensure_stripe_meter("wedding_active")

    # Did NOT match the v2 meter; created a fresh one.
    assert result == "mtr_brand_new"
    mock_create.assert_called_once()


def test_ensure_stripe_meter_match_is_case_sensitive():
    """``Wedding_Active`` must NOT match ``wedding_active``. Stripe's
    ``event_name`` is case-sensitive at the API level — case-insensitive
    matching here would create a meter that emits to a different
    aggregation bucket than the one running events fire to."""
    from app.services.stripe_meter_helpers import ensure_stripe_meter

    not_a_match = _meter(meter_id="mtr_caps", event_name="Wedding_Active")
    listing = _listing(not_a_match)

    new_meter = _meter(meter_id="mtr_lowercase", event_name="wedding_active")

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
        result = ensure_stripe_meter("wedding_active")

    assert result == "mtr_lowercase"
    mock_create.assert_called_once()


def test_ensure_stripe_meter_finds_target_on_paginated_second_page():
    """If the account has 100+ active meters, the target may be on page 2.
    auto_paging_iter must walk past the first page. A regression that
    iterated only ``listing.data`` would miss it.

    Post-C2: also patch Meter.retrieve since the matching meter is now
    validated via assert_meter_config before being returned."""
    from app.services.stripe_meter_helpers import ensure_stripe_meter

    # 100 distractors on page 1, target on page 2
    page1 = [
        _meter(meter_id=f"mtr_p1_{i}", event_name=f"distractor_{i}") for i in range(100)
    ]
    target = _meter(meter_id="mtr_target", event_name="wedding_active")
    listing = _listing(*page1, target)

    with (
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.list",
            return_value=listing,
        ),
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
            return_value=target,  # C2: validate the matching meter
        ),
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.create"
        ) as mock_create,
    ):
        result = ensure_stripe_meter("wedding_active")

    assert result == "mtr_target"
    mock_create.assert_not_called()


def test_ensure_stripe_meter_idempotent_across_back_to_back_calls():
    """Two sequential calls (e.g., Mongo retry on the seed upsert) must
    return the same id. This is the contract that makes ``Dockerfile.coolify``
    safe — every container restart re-runs the seed.

    Post-C2: each call validates via Meter.retrieve. Patch it so both
    sequential validations succeed."""
    from app.services.stripe_meter_helpers import ensure_stripe_meter

    existing = _meter(meter_id="mtr_idempotent", event_name="wedding_active")

    # Both calls hit the same listing (Stripe is the source of truth).
    with (
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.list",
            side_effect=[_listing(existing), _listing(existing)],
        ),
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
            return_value=existing,  # C2: validate on each call
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
#
# Every test below proves ensure_stripe_meter wouldn't return the wrong
# meter even if Stripe surfaces tricky data shapes.
# ===========================================================================


def test_ensure_stripe_meter_skips_inactive_meters():
    """If a meter with the right event_name exists but is inactive, the
    list call already filters status="active" so it won't surface it.
    Even if it did surface (defensive double-check), the function must
    still create a fresh active meter rather than return the stale id.

    Note: today the impl trusts the API filter and would return whatever
    list yields. Pin this so a future refactor that loosens the filter
    can't silently regress.
    """
    from app.services.stripe_meter_helpers import ensure_stripe_meter

    inactive_meter = _meter(
        meter_id="mtr_inactive",
        event_name="wedding_active",
        status="inactive",  # would only matter if filter is dropped
    )

    # Simulate the API correctly filtering — listing yields nothing.
    listing = _listing()
    new_meter = _meter(meter_id="mtr_fresh_active", event_name="wedding_active")

    with (
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.list",
            return_value=listing,
        ) as mock_list,
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.create",
            return_value=new_meter,
        ),
    ):
        result = ensure_stripe_meter("wedding_active")

    # Pin the filter — list MUST be called with status="active".
    mock_list.assert_called_once()
    assert mock_list.call_args.kwargs.get("status") == "active"
    assert result == "mtr_fresh_active"
    _ = inactive_meter  # documents the threat model


def test_ensure_stripe_meter_creates_fresh_when_list_returns_empty():
    """Empty list → create. A regression that returned None or raised
    on empty list would block fresh deploys."""
    from app.services.stripe_meter_helpers import ensure_stripe_meter

    new_meter = _meter(meter_id="mtr_first_time", event_name="wedding_active")

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
#
# These exercise the runtime hooks (report_meter_event) at the unit level
# with the helpers. Most live in test_metering_gating.py already; below
# are the additional gaps from the Part 1 review (M2) and the Stripe-doc
# research (24h identifier window).
# ===========================================================================


def test_report_meter_event_with_negative_value_for_reversal():
    """The codebase emits value="-1" for delete reversals. Pin that the
    request actually carries the negative sign through to Stripe — a
    refactor that coerces to abs() or strips signs would break billing."""
    from unittest.mock import MagicMock

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
    assert payload_sent["value"] == "-1", (
        "Reversal value must reach Stripe with the negative sign intact. "
        "If this fails, check stripe_service.report_meter_event for any "
        "value-coercion logic."
    )


def test_report_meter_event_event_name_is_passed_through_unchanged():
    """``event_name`` MUST match the meter's event_name byte-for-byte in
    Stripe. A regression that title-cased / lower-cased / trimmed it
    would route every event to no-meter (silently dropped)."""
    from unittest.mock import MagicMock

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


def test_report_meter_event_idempotency_window_is_24h_per_stripe_docs():
    """Pin the documented Stripe behavior: identifier uniqueness is
    24h-rolling. A retry past 24h would NOT be deduped. The codebase's
    monthly idempotency keys (wedding_create_*_YYYY-MM) work because
    callers also Mongo-side-skip via ``last_billed_at`` checks — pin
    that the dedupe error path is independent of the time horizon.

    This is documentation-as-test: if Stripe's behavior changes, the
    test stays passing but the helper-reality drifts. The Stripe doc
    URL in the helper module's docstring is the source of truth."""
    from stripe import StripeError

    from app.services.stripe_service import StripeService

    service = StripeService.__new__(StripeService)

    # First call: success
    fake_event = MagicMock()
    fake_event.identifier = "wedding_create_w_cus_2026-04"

    # Second call: Stripe says "already exists"
    with patch(
        "app.services.stripe_service.stripe.billing.MeterEvent.create",
        side_effect=[
            fake_event,
            StripeError("identifier already exists"),
        ],
    ):
        first = service.report_meter_event(
            event_name="wedding_active",
            payload={"stripe_customer_id": "cus", "value": "1"},
            identifier="wedding_create_w_cus_2026-04",
        )
        second = service.report_meter_event(
            event_name="wedding_active",
            payload={"stripe_customer_id": "cus", "value": "1"},
            identifier="wedding_create_w_cus_2026-04",
        )

    # Both must report success; the second flagged as already_recorded
    assert first["status"] == "success"
    assert second["status"] == "success"
    assert second.get("already_recorded") is True


# ===========================================================================
# Documentation / pinning tests for KNOWN current-behavior caveats
#
# These tests pin behavior that the Part 1/2 review flagged as imperfect
# but deliberately not changed in this PR. If the behavior is fixed
# later, these tests should be inverted — but until then they document
# what operators should expect.
# ===========================================================================


def test_known_caveat_delete_can_emit_reversal_for_unbilled_wedding():
    """Part 1 finding M2: the wedding-delete path doesn't gate on
    ``last_billed_at`` before emitting ``-1``. A wedding created on a
    flat plan, then plan-flipped metered, then deleted, would emit a
    stray -1 with no prior +1 to cancel.

    This test is a NO-OP behavior assertion — it pins the helper's
    contract: ``report_meter_event`` itself doesn't know whether a
    matching +1 ever fired. That gating is the caller's job.

    When M2 is fixed (in app/api/wedding.py), this test stays passing
    because the contract is unchanged; but the caller-side test in
    test_metering_gating.py should grow a new assertion that the
    delete path does the gating itself."""
    from unittest.mock import MagicMock

    from app.services.stripe_service import StripeService

    service = StripeService.__new__(StripeService)

    fake_event = MagicMock()
    fake_event.identifier = "wedding_delete_w_unbilled"

    with patch(
        "app.services.stripe_service.stripe.billing.MeterEvent.create",
        return_value=fake_event,
    ):
        result = service.report_meter_event(
            event_name="wedding_active",
            payload={"stripe_customer_id": "cus", "value": "-1"},
            identifier="wedding_delete_w_unbilled",
        )

    # Stripe accepted it. Whether this was a SEMANTICALLY correct call
    # is for the caller to decide via last_billed_at gating.
    assert result["status"] == "success"


def test_known_caveat_assert_meter_config_does_not_check_status():
    """Pin: ``assert_meter_config`` doesn't fail-closed if the meter is
    inactive — it only checks the config shape. ``Meter.retrieve``
    returns inactive meters too. Today the seed pre-validates via list
    (``status="active"``), so an inactive meter wouldn't reach
    ``assert_meter_config`` from that path. But ``sync_plan_to_stripe``
    can pass an arbitrary meter_id from Mongo — and that meter could
    have been deactivated out of band.

    If you want fail-closed on inactive, add a status check in
    assert_meter_config. Until then, this test pins the gap."""
    from app.services.stripe_meter_helpers import assert_meter_config

    inactive_but_otherwise_canonical = _meter(status="inactive")

    with patch(
        "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
        return_value=inactive_but_otherwise_canonical,
    ):
        # Currently passes — TODO if we tighten this, invert the assertion.
        assert_meter_config("mtr_inactive_canonical")
