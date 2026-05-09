#!/usr/bin/env python3
"""Adversarial E2E driver for the metered-seed scriptable provisioning.

Companion to ``verify_planner_metered_lifecycle.py`` — that driver covers
the runtime billing lifecycle once metering is on. **This** driver covers
the provisioning side: ``ensure_stripe_meter`` and ``assert_meter_config``
against a real Stripe test account.

DESIGN NOTE — why this driver does NOT subprocess the seed
==========================================================

Live verification on 2026-05-08 02:17 surfaced a fundamental design flaw
in an earlier version of this driver: it tried to flip Mongo state to
``is_metered=True`` then run ``scripts/seed_subscription_plans.py`` and
expect the seed to provision the meter.

That doesn't work. The seed script is **intentionally** the source of
truth for plan config — it iterates its hardcoded ``plans = [...]`` list
and overwrites Mongo via ``$set``. So any test-time Mongo flip is
silently reverted on the next seed run.

Operators flip plans by editing ``seed_subscription_plans.py`` and
redeploying. That's a deploy-shape integration test, not something a
testbed driver can simulate without a code edit + redeploy cycle.

So this driver tests the **HELPERS** directly — ``ensure_stripe_meter``,
``assert_meter_config``, and ``stripe_service.sync_plan_to_stripe`` —
which are what the seed and runtime both use. The "does the seed
correctly call the helpers when given a metered plan" question is
covered by:

* Unit tests in ``tests/backend/test_metering_hardening.py`` (source-level
  guards, mock-driven flow tests)
* The ``test_seed_is_hardcoded_source_of_truth_for_plan_config`` test
  that pins the seed's intentional design

Adversarial scenarios (each is a phase):

* **S1 — fresh meter provisioning.** Call ``ensure_stripe_meter`` directly.
  Verify Stripe-side meter exists with canonical config; verify
  ``assert_meter_config`` validates it.

* **S2 — idempotent re-provisioning.** Call ``ensure_stripe_meter`` again.
  Same meter id returned. ``Meter.list`` count for event_name stays at 1.

* **S3 — stale meter_id rejection.** Call ``assert_meter_config`` with a
  fabricated id. Expect ``ValueError("not found")``. Then re-call
  ``ensure_stripe_meter`` and verify it returns a (different) valid id.

* **S4 — half-configured plan rejection.** Call
  ``stripe_service.sync_plan_to_stripe`` with ``is_metered=True`` and
  ``meter_event_name=None``. Expect HTTPException 400.

* **S5 — wrong-aggregation meter blocked.** Manually create a Stripe Meter
  with ``formula=count``. Call ``assert_meter_config(that_meter_id)``.
  Expect ``ValueError`` mentioning "must be 'sum'". Cleanup the hostile
  meter.

* **S6 — flat→metered Stripe Price migration.** Call
  ``stripe_service.sync_plan_to_stripe`` directly with a plan dict
  carrying an existing flat ``stripe_price_id_*``. Verify a NEW metered
  price is created and the old flat price is deactivated.

Skip discipline: each phase is independent. Set ``METERED_E2E_PHASES`` to
a comma-separated subset to run only specific phases.

Usage::

    # All phases (interactive — pauses at checkpoints)
    python testbed/verify_metered_seed_e2e.py

    # Specific phases
    METERED_E2E_PHASES=S1,S2 python testbed/verify_metered_seed_e2e.py

    # Unattended
    TESTBED_NON_INTERACTIVE=1 python testbed/verify_metered_seed_e2e.py
"""

from __future__ import annotations

import logging
import os
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
    ensure_stripe_meter,
)
from testbed.harness import Harness

logger = logging.getLogger(__name__)

DRIVER_NAME = "verify_metered_seed_e2e"
TARGET_PLAN_ID = "plan_signature"
ALL_PHASES = ("S1", "S2", "S3", "S4", "S5", "S6")


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


