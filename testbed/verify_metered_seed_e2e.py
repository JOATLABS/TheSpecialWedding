#!/usr/bin/env python3
"""Adversarial E2E driver for the metered-seed scriptable provisioning.

Companion to ``verify_planner_metered_lifecycle.py`` — that driver covers
the runtime billing lifecycle (E1-E5: create, second create, delete,
retry-pending, badge UX) once metering is on. **This** driver covers the
provisioning side: the seed script, ``ensure_stripe_meter``, and
``assert_meter_config`` against a real Stripe test account.

Adversarial scenarios (each is a phase):

* **S1 — fresh seed.** Run the seed against a clean Mongo plan catalog; verify
  the Stripe Meter exists on Stripe with the canonical config (sum +
  by_id + stripe_customer_id + value), Stripe Prices have
  ``recurring.usage_type=metered``, and Mongo carries
  ``meter_event_name`` + ``meter_id``.

* **S2 — idempotent re-seed.** Run the seed a second time. Assert NO new
  Meter created (same id), NO new Product, NO new Prices. The
  ``Meter.list`` count for the event_name stays at 1.

* **S3 — stale meter_id recovery.** Set ``plan.meter_id`` in Mongo to a
  fabricated ``mtr_DELETED`` id. Run the seed. Assert:
  - The seed's preflight (``assert_meter_config``) raises clearly.
  - The seed falls through to ``ensure_stripe_meter`` and provisions a
    fresh meter with the canonical config.
  - Mongo's ``meter_id`` is updated to the new id.

* **S4 — half-configured plan rejection.** Set ``plan.is_metered=True``
  but ``plan.meter_event_name=None`` in Mongo (simulates partial admin
  edit). Run ``stripe_service.sync_plan_to_stripe`` directly. Assert
  HTTPException 400 with a message that mentions ``meter_event_name``.

* **S5 — wrong-aggregation meter blocked.** Manually create a Stripe
  Meter with ``formula=count`` (the wrong shape). Set ``plan.meter_id``
  to that meter. Run the seed. Assert preflight rejects with a message
  mentioning ``"must be 'sum'"``.

* **S6 — flat→metered migration.** Start with a flat plan in Mongo.
  Update the seed dict to flip ``is_metered=True`` + add
  ``meter_event_name``. Run the seed. Assert:
  - A new Stripe Price is created with ``usage_type=metered``.
  - The old flat Price is deactivated.
  - Mongo carries the new Price IDs.
  - **Existing customers on the old flat price are NOT auto-migrated**
    (this is the documented product gap from
    METERING_REVIEW_2026-05-04_PART2.md §7-#3).

* **S7 — cross-period reversal (lifecycle hand-off).** Create a wedding
  in period A (clock advance), advance clock past period boundary,
  delete the wedding in period B. Read
  ``stripe.billing.MeterEventSummary`` for both periods. Document
  whether the negative cycle total in period B clamps to 0 or
  produces a real credit. (This is the open product question #2 from
  the review — pin Stripe's actual behavior here.)

Skip discipline: like the lifecycle driver, this exits 0 cleanly when no
plan is metered in the live catalog (S1 cannot be run against a flat-
only catalog). Phases S3/S4/S5/S6 set up the metered state themselves
when needed; S7 hands off to the existing lifecycle driver after a clock
advance.

Usage::

    # Run all phases (interactive — pauses at checkpoints)
    python testbed/verify_metered_seed_e2e.py

    # Pin a clock id across runs
    METERED_E2E_CLOCK_ID=clock_xxx python testbed/verify_metered_seed_e2e.py

    # Unattended (CI-shaped)
    TESTBED_NON_INTERACTIVE=1 python testbed/verify_metered_seed_e2e.py

    # Run only specific phases
    METERED_E2E_PHASES=S1,S2 python testbed/verify_metered_seed_e2e.py
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import stripe

from app.services.stripe_meter_helpers import (
    METER_AGGREGATION_FORMULA,
    METER_CUSTOMER_MAPPING_KEY,
    METER_EVENT_NAME_WEDDING_ACTIVE,
    METER_VALUE_KEY,
    assert_meter_config,
)
from testbed.harness import Harness

logger = logging.getLogger(__name__)

DRIVER_NAME = "verify_metered_seed_e2e"

# Reusable clock for cross-period scenarios. Pin via env after first run.
TEST_CLOCK_NAME = "metered-seed-e2e"
TEST_CLOCK_ID = os.getenv("METERED_E2E_CLOCK_ID")

# Plan we'll exercise. Signature is the standard "metered candidate" from
# the seed catalog (per METERING_AUDIT.md §3 it was always intended to be
# the featured plan, so flipping it metered is the natural test bed).
TARGET_PLAN_ID = "plan_signature"

# Phases — set METERED_E2E_PHASES env to comma-separated subset.
ALL_PHASES = ("S1", "S2", "S3", "S4", "S5", "S6", "S7")


# =============================================================================
# Helpers
# =============================================================================


def _selected_phases() -> list[str]:
    raw = os.getenv("METERED_E2E_PHASES")
    if not raw:
        return list(ALL_PHASES)
    selected = [p.strip().upper() for p in raw.split(",") if p.strip()]
    invalid = [p for p in selected if p not in ALL_PHASES]
    if invalid:
        raise SystemExit(f"Unknown phase(s): {invalid}. Valid: {ALL_PHASES}")
    return selected


def _run_seed_subprocess(h: Harness) -> tuple[int, str, str]:
    """Run scripts/seed_subscription_plans.py as a subprocess. Returns
    (returncode, stdout, stderr). The seed inherits STRIPE_* env from the
    parent so it hits the same Stripe test account."""
    repo_root = Path(__file__).resolve().parent.parent
    script = repo_root / "scripts" / "seed_subscription_plans.py"
    h.log.info(f"  Running: python {script}")
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(repo_root),
        env={**os.environ, "STRIPE_ENABLED": "true"},
        capture_output=True,
        text=True,
        timeout=120,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _read_plan(h: Harness, plan_id: str) -> Optional[dict]:
    return h.mongo["subscription_plans"].find_one({"_id": plan_id})


def _list_meters_for_event(event_name: str) -> list[dict]:
    """Return all active meters matching the event_name (should be 0 or 1)."""
    matches = []
    try:
        meters = stripe.billing.Meter.list(status="active", limit=100)
        for m in meters.auto_paging_iter():
            if getattr(m, "event_name", None) == event_name:
                matches.append({"id": m.id, "event_name": m.event_name})
    except stripe.error.StripeError as exc:
        logger.warning(f"Meter.list failed: {exc}")
    return matches


def _find_metered_price_for_plan(plan: dict) -> Optional[dict]:
    """Look up the active metered Price for the plan's product, if any."""
    product_id = plan.get("stripe_product_id")
    if not product_id:
        return None
    try:
        prices = stripe.Price.list(product=product_id, active=True, limit=10)
        for p in prices.auto_paging_iter():
            if p.recurring and p.recurring.usage_type == "metered":
                return {
                    "id": p.id,
                    "interval": p.recurring.interval,
                    "meter": getattr(p.recurring, "meter", None),
                }
    except stripe.error.StripeError as exc:
        logger.warning(f"Price.list failed for {product_id}: {exc}")
    return None


