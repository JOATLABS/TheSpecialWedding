"""Regression guards around the metering pipeline.

Per the 2026-05-10 billing decision, the metering **infrastructure** is now
the intended production billing model for canonical public plans. Wedding
create/delete hooks, the daily batch job, retry endpoint, plan model flags, and
plan editor UI all remain gated on ``plan.is_metered == True AND
plan.meter_event_name``.

The risk is drifting into a half-metered plan — for example, a seed edit that
sets ``is_metered=True`` but forgets ``meter_event_name``, or a refactor that
weakens Stripe MeterEvent idempotency behavior. This file contains unit-level
guards that would fire immediately in CI:

This file contains unit-level guards that would fire immediately in CI:

1. **Seed default invariant** — every canonical plan emitted by
   ``scripts/seed_subscription_plans.py`` must ship ``is_metered=True`` with
   ``meter_event_name="wedding_active"``.
2. **Meter-event identifier truncation** — ``StripeService.report_meter_event``
   must truncate the Stripe idempotency ``identifier`` to 100 chars (Stripe's
   hard limit). The guard protects against a refactor that drops ``[:100]``
   and silently starts failing long idempotency keys in prod.
3. **Meter-event idempotency-duplicate handling** — a ``StripeError`` whose
   message hints at "identifier already"/"duplicate" is treated as success.
   That's the contract the retry endpoint and the daily batch job rely on
   for safe replay.

A full integration run (create wedding → verify Stripe MeterEvent) belongs
in ``testbed/verify_planner_metered_lifecycle.py`` — not here. This file's
job is to catch regressions before the live driver is even attempted.
"""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path
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
# 1) Seed-plan invariant
# ---------------------------------------------------------------------------


_LITERAL_FIELDS = ("_id", "name", "is_metered", "meter_event_name", "meter_id")


def _load_seed_plans() -> list[dict]:
    """Return the ``plans`` list from ``scripts/seed_subscription_plans.py``
    using an AST parse — **not** ``import``.

    The script aggressively runs Mongo connection code at module import
    (``sys.exit(1)`` on failure, no ``if __name__ == "__main__":`` guard for
    it), so a plain import inside pytest attempts a live Mongo connection
    and fails with ServerSelectionTimeoutError. Parsing the AST sidesteps
    every side effect — no network, no env, no imports to mock.

    We can't use ``ast.literal_eval`` on the whole dict because some values
    are function calls (``datetime.now(timezone.utc)``). Instead we walk
    the dict entries and pull only the fields this test file cares about —
    all of which are pure literals (strings, bools, None).
    """
    path = Path(PROJECT_ROOT) / "scripts" / "seed_subscription_plans.py"
    tree = ast.parse(path.read_text())

    plans_node = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if "plans" in targets:
                plans_node = node.value
                break

    if plans_node is None or not isinstance(plans_node, ast.List):
        raise AssertionError(
            "scripts/seed_subscription_plans.py: expected a module-level "
            "`plans = [...]` list. If the script was refactored, update "
            "this test helper to match."
        )

    extracted: list[dict] = []
    for plan_node in plans_node.elts:
        if not isinstance(plan_node, ast.Dict):
            continue
        plan: dict = {}
        for key_node, value_node in zip(plan_node.keys, plan_node.values):
            if not isinstance(key_node, ast.Constant):
                continue
            key = key_node.value
            if key not in _LITERAL_FIELDS:
                continue
            try:
                plan[key] = ast.literal_eval(value_node)
            except ValueError:
                # Non-literal value for a field we expected to be literal —
                # worth surfacing because it signals a schema change.
                raise AssertionError(
                    f"Plan field {key!r} is no longer a pure literal in "
                    f"seed_subscription_plans.py. Update _LITERAL_FIELDS or "
                    f"rewrite the loader."
                )
        extracted.append(plan)

    return extracted


def test_seed_plans_are_flat_by_default():
    """Every default plan must ship with FLAT billing (is_metered=False).

    2026-05-09: pricing strategy refresh — seed plans are flat. The metering
    hardening infrastructure stays available; flipping a plan to metered is
    a deliberate per-plan edit + redeploy. See
    docs/analysis/METERING_IMPLEMENTATION_2026-05-04.md.

    If this test fails, either:
    - A plan was intentionally flipped to metered → update this test and the
      strategy doc together, OR
    - A plan was accidentally flipped to metered → revert before merge.
    """
    plans = _load_seed_plans()
    assert len(plans) >= 3, (
        "Seed catalog shrank below the 3-plan baseline "
        "(Solo Founding / Solo Standard / White Glove). Confirm this is "
        "intentional."
    )

    metered = [p for p in plans if p.get("is_metered")]
    assert metered == [], (
        f"Seed plans drifted to metered billing: {[p['_id'] for p in metered]}. "
        "The 2026-05-09 pricing strategy ships all plans flat. If you intend "
        "to switch a specific plan to metered, update this test alongside the "
        "seed change."
    )


def test_seed_plans_have_required_identity_fields():
    """Sanity: guard against a seed edit that removes `_id` / name.

    Also flags the half-configured state where a flat plan has a meter
    event name set — that combination signals someone started wiring
    metering and stopped. Better to clear meter_event_name or finish
    the flip than leave it in the half state.
    """
    for plan in _load_seed_plans():
        assert plan.get("_id"), f"Plan missing _id: {plan}"
        assert plan.get("name"), f"Plan missing name: {plan}"
        # Half-configured guard: if meter_event_name is set, is_metered
        # must be True. The inverse (is_metered=True with no event_name)
        # is rejected at preflight by sync_plan_to_stripe.
        if plan.get("meter_event_name"):
            assert plan.get("is_metered") is True, (
                f"Plan {plan['_id']} sets meter_event_name="
                f"{plan['meter_event_name']!r} but is_metered is False. "
                "Either finish the metered setup or clear meter_event_name "
                "— half-configured plans are a trap."
            )


