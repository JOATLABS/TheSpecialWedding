#!/usr/bin/env python3
"""
Planner ↔ Couple Package + Contract Flow — Live Verification
==============================================================

Purpose
-------
Verify the canonical planner→couple billing flow end-to-end through the
real production code paths:

  1. Planner creates a wedding (POST /admin/weddings).
  2. Planner builds a package with a payment schedule (POST /packages).
  3. Planner sends the package to the couple (POST /admin/packages/{id}/send),
     which invokes `package_service.send_package_to_couple` and produces
     a contract row via the production code path — no synthetic Mongo
     seeds.
  4. Couple opens the public contract URL, captures a payment method via
     Stripe SetupIntent, and signs (POST /public/contracts/{token}/sign).
  5. Backend auto-charges the deposit through Stripe with
     `transfer_data.destination` = the planner's connected account.
  6. /admin/money "Incoming" reflects the new state on the planner side;
     /couple/dashboard "Payments" reflects on the couple side.

This replaces the earlier synthetic-seed approach. A previous version of
this driver inserted a contract row directly into Mongo, bypassing
`send_package_to_couple`. That version "worked" for testing the deposit
charge logic but did not exercise the production flow — no package
existed, no wedding existed, the package counter was never incremented,
the contract email was never sent. Per the explicit feedback:

  "How is the couple going to pay for a package that doesn't exist
   for a wedding that doesn't exist?"

Two-layer verification per CLAUDE.md:

- Backend asserts: scheduled_payments rows created, deposit row flips to
  `succeeded`, Stripe PaymentIntent has the right destination account.
- UI checkpoints: planner Money → Incoming, couple-portal Payments view.

Accounts (plus-variant; base accounts never touched)
----------------------------------------------------
  Planner : test_planner+contractflow@thespecialwedding.io
  Couple  : test_couple+contractflow@thespecialwedding.io

Phases
------
  SEED        — register/login planner, bypass subscription, ensure
                Stripe Connect is live, create a real wedding via
                POST /admin/weddings, create a real package via
                POST /packages (status='active'), call
                POST /admin/packages/{id}/send to produce a real
                contract row.
  CHECKPOINT_UI1
              — planner inspects /admin/money. Schedule rows do not
                exist YET (sign hasn't fired) — we surface that
                explicitly. Optional: planner can also visit
                /admin/packages/{id} to see contracts_count incremented.
  SIGN        — driver POSTs /public/contracts/{token}/setup-intent,
                confirms the SetupIntent server-side via Stripe with a
                test PM (pm_card_visa), POSTs the sign endpoint.
                Backend auto-charges the deposit.
  ASSERT_DEPOSIT
              — driver queries scheduled_payments for the contract,
                asserts the deposit row is `succeeded` with a
                stripe_payment_intent_id, then queries Stripe for the
                PaymentIntent and asserts transfer_data.destination
                matches the planner's stripe_connect_id.
  CHECKPOINT_UI2
              — couple-side Payments view shows Total / Paid /
                Remaining reflecting the deposit; deposit row reads
                Paid; milestone row reads Pending.
  CHECKPOINT_UI3
              — planner reloads /admin/money → Incoming. Deposit row
                Succeeded; milestone row Scheduled with the right
                couple/wedding labels.
  DONE        — print summary and exit 0.

Cleanup pair: cleanup_planner_couple_contract_flow_state.py

Usage
-----
    python testbed/verify_planner_couple_contract_flow.py
"""

from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
import stripe
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("verify_contract_flow")

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")
MONGO_DB = os.getenv("MONGO_DB") or os.getenv("MONGO_NAME", "wedding")

ADMIN_EMAIL = os.getenv("ROOT_ADMIN_EMAIL", "thedeveloper@thespecialwedding.io")
ADMIN_PASSWORD = os.getenv("ROOT_ADMIN_PASSWORD")

PLANNER_EMAIL = "test_planner+contractflow@thespecialwedding.io"
PLANNER_PASSWORD = "ContractFlowPlanner2026!"  # pragma: allowlist secret
PLANNER_FIRST = "Contract"
PLANNER_LAST = "FlowPlanner"

COUPLE_EMAIL = "test_couple+contractflow@thespecialwedding.io"
COUPLE_PARTNER1 = "Alex Davis"
COUPLE_PARTNER2 = "Jamie Rivera"
COUPLE_DISPLAY = f"{COUPLE_PARTNER1} & {COUPLE_PARTNER2}"

