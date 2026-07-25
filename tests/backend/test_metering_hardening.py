"""Unit tests for the metering-hardening fixes — SS1, C2, SS4, C5.

Each fix has at least one test that's been mutation-validated: deliberately
breaking the fix in code makes the test fail with a meaningful message.

References:
* docs/analysis/METERING_GAP_SCENARIOS_2026-05-04.md (the gap doc)
* docs/analysis/METERING_IMPLEMENTATION_2026-05-04.md (mutation-test proof)
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

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
):
    m = MagicMock()
    m.id = meter_id
    m.event_name = event_name
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
# SS1 — idempotency_key on Meter.create
# ===========================================================================


def test_ss1_meter_create_passes_idempotency_key():
    """Concurrent seed runs (rolling deploy) must share idempotency_key
    so Stripe's 24h cache returns the same meter id."""
    from app.services.stripe_meter_helpers import ensure_stripe_meter

    new_meter = _meter(meter_id="mtr_just_created")

    with (
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.list",
            return_value=_listing(),
        ),
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.create",
            return_value=new_meter,
        ) as mock_create,
    ):
        result = ensure_stripe_meter("wedding_active")

    assert result == "mtr_just_created"
    kwargs = mock_create.call_args.kwargs
    assert "idempotency_key" in kwargs, (
        "SS1 fix missing — Meter.create must pass idempotency_key. "
        "Without it, concurrent seed runs create duplicate meters."
    )
    assert kwargs["idempotency_key"] == "ensure_stripe_meter_wedding_active"


def test_ss1_idempotency_key_differs_per_event_name():
    """Distinct meters must get distinct idempotency keys."""
    from app.services.stripe_meter_helpers import ensure_stripe_meter

    captured = []

    def fake_create(**kwargs):
        captured.append(kwargs.get("idempotency_key"))
        m = _meter(meter_id=f"mtr_{kwargs['event_name']}")
        m.event_name = kwargs["event_name"]
        return m

    with (
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.list",
            return_value=_listing(),
        ),
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.create",
            side_effect=fake_create,
        ),
    ):
        ensure_stripe_meter("wedding_active")
        ensure_stripe_meter("api_calls")

    assert len(set(captured)) == 2, f"Same key for distinct events: {captured}"


# ===========================================================================
# C2 — ensure_stripe_meter validates existing matches
# ===========================================================================


def test_c2_existing_misconfigured_meter_is_not_silently_returned():
    """A matching but misconfigured meter must raise, not be returned."""
    from app.services.stripe_meter_helpers import ensure_stripe_meter

    bad = _meter(meter_id="mtr_bad", formula="count")

    with (
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.list",
            return_value=_listing(bad),
        ),
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
            return_value=bad,
        ),
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.create"
        ) as mock_create,
    ):
        # The original ValueError from assert_meter_config bubbles up.
        with pytest.raises(ValueError, match="must be 'sum'"):
            ensure_stripe_meter("wedding_active")

    mock_create.assert_not_called()


def test_c2_existing_valid_meter_is_returned_without_create():
    """Matching valid meter is returned; no new create call."""
    from app.services.stripe_meter_helpers import ensure_stripe_meter

    good = _meter(meter_id="mtr_good")

    with (
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.list",
            return_value=_listing(good),
        ),
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
            return_value=good,
        ),
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.create"
        ) as mock_create,
    ):
        result = ensure_stripe_meter("wedding_active")

    assert result == "mtr_good"
    mock_create.assert_not_called()


# ===========================================================================
# SS4 — update_wedding_meter_state retry behavior
# ===========================================================================


@pytest.mark.asyncio
async def test_ss4_update_succeeds_on_first_attempt():
    from app.utils.meter_state import update_wedding_meter_state

    coll = MagicMock()
    result_obj = MagicMock()
    result_obj.matched_count = 1
    coll.update_one = AsyncMock(return_value=result_obj)

    ok = await update_wedding_meter_state(
        coll, "wid_123", {"last_billed_at": "now"}, context="test_happy"
    )

    assert ok is True
    coll.update_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_ss4_update_retries_once_on_failure_then_succeeds():
    """Transient blip: first raises, second succeeds. Retry contract."""
    from app.utils.meter_state import update_wedding_meter_state

    coll = MagicMock()
    result_obj = MagicMock()
    result_obj.matched_count = 1
    coll.update_one = AsyncMock(
        side_effect=[ConnectionError("transient blip"), result_obj]
    )

    ok = await update_wedding_meter_state(
        coll, "wid_123", {"meter_pending": True}, context="test_retry"
    )

    assert ok is True
    assert coll.update_one.await_count == 2


