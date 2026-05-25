#!/usr/bin/env python3
"""
Assignment Category Relink — Live Verification
==============================================

Verifies the PATCH /admin/assignments/{id} and DELETE /admin/assignments/{id}
endpoints introduced to unblock the "vendor already assigned to this wedding"
case reported on /admin/budget.

Pre-change behavior
-------------------
A vendor assigned to a wedding from the Vendor Directory tab (with
``budget_category_id: null``) could not be linked to a budget category
afterwards. The Edit Category modal POSTed ``/admin/assign`` again, which
409'd because the partial unique index
``idx_vendor_assignment_wedding_vendor_unique`` keys on
``(wedding_id, vendor_profile_id)`` — not on ``budget_category_id``. The
``budget_category_id`` was effectively set-once.

Post-change behavior
--------------------
The new ``PATCH /admin/assignments/{id}`` route treats
``budget_category_id`` as a mutable property of the (wedding, vendor)
link. The new ``DELETE /admin/assignments/{id}`` soft-deletes the row
(sets ``is_deleted: True``), freeing the (wedding, vendor) slot.

Strategy
--------
SEED: one planner, two weddings (A, B), one vendor, and two budget
categories on wedding A.

VERIFY:
  1. POST /assign with no category → row created, ``budget_category_id``
     is null, ``is_deleted`` is False (covers the is_deleted insert fix).
  2. PATCH ``budget_category_id`` to category A1 → row updated, link
     visible on get_wedding_vendors.
  3. PATCH ``budget_category_id`` to category A2 → row updated again
     (re-link path).
  4. PATCH ``budget_category_id`` to null → row detached (unlink path).
  5. PATCH ``budget_category_id`` to a category on wedding B → 400
     "Budget category belongs to a different wedding"
     (cross-wedding guard).
  6. DELETE the assignment → row's is_deleted flips to True.
  7. POST /assign again with the same (vendor, wedding) → succeeds
     because the soft-deleted row no longer occupies the unique slot.

CHECKPOINT: a single live UX checkpoint where the user opens
/admin/budget, sees the Unlinked Vendors panel for the floating
assignment, links it to a category via the inline picker, and watches
the budget card update with the vendor badge.

Cleanup pair: cleanup_assignment_category_relink_state.py (created
manually if/when this driver is re-run against a long-lived stage).

Usage
-----
    # In another terminal:
    python testbed/testbed.py up
    # Then:
    python testbed/verify_assignment_category_relink.py
    # When done:
    python testbed/testbed.py down
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from bson import ObjectId

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from testbed.harness import Harness, PM_TOKEN_GOOD  # noqa: E402

# ---------------------------------------------------------------------------
# Driver constants — grep-visible so reruns are deterministic
# ---------------------------------------------------------------------------

PLANNER_EMAIL = "test_planner+relink@thespecialwedding.io"
PLANNER_PASSWORD = "RelinkVerifier2026!"  # pragma: allowlist secret
PLANNER_FIRST = "Relink"
PLANNER_LAST = "Verifier"
PLANNER_COMPANY = "Relink QA Co"

VENDOR_BUSINESS_NAME = "Relink Vendor Co"
VENDOR_EMAIL = "vendor+relink@thespecialwedding.io"
VENDOR_CATEGORY = "florist"

WEDDING_A_COUPLE = "Alex & Jordan (Relink A)"
WEDDING_B_COUPLE = "Riley & Sky (Relink B)"
CATEGORY_A1_NAME = "Florals — Ceremony"
CATEGORY_A2_NAME = "Florals — Reception"
CATEGORY_B_NAME = "Florals — Wedding B"

WEDDING_DATE_OFFSET_DAYS = 180
PLAN_ID = os.getenv("RELINK_PLAN_ID", "plan_signature")


def _api_patch(
    h: Harness, path: str, *, token: str, json: dict | None = None
) -> requests.Response:
    """PATCH helper — the shared harness does not expose PATCH because no
    other driver needed it; adding it locally keeps the harness surface
    small and lets this driver be self-contained.
    """
    return requests.patch(
        f"{h.config.backend_url}{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=json or {},
        timeout=30,
    )


def _api_delete(h: Harness, path: str, *, token: str) -> requests.Response:
    return requests.delete(
        f"{h.config.backend_url}{path}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    h = Harness(driver_name="verify_assignment_category_relink")
    h.preflight()
    admin_token = h.get_admin_token()

    # ---- SEED -----------------------------------------------------------
    h.phase("SEED", "subscribe planner; build two weddings, vendor, two categories")

    h.seed_planner(
        admin_token=admin_token,
        email=PLANNER_EMAIL,
        password=PLANNER_PASSWORD,
        plan_id=PLAN_ID,
        first_name=PLANNER_FIRST,
        last_name=PLANNER_LAST,
        company_name=PLANNER_COMPANY,
        pm_token=PM_TOKEN_GOOD,
    )

    token = h.login(PLANNER_EMAIL, PLANNER_PASSWORD)

    wedding_date = (
        (datetime.now(timezone.utc) + timedelta(days=WEDDING_DATE_OFFSET_DAYS))
        .date()
        .isoformat()
    )

    wedding_a_id = h.create_wedding(
        planner_token=token,
        couple_names=WEDDING_A_COUPLE,
        date_iso=wedding_date,
        guest_count=80,
        venue="Test Venue A",
    )
    wedding_b_id = h.create_wedding(
        planner_token=token,
        couple_names=WEDDING_B_COUPLE,
        date_iso=wedding_date,
        guest_count=80,
        venue="Test Venue B",
    )

    vendor_id = h.create_vendor_profile(
        planner_token=token,
        business_name=VENDOR_BUSINESS_NAME,
        email=VENDOR_EMAIL,
        service_category=VENDOR_CATEGORY,
    )

    category_a1_id = h.create_budget_category(
        planner_token=token,
        wedding_id=wedding_a_id,
        name=CATEGORY_A1_NAME,
        budgeted_amount=3000.00,
    )
    category_a2_id = h.create_budget_category(
        planner_token=token,
        wedding_id=wedding_a_id,
        name=CATEGORY_A2_NAME,
        budgeted_amount=5000.00,
    )
    category_b_id = h.create_budget_category(
        planner_token=token,
        wedding_id=wedding_b_id,
        name=CATEGORY_B_NAME,
        budgeted_amount=4000.00,
    )

    h.log.info("")
    h.log.info("Seed summary:")
    h.log.info(f"  planner:      {PLANNER_EMAIL}")
    h.log.info(f"  wedding_a:    {wedding_a_id}")
    h.log.info(f"  wedding_b:    {wedding_b_id}")
    h.log.info(f"  vendor:       {vendor_id}")
    h.log.info(f"  category_a1:  {category_a1_id}")
    h.log.info(f"  category_a2:  {category_a2_id}")
    h.log.info(f"  category_b:   {category_b_id}")
    h.log.info("")

    # ---- 1. POST /assign with no category --------------------------------
    h.phase(
        "VERIFY 1",
        "POST /assign with no category → floating row, is_deleted=False",
    )
    assignment_id = h.assign_vendor_to_wedding(
        planner_token=token,
        vendor_profile_id=vendor_id,
        wedding_id=wedding_a_id,
    )
    doc = h.mongo["vendor_assignments"].find_one({"_id": ObjectId(assignment_id)})
    _assert(doc is not None, "assignment row missing after POST /assign")
    _assert(
        doc.get("budget_category_id") in (None, ""),
        f"budget_category_id should be null, got {doc.get('budget_category_id')!r}",
    )
    _assert(
        doc.get("is_deleted") is False,
        f"is_deleted must be set to False on insert (partial index requires "
        f"exact False), got {doc.get('is_deleted')!r}",
    )
    h.log.info(f"  ✅ floating assignment created: {assignment_id}")

    # ---- 2. PATCH to category A1 -----------------------------------------
    h.phase("VERIFY 2", "PATCH budget_category_id → category_a1")
    resp = _api_patch(
        h,
        f"/admin/assignments/{assignment_id}",
        token=token,
        json={"budget_category_id": category_a1_id},
    )
    _assert(resp.status_code == 200, f"PATCH a1 failed: {resp.status_code} {resp.text}")
    body = resp.json()
    _assert(
        body.get("budget_category_id") == category_a1_id,
        f"response budget_category_id mismatch: {body.get('budget_category_id')!r}",
    )
    h.log.info(f"  ✅ linked to category_a1 ({CATEGORY_A1_NAME})")

    # ---- 3. PATCH to category A2 (re-link) -------------------------------
    h.phase("VERIFY 3", "PATCH budget_category_id → category_a2 (re-link)")
    resp = _api_patch(
        h,
        f"/admin/assignments/{assignment_id}",
        token=token,
        json={"budget_category_id": category_a2_id},
    )
    _assert(resp.status_code == 200, f"PATCH a2 failed: {resp.status_code} {resp.text}")
    body = resp.json()
    _assert(
        body.get("budget_category_id") == category_a2_id,
        f"re-link response mismatch: {body.get('budget_category_id')!r}",
    )
    h.log.info(f"  ✅ re-linked to category_a2 ({CATEGORY_A2_NAME})")

    # ---- 4. PATCH to null (unlink) ---------------------------------------
    h.phase("VERIFY 4", "PATCH budget_category_id → null (unlink)")
    resp = _api_patch(
        h,
        f"/admin/assignments/{assignment_id}",
        token=token,
        json={"budget_category_id": None},
    )
    _assert(
        resp.status_code == 200,
        f"PATCH unlink failed: {resp.status_code} {resp.text}",
    )
    body = resp.json()
    _assert(
        body.get("budget_category_id") in (None, ""),
        f"unlink response should be null, got {body.get('budget_category_id')!r}",
    )
    h.log.info("  ✅ assignment is floating again")

    # ---- 5. Cross-wedding guard ------------------------------------------
    h.phase(
        "VERIFY 5",
        "PATCH budget_category_id → category on wedding B → 400",
    )
    resp = _api_patch(
        h,
        f"/admin/assignments/{assignment_id}",
        token=token,
        json={"budget_category_id": category_b_id},
    )
    _assert(
        resp.status_code == 400,
        f"cross-wedding PATCH should 400, got {resp.status_code} {resp.text}",
    )
    body = resp.json()
    detail = body.get("detail", "")
    _assert(
        "different wedding" in str(detail).lower(),
        f"cross-wedding detail unexpected: {detail!r}",
    )
    h.log.info(f"  ✅ cross-wedding rejected: {detail}")

    # ---- 6. DELETE → soft-delete -----------------------------------------
    h.phase("VERIFY 6", "DELETE /assignments/{id} → soft-delete")
    resp = _api_delete(h, f"/admin/assignments/{assignment_id}", token=token)
    _assert(
        resp.status_code == 204,
        f"DELETE should return 204, got {resp.status_code} {resp.text}",
    )
    doc = h.mongo["vendor_assignments"].find_one({"_id": ObjectId(assignment_id)})
    _assert(doc is not None, "row should remain (soft-delete)")
    _assert(
        doc.get("is_deleted") is True,
        f"is_deleted should be True, got {doc.get('is_deleted')!r}",
    )
    _assert(doc.get("deleted_at") is not None, "deleted_at should be stamped")
    h.log.info(f"  ✅ assignment soft-deleted: {assignment_id}")

    # ---- 7. Re-assign after soft-delete ----------------------------------
    h.phase(
        "VERIFY 7",
        "POST /assign with same (vendor, wedding) → succeeds after soft-delete",
    )
    new_assignment_id = h.assign_vendor_to_wedding(
        planner_token=token,
        vendor_profile_id=vendor_id,
        wedding_id=wedding_a_id,
        budget_category_id=category_a1_id,
    )
    _assert(
        new_assignment_id != assignment_id,
        "re-assignment should mint a NEW row, not reuse the soft-deleted one",
    )
    h.log.info(f"  ✅ re-assigned cleanly: {new_assignment_id}")

    # ---- CHECKPOINT ------------------------------------------------------
    h.phase("CHECKPOINT", "live UX walk-through with the user watching")
    h.log.info("")
    h.log.info("Open the admin app as the test planner:")
    h.log.info(f"  email:    {PLANNER_EMAIL}")
    h.log.info(f"  password: {PLANNER_PASSWORD}")
    h.log.info("")
    h.log.info("Then:")
    h.log.info("  1. Navigate to /admin/budget and pick wedding A from the picker.")
    h.log.info("     EXPECT: vendor card on category A1 shows the vendor name.")
    h.log.info(
        "  2. From the same wedding, soft-delete that assignment via the "
        "Vendor Directory tab,"
    )
    h.log.info(
        "     then POST a NEW floating assignment from the Vendor Directory "
        "(no category)."
    )
    h.log.info(
        "     EXPECT: /admin/budget now renders the Unlinked Vendors panel."
    )
    h.log.info(
        "  3. In the panel, click 'Link to category', pick category A2 from "
        "the inline select."
    )
    h.log.info(
        "     EXPECT: toast 'Linked … to category', panel collapses, the A2 "
        "card now shows the vendor."
    )
    h.log.info(
        "  4. Open Edit Category on category A1 — the vendor dropdown should "
        "label the same vendor as 'on this wedding (Florals — Reception)'."
    )
    h.log.info(
        "     Pick it; submit. EXPECT: A1 now shows the vendor; A2 no longer "
        "shows it (link MOVED, not duplicated)."
    )
    h.log.info(
        "  5. Open the Unlinked Vendors panel for any floating vendor, click "
        "the trash icon, confirm."
    )
    h.log.info("     EXPECT: toast, row vanishes, vendor stays in directory.")
    h.log.info("")
    h.log.info("All seven scripted checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
