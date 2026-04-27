#!/usr/bin/env python3
"""
Planner ↔ Couple Contract Flow — Live Verification
====================================================

Purpose
-------
Verify the canonical planner→couple billing flow end-to-end:

  1. Planner builds (we seed) a contract with a payment schedule
     (deposit on signing + one milestone).
  2. Couple opens the public contract URL, sets up a payment method via
     Stripe SetupIntent, and signs the contract.
  3. Backend automatically charges the deposit through Stripe with
     `transfer_data.destination` = the planner's connected account.
  4. The /admin/money "Incoming" view (planner side) and the
     /couple/dashboard "Payments" view (couple side) reflect the new
     state.

This is the flow the platform actually uses for couple billing — NOT the
removed ad-hoc "Couple Payments" tab. The earlier
`verify_couple_payments_gate.py` driver tested a feature that no longer
exists; this driver replaces it.

Two-layer verification per CLAUDE.md:

- Backend asserts: scheduled_payments rows created, deposit row flips to
  `succeeded`, Stripe PaymentIntent has the right destination account.
- UI checkpoints: planner Money → Incoming, couple dashboard → Payments.

Accounts (plus-variant; base accounts never touched)
----------------------------------------------------
  Planner : test_planner+contractflow@thespecialwedding.io
  Couple  : test_couple+contractflow@thespecialwedding.io
  Wedding : seeded against the planner

Phases
------
  SEED          — register/login planner, bypass subscription, ensure
                  Stripe Connect is live, create a wedding, insert a
                  contract row with a payment schedule (deposit + one
                  milestone) plus a fresh public token.
  CHECKPOINT_UI1— planner inspects /admin/money → Incoming. Two rows
                  (deposit + milestone) appear with status='scheduled',
                  the right couple/wedding label, and the right amounts.
  SIGN          — driver POSTs /public/contracts/{token}/setup-intent,
                  uses the Stripe API to confirm a SetupIntent with a
                  test PM (pm_card_visa), then POSTs the sign endpoint.
                  Backend auto-charges the deposit.
  ASSERT_DEPOSIT— driver queries Mongo for the deposit row and asserts
                  status='succeeded' + a stripe_payment_intent_id is set.
                  Then queries Stripe for that PaymentIntent and asserts
                  transfer_data.destination matches the planner's
                  stripe_connect_id.
  CHECKPOINT_UI2— couple opens /couple/dashboard → Payments. Total /
                  Paid / Remaining reflect the deposit; the deposit row
                  shows as Paid; the milestone row shows as Pending.
  CHECKPOINT_UI3— planner reloads /admin/money → Incoming. Deposit row
                  is now Succeeded; milestone row remains scheduled.
  DONE          — print summary and exit 0.

Cleanup pair: cleanup_planner_couple_contract_flow_state.py

Usage
-----
    python testbed/verify_planner_couple_contract_flow.py
"""

from __future__ import annotations

import logging
import os
import secrets
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
COUPLE_NAME = "Contract Flow Couple"

PLAN_ID = os.getenv("CONTRACTFLOW_PLAN_ID", "plan_signature")

# Contract financials. Deposit is the on-signing line; milestone fires on
# autopilot when its due date arrives. Keep numbers small so test runs
# don't pile up against any Stripe sandbox limits.
DEPOSIT_AMOUNT = 100.0  # USD
MILESTONE_AMOUNT = 250.0  # USD
TOTAL_AMOUNT = DEPOSIT_AMOUNT + MILESTONE_AMOUNT
CURRENCY = "usd"

if not STRIPE_SECRET_KEY:
    raise SystemExit("STRIPE_SECRET_KEY not set in .env")
if not MONGO_URI:
    raise SystemExit("MONGO_URI not set in .env")
if not ADMIN_PASSWORD:
    raise SystemExit("ROOT_ADMIN_PASSWORD not set in .env")

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
    """Flip subscription_status=active so the planner can reach /admin/money.

    This is a TEST-ONLY shortcut for verification — the canonical
    contract+autopilot path doesn't depend on the planner's SaaS
    subscription state, but the planner UI gates everything behind it.
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
    `charges_enabled`. If not, generate an Account Link and pause for
    the user to complete hosted onboarding (Use test data buttons).

    Returns the connect account id.
    """
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

    # Check charges_enabled. If not, walk the user through hosted onboarding.
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


