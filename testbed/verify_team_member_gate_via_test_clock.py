#!/usr/bin/env python3
"""
PR1 Team-Member Gate — Live Verification via Stripe Test Clock
================================================================

Purpose
-------
Verify end-to-end that when a planner's Stripe subscription transitions to
a blocked status (past_due via failed renewal), every team-member under that
planner is also blocked — including profile hydration, planner-area API calls,
the /admin proxy redirect, and the frontend `billingBlockTarget` navigation
policy. And that when the subscription recovers, they become unblocked again.

The flow uses REAL Stripe test-clock time travel (no manual Mongo flag flips)
so the failing-charge webhook fires for real and Stripe sends a real dunning
email to the planner's Cloudflare-routed alias.

Accounts (both plus-variants; base accounts never touched)
----------------------------------------------------------
  Planner       : test_planner2+teamgate@thespecialwedding.io
  Team member   : test_team_member+teamgate@thespecialwedding.io

Stripe test clock
-----------------
  Preferred legacy id: clock_1TNGs4JbfaNLE8qUOMEjk2ZU
  Fallback name      : team-member-gate

The legacy clock id is reused when it exists. If that id has been deleted from
Stripe test mode, the driver reuses or creates a named replacement clock so the
verification can still run from a clean sandbox.

Phases
------
  SEED  — register planner on clock, subscribe with good card, invite +
          accept team member. Planner active. Team member unblocked.
  FAIL  — swap default PM to will-fail card 4000 0000 0000 0341, advance
          clock past renewal. Renewal charge fails → webhook → past_due.
          Stripe sends a real dunning email to the planner alias. The driver
          asserts stale team-member sessions and planner feature routes 402,
          then pauses for Chrome + Gmail `billingBlockTarget` review.
  FIX   — swap PM back to 4242, advance clock. Stripe retry succeeds →
          subscription returns to active. Team member unblocked again.

The script pauses between phases. It will NOT advance without explicit
Enter confirmation at each checkpoint, per the "live verification before
anything can be checked as completed" rule.

Usage
-----
    python testbed/verify_team_member_gate_via_test_clock.py

Requirements
------------
  - Backend running at localhost:8000 (or BACKEND_URL)
  - Frontend running at FRONTEND_URL, or at TESTBED_FRONTEND_PORT / localhost:3000
  - Stripe CLI forwarding: stripe listen --forward-to localhost:8000/stripe/webhook
  - STRIPE_SECRET_KEY in .env
  - MongoDB reachable at MONGO_URI / MONGO_DB
"""

from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Add project root to path (so "from app..." works if ever needed)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
import stripe
from dotenv import load_dotenv
from pymongo import MongoClient

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("verify_gate")

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


def _default_frontend_url() -> str:
    return f"http://localhost:{os.getenv('TESTBED_FRONTEND_PORT', '3000')}"


FRONTEND_URL = os.getenv("FRONTEND_URL", _default_frontend_url())
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")
MONGO_DB = os.getenv("MONGO_DB") or os.getenv("MONGO_NAME", "wedding")

ADMIN_EMAIL = os.getenv("ROOT_ADMIN_EMAIL", "thedeveloper@thespecialwedding.io")
ADMIN_PASSWORD = os.getenv("ROOT_ADMIN_PASSWORD")

PLANNER_EMAIL = "test_planner2+teamgate@thespecialwedding.io"
PLANNER_PASSWORD = "TeamGatePlanner2026!"  # pragma: allowlist secret
TEAM_MEMBER_EMAIL = "test_team_member+teamgate@thespecialwedding.io"
TEAM_MEMBER_PASSWORD = "TeamGateMember2026!"  # pragma: allowlist secret

LEGACY_TEST_CLOCK_ID = "clock_1TNGs4JbfaNLE8qUOMEjk2ZU"
TEST_CLOCK_NAME = "team-member-gate"
TEST_CLOCK_ID = os.getenv("TEAM_MEMBER_GATE_CLOCK_ID", LEGACY_TEST_CLOCK_ID)
PLAN_ID = "plan_signature"

# Stripe test PaymentMethod tokens.
# We use pre-built test PM tokens rather than raw card dicts because this
# account (correctly) does not have raw-card-data API access enabled.
# See: https://docs.stripe.com/testing#cards
PM_TOKEN_GOOD = "pm_card_visa"  # 4242, always succeeds
# pm_card_chargeCustomerFail maps to 4000 0000 0000 0341 — initial charge
# succeeds but all subsequent renewal charges fail. This is the token Stripe
# recommends for simulating past_due via test clocks.
PM_TOKEN_WILL_FAIL_ON_RENEWAL = "pm_card_chargeCustomerFail"