PLAN_ID = os.getenv("CONTRACTFLOW_PLAN_ID", "plan_signature")

# Package financials. Deposit is the on-signing line; milestone fires on
# autopilot when its due date arrives. Keep numbers small so test runs
# don't pile up against any Stripe sandbox limits.
DEPOSIT_AMOUNT = 100.0
MILESTONE_AMOUNT = 250.0
TOTAL_AMOUNT = DEPOSIT_AMOUNT + MILESTONE_AMOUNT
CURRENCY = "usd"

WEDDING_DATE_OFFSET_DAYS = 180  # ~6 months out

if not STRIPE_SECRET_KEY:
    raise SystemExit("STRIPE_SECRET_KEY not set in .env")
if not MONGO_URI:
    raise SystemExit("MONGO_URI not set in .env")
if not ADMIN_PASSWORD:
    raise SystemExit("ROOT_ADMIN_PASSWORD not set in .env")

# package_service.send_to_couple unconditionally calls the contract email
# service AFTER inserting the contract row, and DELETES the contract
# (then raises RuntimeError) if the email send returns falsy. See
# package_service.py:425-431. So if RESEND_API_KEY isn't configured,
# the SEND step fails in a confusing way: the API returns 500 and the
# contract row gets garbage-collected. Pre-flight here so we fail fast
# with a clear message instead.
if not os.getenv("RESEND_API_KEY"):
    raise SystemExit(
        "RESEND_API_KEY not set in .env.\n\n"
        "package_service.send_to_couple sends a contract email after\n"
        "creating the contract row, and rolls back the row if the email\n"
        "send fails. Set RESEND_API_KEY (any test/dev key works — Resend\n"
        "test mode is fine) and re-run."
    )

stripe.api_key = STRIPE_SECRET_KEY


# ---------------------------------------------------------------------------
# Console helpers
# ---------------------------------------------------------------------------


def banner(label: str) -> None:
    logger.info("")
    logger.info("=" * 72)
    logger.info("  PHASE — %s", label)
    logger.info("=" * 72)


def checkpoint(label: str, lines: list[str]) -> None:
    logger.info("─" * 72)
    logger.info("  CHECKPOINT %s", label)
    logger.info("─" * 72)
    for ln in lines:
        logger.info("  %s", ln)
    logger.info("─" * 72)
    input("→ Press ENTER once you've verified this checkpoint in Chrome… ")


def assert_eq(name: str, actual, expected) -> None:
    if actual != expected:
        raise AssertionError(f"{name}: expected {expected!r}, got {actual!r}")
    logger.info("  ✅ %s == %r", name, expected)


def assert_truthy(name: str, value) -> None:
    if not value:
        raise AssertionError(f"{name}: expected truthy, got {value!r}")
    logger.info("  ✅ %s truthy (%r)", name, value)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def login(email: str, password: str) -> str:
    """Login via /admin/token. Returns bearer access_token."""
    r = requests.post(
        f"{BACKEND_URL}/admin/token",
        json={"email": email, "password": password},
        timeout=15,
    )
    r.raise_for_status()
    payload = r.json()
    token = payload.get("access_token") or payload.get("token")
    if not token:
        raise RuntimeError(f"login: no token in response {payload!r}")
    return token


def auth_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def find_user_id_by_email(admin_token: str, email: str) -> str:
    r = requests.get(
        f"{BACKEND_URL}/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=15,
    )
    r.raise_for_status()
    payload = r.json()
    users = payload.get("users") if isinstance(payload, dict) else payload
    for u in users or []:
        if (u.get("email") or "").lower() == email.lower():
            return str(u.get("_id") or u.get("id"))
    raise RuntimeError(f"No user with email {email}")


# ---------------------------------------------------------------------------
# SEED helpers
# ---------------------------------------------------------------------------