def ensure_test_wedding(mongo_db, planner_user_id: str) -> str:
    """Insert a wedding row owned by the planner if one doesn't exist."""
    existing = mongo_db["weddings"].find_one(
        {"planner_id": planner_user_id, "couple.email": COUPLE_EMAIL}
    )
    if existing:
        wedding_id = str(existing["_id"])
        logger.info("  Wedding already exists: %s", wedding_id)
        return wedding_id

    wedding_doc = {
        "planner_id": planner_user_id,
        "title": f"{COUPLE_NAME} Wedding",
        "couple": {"name": COUPLE_NAME, "email": COUPLE_EMAIL},
        "wedding_date": datetime.now(timezone.utc) + timedelta(days=180),
        "status": "active",
        "guest_count": 50,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "source": "verify_planner_couple_contract_flow test seed",
    }
    result = mongo_db["weddings"].insert_one(wedding_doc)
    wedding_id = str(result.inserted_id)
    logger.info("  ✅ Created wedding: %s", wedding_id)
    return wedding_id


def insert_contract(mongo_db, planner_user_id: str, wedding_id: str) -> str:
    """Insert a contract row in 'sent' state with a known public token.

    Mirrors the shape contract_service expects:
      - status='sent' (signable)
      - public token (used by /public/contracts/{token}/sign and setup-intent)
      - planner_id, wedding_id, couple
      - package_snapshot.payment_schedule (deposit on_signing + milestone in 7 days)
      - package_snapshot.total_amount, currency

    Returns the contract token.
    """
    # Re-use the contract if a previous run left one in place — keeps the test
    # idempotent the way the existing testbed drivers are.
    existing = mongo_db["contracts"].find_one(
        {
            "planner_id": planner_user_id,
            "wedding_id": wedding_id,
            "couple.email": COUPLE_EMAIL,
        }
    )
    if existing and existing.get("status") == "sent":
        token = existing["token"]
        logger.info("  Reusing existing contract: token=%s", token)
        return token

    if existing:
        # Old contract from a prior run, but in a non-signable status.
        # Drop it so the seed creates a fresh signable one.
        mongo_db["contracts"].delete_one({"_id": existing["_id"]})
        mongo_db["scheduled_payments"].delete_many(
            {"contract_id": str(existing["_id"])}
        )
        logger.info("  Removed stale contract from prior run.")

    token = secrets.token_urlsafe(24)
    now = datetime.now(timezone.utc)
    wedding_date = now + timedelta(days=180)

    contract_doc = {
        "token": token,
        "status": "sent",
        "planner_id": planner_user_id,
        "wedding_id": wedding_id,
        "wedding_date": wedding_date,
        "couple": {"name": COUPLE_NAME, "email": COUPLE_EMAIL},
        "package_name": "Test Wedding Package",
        "package_snapshot": {
            "name": "Test Wedding Package",
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
        },
        "custom_sections": [
            {
                "title": "Scope of services",
                "content": "Wedding planning + day-of coordination.",
            },
            {
                "title": "Cancellation",
                "content": "Standard 50% deposit non-refundable after sign.",
            },
        ],
        "created_at": now,
        "updated_at": now,
        "sent_at": now,
        "source": "verify_planner_couple_contract_flow test seed",
    }
    result = mongo_db["contracts"].insert_one(contract_doc)
    logger.info(
        "  ✅ Inserted contract: id=%s token=%s schedule=$%.2f deposit + $%.2f milestone",
        result.inserted_id,
        token,
        DEPOSIT_AMOUNT,
        MILESTONE_AMOUNT,
    )
    return token


# ---------------------------------------------------------------------------
# Sign helpers
# ---------------------------------------------------------------------------


