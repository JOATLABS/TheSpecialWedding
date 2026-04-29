#!/usr/bin/env python3
"""
Payment-Link Webhook → record_payment Routing — Live Verification
==================================================================

Verifies the fix at app/services/vendor_service.py:handle_payment_link_webhook.

Before the fix: on `checkout.session.completed`, the webhook updated the
linked milestone INLINE (status=PAID, paid_amount=link.amount). It bypassed
the canonical `record_payment` primitive and therefore missed:

  1. Idempotency guard — Stripe retries → milestone double-credited.
  2. Status lock — already-PAID milestone re-credited.
  3. Amount clamp — overpayment not validated.
  4. Transactional rollups to vendor_assignments.paid_amount,
     vendor_profiles.total_revenue, budget_categories.actual_spent —
     these never moved on payment-link-paid milestones.

After the fix: the webhook routes through `record_payment`, which runs all
three guards inside a Mongo transaction and rolls up to the three sibling
collections.

Strategy
--------
The verifier seeds product state through real planner endpoints (matching
verify_vendor_contract_budget_propagation), then drives the webhook by
calling `vendor_service.handle_payment_link_webhook` directly with a
synthesized stripe.Event-shaped dict. The payment_link doc is seeded
directly in Mongo (the planner's link-create path would call into Stripe;
the verifier's focus is the WEBHOOK→record_payment routing, not the
link-create side).

Cases
-----
  A. First-time payment for milestone-A with intent pi_test_a1.
     Expect milestone PAID, paid_amount == link.amount,
     vendor_assignments.paid_amount += amount,
     vendor_profiles.total_revenue += amount,
     budget_categories.actual_spent += amount.

  B. Replay of the same webhook (same intent pi_test_a1).
     Expect milestone STILL paid_amount == link.amount (NOT doubled),
     no further rollup increment on assignment / profile / category.
     This is the idempotency guard.

  C. A fresh contract / fresh milestone-C / fresh intent pi_test_c1.
     Expect the same end state as A — proves the webhook still works on
     the next contract after a successful prior run.

Pre-conditions
--------------
  - STRIPE_SECRET_KEY, MONGO_URI, ROOT_ADMIN_PASSWORD in .env
  - Backend on localhost:8000 (testbed/testbed.py up)
  - The webhook handler does NOT need Stripe to be reachable — it
    swallows StripeError on the receipt_url best-effort lookup. So fake
    pi_test_* ids are fine.

Cleanup pair: cleanup_payment_link_webhook_record_payment_routing_state.py

Usage
-----
    # In another terminal:
    python testbed/testbed.py up
    # Then:
    python testbed/verify_payment_link_webhook_record_payment_routing.py
    # When done:
    python testbed/cleanup_payment_link_webhook_record_payment_routing_state.py
    python testbed/testbed.py down
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bson import ObjectId

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from testbed.harness import Harness, PM_TOKEN_GOOD  # noqa: E402

# ---------------------------------------------------------------------------
# Driver constants — grep-visible so reruns are deterministic
# ---------------------------------------------------------------------------

PLANNER_EMAIL = "test_planner+plinkwebhook@thespecialwedding.io"
PLANNER_PASSWORD = "PLinkWebhookPlanner2026!"  # pragma: allowlist secret
PLANNER_FIRST = "PLink"
PLANNER_LAST = "WebhookPlanner"
PLANNER_COMPANY = "PLink-Webhook QA Co"

COUPLE_DISPLAY = "Riley & Sky (PLinkWebhook)"

VENDOR_BUSINESS_NAME = "Lens Co — PLinkWebhook Verifier"
VENDOR_EMAIL = "vendor+plinkwebhook@thespecialwedding.io"
VENDOR_CATEGORY = "photographer"

# Budget the rollup writes into.
BUDGET_CATEGORY_NAME = "Photography (PLinkWebhook Verifier)"
BUDGET_CATEGORY_ALLOCATED = 5000.00

# Contract A — used for cases A (first-time) and B (replay).
CONTRACT_A_TOTAL = 3000.00
CONTRACT_A_DEPOSIT_PCT = 50.0
MILESTONE_A_DESCRIPTION = "Milestone A (PLinkWebhook)"
MILESTONE_A_AMOUNT = 1500.00
MILESTONE_A_PAYMENT_INTENT = "pi_test_a1"
MILESTONE_A_CHECKOUT_SESSION = "cs_test_a1"
PAYMENT_LINK_A_STRIPE_PL_ID = "plink_test_a1"

# Contract C — used for case C (fresh contract after a successful prior run).
CONTRACT_C_TOTAL = 2400.00
CONTRACT_C_DEPOSIT_PCT = 50.0
MILESTONE_C_DESCRIPTION = "Milestone C (PLinkWebhook)"
MILESTONE_C_AMOUNT = 1200.00
MILESTONE_C_PAYMENT_INTENT = "pi_test_c1"
MILESTONE_C_CHECKOUT_SESSION = "cs_test_c1"
PAYMENT_LINK_C_STRIPE_PL_ID = "plink_test_c1"

# Contract D — used for case D (partial payment then top-up).
CONTRACT_D_TOTAL = 2000.00
CONTRACT_D_DEPOSIT_PCT = 50.0
MILESTONE_D_DESCRIPTION = "Milestone D (PLinkWebhook partial+topup)"
MILESTONE_D_AMOUNT = 1000.00
MILESTONE_D_PARTIAL_AMOUNT = 400.00
MILESTONE_D_TOPUP_AMOUNT = 600.00
MILESTONE_D_PARTIAL_PI = "pi_test_d1"
MILESTONE_D_TOPUP_PI = "pi_test_d2"
MILESTONE_D_PARTIAL_CS = "cs_test_d1"
MILESTONE_D_TOPUP_CS = "cs_test_d2"
PAYMENT_LINK_D_PARTIAL_STRIPE_PL_ID = "plink_test_d1"
PAYMENT_LINK_D_TOPUP_STRIPE_PL_ID = "plink_test_d2"

# Contract F — used for case F (milestone deleted between link and webhook).
CONTRACT_F_TOTAL = 1600.00
CONTRACT_F_DEPOSIT_PCT = 50.0
MILESTONE_F_DESCRIPTION = "Milestone F (PLinkWebhook missing-milestone)"
MILESTONE_F_AMOUNT = 800.00
MILESTONE_F_PAYMENT_INTENT = "pi_test_f1"
MILESTONE_F_CHECKOUT_SESSION = "cs_test_f1"
PAYMENT_LINK_F_STRIPE_PL_ID = "plink_test_f1"

# Contract G — used for case G (legacy data: payment_link.created_by is None).
CONTRACT_G_TOTAL = 1200.00
CONTRACT_G_DEPOSIT_PCT = 50.0
MILESTONE_G_DESCRIPTION = "Milestone G (PLinkWebhook missing-created_by)"
MILESTONE_G_AMOUNT = 600.00
MILESTONE_G_PAYMENT_INTENT = "pi_test_g1"
MILESTONE_G_CHECKOUT_SESSION = "cs_test_g1"
PAYMENT_LINK_G_STRIPE_PL_ID = "plink_test_g1"

WEDDING_DATE_OFFSET_DAYS = 180
PLAN_ID = os.getenv("PLINKWEBHOOK_PLAN_ID", "plan_signature")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_checkout_session_completed_event(
    *,
    payment_link_doc_id: str,
    stripe_payment_link_id: str,
    payment_intent: str,
    checkout_session_id: str,
    amount_cents: int,
) -> dict:
    """Construct a stripe.Event-shaped dict the webhook handler accepts.

    Mirror what Stripe sends on a real `checkout.session.completed`. The
    handler reads:
      data.object.metadata.payment_link_id  (our internal id, preferred)
      data.object.payment_link             (Stripe's PaymentLink id, fallback)
      data.object.id                        (checkout session id)
      data.object.payment_intent            (PI id)

    The fixture sets BOTH the metadata key (so the handler hits the fast
    path) and the stripe payment_link id (so the fallback path is also
    populated for parity with prod).
    """
    return {
        "id": f"evt_test_{checkout_session_id}",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": checkout_session_id,
                "object": "checkout.session",
                "payment_intent": payment_intent,
                "payment_link": stripe_payment_link_id,
                "payment_status": "paid",
                "amount_total": amount_cents,
                "currency": "usd",
                "metadata": {
                    "payment_link_id": payment_link_doc_id,
                },
            }
        },
    }


def _seed_payment_link_doc(
    h: Harness,
    *,
    milestone_id: str,
    wedding_id: str,
    vendor_profile_id: str,
    contract_id: str,
    amount: float,
    created_by: str,
    stripe_payment_link_id: str,
) -> str:
    """Insert a payment_link row directly via pymongo (synchronous).

    The verifier focuses on the WEBHOOK side — the link-create side is the
    planner's responsibility and lives in vendor_service.create_payment_link
    (which calls into Stripe). Seeding the doc here keeps the test focused.
    """
    now = datetime.now(timezone.utc)
    doc = {
        "wedding_id": wedding_id,
        "contract_id": contract_id,
        "milestone_id": milestone_id,
        "vendor_profile_id": vendor_profile_id,
        "payer_type": "couple",
        "payer_email": "couple+plinkwebhook@thespecialwedding.io",
        "payer_name": COUPLE_DISPLAY,
        "recipient_type": "vendor",
        "recipient_email": VENDOR_EMAIL,
        "recipient_name": VENDOR_BUSINESS_NAME,
        "amount": amount,
        "currency": "USD",
        "description": "PLinkWebhook verifier seed",
        "due_date": now + timedelta(days=14),
        "expires_at": now + timedelta(days=30),
        "stripe_payment_link_id": stripe_payment_link_id,
        "stripe_payment_link_url": f"https://checkout.stripe.com/c/test/{stripe_payment_link_id}",
        "status": "sent",
        "access_token": f"tok_plinkwebhook_{stripe_payment_link_id}",
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
        "reminder_sent_count": 0,
    }
    result = h.mongo["payment_links"].insert_one(doc)
    plink_id = str(result.inserted_id)
    h.log.info(
        f"  ✅ Seeded payment_link doc {plink_id} "
        f"(milestone={milestone_id}, amount=${amount:.2f}, "
        f"stripe_pl={stripe_payment_link_id})"
    )
    return plink_id


def _read_milestone(h: Harness, milestone_id: str) -> dict:
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
    doc = h.mongo["vendor_profiles"].find_one({"_id": ObjectId(vendor_profile_id)})
    if not doc:
        raise AssertionError(f"vendor_profile {vendor_profile_id} not found")
    return doc


def _read_budget_category(h: Harness, category_id: str) -> dict:
    doc = h.mongo["budget_categories"].find_one({"_id": ObjectId(category_id)})
    if not doc:
        raise AssertionError(f"budget_category {category_id} not found")
    return doc


def _read_payment_link_doc(h: Harness, payment_link_id: str) -> dict:
    doc = h.mongo["payment_links"].find_one({"_id": ObjectId(payment_link_id)})
    if not doc:
        raise AssertionError(f"payment_link {payment_link_id} not found")
    return doc


def _approx_eq(a: float, b: float, tol: float = 0.005) -> bool:
    return abs(float(a) - float(b)) <= tol


def _fire_webhook_sync(event: dict) -> dict:
    """Drive the webhook handler. Lazy-imports the service so the harness
    can finish env setup before Motor instantiates its event-loop-bound client.
    """
    # Late import — vendor_service binds to mongo.client at import time;
    # importing it before the harness loads .env can pin to the wrong DB.
    from app.services.vendor_service import vendor_service  # noqa: WPS433

    return asyncio.run(vendor_service.handle_payment_link_webhook(event))


# ---------------------------------------------------------------------------
# Phases
# ---------------------------------------------------------------------------


def main() -> int:
    h = Harness(driver_name="verify_payment_link_webhook_record_payment_routing")
    h.preflight()
    admin_token = h.get_admin_token()

    # ---- SEED ---------------------------------------------------------------
    h.phase(
        "SEED",
        "subscribe planner; build wedding + budget + vendor + assignment + contract A",
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
        venue="Test Venue (PLinkWebhook Verifier)",
    )

    budget_category_id = h.create_budget_category(
        planner_token=planner_token,
        wedding_id=wedding_id,
        name=BUDGET_CATEGORY_NAME,
        budgeted_amount=BUDGET_CATEGORY_ALLOCATED,
        description="PLinkWebhook verifier — actual_spent should rise on case A and case C.",
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
        service_notes="PLinkWebhook verifier — assignment row.",
    )

    contract_a_id = h.create_vendor_contract(
        planner_token=planner_token,
        wedding_id=wedding_id,
        vendor_profile_id=vendor_profile_id,
        total_amount=CONTRACT_A_TOTAL,
        deposit_percentage=CONTRACT_A_DEPOSIT_PCT,
        service_date=wedding_date,
        service_location="Test Venue (PLinkWebhook Verifier)",
    )

    due_date_iso = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    milestones_a = h.create_payment_milestones(
        planner_token=planner_token,
        contract_id=contract_a_id,
        milestones=[
            {
                "description": MILESTONE_A_DESCRIPTION,
                "amount": MILESTONE_A_AMOUNT,
                "due_date": due_date_iso,
            }
        ],
    )
    milestone_a_id = str(milestones_a[0].get("id") or milestones_a[0].get("_id"))

    payment_link_a_id = _seed_payment_link_doc(
        h,
        milestone_id=milestone_a_id,
        wedding_id=wedding_id,
        vendor_profile_id=vendor_profile_id,
        contract_id=contract_a_id,
        amount=MILESTONE_A_AMOUNT,
        created_by=PLANNER_EMAIL,
        stripe_payment_link_id=PAYMENT_LINK_A_STRIPE_PL_ID,
    )

    # Snapshot pre-state — the deltas after each case must equal the
    # webhook amount, NOT compounded across cases.
    profile_before = _read_vendor_profile(h, vendor_profile_id)
    revenue_before = float(profile_before.get("total_revenue") or 0)
    cat_before = _read_budget_category(h, budget_category_id)
    spent_before = float(cat_before.get("actual_spent") or 0)
    asn_before = _read_assignment(
        h, vendor_profile_id=vendor_profile_id, wedding_id=wedding_id
    )
    asn_paid_before = float(asn_before.get("paid_amount") or 0)
    h.log.info(
        f"  PRE-SEED ROLLUP: assignment.paid=${asn_paid_before:.2f}, "
        f"profile.total_revenue=${revenue_before:.2f}, "
        f"budget.actual_spent=${spent_before:.2f}"
    )

    h.checkpoint(
        "UI-1 (pre-webhook — milestone A pending, rollups all zero)",
        [
            f"Open {h.config.frontend_url}/admin/login as planner:",
            f"     {PLANNER_EMAIL} / {PLANNER_PASSWORD}",
            f"/admin/weddings/{wedding_id} should list {COUPLE_DISPLAY}.",
            f"/admin/budget?wedding_id={wedding_id} → '{BUDGET_CATEGORY_NAME}'",
            f"     allocated ${BUDGET_CATEGORY_ALLOCATED:,.2f}, actual_spent $0.00.",
            f"On /admin/vendors/contracts/{contract_a_id} → Payments tab,",
            f"     '{MILESTONE_A_DESCRIPTION}' should show as PENDING (paid_amount $0).",
        ],
    )

    # ---- CASE A — first-time webhook ---------------------------------------
    h.phase(
        "CASE_A",
        "fire checkout.session.completed for milestone A — expect record_payment to credit",
    )
    event_a = _build_checkout_session_completed_event(
        payment_link_doc_id=payment_link_a_id,
        stripe_payment_link_id=PAYMENT_LINK_A_STRIPE_PL_ID,
        payment_intent=MILESTONE_A_PAYMENT_INTENT,
        checkout_session_id=MILESTONE_A_CHECKOUT_SESSION,
        amount_cents=int(MILESTONE_A_AMOUNT * 100),
    )
    result_a = _fire_webhook_sync(event_a)
    if not result_a.get("processed"):
        raise AssertionError(
            f"webhook reported processed=False for case A: {result_a!r}"
        )
    h.log.info(f"  webhook returned: {result_a!r}")

    milestone_after_a = _read_milestone(h, milestone_a_id)
    if milestone_after_a.get("status") != "paid":
        raise AssertionError(
            f"CASE A FAIL: milestone status expected 'paid', "
            f"got {milestone_after_a.get('status')!r}"
        )
    if not _approx_eq(milestone_after_a.get("paid_amount", 0), MILESTONE_A_AMOUNT):
        raise AssertionError(
            f"CASE A FAIL: milestone.paid_amount expected ${MILESTONE_A_AMOUNT:.2f}, "
            f"got ${float(milestone_after_a.get('paid_amount', 0)):.2f}"
        )
    if milestone_after_a.get("stripe_payment_intent_id") != MILESTONE_A_PAYMENT_INTENT:
        raise AssertionError(
            f"CASE A FAIL: milestone.stripe_payment_intent_id expected "
            f"{MILESTONE_A_PAYMENT_INTENT!r}, "
            f"got {milestone_after_a.get('stripe_payment_intent_id')!r}. "
            "If this is missing, record_payment was NOT called from the webhook."
        )

    asn_after_a = _read_assignment(
        h, vendor_profile_id=vendor_profile_id, wedding_id=wedding_id
    )
    asn_paid_after_a = float(asn_after_a.get("paid_amount") or 0)
    if not _approx_eq(asn_paid_after_a, asn_paid_before + MILESTONE_A_AMOUNT):
        raise AssertionError(
            f"CASE A FAIL: vendor_assignments.paid_amount expected "
            f"${asn_paid_before + MILESTONE_A_AMOUNT:.2f}, got ${asn_paid_after_a:.2f}. "
            "Pre-fix the webhook never updated this field — confirm record_payment routing."
        )

    profile_after_a = _read_vendor_profile(h, vendor_profile_id)
    revenue_after_a = float(profile_after_a.get("total_revenue") or 0)
    if not _approx_eq(revenue_after_a, revenue_before + MILESTONE_A_AMOUNT):
        raise AssertionError(
            f"CASE A FAIL: vendor_profiles.total_revenue expected "
            f"${revenue_before + MILESTONE_A_AMOUNT:.2f}, got ${revenue_after_a:.2f}"
        )

    cat_after_a = _read_budget_category(h, budget_category_id)
    spent_after_a = float(cat_after_a.get("actual_spent") or 0)
    if not _approx_eq(spent_after_a, spent_before + MILESTONE_A_AMOUNT):
        raise AssertionError(
            f"CASE A FAIL: budget_categories.actual_spent expected "
            f"${spent_before + MILESTONE_A_AMOUNT:.2f}, got ${spent_after_a:.2f}"
        )

    plink_after_a = _read_payment_link_doc(h, payment_link_a_id)
    if plink_after_a.get("status") != "paid":
        raise AssertionError(
            f"CASE A FAIL: payment_links.status expected 'paid', "
            f"got {plink_after_a.get('status')!r}"
        )

    h.log.info("  ✅ CASE A — first-time webhook → milestone PAID + rollup increments")

    h.checkpoint(
        "UI-2 (post-CASE-A — milestone A paid, budget reflects payment)",
        [
            f"/admin/budget?wedding_id={wedding_id} → '{BUDGET_CATEGORY_NAME}'",
            f"     actual_spent should now be ${spent_after_a:,.2f} "
            f"(was ${spent_before:,.2f}).",
            f"/admin/vendors/contracts/{contract_a_id} → Payments tab,",
            f"     '{MILESTONE_A_DESCRIPTION}' should show as PAID via stripe.",
        ],
    )

    # ---- CASE B — replay (idempotency guard) -------------------------------
    h.phase(
        "CASE_B",
        "fire same checkout.session.completed again — expect idempotent NO-OP",
    )
    event_b = _build_checkout_session_completed_event(
        payment_link_doc_id=payment_link_a_id,
        stripe_payment_link_id=PAYMENT_LINK_A_STRIPE_PL_ID,
        payment_intent=MILESTONE_A_PAYMENT_INTENT,  # SAME intent as A
        checkout_session_id=MILESTONE_A_CHECKOUT_SESSION,
        amount_cents=int(MILESTONE_A_AMOUNT * 100),
    )
    result_b = _fire_webhook_sync(event_b)
    if not result_b.get("processed"):
        raise AssertionError(
            f"webhook reported processed=False for case B (idempotent replay): "
            f"{result_b!r}. The handler must swallow the guard rejection and "
            "return {'processed': True} so Stripe stops retrying."
        )
    h.log.info(f"  webhook returned: {result_b!r}")

    milestone_after_b = _read_milestone(h, milestone_a_id)
    if not _approx_eq(milestone_after_b.get("paid_amount", 0), MILESTONE_A_AMOUNT):
        raise AssertionError(
            f"CASE B FAIL — IDEMPOTENCY BROKEN: milestone.paid_amount expected "
            f"${MILESTONE_A_AMOUNT:.2f} (NOT doubled), "
            f"got ${float(milestone_after_b.get('paid_amount', 0)):.2f}. "
            "The webhook double-credited on retry. record_payment's intent "
            "guard or status lock should have caught this."
        )

    asn_after_b = _read_assignment(
        h, vendor_profile_id=vendor_profile_id, wedding_id=wedding_id
    )
    asn_paid_after_b = float(asn_after_b.get("paid_amount") or 0)
    if not _approx_eq(asn_paid_after_b, asn_paid_after_a):
        raise AssertionError(
            f"CASE B FAIL — IDEMPOTENCY BROKEN: vendor_assignments.paid_amount "
            f"expected ${asn_paid_after_a:.2f} (unchanged from CASE A), "
            f"got ${asn_paid_after_b:.2f}"
        )

    profile_after_b = _read_vendor_profile(h, vendor_profile_id)
    revenue_after_b = float(profile_after_b.get("total_revenue") or 0)
    if not _approx_eq(revenue_after_b, revenue_after_a):
        raise AssertionError(
            f"CASE B FAIL — IDEMPOTENCY BROKEN: vendor_profiles.total_revenue "
            f"expected ${revenue_after_a:.2f} (unchanged from CASE A), "
            f"got ${revenue_after_b:.2f}"
        )

    cat_after_b = _read_budget_category(h, budget_category_id)
    spent_after_b = float(cat_after_b.get("actual_spent") or 0)
    if not _approx_eq(spent_after_b, spent_after_a):
        raise AssertionError(
            f"CASE B FAIL — IDEMPOTENCY BROKEN: budget_categories.actual_spent "
            f"expected ${spent_after_a:.2f} (unchanged from CASE A), "
            f"got ${spent_after_b:.2f}"
        )

    h.log.info(
        "  ✅ CASE B — replay was idempotent (no double-credit, no double-rollup)"
    )

    # ---- CASE C — fresh contract / fresh milestone / fresh PI --------------
    h.phase(
        "CASE_C",
        "fresh contract + milestone — different PI; expect record_payment credit again",
    )

    contract_c_id = h.create_vendor_contract(
        planner_token=planner_token,
        wedding_id=wedding_id,
        vendor_profile_id=vendor_profile_id,
        total_amount=CONTRACT_C_TOTAL,
        deposit_percentage=CONTRACT_C_DEPOSIT_PCT,
        service_date=wedding_date,
        service_location="Test Venue (PLinkWebhook Verifier)",
    )

    milestones_c = h.create_payment_milestones(
        planner_token=planner_token,
        contract_id=contract_c_id,
        milestones=[
            {
                "description": MILESTONE_C_DESCRIPTION,
                "amount": MILESTONE_C_AMOUNT,
                "due_date": due_date_iso,
            }
        ],
    )
    milestone_c_id = str(milestones_c[0].get("id") or milestones_c[0].get("_id"))

    payment_link_c_id = _seed_payment_link_doc(
        h,
        milestone_id=milestone_c_id,
        wedding_id=wedding_id,
        vendor_profile_id=vendor_profile_id,
        contract_id=contract_c_id,
        amount=MILESTONE_C_AMOUNT,
        created_by=PLANNER_EMAIL,
        stripe_payment_link_id=PAYMENT_LINK_C_STRIPE_PL_ID,
    )

    event_c = _build_checkout_session_completed_event(
        payment_link_doc_id=payment_link_c_id,
        stripe_payment_link_id=PAYMENT_LINK_C_STRIPE_PL_ID,
        payment_intent=MILESTONE_C_PAYMENT_INTENT,
        checkout_session_id=MILESTONE_C_CHECKOUT_SESSION,
        amount_cents=int(MILESTONE_C_AMOUNT * 100),
    )
    result_c = _fire_webhook_sync(event_c)
    if not result_c.get("processed"):
        raise AssertionError(
            f"webhook reported processed=False for case C: {result_c!r}"
        )
    h.log.info(f"  webhook returned: {result_c!r}")

    milestone_after_c = _read_milestone(h, milestone_c_id)
    if milestone_after_c.get("status") != "paid":
        raise AssertionError(
            f"CASE C FAIL: milestone-C status expected 'paid', "
            f"got {milestone_after_c.get('status')!r}"
        )
    if not _approx_eq(milestone_after_c.get("paid_amount", 0), MILESTONE_C_AMOUNT):
        raise AssertionError(
            f"CASE C FAIL: milestone-C.paid_amount expected ${MILESTONE_C_AMOUNT:.2f}, "
            f"got ${float(milestone_after_c.get('paid_amount', 0)):.2f}"
        )
    if milestone_after_c.get("stripe_payment_intent_id") != MILESTONE_C_PAYMENT_INTENT:
        raise AssertionError(
            f"CASE C FAIL: milestone-C.stripe_payment_intent_id expected "
            f"{MILESTONE_C_PAYMENT_INTENT!r}, "
            f"got {milestone_after_c.get('stripe_payment_intent_id')!r}"
        )

    asn_after_c = _read_assignment(
        h, vendor_profile_id=vendor_profile_id, wedding_id=wedding_id
    )
    asn_paid_after_c = float(asn_after_c.get("paid_amount") or 0)
    if not _approx_eq(asn_paid_after_c, asn_paid_after_b + MILESTONE_C_AMOUNT):
        raise AssertionError(
            f"CASE C FAIL: vendor_assignments.paid_amount expected "
            f"${asn_paid_after_b + MILESTONE_C_AMOUNT:.2f} (CASE B + C amount), "
            f"got ${asn_paid_after_c:.2f}"
        )

    profile_after_c = _read_vendor_profile(h, vendor_profile_id)
    revenue_after_c = float(profile_after_c.get("total_revenue") or 0)
    if not _approx_eq(revenue_after_c, revenue_after_b + MILESTONE_C_AMOUNT):
        raise AssertionError(
            f"CASE C FAIL: vendor_profiles.total_revenue expected "
            f"${revenue_after_b + MILESTONE_C_AMOUNT:.2f}, got ${revenue_after_c:.2f}"
        )

    cat_after_c = _read_budget_category(h, budget_category_id)
    spent_after_c = float(cat_after_c.get("actual_spent") or 0)
    if not _approx_eq(spent_after_c, spent_after_b + MILESTONE_C_AMOUNT):
        raise AssertionError(
            f"CASE C FAIL: budget_categories.actual_spent expected "
            f"${spent_after_b + MILESTONE_C_AMOUNT:.2f}, got ${spent_after_c:.2f}"
        )

    h.log.info("  ✅ CASE C — fresh milestone webhook → fresh credit + fresh rollup")

    h.checkpoint(
        "UI-3 (post-CASE-C — both milestones paid, budget summed)",
        [
            f"/admin/budget?wedding_id={wedding_id} → '{BUDGET_CATEGORY_NAME}'",
            f"     actual_spent should now be ${spent_after_c:,.2f} "
            f"(${MILESTONE_A_AMOUNT:,.2f} + ${MILESTONE_C_AMOUNT:,.2f}).",
            f"/admin/vendors/contracts/{contract_c_id} → Payments tab,",
            f"     '{MILESTONE_C_DESCRIPTION}' should show as PAID via stripe.",
        ],
    )

    # ---- CASE D — partial then top-up --------------------------------------
    h.phase(
        "CASE_D",
        "two payment_links against the same milestone — partial then top-up; "
        "expect milestone partial → paid, rollups += full amount once",
    )

    contract_d_id = h.create_vendor_contract(
        planner_token=planner_token,
        wedding_id=wedding_id,
        vendor_profile_id=vendor_profile_id,
        total_amount=CONTRACT_D_TOTAL,
        deposit_percentage=CONTRACT_D_DEPOSIT_PCT,
        service_date=wedding_date,
        service_location="Test Venue (PLinkWebhook Verifier)",
    )

    milestones_d = h.create_payment_milestones(
        planner_token=planner_token,
        contract_id=contract_d_id,
        milestones=[
            {
                "description": MILESTONE_D_DESCRIPTION,
                "amount": MILESTONE_D_AMOUNT,
                "due_date": due_date_iso,
            }
        ],
    )
    milestone_d_id = str(milestones_d[0].get("id") or milestones_d[0].get("_id"))

    payment_link_d_partial_id = _seed_payment_link_doc(
        h,
        milestone_id=milestone_d_id,
        wedding_id=wedding_id,
        vendor_profile_id=vendor_profile_id,
        contract_id=contract_d_id,
        amount=MILESTONE_D_PARTIAL_AMOUNT,
        created_by=PLANNER_EMAIL,
        stripe_payment_link_id=PAYMENT_LINK_D_PARTIAL_STRIPE_PL_ID,
    )
    payment_link_d_topup_id = _seed_payment_link_doc(
        h,
        milestone_id=milestone_d_id,
        wedding_id=wedding_id,
        vendor_profile_id=vendor_profile_id,
        contract_id=contract_d_id,
        amount=MILESTONE_D_TOPUP_AMOUNT,
        created_by=PLANNER_EMAIL,
        stripe_payment_link_id=PAYMENT_LINK_D_TOPUP_STRIPE_PL_ID,
    )

    asn_paid_before_d = asn_paid_after_c
    revenue_before_d = revenue_after_c
    spent_before_d = spent_after_c

    # Fire the partial payment first.
    event_d_partial = _build_checkout_session_completed_event(
        payment_link_doc_id=payment_link_d_partial_id,
        stripe_payment_link_id=PAYMENT_LINK_D_PARTIAL_STRIPE_PL_ID,
        payment_intent=MILESTONE_D_PARTIAL_PI,
        checkout_session_id=MILESTONE_D_PARTIAL_CS,
        amount_cents=int(MILESTONE_D_PARTIAL_AMOUNT * 100),
    )
    result_d_partial = _fire_webhook_sync(event_d_partial)
    if not result_d_partial.get("processed"):
        raise AssertionError(
            f"CASE D FAIL: partial webhook reported processed=False: "
            f"{result_d_partial!r}"
        )
    h.log.info(f"  partial webhook returned: {result_d_partial!r}")

    milestone_after_d_partial = _read_milestone(h, milestone_d_id)
    if milestone_after_d_partial.get("status") != "partial":
        raise AssertionError(
            f"CASE D FAIL (partial): milestone status expected 'partial', "
            f"got {milestone_after_d_partial.get('status')!r}"
        )
    if not _approx_eq(
        milestone_after_d_partial.get("paid_amount", 0), MILESTONE_D_PARTIAL_AMOUNT
    ):
        raise AssertionError(
            f"CASE D FAIL (partial): paid_amount expected "
            f"${MILESTONE_D_PARTIAL_AMOUNT:.2f}, "
            f"got ${float(milestone_after_d_partial.get('paid_amount', 0)):.2f}"
        )

    asn_after_d_partial = _read_assignment(
        h, vendor_profile_id=vendor_profile_id, wedding_id=wedding_id
    )
    asn_paid_after_d_partial = float(asn_after_d_partial.get("paid_amount") or 0)
    if not _approx_eq(
        asn_paid_after_d_partial, asn_paid_before_d + MILESTONE_D_PARTIAL_AMOUNT
    ):
        raise AssertionError(
            f"CASE D FAIL (partial): assignment.paid_amount expected "
            f"${asn_paid_before_d + MILESTONE_D_PARTIAL_AMOUNT:.2f}, "
            f"got ${asn_paid_after_d_partial:.2f}"
        )

    # Now fire the top-up.
    event_d_topup = _build_checkout_session_completed_event(
        payment_link_doc_id=payment_link_d_topup_id,
        stripe_payment_link_id=PAYMENT_LINK_D_TOPUP_STRIPE_PL_ID,
        payment_intent=MILESTONE_D_TOPUP_PI,
        checkout_session_id=MILESTONE_D_TOPUP_CS,
        amount_cents=int(MILESTONE_D_TOPUP_AMOUNT * 100),
    )
    result_d_topup = _fire_webhook_sync(event_d_topup)
    if not result_d_topup.get("processed"):
        raise AssertionError(
            f"CASE D FAIL: top-up webhook reported processed=False: {result_d_topup!r}"
        )
    h.log.info(f"  top-up webhook returned: {result_d_topup!r}")

    milestone_after_d_topup = _read_milestone(h, milestone_d_id)
    if milestone_after_d_topup.get("status") != "paid":
        raise AssertionError(
            f"CASE D FAIL (top-up): milestone status expected 'paid', "
            f"got {milestone_after_d_topup.get('status')!r}"
        )
    if not _approx_eq(
        milestone_after_d_topup.get("paid_amount", 0), MILESTONE_D_AMOUNT
    ):
        raise AssertionError(
            f"CASE D FAIL (top-up): paid_amount expected "
            f"${MILESTONE_D_AMOUNT:.2f}, "
            f"got ${float(milestone_after_d_topup.get('paid_amount', 0)):.2f}"
        )

    asn_after_d_topup = _read_assignment(
        h, vendor_profile_id=vendor_profile_id, wedding_id=wedding_id
    )
    asn_paid_after_d_topup = float(asn_after_d_topup.get("paid_amount") or 0)
    if not _approx_eq(asn_paid_after_d_topup, asn_paid_before_d + MILESTONE_D_AMOUNT):
        raise AssertionError(
            f"CASE D FAIL (top-up): assignment.paid_amount expected "
            f"${asn_paid_before_d + MILESTONE_D_AMOUNT:.2f}, "
            f"got ${asn_paid_after_d_topup:.2f}"
        )

    profile_after_d = _read_vendor_profile(h, vendor_profile_id)
    revenue_after_d = float(profile_after_d.get("total_revenue") or 0)
    if not _approx_eq(revenue_after_d, revenue_before_d + MILESTONE_D_AMOUNT):
        raise AssertionError(
            f"CASE D FAIL (top-up): vendor_profiles.total_revenue expected "
            f"${revenue_before_d + MILESTONE_D_AMOUNT:.2f}, "
            f"got ${revenue_after_d:.2f}"
        )

    cat_after_d = _read_budget_category(h, budget_category_id)
    spent_after_d = float(cat_after_d.get("actual_spent") or 0)
    if not _approx_eq(spent_after_d, spent_before_d + MILESTONE_D_AMOUNT):
        raise AssertionError(
            f"CASE D FAIL (top-up): budget_categories.actual_spent expected "
            f"${spent_before_d + MILESTONE_D_AMOUNT:.2f}, "
            f"got ${spent_after_d:.2f}"
        )

    # Both link docs should be PAID now.
    plink_d_partial_after = _read_payment_link_doc(h, payment_link_d_partial_id)
    if plink_d_partial_after.get("status") != "paid":
        raise AssertionError(
            f"CASE D FAIL: partial payment_link status expected 'paid', "
            f"got {plink_d_partial_after.get('status')!r}"
        )
    plink_d_topup_after = _read_payment_link_doc(h, payment_link_d_topup_id)
    if plink_d_topup_after.get("status") != "paid":
        raise AssertionError(
            f"CASE D FAIL: top-up payment_link status expected 'paid', "
            f"got {plink_d_topup_after.get('status')!r}"
        )

    h.log.info(
        "  ✅ CASE D — partial then top-up → milestone PAID, rollups += full amount"
    )

    h.checkpoint(
        "UI-4 (post-CASE-D — partial+topup milestone fully paid)",
        [
            f"/admin/vendors/contracts/{contract_d_id} → Payments tab,",
            f"     '{MILESTONE_D_DESCRIPTION}' shows PAID, paid_amount "
            f"${MILESTONE_D_AMOUNT:,.2f}.",
            f"/admin/budget?wedding_id={wedding_id} → '{BUDGET_CATEGORY_NAME}'",
            f"     actual_spent should now include +${MILESTONE_D_AMOUNT:,.2f} "
            f"from CASE D.",
        ],
    )

    # ---- CASE F — milestone deleted between link create and webhook fire ---
    h.phase(
        "CASE_F",
        "delete milestone after link is seeded; fire webhook; expect ERROR "
        "log + processed=True + payment_link NOT marked PAID",
    )

    contract_f_id = h.create_vendor_contract(
        planner_token=planner_token,
        wedding_id=wedding_id,
        vendor_profile_id=vendor_profile_id,
        total_amount=CONTRACT_F_TOTAL,
        deposit_percentage=CONTRACT_F_DEPOSIT_PCT,
        service_date=wedding_date,
        service_location="Test Venue (PLinkWebhook Verifier)",
    )

    milestones_f = h.create_payment_milestones(
        planner_token=planner_token,
        contract_id=contract_f_id,
        milestones=[
            {
                "description": MILESTONE_F_DESCRIPTION,
                "amount": MILESTONE_F_AMOUNT,
                "due_date": due_date_iso,
            }
        ],
    )
    milestone_f_id = str(milestones_f[0].get("id") or milestones_f[0].get("_id"))

    payment_link_f_id = _seed_payment_link_doc(
        h,
        milestone_id=milestone_f_id,
        wedding_id=wedding_id,
        vendor_profile_id=vendor_profile_id,
        contract_id=contract_f_id,
        amount=MILESTONE_F_AMOUNT,
        created_by=PLANNER_EMAIL,
        stripe_payment_link_id=PAYMENT_LINK_F_STRIPE_PL_ID,
    )

    # Snapshot rollups so we can assert no movement.
    asn_before_f = float(
        _read_assignment(
            h, vendor_profile_id=vendor_profile_id, wedding_id=wedding_id
        ).get("paid_amount")
        or 0
    )
    revenue_before_f = float(
        _read_vendor_profile(h, vendor_profile_id).get("total_revenue") or 0
    )
    spent_before_f = float(
        _read_budget_category(h, budget_category_id).get("actual_spent") or 0
    )

    # Delete the milestone OUT FROM UNDER the link.
    h.mongo["vendor_payment_milestones"].delete_one({"_id": ObjectId(milestone_f_id)})
    h.log.info(f"  Deleted milestone {milestone_f_id} directly to simulate orphan link")

    event_f = _build_checkout_session_completed_event(
        payment_link_doc_id=payment_link_f_id,
        stripe_payment_link_id=PAYMENT_LINK_F_STRIPE_PL_ID,
        payment_intent=MILESTONE_F_PAYMENT_INTENT,
        checkout_session_id=MILESTONE_F_CHECKOUT_SESSION,
        amount_cents=int(MILESTONE_F_AMOUNT * 100),
    )
    result_f = _fire_webhook_sync(event_f)
    if not result_f.get("processed"):
        raise AssertionError(
            f"CASE F FAIL: webhook reported processed=False; expected True so "
            f"Stripe stops retrying (orphan link → ERROR + ack). Got: {result_f!r}"
        )
    h.log.info(f"  webhook returned: {result_f!r}")

    plink_f_after = _read_payment_link_doc(h, payment_link_f_id)
    if plink_f_after.get("status") == "paid":
        raise AssertionError(
            "CASE F FAIL: payment_link status was set to 'paid' even though "
            "record_payment failed (milestone missing). The fix should keep "
            "the link in its prior status so retries can complete cleanly "
            "if the milestone reappears, OR the orphan log is ops's signal."
        )

    asn_after_f = float(
        _read_assignment(
            h, vendor_profile_id=vendor_profile_id, wedding_id=wedding_id
        ).get("paid_amount")
        or 0
    )
    if not _approx_eq(asn_after_f, asn_before_f):
        raise AssertionError(
            f"CASE F FAIL: assignment.paid_amount moved despite missing milestone "
            f"(before=${asn_before_f:.2f}, after=${asn_after_f:.2f})"
        )
    revenue_after_f = float(
        _read_vendor_profile(h, vendor_profile_id).get("total_revenue") or 0
    )
    if not _approx_eq(revenue_after_f, revenue_before_f):
        raise AssertionError(
            f"CASE F FAIL: vendor_profiles.total_revenue moved despite missing "
            f"milestone (before=${revenue_before_f:.2f}, after=${revenue_after_f:.2f})"
        )
    spent_after_f = float(
        _read_budget_category(h, budget_category_id).get("actual_spent") or 0
    )
    if not _approx_eq(spent_after_f, spent_before_f):
        raise AssertionError(
            f"CASE F FAIL: budget_categories.actual_spent moved despite missing "
            f"milestone (before=${spent_before_f:.2f}, after=${spent_after_f:.2f})"
        )

    h.log.info(
        "  ✅ CASE F — orphan link → processed=True, link NOT marked PAID, "
        "no rollups moved"
    )

    # ---- CASE G — payment_link.created_by is None (legacy data simulation) -
    h.phase(
        "CASE_G",
        "seed payment_link with created_by=None; fire webhook; expect "
        "ERROR log 'missing created_by' + processed=True + milestone untouched",
    )

    contract_g_id = h.create_vendor_contract(
        planner_token=planner_token,
        wedding_id=wedding_id,
        vendor_profile_id=vendor_profile_id,
        total_amount=CONTRACT_G_TOTAL,
        deposit_percentage=CONTRACT_G_DEPOSIT_PCT,
        service_date=wedding_date,
        service_location="Test Venue (PLinkWebhook Verifier)",
    )

    milestones_g = h.create_payment_milestones(
        planner_token=planner_token,
        contract_id=contract_g_id,
        milestones=[
            {
                "description": MILESTONE_G_DESCRIPTION,
                "amount": MILESTONE_G_AMOUNT,
                "due_date": due_date_iso,
            }
        ],
    )
    milestone_g_id = str(milestones_g[0].get("id") or milestones_g[0].get("_id"))

    # Seed a link with NULL created_by — this simulates legacy rows from
    # before created_by was made required on the model.
    payment_link_g_id = _seed_payment_link_doc(
        h,
        milestone_id=milestone_g_id,
        wedding_id=wedding_id,
        vendor_profile_id=vendor_profile_id,
        contract_id=contract_g_id,
        amount=MILESTONE_G_AMOUNT,
        created_by=PLANNER_EMAIL,  # seed with valid value first
        stripe_payment_link_id=PAYMENT_LINK_G_STRIPE_PL_ID,
    )
    h.mongo["payment_links"].update_one(
        {"_id": ObjectId(payment_link_g_id)},
        {"$set": {"created_by": None}},
    )
    h.log.info(
        f"  Forced payment_link {payment_link_g_id} created_by=None to "
        "simulate legacy data"
    )

    # Snapshot pre-state.
    milestone_before_g = _read_milestone(h, milestone_g_id)
    paid_amount_before_g = float(milestone_before_g.get("paid_amount") or 0)
    asn_before_g = float(
        _read_assignment(
            h, vendor_profile_id=vendor_profile_id, wedding_id=wedding_id
        ).get("paid_amount")
        or 0
    )
    revenue_before_g = float(
        _read_vendor_profile(h, vendor_profile_id).get("total_revenue") or 0
    )
    spent_before_g = float(
        _read_budget_category(h, budget_category_id).get("actual_spent") or 0
    )

    event_g = _build_checkout_session_completed_event(
        payment_link_doc_id=payment_link_g_id,
        stripe_payment_link_id=PAYMENT_LINK_G_STRIPE_PL_ID,
        payment_intent=MILESTONE_G_PAYMENT_INTENT,
        checkout_session_id=MILESTONE_G_CHECKOUT_SESSION,
        amount_cents=int(MILESTONE_G_AMOUNT * 100),
    )
    result_g = _fire_webhook_sync(event_g)
    if not result_g.get("processed"):
        raise AssertionError(
            f"CASE G FAIL: webhook reported processed=False; expected True. "
            f"Got: {result_g!r}"
        )
    h.log.info(f"  webhook returned: {result_g!r}")

    # Milestone untouched.
    milestone_after_g = _read_milestone(h, milestone_g_id)
    if not _approx_eq(milestone_after_g.get("paid_amount", 0), paid_amount_before_g):
        raise AssertionError(
            f"CASE G FAIL: milestone.paid_amount moved despite missing "
            f"created_by (before=${paid_amount_before_g:.2f}, "
            f"after=${float(milestone_after_g.get('paid_amount', 0)):.2f})"
        )
    if milestone_after_g.get("status") == "paid":
        raise AssertionError(
            "CASE G FAIL: milestone status was set to 'paid' even though "
            "record_payment was never called (missing created_by)."
        )

    # Rollups untouched.
    asn_after_g = float(
        _read_assignment(
            h, vendor_profile_id=vendor_profile_id, wedding_id=wedding_id
        ).get("paid_amount")
        or 0
    )
    if not _approx_eq(asn_after_g, asn_before_g):
        raise AssertionError(
            f"CASE G FAIL: assignment.paid_amount moved (before=${asn_before_g:.2f}, "
            f"after=${asn_after_g:.2f})"
        )
    revenue_after_g = float(
        _read_vendor_profile(h, vendor_profile_id).get("total_revenue") or 0
    )
    if not _approx_eq(revenue_after_g, revenue_before_g):
        raise AssertionError(
            f"CASE G FAIL: vendor_profiles.total_revenue moved "
            f"(before=${revenue_before_g:.2f}, after=${revenue_after_g:.2f})"
        )
    spent_after_g = float(
        _read_budget_category(h, budget_category_id).get("actual_spent") or 0
    )
    if not _approx_eq(spent_after_g, spent_before_g):
        raise AssertionError(
            f"CASE G FAIL: budget_categories.actual_spent moved "
            f"(before=${spent_before_g:.2f}, after=${spent_after_g:.2f})"
        )

    # The link doc IS expected to be marked PAID per the documented choice in
    # the handler: planner needs the link doc to reflect what Stripe collected
    # even when the rollup couldn't run. Ops finds the orphan via the ERROR log.
    plink_g_after = _read_payment_link_doc(h, payment_link_g_id)
    if plink_g_after.get("status") != "paid":
        raise AssertionError(
            "CASE G FAIL: payment_link doc was NOT marked PAID. The handler's "
            "documented choice for missing-created_by is to still update the "
            "link doc so the planner sees what Stripe collected; ops finds "
            "the orphan via the 'missing created_by' ERROR log."
        )

    h.log.info(
        "  ✅ CASE G — missing created_by → milestone untouched, rollups "
        "untouched, link doc updated to PAID per benign-update path"
    )

    h.log.info("")
    h.log.info(
        "✅ verify_payment_link_webhook_record_payment_routing: "
        "all assertions pass (CASE A + B + C + D + F + G)"
    )
    h.log.info(
        "Run testbed/cleanup_payment_link_webhook_record_payment_routing_state.py to reset."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        import logging

        logging.getLogger("verify_payment_link_webhook_record_payment_routing").error(
            f"Verification aborted: {exc}", exc_info=True
        )
        raise SystemExit(1)