def ensure_planner_registered(mongo_db) -> str:
    """Register if missing, activate, return planner's user_id."""
    try:
        login(PLANNER_EMAIL, PLANNER_PASSWORD)
        logger.info("  Planner already exists, logged in.")
    except requests.HTTPError:
        logger.info("  Registering planner via /public/register…")
        admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
        r = requests.post(
            f"{BACKEND_URL}/public/register",
            json={
                "email": PLANNER_EMAIL,
                "password": PLANNER_PASSWORD,
                "first_name": PLANNER_FIRST,
                "last_name": PLANNER_LAST,
                "company_name": "ContractFlow QA Co",
                "selected_plan_id": PLAN_ID,
                "role": "wedding_planner",
            },
            timeout=15,
        )
        if r.status_code not in (200, 201):
            raise RuntimeError(f"register failed: {r.status_code} {r.text}")
        user_id = find_user_id_by_email(admin_token, PLANNER_EMAIL)
        requests.post(
            f"{BACKEND_URL}/users/{user_id}/activate",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        ).raise_for_status()
        mongo_db["users"].update_one(
            {"_id": ObjectId(user_id)}, {"$set": {"email_verified": True}}
        )
        login(PLANNER_EMAIL, PLANNER_PASSWORD)
        logger.info("  ✅ Registered + activated.")

    user = mongo_db["users"].find_one({"email": PLANNER_EMAIL})
    return str(user["_id"])


def bypass_subscription_gate(mongo_db, planner_user_id: str) -> None:
    """Flip subscription_status=active so the planner can reach
    /admin/weddings, /admin/packages, /admin/money. Test-only shortcut.
    """
    now = datetime.now(timezone.utc)
    mongo_db["users"].update_one(
        {"_id": ObjectId(planner_user_id)},
        {
            "$set": {
                "subscription_status": "active",
                "is_active": True,
                "user_data.plan_id": PLAN_ID,
            }
        },
    )
    mongo_db["user_subscriptions"].update_one(
        {"user_id": planner_user_id},
        {
            "$set": {
                "user_id": planner_user_id,
                "plan_id": PLAN_ID,
                "status": "active",
                "billing_interval": "monthly",
                "current_period_start": now.isoformat(),
                "current_period_end": (now + timedelta(days=30)).isoformat(),
                "payment_status": "paid",
                "created_at": now.isoformat(),
                "source": "verify_planner_couple_contract_flow test bypass",
            }
        },
        upsert=True,
    )
    logger.info("  ✅ subscription_status=active for planner.")


def ensure_planner_connect_account(mongo_db, planner_user_id: str) -> str:
    """Ensure the planner has a Stripe Connect Express account that is
    `charges_enabled`. Falls back to hosted onboarding if charges_enabled
    is false (Express accounts can't be auto-onboarded via the API)."""
    user = mongo_db["users"].find_one({"_id": ObjectId(planner_user_id)})
    connect_id = user.get("stripe_connect_id") if user else None

    if not connect_id:
        logger.info("  Creating Stripe Express account for planner…")
        try:
            account = stripe.Account.create(
                type="express",
                country="US",
                email=PLANNER_EMAIL,
                capabilities={
                    "card_payments": {"requested": True},
                    "transfers": {"requested": True},
                },
                business_type="individual",
                business_profile={
                    "url": "https://thespecialwedding.io",
                    "mcc": "7299",
                    "product_description": "Wedding planning services (test)",
                },
            )
        except stripe.error.InvalidRequestError as exc:
            if "signed up for Connect" in str(exc):
                raise SystemExit(
                    "Stripe Connect is not enabled for this test account.\n"
                    "Visit https://dashboard.stripe.com/test/connect and click "
                    "'Get started' (one-time, free)."
                )
            raise
        connect_id = account.id
        mongo_db["users"].update_one(
            {"_id": ObjectId(planner_user_id)},
            {"$set": {"stripe_connect_id": connect_id}},
        )
        logger.info("  ✅ Created Stripe account: %s", connect_id)

    account = stripe.Account.retrieve(connect_id)
    if not account.charges_enabled:
        logger.info("  Account exists but charges_enabled=False — onboarding needed.")
        link = stripe.AccountLink.create(
            account=connect_id,
            refresh_url=f"{FRONTEND_URL}/admin/planner/billing",
            return_url=f"{FRONTEND_URL}/admin/planner/billing",
            type="account_onboarding",
        )
        logger.info("─" * 72)
        logger.info("  HOSTED ONBOARDING REQUIRED")
        logger.info("  Open in Chrome and complete (use 'Use test data' buttons):")
        logger.info("    %s", link.url)
        logger.info("  When Stripe redirects you back, return here and press ENTER.")
        logger.info("─" * 72)
        input("→ Press ENTER once Stripe has redirected you back… ")

        for attempt in range(1, 25):
            account = stripe.Account.retrieve(connect_id)
            if account.charges_enabled:
                logger.info("  ✅ charges_enabled=True (poll %d)", attempt)
                break
            logger.info("  ⏳ charges_enabled=False (poll %d/24)", attempt)
            time.sleep(5)
        else:
            raise RuntimeError("charges_enabled never flipped to True.")
    else:
        logger.info(
            "  ✅ Stripe Connect account ready: %s (charges_enabled=True)", connect_id
        )

    return connect_id