@pytest.mark.asyncio
async def test_ss4_update_returns_false_after_persistent_failure(caplog):
    """Both attempts fail → False AND grep-able STRIPE_MONGO_DIVERGENCE log."""
    import logging

    from app.utils.meter_state import update_wedding_meter_state

    coll = MagicMock()
    coll.update_one = AsyncMock(side_effect=ConnectionError("dead mongo"))

    with caplog.at_level(logging.ERROR):
        ok = await update_wedding_meter_state(
            coll, "wid_dead", {"x": 1}, context="test_persistent_fail"
        )

    assert ok is False
    assert coll.update_one.await_count == 2
    error_logs = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert any("STRIPE_MONGO_DIVERGENCE" in r.getMessage() for r in error_logs), (
        "SS4: persistent failure must emit the grep-able "
        "STRIPE_MONGO_DIVERGENCE log prefix for ops alerting."
    )
    assert any("test_persistent_fail" in r.getMessage() for r in error_logs), (
        "Failure log must include the context label."
    )


@pytest.mark.asyncio
async def test_ss4_returns_false_when_no_document_matched():
    from app.utils.meter_state import update_wedding_meter_state

    coll = MagicMock()
    result_obj = MagicMock()
    result_obj.matched_count = 0
    coll.update_one = AsyncMock(return_value=result_obj)

    ok = await update_wedding_meter_state(
        coll, "wid_gone", {"x": 1}, context="test_no_match"
    )

    assert ok is False


# ===========================================================================
# C5 — coerce_period_start with the source-level guard from mutation pass
# ===========================================================================


def test_c5_parses_iso_string_with_z_suffix():
    from app.utils.period_parsing import coerce_period_start

    result = coerce_period_start("2026-04-15T12:34:56Z")
    assert result is not None
    assert result.utcoffset() == timedelta(0)


def test_c5_parses_iso_string_with_explicit_offset():
    from app.utils.period_parsing import coerce_period_start

    result = coerce_period_start("2026-04-15T12:34:56+00:00")
    assert result is not None
    assert result.utcoffset() == timedelta(0)


def test_c5_naive_datetime_assumed_utc_not_local():
    """The bug fix: naive datetime tagged as UTC, not local timezone.

    On a UTC host, the buggy ``datetime.now(timezone.utc).astimezone().tzinfo``
    accidentally produces a UTC tzinfo too — but it's a NEW instance, not
    the singleton, so ``is timezone.utc`` (object identity) catches it.
    Companion source-level test below catches the bug regardless of host TZ."""
    from app.utils.period_parsing import coerce_period_start

    naive = datetime(2026, 4, 15, 12, 34, 56)
    result = coerce_period_start(naive)

    assert result is not None
    assert result.tzinfo is timezone.utc, (
        f"Naive datetime must be coerced to UTC, got {result.tzinfo!r}. "
        f"This is the C5 fix — see METERING_GAP_SCENARIOS_2026-05-04.md."
    )
    assert result.year == 2026 and result.hour == 12


def test_c5_naive_datetime_uses_utc_constant_not_runtime_local():
    """Host-tz-independent guard from the mutation pass — asserts the
    helper source uses ``timezone.utc`` directly, NOT the buggy
    ``datetime.now(timezone.utc).astimezone().tzinfo`` chain.

    The output-level assertion above happens to catch the bug via object
    identity, but a refactor to ``==`` instead of ``is`` would silently
    pass on UTC hosts. This source-level check fires regardless."""
    import ast
    import inspect

    from app.utils import period_parsing

    src = inspect.getsource(period_parsing)
    tree = ast.parse(src)
    bad_chain = "datetime.now(timezone.utc).astimezone().tzinfo"

    def _check_node(node):
        try:
            return bad_chain in ast.unparse(node)
        except Exception:
            return False

    bad_uses = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body_nodes = node.body
            # Skip the docstring (which legitimately mentions the bug).
            if (
                body_nodes
                and isinstance(body_nodes[0], ast.Expr)
                and isinstance(body_nodes[0].value, ast.Constant)
                and isinstance(body_nodes[0].value.value, str)
            ):
                body_nodes = body_nodes[1:]
            for stmt in body_nodes:
                if _check_node(stmt):
                    bad_uses.append(node.name)
                    break

    assert not bad_uses, (
        f"period_parsing.py reintroduced the buggy local-tz coercion "
        f"pattern {bad_chain!r} in function(s): {bad_uses}. This works "
        f"accidentally on UTC hosts but breaks on any other timezone. "
        f"See METERING_GAP_SCENARIOS §C5."
    )
    # `datetime.UTC` is the same singleton object as `datetime.timezone.utc`
    # (added as an alias in 3.11), so either spelling satisfies this guard.
    # What must not change is that the coercion tags a fixed UTC constant
    # rather than deriving one from the host clock.
    assert "tzinfo=UTC" in src or "tzinfo=timezone.utc" in src, (
        "period_parsing.py no longer tags the naive-datetime coercion with a "
        "fixed UTC constant (`tzinfo=UTC` / `tzinfo=timezone.utc`). If you "
        "intentionally restructured, update this guard."
    )


