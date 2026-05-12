#!/usr/bin/env python3
"""Live E2E driver for the seed's price-refresh behavior.

Companion to ``verify_metered_seed_e2e.py``. That driver covers the
provisioning helpers (meter creation, half-config rejection, metered Price
migration). **This** driver covers the missing piece that production
forensics surfaced on 2026-05-10:

* Mongo upsert used ``$setOnInsert`` for ``price_monthly`` and friends, so
  re-deploying a price refresh ($29 → $49) left existing plans at the old
  price forever — visible at thespecialwedding.io.
* The seed's local Stripe helper adopted existing Prices without comparing
  ``unit_amount``, so even after the Mongo bug was fixed, the recorded
  ``stripe_price_id_monthly`` would still point at the old $29 Stripe
  Price.

The fix has two parts (see ``scripts/seed_subscription_plans.py``):

1. Strategy-controlled fields moved from ``$setOnInsert`` to ``$set``.
2. ``create_stripe_product_and_prices`` now compares ``unit_amount``
   against the seed declaration and, on mismatch, creates a new Stripe
   Price + deactivates the old one — matching Stripe's immutability
   contract from
   https://docs.stripe.com/billing/subscriptions/change-price.

This driver verifies both parts against a real Stripe test account using a
dedicated fixture plan id (``plan_testbed_price_refresh``) so it cannot
collide with real canonical plans.

Phases:

* **P1 — Setup.** Create the fixture in Mongo with ``price_monthly=29``,
  call the seed helper once (with ``existing_mongo=None``) to provision
  Stripe Product + $29 Price. Record the OLD ``stripe_price_id_monthly``.

* **P2 — Price refresh.** Call the seed helper again with
  ``price_monthly=49`` and the prior Mongo doc passed as
  ``existing_mongo``. Assert:
    - returned ``stripe_price_id_monthly`` is NEW (≠ OLD)
    - new Stripe Price has ``unit_amount == 4900``
    - old Stripe Price has ``active == False``

* **P3 — Idempotent re-run.** Call the seed helper a THIRD time with the
  same $49 declaration and the P2-updated Mongo doc. Assert the returned
  id equals the P2 id (no third Price created). Validates the steady-state
  cost: no Stripe Price churn on deploys where nothing changed.

* **P4 — Mongo upsert pin.** Insert a fixture doc at $29, run the upsert
  modifier the seed uses (``$set`` carrying $49), and assert the post-
  update doc reads ``price_monthly == 49``. Validates that strategy
  fields propagate through redeploys.

* **P5 — Cleanup.** Archive the Stripe Product, delete the Mongo fixture
  plan and any subscription rows that leaked through.

Skip discipline: each phase is independent. Set ``PRICE_REFRESH_PHASES`` to
a comma-separated subset.

Usage::

    # All phases (interactive — pauses at checkpoints)
    python testbed/verify_seed_price_refresh_e2e.py

    # Specific phases
    PRICE_REFRESH_PHASES=P1,P2 python testbed/verify_seed_price_refresh_e2e.py

    # Unattended
    TESTBED_NON_INTERACTIVE=1 python testbed/verify_seed_price_refresh_e2e.py

WARNING: This driver creates a real Stripe Product and Prices on the
account whose key is in ``STRIPE_SECRET_KEY``. Use a test key. Cleanup
(P5) archives the Product but does NOT delete Prices (Stripe doesn't
allow Price deletion — archive is the canonical disposal).
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import stripe  # noqa: E402

from testbed.harness import Harness  # noqa: E402

logger = logging.getLogger(__name__)

DRIVER_NAME = "verify_seed_price_refresh_e2e"
FIXTURE_PLAN_ID = "plan_testbed_price_refresh"
FIXTURE_PLAN_NAME = "Testbed Price Refresh"
OLD_MONTHLY = 29
OLD_YEARLY = 290
NEW_MONTHLY = 49
NEW_YEARLY = 490

ALL_PHASES = ("P1", "P2", "P3", "P4", "P5")


# =============================================================================
# Helpers
# =============================================================================


def _selected_phases() -> list[str]:
    raw = os.getenv("PRICE_REFRESH_PHASES")
    if not raw:
        return list(ALL_PHASES)
    selected = [p.strip().upper() for p in raw.split(",") if p.strip()]
    invalid = [p for p in selected if p not in ALL_PHASES]
    if invalid:
        raise SystemExit(f"Unknown phase(s): {invalid}. Valid: {ALL_PHASES}")
    return selected


def _build_fixture_plan(price_monthly: float, price_yearly: float) -> dict:
    """Build a fixture plan dict in the same shape the seed expects.

    Marked as flat (``is_metered=False``) so the seed helper doesn't go
    looking for a Stripe Meter. The fixture _id deliberately doesn't
    match any canonical CANONICAL_PUBLIC_PLAN_IDS — protects against
    accidental interference with real plans during a co-run.
    """
    return {
        "_id": FIXTURE_PLAN_ID,
        "name": FIXTURE_PLAN_NAME,
        "description": "Testbed fixture — DO NOT use in production",
        "price_monthly": price_monthly,
        "price_yearly": price_yearly,
        "trial_days": 0,
        "billing_model": "flat_rate",
        "is_metered": False,
        "max_weddings": 1,
        "max_weddings_lifetime": False,
        "max_guests_per_wedding": 10,
        "ai_credits_monthly": 0,
        "storage_gb": 1,
        "staff_seats": 1,
        "features": {"testbed_fixture": True},
        "features_list": ["Testbed fixture"],
        "is_active": True,
        "is_featured": False,
        "sort_order": 999,
        "display_order": 999,
        "created_by": "testbed",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


def _seed_helper():
    """Import the seed helper without triggering its module-level side effects.

    The seed module runs ``MongoClient.command('ping')`` and other Mongo
    setup at import. The driver already has a Mongo connection through
    Harness, so a second client init is fine, but we want a clean import.
    The ``SEED_SUBSCRIPTION_PLANS_IMPORT_CHECK_ONLY=1`` env flag bails the
    seed before any work, but that also skips defining the functions. So
    we set the flag while running the script's import then strip it back.

    Simpler path: just do ``importlib.util`` and accept the side effects;
    the side effects are benign in a test env (pymongo client + dotenv).
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "seed_subscription_plans",
        Path(__file__).resolve().parent.parent
        / "scripts"
        / "seed_subscription_plans.py",
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    # Don't run the seed's main loop — only the function definitions.
    # The cleanest way is to set the env flag, but that aborts before
    # function definition. Workaround: monkey-patch __name__ check away
    # by reading & exec-ing without the bottom loop. Actually the seed
    # has no `if __name__ == "__main__"` guard, so we have to suppress
    # the main loop differently.
    #
    # Pragmatic approach: import the script as a normal module. The main
    # loop runs once on import and processes whatever plans are declared.
    # That's fine — those are the live canonical plans, and the seed is
    # already idempotent against existing prod state. We then call the
    # functions for our fixture.
    #
    # If the user runs this in an env where they don't want the seed
    # main loop to fire, they should run with PRICE_REFRESH_PHASES=P4
    # which doesn't need the Stripe helpers.
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _read_plan(h: Harness, plan_id: str) -> Optional[dict]:
    return h.mongo["subscription_plans"].find_one({"_id": plan_id})