def create_wedding(planner_token: str) -> str:
    """POST /admin/weddings — creates a real wedding row through the
    production code path. Required: couple_names + date.
    """
    wedding_date = (
        datetime.now(timezone.utc) + timedelta(days=WEDDING_DATE_OFFSET_DAYS)
    ).date()
    payload = {
        "couple_names": COUPLE_DISPLAY,
        "date": wedding_date.isoformat(),
        "guest_count": 50,
        "venue": "Test Venue (verifier seed)",
        "status": "active",
    }
    r = requests.post(
        f"{BACKEND_URL}/admin/weddings",
        headers=auth_headers(planner_token),
        json=payload,
        timeout=20,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"wedding create failed: {r.status_code} {r.text}")
    body = r.json()
    # Wedding response shape varies — look for id or _id, possibly nested.
    wedding_id = (
        body.get("id")
        or body.get("_id")
        or (body.get("wedding") or {}).get("id")
        or (body.get("wedding") or {}).get("_id")
    )
    if not wedding_id:
        raise RuntimeError(f"could not find wedding_id in response: {body!r}")
    logger.info("  ✅ Created wedding: %s (date=%s)", wedding_id, wedding_date)
    return str(wedding_id)


def create_package(planner_token: str) -> str:
    """POST /packages — creates a real package row through the production
    code path. Status='active' so it can be sent to a couple immediately.
    Includes a payment schedule with a deposit on signing + a milestone
    7 days after signing.
    """
    payload = {
        "name": "Test Wedding Package — Contract Flow Verifier",
        "description": "Full planning + day-of coordination (test seed).",
        "services": [
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
        "total_amount": TOTAL_AMOUNT,
        "currency": CURRENCY,
        "payment_schedule": [
            {
                "name": "Deposit",
                "trigger": "on_signing",
                "amount": DEPOSIT_AMOUNT,
            },
            {
                "name": "Milestone payment",
                "trigger": "days_after_signing",
                "days_after": 7,
                "amount": MILESTONE_AMOUNT,
            },
        ],
        "cancellation_policy": "Standard 50% deposit non-refundable after sign.",
        "status": "active",
    }
    # The packages_router is mounted with prefix="/admin" in main.py, so
    # the declared @router.post("/packages") resolves to /admin/packages.
    r = requests.post(
        f"{BACKEND_URL}/admin/packages",
        headers=auth_headers(planner_token),
        json=payload,
        timeout=20,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"package create failed: {r.status_code} {r.text}")
    body = r.json()
    package = body.get("package") or body
    package_id = package.get("id") or package.get("_id")
    if not package_id:
        raise RuntimeError(f"could not find package_id in response: {body!r}")
    logger.info(
        "  ✅ Created package: %s ($%.2f total, deposit $%.2f + milestone $%.2f)",
        package_id,
        TOTAL_AMOUNT,
        DEPOSIT_AMOUNT,
        MILESTONE_AMOUNT,
    )
    return str(package_id)


def send_package_to_couple(planner_token: str, package_id: str, wedding_id: str) -> str:
    """POST /packages/{package_id}/send — routes through the canonical
    `package_service.send_package_to_couple`. Returns the public contract
    token from the response.
    """
    payload = {
        "couple": {
            "partner1_name": COUPLE_PARTNER1,
            "partner2_name": COUPLE_PARTNER2,
            "email": COUPLE_EMAIL,
        },
        "wedding_id": wedding_id,
    }
    # /admin prefix per main.py — same as create.
    r = requests.post(
        f"{BACKEND_URL}/admin/packages/{package_id}/send",
        headers=auth_headers(planner_token),
        json=payload,
        timeout=30,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"send failed: {r.status_code} {r.text}")
    body = r.json()
    contract = body.get("contract") or body
    token = contract.get("token") or contract.get("public_token")
    if not token:
        raise RuntimeError(f"could not find contract token in response: {body!r}")
    logger.info("  ✅ Sent package — contract token: %s", token)
    return token


# ---------------------------------------------------------------------------
# Sign helpers
# ---------------------------------------------------------------------------


def setup_payment_method_and_sign(token: str) -> Dict[str, Any]:
    """Realistic sign flow: SetupIntent → confirm with pm_card_visa → sign.
    Returns the sign response payload.
    """
    # 1. Init SetupIntent
    r = requests.post(
        f"{BACKEND_URL}/public/contracts/{token}/setup-intent",
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    customer_id = data["customer_id"]
    client_secret = data["client_secret"]
    setup_intent_id = client_secret.split("_secret_")[0]
    logger.info(
        "  ✅ SetupIntent initialized: customer=%s setup_intent=%s",
        customer_id,
        setup_intent_id,
    )

    # 2. Confirm SetupIntent server-side with a test PM token
    setup_intent = stripe.SetupIntent.confirm(
        setup_intent_id,
        payment_method="pm_card_visa",
    )
    if setup_intent.status != "succeeded":
        raise RuntimeError(
            f"SetupIntent confirm did not succeed: status={setup_intent.status}"
        )
    payment_method_id = setup_intent.payment_method
    logger.info("  ✅ SetupIntent confirmed: pm=%s", payment_method_id)

    pm = stripe.PaymentMethod.retrieve(payment_method_id)
    last4 = pm.card.last4 if pm.card else None
    brand = pm.card.brand if pm.card else None

    # 3. POST sign
    r = requests.post(
        f"{BACKEND_URL}/public/contracts/{token}/sign",
        json={
            "signature_name": COUPLE_PARTNER1,
            "accept_terms": True,
            "stripe_customer_id": customer_id,
            "stripe_payment_method_id": payment_method_id,
            "setup_intent_id": setup_intent_id,
            "payment_method_last4": last4,
            "payment_method_brand": brand,
        },
        timeout=30,
    )
    if r.status_code != 200:
        raise RuntimeError(f"sign failed: {r.status_code} {r.text}")
    sign_payload = r.json()
    logger.info("  ✅ Contract signed.")
    logger.info(
        "     deposit_processed=%s scheduled_payments=%d",
        sign_payload.get("contract", {}).get("deposit_processed"),
        len(sign_payload.get("contract", {}).get("scheduled_payments", []) or []),
    )
    return sign_payload


# ---------------------------------------------------------------------------
# ASSERT helpers
# ---------------------------------------------------------------------------


def assert_deposit_charged(
    mongo_db, contract_token: str, planner_connect_id: str
) -> None:
    contract = mongo_db["contracts"].find_one({"token": contract_token})
    if not contract:
        raise AssertionError("Contract row missing after sign")

    payments = list(
        mongo_db["scheduled_payments"]
        .find({"contract_id": str(contract["_id"])})
        .sort("due_date", 1)
    )
    if len(payments) != 2:
        raise AssertionError(
            f"Expected 2 scheduled_payments rows (deposit + milestone), "
            f"got {len(payments)}"
        )

    deposit = payments[0]
    milestone = payments[1]
    assert_eq("deposit.name", deposit.get("name"), "Deposit")
    assert_eq("deposit.status", deposit.get("status"), "succeeded")
    assert_truthy(
        "deposit.stripe_payment_intent_id", deposit.get("stripe_payment_intent_id")
    )
    assert_eq("deposit.amount", float(deposit.get("amount", 0)), DEPOSIT_AMOUNT)

    assert_eq("milestone.name", milestone.get("name"), "Milestone payment")
    assert_eq("milestone.status", milestone.get("status"), "scheduled")
    assert_eq("milestone.amount", float(milestone.get("amount", 0)), MILESTONE_AMOUNT)

    pi = stripe.PaymentIntent.retrieve(deposit["stripe_payment_intent_id"])
    transfer_dest = (pi.get("transfer_data") or {}).get("destination")
    assert_eq("deposit.transfer_data.destination", transfer_dest, planner_connect_id)
    assert_eq(
        "deposit.amount_received_cents",
        pi.get("amount_received"),
        int(DEPOSIT_AMOUNT * 100),
    )


# ---------------------------------------------------------------------------
# Phases
# ---------------------------------------------------------------------------


def phase_seed(mongo_db) -> Dict[str, Any]:
    banner("SEED")
    planner_user_id = ensure_planner_registered(mongo_db)
    bypass_subscription_gate(mongo_db, planner_user_id)
    connect_id = ensure_planner_connect_account(mongo_db, planner_user_id)

    planner_token = login(PLANNER_EMAIL, PLANNER_PASSWORD)
    wedding_id = create_wedding(planner_token)
    package_id = create_package(planner_token)
    contract_token = send_package_to_couple(planner_token, package_id, wedding_id)

    return {
        "planner_user_id": planner_user_id,
        "planner_token": planner_token,
        "connect_id": connect_id,
        "wedding_id": wedding_id,
        "package_id": package_id,
        "contract_token": contract_token,
    }


def phase_checkpoint_ui1(state: Dict[str, Any]) -> None:
    """Pre-sign. The contract exists and the package shows
    contracts_count=1, but `scheduled_payments` rows aren't created
    until sign-time. So Money → Incoming should NOT yet have rows for
    this contract. The package list should show the package as 'active'
    with one contract sent."""
    checkpoint(
        "UI-1 (pre-sign — package + contract exist, no schedule rows yet)",
        [
            f"1. Open {FRONTEND_URL}/admin/login as planner:",
            f"     {PLANNER_EMAIL} / {PLANNER_PASSWORD}",
            f"2. /admin/weddings should list one wedding for {COUPLE_DISPLAY}",
            f"   (date about {WEDDING_DATE_OFFSET_DAYS} days out).",
            "3. /admin/packages should list 'Test Wedding Package — Contract",
            "   Flow Verifier' as Active with 1 contract sent.",
            "4. /admin/money → Incoming should NOT yet show payment rows for",
            "   this contract. Schedule rows are inserted by the sign endpoint.",
            "5. Public contract URL should be signable:",
            f"     {FRONTEND_URL}/contracts/{state['contract_token']}",
        ],
    )


def phase_sign(state: Dict[str, Any]) -> None:
    banner("SIGN")
    setup_payment_method_and_sign(state["contract_token"])


def phase_assert_deposit(mongo_db, state: Dict[str, Any]) -> None:
    banner("ASSERT_DEPOSIT")
    assert_deposit_charged(
        mongo_db,
        contract_token=state["contract_token"],
        planner_connect_id=state["connect_id"],
    )


def phase_checkpoint_ui2_couple(state: Dict[str, Any]) -> None:
    checkpoint(
        "UI-2 (couple-side Payments view reflects the deposit)",
        [
            "1. The couple was sent a contract email with the public link",
            f"     {FRONTEND_URL}/contracts/{state['contract_token']}",
            "   Open it (private window if you want to confirm couple-side",
            "   visibility independent of planner auth).",
            "2. The Payments / Schedule view should show:",
            f"      Total = ${TOTAL_AMOUNT:.2f}",
            f"      Paid  = ${DEPOSIT_AMOUNT:.2f}",
            f"      Remaining = ${MILESTONE_AMOUNT:.2f}",
            "3. The Deposit row reads as 'Paid'.",
            "4. The Milestone row reads as 'Scheduled' (or 'Pending') with",
            "   a due date about 7 days from today.",
        ],
    )


def phase_checkpoint_ui3_money_after(state: Dict[str, Any]) -> None:
    checkpoint(
        "UI-3 (planner Money → Incoming reflects the deposit)",
        [
            f"1. Reload {FRONTEND_URL}/admin/money → Incoming tab.",
            f"2. A row for {COUPLE_DISPLAY} 'Deposit' appears with",
            f"   status=Succeeded and amount ${DEPOSIT_AMOUNT:.2f}.",
            f"3. A row for {COUPLE_DISPLAY} 'Milestone payment' appears with",
            f"   status=Scheduled and amount ${MILESTONE_AMOUNT:.2f}.",
            "4. The 'Card' column shows a Visa ending in 4242.",
            "5. Summary cards at the top reflect the new pending/incoming totals.",
        ],
    )


def main() -> int:
    client = MongoClient(MONGO_URI)
    mongo_db = client[MONGO_DB]

    state = phase_seed(mongo_db)
    phase_checkpoint_ui1(state)
    phase_sign(state)
    phase_assert_deposit(mongo_db, state)
    phase_checkpoint_ui2_couple(state)
    phase_checkpoint_ui3_money_after(state)

    logger.info("")
    logger.info("=" * 72)
    logger.info("  ✅ All checkpoints passed.")
    logger.info("=" * 72)
    logger.info("Run testbed/cleanup_planner_couple_contract_flow_state.py to")
    logger.info("reset for the next run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
