#!/usr/bin/env python3
"""
Planner ↔ Couple Package + Contract Flow — Live Verification
==============================================================

Verifies the canonical planner→couple billing flow end-to-end through real
production code paths — no Mongo writes for product state, all subscription
and contract state arrives through the actual API + webhook flows.

The flow:

  1. Planner subscribes to the SaaS (real Stripe Subscription, no clock).
  2. Planner connects Stripe Express (real onboarding).
  3. Planner creates a wedding (`POST /admin/weddings`).
  4. Planner invites the couple (`POST /admin/couple-portal/invite`),
     which gives the couple a setup_link for portal access.
  5. Planner builds a package (`POST /admin/packages`).
  6. Planner sends the package to the couple
     (`POST /admin/packages/{id}/send`), creating the public-token
     contract through `package_service.send_to_couple`.
  7. Couple captures payment method via Stripe SetupIntent (real Stripe).
  8. Couple signs the contract (`POST /public/contracts/{token}/sign`)
     → backend auto-charges the deposit through Stripe with
     `transfer_data.destination = planner.stripe_connect_id`.
  9. Backend assertions on `scheduled_payments` + Stripe PaymentIntent.
  10. UI checkpoints on `/admin/money` (planner) and the couple portal.

All subscription / customer / package / contract state is created by
hitting the real product endpoints. No `subscription_status` flip in
Mongo, no `user_subscriptions` upsert — the subscription is a real
`stripe.Subscription` and the webhook handler flips Mongo state in the
production code path.

Test-harness conventions retained per existing testbed drivers:
- `email_verified` is flipped directly in Mongo because there's no
  test-mode email round-trip endpoint.
- Wedding / package / contract assertions read Mongo for verification
  (READS only — never WRITES product state).

Accounts (plus-variant; base accounts never touched)
----------------------------------------------------
  Planner : test_planner+contractflow@thespecialwedding.io
  Couple  : test_couple+contractflow@thespecialwedding.io

Pre-conditions
--------------
  - `RESEND_API_KEY` set in .env (or send_to_couple rolls back the contract)
  - `STRIPE_SECRET_KEY`, `MONGO_URI`, `ROOT_ADMIN_PASSWORD` in .env
  - Backend on localhost:8000, frontend on localhost:3000
  - Stripe webhook listener forwarding: `stripe listen --forward-to localhost:8000/stripe/webhook`
  - Stripe Connect signed up at https://dashboard.stripe.com/test/connect

Cleanup pair: cleanup_planner_couple_contract_flow_state.py

Usage
-----
    python testbed/verify_planner_couple_contract_flow.py
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import stripe

from testbed.harness import Harness, PM_TOKEN_GOOD

# ---------------------------------------------------------------------------
# Driver constants — grep-visible so reruns are deterministic
# ---------------------------------------------------------------------------

PLANNER_EMAIL = "test_planner+contractflow@thespecialwedding.io"
PLANNER_PASSWORD = "ContractFlowPlanner2026!"  # pragma: allowlist secret
PLANNER_FIRST = "Contract"
PLANNER_LAST = "FlowPlanner"
PLANNER_COMPANY = "ContractFlow QA Co"

COUPLE_EMAIL = "test_couple+contractflow@thespecialwedding.io"
COUPLE_PARTNER1 = "Alex Davis"
COUPLE_PARTNER2 = "Jamie Rivera"
COUPLE_DISPLAY = f"{COUPLE_PARTNER1} & {COUPLE_PARTNER2}"

PLAN_ID = os.getenv("CONTRACTFLOW_PLAN_ID", "plan_signature")

# Package financials. Deposit is on-signing; milestone is days_after_signing
# (not driven in this test — would need a clock).
DEPOSIT_AMOUNT = 100.0
MILESTONE_AMOUNT = 250.0
TOTAL_AMOUNT = DEPOSIT_AMOUNT + MILESTONE_AMOUNT
CURRENCY = "usd"

WEDDING_DATE_OFFSET_DAYS = 180
PACKAGE_NAME = "Test Wedding Package — Contract Flow Verifier"


# ---------------------------------------------------------------------------
# Phases
# ---------------------------------------------------------------------------


def main() -> int:
    # The harness loads .env at Harness() construction. RESEND_API_KEY is
    # validated by harness.send_package_to_couple at the moment it's needed
    # — no driver-side precheck required.
    h = Harness(driver_name="verify_planner_couple_contract_flow")
    h.preflight()
    admin_token = h.get_admin_token()

    # ---- SEED ---------------------------------------------------------------
    h.phase("SEED", "subscribe planner via real Stripe; build wedding+package+contract")

    # 1. Subscribe the planner via real Stripe Subscription (no clock — this
    #    test doesn't drive subscription state through time).
    seed = h.seed_planner(
        admin_token=admin_token,
        email=PLANNER_EMAIL,
        password=PLANNER_PASSWORD,
        plan_id=PLAN_ID,
        first_name=PLANNER_FIRST,
        last_name=PLANNER_LAST,
        company_name=PLANNER_COMPANY,
        pm_token=PM_TOKEN_GOOD,
    )

    # 2. Stripe Connect Express. Single harness call: create-if-missing,
    #    drop into hosted onboarding if charges aren't enabled, poll
    #    until ready.
    connect_id = h.ensure_connect_ready(
        user_id=seed.user_id,
        email=PLANNER_EMAIL,
        return_url=f"{h.config.frontend_url}/admin/planner/billing",
    )

    # 3. Wedding via API.
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
        guest_count=50,
        venue="Test Venue (verifier seed)",
    )

    # 4. Invite couple → real production code path that creates the
    #    couple-portal invite and returns a setup_link the couple uses
    #    to complete portal account setup.
    invite_resp = h.invite_couple_to_wedding(
        planner_token=planner_token,
        wedding_id=wedding_id,
        email=COUPLE_EMAIL,
        partner1_name=COUPLE_PARTNER1,
        partner2_name=COUPLE_PARTNER2,
    )
    couple_setup_link = invite_resp.get("setup_link")

    # 5. Build the package.
    package_id = h.create_package(
        planner_token=planner_token,
        name=PACKAGE_NAME,
        total_amount=TOTAL_AMOUNT,
        currency=CURRENCY,
        services=[
            {
                "name": "Wedding planning",
                "description": "Full planning support",
                "included": True,
            },
            {
                "name": "Day-of coordination",
                "description": "On-site coordination on the wedding day",
                "included": True,
            },
        ],
        payment_schedule=[
            {"name": "Deposit", "trigger": "on_signing", "amount": DEPOSIT_AMOUNT},
            {
                "name": "Milestone payment",
                "trigger": "days_after_signing",
                "days_after": 7,
                "amount": MILESTONE_AMOUNT,
            },
        ],
        cancellation_policy="Standard 50% deposit non-refundable after sign.",
    )

    # 6. Send package → real production path → public contract token.
    contract_token = h.send_package_to_couple(
        planner_token=planner_token,
        package_id=package_id,
        wedding_id=wedding_id,
        couple_email=COUPLE_EMAIL,
        partner1_name=COUPLE_PARTNER1,
        partner2_name=COUPLE_PARTNER2,
    )

    # ---- UI-1: pre-sign world-state check -----------------------------------
    h.checkpoint(
        "UI-1 (pre-sign — package + contract exist, schedule rows do NOT)",
        [
            f"Open {h.config.frontend_url}/admin/login as planner:",
            f"     {PLANNER_EMAIL} / {PLANNER_PASSWORD}",
            "/admin/weddings should list one wedding for "
            f"{COUPLE_DISPLAY} (date {wedding_date}).",
            f"/admin/weddings/{wedding_id} → Couple tab → couple {COUPLE_EMAIL}",
            "  is shown as Invited (not yet linked).",
            f"/admin/packages should list '{PACKAGE_NAME}' as Active with",
            "  '1 contracts' counter (incremented by send_to_couple).",
            "/admin/money → Incoming should NOT yet show payment rows for",
            "  this contract — schedule rows are inserted at sign time.",
            f"Public contract URL signable at: {h.config.frontend_url}/contracts/{contract_token}",
        ]
        + (
            [f"Couple setup link (optional manual setup): {couple_setup_link}"]
            if couple_setup_link
            else []
        ),
    )

    # ---- SIGN ---------------------------------------------------------------
    h.phase("SIGN")
    si = h.init_contract_setup_intent(contract_token)
    pm = h.confirm_setup_intent_with_test_pm(si["setup_intent_id"])
    h.sign_contract(
        contract_token=contract_token,
        signature_name=COUPLE_PARTNER1,
        customer_id=si["customer_id"],
        payment_method_id=pm["payment_method_id"],
        setup_intent_id=si["setup_intent_id"],
        last4=pm["last4"],
        brand=pm["brand"],
    )
    h.wait_for_webhooks()

    # ---- ASSERT_DEPOSIT -----------------------------------------------------
    h.phase("ASSERT_DEPOSIT")
    contract_doc = h.mongo["contracts"].find_one({"token": contract_token})
    if not contract_doc:
        raise AssertionError("Contract row missing after sign")

    payments = list(
        h.mongo["scheduled_payments"]
        .find({"contract_id": str(contract_doc["_id"])})
        .sort("due_date", 1)
    )
    if len(payments) != 2:
        raise AssertionError(
            f"Expected 2 scheduled_payments rows (deposit + milestone), "
            f"got {len(payments)}"
        )
    deposit, milestone = payments

    if deposit.get("name") != "Deposit":
        raise AssertionError(
            f"deposit.name expected 'Deposit', got {deposit.get('name')!r}"
        )
    if deposit.get("status") != "succeeded":
        raise AssertionError(
            f"deposit.status expected 'succeeded', got {deposit.get('status')!r}"
        )
    if not deposit.get("stripe_payment_intent_id"):
        raise AssertionError("deposit.stripe_payment_intent_id missing")
    if float(deposit.get("amount", 0)) != DEPOSIT_AMOUNT:
        raise AssertionError(
            f"deposit.amount expected {DEPOSIT_AMOUNT}, got {deposit.get('amount')}"
        )
    h.log.info("  ✅ deposit row asserts pass")

    if milestone.get("name") != "Milestone payment":
        raise AssertionError(f"milestone.name unexpected: {milestone.get('name')!r}")
    if milestone.get("status") != "scheduled":
        raise AssertionError(
            f"milestone.status expected 'scheduled', got {milestone.get('status')!r}"
        )
    if float(milestone.get("amount", 0)) != MILESTONE_AMOUNT:
        raise AssertionError(
            f"milestone.amount expected {MILESTONE_AMOUNT}, got {milestone.get('amount')}"
        )
    h.log.info("  ✅ milestone row asserts pass")

    pi = stripe.PaymentIntent.retrieve(deposit["stripe_payment_intent_id"])
    transfer_dest = (pi.get("transfer_data") or {}).get("destination")
    if transfer_dest != connect_id:
        raise AssertionError(
            f"deposit.transfer_data.destination expected {connect_id!r}, "
            f"got {transfer_dest!r}"
        )
    if pi.get("amount_received") != int(DEPOSIT_AMOUNT * 100):
        raise AssertionError(
            f"deposit Stripe amount_received expected {int(DEPOSIT_AMOUNT * 100)}, "
            f"got {pi.get('amount_received')}"
        )
    h.log.info("  ✅ Stripe PaymentIntent destination + amount asserts pass")

    # ---- UI-2: couple-side reflects the deposit -----------------------------
    h.checkpoint(
        "UI-2 (couple-side reflects the deposit)",
        [
            "The couple was sent a contract email with the public contract URL:",
            f"     {h.config.frontend_url}/contracts/{contract_token}",
            "Open it (private window) and confirm the Payments / Schedule view shows:",
            f"     Total = ${TOTAL_AMOUNT:.2f}",
            f"     Paid  = ${DEPOSIT_AMOUNT:.2f}",
            f"     Remaining = ${MILESTONE_AMOUNT:.2f}",
            "The Deposit row reads as 'Paid'.",
            "The Milestone row reads as 'Scheduled' / 'Pending' with a due date",
            "  about 7 days from today.",
        ],
    )

    # ---- UI-3: planner Money → Incoming reflects the deposit ---------------
    h.checkpoint(
        "UI-3 (planner Money → Incoming reflects the deposit)",
        [
            f"Reload {h.config.frontend_url}/admin/money → Incoming tab.",
            f"A row for {COUPLE_DISPLAY} 'Deposit' appears with",
            f"  status=Succeeded and amount ${DEPOSIT_AMOUNT:.2f}.",
            f"A row for {COUPLE_DISPLAY} 'Milestone payment' appears with",
            f"  status=Scheduled and amount ${MILESTONE_AMOUNT:.2f}.",
            "The 'Card' column shows a Visa ending in 4242.",
            "Summary cards at the top reflect the new pending/incoming totals.",
        ],
    )

    h.banner("✅ All checkpoints passed.")
    h.log.info(
        "Run testbed/cleanup_planner_couple_contract_flow_state.py to reset "
        "for the next run."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