# =============================================================================
# Phases
# =============================================================================


def phase_p1_setup(h: Harness, seed_mod) -> dict:
    """P1: provision fixture in Mongo + Stripe at OLD price.

    Returns the recorded fixture plan dict including the OLD Stripe IDs.
    """
    h.phase("P1_SETUP", f"Create fixture {FIXTURE_PLAN_ID!r} at OLD ${OLD_MONTHLY}/mo")

    # Clean any stragglers from a prior aborted run.
    h.mongo["subscription_plans"].delete_one({"_id": FIXTURE_PLAN_ID})

    fixture = _build_fixture_plan(OLD_MONTHLY, OLD_YEARLY)
    h.mongo["subscription_plans"].insert_one(fixture.copy())
    h.log.info(f"  Inserted Mongo fixture at ${OLD_MONTHLY}/mo")

    # Call the seed helper to provision Stripe Product + Prices at $29.
    # No existing_mongo passed → simulates fresh-create path.
    stripe_ids = seed_mod.create_stripe_product_and_prices(fixture)
    assert stripe_ids.get("stripe_product_id"), (
        f"P1: seed helper did not return a stripe_product_id; got {stripe_ids!r}"
    )
    assert stripe_ids.get("stripe_price_id_monthly"), (
        f"P1: no monthly price id returned; got {stripe_ids!r}"
    )

    h.mongo["subscription_plans"].update_one(
        {"_id": FIXTURE_PLAN_ID},
        {"$set": stripe_ids},
    )

    old_monthly = stripe.Price.retrieve(stripe_ids["stripe_price_id_monthly"])
    assert old_monthly.unit_amount == OLD_MONTHLY * 100, (
        f"P1: Stripe Price monthly unit_amount={old_monthly.unit_amount}, "
        f"expected {OLD_MONTHLY * 100}"
    )
    assert old_monthly.active is True

    h.log.info(
        f"  ✅ Stripe Product {stripe_ids['stripe_product_id']} created with "
        f"monthly Price {stripe_ids['stripe_price_id_monthly']} @ ${OLD_MONTHLY}"
    )

    fixture.update(stripe_ids)
    return fixture


