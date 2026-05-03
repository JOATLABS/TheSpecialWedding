#!/usr/bin/env python3
"""
AlertWire — Vendor Payment → Budget-Alert Refresh — Live Verification
======================================================================

Verifies the AlertWire fix that landed at three call sites:

  1. ``app/services/vendor_service.py:record_payment`` — after the
     milestone + rollup transaction commits.
  2. ``app/services/autopilot_service.py:_sync_payment_to_budget`` —
     after ``record_contract_payment`` returns.
  3. ``app/services/budget_service.py:record_contract_payment`` — before
     returning.

Each site now calls ``await BudgetService().evaluate_budget_alerts(wedding_id)``,
the public wrapper added by AlertWire around the previously-private
``_check_budget_alerts``. Pre-AlertWire, vendor-driven payments
(``vendor_service.record_payment``) bypassed alert evaluation entirely; a
$1,500 payment against a $1,000-allocated category would inflate
``budget_categories.actual_spent`` but never raise an ``over_budget``
alert in the ``budget_alerts`` collection.

NOTE — alert collection name. The task brief mentioned a "notifications"
collection; the actual implementation in ``_check_budget_alerts`` writes
to ``budget_alerts`` (model: ``app/models/budget.py:BudgetAlert``). This
verifier asserts against ``budget_alerts``.

Strategy
--------
This verifier focuses on the vendor_service site (the most
behaviorally-load-bearing of the three — it is the wedding-driven path
that lacked any prior alert refresh). The other two sites already had
implicit alert paths via ``record_contract_payment``; AlertWire makes the
refresh explicit and uniform.

Cases
-----
  CASE_TRIGGER  — record a $1,500 payment against a $1,000-allocated
                  category. Expect milestone PAID, all rollups updated,
                  AND a single ``over_budget`` alert in ``budget_alerts``
                  scoped to ``(wedding_id, category_id)``.
  CASE_DEDUP    — invoke the public wrapper a second time. Expect the
                  alert count to remain 1: ``_check_budget_alerts``
                  guards on
                  ``{wedding_id, category_id, alert_type, is_resolved: False}``
                  and short-circuits when the alert already exists.

Pre-conditions
--------------
  - ``STRIPE_SECRET_KEY``, ``MONGO_URI``, ``ROOT_ADMIN_PASSWORD`` in .env
  - Backend on localhost:8000 (testbed/testbed.py up)
  - The ``vendor_service.record_payment`` call is awaited directly inside
    the same event loop as the verifier's main(), matching the pattern
    in verify_payment_link_webhook_record_payment_routing.py — Motor's
    connection pool stays bound to a live loop.

Cleanup pair: cleanup_budget_alert_wiring_state.py

Usage
-----
    # In another terminal:
    python testbed/testbed.py up
    # Then:
    python testbed/verify_budget_alert_wiring.py
    # When done:
    python testbed/cleanup_budget_alert_wiring_state.py
    python testbed/testbed.py down
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from testbed.harness import Harness, PM_TOKEN_GOOD  # noqa: E402

# ---------------------------------------------------------------------------
# Driver constants — grep-visible so reruns are deterministic
# ---------------------------------------------------------------------------

PLANNER_EMAIL = "test_planner+alertwire@thespecialwedding.io"
PLANNER_PASSWORD = "AlertWire2026!"  # pragma: allowlist secret
PLANNER_FIRST = "AlertWire"
PLANNER_LAST = "Planner"
PLANNER_COMPANY = "AlertWire QA Co"

COUPLE_DISPLAY = "Cleo & Sam (AlertWire Verifier)"

VENDOR_BUSINESS_NAME = "Lens Co — AlertWire Verifier"
VENDOR_EMAIL = "vendor+alertwire@thespecialwedding.io"
VENDOR_CATEGORY = "photographer"

# Budget the rollup writes into. The trigger payment intentionally
# exceeds the cap so an `over_budget` alert MUST be raised.
BUDGET_CATEGORY_NAME = "Photography (AlertWire Verifier)"
BUDGET_CATEGORY_ALLOCATED = 1000.00

# Contract financials. A single milestone for $1,500 — payment will
# drive `actual_spent` from $0 to $1,500 in one shot, crossing the
# $1,000 cap with $500 of overage.
CONTRACT_TOTAL_AMOUNT = 1500.00
DEPOSIT_PERCENTAGE = 100.0
MILESTONE_DESCRIPTION = "Single Payment (AlertWire Verifier)"
MILESTONE_AMOUNT = 1500.00
PAYMENT_METHOD = "cash"

WEDDING_DATE_OFFSET_DAYS = 180
PLAN_ID = os.getenv("ALERTWIRE_PLAN_ID", "plan_signature")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _count_over_budget_alerts(h: Harness, *, wedding_id: str, category_id: str) -> int:
    """Count unresolved ``over_budget`` alerts scoped to (wedding, category).

    This is the dedup boundary that ``_check_budget_alerts`` enforces:
    the next call within the same wedding+category should NOT create a
    second row while the first remains unresolved.
    """
    return h.mongo["budget_alerts"].count_documents(
        {
            "wedding_id": wedding_id,
            "category_id": category_id,
            "alert_type": "over_budget",
        }
    )


def _read_one_over_budget_alert(
    h: Harness, *, wedding_id: str, category_id: str
) -> dict:
    doc = h.mongo["budget_alerts"].find_one(
        {
            "wedding_id": wedding_id,
            "category_id": category_id,
            "alert_type": "over_budget",
        }
    )
    if not doc:
        raise AssertionError(
            f"expected an `over_budget` alert for wedding={wedding_id} "
            f"category={category_id}, found none"
        )
    return doc


def _read_milestone(h: Harness, milestone_id: str) -> dict:
    from bson import ObjectId

    doc = h.mongo["vendor_payment_milestones"].find_one({"_id": ObjectId(milestone_id)})
    if not doc:
        raise AssertionError(f"milestone {milestone_id} not found in Mongo")
    return doc


def _read_assignment(h: Harness, *, vendor_profile_id: str, wedding_id: str) -> dict:
    doc = h.mongo["vendor_assignments"].find_one(
        {"vendor_profile_id": vendor_profile_id, "wedding_id": wedding_id}
    )
    if not doc:
        raise AssertionError(
            f"vendor_assignment for vp={vendor_profile_id} w={wedding_id} not found"
        )
    return doc


def _read_vendor_profile(h: Harness, vendor_profile_id: str) -> dict:
    from bson import ObjectId

    doc = h.mongo["vendor_profiles"].find_one({"_id": ObjectId(vendor_profile_id)})
    if not doc:
        raise AssertionError(f"vendor_profile {vendor_profile_id} not found")
    return doc


def _read_budget_category(h: Harness, category_id: str) -> dict:
    from bson import ObjectId

    doc = h.mongo["budget_categories"].find_one({"_id": ObjectId(category_id)})
    if not doc:
        raise AssertionError(f"budget_category {category_id} not found")
    return doc


def _approx_eq(a: float, b: float, tol: float = 0.005) -> bool:
    return abs(float(a) - float(b)) <= tol


# ---------------------------------------------------------------------------
# Phases
# ---------------------------------------------------------------------------


async def main() -> int:
    # Late import — vendor_service binds to mongo.client at import time.
    # Importing it before the harness loads .env would pin to the wrong DB.
    # Inside this single event loop we await record_payment directly so
    # Motor's connection pool stays bound to a live loop across the call.
    from app.services.budget_service import BudgetService  # noqa: WPS433
    from app.services.vendor_service import vendor_service  # noqa: WPS433

    h = Harness(driver_name="verify_budget_alert_wiring")
    h.preflight()
    admin_token = h.get_admin_token()

    # ---- SEED ---------------------------------------------------------------
    h.phase(
        "SEED",
        "subscribe planner; build wedding + budget + vendor + assignment + contract + milestone",
    )

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

    planner_token = h.login(PLANNER_EMAIL, PLANNER_PASSWORD)

    wedding_date = (
        (datetime.now(timezone.utc) + timedelta(days=WEDDING_DATE_OFFSET_DAYS))
        .date()
        .isoformat()
    )
    wedding_id = h.create_wedding(
        planner_token=planner_token,
        couple_names=COUPLE_DISPLAY,
        date_iso=wedding_date,
        guest_count=80,
        venue="Test Venue (AlertWire Verifier)",
    )

    budget_category_id = h.create_budget_category(
        planner_token=planner_token,
        wedding_id=wedding_id,
        name=BUDGET_CATEGORY_NAME,
        budgeted_amount=BUDGET_CATEGORY_ALLOCATED,
        description=(
            "AlertWire verifier — $1k cap. The verifier records a $1.5k "
            "payment to drive over_budget."
        ),
    )

    vendor_profile_id = h.create_vendor_profile(
        planner_token=planner_token,
        business_name=VENDOR_BUSINESS_NAME,
        email=VENDOR_EMAIL,
        service_category=VENDOR_CATEGORY,
    )

    h.assign_vendor_to_wedding(
        planner_token=planner_token,
        vendor_profile_id=vendor_profile_id,
        wedding_id=wedding_id,
        budget_category_id=budget_category_id,
        service_notes="AlertWire verifier — assignment row.",
    )

    contract_id = h.create_vendor_contract(
        planner_token=planner_token,
        wedding_id=wedding_id,
        vendor_profile_id=vendor_profile_id,
        total_amount=CONTRACT_TOTAL_AMOUNT,
        deposit_percentage=DEPOSIT_PERCENTAGE,
        service_date=wedding_date,
        service_location="Test Venue (AlertWire Verifier)",
    )

    due_date_iso = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    created_milestones = h.create_payment_milestones(
        planner_token=planner_token,
        contract_id=contract_id,
        milestones=[
            {
                "description": MILESTONE_DESCRIPTION,
                "amount": MILESTONE_AMOUNT,
                "due_date": due_date_iso,
            }
        ],
    )
    if not created_milestones:
        raise AssertionError("milestone create returned no documents")
    milestone = created_milestones[0]
    milestone_id = str(milestone.get("id") or milestone.get("_id"))
    if not milestone_id:
        raise AssertionError(f"created milestone has no id field: {milestone!r}")

    # Pre-trigger snapshot. The over_budget alert must be 0 at this
    # point; if a prior run leaked, cleanup wasn't run and re-running
    # the verifier without scrub will produce a false PASS on dedup.
    pre_alert_count = _count_over_budget_alerts(
        h, wedding_id=wedding_id, category_id=budget_category_id
    )
    if pre_alert_count != 0:
        raise AssertionError(
            "PRE-SEED FAIL: budget_alerts collection already contains "
            f"{pre_alert_count} `over_budget` alert(s) for wedding={wedding_id} "
            f"category={budget_category_id}. Run cleanup_budget_alert_wiring_state.py "
            "before re-running this verifier."
        )

    cat_before = _read_budget_category(h, budget_category_id)
    spent_before = float(cat_before.get("actual_spent") or 0)
    profile_before = _read_vendor_profile(h, vendor_profile_id)
    revenue_before = float(profile_before.get("total_revenue") or 0)
    asn_before = _read_assignment(
        h, vendor_profile_id=vendor_profile_id, wedding_id=wedding_id
    )
    asn_paid_before = float(asn_before.get("paid_amount") or 0)
    h.log.info(
        f"  PRE-TRIGGER: budget.actual_spent=${spent_before:.2f}, "
        f"profile.total_revenue=${revenue_before:.2f}, "
        f"assignment.paid=${asn_paid_before:.2f}, "
        f"over_budget alert count={pre_alert_count}"
    )

    # ---- CASE_TRIGGER — vendor payment crosses the $1k cap -----------------
    h.phase(
        "CASE_TRIGGER",
        f"record_payment ${MILESTONE_AMOUNT:.2f} against ${BUDGET_CATEGORY_ALLOCATED:.2f} cap; "
        "expect milestone PAID, rollups updated, AND a single over_budget alert",
    )
    await vendor_service.record_payment(
        milestone_id=milestone_id,
        amount=MILESTONE_AMOUNT,
        payment_method=PAYMENT_METHOD,
        created_by=PLANNER_EMAIL,
        notes="AlertWire verifier — single payment, drives over_budget",
    )

    # Milestone is PAID with the full amount.
    milestone_after = _read_milestone(h, milestone_id)
    if milestone_after.get("status") != "paid":
        raise AssertionError(
            f"CASE_TRIGGER FAIL: milestone status expected 'paid', "
            f"got {milestone_after.get('status')!r}"
        )
    if not _approx_eq(milestone_after.get("paid_amount", 0), MILESTONE_AMOUNT):
        raise AssertionError(
            f"CASE_TRIGGER FAIL: milestone.paid_amount expected "
            f"${MILESTONE_AMOUNT:.2f}, "
            f"got ${float(milestone_after.get('paid_amount', 0)):.2f}"
        )

    # Rollups all moved by exactly the milestone amount.
    asn_after = _read_assignment(
        h, vendor_profile_id=vendor_profile_id, wedding_id=wedding_id
    )
    asn_paid_after = float(asn_after.get("paid_amount") or 0)
    if not _approx_eq(asn_paid_after, asn_paid_before + MILESTONE_AMOUNT):
        raise AssertionError(
            f"CASE_TRIGGER FAIL: vendor_assignments.paid_amount expected "
            f"${asn_paid_before + MILESTONE_AMOUNT:.2f}, got ${asn_paid_after:.2f}"
        )

    profile_after = _read_vendor_profile(h, vendor_profile_id)
    revenue_after = float(profile_after.get("total_revenue") or 0)
    if not _approx_eq(revenue_after, revenue_before + MILESTONE_AMOUNT):
        raise AssertionError(
            f"CASE_TRIGGER FAIL: vendor_profiles.total_revenue expected "
            f"${revenue_before + MILESTONE_AMOUNT:.2f}, got ${revenue_after:.2f}"
        )

    cat_after = _read_budget_category(h, budget_category_id)
    spent_after = float(cat_after.get("actual_spent") or 0)
    if not _approx_eq(spent_after, spent_before + MILESTONE_AMOUNT):
        raise AssertionError(
            f"CASE_TRIGGER FAIL: budget_categories.actual_spent expected "
            f"${spent_before + MILESTONE_AMOUNT:.2f}, got ${spent_after:.2f}"
        )

    # AlertWire's primary assertion: a NEW `over_budget` alert exists
    # for this wedding+category. Pre-AlertWire this would still be 0
    # because vendor_service.record_payment never called the alert
    # evaluator.
    post_alert_count = _count_over_budget_alerts(
        h, wedding_id=wedding_id, category_id=budget_category_id
    )
    if post_alert_count != 1:
        raise AssertionError(
            "CASE_TRIGGER FAIL — ALERTWIRE BROKEN: expected exactly 1 "
            "`over_budget` alert in budget_alerts for "
            f"wedding={wedding_id} category={budget_category_id}, "
            f"got {post_alert_count}. Pre-AlertWire this would have been 0 "
            "(vendor_service.record_payment bypassed alert evaluation). "
            "If 0: confirm `await BudgetService().evaluate_budget_alerts(...)` "
            "is called after _record_in_transaction commits in vendor_service."
        )

    alert = _read_one_over_budget_alert(
        h, wedding_id=wedding_id, category_id=budget_category_id
    )
    expected_overage = spent_after - BUDGET_CATEGORY_ALLOCATED  # $500
    alert_amount = float(alert.get("amount") or 0)
    if not _approx_eq(alert_amount, expected_overage):
        raise AssertionError(
            f"CASE_TRIGGER FAIL: alert.amount expected overage "
            f"${expected_overage:.2f} (spent ${spent_after:.2f} - cap "
            f"${BUDGET_CATEGORY_ALLOCATED:.2f}), got ${alert_amount:.2f}"
        )
    alert_threshold = float(alert.get("threshold") or 0)
    if not _approx_eq(alert_threshold, BUDGET_CATEGORY_ALLOCATED):
        raise AssertionError(
            f"CASE_TRIGGER FAIL: alert.threshold expected "
            f"${BUDGET_CATEGORY_ALLOCATED:.2f} (the cap), "
            f"got ${alert_threshold:.2f}"
        )
    if alert.get("severity") != "high":
        raise AssertionError(
            f"CASE_TRIGGER FAIL: alert.severity expected 'high' "
            f"(over_budget tier per _check_budget_alerts), "
            f"got {alert.get('severity')!r}"
        )
    if alert.get("is_resolved") is True:
        raise AssertionError(
            "CASE_TRIGGER FAIL: alert.is_resolved is True; expected False "
            "for a fresh over_budget alert (the dedup guard reads "
            "is_resolved: False)."
        )
    # Title should reference the category by name.
    alert_title = str(alert.get("title") or "")
    if BUDGET_CATEGORY_NAME not in alert_title:
        raise AssertionError(
            f"CASE_TRIGGER FAIL: alert.title expected to include "
            f"'{BUDGET_CATEGORY_NAME}', got {alert_title!r}"
        )

    h.log.info(
        f"  ✅ CASE_TRIGGER — over_budget alert raised "
        f"(amount=${alert_amount:.2f}, severity={alert.get('severity')!r}, "
        f"title={alert_title!r})"
    )

    # ---- CASE_DEDUP — second public-wrapper call should NOT duplicate ------
    h.phase(
        "CASE_DEDUP",
        "invoke evaluate_budget_alerts again; expect alert count to remain 1",
    )
    await BudgetService().evaluate_budget_alerts(wedding_id)

    dedup_count = _count_over_budget_alerts(
        h, wedding_id=wedding_id, category_id=budget_category_id
    )
    if dedup_count != 1:
        raise AssertionError(
            "CASE_DEDUP FAIL: a second invocation of evaluate_budget_alerts "
            f"changed the over_budget alert count to {dedup_count}; expected "
            "1. The dedup guard in _check_budget_alerts checks "
            "{wedding_id, category_id, alert_type, is_resolved: False} and "
            "should short-circuit when an unresolved match exists."
        )

    h.log.info(
        "  ✅ CASE_DEDUP — repeat evaluate_budget_alerts() did not duplicate "
        "the alert (still 1 row)"
    )

    # ---- CHECKPOINT — UI: planner sees the alert in /admin/notifications ---
    h.checkpoint(
        "UI-1 (post-AlertWire — over_budget alert visible to planner)",
        [
            f"Open {h.config.frontend_url}/admin/login as planner:",
            f"     {PLANNER_EMAIL} / {PLANNER_PASSWORD}",
            "Navigate to /admin/notifications.",
            f"Confirm an `over_budget` alert for '{BUDGET_CATEGORY_NAME}' is",
            f"     listed: spent ${spent_after:,.2f} against allocation",
            f"     ${BUDGET_CATEGORY_ALLOCATED:,.2f} (overage "
            f"${spent_after - BUDGET_CATEGORY_ALLOCATED:,.2f}).",
            "Browser console should be clean (no 4xx/5xx, no React warnings).",
            f"Optional: /admin/budget?wedding_id={wedding_id} should also",
            "     surface this alert in the alerts panel.",
        ],
    )

    h.log.info("")
    h.log.info(
        "✅ verify_budget_alert_wiring: all assertions pass (CASE_TRIGGER + CASE_DEDUP)"
    )
    h.log.info(
        "Run testbed/cleanup_budget_alert_wiring_state.py to reset before rerun."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except Exception as exc:
        import logging

        logging.getLogger("verify_budget_alert_wiring").error(
            f"Verification aborted: {exc}", exc_info=True
        )
        raise SystemExit(1)