def test_c5_aware_non_utc_datetime_normalized_to_utc():
    from app.utils.period_parsing import coerce_period_start

    plus_five = timezone(timedelta(hours=5))
    aware = datetime(2026, 4, 15, 17, 34, 56, tzinfo=plus_five)
    result = coerce_period_start(aware)
    assert result is not None
    assert result.utcoffset() == timedelta(0)
    assert result.hour == 12


def test_c5_returns_none_on_missing_value():
    from app.utils.period_parsing import coerce_period_start

    assert coerce_period_start(None) is None
    assert coerce_period_start("") is None
    assert coerce_period_start("   ") is None


def test_c5_returns_none_on_unparseable_string():
    from app.utils.period_parsing import coerce_period_start

    assert coerce_period_start("not-a-date") is None
    assert coerce_period_start("2026-13-99") is None


def test_c5_returns_none_on_unexpected_type():
    from app.utils.period_parsing import coerce_period_start

    assert coerce_period_start(12345) is None
    assert coerce_period_start({"foo": "bar"}) is None
    assert coerce_period_start(["list"]) is None


def test_c5_already_utc_aware_passes_through():
    from app.utils.period_parsing import coerce_period_start

    already = datetime(2026, 4, 15, 12, 0, 0, tzinfo=timezone.utc)
    result = coerce_period_start(already)
    assert result == already


# ===========================================================================
# S1 lesson — the seed script is hardcoded source-of-truth for plan config
#
# Pin the assumption that bit us in live verification: the seed iterates
# its hardcoded `plans = [...]` list, NOT Mongo. Anyone who tries to
# "fix" the seed to read from Mongo would change this contract — and
# break the testbed driver's design (which calls helpers directly
# rather than expecting seed-from-Mongo). See live verification log
# 2026-05-08 02:17:55 — S1 phase failed because the seed overwrote the
# Mongo state the test setup wrote.
# ===========================================================================


def test_seed_preserves_admin_mutable_plan_config_but_owns_billing_shape():
    """The seed script bootstraps canonical plans and enforces billing shape.

    This test scans the seed source for Mongo reads that would drive the
    seed catalog. The legitimate Mongo reads are the dedup pass at startup,
    loading an existing plan so root-admin price/features/visibility changes
    are preserved, and the billing-model transition guard that checks whether
    active subscriptions would be stranded on old Stripe Prices.
    """
    from pathlib import Path

    seed_path = Path(PROJECT_ROOT) / "scripts" / "seed_subscription_plans.py"
    src = seed_path.read_text()

    # The dedup pass at startup reads collection.find({}). The transition
    # guard may read one existing plan to compare billing_model, but NO Mongo
    # state should drive which plans or fields are seeded.
    forbidden_patterns = [
        # Iterating Mongo to choose what to seed:
        "for plan in collection.find",
    ]

    for pattern in forbidden_patterns:
        assert pattern not in src, (
            f"scripts/seed_subscription_plans.py contains {pattern!r}. "
            f"The seed is intentionally hardcoded source-of-truth for "
            f"plan config. Reading Mongo to drive seeding would break "
            f"the testbed driver's design assumption that the seed "
            f"won't respect Mongo overrides. See "
            f"docs/analysis/METERING_IMPLEMENTATION_2026-05-04.md "
            f"for the live verification log that pinned this."
        )

    # Positive assertion: the seed iterates a hardcoded list.
    assert "for plan in plans:" in src, (
        "Seed no longer iterates the hardcoded `plans` list. If the "
        "iteration shape changed, update this test."
    )
    assert "_build_effective_seed_plan(plan, existing_plan)" in src
    assert (
        "_guard_seed_billing_model_transition(plan_id, existing_plan, plan_for_sync)"
        in src
    )
    assert '"price_monthly": plan_with_stripe["price_monthly"]' in src
    assert '"features": plan_with_stripe.get("features", {})' in src
    assert '"billing_model": plan_with_stripe.get(' in src
