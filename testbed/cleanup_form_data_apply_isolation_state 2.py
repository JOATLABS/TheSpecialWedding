#!/usr/bin/env python3
"""Clean up state from verify_form_data_apply_isolation.py.

Removes — using harness primitives where they exist so the cleanup arc
matches the other testbed cleanups:

  - vendor_forms + vendor_submissions tied to either planner
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
    python testbed/cleanup_form_data_apply_isolation_state.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


from testbed.harness import Harness

# ---------------------------------------------------------------------------
# Driver constants — mirror the verifier so cleanup matches what was seeded
# ---------------------------------------------------------------------------

PLANNER_A_EMAIL = "test_planner+formapply_a@thespecialwedding.io"
PLANNER_B_EMAIL = "test_planner+formapply_b@thespecialwedding.io"

VENDOR_A_BUSINESS_NAME = "Vendor A Co — FormApply Verifier"
VENDOR_A_EMAIL = "vendor+formapply_a@thespecialwedding.io"
VENDOR_B_BUSINESS_NAME = "Vendor B Co — FormApply Verifier"
VENDOR_B_EMAIL = "vendor+formapply_b@thespecialwedding.io"


def _cleanup_planner(h: Harness, planner_email: str) -> None:
    user = h.mongo["users"].find_one({"email": planner_email})
    if not user:
        h.log.info(f"  (no user for {planner_email} — skipping)")
        return

    h.log.info(f"Cleaning state for planner {planner_email}…")

    # vendor_forms are owned via created_by == planner_email; submissions
    # join through form_id.
    form_ids = [
        str(f["_id"])
        for f in h.mongo["vendor_forms"].find({"created_by": planner_email}, {"_id": 1})
    ]
    if form_ids:
        sub = h.mongo["vendor_submissions"].delete_many({"form_id": {"$in": form_ids}})
        if sub.deleted_count:
            h.log.info(f"  ✅ vendor_submissions: removed {sub.deleted_count}")
        vf = h.mongo["vendor_forms"].delete_many({"created_by": planner_email})
        if vf.deleted_count:
            h.log.info(f"  ✅ vendor_forms: removed {vf.deleted_count}")

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
    h = Harness(driver_name="cleanup_form_data_apply_isolation")
    h.log.info("Starting cleanup of form-data apply isolation state…")
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

        logging.getLogger("cleanup_form_data_apply_isolation").error(
            f"Cleanup aborted: {exc}", exc_info=True
        )
        raise SystemExit(1)