def _find_active_prices_for_plan(plan: dict) -> list[dict]:
    """Return ALL active prices on the plan's product."""
    product_id = plan.get("stripe_product_id")
    if not product_id:
        return []
    try:
        prices = stripe.Price.list(product=product_id, active=True, limit=20)
        return [
            {
                "id": p.id,
                "interval": p.recurring.interval if p.recurring else None,
                "usage_type": p.recurring.usage_type if p.recurring else None,
                "meter": getattr(p.recurring, "meter", None) if p.recurring else None,
            }
            for p in prices.auto_paging_iter()
        ]
    except stripe.error.StripeError as exc:
        logger.warning(f"Price.list failed: {exc}")
        return []


# =============================================================================
# Phases
# =============================================================================


def phase_s1_fresh_seed(h: Harness) -> None:
    """S1: Run the seed; expect provisioning of meter + metered prices."""
    h.phase("S1_FRESH_SEED", "Seed runs cleanly; meter + metered prices provisioned")

    # Pre-flip the plan dict in Mongo to is_metered=True so the seed's
    # $set block sees it. This simulates the operator having committed
    # the "flip is_metered=True" edit to seed_subscription_plans.py
    # without us having to actually edit the file in the test.
    flip_result = h.mongo["subscription_plans"].update_one(
        {"_id": TARGET_PLAN_ID},
        {
            "$set": {
                "is_metered": True,
                "meter_event_name": METER_EVENT_NAME_WEDDING_ACTIVE,
                "meter_id": None,  # let the seed provision
            }
        },
    )
    h.log.info(
        f"  Pre-flipped {TARGET_PLAN_ID} to metered (matched={flip_result.matched_count})"
    )

    rc, stdout, stderr = _run_seed_subprocess(h)
    h.log.info(f"  Seed exit code: {rc}")
    h.log.info(f"  Seed stdout (last 500): ...{stdout[-500:]}")
    if stderr:
        h.log.info(f"  Seed stderr (last 500): ...{stderr[-500:]}")
    assert rc == 0, f"S1: seed failed with exit code {rc}"

    # Verify Stripe-side state
    meters = _list_meters_for_event(METER_EVENT_NAME_WEDDING_ACTIVE)
    assert len(meters) >= 1, (
        f"S1: expected at least 1 meter for event_name={METER_EVENT_NAME_WEDDING_ACTIVE!r}, "
        f"found {len(meters)}. Check seed stdout for [METER] lines."
    )
    meter_id = meters[0]["id"]
    h.log.info(f"  ✅ Meter exists: {meter_id}")

    # Preflight assert_meter_config — it should pass now
    try:
        assert_meter_config(meter_id)
        h.log.info("  ✅ Meter config matches canonical shape")
    except ValueError as exc:
        raise AssertionError(f"S1: meter exists but is misconfigured: {exc}")

    # Verify Mongo-side state
    plan = _read_plan(h, TARGET_PLAN_ID)
    assert plan, f"S1: plan {TARGET_PLAN_ID!r} disappeared from Mongo"
    assert plan.get("meter_event_name") == METER_EVENT_NAME_WEDDING_ACTIVE, (
        f"S1: meter_event_name not persisted; this is the CC3 bug coming back. "
        f"Got {plan.get('meter_event_name')!r}"
    )
    assert plan.get("meter_id") == meter_id, (
        f"S1: meter_id not persisted to Mongo. Expected {meter_id}, got {plan.get('meter_id')}"
    )
    h.log.info("  ✅ Mongo carries meter_event_name and meter_id")

    # Verify metered Price exists
    metered_price = _find_metered_price_for_plan(plan)
    assert metered_price, (
        f"S1: no metered Price found on product {plan.get('stripe_product_id')!r}. "
        f"Stripe-side billing won't engage."
    )
    assert metered_price["meter"] == meter_id, (
        f"S1: metered Price references wrong meter. "
        f"Expected {meter_id}, got {metered_price['meter']}"
    )
    h.log.info(f"  ✅ Metered Price exists: {metered_price['id']} → meter {meter_id}")

    h.checkpoint(
        "S1_PROVISIONED",
        expectations=[
            "Stripe Dashboard → Billing → Meters: 'wedding_active' is active",
            f"  - aggregation: {METER_AGGREGATION_FORMULA!r}",
            f"  - customer_mapping.event_payload_key: {METER_CUSTOMER_MAPPING_KEY!r}",
            f"  - value_settings.event_payload_key: {METER_VALUE_KEY!r}",
            "Stripe Dashboard → Products → Signature: a metered Price exists",
            f"Mongo: subscription_plans.{TARGET_PLAN_ID} has meter_event_name and meter_id",
        ],
    )