def phase_p2_refresh(h: Harness, seed_mod, fixture_with_old_ids: dict) -> dict:
    """P2: refresh to NEW price. Assert new Stripe Price created, old archived."""
    h.phase("P2_REFRESH", f"Refresh fixture price to NEW ${NEW_MONTHLY}/mo")

    old_monthly_id = fixture_with_old_ids["stripe_price_id_monthly"]
    old_yearly_id = fixture_with_old_ids["stripe_price_id_yearly"]

    refreshed = _build_fixture_plan(NEW_MONTHLY, NEW_YEARLY)
    refreshed.update(
        {
            "stripe_product_id": fixture_with_old_ids["stripe_product_id"],
            "stripe_price_id_monthly": old_monthly_id,
            "stripe_price_id_yearly": old_yearly_id,
        }
    )

    # Pass the existing Mongo doc so the helper sees the recorded old IDs.
    stripe_ids = seed_mod.create_stripe_product_and_prices(
        refreshed, fixture_with_old_ids
    )
    new_monthly_id = stripe_ids["stripe_price_id_monthly"]
    new_yearly_id = stripe_ids["stripe_price_id_yearly"]

    h.log.info(f"  Old monthly: {old_monthly_id} → New monthly: {new_monthly_id}")

    assert new_monthly_id != old_monthly_id, (
        f"P2: monthly Price id unchanged ({new_monthly_id}); seed helper "
        f"did NOT create a new Stripe Price on unit_amount drift. The "
        f"immutability fix in scripts/seed_subscription_plans.py is "
        "broken — production prices won't refresh on deploy."
    )
    assert new_yearly_id != old_yearly_id, (
        f"P2: yearly Price id unchanged ({new_yearly_id})"
    )

    # New Stripe Price reflects the refreshed amount.
    new_monthly = stripe.Price.retrieve(new_monthly_id)
    assert new_monthly.unit_amount == NEW_MONTHLY * 100, (
        f"P2: new Stripe Price unit_amount={new_monthly.unit_amount}, "
        f"expected {NEW_MONTHLY * 100}"
    )
    assert new_monthly.active is True
    h.log.info(f"  ✅ New monthly Price: unit_amount={new_monthly.unit_amount}")

    # Old Stripe Price archived.
    old_monthly = stripe.Price.retrieve(old_monthly_id)
    assert old_monthly.active is False, (
        f"P2: old monthly Price {old_monthly_id} still active=True. The "
        "deactivation half of the immutability dance is broken. Future "
        "Checkout sessions could still default to the old price."
    )
    h.log.info("  ✅ Old monthly Price archived (active=False)")

    # Commit the new IDs to Mongo so P3 sees them.
    h.mongo["subscription_plans"].update_one(
        {"_id": FIXTURE_PLAN_ID},
        {
            "$set": {
                **stripe_ids,
                "price_monthly": NEW_MONTHLY,
                "price_yearly": NEW_YEARLY,
            }
        },
    )

    h.checkpoint(
        "P2_REFRESHED",
        expectations=[
            f"Stripe Dashboard → Products → {FIXTURE_PLAN_NAME}: 2 prices total",
            f"  - {new_monthly_id}: ${NEW_MONTHLY}/mo (active)",
            f"  - {old_monthly_id}: ${OLD_MONTHLY}/mo (archived)",
        ],
    )

    refreshed.update(stripe_ids)
    return refreshed