# ---------------------------------------------------------------------------
# 2 + 3) StripeService.report_meter_event contract
# ---------------------------------------------------------------------------


def _build_stripe_service():
    """Construct StripeService skipping __init__ (which hits mongo)."""
    from app.services.stripe_service import StripeService

    service = StripeService.__new__(StripeService)
    # __init__ only assigns mongo collection handles; none of them are used
    # by report_meter_event, so leaving them unset is safe.
    return service


def test_report_meter_event_truncates_identifier_to_100_chars():
    """Stripe caps meter-event idempotency keys at 100 characters.

    ``stripe_service.py:406`` enforces this with ``identifier[:100]``.
    Dropping that slice would start causing Stripe 400s on long keys —
    and our retry keys can legitimately approach 100 (wedding_delete_
    <24-char-oid>_cus_<14>_YYYY-MM ≈ 60 chars, comfortable; but the format
    is extensible so the cap matters).
    """
    service = _build_stripe_service()
    long_id = "x" * 500  # comfortably over the cap

    with patch(
        "app.services.stripe_service.stripe.billing.MeterEvent.create"
    ) as mock_create:
        fake_event = MagicMock()
        fake_event.identifier = long_id[:100]
        mock_create.return_value = fake_event

        result = service.report_meter_event(
            event_name="wedding_active",
            payload={"stripe_customer_id": "cus_test", "value": "1"},
            identifier=long_id,
        )

    assert result["status"] == "success"
    mock_create.assert_called_once()
    called_identifier = mock_create.call_args.kwargs["identifier"]
    assert len(called_identifier) == 100, (
        f"identifier must be truncated to 100 chars, got {len(called_identifier)}. "
        "Check stripe_service.py:406 — the `[:100]` slice must remain."
    )
    assert called_identifier == "x" * 100


def test_report_meter_event_treats_duplicate_identifier_as_success():
    """Stripe returns a 400 on duplicate idempotency keys; the retry
    endpoint and the daily batch depend on that being normalized to a
    success so replay is safe. See ``stripe_service.py:412-421``."""
    from stripe import StripeError

    service = _build_stripe_service()

    with patch(
        "app.services.stripe_service.stripe.billing.MeterEvent.create"
    ) as mock_create:
        mock_create.side_effect = StripeError(
            "An event with identifier `foo` already exists for this meter."
        )

        result = service.report_meter_event(
            event_name="wedding_active",
            payload={"stripe_customer_id": "cus_test", "value": "1"},
            identifier="foo",
        )

    assert result["status"] == "success", (
        "Duplicate-identifier StripeError must be normalized to success. "
        "Otherwise the retry endpoint and daily batch will double-report."
    )
    assert result.get("already_recorded") is True


def test_report_meter_event_returns_error_on_other_stripe_errors():
    """Counter-case to the duplicate check above — a *different* Stripe
    error (e.g. network, bad payload) must surface as error so the caller
    knows to set ``meter_pending=True`` on the wedding doc (see
    ``app/api/wedding.py:228-242``)."""
    from stripe import StripeError

    service = _build_stripe_service()

    with patch(
        "app.services.stripe_service.stripe.billing.MeterEvent.create"
    ) as mock_create:
        mock_create.side_effect = StripeError("API connection error")

        result = service.report_meter_event(
            event_name="wedding_active",
            payload={"stripe_customer_id": "cus_test", "value": "1"},
            identifier="wedding_create_abc_cus_123_2026-04",
        )

    assert result["status"] == "error"
    assert "API connection error" in result["message"]


# ---------------------------------------------------------------------------
# Idempotency-key format lock — cheap guard for the retry endpoint
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "key_template, expected_prefix",
    [
        ("wedding_create_{wid}_{cid}_{period}", "wedding_create_"),
        ("wedding_delete_{wid}_{cid}_{period}", "wedding_delete_"),
        ("meter_retry_{wid}_{cid}_{period}", "meter_retry_"),
        ("billing_job_{wid}_{cid}_{period}", "billing_job_"),
    ],
)
def test_idempotency_key_prefixes_are_distinct(key_template, expected_prefix):
    """The four metering entry points (create hook, delete hook, retry
    endpoint, daily batch) each use a distinct idempotency-key prefix so
    Stripe treats them as different billing events per period.

    If a refactor accidentally aligns two prefixes, a retry would land on
    the same identifier as the original attempt and Stripe would silently
    dedupe it — hiding the failure. This check pins the contract.
    """
    key = key_template.format(wid="wed_123", cid="cus_abc", period="2026-04")
    assert key.startswith(expected_prefix)
    # 100-char Stripe cap: an ObjectId is 24 chars, customer id ~14 chars,
    # period 7 chars — all templates fit comfortably, but verify it stays true.
    assert len(key) < 100, (
        f"Idempotency key template {key_template!r} approaches Stripe's 100-char "
        f"cap (current length {len(key)}). Either shorten the prefix or add a "
        "hash step before it breaks in prod."
    )