WEBHOOK_SETTLE_SECONDS = 10

BILLING_BLOCK_TARGET_E2E_CHECKPOINTS = (
    {
        "marker": "BILLING_TARGET_PLANNER_SOFT_NAV",
        "expectations": (
            "Chrome: as the blocked PLANNER, open /admin and /admin/guests; "
            "billingBlockTarget must send both to /admin/planner/billing.",
            "Chrome: trigger guests quick-remind, guest list, or table list "
            "raw-fetch 402 handling; expect the same /admin/planner/billing "
            "target with no route-local fallback.",
            "Chrome devtools: the planner path should preserve the fresh "
            "session and avoid duplicate generic billing toasts.",
        ),
    },
    {
        "marker": "BILLING_TARGET_TEAM_MEMBER_LOGOUT",
        "expectations": (
            "Chrome: if the TEAM MEMBER session from CHECKPOINT 0 is still "
            "open, reload /admin or /admin/guests; profile hydration should "
            "derive a logout billingBlockTarget.",
            "Chrome: blocked team-member navigation must land on "
            "/admin/login?error=... and must not visit /admin/planner/billing.",
            "Chrome: fresh team-member login still receives the 402 inline "
            "owner-subscription message and no admin_token cookie is issued.",
        ),
    },
)

# ---------------------------------------------------------------------------
# Guard rails
# ---------------------------------------------------------------------------

if not STRIPE_SECRET_KEY:
    logger.error("STRIPE_SECRET_KEY is not set in .env")
    sys.exit(1)

if not ADMIN_PASSWORD:
    logger.error("ROOT_ADMIN_PASSWORD is not set in .env")
    sys.exit(1)

if not MONGO_URI:
    logger.error("MONGO_URI / MONGODB_URI is not set in .env")
    sys.exit(1)

stripe.api_key = STRIPE_SECRET_KEY

# ---------------------------------------------------------------------------
# Mongo helpers — used to (a) link Stripe customer to planner user, and
# (b) read the team-member invite token so the script can accept without
# waiting on email delivery.
# ---------------------------------------------------------------------------

mongo = MongoClient(MONGO_URI)[MONGO_DB]


def link_stripe_customer(user_id: str, email: str, customer_id: str) -> None:
    """Upsert the users + stripe_customers mapping so webhooks resolve."""
    from bson import ObjectId

    mongo["stripe_customers"].update_one(
        {"stripe_customer_id": customer_id},
        {
            "$set": {
                "stripe_customer_id": customer_id,
                "user_id": user_id,
                "email": email,
                "source": "verify_team_member_gate_via_test_clock",
                "updated_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )

    mongo["users"].update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"stripe_customer_id": customer_id}},
    )