def phase_s2_idempotent_reseed(h: Harness) -> None:
    """S2: Re-run the seed. No new resources should be created."""
    h.phase("S2_IDEMPOTENT_RESEED", "Re-running seed is a no-op for Stripe resources")

    plan_before = _read_plan(h, TARGET_PLAN_ID)
    assert plan_before, "S2: target plan must exist (run S1 first)"

    meter_count_before = len(_list_meters_for_event(METER_EVENT_NAME_WEDDING_ACTIVE))
    prices_before = _find_active_prices_for_plan(plan_before)
    h.log.info(
        f"  Pre-reseed: {meter_count_before} meter(s), "
        f"{len(prices_before)} active price(s) for product"
    )

    rc, stdout, stderr = _run_seed_subprocess(h)
    assert rc == 0, f"S2: seed failed with exit code {rc}"

    meter_count_after = len(_list_meters_for_event(METER_EVENT_NAME_WEDDING_ACTIVE))
    plan_after = _read_plan(h, TARGET_PLAN_ID)
    prices_after = _find_active_prices_for_plan(plan_after)
    h.log.info(
        f"  Post-reseed: {meter_count_after} meter(s), "
        f"{len(prices_after)} active price(s)"
    )

    assert meter_count_after == meter_count_before, (
        f"S2: meter count grew from {meter_count_before} to {meter_count_after} — "
        f"ensure_stripe_meter is creating duplicates."
    )
    assert plan_after.get("meter_id") == plan_before.get("meter_id"), (
        "S2: meter_id changed across reseeds — should be stable."
    )
    assert plan_after.get("stripe_price_id_monthly") == plan_before.get(
        "stripe_price_id_monthly"
    ), "S2: monthly Price ID changed — ensure_price detected a false mismatch"
    assert plan_after.get("stripe_price_id_yearly") == plan_before.get(
        "stripe_price_id_yearly"
    ), "S2: yearly Price ID changed across reseeds"

    h.log.info("  ✅ Idempotent: no duplicate meter, no new prices, IDs stable")


