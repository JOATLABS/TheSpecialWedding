#!/usr/bin/env python3
"""Clean up state from verify_planner_couple_contract_flow.py.

Removes — using harness primitives where they exist so the cleanup
arc is consistent with the other testbed cleanups:

  - the planner's contract rows + scheduled_payments rows
  - the planner's package(s) seeded by the verifier
  - couple-portal invite rows tied to the planner's wedding
  - the couple's Stripe Customer object(s) (one per signed contract)
  - the planner's Stripe Connect Express account (via harness)
  - the planner's user / user_subscriptions / stripe_customers /
    team_members / usage_tracking / weddings rows
    (via harness.delete_user_chain — also handles
    `assigned_planner_email` orphans)
  - the planner user itself

Safe to re-run.

Usage:
    python testbed/cleanup_planner_couple_contract_flow_state.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import stripe

from testbed.harness import Harness

# ---------------------------------------------------------------------------
# Driver constants — mirror the verifier so cleanup matches what was seeded
# ---------------------------------------------------------------------------

PLANNER_EMAIL = "test_planner+contractflow@thespecialwedding.io"
COUPLE_EMAIL = "test_couple+contractflow@thespecialwedding.io"
PACKAGE_NAME_PREFIX = "Test Wedding Package — Contract Flow Verifier"


def cleanup(h: Harness) -> None:
    user = h.mongo["users"].find_one({"email": PLANNER_EMAIL})
    if not user:
        h.log.info("  (no planner user — nothing to clean)")
        return

    user_id = str(user["_id"])
    h.log.info(f"Cleaning state for planner {PLANNER_EMAIL} (user_id={user_id})…")

    # 1. Stripe Connect Express account (via harness — swallows
    #    already-deleted errors).
    if user.get("stripe_connect_id"):
        h.delete_connect_account(user["stripe_connect_id"])

    # 2. Contracts produced by send_to_couple, plus their scheduled_payments
    #    rows and the couple's Stripe Customer objects.
    contracts = list(
        h.mongo["contracts"].find({"planner_id": user_id, "couple.email": COUPLE_EMAIL})
    )
    for contract in contracts:
        contract_id_str = str(contract["_id"])
        sp = h.mongo["scheduled_payments"].delete_many({"contract_id": contract_id_str})
        if sp.deleted_count:
            h.log.info(
                f"  ✅ scheduled_payments: removed {sp.deleted_count} for "
                f"contract {contract_id_str}"
            )
        couple_customer_id = contract.get("stripe_customer_id")
        if couple_customer_id:
            try:
                stripe.Customer.delete(couple_customer_id)
                h.log.info(f"  ✅ Deleted couple Stripe customer {couple_customer_id}")
            except stripe.error.StripeError as exc:
                h.log.warning(
                    f"  ⚠️ Could not delete couple Stripe customer "
                    f"{couple_customer_id}: {exc}"
                )
    if contracts:
        result = h.mongo["contracts"].delete_many(
            {"planner_id": user_id, "couple.email": COUPLE_EMAIL}
        )
        if result.deleted_count:
            h.log.info(f"  ✅ contracts: removed {result.deleted_count}")

    # 3. Packages seeded by the verifier — match by planner_id + name prefix
    #    so we don't drop unrelated packages the planner may have.
    pkg_result = h.mongo["packages"].delete_many(
        {
            "planner_id": user_id,
            "name": {"$regex": f"^{PACKAGE_NAME_PREFIX}"},
        }
    )
    if pkg_result.deleted_count:
        h.log.info(f"  ✅ packages: removed {pkg_result.deleted_count}")

    # 4. Couple-portal invite rows tied to the planner — both via the
    #    `couples` (or equivalent) collection and team_members-style rows.
    #    The harness's delete_user_chain handles team_members (incoming +
    #    outgoing) further down. Here we just clear the couple-portal
    #    invite by email so a re-run can re-invite.
    for coll in ("couples", "couple_portal_invites"):
        try:
            r = h.mongo[coll].delete_many(
                {
                    "$or": [
                        {"email": COUPLE_EMAIL.lower()},
                        {"email": COUPLE_EMAIL},
                        {"planner_id": user_id, "couple_email": COUPLE_EMAIL},
                    ]
                }
            )
            if r.deleted_count:
                h.log.info(f"  ✅ {coll}: removed {r.deleted_count}")
        except Exception:
            # Collection may not exist in this env — that's fine; the
            # invite mechanism varies by deploy.
            pass

    # 5. Hand the rest off to the harness's standard cleanup arc:
    #    user_subscriptions / stripe_customers / team_members /
    #    usage_tracking / weddings (by assigned_planner_email + by
    #    planner_id) / users itself. delete_user_chain logs each
    #    affected collection so the operator sees what was removed.
    h.delete_user_chain(PLANNER_EMAIL)


def main() -> int:
    h = Harness(driver_name="cleanup_planner_couple_contract_flow")
    h.log.info("Starting cleanup of planner-couple contract flow verification state…")
    h.log.info(f"  Mongo DB: {h.config.mongo_db}")
    h.log.info(f"  Planner:  {PLANNER_EMAIL}")
    h.log.info(f"  Couple:   {COUPLE_EMAIL}")
    h.log.info("")
    cleanup(h)
    h.log.info("")
    h.log.info("Cleanup complete. SEED phase can run from a blank slate.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        # Reuse module-level logger; harness has logging configured by now.
        import logging

        logging.getLogger("cleanup_contract_flow").error(
            f"Cleanup aborted: {exc}", exc_info=True
        )
        raise SystemExit(1)