def setup_payment_method_and_sign(token: str) -> Dict[str, Any]:
    """Run the realistic sign flow:
      1) POST /public/contracts/{token}/setup-intent → client_secret + customer_id
      2) Confirm SetupIntent via Stripe API with pm_card_visa
      3) POST /public/contracts/{token}/sign with setup_intent_id + pm_id

    Returns the sign response payload.
    """
    # 1. Initialize SetupIntent
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

    # 2. Confirm the SetupIntent with a test PM. In test mode you can confirm
    # server-side using a pm_card_* token without a 3DS step.
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

    # Retrieve PM for last4/brand metadata
    pm = stripe.PaymentMethod.retrieve(payment_method_id)
    last4 = pm.card.last4 if pm.card else None
    brand = pm.card.brand if pm.card else None

    # 3. POST sign
    r = requests.post(
        f"{BACKEND_URL}/public/contracts/{token}/sign",
        json={
            "signature_name": COUPLE_NAME,
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

    # Verify the PaymentIntent on Stripe routed to the planner's account.
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
    wedding_id = ensure_test_wedding(mongo_db, planner_user_id)
    token = insert_contract(mongo_db, planner_user_id, wedding_id)
    return {
        "planner_user_id": planner_user_id,
        "connect_id": connect_id,
        "wedding_id": wedding_id,
        "contract_token": token,
    }


def phase_checkpoint_ui1_money_scheduled(state: Dict[str, Any]) -> None:
    """Note: the Money page reads scheduled_payments. Before sign, those rows
    don't exist yet (they're created by `_create_scheduled_payments` at sign
    time). So at this checkpoint, there's nothing to see in Incoming for this
    contract. We surface that explicitly so the user knows what to look at."""
    checkpoint(
        "UI-1 (pre-sign — Incoming should NOT yet show this contract)",
        [
            f"1. Open {FRONTEND_URL}/admin/planner/billing as planner:",
            f"   {PLANNER_EMAIL} / {PLANNER_PASSWORD}",
            "2. Go to Money in the sidebar → Incoming tab.",
            "3. The new contract is in 'sent' status with no scheduled_payments",
            "   yet, so it does NOT appear in Incoming. (Schedule rows are",
            "   inserted by the sign endpoint.)",
            "4. Confirm no surprise rows for our test couple (Contract Flow Couple).",
            "5. Open the public contract URL to confirm it's signable:",
            f"   {FRONTEND_URL}/contracts/{state['contract_token']}",
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
        "UI-2 (couple dashboard reflects the deposit)",
        [
            "1. Open the couple-side portal in a private window. Ideally",
            "   sign in as the couple if you have credentials wired; if not,",
            "   visit the public portal route via the contract token:",
            f"   {FRONTEND_URL}/contracts/{state['contract_token']}",
            "   (Or load /couple/dashboard if the test couple is provisioned.)",
            "2. The Payments view should show:",
            f"      Total = ${TOTAL_AMOUNT:.2f}",
            f"      Paid  = ${DEPOSIT_AMOUNT:.2f}",
            f"      Remaining = ${MILESTONE_AMOUNT:.2f}",
            "3. The deposit row reads as 'Paid'.",
            "4. The milestone row reads as 'Scheduled' (or 'Pending') with",
            "   a due date about 7 days from today.",
        ],
    )


def phase_checkpoint_ui3_money_after(state: Dict[str, Any]) -> None:
    checkpoint(
        "UI-3 (planner Money → Incoming reflects the deposit)",
        [
            f"1. Reload {FRONTEND_URL}/admin/money → Incoming tab.",
            f"2. A row for {COUPLE_NAME} 'Deposit' appears with",
            f"   status=Succeeded and amount ${DEPOSIT_AMOUNT:.2f}.",
            f"3. A row for {COUPLE_NAME} 'Milestone payment' appears with",
            f"   status=Scheduled and amount ${MILESTONE_AMOUNT:.2f}.",
            "4. The 'Card' column shows a Visa ending in 4242.",
            "5. Summary cards at the top reflect the new pending/incoming totals.",
        ],
    )


def main() -> int:
    client = MongoClient(MONGO_URI)
    mongo_db = client[MONGO_DB]

    state = phase_seed(mongo_db)
    phase_checkpoint_ui1_money_scheduled(state)
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
