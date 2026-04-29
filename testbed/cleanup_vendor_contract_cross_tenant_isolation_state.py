#!/usr/bin/env python3
"""Clean up state from verify_vendor_contract_cross_tenant_isolation.py.

Removes — using harness primitives where they exist so the cleanup arc
matches the other testbed cleanups:

  - vendor_contracts rows tied to either planner
  - vendor_contract_activities for those contracts
  - vendor_assignments rows tied to either planner
  - vendor_profiles rows seeded by the verifier (matched by name + email)
  - the planner users themselves via harness.delete_user_chain (handles
    user_subscriptions / stripe_customers / weddings / team_members /
    usage_tracking / packages)

Direct Mongo deletes are used here for cleanup parity with the other
testbed cleanups. The verifier's PRODUCT-state changes go through
endpoints; this script is the after-test scrub.

Safe to re-run.

Usage:
    python testbed/cleanup_vendor_contract_cross_tenant_isolation_state.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


from testbed.harness import Harness

# ---------------------------------------------------------------------------
# Driver constants — mirror the verifier so cleanup matches what was seeded
# ---------------------------------------------------------------------------

PLANNER_A_EMAIL = "test_planner+xtenant_a@thespecialwedding.io"
PLANNER_B_EMAIL = "test_planner+xtenant_b@thespecialwedding.io"

VENDOR_A_BUSINESS_NAME = "Vendor A Co — XTenant Verifier"
VENDOR_A_EMAIL = "vendor+xtenant_a@thespecialwedding.io"
VENDOR_B_BUSINESS_NAME = "Vendor B Co — XTenant Verifier"
VENDOR_B_EMAIL = "vendor+xtenant_b@thespecialwedding.io"


def _cleanup_planner(h: Harness, planner_email: str) -> None:
    user = h.mongo["users"].find_one({"email": planner_email})
    if not user:
        h.log.info(f"  (no user for {planner_email} — skipping)")
        return

    h.log.info(f"Cleaning state for planner {planner_email}…")

    contract_filter = {"created_by": planner_email}
    contract_ids = [
        str(c["_id"])
        for c in h.mongo["vendor_contracts"].find(contract_filter, {"_id": 1})
    ]

    if contract_ids:
        ms = h.mongo["vendor_payment_milestones"].delete_many(
            {"contract_id": {"$in": contract_ids}}
        )
        if ms.deleted_count:
            h.log.info(f"  ✅ vendor_payment_milestones: removed {ms.deleted_count}")

        ca = h.mongo["vendor_contract_activities"].delete_many(
            {"contract_id": {"$in": contract_ids}}
        )
        if ca.deleted_count:
            h.log.info(f"  ✅ vendor_contract_activities: removed {ca.deleted_count}")

        cr = h.mongo["vendor_contracts"].delete_many(contract_filter)
        if cr.deleted_count:
            h.log.info(f"  ✅ vendor_contracts: removed {cr.deleted_count}")

    asn = h.mongo["vendor_assignments"].delete_many({"created_by": planner_email})
    if asn.deleted_count:
        h.log.info(f"  ✅ vendor_assignments: removed {asn.deleted_count}")

    # Hand the rest off to harness's standard cleanup arc
    # (user / user_subscriptions / stripe_customers / weddings / team_members
    # / usage_tracking / packages).
    h.delete_user_chain(planner_email)


def _cleanup_vendor_profiles(h: Harness) -> None:
    vp = h.mongo["vendor_profiles"].delete_many(
        {
            "$or": [
                {"business_name": VENDOR_A_BUSINESS_NAME},
                {"business_name": VENDOR_B_BUSINESS_NAME},
                {"email": VENDOR_A_EMAIL},
                {"email": VENDOR_B_EMAIL},
            ]
        }
    )
    if vp.deleted_count:
        h.log.info(f"  ✅ vendor_profiles: removed {vp.deleted_count}")


def main() -> int:
    h = Harness(driver_name="cleanup_vendor_contract_cross_tenant_isolation")
    h.log.info("Starting cleanup of vendor cross-tenant isolation state…")
    h.log.info(f"  Mongo DB: {h.config.mongo_db}")
    h.log.info(f"  Planner A: {PLANNER_A_EMAIL}")
    h.log.info(f"  Planner B: {PLANNER_B_EMAIL}")
    h.log.info(f"  Vendors:   {VENDOR_A_BUSINESS_NAME!r}, {VENDOR_B_BUSINESS_NAME!r}")
    h.log.info("")
    _cleanup_planner(h, PLANNER_A_EMAIL)
    _cleanup_planner(h, PLANNER_B_EMAIL)
    _cleanup_vendor_profiles(h)
    h.log.info("")
    h.log.info("Cleanup complete. SEED phase can run from a blank slate.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        import logging

        logging.getLogger("cleanup_vendor_contract_cross_tenant_isolation").error(
            f"Cleanup aborted: {exc}", exc_info=True
        )
        raise SystemExit(1)
