#!/usr/bin/env python3
"""
Vendor Contract → Budget Category Propagation — Live Verification
==================================================================

Verifies the fix at app/services/vendor_service.py:create_contract that
populates `vendor_contracts.budget_category_id` from the vendor's prior
assignment, so milestone payments can roll up into
`budget_categories.actual_spent`.

Before the fix: contract.budget_category_id was hardcoded `None` at
create. The conditional rollup at vendor_service.record_payment :3129
(`if milestone.get("budget_category_id"):`) was unreachable in practice,
so manual milestone payments never updated the budget tracker.

After the fix: contract create now reads the assignment for
(vendor_profile_id, wedding_id) and copies budget_category_id from it.
Milestones inherit the value at create. record_payment's $inc on
budget_categories.actual_spent now fires as designed.

Flow (every step through the real planner endpoint):

  1. Planner subscribes (real Stripe Subscription, no clock).
  2. Planner creates a wedding.
  3. Planner creates a budget category for the wedding.
  4. Planner adds a vendor to the directory.
  5. Planner assigns the vendor to the wedding WITH the budget category.
  6. Planner creates a vendor contract.
  7. ASSERT: contract.budget_category_id == the category id from step 3.
     This is the fix's primary assertion. Pre-fix: would be None.
  8. Planner creates a payment milestone on the contract.
  9. Planner records a manual payment against the milestone.
 10. ASSERT: budget.categories[that_category].actual_spent reflects
     the payment. Pre-fix: would still be 0 because the rollup was
     unreachable.
 11. UI checkpoints in Chrome with the user watching.

No direct Mongo writes for product state. Every state change goes
through an endpoint a real planner would hit.

Accounts (plus-variant; base accounts never touched)
----------------------------------------------------
  Planner : test_planner+budgetprop@thespecialwedding.io

Pre-conditions
--------------
  - `STRIPE_SECRET_KEY`, `MONGO_URI`, `ROOT_ADMIN_PASSWORD` in .env
  - Backend on localhost:8000, frontend on localhost:3000
  - Stripe webhook listener forwarding:
      `stripe listen --forward-to localhost:8000/stripe/webhook`

Cleanup pair: cleanup_vendor_contract_budget_propagation_state.py

Usage
-----
    python testbed/verify_vendor_contract_budget_propagation.py
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from testbed.harness import Harness, PM_TOKEN_GOOD

# ---------------------------------------------------------------------------
# Driver constants — grep-visible so reruns are deterministic
# ---------------------------------------------------------------------------

PLANNER_EMAIL = "test_planner+budgetprop@thespecialwedding.io"
PLANNER_PASSWORD = "BudgetPropPlanner2026!"  # pragma: allowlist secret
PLANNER_FIRST = "Budget"
PLANNER_LAST = "PropPlanner"
PLANNER_COMPANY = "Budget Propagation QA Co"

COUPLE_DISPLAY = "Avery & Morgan (BudgetProp)"

VENDOR_BUSINESS_NAME = "Snap Studios — BudgetProp Verifier"
VENDOR_EMAIL = "vendor+budgetprop@thespecialwedding.io"
VENDOR_CATEGORY = "photographer"

# Budget shape the planner sets up.
BUDGET_CATEGORY_NAME = "Photography (BudgetProp Verifier)"
BUDGET_CATEGORY_ALLOCATED = 5000.00

# Contract financials.
CONTRACT_TOTAL_AMOUNT = 3000.00
DEPOSIT_PERCENTAGE = 50.0

# Payment to record manually.
DEPOSIT_MILESTONE_DESCRIPTION = "Deposit (BudgetProp Verifier)"
DEPOSIT_MILESTONE_AMOUNT = 1500.00
PAYMENT_METHOD = "bank_transfer"

WEDDING_DATE_OFFSET_DAYS = 180
PLAN_ID = os.getenv("BUDGETPROP_PLAN_ID", "plan_signature")


# ---------------------------------------------------------------------------
# Phases
# ---------------------------------------------------------------------------


def main() -> int:
    h = Harness(driver_name="verify_vendor_contract_budget_propagation")
    h.preflight()
    admin_token = h.get_admin_token()

    # ---- SEED ---------------------------------------------------------------
    h.phase(
        "SEED",
        "subscribe planner via real Stripe; build wedding + budget + vendor + assignment",
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
        venue="Test Venue (BudgetProp Verifier)",
    )

    # The budget category — what the contract should inherit through the fix.
    budget_category_id = h.create_budget_category(
        planner_token=planner_token,
        wedding_id=wedding_id,
        name=BUDGET_CATEGORY_NAME,
        budgeted_amount=BUDGET_CATEGORY_ALLOCATED,
        description="Verifier-seeded category. Cleanup removes by name suffix.",
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
        service_notes="BudgetProp verifier seed. Real assignment row.",
    )

    # ---- UI-1: pre-contract world-state check -------------------------------
    h.checkpoint(
        "UI-1 (pre-contract — wedding, budget category, and assignment exist)",
        [
            f"Open {h.config.frontend_url}/admin/login as planner:",
            f"     {PLANNER_EMAIL} / {PLANNER_PASSWORD}",
            f"/admin/weddings should list {COUPLE_DISPLAY} (date {wedding_date}).",
            f"/admin/budget?wedding_id={wedding_id} should show:",
            f"     '{BUDGET_CATEGORY_NAME}' allocated ${BUDGET_CATEGORY_ALLOCATED:,.2f}",
            "     actual_spent: $0.00 (no payments recorded yet).",
            f"/admin/vendors should list {VENDOR_BUSINESS_NAME}.",
            f"/admin/weddings/{wedding_id} → Vendors tab should show",
            f"     {VENDOR_BUSINESS_NAME} assigned, linked to '{BUDGET_CATEGORY_NAME}'.",
        ],
    )

    # ---- CREATE CONTRACT ----------------------------------------------------
    h.phase(
        "CREATE_CONTRACT",
        "create vendor contract; assert it inherited budget_category_id from assignment",
    )
    contract_id = h.create_vendor_contract(
        planner_token=planner_token,
        wedding_id=wedding_id,
        vendor_profile_id=vendor_profile_id,
        total_amount=CONTRACT_TOTAL_AMOUNT,
        deposit_percentage=DEPOSIT_PERCENTAGE,
        service_date=wedding_date,
        service_location="Test Venue (BudgetProp Verifier)",
    )

    contract_doc = h.get_vendor_contract(
        planner_token=planner_token, contract_id=contract_id
    )
    contract_category = contract_doc.get("budget_category_id")
    if contract_category != budget_category_id:
        raise AssertionError(
            "FIX REGRESSION: contract.budget_category_id did not inherit "
            "from the assignment.\n"
            f"  expected: {budget_category_id!r} (the assignment's category)\n"
            f"  got:      {contract_category!r}\n"
            "Pre-fix this would always be None. Post-fix it should match "
            "the budget_category_id passed into assign_vendor_to_wedding "
            "earlier in this same driver run."
        )
    h.log.info(
        "  ✅ contract.budget_category_id inherited from assignment "
        f"({contract_category}) — primary fix assertion passes"
    )

    # ---- CREATE MILESTONE + RECORD PAYMENT ----------------------------------
    h.phase(
        "RECORD_PAYMENT",
        "create a milestone and record an offline payment; expect budget rollup",
    )
    due_date_iso = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    created_milestones = h.create_payment_milestones(
        planner_token=planner_token,
        contract_id=contract_id,
        milestones=[
            {
                "description": DEPOSIT_MILESTONE_DESCRIPTION,
                "amount": DEPOSIT_MILESTONE_AMOUNT,
                "due_date": due_date_iso,
            }
        ],
    )
    if not created_milestones:
        raise AssertionError("milestone create returned no documents")
    milestone = created_milestones[0]
    milestone_id = milestone.get("id") or milestone.get("_id")
    if not milestone_id:
        raise AssertionError(f"created milestone has no id field: {milestone!r}")

    # Read budget BEFORE payment so we can show the delta.
    budget_before = h.get_wedding_budget(
        planner_token=planner_token, wedding_id=wedding_id
    )
    spent_before = _category_actual_spent(budget_before, budget_category_id)
    h.log.info(f"  budget.actual_spent BEFORE payment: ${spent_before:.2f}")

    h.record_milestone_payment(
        planner_token=planner_token,
        milestone_id=str(milestone_id),
        amount=DEPOSIT_MILESTONE_AMOUNT,
        payment_method=PAYMENT_METHOD,
        notes="BudgetProp verifier — manual offline payment",
    )

    # ---- ASSERT BUDGET ROLLUP -----------------------------------------------
    h.phase("ASSERT_BUDGET_ROLLUP")
    budget_after = h.get_wedding_budget(
        planner_token=planner_token, wedding_id=wedding_id
    )
    spent_after = _category_actual_spent(budget_after, budget_category_id)
    h.log.info(f"  budget.actual_spent AFTER payment: ${spent_after:.2f}")

    expected_spent = spent_before + DEPOSIT_MILESTONE_AMOUNT
    # 0.5-cent tolerance for float rounding (matches record_payment guard).
    if abs(spent_after - expected_spent) > 0.005:
        raise AssertionError(
            "FIX REGRESSION: budget.actual_spent did not increment.\n"
            f"  before:   ${spent_before:.2f}\n"
            f"  payment:  ${DEPOSIT_MILESTONE_AMOUNT:.2f}\n"
            f"  expected: ${expected_spent:.2f}\n"
            f"  got:      ${spent_after:.2f}\n"
            "Pre-fix the rollup at vendor_service.record_payment :3129 was "
            "unreachable because the milestone inherited budget_category_id "
            "from a contract that always had None. Post-fix the rollup fires."
        )
    h.log.info(
        "  ✅ budget.actual_spent rose by the milestone payment amount "
        "— downstream fix assertion passes"
    )

    # ---- UI-2: budget tracker reflects the payment --------------------------
    h.checkpoint(
        "UI-2 (post-payment — budget page reflects the milestone payment)",
        [
            f"Open {h.config.frontend_url}/admin/budget?wedding_id={wedding_id}",
            f"     '{BUDGET_CATEGORY_NAME}' should now show:",
            f"     allocated ${BUDGET_CATEGORY_ALLOCATED:,.2f}",
            f"     spent     ${spent_after:,.2f}",
            f"     remaining ${BUDGET_CATEGORY_ALLOCATED - spent_after:,.2f}",
            "  Pre-fix this number stayed at $0.00 even after recording the payment.",
            f"On /admin/vendors/contracts/{contract_id} → Payments tab,",
            f"     the milestone '{DEPOSIT_MILESTONE_DESCRIPTION}' should show as",
            f"     paid (${DEPOSIT_MILESTONE_AMOUNT:.2f} via {PAYMENT_METHOD}).",
        ],
    )

    h.log.info("")
    h.log.info("✅ verify_vendor_contract_budget_propagation: all assertions pass")
    h.log.info(
        "Run testbed/cleanup_vendor_contract_budget_propagation_state.py to reset."
    )
    return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _category_actual_spent(wedding_budget_response: dict, category_id: str) -> float:
    """Pull `actual_spent` for a specific category out of the GET wedding
    budget response shape.

    The endpoint returns
        {wedding_id, summary, categories: [...], alerts: [...], last_updated}
    where each category has both `_id` and `id` (stringified).
    """
    categories = wedding_budget_response.get("categories") or []
    for cat in categories:
        cat_id = cat.get("id") or cat.get("_id")
        if str(cat_id) == str(category_id):
            return float(cat.get("actual_spent") or 0)
    raise AssertionError(
        f"category {category_id!r} not present in wedding budget response. "
        f"got: {[c.get('id') or c.get('_id') for c in categories]!r}"
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        import logging

        logging.getLogger("verify_vendor_contract_budget_propagation").error(
            f"Verification aborted: {exc}", exc_info=True
        )
        raise SystemExit(1)
