#!/usr/bin/env python3
"""
Dashboard Payment Aggregation Cross-Tenant Isolation — Live Verification
========================================================================

Verifies the fix at app/services/vendor_service.py:get_dashboard_counts and
get_payment_milestones for VENDOR_CONTRACT_PREPROD ticket #2: a planner
viewing /admin/dashboard saw totals summed across every other planner's
milestones because the milestone aggregation pipeline filtered by
``wedding_id`` only (and not at all when no wedding filter was passed).

Pre-fix behavior
----------------
``get_dashboard_counts`` ran a milestone ``$group`` over ALL planners'
``vendor_payment_milestones`` rows. ``get_payment_milestones`` had a
similar shape: when invoked WITHOUT a ``contract_id`` and WITHOUT a
``created_by``, the find spanned every planner. The ``update_many``
overdue-marking branch filtered only on ``_id IN [...]`` — fragile
against future callers.

Post-fix behavior
-----------------
Both methods now accept ``created_by: Optional[str]``:

  - When ``None`` (root admin): scope is bypassed (matches Ticket #1
    pattern at app/api/vendor_management.py:73, :133, :148, :440).
  - When provided: the find / aggregation pipeline / update_many all
    filter by ``created_by``. The aggregation ``$match`` lands BEFORE
    ``$group`` so cross-tenant rows never enter the sum.

The dashboard route at app/api/vendor_management.py:577 derives
``owner_email`` exactly the same way and threads it through.

Strategy
--------
SEED two planners on real subscriptions, then build:

  * Planner A → 1 wedding (W_A) → 1 vendor → 1 contract → 3 milestones
        $10k paid, $10k scheduled, $10k scheduled. Total seeded = $30k.
  * Planner B → 1 wedding (W_B) → 1 vendor → 1 contract → 5 milestones
        all $100k each, all PAID. Total seeded = $500k.
  * Planner C → no contracts, no milestones (empty-state planner).

Three CASES — each hits ``/admin/dashboard`` and asserts the response
breakdown matches the seeded planner ONLY:

  CASE 1 — no wedding filter, planner A. Pre-fix: total_paid > $10k +
           total_due > $20k (leak from B). Post-fix: exact A breakdown.
  CASE 2 — wedding_id=W_A, planner A. Same exact breakdown.
  CASE 3 — planner C with zero seeded milestones. All numeric fields
           are zero (NOT planner B's totals).

Plus 2 live UI checkpoints (planner A's dashboard cards; planner B
confirms their own totals are still visible to them only).

Cleanup pair: cleanup_dashboard_payment_aggregation_isolation_state.py

Usage
-----
    # In another terminal:
    python testbed/testbed.py up
    # Then:
    python testbed/verify_dashboard_payment_aggregation_isolation.py
    # When done:
    python testbed/cleanup_dashboard_payment_aggregation_isolation_state.py
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

PLANNER_A_EMAIL = "test_planner+dashagg_a@thespecialwedding.io"
PLANNER_A_PASSWORD = "DashAggA2026!"  # pragma: allowlist secret
PLANNER_A_FIRST = "DashAgg"
PLANNER_A_LAST = "PlannerA"
PLANNER_A_COMPANY = "DashAgg QA Co A"

PLANNER_B_EMAIL = "test_planner+dashagg_b@thespecialwedding.io"
PLANNER_B_PASSWORD = "DashAggB2026!"  # pragma: allowlist secret
PLANNER_B_FIRST = "DashAgg"
PLANNER_B_LAST = "PlannerB"
PLANNER_B_COMPANY = "DashAgg QA Co B"

PLANNER_C_EMAIL = "test_planner+dashagg_c@thespecialwedding.io"
PLANNER_C_PASSWORD = "DashAggC2026!"  # pragma: allowlist secret
PLANNER_C_FIRST = "DashAgg"
PLANNER_C_LAST = "PlannerC"
PLANNER_C_COMPANY = "DashAgg QA Co C"

VENDOR_A_BUSINESS_NAME = "Vendor A Co — DashAgg Verifier"
VENDOR_A_EMAIL = "vendor+dashagg_a@thespecialwedding.io"
VENDOR_B_BUSINESS_NAME = "Vendor B Co — DashAgg Verifier"
VENDOR_B_EMAIL = "vendor+dashagg_b@thespecialwedding.io"
VENDOR_CATEGORY = "florist"

WEDDING_A_COUPLE = "Alex & Jordan (DashAgg A)"
WEDDING_B_COUPLE = "Riley & Sky (DashAgg B)"

# Planner A — 3 milestones, $30k total: 1 paid $10k + 2 scheduled $10k.
CONTRACT_A_TOTAL = 30000.00
MILESTONE_A1_AMOUNT = 10000.00  # will be marked PAID via record_payment
MILESTONE_A2_AMOUNT = 10000.00  # remains pending (scheduled)
MILESTONE_A3_AMOUNT = 10000.00  # remains pending (scheduled)
PLANNER_A_TOTAL_PAID_EXPECTED = 10000.00
PLANNER_A_TOTAL_DUE_EXPECTED = 20000.00  # 2 pending milestones
PLANNER_A_PENDING_COUNT_EXPECTED = 2
PLANNER_A_OVERDUE_COUNT_EXPECTED = 0

# Planner B — 5 milestones, $500k total all PAID.
CONTRACT_B_TOTAL = 500000.00
MILESTONE_B_AMOUNT = 100000.00
PLANNER_B_TOTAL_PAID_EXPECTED = 500000.00
PLANNER_B_TOTAL_DUE_EXPECTED = 0.00

WEDDING_DATE_OFFSET_DAYS = 180
PLAN_ID = os.getenv("DASHAGG_PLAN_ID", "plan_signature")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _approx_eq(a: float, b: float, tol: float = 0.005) -> bool:
    return abs(float(a) - float(b)) <= tol


def _fetch_dashboard(h: Harness, *, token: str, wedding_id: str | None = None) -> dict:
    """GET /admin/dashboard and return the parsed payload.

    Mirrors the live UI request so the verifier exercises the same code
    path the planner does. ``wedding_id`` is forwarded as a query param
    when provided.
    """
    path = "/admin/dashboard"
    if wedding_id:
        path += f"?wedding_id={wedding_id}"
    resp = h.api_get(path, token=token)
    if resp.status_code != 200:
        raise AssertionError(
            f"GET {path} expected 200, got {resp.status_code} body={resp.text[:300]}"
        )
    return resp.json()


def _seed_planner_milestones(
    h: Harness,
    *,
    planner_token: str,
    planner_email: str,
    wedding_couple: str,
    vendor_business_name: str,
    vendor_email: str,
    contract_total: float,
    milestone_specs: list[tuple[str, float, bool]],
    wedding_date_iso: str,
) -> dict:
    """Seed wedding + vendor + assignment + contract + milestones.

    ``milestone_specs`` is a list of ``(description, amount, mark_paid)``
    tuples. When ``mark_paid`` is True the milestone is recorded paid via
    the ``record_payment`` endpoint so the resulting status is ``paid``
    and ``paid_amount == amount``. This is exactly what a planner would
    do in production — every state change rides through the real route.

    Returns a dict with the ids the cleanup pair needs.
    """
    wedding_id = h.create_wedding(
        planner_token=planner_token,
        couple_names=wedding_couple,
        date_iso=wedding_date_iso,
        guest_count=80,
        venue=f"Test Venue ({vendor_business_name})",
    )

    vendor_id = h.create_vendor_profile(
        planner_token=planner_token,
        business_name=vendor_business_name,
        email=vendor_email,
        service_category=VENDOR_CATEGORY,
    )

    h.assign_vendor_to_wedding(
        planner_token=planner_token,
        vendor_profile_id=vendor_id,
        wedding_id=wedding_id,
        service_notes=f"DashAgg verifier — {planner_email}",
    )

    contract_id = h.create_vendor_contract(
        planner_token=planner_token,
        wedding_id=wedding_id,
        vendor_profile_id=vendor_id,
        total_amount=contract_total,
        service_date=wedding_date_iso,
        service_location=f"Test Venue ({vendor_business_name})",
    )

    due_date_iso = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
    payload_milestones = [
        {"description": desc, "amount": amount, "due_date": due_date_iso}
        for (desc, amount, _paid) in milestone_specs
    ]
    created = h.create_payment_milestones(
        planner_token=planner_token,
        contract_id=contract_id,
        milestones=payload_milestones,
    )

    milestone_ids: list[str] = []
    for ms_doc, (_desc, amount, mark_paid) in zip(created, milestone_specs):
        ms_id = str(ms_doc.get("id") or ms_doc.get("_id"))
        milestone_ids.append(ms_id)
        if mark_paid:
            h.record_milestone_payment(
                planner_token=planner_token,
                milestone_id=ms_id,
                amount=amount,
                payment_method="bank_transfer",
                notes="DashAgg verifier — pre-marked paid for total_paid total.",
            )

    return {
        "wedding_id": wedding_id,
        "vendor_id": vendor_id,
        "contract_id": contract_id,
        "milestone_ids": milestone_ids,
    }


# ---------------------------------------------------------------------------
# Phases
# ---------------------------------------------------------------------------


async def main() -> int:
    h = Harness(driver_name="verify_dashboard_payment_aggregation_isolation")
    h.preflight()
    admin_token = h.get_admin_token()

    # ---- SEED ---------------------------------------------------------------
    h.phase(
        "SEED",
        "subscribe planner A + B + C; build $30k (A) + $500k (B); C empty",
    )

    h.seed_planner(
        admin_token=admin_token,
        email=PLANNER_A_EMAIL,
        password=PLANNER_A_PASSWORD,
        plan_id=PLAN_ID,
        first_name=PLANNER_A_FIRST,
        last_name=PLANNER_A_LAST,
        company_name=PLANNER_A_COMPANY,
        pm_token=PM_TOKEN_GOOD,
    )
    h.seed_planner(
        admin_token=admin_token,
        email=PLANNER_B_EMAIL,
        password=PLANNER_B_PASSWORD,
        plan_id=PLAN_ID,
        first_name=PLANNER_B_FIRST,
        last_name=PLANNER_B_LAST,
        company_name=PLANNER_B_COMPANY,
        pm_token=PM_TOKEN_GOOD,
    )
    h.seed_planner(
        admin_token=admin_token,
        email=PLANNER_C_EMAIL,
        password=PLANNER_C_PASSWORD,
        plan_id=PLAN_ID,
        first_name=PLANNER_C_FIRST,
        last_name=PLANNER_C_LAST,
        company_name=PLANNER_C_COMPANY,
        pm_token=PM_TOKEN_GOOD,
    )

    token_a = h.login(PLANNER_A_EMAIL, PLANNER_A_PASSWORD)
    token_b = h.login(PLANNER_B_EMAIL, PLANNER_B_PASSWORD)
    token_c = h.login(PLANNER_C_EMAIL, PLANNER_C_PASSWORD)

    wedding_date = (
        (datetime.now(timezone.utc) + timedelta(days=WEDDING_DATE_OFFSET_DAYS))
        .date()
        .isoformat()
    )

    seed_a = _seed_planner_milestones(
        h,
        planner_token=token_a,
        planner_email=PLANNER_A_EMAIL,
        wedding_couple=WEDDING_A_COUPLE,
        vendor_business_name=VENDOR_A_BUSINESS_NAME,
        vendor_email=VENDOR_A_EMAIL,
        contract_total=CONTRACT_A_TOTAL,
        milestone_specs=[
            ("DashAgg A — milestone 1 (paid)", MILESTONE_A1_AMOUNT, True),
            ("DashAgg A — milestone 2 (scheduled)", MILESTONE_A2_AMOUNT, False),
            ("DashAgg A — milestone 3 (scheduled)", MILESTONE_A3_AMOUNT, False),
        ],
        wedding_date_iso=wedding_date,
    )

    seed_b = _seed_planner_milestones(
        h,
        planner_token=token_b,
        planner_email=PLANNER_B_EMAIL,
        wedding_couple=WEDDING_B_COUPLE,
        vendor_business_name=VENDOR_B_BUSINESS_NAME,
        vendor_email=VENDOR_B_EMAIL,
        contract_total=CONTRACT_B_TOTAL,
        milestone_specs=[
            (f"DashAgg B — milestone {n} (paid)", MILESTONE_B_AMOUNT, True)
            for n in range(1, 6)
        ],
        wedding_date_iso=wedding_date,
    )

    h.log.info("")
    h.log.info("Seed summary:")
    h.log.info(f"  planner A: {PLANNER_A_EMAIL}")
    h.log.info(f"    wedding:    {seed_a['wedding_id']}")
    h.log.info(f"    contract:   {seed_a['contract_id']}")
    h.log.info(
        f"    milestones: 3 totalling ${CONTRACT_A_TOTAL:,.2f} "
        f"(${PLANNER_A_TOTAL_PAID_EXPECTED:,.2f} paid + "
        f"${PLANNER_A_TOTAL_DUE_EXPECTED:,.2f} pending)"
    )
    h.log.info(f"  planner B: {PLANNER_B_EMAIL}")
    h.log.info(f"    wedding:    {seed_b['wedding_id']}")
    h.log.info(f"    contract:   {seed_b['contract_id']}")
    h.log.info(f"    milestones: 5 totalling ${CONTRACT_B_TOTAL:,.2f} all paid")
    h.log.info(f"  planner C: {PLANNER_C_EMAIL}  (no milestones)")
    h.log.info("")

    failures: list[str] = []

    def _expect_payments(
        label: str,
        payload: dict,
        *,
        expected_total_paid: float,
        expected_total_due: float,
        expected_pending_count: int,
        expected_overdue_count: int,
    ) -> None:
        payments = payload.get("payments") or {}
        total_paid = float(payments.get("total_paid") or 0)
        total_due = float(payments.get("total_due") or 0)
        pending_count = int(payments.get("pending_count") or 0)
        overdue_count = int(payments.get("overdue_count") or 0)

        ok = True
        if not _approx_eq(total_paid, expected_total_paid):
            failures.append(
                f"{label}: total_paid expected ${expected_total_paid:,.2f}, "
                f"got ${total_paid:,.2f} (likely cross-tenant leak)"
            )
            ok = False
        if not _approx_eq(total_due, expected_total_due):
            failures.append(
                f"{label}: total_due expected ${expected_total_due:,.2f}, "
                f"got ${total_due:,.2f} (likely cross-tenant leak)"
            )
            ok = False
        if pending_count != expected_pending_count:
            failures.append(
                f"{label}: pending_count expected {expected_pending_count}, "
                f"got {pending_count}"
            )
            ok = False
        if overdue_count != expected_overdue_count:
            failures.append(
                f"{label}: overdue_count expected {expected_overdue_count}, "
                f"got {overdue_count}"
            )
            ok = False

        if ok:
            h.log.info(
                f"  ✅ {label}: total_paid=${total_paid:,.2f}, "
                f"total_due=${total_due:,.2f}, pending={pending_count}, "
                f"overdue={overdue_count}"
            )
        else:
            h.log.error(
                f"  ❌ {label}: total_paid=${total_paid:,.2f}, "
                f"total_due=${total_due:,.2f}, pending={pending_count}, "
                f"overdue={overdue_count}"
            )

    # ---- CASE 1 — no filter, planner A -------------------------------------
    h.phase(
        "CASE_1",
        "planner A → /admin/dashboard (no wedding filter) — "
        "expect A's $30k breakdown only, NOT a leak from B's $500k",
    )

    payload_a_nofilter = _fetch_dashboard(h, token=token_a)
    _expect_payments(
        "CASE 1 — planner A no-filter",
        payload_a_nofilter,
        expected_total_paid=PLANNER_A_TOTAL_PAID_EXPECTED,
        expected_total_due=PLANNER_A_TOTAL_DUE_EXPECTED,
        expected_pending_count=PLANNER_A_PENDING_COUNT_EXPECTED,
        expected_overdue_count=PLANNER_A_OVERDUE_COUNT_EXPECTED,
    )

    # ---- CASE 2 — wedding filter, planner A --------------------------------
    h.phase(
        "CASE_2",
        f"planner A → /admin/dashboard?wedding_id={seed_a['wedding_id']} — "
        "expect SAME $30k breakdown (filter narrows further, not wider)",
    )

    payload_a_wfilter = _fetch_dashboard(
        h, token=token_a, wedding_id=seed_a["wedding_id"]
    )
    _expect_payments(
        "CASE 2 — planner A wedding-filter",
        payload_a_wfilter,
        expected_total_paid=PLANNER_A_TOTAL_PAID_EXPECTED,
        expected_total_due=PLANNER_A_TOTAL_DUE_EXPECTED,
        expected_pending_count=PLANNER_A_PENDING_COUNT_EXPECTED,
        expected_overdue_count=PLANNER_A_OVERDUE_COUNT_EXPECTED,
    )

    # ---- CASE 3 — empty-state planner C ------------------------------------
    h.phase(
        "CASE_3",
        "planner C (no milestones) → /admin/dashboard — "
        "expect zeros, NOT planner B's $500k",
    )

    payload_c = _fetch_dashboard(h, token=token_c)
    _expect_payments(
        "CASE 3 — planner C empty-state",
        payload_c,
        expected_total_paid=0.0,
        expected_total_due=0.0,
        expected_pending_count=0,
        expected_overdue_count=0,
    )

    # Sanity: planner B still sees their own $500k. The fix must not over-scope.
    payload_b_nofilter = _fetch_dashboard(h, token=token_b)
    _expect_payments(
        "SANITY — planner B no-filter",
        payload_b_nofilter,
        expected_total_paid=PLANNER_B_TOTAL_PAID_EXPECTED,
        expected_total_due=PLANNER_B_TOTAL_DUE_EXPECTED,
        expected_pending_count=0,
        expected_overdue_count=0,
    )

    # ---- CHECKPOINTS -------------------------------------------------------
    h.checkpoint(
        "1 — Planner A dashboard cards (live UI)",
        [
            f"Open {h.config.frontend_url}/admin/login as planner A:",
            f"     {PLANNER_A_EMAIL} / {PLANNER_A_PASSWORD}",
            "Navigate to /admin/dashboard.",
            f"Confirm Total Paid card reads ${PLANNER_A_TOTAL_PAID_EXPECTED:,.2f} "
            "(NOT a higher number).",
            f"Confirm Total Due card reads ${PLANNER_A_TOTAL_DUE_EXPECTED:,.2f}.",
            f"Confirm Pending count = {PLANNER_A_PENDING_COUNT_EXPECTED}.",
            "Console: no errors, no warnings.",
            "(pre-fix the cards summed across planner B's $500k as well)",
        ],
    )

    h.checkpoint(
        "2 — Planner B dashboard cards (live UI)",
        [
            f"Logout, then login as planner B: {PLANNER_B_EMAIL} / "
            f"{PLANNER_B_PASSWORD}",
            "Navigate to /admin/dashboard.",
            f"Confirm Total Paid card reads ${PLANNER_B_TOTAL_PAID_EXPECTED:,.2f}.",
            f"Confirm Total Due card reads ${PLANNER_B_TOTAL_DUE_EXPECTED:,.2f}.",
            "(planner B's totals are still visible to planner B — the fix "
            "scopes per-planner, it does not over-restrict)",
            "Console: no errors, no warnings.",
        ],
    )

    h.log.info("")
    if failures:
        h.log.error(f"verify FAILED with {len(failures)} issue(s):")
        for f in failures:
            h.log.error(f"  ✗ {f}")
        h.log.info(
            "Run testbed/cleanup_dashboard_payment_aggregation_isolation_state.py "
            "to reset."
        )
        return 1

    h.log.info(
        "✅ verify_dashboard_payment_aggregation_isolation: all 3 cases + "
        "SANITY passed. Dashboard payment aggregation is planner-scoped."
    )
    h.log.info(
        "Run testbed/cleanup_dashboard_payment_aggregation_isolation_state.py to reset."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except Exception as exc:
        import logging

        logging.getLogger("verify_dashboard_payment_aggregation_isolation").error(
            f"Verification aborted: {exc}", exc_info=True
        )
        raise SystemExit(1)
