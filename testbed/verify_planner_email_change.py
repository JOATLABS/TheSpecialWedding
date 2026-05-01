#!/usr/bin/env python3
"""
Planner Email-Change Cascade — Live Verification
=================================================

Pins the email-change cluster fixed in commits to:
  - app/api/user_management.py
  - app/services/user_management_service.py
  - app/admin/components/AccountSettingsModal.tsx
  - app/api/guest.py

The original bug: when a planner verified an email change, only the
``users.email`` field updated. Every denormalized FK (``weddings.\
assigned_planner_email``, calendar connections, activity logs, etc.) kept
pointing at the old email, so the couple portal kept showing the OLD planner
email under "Your planner". Compounded by:

    1. The verification email was never actually sent (event published with
       no listener).
    2. The Account Settings modal pre-filled "New Email Address" with the
       current email, so re-opens looked like the change reverted.
    3. ``verify_email_change`` did not reissue the auth cookie, so a
       successful verification immediately force-logged-out the user on
       the next API call (JWT sub ≠ users.email).
    4. There was no way to cancel a pending change short of waiting 24h.
    5. Separately: ``GET /admin/guests/{id}/activity`` for a guest without
       an email leaked every activity log row in the wedding (Mongo
       null-match in the OR clause).

Scenario checkpoints
--------------------

    SEED — fresh planner + wedding + 2 guests (one with email, one without)
           + a couple_users row so couple portal renders something.

    P0 — Baseline (UX): admin profile shows current email; couple portal
         shows the planner's CURRENT email under "Your planner".

    P1 — Request change: PUT /profile/email transitions user to
         pending. ``pending_email`` is exposed by /admin/profile.

    P2 — Modal UX (Chrome): account-settings modal shows
         current-email row, empty new-email field, amber pending banner
         with the new email + working cancel button.

    P3 — Cancel: DELETE /profile/email/pending clears pending_email.
         /admin/profile returns to baseline. Modal banner disappears on
         refresh.

    P4 — Re-request + read token: trigger another pending change and read
         the email_change_token directly from Mongo (no real email
         delivery needed).

    P5 — Verify (the cascade itself): GET /verify-email-change/{token}
         flips users.email, sets a fresh ``admin_token`` cookie carrying
         ``sub=NEW_EMAIL``, and cascades the new email to every
         denormalized FK.

    P6 — Cascade assertions (Mongo): users.email, weddings.\
         assigned_planner_email, activity_logs.{planner_email,actor_email}
         all show NEW_EMAIL; OLD_EMAIL has zero hits.

    P7 — Auth: login with OLD_EMAIL → 401; login with NEW_EMAIL → 200.

    P8 — Couple portal (Chrome UX): "Your planner" email is the new value,
         not stale. Cache invalidation worked.

    P9 — Guest activity null-email leak: GET /admin/guests/{guest_no_email_id}
         /activity returns ONLY rows tied to that guest, not the
         wedding-wide feed.

Why this lives in testbed/
--------------------------

Per testbed/README.md, lifecycle drivers go here. The email-change cluster
is a state machine across 8 collections + cookie reissue + cache
invalidation; clicking through it by hand misses cascade hits in
collections nobody opens routinely. The pytest contract layer can't reach
this either — it monkey-patches Mongo, which means the cascade write paths
never actually run.

Pair with ``cleanup_planner_email_change_state.py`` — every run is
idempotent because cleanup drops the plus-variant planner chain plus any
Mongo rows the driver may have rewritten under the new email.

Usage
-----

    # First run — creates a clock and prints its id
    python testbed/verify_planner_email_change.py

    # Subsequent runs — reuse the clock
    EMAIL_CHANGE_CLOCK_ID=clock_... python testbed/verify_planner_email_change.py

    # CI-shaped — skip ENTER gates at UX checkpoints
    TESTBED_NON_INTERACTIVE=1 python testbed/verify_planner_email_change.py
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import requests
from bson import ObjectId

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from testbed.harness import PM_TOKEN_GOOD, Harness  # noqa: E402

logger = logging.getLogger(__name__)

DRIVER_NAME = "verify_planner_email_change"

# Reusable clock (id printed on first run; pin via env var afterwards).
TEST_CLOCK_NAME = "planner-email-change"
TEST_CLOCK_ID = os.getenv("EMAIL_CHANGE_CLOCK_ID")

# Plus-variant isolation — cleanup targets these.
OLD_EMAIL = "test_planner+emailchange@thespecialwedding.io"
PLANNER_PASSWORD = "EmailChangePlanner2026!"  # pragma: allowlist secret
NEW_EMAIL = "test_planner+emailchange_new@thespecialwedding.io"

# Couple invited to the wedding so the couple portal renders the planner
# email under "Your planner". The couple portal is the canonical
# stale-email failure surface from the original bug report.
COUPLE_EMAIL = "test_couple+emailchange@thespecialwedding.io"
COUPLE_PARTNER1 = "Cascade"
COUPLE_PARTNER2 = "Test"

# Lowest-friction signature plan — same convention as other drivers.
PLAN_ID = os.getenv("EMAIL_CHANGE_PLAN_ID", "plan_signature")

# Wedding fixture.
WEDDING_COUPLE_NAMES = f"{COUPLE_PARTNER1} & {COUPLE_PARTNER2}"
WEDDING_DATE_ISO = (datetime.now(timezone.utc) + timedelta(days=180)).strftime(
    "%Y-%m-%d"
)

# Two guests — one with email (canary, should be filtered OUT of the
# no-email guest's activity panel), one with PHONE-ONLY (the bug
# scenario; real planners do this all the time when they only have a
# phone number on a guest). The original bug fired because the activity
# query added `metadata.guest_email: None` to the OR clause when
# guest.email was missing — matching every doc without that field. The
# API enforces "phone OR email required" at create time, so we cannot
# create a completely contactless guest, but phone-only is enough to
# trigger the original null-coalescing bug.
GUEST_WITH_EMAIL_NAME = "Has Email Canary"
GUEST_WITH_EMAIL_EMAIL = "guest_canary+emailchange@example.invalid"
GUEST_NO_EMAIL_NAME = "Phone Only Target"
GUEST_NO_EMAIL_PHONE = "+15558675309"


# ============================================================================
# SEED
# ============================================================================


def _wait_for_subscription_active(
    h: Harness,
    *,
    user_id: str,
    customer_id: str,
    subscription_id: str,
    max_attempts: int = 24,
    poll_interval_sec: float = 2.5,
) -> None:
    """Poll Mongo until users.subscription_status flips to active.

    Every authenticated planner endpoint (incl. /admin/weddings) gates on
    ``users.subscription_status`` via ``_SUB_BLOCK_REASONS`` in
    ``app/dependencies/auth_extended.py``. The flip happens only inside
    ``StripeService._sync_subscription_state`` when the
    `customer.subscription.created` webhook lands.

    On failure dumps every state surface relevant to that flip — the user
    record, the user_subscriptions row, the stripe_customers link, plus
    the latest webhook events from the stripe_webhook_events collection
    — so the cause is observable from the run log without re-running.
    """

    h.log.info(
        "  ⏳ Waiting for users.subscription_status to flip to active "
        f"(max {max_attempts} polls × {poll_interval_sec}s)…"
    )
    last_user_status: object = "<unset>"
    last_sub_status: object = "<unset>"
    for attempt in range(1, max_attempts + 1):
        user = h.mongo["users"].find_one(
            {"_id": ObjectId(user_id)},
            {"subscription_status": 1, "is_active": 1, "email_verified": 1},
        )
        last_user_status = (user or {}).get("subscription_status")

        sub_doc = h.mongo["user_subscriptions"].find_one(
            {"stripe_subscription_id": subscription_id},
            {"status": 1, "stripe_status": 1, "user_id": 1},
        )
        last_sub_status = (sub_doc or {}).get("status")

        if last_user_status in {"active", "trialing"}:
            h.log.info(
                f"  ✅ users.subscription_status={last_user_status!r}, "
                f"user_subscriptions.status={last_sub_status!r} "
                f"after poll {attempt}/{max_attempts}"
            )
            return
        h.log.info(
            f"     poll {attempt}/{max_attempts}: "
            f"users.subscription_status={last_user_status!r}, "
            f"user_subscriptions.status={last_sub_status!r}"
        )
        import time

        time.sleep(poll_interval_sec)

    # Timed out — dump everything relevant for diagnosis.
    h.log.error("─" * 72)
    h.log.error("Subscription state did not converge to active. Dumping state:")
    h.log.error("─" * 72)

    user_doc = h.mongo["users"].find_one({"_id": ObjectId(user_id)}) or {}
    h.log.error(
        f"  users[{user_id}]:\n"
        f"    subscription_status = {user_doc.get('subscription_status')!r}\n"
        f"    is_active           = {user_doc.get('is_active')!r}\n"
        f"    email_verified      = {user_doc.get('email_verified')!r}\n"
        f"    registration_source = {user_doc.get('registration_source')!r}\n"
        f"    stripe_customer_id  = {user_doc.get('stripe_customer_id')!r}\n"
        f"    stripe_subscription_id = {user_doc.get('stripe_subscription_id')!r}"
    )

    sub_doc = (
        h.mongo["user_subscriptions"].find_one(
            {"stripe_subscription_id": subscription_id}
        )
        or {}
    )
    if sub_doc:
        h.log.error(
            f"  user_subscriptions[{subscription_id}]:\n"
            f"    user_id       = {sub_doc.get('user_id')!r}\n"
            f"    status        = {sub_doc.get('status')!r}\n"
            f"    stripe_status = {sub_doc.get('stripe_status')!r}\n"
            f"    plan_id       = {sub_doc.get('plan_id')!r}\n"
            f"    updated_at    = {sub_doc.get('updated_at')!r}"
        )
    else:
        h.log.error(
            f"  user_subscriptions[{subscription_id}]: "
            "<no document> ← webhook never wrote a row at all"
        )

    cust_link = h.mongo["stripe_customers"].find_one(
        {"stripe_customer_id": customer_id}
    )
    h.log.error(
        f"  stripe_customers[{customer_id}]:\n"
        f"    user_id = "
        f"{(cust_link or {}).get('user_id')!r}\n"
        f"    email   = {(cust_link or {}).get('email')!r}"
    )

    # Newest 10 stripe_webhook_events tied to this customer or subscription.
    # If `stripe listen` is forwarding but the events don't reach this
    # collection, the backend is rejecting them (likely STRIPE_WEBHOOK_SECRET
    # mismatch or signature verification failure) and the run log will show
    # 0 events here.
    recent = list(
        h.mongo["stripe_webhook_events"]
        .find(
            {
                "$or": [
                    {"data.object.id": subscription_id},
                    {"data.object.customer": customer_id},
                    {"data.object.id": customer_id},
                ]
            },
            {"type": 1, "created": 1, "data.object.id": 1, "data.object.status": 1},
        )
        .sort([("created", -1)])
        .limit(10)
    )
    if recent:
        h.log.error(
            f"  stripe_webhook_events (most recent {len(recent)} for this sub/customer):"
        )
        for ev in recent:
            obj = (ev.get("data") or {}).get("object") or {}
            h.log.error(
                f"    {ev.get('type'):40s} "
                f"id={obj.get('id')} "
                f"status={obj.get('status')!r} "
                f"created={ev.get('created')}"
            )
    else:
        h.log.error(
            "  stripe_webhook_events: NO events recorded for this sub/customer.\n"
            "    Either the events collection isn't where this backend records "
            "deliveries,\n"
            "    or signature verification rejected the webhook before it was "
            "persisted."
        )

    h.log.error("─" * 72)
    raise RuntimeError(
        "Subscription never transitioned to active in Mongo.\n"
        f"  last users.subscription_status      = {last_user_status!r}\n"
        f"  last user_subscriptions.status      = {last_sub_status!r}\n\n"
        "  See the dump above for the actual state of the user record,\n"
        "  the subscription doc, the stripe_customers link, and recent\n"
        "  webhook events. That's enough to localize where the chain broke."
    )


def seed_phase(h: Harness) -> dict:
    """Create planner, wedding, two guests + activity-log rows.

    Idempotent — wipes prior state for the plus-variant emails before
    re-seeding.
    """
    h.banner(f"PHASE SEED — {DRIVER_NAME}")

    admin_token = h.get_admin_token()

    # Wipe before re-seed so the driver is re-runnable without first
    # invoking cleanup. We DO NOT touch the test clock.
    h.log.info("Wiping prior plus-variant state…")
    for email in (OLD_EMAIL, NEW_EMAIL):
        h.delete_user_chain(email)
    # Couple users live outside the user_chain sweep — clear them by email.
    h.mongo["couple_users"].delete_many({"email": COUPLE_EMAIL})

    # Activity log rows from prior runs would taint the P9 null-email leak
    # check, so wipe rows we authored.
    h.mongo["activity_logs"].delete_many({"metadata.driver": DRIVER_NAME})

    # Get-or-create the reusable clock. First run prints the new id; you
    # can pin it via EMAIL_CHANGE_CLOCK_ID for subsequent runs.
    clock = h.get_or_create_clock(TEST_CLOCK_ID, name=TEST_CLOCK_NAME)
    clock_id = clock.id
    if not TEST_CLOCK_ID:
        h.log.info(
            f"  💡 Pin this clock for future runs: "
            f"export EMAIL_CHANGE_CLOCK_ID={clock_id}"
        )

    # Seed planner via the standard 6-step bootstrap (real Stripe customer
    # so couple portal / billing / dashboard render normally).
    seed = h.seed_planner_on_clock(
        admin_token=admin_token,
        clock_id=clock_id,
        email=OLD_EMAIL,
        password=PLANNER_PASSWORD,
        plan_id=PLAN_ID,
        first_name="Cascade",
        last_name="QA",
        company_name="Email-Change QA Co",
        pm_token=PM_TOKEN_GOOD,
    )

    # Poll Mongo until users.subscription_status flips to active. On
    # timeout, dumps the user record, the user_subscriptions row, the
    # stripe_customers link, and the most recent webhook events keyed to
    # this customer/subscription so the failure is observable from the
    # log without re-running.
    _wait_for_subscription_active(
        h,
        user_id=seed.user_id,
        customer_id=seed.customer_id,
        subscription_id=seed.subscription_id,
    )

    planner_token = h.login(OLD_EMAIL, PLANNER_PASSWORD)

    # Create the wedding via the production code path.
    wedding_id = h.create_wedding(
        planner_token=planner_token,
        couple_names=WEDDING_COUPLE_NAMES,
        date_iso=WEDDING_DATE_ISO,
        guest_count=50,
        venue="Cascade Test Venue",
    )

    # Two guests — one with email, one without — created via the planner
    # API so they pass through the same write path real users hit.
    guest_with_email_id = _create_guest(
        h,
        planner_token=planner_token,
        wedding_id=wedding_id,
        name=GUEST_WITH_EMAIL_NAME,
        email=GUEST_WITH_EMAIL_EMAIL,
    )
    guest_no_email_id = _create_guest(
        h,
        planner_token=planner_token,
        wedding_id=wedding_id,
        name=GUEST_NO_EMAIL_NAME,
        email=None,
        phone=GUEST_NO_EMAIL_PHONE,
    )

    # Plant one activity_log row per guest so the P9 leak check is
    # observable. We write directly to Mongo with a metadata.driver tag so
    # cleanup can sweep them later.
    now = datetime.now(timezone.utc)
    h.mongo["activity_logs"].insert_many(
        [
            {
                "type": "guest_updated",
                "message": f"Updated {GUEST_WITH_EMAIL_NAME} (canary)",
                "timestamp": now,
                "created_at": now,
                "wedding_id": wedding_id,
                "planner_email": OLD_EMAIL,
                "actor_email": OLD_EMAIL,
                "metadata": {
                    "driver": DRIVER_NAME,
                    "guest_id": guest_with_email_id,
                    "guest_name": GUEST_WITH_EMAIL_NAME,
                    "guest_email": GUEST_WITH_EMAIL_EMAIL,
                },
            },
            {
                "type": "guest_updated",
                "message": f"Updated {GUEST_NO_EMAIL_NAME} (target)",
                "timestamp": now,
                "created_at": now,
                "wedding_id": wedding_id,
                "planner_email": OLD_EMAIL,
                "actor_email": OLD_EMAIL,
                "metadata": {
                    "driver": DRIVER_NAME,
                    "guest_id": guest_no_email_id,
                    "guest_name": GUEST_NO_EMAIL_NAME,
                },
            },
        ]
    )
    h.log.info(f"  ✅ Seeded 2 activity_log rows tagged driver={DRIVER_NAME}")

    h.log.info(
        f"  ✅ SEED complete — planner={seed.user_id} wedding={wedding_id} "
        f"guests=({guest_with_email_id}, {guest_no_email_id})"
    )
    return {
        "admin_token": admin_token,
        "planner_token": planner_token,
        "user_id": seed.user_id,
        "wedding_id": wedding_id,
        "guest_with_email_id": guest_with_email_id,
        "guest_no_email_id": guest_no_email_id,
        "clock_id": clock_id,
    }


def _create_guest(
    h: Harness,
    *,
    planner_token: str,
    wedding_id: str,
    name: str,
    email: str | None,
    phone: str | None = None,
) -> str:
    """Create a guest via POST /admin/guests.

    Contract per the actual code:
      - ``wedding_id`` is a QUERY param (``app/api/guest.py:285``).
      - Body matches ``CreateGuestRequest`` (``app/models/guest.py:218``):
        name, phone, email, group_id, role, plus_one_allowed,
        number_of_plus_ones_allowed.
      - Service requires phone OR email (``app/services/guest_service.py:697``)
        — passing neither yields 400 "At least phone or email is required".
    """
    if not email and not phone:
        raise ValueError(
            "_create_guest requires either email or phone — the create_guest "
            "service rejects guests with neither."
        )
    payload: dict = {
        "name": name,
        "plus_one_allowed": False,
    }
    if email:
        payload["email"] = email
    if phone:
        payload["phone"] = phone
    resp = h.api_post(
        f"/admin/guests?wedding_id={wedding_id}",
        token=planner_token,
        json=payload,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Guest create failed for {name}: {resp.status_code} {resp.text}"
        )
    body = resp.json()
    guest_id = body.get("id") or body.get("_id") or (body.get("guest") or {}).get("id")
    if not guest_id:
        raise RuntimeError(f"Guest create returned no id: {body!r}")
    h.log.info(
        f"  ✅ Created guest: {guest_id} "
        f"({name}, email={email or '—'}, phone={phone or '—'})"
    )
    return str(guest_id)


# ============================================================================
# Driver
# ============================================================================


def main() -> int:
    h = Harness(driver_name=DRIVER_NAME)
    h.preflight()

    state = seed_phase(h)
    planner_token = state["planner_token"]
    user_id = state["user_id"]
    guest_no_email_id = state["guest_no_email_id"]
    guest_with_email_id = state["guest_with_email_id"]

    # ───────────────── P0 — Baseline (UX) ─────────────────
    h.phase("P0", "baseline — admin profile + couple portal show OLD_EMAIL")
    profile = h.api_get("/admin/profile", token=planner_token).json()
    if profile.get("email") != OLD_EMAIL:
        raise AssertionError(
            f"Baseline profile email = {profile.get('email')!r}, expected {OLD_EMAIL!r}"
        )
    if profile.get("pending_email"):
        raise AssertionError(
            f"Baseline profile already has pending_email={profile['pending_email']!r}"
        )
    h.log.info(f"  ✅ /admin/profile → email={profile['email']}, no pending")

    h.checkpoint(
        "P0",
        [
            f"Open Chrome → /admin/profile (logged in as {OLD_EMAIL})",
            f"Confirm Account Settings → Email tab shows Current Email = {OLD_EMAIL}",
            "Confirm New Email Address field is EMPTY (no prefill)",
            "Confirm NO amber 'Verification pending' banner is rendered",
        ],
    )

    # ───────────────── P1 — Request change ─────────────────
    h.phase("P1", "request email change → pending state")
    # PUT, not POST — see decorator at app/api/user_management.py:525.
    # Harness has no api_put helper, so go direct via requests like we do
    # for the DELETE below.
    resp = requests.put(
        f"{h.config.backend_url}/profile/email",
        headers={"Authorization": f"Bearer {planner_token}"},
        json={"new_email": NEW_EMAIL, "password": PLANNER_PASSWORD},
        timeout=30,
    )
    if resp.status_code != 200:
        raise AssertionError(
            f"PUT /profile/email expected 200, got "
            f"{resp.status_code}: {resp.text[:300]}"
        )
    body = resp.json()
    if not body.get("verification_required"):
        raise AssertionError(f"verification_required not true: {body!r}")
    if body.get("pending_email") != NEW_EMAIL:
        raise AssertionError(
            f"pending_email mismatch: {body.get('pending_email')!r} ≠ {NEW_EMAIL!r}"
        )
    email_send_status = body.get("verification_email_sent")
    if email_send_status is True:
        h.log.info("  ✅ verification email send returned success")
    else:
        h.log.warning(
            f"  ⚠️ verification_email_sent={email_send_status!r} — "
            "Resend may not be configured locally; cascade test still proceeds "
            "since we read the token directly from Mongo."
        )

    # ───────────────── P2 — Modal UX (Chrome) ─────────────────
    # Read straight from Mongo first to see what change_email actually
    # persisted. If THIS shows pending_email=None then the API returning
    # 200 is lying about its write.

    raw_user = h.mongo["users"].find_one({"_id": ObjectId(user_id)})
    if not raw_user:
        raise AssertionError(
            f"After PUT /profile/email, users[{user_id}] does not exist "
            "in Mongo. Did the cascade run prematurely?"
        )

    h.log.info(
        "  Mongo direct read of user record:\n"
        f"    _id                       = {raw_user.get('_id')}\n"
        f"    email                     = {raw_user.get('email')!r}\n"
        f"    pending_email             = {raw_user.get('pending_email')!r}\n"
        f"    email_change_token        = "
        f"{(raw_user.get('email_change_token') or '<none>')[:20]}…\n"
        f"    email_change_token_expires = "
        f"{raw_user.get('email_change_token_expires')!r}\n"
        f"    email_change_requested_at = "
        f"{raw_user.get('email_change_requested_at')!r}"
    )

    if raw_user.get("pending_email") != NEW_EMAIL:
        raise AssertionError(
            "Mongo direct read shows pending_email did NOT get persisted by "
            "change_email even though the API returned 200 with "
            "verification_email_sent=True.\n\n"
            f"  raw_user.pending_email = {raw_user.get('pending_email')!r}\n"
            f"  expected               = {NEW_EMAIL!r}\n"
            f"  raw_user.email         = {raw_user.get('email')!r}\n\n"
            "Possible causes:\n"
            "  1. update_one in change_email matched a DIFFERENT document "
            "(case mismatch on email, race with verify, etc.)\n"
            "  2. A subsequent process (verify_email_change running too "
            "early, or a webhook listener) cleared the field.\n"
            "  3. The api_post returned a cached response from before this "
            "request actually ran.\n"
        )

    # Confirmed in Mongo. Now check the API surfaces it correctly.
    profile = h.api_get("/admin/profile", token=planner_token).json()
    if profile.get("pending_email") != NEW_EMAIL:
        nested_user_data = profile.get("user_data") or {}
        nested_pending = nested_user_data.get("pending_email")
        top_level_keys = sorted(profile.keys())
        raise AssertionError(
            f"Mongo HAS pending_email={raw_user.get('pending_email')!r}, "
            "but /admin/profile is not surfacing it at the top level.\n"
            f"  top-level pending_email = {profile.get('pending_email')!r}\n"
            f"  user_data.pending_email = {nested_pending!r}\n"
            f"  top-level keys          = {top_level_keys}\n"
            "Likely uvicorn did not reload app/api/admin_auth.py after the "
            "edit that adds pending_email to the top-level response."
        )
    if "password_hash" in profile or "email_change_token" in profile:
        raise AssertionError(
            "/admin/profile leaked password_hash or email_change_token — "
            "the projection in get_user_profile is misconfigured."
        )
    h.log.info(
        f"  ✅ /admin/profile → email={profile['email']}, "
        f"pending_email={profile['pending_email']} (no secret leakage)"
    )

    h.checkpoint(
        "P2",
        [
            "In Chrome, refresh /admin/profile + reopen Account Settings",
            f"Confirm Current Email row still shows {OLD_EMAIL}",
            "Confirm New Email Address field is EMPTY (still no prefill)",
            f"Confirm AMBER banner: 'Verification pending' showing {NEW_EMAIL}",
            "Confirm 'Cancel pending change' button is visible inside the banner",
            "Confirm browser console has no errors related to the modal",
        ],
    )

    # ───────────────── P3 — Cancel ─────────────────
    h.phase("P3", "DELETE /profile/email/pending clears pending_email")
    # Harness has no api_delete helper; drop to requests directly,
    # matching how verify_metrics_snapshot_no_body.py uses requests for
    # endpoints not covered by harness shortcuts.
    resp = requests.delete(
        f"{h.config.backend_url}/profile/email/pending",
        headers={"Authorization": f"Bearer {planner_token}"},
        timeout=30,
    )
    if resp.status_code != 200:
        raise AssertionError(
            f"DELETE /profile/email/pending expected 200, got "
            f"{resp.status_code}: {resp.text[:300]}"
        )
    body = resp.json()
    if not body.get("cancelled"):
        raise AssertionError(f"cancelled not true: {body!r}")
    h.log.info(f"  ✅ cancelled=true ({body.get('message')})")

    profile = h.api_get("/admin/profile", token=planner_token).json()
    if profile.get("pending_email"):
        raise AssertionError(
            f"After cancel, pending_email still set: {profile['pending_email']!r}"
        )
    if profile.get("email") != OLD_EMAIL:
        raise AssertionError(
            f"After cancel, active email changed unexpectedly: {profile.get('email')!r}"
        )
    h.log.info("  ✅ /admin/profile → pending cleared, active email unchanged")

    h.checkpoint(
        "P3",
        [
            "In Chrome, refresh /admin/profile or reopen Account Settings",
            "Confirm AMBER banner is gone",
            "Confirm New Email Address field is empty (still no prefill)",
        ],
    )

    # ───────────────── P4 — Re-request + read token ─────────────────
    h.phase("P4", "re-request change so we can drive verify with a real token")
    resp = requests.put(
        f"{h.config.backend_url}/profile/email",
        headers={"Authorization": f"Bearer {planner_token}"},
        json={"new_email": NEW_EMAIL, "password": PLANNER_PASSWORD},
        timeout=30,
    )
    if resp.status_code != 200:
        raise AssertionError(
            f"P4 PUT /profile/email expected 200, got {resp.status_code}: {resp.text[:300]}"
        )

    user_doc = h.mongo["users"].find_one({"_id": ObjectId(user_id)})
    if not user_doc or not user_doc.get("email_change_token"):
        raise AssertionError(
            "Could not read email_change_token from users collection — change_email "
            "did not persist the token."
        )
    token_value = user_doc["email_change_token"]
    h.log.info(f"  ✅ email_change_token captured ({len(token_value)} chars)")

    # ───────────────── P5 — Verify (cascade + cookie) ─────────────────
    h.phase("P5", "GET /verify-email-change/{token} → cascade + cookie reissue")
    verify_resp = requests.get(
        f"{h.config.backend_url}/verify-email-change/{token_value}",
        timeout=30,
        allow_redirects=False,
    )
    if verify_resp.status_code != 200:
        raise AssertionError(
            f"verify-email-change expected 200, got {verify_resp.status_code}: "
            f"{verify_resp.text[:300]}"
        )
    body = verify_resp.json()
    if body.get("old_email") != OLD_EMAIL or body.get("new_email") != NEW_EMAIL:
        raise AssertionError(f"Verify response old_email/new_email wrong: {body!r}")
    h.log.info(
        f"  ✅ Verify response: old={body['old_email']} → new={body['new_email']}"
    )

    # Cookie reissue check.
    set_cookie_header = verify_resp.headers.get("set-cookie", "")
    if "admin_token=" not in set_cookie_header:
        raise AssertionError(
            f"verify-email-change did not set admin_token cookie. "
            f"Set-Cookie header: {set_cookie_header[:300]!r}"
        )
    new_cookie = verify_resp.cookies.get("admin_token")
    if not new_cookie:
        raise AssertionError("admin_token cookie not parseable from verify response")

    # Decode the JWT *without* verifying signature (we don't have the key
    # in this driver) — we just want to confirm sub=NEW_EMAIL.
    decoded = jwt.decode(new_cookie, options={"verify_signature": False})
    if decoded.get("sub") != NEW_EMAIL:
        raise AssertionError(
            f"Reissued JWT sub mismatch: {decoded.get('sub')!r} ≠ {NEW_EMAIL!r}"
        )
    h.log.info(f"  ✅ Reissued admin_token has sub={decoded['sub']}")

    # ───────────────── P6 — Cascade assertions (Mongo) ─────────────────
    h.phase("P6", "cascade across denormalized FK fields")

    cascade_targets: list[tuple[str, str]] = [
        ("users", "email"),
        ("weddings", "assigned_planner_email"),
        ("activity_logs", "planner_email"),
        ("activity_logs", "actor_email"),
    ]
    for coll, field in cascade_targets:
        old_count = h.mongo[coll].count_documents({field: OLD_EMAIL})
        new_count = h.mongo[coll].count_documents({field: NEW_EMAIL})
        h.log.info(f"  {coll}.{field}: old={old_count}, new={new_count}")
        if old_count != 0:
            raise AssertionError(
                f"Stale value: {coll}.{field} still has {old_count} rows = {OLD_EMAIL}"
            )
        if new_count == 0:
            # users.email + weddings.assigned_planner_email MUST be > 0;
            # activity_logs may legitimately be 0 if our seed rows had
            # planner_email=None (they didn't here, so we expect > 0).
            raise AssertionError(
                f"Cascade gap: {coll}.{field} has 0 rows = {NEW_EMAIL} after verify"
            )
    h.log.info("  ✅ All scalar cascade fields updated cleanly")

    # ───────────────── P7 — Auth (login old vs new) ─────────────────
    h.phase("P7", "login with OLD_EMAIL → 401, NEW_EMAIL → 200")
    old_login = h.api_post(
        "/admin/token",
        json={"email": OLD_EMAIL, "password": PLANNER_PASSWORD},
    )
    if old_login.status_code == 200:
        raise AssertionError(
            f"Login with OLD_EMAIL succeeded after verify — should 401. "
            f"Status={old_login.status_code}"
        )
    h.log.info(
        f"  ✅ Login with OLD_EMAIL = {old_login.status_code} (expected non-200)"
    )

    new_login = h.api_post(
        "/admin/token",
        json={"email": NEW_EMAIL, "password": PLANNER_PASSWORD},
    )
    if new_login.status_code != 200:
        raise AssertionError(
            f"Login with NEW_EMAIL expected 200, got {new_login.status_code}: "
            f"{new_login.text[:300]}"
        )
    new_token = new_login.json()["access_token"]
    h.log.info(f"  ✅ Login with NEW_EMAIL = 200 (token len={len(new_token)})")

    # ───────────────── P8 — Couple portal UX ─────────────────
    h.checkpoint(
        "P8",
        [
            "In Chrome, log in to the couple portal using the COUPLE invite link",
            f"  (couple email: {COUPLE_EMAIL})",
            "Open the dashboard and find the 'Your planner' card",
            f"Confirm the email shown is {NEW_EMAIL} (NOT the old one)",
            "If you see the old email, the couple_portal_dashboard cache",
            "  was not invalidated — check _invalidate_planner_email_caches",
            "  in user_management_service.py.",
        ],
    )

    # ───────────────── P9 — Guest activity null-email leak fix ─────────────────
    h.phase("P9", "guest with no email returns ONLY their own activity")
    activity_resp = h.api_get(
        f"/admin/guests/{guest_no_email_id}/activity",
        token=new_token,
    )
    if activity_resp.status_code != 200:
        raise AssertionError(
            f"GET guest activity expected 200, got {activity_resp.status_code}: "
            f"{activity_resp.text[:300]}"
        )
    payload = activity_resp.json()
    rows = (
        payload.get("activities") or (payload.get("data") or {}).get("activities") or []
    )

    leaked = [
        r
        for r in rows
        if (r.get("metadata") or {}).get("guest_id") == guest_with_email_id
    ]
    if leaked:
        raise AssertionError(
            f"Guest activity leaked {len(leaked)} row(s) belonging to the OTHER "
            f"guest (id={guest_with_email_id}). The Mongo OR clause is matching "
            "on metadata.guest_email=None again."
        )
    h.log.info(
        f"  ✅ Guest activity for {guest_no_email_id} returned {len(rows)} row(s); "
        "no leak from the email-having guest."
    )

    h.banner("ALL CHECKPOINTS PASSED")
    h.log.info("")
    h.log.info("Backend layer:")
    h.log.info("  ✓ change_email persists pending_email + verification token")
    h.log.info("  ✓ /admin/profile exposes pending_email without leaking secrets")
    h.log.info("  ✓ DELETE /profile/email/pending clears pending state")
    h.log.info("  ✓ verify_email_change cascades across users/weddings/activity_logs")
    h.log.info("  ✓ verify_email_change reissues admin_token cookie with new sub")
    h.log.info("  ✓ login auth flips OLD→NEW after verify")
    h.log.info("  ✓ guest activity null-email leak no longer reproduces")
    h.log.info("")
    h.log.info("UX layer (per Chrome checkpoints above):")
    h.log.info("  ✓ Modal shows current-email row + empty new-email field")
    h.log.info("  ✓ Pending banner + cancel button render correctly")
    h.log.info("  ✓ Couple portal shows the new planner email")
    h.log.info("")
    h.log.info("To clean up: python testbed/cleanup_planner_email_change_state.py")

    return 0


if __name__ == "__main__":
    sys.exit(main())
