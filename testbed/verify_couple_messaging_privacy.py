#!/usr/bin/env python3
"""Couple-messaging privacy verification.

Pins the SECURITY fix at ``app/api/couple_portal.py:couple_get_messages``
(the comment block starting "SECURITY: do NOT return sender_email on the
couple-facing GET"). The couple-facing message GET must not expose
planner/team login emails. Planner-side parity must still project
``sender_email`` — it's how planners disambiguate multiple team senders on a
shared thread.

Scenario checkpoints
--------------------

    P0 — Seed: planner on signature plan, wedding created, couple invited,
         couple setup completed, both parties exchanged one message.
    P1 — GET /couple/portal/messages (couple auth): response messages
         include ``sender_role`` / ``sender_name`` but NOT ``sender_email``.
         The couple-side `isSelfAuthored` in
         ``app/types/messaging.ts`` falls back to sender_role comparison.
    P2 — GET /couple-portal/messages?wedding_id=... (planner auth):
         response messages DO include ``sender_email`` so planners can
         distinguish multiple team senders. Regression guard — the fix
         must not accidentally scrub the planner surface too.

Why this lives in testbed/
--------------------------

The testbed charter (``testbed/README.md``) is lifecycle walkers that
exercise the real API surface end-to-end against live Mongo + real webhooks
— not pytest unit tests. This driver seeds a real planner (via the shared
planner-bootstrap harness used by the subscription-lifecycle drivers),
invites a real couple, and asserts the *wire* shape of both endpoint
responses. That's the layer the pytest contract test at
``tests/backend/test_couple_messages_contract.py`` can't reach by design —
pytest there monkey-patches Mongo, so it proves the projector shape but
not the deployed router wiring.

Pair with ``cleanup_couple_messaging_privacy_state.py`` — every run should
be idempotent because that cleanup drops the plus-variant planner chain +
all couple_users / couple_messages rows for the test wedding ids it finds.

Usage
-----

    # First run — creates the reusable clock and prints its id
    python testbed/verify_couple_messaging_privacy.py

    # Subsequent runs — pin the clock (cleanup preserves it)
    COUPLE_PRIVACY_CLOCK_ID=clock_... python testbed/verify_couple_messaging_privacy.py

    # Unattended (CI-shaped — skips ENTER gates at checkpoints)
    TESTBED_NON_INTERACTIVE=1 python testbed/verify_couple_messaging_privacy.py
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


from testbed.harness import PM_TOKEN_GOOD, Harness, PlannerSeed

logger = logging.getLogger(__name__)

DRIVER_NAME = "verify_couple_messaging_privacy"

# Clock is reused across runs — NEVER delete it from cleanup.
TEST_CLOCK_NAME = "couple-messaging-privacy"
TEST_CLOCK_ID = os.getenv("COUPLE_PRIVACY_CLOCK_ID")

# Plus-variant isolation — cleanup targets these.
PLANNER_EMAIL = "test_planner+msg_privacy@thespecialwedding.io"
PLANNER_PASSWORD = "MsgPrivacyPlanner2026!"  # pragma: allowlist secret

COUPLE_EMAIL = "test_couple+msg_privacy@thespecialwedding.io"
COUPLE_PASSWORD = "MsgPrivacyCouple2026!"  # pragma: allowlist secret
COUPLE_PARTNER1 = "Privy"
COUPLE_PARTNER2 = "Couple"

# Default paid plan — we don't care which plan, only that the planner is
# allowed to create a wedding and invite a couple. plan_signature is the
# lowest-friction signature plan in the seed data.
PLAN_ID = os.getenv("COUPLE_PRIVACY_PLAN_ID", "plan_signature")

# Message content we later assert on. Keep distinct so the couple can tell
# which side sent which in the Chrome walk-through.
COUPLE_MSG_CONTENT = "[testbed:couple] Hi planner! — msg_privacy driver"
PLANNER_MSG_CONTENT = "[testbed:planner] Hi couple! — msg_privacy driver"


# =============================================================================
# Idempotency helpers — keep the driver re-runnable without cleanup
# =============================================================================


def _wipe_test_wedding_state(h: Harness) -> None:
    """Drop couple_users + couple_messages + weddings tied to our plus-variants.

    Runs at the top of the seed phase so re-running the driver without first
    invoking cleanup still enters a known-empty state. The harness's
    ``delete_user_chain`` covers the planner + weddings-by-email, but the
    couple_users + couple_messages collections are not in its sweep because
    they're not part of the generic subscription-lifecycle chain.
    """
    # Planner-owned weddings (email-keyed — survives user_id regen).
    wedding_filter = {
        "$or": [
            {"assigned_planner_email": PLANNER_EMAIL},
            {"created_by": PLANNER_EMAIL},
        ]
    }
    wedding_docs = list(h.mongo["weddings"].find(wedding_filter, {"_id": 1}))
    wedding_ids = [str(w["_id"]) for w in wedding_docs]

    if wedding_ids:
        cm_result = h.mongo["couple_messages"].delete_many(
            {"wedding_id": {"$in": wedding_ids}}
        )
        if cm_result.deleted_count:
            h.log.info(
                f"  ✅ couple_messages: removed {cm_result.deleted_count} "
                f"doc(s) for wedding_ids={wedding_ids}"
            )

        cu_result = h.mongo["couple_users"].delete_many(
            {"wedding_id": {"$in": wedding_ids}}
        )
        if cu_result.deleted_count:
            h.log.info(
                f"  ✅ couple_users: removed {cu_result.deleted_count} doc(s) "
                f"for wedding_ids={wedding_ids}"
            )

    # Belt-and-braces: drop couple_users by email too, in case a prior run
    # left an orphan tied to a wedding that was already cleaned up.
    cu_email_result = h.mongo["couple_users"].delete_many({"email": COUPLE_EMAIL})
    if cu_email_result.deleted_count:
        h.log.info(
            f"  ✅ couple_users (by email): removed "
            f"{cu_email_result.deleted_count} doc(s) for {COUPLE_EMAIL}"
        )


# =============================================================================
# Phases
# =============================================================================


def phase_seed(h: Harness, admin_token: str, clock_id: str) -> PlannerSeed:
    h.phase(
        "MSG_PRIVACY_SEED",
        "Bootstrap planner on paid plan + clock (idempotent — re-running is OK)",
    )

    # Always wipe couple_users + couple_messages + test weddings first. The
    # planner chain itself is idempotent via reuse/reseed below.
    _wipe_test_wedding_state(h)

    # Reuse planner if present. Mirrors the pattern from
    # verify_planner_metered_lifecycle.phase_seed.
    existing = h.mongo["users"].find_one({"email": PLANNER_EMAIL})
    if existing:
        sub = h.mongo["user_subscriptions"].find_one(
            {
                "user_id": str(existing["_id"]),
                "status": {"$in": ["active", "trialing"]},
            }
        )
        customer_doc = h.mongo["stripe_customers"].find_one(
            {"user_id": str(existing["_id"])}
        )
        if sub and customer_doc:
            h.log.info(
                f"  ♻ Reusing existing planner user_id={existing['_id']} "
                f"customer_id={customer_doc['stripe_customer_id']} "
                f"sub_id={sub.get('stripe_subscription_id')}"
            )
            return PlannerSeed(
                clock_id=clock_id,
                customer_id=customer_doc["stripe_customer_id"],
                subscription_id=sub["stripe_subscription_id"],
                user_id=str(existing["_id"]),
                email=PLANNER_EMAIL,
                plan_id=PLAN_ID,
                has_trial=False,
            )
        # Partial state — drop it and reseed cleanly.
        h.log.info("  ⚠ Partial planner state — dropping Mongo chain and reseeding.")
        h.delete_user_chain(PLANNER_EMAIL)

    seed = h.seed_planner_on_clock(
        admin_token=admin_token,
        clock_id=clock_id,
        email=PLANNER_EMAIL,
        password=PLANNER_PASSWORD,
        plan_id=PLAN_ID,
        pm_token=PM_TOKEN_GOOD,
        trial_days=None,
    )

    h.checkpoint(
        "P0_SEED_COMPLETE",
        expectations=[
            f"Planner creds — email: {PLANNER_EMAIL}  password: {PLANNER_PASSWORD}",
            f"Planner {PLANNER_EMAIL} is on plan_id={PLAN_ID}",
            "Stripe subscription is active (not trialing)",
            "Chrome is NOT required for this phase — pure backend bootstrap",
        ],
    )
    return seed


def phase_create_wedding(h: Harness, planner_token: str) -> str:
    h.phase(
        "MSG_PRIVACY_WEDDING",
        "Planner creates a wedding so there's a conversation target",
    )
    resp = h.api_post(
        "/admin/weddings",
        token=planner_token,
        json={
            "couple_names": f"{COUPLE_PARTNER1} & {COUPLE_PARTNER2}",
            "date": "2027-10-10",
        },
    )
    h.log.info(f"  POST /admin/weddings -> {resp.status_code}")
    assert resp.status_code in (200, 201), (
        f"wedding create returned {resp.status_code} — body={resp.text}"
    )

    payload = resp.json() or {}
    wedding_id = payload.get("_id") or payload.get("id") or payload.get("wedding_id")
    if not wedding_id:
        # Fall back to the most recent wedding owned by this planner.
        doc = h.mongo["weddings"].find_one(
            {"assigned_planner_email": PLANNER_EMAIL},
            sort=[("_id", -1)],
        )
        assert doc, "could not resolve freshly-created wedding_id"
        wedding_id = str(doc["_id"])

    h.log.info(f"  ✅ wedding_id = {wedding_id}")
    return wedding_id


def phase_invite_couple(h: Harness, planner_token: str, wedding_id: str) -> str:
    """Invite the couple, read the invite_token from Mongo, complete setup.

    Returns the couple's access_token (JWT) for subsequent couple-side calls.
    """
    h.phase(
        "MSG_PRIVACY_COUPLE_SETUP",
        "Planner invites couple; couple completes setup via invite_token",
    )

    invite_resp = h.api_post(
        "/admin/couple-portal/invite",
        token=planner_token,
        json={
            "email": COUPLE_EMAIL,
            "partner1_name": COUPLE_PARTNER1,
            "partner2_name": COUPLE_PARTNER2,
            "wedding_id": wedding_id,
        },
    )
    h.log.info(f"  POST /admin/couple-portal/invite -> {invite_resp.status_code}")
    assert invite_resp.status_code in (200, 201), (
        f"invite failed {invite_resp.status_code} — body={invite_resp.text}"
    )
    invite_body = invite_resp.json() or {}
    setup_link = invite_body.get("setup_link") or ""
    # setup_link format: {frontend_url}/couple/setup/{invite_token}
    invite_token = setup_link.rsplit("/", 1)[-1] if setup_link else ""
    if not invite_token:
        # Fall back to reading directly from Mongo.
        doc = h.mongo["couple_users"].find_one(
            {"email": COUPLE_EMAIL, "wedding_id": wedding_id},
            {"invite_token": 1},
        )
        assert doc and doc.get("invite_token"), (
            "could not resolve invite_token from Mongo"
        )
        invite_token = doc["invite_token"]
    h.log.info(f"  ✅ invite_token resolved (len={len(invite_token)})")

    setup_resp = h.api_post(
        "/couple/setup-password",
        json={"token": invite_token, "password": COUPLE_PASSWORD},
    )
    h.log.info(f"  POST /couple/setup-password -> {setup_resp.status_code}")
    assert setup_resp.status_code in (200, 201), (
        f"couple setup failed {setup_resp.status_code} — body={setup_resp.text}"
    )
    setup_body = setup_resp.json() or {}
    couple_token = setup_body.get("access_token")
    assert couple_token, (
        f"couple setup response missing access_token — body={setup_body}"
    )
    h.log.info("  ✅ couple setup complete — bearer access_token acquired")

    return couple_token


def phase_exchange_messages(
    h: Harness,
    planner_token: str,
    couple_token: str,
    wedding_id: str,
) -> None:
    """Both sides send one message each."""
    h.phase(
        "MSG_PRIVACY_EXCHANGE",
        "Couple and planner each send one message to seed the thread",
    )

    couple_send = h.api_post(
        "/couple/portal/messages",
        token=couple_token,
        json={"content": COUPLE_MSG_CONTENT},
    )
    h.log.info(f"  POST /couple/portal/messages (couple) -> {couple_send.status_code}")
    assert couple_send.status_code in (200, 201), (
        f"couple send failed {couple_send.status_code} — body={couple_send.text}"
    )

    planner_send = h.api_post(
        "/couple-portal/messages",
        token=planner_token,
        json={"wedding_id": wedding_id, "content": PLANNER_MSG_CONTENT},
    )
    h.log.info(
        f"  POST /couple-portal/messages (planner) -> {planner_send.status_code}"
    )
    assert planner_send.status_code in (200, 201), (
        f"planner send failed {planner_send.status_code} — body={planner_send.text}"
    )

    h.log.info("  ✅ Both messages persisted")


def phase_assert_couple_get_strips_email(h: Harness, couple_token: str) -> dict:
    """P1 — couple GET must not include sender_email on any message."""
    h.phase(
        "MSG_PRIVACY_P1",
        "Couple GET: sender_email must be absent on every message",
    )

    resp = h.api_get("/couple/portal/messages", token=couple_token)
    h.log.info(f"  GET /couple/portal/messages -> {resp.status_code}")
    assert resp.status_code == 200, (
        f"couple GET returned {resp.status_code} — body={resp.text}"
    )
    body = resp.json() or {}
    messages = body.get("messages") or []
    assert len(messages) >= 2, (
        f"expected at least 2 messages in the thread, got {len(messages)} — body={body}"
    )

    # Log a summary so the transcript makes the wire-shape explicit.
    for idx, msg in enumerate(messages):
        h.log.info(
            f"  msg[{idx}] role={msg.get('sender_role')!r} "
            f"name={msg.get('sender_name')!r} "
            f"has_sender_email={'sender_email' in msg}"
        )

    offenders = [idx for idx, m in enumerate(messages) if "sender_email" in m]
    assert not offenders, (
        "SECURITY REGRESSION: couple GET response includes `sender_email` on "
        f"message indices {offenders}. Restore the projector fix at "
        "app/api/couple_portal.py couple_get_messages. The couple portal must "
        "never see planner/team login emails."
    )

    for idx, m in enumerate(messages):
        assert m.get("sender_role") in ("couple", "planner"), (
            f"msg[{idx}] has unexpected sender_role={m.get('sender_role')!r} — "
            f"role fallback for isSelfAuthored needs a recognisable role"
        )
        assert "sender_name" in m, (
            f"msg[{idx}] missing sender_name — couple dashboard still needs a "
            f"human-readable author for display"
        )

    h.log.info("  ✅ No sender_email on any couple-facing message")

    h.checkpoint(
        "P1_COUPLE_GET_STRIPS_EMAIL",
        expectations=[
            "Chrome DevTools → Network → GET /couple/portal/messages response:",
            "  every message object has `sender_role` and `sender_name`",
            "  NO message object has `sender_email`",
            "Couple dashboard still renders each message's authorship correctly",
            "  (planner-authored messages show planner name, not 'You')",
        ],
    )
    return body


def phase_assert_planner_get_keeps_email(
    h: Harness, planner_token: str, wedding_id: str
) -> dict:
    """P2 — planner GET must still include sender_email (parity guard)."""
    h.phase(
        "MSG_PRIVACY_P2",
        "Planner GET: sender_email must REMAIN present on every message",
    )

    resp = h.api_get(
        f"/couple-portal/messages?wedding_id={wedding_id}",
        token=planner_token,
    )
    h.log.info(f"  GET /couple-portal/messages -> {resp.status_code}")
    assert resp.status_code == 200, (
        f"planner GET returned {resp.status_code} — body={resp.text}"
    )
    body = resp.json() or {}
    messages = body.get("messages") or []
    assert len(messages) >= 2, (
        f"expected at least 2 messages on planner side, got {len(messages)}"
    )

    for idx, msg in enumerate(messages):
        h.log.info(
            f"  msg[{idx}] role={msg.get('sender_role')!r} "
            f"email={msg.get('sender_email')!r}"
        )

    missing = [idx for idx, m in enumerate(messages) if "sender_email" not in m]
    assert not missing, (
        "REGRESSION: planner GET response stripped `sender_email` on message "
        f"indices {missing}. Planners need sender_email to disambiguate "
        "multiple team senders on a shared thread. Check that the fix at "
        "app/api/couple_portal.py:couple_get_messages didn't accidentally "
        "spill into planner_get_messages."
    )

    h.log.info("  ✅ sender_email present on every planner-facing message")

    h.checkpoint(
        "P2_PLANNER_GET_KEEPS_EMAIL",
        expectations=[
            "Chrome DevTools → Network → GET /couple-portal/messages response:",
            "  every message object has `sender_email` populated",
            "Planner inbox UI still shows per-sender identity on multi-team threads",
        ],
    )
    return body


# =============================================================================
# Entry point
# =============================================================================


def main() -> int:
    h = Harness(driver_name=DRIVER_NAME)
    h.banner("VERIFY — Couple Messaging Privacy (sender_email projection)")
    h.log.info(f"  Planner email : {PLANNER_EMAIL}")
    h.log.info(f"  Couple email  : {COUPLE_EMAIL}")
    h.log.info(f"  Clock name    : {TEST_CLOCK_NAME}")
    h.log.info(
        f"  Clock id      : {TEST_CLOCK_ID or '(none — fresh clock, pin via COUPLE_PRIVACY_CLOCK_ID next run)'}"
    )
    h.log.info(f"  Plan id       : {PLAN_ID}")
    h.log.info(f"  Started at    : {datetime.now(timezone.utc).isoformat()}")

    h.preflight()

    h.phase("MSG_PRIVACY_CLOCK", "Resolve the reusable test clock")
    clock = h.get_or_create_clock(TEST_CLOCK_ID, name=TEST_CLOCK_NAME)
    clock_id = clock.id

    admin_token = h.get_admin_token()

    seed = phase_seed(h, admin_token, clock_id)
    planner_token = h.login(PLANNER_EMAIL, PLANNER_PASSWORD)

    wedding_id = phase_create_wedding(h, planner_token)
    couple_token = phase_invite_couple(h, planner_token, wedding_id)
    phase_exchange_messages(h, planner_token, couple_token, wedding_id)

    phase_assert_couple_get_strips_email(h, couple_token)
    phase_assert_planner_get_keeps_email(h, planner_token, wedding_id)

    h.banner("VERIFY — Couple Messaging Privacy COMPLETE ✅")
    h.log.info(
        "  Reminder: reusable clock preserved. Next run can pin "
        f"COUPLE_PRIVACY_CLOCK_ID={clock_id}"
    )
    h.log.info(
        f"  Driver seeded planner user_id={seed.user_id}, customer_id={seed.customer_id}"
    )
    h.log.info(
        "  Clean up with: python testbed/cleanup_couple_messaging_privacy_state.py "
        f"(set COUPLE_PRIVACY_CLOCK_ID={clock_id} to also sweep Stripe customers)"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"\n❌ Driver aborted: {exc}\n")
        raise SystemExit(1)