def _read_plan(h: Harness, plan_id: str) -> Optional[dict]:
    return h.mongo["subscription_plans"].find_one({"_id": plan_id})


def _list_meters_for_event(event_name: str) -> list[dict]:
    matches = []
    try:
        meters = stripe.billing.Meter.list(status="active", limit=100)
        for m in meters.auto_paging_iter():
            if getattr(m, "event_name", None) == event_name:
                matches.append({"id": m.id, "event_name": m.event_name})
    except stripe.error.StripeError as exc:
        logger.warning(f"Meter.list failed: {exc}")
    return matches


# =============================================================================
# Phases
# =============================================================================


def phase_s1_fresh_meter_provisioning(h: Harness) -> None:
    """S1: ensure_stripe_meter creates (or finds) the canonical meter."""
    h.phase(
        "S1_FRESH_METER",
        "Provision meter via ensure_stripe_meter directly (NOT via seed subprocess)",
    )

    meter_id = ensure_stripe_meter(
        event_name=METER_EVENT_NAME_WEDDING_ACTIVE,
        display_name="Signature (wedding_active) — testbed",
    )
    h.log.info(f"  ✅ Meter id returned: {meter_id}")
    assert meter_id and meter_id.startswith("mtr_"), (
        f"S1: expected mtr_… id, got {meter_id!r}"
    )

    # Verify on Stripe side
    matches = _list_meters_for_event(METER_EVENT_NAME_WEDDING_ACTIVE)
    assert len(matches) >= 1, (
        f"S1: Stripe Meter.list returned {len(matches)} meters for "
        f"event_name={METER_EVENT_NAME_WEDDING_ACTIVE!r}; expected ≥1"
    )
    h.log.info(f"  ✅ Stripe-side: {len(matches)} active meter(s) for event_name")

    # Verify canonical config
    try:
        assert_meter_config(meter_id)
        h.log.info("  ✅ assert_meter_config validates the canonical shape")
    except ValueError as exc:
        raise AssertionError(f"S1: meter exists but is misconfigured: {exc}")

    h.checkpoint(
        "S1_PROVISIONED",
        expectations=[
            "Stripe Dashboard → Billing → Meters: 'wedding_active' is active",
            f"  - aggregation: {METER_AGGREGATION_FORMULA!r}",
            f"  - customer_mapping.event_payload_key: {METER_CUSTOMER_MAPPING_KEY!r}",
            f"  - value_settings.event_payload_key: {METER_VALUE_KEY!r}",
            f"meter_id: {meter_id}",
        ],
    )


def phase_s2_idempotent_reprovisioning(h: Harness) -> None:
    """S2: second call returns same id; meter count stays at 1."""
    h.phase("S2_IDEMPOTENT", "ensure_stripe_meter is idempotent (SS1 fix in action)")

    count_before = len(_list_meters_for_event(METER_EVENT_NAME_WEDDING_ACTIVE))
    h.log.info(f"  Pre-call: {count_before} meter(s) for event_name")

    meter_id_1 = ensure_stripe_meter(event_name=METER_EVENT_NAME_WEDDING_ACTIVE)
    meter_id_2 = ensure_stripe_meter(event_name=METER_EVENT_NAME_WEDDING_ACTIVE)

    count_after = len(_list_meters_for_event(METER_EVENT_NAME_WEDDING_ACTIVE))
    h.log.info(f"  Post-call: {count_after} meter(s); ids {meter_id_1} == {meter_id_2}")

    assert meter_id_1 == meter_id_2, (
        f"S2: ensure_stripe_meter returned DIFFERENT ids for back-to-back "
        f"calls: {meter_id_1!r} vs {meter_id_2!r}. SS1 idempotency_key broken."
    )
    assert count_after == count_before or count_after == 1, (
        f"S2: meter count grew from {count_before} to {count_after}. "
        f"Either ensure_stripe_meter created a duplicate, or another "
        f"meter exists for this event_name from a prior test run."
    )

    h.log.info("  ✅ Idempotent: same id returned, no duplicate created")


