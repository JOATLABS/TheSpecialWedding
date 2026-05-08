"""Unit tests for the metering-hardening fixes.

Covers four gap-scenario closures:

* **SS1** — ``ensure_stripe_meter`` passes ``idempotency_key`` to
  ``Meter.create``, preventing duplicate meters when concurrent seed
  runs race during a rolling deploy.
* **C2** — ``ensure_stripe_meter`` validates an existing match via
  ``assert_meter_config`` before returning, refusing to silently bind
  to a misconfigured meter.
* **SS4** — ``update_wedding_meter_state`` retries once on Mongo failure
  and emits a grep-able ``STRIPE_MONGO_DIVERGENCE`` log on persistent
  failure.
* **C5** — ``coerce_period_start`` handles the four input shapes
  (string-with-Z, naive datetime, aware datetime, None/garbage) and —
  importantly — defaults naive datetimes to **UTC** rather than the
  process's local timezone, fixing a latent bug in the prior inline
  parser in ``app/api/wedding.py``.

References:

* docs/analysis/METERING_GAP_SCENARIOS_2026-05-04.md (the full gap doc)
* docs/analysis/METERING_REVIEW_2026-05-04_PART2.md §C5, §SS1, §SS4
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


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


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
    """Concurrent seed runs (e.g., rolling deploy) must share an
    idempotency key so Stripe's 24h cache returns the same meter id
    rather than creating duplicates. Pin the key shape."""
    from app.services.stripe_meter_helpers import ensure_stripe_meter

    listing = _listing()  # empty — forces create path
    new_meter = _meter(meter_id="mtr_just_created")

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

    assert result == "mtr_just_created"
    kwargs = mock_create.call_args.kwargs
    assert "idempotency_key" in kwargs, (
        "SS1 fix missing — Meter.create must pass idempotency_key. "
        "Without it, concurrent seed runs create duplicate meters."
    )
    assert kwargs["idempotency_key"] == "ensure_stripe_meter_wedding_active", (
        f"idempotency_key shape changed; expected the event_name-keyed form. "
        f"Got {kwargs['idempotency_key']!r}"
    )


def test_ss1_idempotency_key_differs_per_event_name():
    """Different event_names must get different idempotency keys —
    otherwise distinct meters would collide on the cache."""
    from app.services.stripe_meter_helpers import ensure_stripe_meter

    captured_keys = []

    def fake_create(**kwargs):
        captured_keys.append(kwargs.get("idempotency_key"))
        m = _meter(meter_id=f"mtr_for_{kwargs['event_name']}")
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

    assert len(set(captured_keys)) == 2, (
        f"Different event_names produced the same idempotency_key: {captured_keys}"
    )


# ===========================================================================
# C2 — ensure_stripe_meter validates existing matches
# ===========================================================================


def test_c2_existing_misconfigured_meter_is_not_silently_returned():
    """If Meter.list finds a matching meter that has the wrong formula,
    ensure_stripe_meter must NOT return it. It must raise so the
    operator gets a clear signal that the meter needs fixing."""
    from app.services.stripe_meter_helpers import ensure_stripe_meter

    bad_existing = _meter(meter_id="mtr_bad", formula="count")
    listing = _listing(bad_existing)

    with (
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.list",
            return_value=listing,
        ),
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
            return_value=bad_existing,
        ),
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.create"
        ) as mock_create,
    ):
        # The original ValueError from assert_meter_config bubbles up
        # unchanged; the "invalid config" framing lives in the helper's
        # log line, not the exception message. Match the underlying
        # rejection reason instead.
        with pytest.raises(ValueError, match="must be 'sum'"):
            ensure_stripe_meter("wedding_active")

    # And critically: no fresh meter was created.
    mock_create.assert_not_called()


def test_c2_existing_valid_meter_is_returned_without_create():
    """The happy path of C2: a matching existing meter that IS valid
    is returned without calling Meter.create. Idempotency contract."""
    from app.services.stripe_meter_helpers import ensure_stripe_meter

    good_existing = _meter(meter_id="mtr_good")
    listing = _listing(good_existing)

    with (
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.list",
            return_value=listing,
        ),
        patch(
            "app.services.stripe_meter_helpers.stripe.billing.Meter.retrieve",
            return_value=good_existing,
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
    """Happy path: Mongo update succeeds, retry helper returns True."""
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
    """Transient blip: first attempt raises, second succeeds. Helper
    must retry — this is the SS4 contract."""
    from app.utils.meter_state import update_wedding_meter_state

    coll = MagicMock()
    result_obj = MagicMock()
    result_obj.matched_count = 1
    coll.update_one = AsyncMock(
        side_effect=[
            ConnectionError("transient blip"),
            result_obj,
        ]
    )

    ok = await update_wedding_meter_state(
        coll, "wid_123", {"meter_pending": True}, context="test_retry"
    )

    assert ok is True
    assert coll.update_one.await_count == 2


@pytest.mark.asyncio
async def test_ss4_update_returns_false_after_persistent_failure(caplog):
    """Both attempts fail. Helper returns False AND emits a grep-able
    STRIPE_MONGO_DIVERGENCE log — operators can alert on that prefix."""
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
        "Failure log must include the context label so the operator "
        "can trace which call site diverged."
    )


@pytest.mark.asyncio
async def test_ss4_returns_false_when_no_document_matched():
    """Mongo accepts the update but matched_count=0 (wedding row was
    deleted between read and update). Treat as failure — helper returns
    False so the caller can log accordingly."""
    from app.utils.meter_state import update_wedding_meter_state

    coll = MagicMock()
    result_obj = MagicMock()
    result_obj.matched_count = 0  # no document matched
    coll.update_one = AsyncMock(return_value=result_obj)

    ok = await update_wedding_meter_state(
        coll, "wid_gone", {"x": 1}, context="test_no_match"
    )

    assert ok is False


# ===========================================================================
# C5 — coerce_period_start
# ===========================================================================


def test_c5_parses_iso_string_with_z_suffix():
    """Stripe sends ISO 8601 with Z suffix for UTC. The parser must
    handle that exact shape."""
    from app.utils.period_parsing import coerce_period_start

    result = coerce_period_start("2026-04-15T12:34:56Z")
    assert result is not None
    assert result.tzinfo is not None
    assert result.utcoffset() == timedelta(0)


def test_c5_parses_iso_string_with_explicit_offset():
    """ISO with +00:00 offset — semantically equivalent to Z."""
    from app.utils.period_parsing import coerce_period_start

    result = coerce_period_start("2026-04-15T12:34:56+00:00")
    assert result is not None
    assert result.utcoffset() == timedelta(0)


def test_c5_naive_datetime_assumed_utc_not_local():
    """The bug fix: a naive datetime from Mongo must be tagged as UTC,
    NOT as the process's local timezone. The previous inline parser in
    wedding.py used the local timezone — silently wrong on non-UTC
    servers.

    This test must catch the bug REGARDLESS of host timezone. On a UTC
    host, the buggy ``datetime.now(timezone.utc).astimezone().tzinfo``
    coincidentally resolves to ``timezone.utc`` and the assertion below
    would pass with the buggy code. To prove the helper isn't taking
    that code path, the companion test
    ``test_c5_naive_datetime_uses_utc_constant_not_runtime_local``
    asserts on the source code itself — see below."""
    from app.utils.period_parsing import coerce_period_start

    naive = datetime(2026, 4, 15, 12, 34, 56)  # no tzinfo
    result = coerce_period_start(naive)

    assert result is not None
    assert result.tzinfo is timezone.utc, (
        f"Naive datetime must be coerced to UTC, got {result.tzinfo!r}. "
        f"This is the C5 fix — see METERING_GAP_SCENARIOS_2026-05-04.md."
    )
    assert result.year == 2026 and result.hour == 12


def test_c5_naive_datetime_uses_utc_constant_not_runtime_local():
    """Host-tz-independent guard: assert the helper source uses
    ``timezone.utc`` directly, NOT ``datetime.now(...).astimezone(...)``.

    Why this exists: the assertion in
    ``test_c5_naive_datetime_assumed_utc_not_local`` checks the OUTPUT
    of the helper. On a UTC host (production!), the buggy
    ``datetime.now(timezone.utc).astimezone().tzinfo`` pattern
    accidentally produces ``timezone.utc`` because the local tz IS UTC.
    The output check would PASS even with the bug, on a UTC host.

    This test catches the bug at the SOURCE level — if anyone reverts
    to the buggy pattern, the static check fails immediately, regardless
    of where the test runs.

    Trade-off acknowledged: source-level checks are brittle to legitimate
    refactors. This one is narrowly scoped to the specific anti-pattern
    that bit us. If the helper is restructured (e.g., split into smaller
    functions), update this test to track the new shape.
    """
    import ast
    import inspect

    from app.utils import period_parsing

    src = inspect.getsource(period_parsing)
    tree = ast.parse(src)

    # Walk function bodies only — skip docstrings and module-level
    # constants/comments. The bug pattern is referenced in this module's
    # docstring as documentation; we only care about executable code.
    bad_chain = "datetime.now(timezone.utc).astimezone().tzinfo"

    def _check_node(node):
        # ast.unparse normalizes whitespace; check the executable form.
        try:
            body_src = ast.unparse(node)
        except Exception:
            return False
        return bad_chain in body_src

    bad_uses = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Strip the docstring before scanning the body
            body_nodes = node.body
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
        f"Use timezone.utc directly. See METERING_GAP_SCENARIOS §C5 "
        f"and the historical bug in app/api/wedding.py:174."
    )

    # Positive assertion: the canonical fix uses timezone.utc directly.
    assert "tzinfo=timezone.utc" in src, (
        "period_parsing.py no longer uses `tzinfo=timezone.utc` for the "
        "naive-datetime coercion. If you intentionally restructured, "
        "update this guard."
    )


def test_c5_aware_non_utc_datetime_normalized_to_utc():
    """If a datetime carries a non-UTC tz, normalize. Future-proofing
    against any path that sets a local-time tz."""
    from app.utils.period_parsing import coerce_period_start

    plus_five = timezone(timedelta(hours=5))
    aware = datetime(2026, 4, 15, 17, 34, 56, tzinfo=plus_five)
    # 17:34 in +05:00 == 12:34 UTC
    result = coerce_period_start(aware)
    assert result is not None
    assert result.utcoffset() == timedelta(0)
    assert result.hour == 12


def test_c5_returns_none_on_missing_value():
    """None / empty string must NOT raise. Callers treat None as
    'skip the period check', which is safer than guessing."""
    from app.utils.period_parsing import coerce_period_start

    assert coerce_period_start(None) is None
    assert coerce_period_start("") is None
    assert coerce_period_start("   ") is None


def test_c5_returns_none_on_unparseable_string():
    """Garbage strings shouldn't blow up the metering hook."""
    from app.utils.period_parsing import coerce_period_start

    assert coerce_period_start("not-a-date") is None
    assert coerce_period_start("2026-13-99") is None  # invalid month


def test_c5_returns_none_on_unexpected_type():
    """If something weird sneaks in (int, dict), don't raise."""
    from app.utils.period_parsing import coerce_period_start

    assert coerce_period_start(12345) is None
    assert coerce_period_start({"foo": "bar"}) is None
    assert coerce_period_start(["list"]) is None


def test_c5_already_utc_aware_passes_through():
    """An already-UTC-aware datetime should round-trip unchanged
    (semantically; tzinfo identity is OK to differ)."""
    from app.utils.period_parsing import coerce_period_start

    already = datetime(2026, 4, 15, 12, 0, 0, tzinfo=timezone.utc)
    result = coerce_period_start(already)
    assert result == already
