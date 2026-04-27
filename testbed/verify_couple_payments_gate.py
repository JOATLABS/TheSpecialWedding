#!/usr/bin/env python3
"""
Couple-Payments Stripe Connect Gate — Live Verification
========================================================

Purpose
-------
Verify that the planner's Couple Payments surface correctly gates the
"Request payment" action on whether the planner has completed Stripe
Connect onboarding (`charges_enabled = true`).

Two layers of verification per CLAUDE.md:

  - Backend: /stripe/connect/status reflects reality (no connect → false;
    after seeding stripe_connect_id → true).
  - UI: in Chrome, the "Request payment" CTA is DISABLED before connect
    and ENABLED after, with the disabled-state tooltip and inline
    empty-state messaging matching the design.

Notable finding (logged at the end of this run):

  POST /stripe/create-payment-intent does NOT currently reject when the
  caller has no stripe_connect_id. It happily creates a payment intent
  without transfer_data.destination, which means funds route to the
  PLATFORM Stripe account, not the planner. The frontend gate this
  driver verifies is the only thing preventing that today. The backend
  needs a matching server-side check; flagged for follow-up.

Accounts (plus-variant; base accounts never touched)
----------------------------------------------------
  Planner : test_planner+couplepay@thespecialwedding.io

Phases
------
  SEED           — register planner via signup endpoint, log in, get token.
                   Assert /stripe/connect/status returns charges_enabled=false.
  CHECKPOINT_UI1 — user inspects Chrome: "Request payment" disabled with
                   tooltip; empty state copy reads "Connect Stripe above
                   to start requesting payments from couples."
  CONNECT        — create a Stripe Express test account, wire it onto the
                   planner's user document. Assert /stripe/connect/status
                   now returns charges_enabled=true.
  CHECKPOINT_UI2 — user reloads Chrome: button is ENABLED, opens modal,
                   creates a payment request. Verify row renders with
                   the right amount and currency.
  ASSERT_API     — GET /stripe/payment-requests includes the new row at
                   the dollar amount the user entered (NOT cents).

Cleanup pair: cleanup_couple_payments_gate_state.py

Usage
-----
    python testbed/verify_couple_payments_gate.py
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

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
logger = logging.getLogger("verify_couple_payments_gate")

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")
MONGO_DB = os.getenv("MONGO_DB") or os.getenv("MONGO_NAME", "wedding")

ADMIN_EMAIL = os.getenv("ROOT_ADMIN_EMAIL", "thedeveloper@thespecialwedding.io")
ADMIN_PASSWORD = os.getenv("ROOT_ADMIN_PASSWORD")

PLANNER_EMAIL = "test_planner+couplepay@thespecialwedding.io"
PLANNER_PASSWORD = "CouplePayPlanner2026!"  # pragma: allowlist secret
PLANNER_FIRST = "Couple"
PLANNER_LAST = "PayTester"

# Used by /public/register; lets the planner subscribe later if needed,
# though this driver doesn't exercise the subscription path.
PLAN_ID = os.getenv("COUPLEPAY_PLAN_ID", "plan_signature")

if not STRIPE_SECRET_KEY:
    raise SystemExit("STRIPE_SECRET_KEY not set in .env")
if not MONGO_URI:
    raise SystemExit("MONGO_URI not set in .env")
if not ADMIN_PASSWORD:
    raise SystemExit(
        "ROOT_ADMIN_PASSWORD not set in .env (needed to activate the planner)"
    )

stripe.api_key = STRIPE_SECRET_KEY


# ---------------------------------------------------------------------------
# Helpers
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


def login(email: str, password: str) -> str:
    """Returns a bearer token via /admin/token (used by both planner + admin)."""
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


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def find_user_id_by_email(admin_token: str, email: str) -> str:
    """Look up a user via admin /users endpoint. Handles {users:[...]} envelope."""
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


def get_connect_status(token: str) -> dict:
    r = requests.get(
        f"{BACKEND_URL}/stripe/connect/status",
        headers=auth_headers(token),
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def get_payment_requests(token: str) -> list[dict]:
    r = requests.get(
        f"{BACKEND_URL}/stripe/payment-requests",
        headers=auth_headers(token),
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------------------
# Phases
# ---------------------------------------------------------------------------


def phase_seed(mongo_db) -> str:
    """Register/sign-in planner, return token. Idempotent.

    Mirrors the verify_team_member_gate pattern: register via
    /public/register, then admin-activate, then flip email_verified
    directly in Mongo so /admin/token works without an email round-trip.
    """
    banner("SEED")

    # 1. Try login first; if it fails, plan to register + activate.
    try:
        token = login(PLANNER_EMAIL, PLANNER_PASSWORD)
        logger.info("  Planner already exists, logged in.")
    except requests.HTTPError:
        logger.info("  Planner not found, registering via /public/register…")
        admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
        r = requests.post(
            f"{BACKEND_URL}/public/register",
            json={
                "email": PLANNER_EMAIL,
                "password": PLANNER_PASSWORD,
                "first_name": PLANNER_FIRST,
                "last_name": PLANNER_LAST,
                "company_name": "CouplePay QA Co",
                "selected_plan_id": PLAN_ID,
                "role": "wedding_planner",
            },
            timeout=15,
        )
        if r.status_code not in (200, 201):
            raise RuntimeError(f"register failed: {r.status_code} {r.text}")
        logger.info("  ✅ Registered.")

        # Activate so is_active=true (admin gate), then flip email_verified
        # directly because /users/{id}/activate doesn't touch that flag and
        # auth_service.authenticate_user rejects unverified public_signup
        # registrations.
        user_id = find_user_id_by_email(admin_token, PLANNER_EMAIL)
        r = requests.post(
            f"{BACKEND_URL}/users/{user_id}/activate",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )
        r.raise_for_status()
        mongo_db["users"].update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"email_verified": True}},
        )
        logger.info("  ✅ Activated + email_verified=True (test bypass).")

        token = login(PLANNER_EMAIL, PLANNER_PASSWORD)
        logger.info("  ✅ Logged in.")

    # Make sure no stale stripe_connect_id is on this user from a prior run.
    user = mongo_db["users"].find_one({"email": PLANNER_EMAIL})
    if user and user.get("stripe_connect_id"):
        logger.info("  Clearing stale stripe_connect_id from prior run.")
        mongo_db["users"].update_one(
            {"_id": user["_id"]}, {"$unset": {"stripe_connect_id": ""}}
        )

    status = get_connect_status(token)
    logger.info("  /stripe/connect/status → %s", status)
    assert_eq("connect.status", status.get("status"), "not_connected")
    assert_eq("connect.charges_enabled", status.get("charges_enabled"), False)
    assert_eq("connect.details_submitted", status.get("details_submitted"), False)

    return token


def phase_checkpoint_ui_disabled() -> None:
    checkpoint(
        "UI-1 (gate engaged)",
        [
            f"1. Open {FRONTEND_URL}/admin/planner/billing as the planner.",
            "2. Click the 'Couple Payments' tab.",
            "3. The 'Request payment' button MUST be disabled (50% opacity).",
            "4. Hover the button — tooltip reads:",
            "   'Connect Stripe before requesting payments from couples.'",
            "5. The empty-state text in the Payment Requests card reads:",
            "   'Connect Stripe above to start requesting payments from couples.'",
            "6. The inline 'Request your first payment' secondary button is",
            "   NOT shown while disconnected.",
            "7. Right column shows: How payment requests work, Fees,",
            "   Need help. (No void next to the cards.)",
        ],
    )


def phase_connect(mongo_db, token: str) -> str:
    """Attach a Stripe Express account to planner. Return account id.

    Two paths:
      A) API-create — fast, no UI round-trip. Requires the platform test
         account to be signed up for Connect. If that hasn't been done, the
         Stripe API rejects with a setup-link error; we surface that and
         offer path B instead of dumping a stack trace.
      B) Manual — driver pauses; user opens the running app and completes
         the actual /stripe/connect/onboard flow in Chrome. Driver polls
         /stripe/connect/status until status='connected'. This validates
         the production-style path end-to-end and works without any
         additional Stripe dashboard setup.
    """
    banner("CONNECT")

    user = mongo_db["users"].find_one({"email": PLANNER_EMAIL})
    if not user:
        raise RuntimeError("planner missing in Mongo after seed")

    # Path A: try API-create first.
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
                "mcc": "7299",  # Misc personal services
                "product_description": "Wedding planning services (test)",
            },
        )
        logger.info("  Created Stripe Express account: %s", account.id)

        mongo_db["users"].update_one(
            {"_id": user["_id"]}, {"$set": {"stripe_connect_id": account.id}}
        )
        logger.info("  Stored stripe_connect_id on planner user.")
        account_id = account.id

    except stripe.error.InvalidRequestError as exc:
        msg = str(exc)
        if "signed up for Connect" in msg or "dashboard.stripe.com/connect" in msg:
            # Setup gap — surface clearly and fall through to manual flow.
            logger.warning("─" * 72)
            logger.warning("  Stripe Connect is not enabled for this test account.")
            logger.warning("  One-time setup: visit")
            logger.warning("    https://dashboard.stripe.com/test/connect")
            logger.warning("  and click 'Get started' (free, ~30 seconds).")
            logger.warning("─" * 72)
            logger.warning("")
            logger.warning("  Falling back to MANUAL onboarding via the running app.")
            logger.warning(
                "  You will complete the actual /stripe/connect/onboard flow"
            )
            logger.warning("  in Chrome; the driver will poll until charges_enabled.")
            logger.warning("─" * 72)
            input(
                "→ Press ENTER to continue with manual onboarding (or Ctrl+C to abort)… "
            )
            account_id = _manual_onboard_and_poll(token)
        else:
            raise

    status = get_connect_status(token)
    logger.info("  /stripe/connect/status → %s", status)
    assert_eq("connect.status", status.get("status"), "connected")

    # Express accounts created via the API are NOT chargeable yet —
    # `charges_enabled` only flips to True after the planner walks the
    # Stripe-hosted onboarding flow. The frontend gate this driver verifies
    # reads `details_submitted && charges_enabled`, so we have to actually
    # complete onboarding before UI-2 can pass.
    if not status.get("charges_enabled"):
        logger.info("  Account is attached but charges_enabled=False.")
        logger.info("  Generating an Account Link for hosted onboarding…")
        link = stripe.AccountLink.create(
            account=account_id,
            refresh_url=f"{FRONTEND_URL}/admin/planner/billing",
            return_url=f"{FRONTEND_URL}/admin/planner/billing",
            type="account_onboarding",
        )
        logger.info("─" * 72)
        logger.info("  HOSTED ONBOARDING REQUIRED")
        logger.info("─" * 72)
        logger.info("  Open this URL in Chrome (paste into the address bar):")
        logger.info("")
        logger.info("    %s", link.url)
        logger.info("")
        logger.info("  Stripe lets you fill the form in test mode using the")
        logger.info(
            "  'Use test data' button at the top of each section. ~1 min total."
        )
        logger.info("  When Stripe redirects you back to the billing page,")
        logger.info("  return here and press ENTER.")
        logger.info("─" * 72)
        input("→ Press ENTER once Stripe has redirected you back… ")

        # Poll until charges_enabled flips. Stripe usually flips it within
        # a few seconds of the final form submit, but capability checks
        # can briefly trail.
        import time

        for attempt in range(1, 25):
            status = get_connect_status(token)
            if status.get("charges_enabled"):
                logger.info(
                    "  ✅ charges_enabled=True (poll %d/24): %s",
                    attempt,
                    status,
                )
                break
            logger.info(
                "  ⏳ charges_enabled=False (poll %d/24) — %s",
                attempt,
                status,
            )
            time.sleep(5)
        else:
            raise RuntimeError(
                "charges_enabled never flipped to True. Check the Stripe "
                "dashboard for missing requirements on this account."
            )

    return account_id


def _manual_onboard_and_poll(token: str, max_polls: int = 60, sleep_s: int = 5) -> str:
    """Fallback when API account creation isn't available.

    Asks the user to complete Stripe onboarding via the running app, then
    polls /stripe/connect/status until details_submitted=true. Returns
    the resolved account id.
    """
    import time

    logger.info("")
    logger.info("─" * 72)
    logger.info("  MANUAL ONBOARDING")
    logger.info("─" * 72)
    logger.info("  1. In Chrome, log in as %s", PLANNER_EMAIL)
    logger.info("  2. Navigate to %s/admin/planner/billing", FRONTEND_URL)
    logger.info("  3. Click the 'Couple Payments' tab → 'Connect Stripe account'.")
    logger.info("  4. Complete the Stripe Express onboarding (use any test data).")
    logger.info("  5. Stripe will redirect you back to the billing page.")
    logger.info("─" * 72)
    logger.info(
        "  Polling /stripe/connect/status every %ds for up to %ds…",
        sleep_s,
        max_polls * sleep_s,
    )

    for attempt in range(1, max_polls + 1):
        status = get_connect_status(token)
        if status.get("details_submitted"):
            logger.info("  ✅ details_submitted=True (poll %d/%d)", attempt, max_polls)
            from app.core.database import mongo  # noqa: F401  (may not be importable here)

            # Re-read user from Mongo to grab the connect id assigned by the app.
            from pymongo import MongoClient

            db = MongoClient(MONGO_URI)[MONGO_DB]
            user = db["users"].find_one({"email": PLANNER_EMAIL})
            connect_id = (user or {}).get("stripe_connect_id") or "unknown"
            return connect_id
        logger.info("  ⏳ details_submitted=False (poll %d/%d)", attempt, max_polls)
        time.sleep(sleep_s)

    raise RuntimeError("Timed out waiting for manual Stripe onboarding to complete.")


def phase_checkpoint_ui_enabled(connect_account_id: str) -> None:
    checkpoint(
        "UI-2 (gate released)",
        [
            "1. Hard-reload the planner billing page (Cmd+Shift+R).",
            "2. The 'Couple Payments' tab now shows the Connect card in",
            "   its 'connected' state with the green checkmark and",
            f"   account id {connect_account_id}.",
            "3. The 'Request payment' button is ENABLED (no opacity, no",
            "   tooltip on hover).",
            "4. The Payment Requests empty state now reads:",
            "   'No requests yet. Send one to collect a deposit, milestone,",
            "    or final balance from a couple.'",
            "5. The inline 'Request your first payment' secondary button",
            "   IS now shown.",
            "6. Click 'Request payment'. Modal opens with title",
            "   'Request a payment'. Description reads",
            "   'Create a payment request for one of your couples.'",
            "7. Pick any wedding, enter $42.00, click Create.",
            "8. Success view shows 'Link ready to share.' with the amount.",
            "9. Close the modal. The new row appears in Payment Requests",
            "   with amount '$42.00 USD' and status badge 'pending'.",
        ],
    )


def phase_assert_api(token: str) -> None:
    banner("ASSERT_API")
    rows = get_payment_requests(token)
    if not rows:
        raise AssertionError("expected at least one payment_requests row")
    latest = rows[0]
    logger.info("  Latest payment request: %r", latest)
    # Backend stores amount in DOLLARS (verified earlier in the review;
    # service layer multiplies by 100 only at the Stripe boundary).
    assert_truthy("payment_request.amount", latest.get("amount"))
    assert_eq("payment_request.amount", float(latest["amount"]), 42.0)
    assert_eq("payment_request.currency", latest.get("currency"), "usd")
    assert_eq("payment_request.status", latest.get("status"), "pending")


def known_finding_backend_gap() -> None:
    logger.info("")
    logger.info("=" * 72)
    logger.info("  KNOWN FINDING (not blocking this run)")
    logger.info("=" * 72)
    logger.info("  POST /stripe/create-payment-intent does not currently reject")
    logger.info("  when the caller has no stripe_connect_id. The frontend gate")
    logger.info("  verified above is the only thing preventing payment intents")
    logger.info("  from being created without transfer_data.destination set.")
    logger.info("  Server-side check should be added in stripe_payment.py around")
    logger.info("  line 700-715 to mirror the UI gate.")
    logger.info("=" * 72)


def main() -> int:
    client = MongoClient(MONGO_URI)
    mongo_db = client[MONGO_DB]

    token = phase_seed(mongo_db)
    phase_checkpoint_ui_disabled()
    account_id = phase_connect(mongo_db, token)
    phase_checkpoint_ui_enabled(account_id)
    phase_assert_api(token)
    known_finding_backend_gap()

    logger.info("")
    logger.info("✅ All checkpoints passed.")
    logger.info(
        "Run testbed/cleanup_couple_payments_gate_state.py to reset for next run."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