def phase_s3_stale_meter_id_rejection(h: Harness) -> None:
    """S3: assert_meter_config rejects a fabricated/deleted id."""
    h.phase(
        "S3_STALE_METER_ID",
        "assert_meter_config rejects nonexistent meter_id with clear message",
    )

    fake_id = "mtr_DELETED_BY_TEST_DOES_NOT_EXIST"
    raised = False
    try:
        assert_meter_config(fake_id)
    except ValueError as exc:
        raised = True
        h.log.info(f"  ✅ Rejected with: {exc}")
        assert "not found" in str(exc), (
            f"S3: rejection message should say 'not found'; got {exc}"
        )

    assert raised, f"S3: assert_meter_config({fake_id!r}) did not raise"

    # Verify recovery: ensure_stripe_meter still works after the bad lookup
    real_id = ensure_stripe_meter(event_name=METER_EVENT_NAME_WEDDING_ACTIVE)
    assert real_id and real_id != fake_id, (
        f"S3: ensure_stripe_meter recovery returned bad id {real_id!r}"
    )
    h.log.info(f"  ✅ Recovery via ensure_stripe_meter: {real_id}")


def phase_s4_half_configured_rejection(h: Harness) -> None:
    """S4: sync_plan_to_stripe rejects is_metered=True with no meter_event_name."""
    h.phase(
        "S4_HALF_CONFIGURED",
        "sync_plan_to_stripe rejects half-configured metered plan",
    )

    from fastapi.exceptions import HTTPException

    from app.services.stripe_service import stripe_service

    bad_plan = {
        "_id": "plan_test_half_config_DO_NOT_PERSIST",
        "name": "Test Half Config",
        "description": "Should never be created",
        "price_monthly": 99,
        "price_yearly": 990,
        "is_metered": True,
        "meter_event_name": None,
    }

    raised = False
    try:
        stripe_service.sync_plan_to_stripe(bad_plan)
    except HTTPException as exc:
        raised = True
        h.log.info(f"  ✅ Rejected with HTTP {exc.status_code}: {exc.detail}")
        assert exc.status_code == 400
        # Either error message is acceptable — the point is fail-fast
        msg = str(exc.detail).lower()
        assert "meter_id" in msg or "meter_event_name" in msg, (
            f"S4: rejection message should mention meter fields; got {exc.detail}"
        )

    assert raised, "S4: expected HTTPException for half-configured plan"


def phase_s5_wrong_aggregation_blocked(h: Harness) -> None:
    """S5: assert_meter_config rejects a meter created with formula=count."""
    h.phase(
        "S5_WRONG_AGGREGATION",
        "Hostile meter (formula=count) rejected at preflight",
    )

    hostile_event = "wedding_active_HOSTILE_TEST"
    hostile_id: Optional[str] = None
    try:
        # Best-effort cleanup of any prior hostile meter
        for m in _list_meters_for_event(hostile_event):
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
        assert "must be 'sum'" in str(exc), f"S5: unexpected reason: {exc}"

    assert raised, "S5: assert_meter_config accepted a count-aggregation meter"

    # Cleanup
    try:
        stripe.billing.Meter.deactivate(hostile_id)
        h.log.info("  ✅ Hostile meter deactivated")
    except stripe.error.StripeError:
        pass