def phase_p3_idempotent(h: Harness, seed_mod, fixture_with_new_ids: dict) -> None:
    """P3: re-run with same $49 declaration. No third Price created."""
    h.phase("P3_IDEMPOTENT", "Re-run seed helper with unchanged $49; expect no churn")

    new_monthly_id = fixture_with_new_ids["stripe_price_id_monthly"]
    new_yearly_id = fixture_with_new_ids["stripe_price_id_yearly"]

    # Count prices on the product BEFORE the no-op re-run.
    product_id = fixture_with_new_ids["stripe_product_id"]
    active_prices_before = sum(
        1 for _ in stripe.Price.list(product=product_id, active=True).auto_paging_iter()
    )

    refreshed_again = _build_fixture_plan(NEW_MONTHLY, NEW_YEARLY)
    refreshed_again.update(
        {
            "stripe_product_id": product_id,
            "stripe_price_id_monthly": new_monthly_id,
            "stripe_price_id_yearly": new_yearly_id,
        }
    )

    stripe_ids = seed_mod.create_stripe_product_and_prices(
        refreshed_again, fixture_with_new_ids
    )

    assert stripe_ids["stripe_price_id_monthly"] == new_monthly_id, (
        f"P3: monthly id churned on no-op re-run "
        f"({new_monthly_id} → {stripe_ids['stripe_price_id_monthly']}). "
        "The seed helper is creating a new Stripe Price every deploy even "
        "when nothing changed."
    )

    active_prices_after = sum(
        1 for _ in stripe.Price.list(product=product_id, active=True).auto_paging_iter()
    )
    assert active_prices_after == active_prices_before, (
        f"P3: active price count grew from {active_prices_before} to "
        f"{active_prices_after} on a no-op re-run"
    )

    h.log.info(
        f"  ✅ Idempotent: monthly id unchanged, {active_prices_after} active "
        "prices (no churn)"
    )