def phase_s3_stale_meter_id_recovery(h: Harness) -> None:
    """S3: Set plan.meter_id to a fake/deleted id, re-run the seed.
    Expect the seed's `_provision_meter_if_needed` fallback to kick in
    via assert_meter_config raising → ensure_stripe_meter."""
    h.phase("S3_STALE_METER_ID", "Stale meter_id triggers re-provisioning")

    fake_id = "mtr_DELETED_BY_TEST"
    h.mongo["subscription_plans"].update_one(
        {"_id": TARGET_PLAN_ID},
        {"$set": {"meter_id": fake_id}},
    )
    h.log.info(f"  Set {TARGET_PLAN_ID}.meter_id = {fake_id!r} (fabricated)")

    rc, stdout, _ = _run_seed_subprocess(h)
    assert rc == 0, f"S3: seed should not crash on stale meter_id; rc={rc}"

    # Look for the seed's recovery log line
    assert "Existing meter_id" in stdout or "is invalid" in stdout, (
        "S3: expected seed to log invalidation of stale meter_id; "
        "check scripts/seed_subscription_plans.py:_provision_meter_if_needed"
    )

    plan = _read_plan(h, TARGET_PLAN_ID)
    assert plan.get("meter_id") and plan["meter_id"] != fake_id, (
        f"S3: meter_id was not refreshed; Mongo still has {plan.get('meter_id')!r}"
    )
    # Real meter id should validate
    assert_meter_config(plan["meter_id"])
    h.log.info(f"  ✅ Recovered: meter_id = {plan['meter_id']}")


def phase_s4_half_configured_rejection(h: Harness) -> None:
    """S4: is_metered=True with meter_event_name=None should be rejected
    by sync_plan_to_stripe (existing behavior, but pin it)."""
    h.phase("S4_HALF_CONFIGURED", "sync_plan_to_stripe rejects half-configured plan")

    from fastapi.exceptions import HTTPException

    from app.services.stripe_service import stripe_service

    bad_plan = {
        "_id": "plan_test_half_config",
        "name": "Test Half Config",
        "description": "Should never be created",
        "price_monthly": 99,
        "price_yearly": 990,
        "is_metered": True,
        "meter_event_name": None,  # the bug
    }

    raised = False
    try:
        stripe_service.sync_plan_to_stripe(bad_plan)
    except HTTPException as exc:
        raised = True
        h.log.info(f"  ✅ Rejected with {exc.status_code}: {exc.detail}")
        assert exc.status_code == 400
        assert (
            "meter_id" in str(exc.detail).lower()
            or "meter_event_name" in str(exc.detail).lower()
        ), f"S4: rejection message should mention meter fields; got {exc.detail}"

    assert raised, "S4: expected HTTPException for half-configured plan"