def phase_s6_flat_to_metered_migration(h: Harness) -> None:
    """S6: sync_plan_to_stripe deactivates old flat price, creates metered."""
    h.phase(
        "S6_FLAT_TO_METERED",
        "sync_plan_to_stripe migrates flat price → metered price",
    )

    from app.services.stripe_service import stripe_service

    # Read the live Signature plan from Mongo (it's the seed-default flat)
    plan = _read_plan(h, TARGET_PLAN_ID)
    assert plan, f"S6: target plan {TARGET_PLAN_ID!r} not found in Mongo"
    flat_monthly = plan.get("stripe_price_id_monthly")
    h.log.info(f"  Current Signature monthly price: {flat_monthly}")

    # Get a real meter_id (provisioned in S1 or now)
    meter_id = ensure_stripe_meter(event_name=METER_EVENT_NAME_WEDDING_ACTIVE)

    # Build a hypothetical metered version of the plan dict and call
    # sync_plan_to_stripe directly. We do NOT persist this to Mongo —
    # that would be a real production change. We just want to verify
    # the helper does the right thing on the Stripe side.
    metered_plan = {
        **plan,
        "is_metered": True,
        "meter_event_name": METER_EVENT_NAME_WEDDING_ACTIVE,
        "meter_id": meter_id,
    }

    h.log.info("  Calling stripe_service.sync_plan_to_stripe with metered config…")
    try:
        result = stripe_service.sync_plan_to_stripe(metered_plan)
    except Exception as exc:
        raise AssertionError(f"S6: sync_plan_to_stripe failed: {exc}")

    new_monthly = result.get("stripe_price_id_monthly")
    h.log.info(f"  New monthly price returned: {new_monthly}")
    assert new_monthly and new_monthly != flat_monthly, (
        f"S6: new monthly price ID didn't change. "
        f"flat={flat_monthly}, new={new_monthly}"
    )

    # Verify the new Price has metered config
    new_price = stripe.Price.retrieve(new_monthly)
    assert new_price.recurring.usage_type == "metered", (
        f"S6: new Price {new_monthly} usage_type={new_price.recurring.usage_type}"
    )
    assert getattr(new_price.recurring, "meter", None) == meter_id, (
        f"S6: new Price meter doesn't match: {new_price.recurring}"
    )
    h.log.info(f"  ✅ New monthly Price is metered, references {meter_id}")

    # Verify old flat Price is deactivated
    old_price = stripe.Price.retrieve(flat_monthly)
    assert not old_price.active, (
        f"S6: old flat Price {flat_monthly} is still active. "
        f"Existing customers on it would still bill flat."
    )
    h.log.info(f"  ✅ Old flat Price {flat_monthly} is now inactive")

    h.checkpoint(
        "S6_MIGRATION_DONE",
        expectations=[
            "New metered Price would be the active billing target for new checkouts",
            "Old flat Price is inactive",
            "**CAVEAT (SS2):** existing Stripe Subscriptions still reference "
            "the old Price. They will keep billing flat until manually swapped "
            "via stripe.Subscription.modify. This is the open product question "
            "in METERING_GAP_SCENARIOS_2026-05-04.md §SS2.",
            "**Mongo NOT updated**: this phase exercised the Stripe side only. "
            "The plan_signature doc in your dev DB still shows is_metered=False. "
            "To actually flip the plan in production, edit "
            "scripts/seed_subscription_plans.py and redeploy.",
        ],
    )


# =============================================================================
# Entry point
# =============================================================================


PHASE_MAP = {
    "S1": phase_s1_fresh_meter_provisioning,
    "S2": phase_s2_idempotent_reprovisioning,
    "S3": phase_s3_stale_meter_id_rejection,
    "S4": phase_s4_half_configured_rejection,
    "S5": phase_s5_wrong_aggregation_blocked,
    "S6": phase_s6_flat_to_metered_migration,
}


def main() -> int:
    h = Harness(driver_name=DRIVER_NAME)
    h.banner("VERIFY — Metered Seed E2E (helpers-direct, NOT via seed subprocess)")
    h.preflight()

    selected = _selected_phases()
    h.log.info(f"  Phases: {selected}")
    h.log.info(
        "  Design note: this driver tests the HELPERS directly. The seed script "
        "is intentionally hardcoded source-of-truth for plan config and ignores "
        "Mongo overrides — see METERING_IMPLEMENTATION_2026-05-04.md S1-fix lesson."
    )

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
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"\n❌ Driver aborted: {exc}\n")
        raise SystemExit(1)