def read_invite_token_from_mongo(owner_id: str, member_email: str) -> str:
    """Pull the plaintext invite_token for the pending team member so we can
    accept without waiting on email delivery."""
    doc = mongo["team_members"].find_one(
        {"owner_id": owner_id, "email": member_email.lower(), "status": "pending"}
    )
    if not doc or not doc.get("invite_token"):
        raise RuntimeError(
            f"Could not read invite_token for {member_email} — doc={doc!r}"
        )
    return doc["invite_token"]


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def api_post(path: str, *, token: Optional[str] = None, json: Optional[dict] = None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    resp = requests.post(f"{BACKEND_URL}{path}", headers=headers, json=json or {})
    return resp


def api_get(path: str, *, token: Optional[str] = None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    resp = requests.get(f"{BACKEND_URL}{path}", headers=headers)
    return resp


def get_admin_token() -> str:
    resp = api_post(
        "/admin/token",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_planner_token() -> str:
    resp = api_post(
        "/admin/token",
        json={"email": PLANNER_EMAIL, "password": PLANNER_PASSWORD},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_team_member_token() -> str:
    resp = api_post(
        "/admin/token",
        json={"email": TEAM_MEMBER_EMAIL, "password": TEAM_MEMBER_PASSWORD},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# Console helpers
# ---------------------------------------------------------------------------


def banner(title: str) -> None:
    line = "=" * 72
    logger.info("")
    logger.info(line)
    logger.info(f"  {title}")
    logger.info(line)


def pause_for_user(prompt: str) -> None:
    logger.info("")
    logger.info("─" * 72)
    logger.info(prompt)
    logger.info("─" * 72)
    input("→ Press ENTER once you've verified this checkpoint in Chrome / Gmail… ")


def wait_for_webhooks(seconds: int = WEBHOOK_SETTLE_SECONDS) -> None:
    logger.info(f"  ⏳ Waiting {seconds}s for Stripe webhooks to settle…")
    time.sleep(seconds)


def wait_for_clock_ready(clock_id: str, max_polls: int = 20) -> None:
    for attempt in range(1, max_polls + 1):
        clock = stripe.test_helpers.TestClock.retrieve(clock_id)
        if clock.status == "ready":
            logger.info(f"  ✅ Clock ready (poll {attempt}/{max_polls})")
            return
        logger.info(f"  ⏳ Clock status={clock.status} (poll {attempt}/{max_polls})")
        time.sleep(5)
    raise RuntimeError(f"Clock {clock_id} never reached ready state")


def resolve_test_clock():
    """Return the reusable team-member-gate Stripe test clock.

    Older runs pinned a concrete test-clock id. Stripe test clocks can be
    deleted from the dashboard, so a dead id should not make the whole live
    verifier unusable. Prefer the configured/legacy id, then a named clock,
    then create a replacement.
    """
    global TEST_CLOCK_ID

    try:
        clock = stripe.test_helpers.TestClock.retrieve(TEST_CLOCK_ID)
        return clock
    except stripe.error.InvalidRequestError as exc:
        if getattr(exc, "code", None) != "resource_missing":
            raise
        logger.warning(
            f"  ⚠️ Configured test clock {TEST_CLOCK_ID} is missing; "
            f"looking for a named {TEST_CLOCK_NAME!r} replacement…"
        )

    for clock in stripe.test_helpers.TestClock.list(limit=100).auto_paging_iter():
        if getattr(clock, "name", None) == TEST_CLOCK_NAME and clock.status == "ready":
            TEST_CLOCK_ID = clock.id
            logger.info(f"  ✅ Reusing named test clock {TEST_CLOCK_ID}")
            return clock

    clock = stripe.test_helpers.TestClock.create(
        name=TEST_CLOCK_NAME,
        frozen_time=int(time.time()),
    )
    TEST_CLOCK_ID = clock.id
    logger.info(f"  ✅ Created replacement test clock {TEST_CLOCK_ID}")
    wait_for_clock_ready(TEST_CLOCK_ID)
    return stripe.test_helpers.TestClock.retrieve(TEST_CLOCK_ID)


def format_billing_block_target_checkpoint() -> str:
    lines = [
        "",
        "  Task #20 billingBlockTarget E2E checkpoints:",
    ]
    for checkpoint in BILLING_BLOCK_TARGET_E2E_CHECKPOINTS:
        lines.append("")
        lines.append(f"  [{checkpoint['marker']}]")
        for expectation in checkpoint["expectations"]:
            lines.append(f"    - {expectation}")
    return "\n".join(lines)


def expect_status(resp, expected_status: int, label: str) -> None:
    if resp.status_code != expected_status:
        raise RuntimeError(
            f"{label} expected HTTP {expected_status}, got "
            f"{resp.status_code}: {resp.text[:500]}"
        )


def expect_profile_blocked(resp, label: str) -> dict:
    expect_status(resp, 200, label)
    payload = resp.json()
    if payload.get("_subscription_blocked") is not True:
        raise RuntimeError(f"{label} did not expose _subscription_blocked=true")
    return payload


def assert_fail_phase_billing_gate_state(state: dict) -> None:
    """Backend-observable half of the task #20 E2E scenario.

    Chrome owns the visible navigation assertion, but the live driver should
    still prove the server state that feeds `billingBlockTarget`: planner
    profile is fresh/blocked, stale team-member profile is fresh/blocked,
    feature routes 402, and fresh team-member login is denied.
    """
    logger.info("Asserting task #20 billing-block backend state…")

    planner_token = get_planner_token()
    planner_profile = expect_profile_blocked(
        api_get("/admin/profile", token=planner_token),
        "planner /admin/profile on past_due",
    )
    planner_status = planner_profile.get("subscription_status")
    if planner_status not in ("past_due", "unpaid"):
        raise RuntimeError(
            "planner profile should expose a blocked subscription_status, "
            f"got {planner_status!r}"
        )
    expect_status(
        api_get("/admin/weddings", token=planner_token),
        402,
        "planner /admin/weddings on past_due",
    )
    logger.info("  ✅ Planner profile is fresh/blocked; feature route returns 402")

    team_member_token = state.get("team_member_active_token")
    if not team_member_token:
        raise RuntimeError("seed phase did not preserve a team-member token")

    team_profile = expect_profile_blocked(
        api_get("/admin/profile", token=team_member_token),
        "stale team-member /admin/profile after owner past_due",
    )
    user_data = team_profile.get("user_data") or {}
    if user_data.get("_blocked_reason_source") != "owner_subscription":
        raise RuntimeError(
            "team-member profile should identify owner_subscription as the "
            f"block source, got {user_data.get('_blocked_reason_source')!r}"
        )
    team_weddings = api_get("/admin/weddings", token=team_member_token)
    expect_status(
        team_weddings,
        402,
        "stale team-member /admin/weddings after owner past_due",
    )
    if "contact your planner" not in team_weddings.text.lower():
        raise RuntimeError(
            "team-member feature 402 should direct them to contact their planner"
        )
    logger.info("  ✅ Stale team-member profile is blocked; feature route returns 402")

    fresh_login = api_post(
        "/admin/token",
        json={"email": TEAM_MEMBER_EMAIL, "password": TEAM_MEMBER_PASSWORD},
    )
    expect_status(fresh_login, 402, "fresh team-member login after owner past_due")
    if "contact your planner" not in fresh_login.text.lower():
        raise RuntimeError(
            "team-member login 402 should direct them to contact their planner"
        )
    logger.info("  ✅ Fresh team-member login is denied with owner billing message")


# ---------------------------------------------------------------------------
# Phase helpers
# ---------------------------------------------------------------------------


def find_user_id_by_email(admin_token: str, email: str) -> str:
    """Uses admin /users endpoint. Handles the {users:[...]} envelope."""
    resp = api_get("/users", token=admin_token)
    resp.raise_for_status()
    payload = resp.json()
    users = payload.get("users") if isinstance(payload, dict) else payload
    for u in users or []:
        if u.get("email", "").lower() == email.lower():
            return u["_id"]
    raise RuntimeError(f"User {email} not found via /users")


def _read_plan_price_monthly(admin_token: str, plan_id: str) -> str | None:
    """Read the monthly Stripe price_id for a plan via the ROOT_ADMIN endpoint.

    The PUBLIC endpoint (/public/subscription-plans) deliberately sanitizes
    out every stripe_*_id field to avoid leaking internal identifiers; it
    will NEVER return a price_id even for a fully-synced plan. So we hit the
    admin list endpoint, which preserves the raw plan document.
    """
    resp = api_get("/subscription-plans?include_inactive=true", token=admin_token)
    resp.raise_for_status()
    payload = resp.json()
    plans = payload if isinstance(payload, list) else payload.get("plans") or []
    for p in plans:
        if p.get("_id") == plan_id or p.get("id") == plan_id:
            return p.get("stripe_price_id_monthly") or None
    return None


def fetch_stripe_price_id(admin_token: str, plan_id: str) -> str:
    price = _read_plan_price_monthly(admin_token, plan_id)
    if price:
        return price

    # Plan exists in Mongo but hasn't been synced to Stripe yet (or was
    # seeded in a fresh env and never linked). Call the admin sync endpoint
    # once — it's idempotent and only does real work for plans missing
    # Stripe IDs — then re-read.
    logger.info(
        f"  ⚠️ plan {plan_id} has no stripe_price_id_monthly — "
        f"syncing all plans to Stripe and retrying…"
    )
    sync_resp = api_post("/system/sync-plans-to-stripe", token=admin_token)
    if sync_resp.status_code not in (200, 201):
        raise RuntimeError(
            f"/system/sync-plans-to-stripe failed: {sync_resp.status_code} {sync_resp.text}"
        )
    sync_payload = sync_resp.json()
    logger.info(f"  ✅ sync response: {sync_payload.get('message')}")
    if sync_payload.get("errors"):
        logger.warning(f"  ⚠️ sync reported errors: {sync_payload['errors']}")

    price = _read_plan_price_monthly(admin_token, plan_id)
    if price:
        return price

    raise RuntimeError(
        f"No Stripe monthly price_id for plan {plan_id} even after /system/sync-plans-to-stripe — "
        f"check that the plan exists in Mongo and that STRIPE_SECRET_KEY is correct on the backend."
    )


def attach_payment_method(customer_id: str, pm_token: str) -> str:
    """Attach a pre-built Stripe test PaymentMethod token to the customer and
    set it as the default invoice PM.

    We take a token string (e.g. ``pm_card_visa``) rather than a raw card
    dict because this Stripe account does not have raw-card-data API access
    enabled — the safer default per Stripe's PCI guidance. The pre-built
    tokens at https://docs.stripe.com/testing#cards are the sanctioned way
    to simulate cards in test mode.
    """
    pm = stripe.PaymentMethod.attach(pm_token, customer=customer_id)
    stripe.Customer.modify(
        customer_id,
        invoice_settings={"default_payment_method": pm.id},
    )
    return pm.id


# ---------------------------------------------------------------------------
# SEED — fresh planner + subscription + invited + accepted team member
# ---------------------------------------------------------------------------


def seed_phase(admin_token: str) -> dict:
    banner("PHASE 1 — SEED  (planner on clock, good card, team member accepted)")

    # 1. Create fresh Stripe customer on the existing clock.
    logger.info(f"Creating Stripe customer on clock {TEST_CLOCK_ID}…")
    customer = stripe.Customer.create(
        email=PLANNER_EMAIL,
        name="TeamGate Planner",
        test_clock=TEST_CLOCK_ID,
        metadata={
            "purpose": "verify_team_member_gate",
            "plan_id": PLAN_ID,
        },
    )
    logger.info(f"  ✅ Stripe customer: {customer.id}")

    # 2. Register planner in backend (plus-variant is a fresh Mongo user).
    resp = api_post(
        "/public/register",
        json={
            "email": PLANNER_EMAIL,
            "password": PLANNER_PASSWORD,
            "first_name": "TeamGate",
            "last_name": "Planner",
            "company_name": "TeamGate QA Co",
            "selected_plan_id": PLAN_ID,
            "role": "wedding_planner",
        },
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Planner register failed: {resp.status_code} {resp.text}")
    logger.info(f"  ✅ Planner registered: {PLANNER_EMAIL}")

    # 3. Resolve user_id and activate through admin so email-verification gate
    #    does not block login.
    user_id = find_user_id_by_email(admin_token, PLANNER_EMAIL)
    api_post(f"/users/{user_id}/activate", token=admin_token).raise_for_status()
    logger.info(f"  ✅ Planner activated (user_id={user_id})")

    # /users/{id}/activate only flips is_active — it does NOT set
    # email_verified=True. Because /public/register marks users with
    # registration_source="public_signup", auth_service.authenticate_user
    # rejects login with 401 "Please verify your email address" until that
    # flag is flipped. Flip it directly so this harness doesn't need a real
    # email round-trip.
    from bson import ObjectId

    mongo["users"].update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"email_verified": True}},
    )
    logger.info("  ✅ Planner email_verified=True (test harness bypass)")

    # 4. Link Stripe customer ↔ planner user so the webhook resolves.
    link_stripe_customer(user_id, PLANNER_EMAIL, customer.id)
    logger.info("  ✅ stripe_customers link upserted")

    # 5. Attach the GOOD card first (this phase proves team member is
    #    unblocked when planner is active).
    attach_payment_method(customer.id, PM_TOKEN_GOOD)
    logger.info("  ✅ Good card attached as default PM (4242…)")

    # 6. Create subscription. No trial → charges immediately → success →
    #    subscription.status = active → webhook → user.subscription_status = active.
    price_id = fetch_stripe_price_id(admin_token, PLAN_ID)
    subscription = stripe.Subscription.create(
        customer=customer.id,
        items=[{"price": price_id}],
        metadata={
            "user_id": user_id,
            "plan_id": PLAN_ID,
            "billing_interval": "monthly",
            "purpose": "verify_team_member_gate",
        },
        payment_settings={"save_default_payment_method": "on_subscription"},
    )
    logger.info(f"  ✅ Subscription: {subscription.id} ({subscription.status})")
    wait_for_webhooks()

    # 7. Planner logs in and invites team member.
    planner_token = get_planner_token()
    invite_resp = api_post(
        "/admin/team/invite",
        token=planner_token,
        json={
            "email": TEAM_MEMBER_EMAIL,
            "role": "editor",
            "wedding_access": "all",
        },
    )
    if invite_resp.status_code not in (200, 201):
        raise RuntimeError(
            f"invite failed: {invite_resp.status_code} {invite_resp.text}"
        )
    logger.info(f"  ✅ Team member invited: {TEAM_MEMBER_EMAIL}")

    # 8. Pull the invite token out of Mongo and accept programmatically.
    invite_token = read_invite_token_from_mongo(user_id, TEAM_MEMBER_EMAIL)
    accept_resp = api_post(
        "/admin/team/accept-invite",
        json={
            "token": invite_token,
            "first_name": "TeamGate",
            "last_name": "Member",
            "password": TEAM_MEMBER_PASSWORD,
        },
    )
    if accept_resp.status_code not in (200, 201):
        raise RuntimeError(
            f"accept-invite failed: {accept_resp.status_code} {accept_resp.text}"
        )
    logger.info(f"  ✅ Team member accepted: {TEAM_MEMBER_EMAIL}")

    # 9. Capture a real active-session team-member token before FAIL. After
    #    the owner goes past_due, fresh login is intentionally denied; this
    #    token lets the driver prove stale-session profile hydration and
    #    feature-route 402 behavior end-to-end.
    team_member_token = get_team_member_token()
    team_profile = api_get("/admin/profile", token=team_member_token)
    expect_status(team_profile, 200, "team-member /admin/profile during SEED")
    if team_profile.json().get("_subscription_blocked") is True:
        raise RuntimeError("team member is unexpectedly blocked during SEED")
    logger.info("  ✅ Team member active-session token captured for FAIL checks")

    return {
        "customer_id": customer.id,
        "subscription_id": subscription.id,
        "planner_user_id": user_id,
        "team_member_active_token": team_member_token,
    }


# ---------------------------------------------------------------------------
# FAIL — swap PM to will-fail, advance clock, confirm past_due + dunning email
# ---------------------------------------------------------------------------


def fail_phase(state: dict) -> None:
    banner("PHASE 2 — FAIL  (swap PM → will-fail card, advance clock, past_due)")

    customer_id = state["customer_id"]
    subscription_id = state["subscription_id"]

    # 1. Swap default payment method to the "succeed-then-fail" card.
    #    We have to update BOTH the customer's invoice_settings.default_payment_method
    #    AND the subscription's own default_payment_method. The SEED-phase
    #    Subscription.create() call passed `save_default_payment_method=on_subscription`,
    #    which pinned pm_card_visa onto the subscription itself after the first
    #    successful charge. For renewals, subscription.default_payment_method
    #    wins over customer.invoice_settings.default_payment_method. If we
    #    only swap the customer default, the +33-day renewal still bills the
    #    good card, succeeds, and the subscription stays active — which is
    #    exactly the false-negative we hit on the first FAIL run.
    logger.info("Swapping default PM to 4000 0000 0000 0341 (renewal will fail)…")
    pm_id = attach_payment_method(customer_id, PM_TOKEN_WILL_FAIL_ON_RENEWAL)
    stripe.Subscription.modify(subscription_id, default_payment_method=pm_id)
    logger.info(f"  ✅ Will-fail card pinned on customer + subscription ({pm_id})")

    # 2. Advance the clock past the next billing period. Signature is monthly,
    #    so ~33 days forward triggers a renewal attempt.
    #
    # NB: the test clock is *reused across runs* (see module docstring), so its
    # frozen_time drifts forward past wall-clock on every successful run. We
    # anchor the advance to the clock's current frozen_time, never to
    # `datetime.now()` — otherwise the second run on the same clock explodes
    # with "Test clocks can only be advanced forward in time."
    current_frozen = stripe.test_helpers.TestClock.retrieve(TEST_CLOCK_ID).frozen_time
    if not current_frozen:
        raise RuntimeError(
            f"Test clock {TEST_CLOCK_ID} has no frozen_time; cannot compute advance target."
        )
    target_ts = int(current_frozen) + 33 * 86400
    logger.info(
        f"Advancing clock from {datetime.fromtimestamp(int(current_frozen), tz=timezone.utc).isoformat()}"
        f" to {datetime.fromtimestamp(target_ts, tz=timezone.utc).isoformat()}"
        " (+33 days) to trigger renewal…"
    )
    stripe.test_helpers.TestClock.advance(TEST_CLOCK_ID, frozen_time=target_ts)
    wait_for_clock_ready(TEST_CLOCK_ID)
    wait_for_webhooks(15)

    # 3. Confirm Stripe sees the subscription as past_due.
    sub = stripe.Subscription.retrieve(subscription_id)
    logger.info(f"  📋 Stripe subscription status: {sub.status}")
    logger.info(f"  📋 Latest invoice id        : {sub.latest_invoice}")
    if sub.latest_invoice:
        try:
            inv = stripe.Invoice.retrieve(sub.latest_invoice)
            # Stripe's newer API dropped `Invoice.paid` (replaced by `status`
            # == "paid" and amount_paid/amount_remaining). Use getattr() so
            # SDKs that model StripeObject without dict.get() support keep this
            # diagnostic from aborting the verification run.
            inv_status = getattr(inv, "status", None)
            inv_attempts = getattr(inv, "attempt_count", None)
            inv_paid = getattr(inv, "paid", inv_status == "paid")
            logger.info(
                f"  📋 Latest invoice status    : {inv_status} "
                f"(attempt_count={inv_attempts}, paid={inv_paid})"
            )
        except stripe.error.StripeError as exc:
            logger.warning(f"  ⚠️ Could not retrieve latest invoice: {exc}")
    if sub.status not in ("past_due", "unpaid"):
        logger.warning(
            "  ⚠️ Subscription did not transition to past_due/unpaid — check Stripe"
            " retry settings or webhook forwarding."
        )

    # 4. Assert backend-observable billing-block state before the browser
    #    checkpoint. This is the scripted half of the task #20 E2E scenario.
    assert_fail_phase_billing_gate_state(state)

    # 5. Checkpoint — user confirms in Gmail + Chrome.
    pause_for_user(
        "CHECKPOINT A — Verify the FAIL state.\n"
        "\n"
        "  Expected behavior changed: team-member login is now BLOCKED at\n"
        "  `POST /admin/token` when the owning planner's subscription is in a\n"
        "  blocked status (past_due / suspended / expired / cancelled).\n"
        "  No session is minted. No dashboard ever loads.\n"
        "\n"
        "  1. Gmail (ojaplusdevplatforms@gmail.com): confirm Stripe dunning email\n"
        f"     arrived for {PLANNER_EMAIL}.\n"
        "\n"
        "  2. Chrome tab (frontend): attempt to log in as the TEAM MEMBER —\n"
        f"        email    : {TEAM_MEMBER_EMAIL}\n"
        f"        password : {TEAM_MEMBER_PASSWORD}\n"
        "     Expect: 402 from `POST /admin/token`, login form stays on /admin/login,\n"
        "             inline error message reads roughly:\n"
        "               \"Your team's subscription requires attention (status: past_due).\n"
        f'                Please contact your planner at {PLANNER_EMAIL} to restore access."\n'
        "             No `admin_token` cookie is issued.\n"
        "             No /admin/profile, /admin/weddings, /notifications/stream calls fire.\n"
        "\n"
        "  3. Chrome tab (frontend): log in as the PLANNER —\n"
        f"        email    : {PLANNER_EMAIL}\n"
        f"        password : {PLANNER_PASSWORD}\n"
        "     Expect: login succeeds, planner is routed to /admin/planner/billing\n"
        "             with a past_due banner and CTA to update the card."
        f"{format_billing_block_target_checkpoint()}"
    )


# ---------------------------------------------------------------------------
# FIX — swap back to 4242, advance clock, confirm active + unblocked
# ---------------------------------------------------------------------------


def fix_phase(state: dict) -> None:
    banner("PHASE 3 — FIX   (swap PM → 4242, advance clock, back to active)")

    customer_id = state["customer_id"]
    subscription_id = state["subscription_id"]

    # 1. Swap back to the good card on BOTH customer and subscription.
    #    See fail_phase for why subscription.default_payment_method has to be
    #    set explicitly — save_default_payment_method=on_subscription pinned
    #    the failing card onto the subscription during FAIL, and we need the
    #    retry to bill the good card now.
    pm_id = attach_payment_method(customer_id, PM_TOKEN_GOOD)
    stripe.Subscription.modify(subscription_id, default_payment_method=pm_id)
    logger.info(f"  ✅ 4242 card pinned on customer + subscription ({pm_id})")

    # 2. Nudge the clock forward so Stripe's retry schedule re-attempts the
    #    open invoice. A few days is enough under default retry settings.
    #
    # Same clock-drift rule as the FAIL phase: anchor to the current frozen
    # time of the reused test clock, not wall-clock. Original intent was
    # "+40 days from wall-now" which was effectively "+7 days past where FAIL
    # left the clock" — keep that same ~7-day nudge here.
    current_frozen = stripe.test_helpers.TestClock.retrieve(TEST_CLOCK_ID).frozen_time
    if not current_frozen:
        raise RuntimeError(
            f"Test clock {TEST_CLOCK_ID} has no frozen_time; cannot compute advance target."
        )
    target_ts = int(current_frozen) + 7 * 86400
    logger.info(
        f"Advancing clock from {datetime.fromtimestamp(int(current_frozen), tz=timezone.utc).isoformat()}"
        f" to {datetime.fromtimestamp(target_ts, tz=timezone.utc).isoformat()}"
        " (+7 days past FAIL) to trigger retry…"
    )
    stripe.test_helpers.TestClock.advance(TEST_CLOCK_ID, frozen_time=target_ts)
    wait_for_clock_ready(TEST_CLOCK_ID)
    wait_for_webhooks(15)

    # 3. If Stripe didn't auto-retry in that window, force it on the open
    #    invoice so the subscription can reach active again.
    sub = stripe.Subscription.retrieve(subscription_id)
    if sub.status != "active":
        logger.info(
            f"  Subscription still {sub.status} — forcing invoice retry on latest open invoice…"
        )
        invoices = stripe.Invoice.list(
            customer=customer_id, subscription=subscription_id, status="open", limit=1
        )
        if invoices.data:
            inv = invoices.data[0]
            try:
                stripe.Invoice.pay(inv.id)
                logger.info(f"  ✅ Forced pay on invoice {inv.id}")
            except stripe.error.StripeError as exc:
                logger.warning(f"  ⚠️ Forced pay failed: {exc.user_message or exc}")
            wait_for_webhooks(10)
            sub = stripe.Subscription.retrieve(subscription_id)

    logger.info(f"  📋 Stripe subscription status now: {sub.status}")

    pause_for_user(
        "CHECKPOINT B — Verify the FIX state.\n"
        "\n"
        "  There's no team-member session to 'reload' from FAIL — login was\n"
        "  refused at /admin/token. So we log in FRESH as team member and\n"
        "  confirm the gate has cleared.\n"
        "\n"
        "  1. Chrome: log in FRESH as TEAM MEMBER —\n"
        f"        email    : {TEAM_MEMBER_EMAIL}\n"
        f"        password : {TEAM_MEMBER_PASSWORD}\n"
        "     Expect: login succeeds, /admin/profile returns normally with\n"
        "             _subscription_blocked = false, planner-area calls succeed.\n"
        "\n"
        "  2. Chrome: reload the PLANNER session.\n"
        "     Expect: no past_due banner, subscription_status = active."
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    banner("PR1 TEAM-MEMBER GATE — LIVE VERIFICATION")
    logger.info(f"  Backend         : {BACKEND_URL}")
    logger.info(f"  Frontend        : {FRONTEND_URL}")
    logger.info(f"  Mongo DB        : {MONGO_DB}")
    logger.info(f"  Planner email   : {PLANNER_EMAIL}")
    logger.info(f"  Team member     : {TEAM_MEMBER_EMAIL}")
    logger.info(f"  Plan            : {PLAN_ID}")

    # Backend reachability.
    try:
        health = requests.get(f"{BACKEND_URL}/health", timeout=5)
        if health.status_code != 200:
            logger.error(f"Backend /health returned {health.status_code}")
            return 1
    except requests.RequestException as exc:
        logger.error(f"Cannot reach backend: {exc}")
        return 1
    logger.info("  ✅ Backend healthy")

    # Confirm the clock exists and is live.
    try:
        clock = resolve_test_clock()
    except stripe.error.StripeError as exc:
        logger.error(f"Cannot retrieve test clock {TEST_CLOCK_ID}: {exc}")
        return 1
    logger.info(f"  Test clock      : {TEST_CLOCK_ID}")
    logger.info(
        f"  ✅ Clock live — status={clock.status} frozen_at="
        f"{datetime.fromtimestamp(clock.frozen_time, tz=timezone.utc).isoformat()}"
    )

    admin_token = get_admin_token()
    logger.info("  ✅ Admin token acquired")

    state = seed_phase(admin_token)

    pause_for_user(
        "CHECKPOINT 0 — Verify the SEED state (optional but useful).\n"
        "\n"
        "  1. Chrome: log in as TEAM MEMBER —\n"
        f"        email    : {TEAM_MEMBER_EMAIL}\n"
        f"        password : {TEAM_MEMBER_PASSWORD}\n"
        "     Expect: _subscription_blocked = false; features accessible.\n"
        "\n"
        "  Press ENTER to begin the FAIL phase (clock will advance)."
    )

    fail_phase(state)
    fix_phase(state)

    banner("VERIFICATION COMPLETE — leaving accounts + clock intact for cleanup")
    logger.info(f"  Stripe customer : {state['customer_id']}")
    logger.info(f"  Subscription    : {state['subscription_id']}")
    logger.info(f"  Planner user_id : {state['planner_user_id']}")
    logger.info(
        "  The test clock was NOT deleted (preserved for re-use per user instruction)."
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        logger.error(f"Verification aborted: {exc}", exc_info=True)
        sys.exit(1)