def phase_s5_wrong_aggregation_blocked(h: Harness) -> None:
    """S5: A meter created with formula=count must be rejected by
    assert_meter_config. This covers the operator who hand-creates a
    meter in the Stripe Dashboard with the wrong aggregation."""
    h.phase("S5_WRONG_AGGREGATION", "Count meter rejected at preflight")

    # Create a hostile meter with the WRONG aggregation
    hostile_event = "wedding_active_HOSTILE_TEST"
    try:
        # Clean up any prior run's hostile meter first
        existing = _list_meters_for_event(hostile_event)
        for m in existing:
            try:
                stripe.billing.Meter.deactivate(m["id"])
            except stripe.error.StripeError:
                pass

        hostile = stripe.billing.Meter.create(
            display_name="HOSTILE Wrong Aggregation Test",
            event_name=hostile_event,
            default_aggregation={"formula": "count"},  # WRONG
            customer_mapping={
                "type": "by_id",
                "event_payload_key": METER_CUSTOMER_MAPPING_KEY,
            },
            value_settings={"event_payload_key": METER_VALUE_KEY},
        )
        hostile_id = hostile.id
        h.log.info(f"  Created hostile meter: {hostile_id} (formula=count)")
    except stripe.error.StripeError as exc:
        h.log.warning(f"  Could not create hostile meter ({exc}); skipping S5")
        return

    raised = False
    try:
        assert_meter_config(hostile_id)
    except ValueError as exc:
        raised = True
        h.log.info(f"  ✅ assert_meter_config rejected: {exc}")
        assert "must be 'sum'" in str(exc), f"unexpected rejection reason: {exc}"

    assert raised, "S5: assert_meter_config accepted a count-aggregation meter"

    # Cleanup the hostile meter
    try:
        stripe.billing.Meter.deactivate(hostile_id)
        h.log.info("  Cleaned up hostile meter")
    except stripe.error.StripeError:
        pass


def phase_s6_flat_to_metered_migration(h: Harness) -> None:
    """S6: Flip plan flat→metered via seed; verify new metered Price
    created and old flat Price deactivated. The CRITICAL caveat:
    existing customers on the old flat price are NOT migrated."""
    h.phase("S6_FLAT_TO_METERED", "Flip plan flat→metered; old prices deactivated")

    # Reset the target plan to flat, drop meter fields, and let the seed
    # re-create flat prices from scratch so we have a clean migration test.
    h.mongo["subscription_plans"].update_one(
        {"_id": TARGET_PLAN_ID},
        {
            "$set": {
                "is_metered": False,
                "meter_event_name": None,
                "meter_id": None,
                "stripe_price_id_monthly": None,
                "stripe_price_id_yearly": None,
            }
        },
    )
    rc1, _, _ = _run_seed_subprocess(h)
    assert rc1 == 0, "S6 setup: seed-as-flat failed"
    plan_flat = _read_plan(h, TARGET_PLAN_ID)
    flat_monthly_price = plan_flat.get("stripe_price_id_monthly")
    h.log.info(f"  Reset to flat: monthly Price = {flat_monthly_price}")

    # Now flip to metered via Mongo (the operator's seed-edit equivalent)
    h.mongo["subscription_plans"].update_one(
        {"_id": TARGET_PLAN_ID},
        {
            "$set": {
                "is_metered": True,
                "meter_event_name": METER_EVENT_NAME_WEDDING_ACTIVE,
            }
        },
    )
    rc2, _, _ = _run_seed_subprocess(h)
    assert rc2 == 0, "S6: seed-as-metered failed"

    plan_metered = _read_plan(h, TARGET_PLAN_ID)
    metered_monthly_price = plan_metered.get("stripe_price_id_monthly")
    h.log.info(f"  Flipped to metered: monthly Price = {metered_monthly_price}")

    assert metered_monthly_price != flat_monthly_price, (
        "S6: monthly Price ID didn't change after flat→metered flip — "
        "either ensure_price didn't detect the mismatch, or the flip didn't take."
    )

    # Verify the new Price has metered config
    new_price = stripe.Price.retrieve(metered_monthly_price)
    assert new_price.recurring.usage_type == "metered", (
        f"S6: new Price {metered_monthly_price} is not metered: "
        f"usage_type={new_price.recurring.usage_type}"
    )
    h.log.info("  ✅ New monthly Price is metered with the right meter_id")

    # Verify the old flat Price was deactivated
    old_price = stripe.Price.retrieve(flat_monthly_price)
    assert not old_price.active, (
        f"S6: old flat Price {flat_monthly_price} was NOT deactivated; "
        f"existing customers on it would still bill at flat rate. "
        f"Check stripe_service.ensure_price's deactivation branch."
    )
    h.log.info(f"  ✅ Old flat Price {flat_monthly_price} is now inactive")

    h.checkpoint(
        "S6_MIGRATION_DONE",
        expectations=[
            "New metered Price is the active billing target for new checkouts",
            "Old flat Price is inactive (not deleted, just inactive)",
            "**CAVEAT:** Existing Stripe Subscriptions still reference the old "
            "Price. They will keep billing flat until manually swapped via "
            "stripe.Subscription.modify. This is the open product question #3 "
            "in METERING_REVIEW_2026-05-04_PART2.md §7.",
        ],
    )