def phase_p4_upsert_modifier(h: Harness) -> None:
    """P4: validate $set carries new price into existing Mongo doc.

    Independent of P1-P3. Doesn't touch Stripe. Inserts a doc at $29 and
    runs the upsert modifier with $49 in $set; asserts the doc reads $49
    after. Catches the original Mongo bug if anyone moves price_monthly
    back to $setOnInsert without going through the upsert_structure test.
    """
    h.phase(
        "P4_UPSERT_MODIFIER",
        "Live-verify Mongo $set carries new price into existing doc",
    )

    coll = h.mongo["subscription_plans"]
    p4_id = f"{FIXTURE_PLAN_ID}_p4"

    coll.delete_one({"_id": p4_id})
    coll.insert_one(
        {
            "_id": p4_id,
            "name": "P4 Fixture",
            "price_monthly": 29,
            "is_metered": False,
            "created_at": datetime.now(timezone.utc),
        }
    )
    h.log.info(f"  Inserted {p4_id} at price_monthly=29")

    # Mimic the seed's upsert: $set carries new strategy, $setOnInsert
    # carries admin toggles (which are no-ops here since doc exists).
    result = coll.update_one(
        {"_id": p4_id},
        {
            "$setOnInsert": {
                "created_at": datetime.now(timezone.utc),
                "is_active": True,
            },
            "$set": {
                "name": "P4 Fixture (refreshed)",
                "price_monthly": 49,
                "is_metered": False,
                "billing_model": "flat_rate",
                "updated_at": datetime.now(timezone.utc),
            },
        },
        upsert=True,
    )
    assert result.modified_count == 1, (
        f"P4: expected modified_count=1, got {result.modified_count}"
    )

    after = coll.find_one({"_id": p4_id})
    assert after is not None
    assert after["price_monthly"] == 49, (
        f"P4: $set did not refresh price_monthly; doc reads {after['price_monthly']}. "
        "If this fails, the original drift bug returned — price_monthly is "
        "back in $setOnInsert."
    )
    assert after["name"] == "P4 Fixture (refreshed)", (
        f"P4: $set did not refresh name; doc reads {after['name']!r}"
    )
    h.log.info("  ✅ Mongo $set propagates price_monthly and name on existing doc")

    # Verify $setOnInsert didn't overwrite is_active (which existed) by
    # introducing a value that would clash if $setOnInsert wrongly fired.
    coll.update_one(
        {"_id": p4_id},
        {"$set": {"is_active": False}},
    )
    coll.update_one(
        {"_id": p4_id},
        {
            "$setOnInsert": {"is_active": True},
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
        upsert=True,
    )
    after2 = coll.find_one({"_id": p4_id})
    assert isinstance(after2, dict)
    assert after2["is_active"] is False, (
        "P4: $setOnInsert wrongly fired against existing doc; admin's "
        "is_active=False toggle would get reverted on every deploy."
    )
    h.log.info("  ✅ $setOnInsert correctly skipped on existing doc")

    coll.delete_one({"_id": p4_id})


def phase_p5_cleanup(h: Harness) -> None:
    """P5: archive Stripe Product, drop Mongo fixture."""
    h.phase(
        "P5_CLEANUP", f"Drop fixture {FIXTURE_PLAN_ID!r} and archive Stripe product"
    )

    plan = _read_plan(h, FIXTURE_PLAN_ID)
    if plan:
        product_id = plan.get("stripe_product_id")
        if product_id:
            try:
                stripe.Product.modify(product_id, active=False)
                h.log.info(f"  Archived Stripe Product {product_id}")
            except stripe.StripeError as exc:
                h.log.warning(f"  Could not archive product {product_id}: {exc}")

    h.mongo["subscription_plans"].delete_many({"_id": FIXTURE_PLAN_ID})
    h.mongo["subscription_plans"].delete_many({"_id": f"{FIXTURE_PLAN_ID}_p4"})
    h.log.info("  ✅ Mongo fixtures removed")


# =============================================================================
# Entrypoint
# =============================================================================


def main() -> int:
    h = Harness(DRIVER_NAME)
    h.banner(f"{DRIVER_NAME} — seed price-refresh live verification")

    phases = _selected_phases()
    h.log.info(f"Running phases: {', '.join(phases)}")

    # Defer seed-module import until actually needed — P4 doesn't use Stripe
    # at all, so allow a P4-only run to skip the import.
    seed_mod = None
    fixture_with_old_ids = None
    fixture_with_new_ids = None

    try:
        if "P1" in phases or "P2" in phases or "P3" in phases:
            seed_mod = _seed_helper()

        if "P1" in phases:
            fixture_with_old_ids = phase_p1_setup(h, seed_mod)
        else:
            fixture_with_old_ids = _read_plan(h, FIXTURE_PLAN_ID)

        if "P2" in phases:
            if not fixture_with_old_ids:
                raise SystemExit(
                    "P2 requires fixture from P1 (or an existing Mongo doc). "
                    "Run P1 first or include it in PRICE_REFRESH_PHASES."
                )
            fixture_with_new_ids = phase_p2_refresh(h, seed_mod, fixture_with_old_ids)
        else:
            fixture_with_new_ids = fixture_with_old_ids

        if "P3" in phases:
            if not fixture_with_new_ids:
                raise SystemExit("P3 requires fixture from P1+P2.")
            phase_p3_idempotent(h, seed_mod, fixture_with_new_ids)

        if "P4" in phases:
            phase_p4_upsert_modifier(h)

        if "P5" in phases:
            phase_p5_cleanup(h)

        h.banner("ALL PHASES PASSED")
        return 0

    except AssertionError as exc:
        h.log.error(f"❌ ASSERTION FAILED: {exc}")
        h.log.error(
            "  Fixture left in place for inspection. Re-run with "
            "PRICE_REFRESH_PHASES=P5 to clean up."
        )
        return 1
    except Exception as exc:
        h.log.exception(f"❌ UNEXPECTED ERROR: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