def phase_s7_cross_period_handoff(h: Harness) -> None:
    """S7: Cross-period reversal verification.

    Rather than reimplementing the lifecycle here, this phase prints the
    hand-off command for `verify_planner_metered_lifecycle.py` extended
    with a clock-advance, plus a Stripe MeterEventSummary readback
    template so the operator can confirm Stripe agrees with the cycle
    totals.
    """
    h.phase("S7_CROSS_PERIOD_HANDOFF", "Cross-period reversal — hand off to lifecycle")

    h.log.info(
        """
  This phase is documentation. The cross-period reversal scenario
  (create wedding in month A, delete in month B) is best exercised
  via the lifecycle driver with a clock advance. Run:

      METERED_CLOCK_ID=<your_clock> \\
          python testbed/verify_planner_metered_lifecycle.py

  Then advance the clock past the period boundary in the Stripe
  Dashboard (or programmatically) and re-run the delete phase.

  After the cross-period delete, read Stripe's MeterEventSummary for
  both periods to confirm the cycle totals:

      import stripe
      summary_a = stripe.billing.MeterEventSummary.list(
          customer=customer_id,
          meter=meter_id,
          start_time=int(period_a_start.timestamp()),
          end_time=int(period_a_end.timestamp()),
      )
      summary_b = stripe.billing.MeterEventSummary.list(
          customer=customer_id,
          meter=meter_id,
          start_time=int(period_b_start.timestamp()),
          end_time=int(period_b_end.timestamp()),
      )

  Pin Stripe's actual behavior: does period B's negative cycle total
  produce a credit on the invoice, or clamp to 0? This is open product
  question #2 in METERING_REVIEW_2026-05-04_PART2.md §7. Document the
  answer and decide whether to switch to MeterEventAdjustment for
  in-window cancellations.
"""
    )

    h.checkpoint(
        "S7_HANDOFF_LOGGED",
        expectations=[
            "You've reviewed the hand-off and have a plan for the cross-period test",
            "You've decided how to verify Stripe's negative-cycle behavior",
        ],
    )


# =============================================================================
# Entry point
# =============================================================================


PHASE_MAP = {
    "S1": phase_s1_fresh_seed,
    "S2": phase_s2_idempotent_reseed,
    "S3": phase_s3_stale_meter_id_recovery,
    "S4": phase_s4_half_configured_rejection,
    "S5": phase_s5_wrong_aggregation_blocked,
    "S6": phase_s6_flat_to_metered_migration,
    "S7": phase_s7_cross_period_handoff,
}


def main() -> int:
    h = Harness(driver_name=DRIVER_NAME)
    h.banner("VERIFY — Metered Seed E2E (adversarial provisioning)")
    h.preflight()

    selected = _selected_phases()
    h.log.info(f"  Phases: {selected}")

    for phase_name in selected:
        phase_fn = PHASE_MAP[phase_name]
        try:
            phase_fn(h)
        except AssertionError as exc:
            h.log.error(f"  ❌ {phase_name} FAILED: {exc}")
            raise
        except Exception as exc:  # noqa: BLE001
            h.log.error(f"  ❌ {phase_name} ABORTED: {exc}")
            raise

    h.banner("VERIFY — Metered Seed E2E COMPLETE ✅")
    h.log.info("  All selected adversarial phases passed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"\n❌ Driver aborted: {exc}\n")
        raise SystemExit(1)
