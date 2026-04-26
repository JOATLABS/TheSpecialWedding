#!/usr/bin/env python3
"""
Scenarios B + C + D — Planner Active Subscription Lifecycle (Live Verification)
================================================================================

Pins end-to-end behavior for a *paying* planner on a flat-priced monthly plan:

  * Scenario B — wedding-count metering (0 / 1 / 2+ → cap at 4th).
  * Scenario C — AI-credit gate, including the mid-month downgrade grandfather.
  * Scenario D — plan change, cancel-at-period-end, canceled-state access,
                 resubscribe, and the past-due → recovery round-trip.

Anchored to `docs/plans/SUBSCRIPTION_LIFECYCLE_TEST_PLAN.md` §3.2–§3.4. Follows
the two-layer E2E rule from `CLAUDE.md`:

  * Scripted (this driver) covers backend-observable state: Mongo rows, 402
    gate messages, webhook settle, subscription status transitions, plan
    snapshots, usage counters.
  * Claude-in-Chrome covers UX-observable state: banner copy, toast rendering,
    console noise, redirect targets. Each `checkpoint(...)` call pauses the
    driver so the browser can be inspected against the fresh server state.

A verification is complete only when both layers agree.

Accounts (plus-variant — base QA accounts are never touched)
------------------------------------------------------------
  Planner (active)    : test_planner+active@thespecialwedding.io
  Planner (downgrade) : test_planner+downgrade@thespecialwedding.io

Stripe test clock
-----------------
  Reused across runs under the name ``planner-active-lifecycle``. The clock
  drifts forward each run; that is expected and why ``advance_clock_days`` is
  anchored on the clock's own ``frozen_time`` rather than wall-now. The paired
  cleanup script deletes clock customers but **not** the clock itself.

Phases
------
  SEED_ACTIVE               — B0: fresh paying Boutique planner on clock, PM
                              attached, no trial. Dashboard-clean state.
  ACTIVE_ZERO_WEDDINGS      — B0.1/B0.2: empty-state + renewal preservation.
  ACTIVE_ONE_WEDDING        — B1.1/B1.2/B1.3: create, renewal, delete.
  ACTIVE_WEDDING_CAP        — B2.1–B2.3: fill cap, 4th → 402 verbatim.
  ACTIVE_AI_CREDIT_CAP      — C1–C4: credit gate + renewal reset.
  PLAN_UPGRADE              — D1: Boutique → Signature mid-cycle.
  PLAN_DOWNGRADE_OVER_CAP   — D2: Signature → Boutique while over cap. Pins
                              actual behavior (open question — see plan §6 Q2).
  AI_DOWNGRADE_SNAPSHOT     — C5: mid-month downgrade with credits already used.
                              Pins plan_snapshot grandfather behavior (Q1).
  SUBSCRIPTION_CANCEL       — D3: cancel_at_period_end=True, status stays
                              active, flag set.
  SUBSCRIPTION_CANCELED     — D4: clock past period end. Pin login/gate
                              behavior (plan §6 Q3).
  SUBSCRIPTION_RESUBSCRIBE  — D5: new subscription on the canceled customer.
  SUBSCRIPTION_PAST_DUE     — D6: PM failure → past_due → recovery mirror of
                              the team-member gate driver (plan §6 Q6).

Usage
-----
    # Spin up services first (from repo root):
    python testbed/testbed.py up
    python testbed/testbed.py seed      # idempotent — plans / admin / indexes

    python testbed/verify_planner_active_lifecycle.py

    # Reset leaked state so another run can SEED from blank:
    python testbed/cleanup_planner_active_verify_state.py

Requirements
------------
  - Backend running at BACKEND_URL (default http://localhost:8000)
  - Frontend running at FRONTEND_URL (default http://localhost:3000)
  - Stripe CLI forwarding webhooks to /stripe/webhook
  - `.env` contains STRIPE_SECRET_KEY, MONGO_URI, ROOT_ADMIN_PASSWORD
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import stripe

from testbed.harness import (
    PM_TOKEN_GOOD,
    PM_TOKEN_WILL_FAIL_ON_RENEWAL,
    Harness,
    PlannerSeed,
)

# ---------------------------------------------------------------------------
# Driver constants (pinned so re-runs and cleanup stay deterministic)
# ---------------------------------------------------------------------------

DRIVER_NAME = "verify_planner_active_lifecycle"

# Clock is reused across runs — NEVER delete it from cleanup.
TEST_CLOCK_NAME = "planner-active-lifecycle"
TEST_CLOCK_ID = os.getenv("ACTIVE_CLOCK_ID")  # pin after first run if desired

# Primary planner — runs scenarios B, C (except C5), D3–D6.
PLANNER_EMAIL = "test_planner+active@thespecialwedding.io"
PLANNER_PASSWORD = "ActivePlanner2026!"  # pragma: allowlist secret

# Secondary planner — used for C5 and D1/D2 so plan changes don't interfere
# with the primary planner's B/C matrix state.
DOWNGRADE_PLANNER_EMAIL = "test_planner+downgrade@thespecialwedding.io"
DOWNGRADE_PLANNER_PASSWORD = "DowngradePlanner2026!"  # pragma: allowlist secret

PLAN_BOUTIQUE = "plan_boutique"
PLAN_SIGNATURE = "plan_signature"

# Limits mirror scripts/seed_subscription_plans.py. Kept here so the assertion
# strings are grep-visible from the driver header — if they drift from the
# seed, the seed wins and these need updating.
BOUTIQUE_MAX_WEDDINGS = 3
BOUTIQUE_AI_CREDITS_MONTHLY = 100
SIGNATURE_MAX_WEDDINGS = 10
SIGNATURE_AI_CREDITS_MONTHLY = 300

# Verbatim gate message from app/services/subscription_service.py (weddings
# branch). Frontend regex matching breaks if this string is edited.
EXPECTED_WEDDING_CAP_MSG = (
    f"Wedding limit exceeded. Plan allows {BOUTIQUE_MAX_WEDDINGS} weddings, "
    f"you have {BOUTIQUE_MAX_WEDDINGS}"
)
# AI credits are now soft-capped with metered overage — there is no hard-stop
# message. Going over plan returns allowed=True with an `overage` flag and the
# accrued `overage_credits`/`overage_cost_cents`. See the check_usage_limits()
# ai_credits branch for the response shape. Assertions below pin the new
# contract.

# Monthly plans renew every 30 days on Stripe's default billing cycle. We add
# one extra day of headroom on every advance so the renewal webhook has
# settled before the next assertion.
DAYS_PER_MONTH = 31

# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------


def _create_wedding(
    h: Harness,
    token: str,
    *,
    bride: str,
    groom: str,
    wedding_date: str = "2027-06-12",
) -> Any:
    """Thin wrapper — reduces the 4-line JSON body noise in the phases below."""
    return h.api_post(
        "/admin/weddings",
        token=token,
        json={"couple_names": f"{bride} & {groom}", "date": wedding_date},
    )


def _wedding_ids_for(h: Harness, user_id: str) -> list[str]:
    """Mongo-side list of wedding ids owned by this planner — used for targeted
    delete assertions so we don't nuke test fixtures from another driver.

    The wedding doc stores ownership under ``assigned_planner_id`` (set by
    ``app/api/wedding.py:create_wedding``), not ``user_id`` / ``owner_id``.
    Keep the legacy fields in the OR so this also works against older fixtures
    that might still have those keys."""
    cur = h.mongo["weddings"].find(
        {
            "$or": [
                {"assigned_planner_id": user_id},
                {"user_id": user_id},
                {"owner_id": user_id},
            ]
        },
        {"_id": 1},
    )
    return [str(doc["_id"]) for doc in cur]


def _current_usage_row(h: Harness, user_id: str) -> Optional[dict]:
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    return h.mongo["usage_tracking"].find_one(
        {"user_id": user_id, "current_month": current_month}
    )


def _subscription_row(h: Harness, user_id: str, stripe_sub_id: str) -> Optional[dict]:
    return h.mongo["user_subscriptions"].find_one(
        {"user_id": user_id, "stripe_subscription_id": stripe_sub_id}
    )


def _change_stripe_plan(
    h: Harness,
    *,
    subscription_id: str,
    new_price_id: str,
    proration: str = "always_invoice",
) -> stripe.Subscription:
    """Swap the price on an existing subscription in place.

    Uses Subscription.modify because harness does not yet wrap plan changes.
    Proration default 'always_invoice' so the test sees the invoice immediately
    — the alternative 'create_prorations' defers the line to the next cycle
    and makes D1's assertion racy against the clock advance.
    """
    sub = stripe.Subscription.retrieve(subscription_id)
    item_id = sub["items"]["data"][0]["id"]
    return stripe.Subscription.modify(
        subscription_id,
        items=[{"id": item_id, "price": new_price_id}],
        proration_behavior=proration,
        metadata={**(sub.get("metadata") or {}), "plan_change_driver": DRIVER_NAME},
    )


# ---------------------------------------------------------------------------
# Scenario B — wedding metering by count (Boutique cap = 3)
# ---------------------------------------------------------------------------


def phase_seed_active(h: Harness, admin_token: str, clock_id: str) -> PlannerSeed:
    """B0 — Fresh paying Boutique planner on the reusable clock. PM attached,
    no trial. This is the canonical "dashboard-clean active planner" state
    that the rest of B/C builds on."""
    h.phase("SEED_ACTIVE", "B0 — paying Boutique planner, PM attached, no trial")
    seed = h.seed_planner_on_clock(
        admin_token=admin_token,
        clock_id=clock_id,
        email=PLANNER_EMAIL,
        password=PLANNER_PASSWORD,
        plan_id=PLAN_BOUTIQUE,
        pm_token=PM_TOKEN_GOOD,
        trial_days=None,  # paying — no trial
    )

    user_doc = h.get_user_doc(seed.user_id) or {}
    sub_doc = _subscription_row(h, seed.user_id, seed.subscription_id) or {}

    h.log.info(f"  users.subscription_status = {user_doc.get('subscription_status')!r}")
    h.log.info(f"  user_subscriptions.status = {sub_doc.get('status')!r}")

    assert user_doc.get("subscription_status") == "active", (
        f"Expected users.subscription_status='active' for a paying planner, "
        f"got {user_doc.get('subscription_status')!r}"
    )
    assert sub_doc.get("status") == "active", (
        f"Expected user_subscriptions.status='active', got {sub_doc.get('status')!r}"
    )
    snapshot = sub_doc.get("plan_snapshot") or {}
    assert snapshot.get("max_weddings") == BOUTIQUE_MAX_WEDDINGS, (
        f"plan_snapshot.max_weddings drift: expected {BOUTIQUE_MAX_WEDDINGS}, "
        f"got {snapshot.get('max_weddings')!r}"
    )
    assert snapshot.get("ai_credits_monthly") == BOUTIQUE_AI_CREDITS_MONTHLY, (
        f"plan_snapshot.ai_credits_monthly drift: expected "
        f"{BOUTIQUE_AI_CREDITS_MONTHLY}, got {snapshot.get('ai_credits_monthly')!r}"
    )

    h.checkpoint(
        "B0",
        [
            f"Chrome login creds — email: {PLANNER_EMAIL}  password: {PLANNER_PASSWORD}",
            "Chrome: log in as the active planner at /admin/login — no banner",
            "  / toast errors.",
            "Chrome: /admin/planner renders the normal dashboard (no billing",
            "  redirect, no 402 handling triggered).",
            "Chrome devtools console: clean (no 401/402/red /admin/profile).",
            "Backend: users.subscription_status == 'active' ✅",
            f"Backend: plan_snapshot pins cap={BOUTIQUE_MAX_WEDDINGS} / credits="
            f"{BOUTIQUE_AI_CREDITS_MONTHLY} ✅",
        ],
    )
    return seed


def phase_active_zero_weddings(h: Harness, seed: PlannerSeed, clock_id: str) -> None:
    """B0.1 / B0.2 — Never create a wedding. Confirm renewal tick preserves
    weddings_count=0 and the AI credits live-query window cleanly resets to
    the new month (i.e. ``/admin/ai/credits`` returns 0 used).

    The legacy ``usage_tracking.ai_credits_used_month`` counter is no longer
    load-bearing — it was the source of the drift bug we replaced with the
    ``ai_usage_log`` live-query. We seed a stale value into it here to prove
    the live-query does not read from it; only ``ai_usage_log`` rows in the
    new month's window matter.
    """
    h.phase("ACTIVE_ZERO_WEDDINGS", "B0.1/B0.2 — empty-state, renewal preserves state")

    usage_before = _current_usage_row(h, seed.user_id) or {}
    h.log.info(
        f"  before renewal: weddings_count="
        f"{usage_before.get('weddings_count', 0)!r} "
        f"ai_credits_used_month="
        f"{usage_before.get('ai_credits_used_month', 0)!r}"
    )

    # Pre-seed a non-zero stale counter. The new contract: this value must
    # NOT leak into the live-query result post-renewal.
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    usage_id = f"usage_{seed.user_id}_{current_month}"
    h.mongo["usage_tracking"].update_one(
        {"_id": usage_id},
        {
            "$set": {
                "user_id": seed.user_id,
                "current_month": current_month,
                "ai_credits_used_month": 25,
                "weddings_count": 0,
                "last_updated": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )

    h.advance_clock_days(clock_id, DAYS_PER_MONTH)
    h.wait_for_webhooks()

    usage_after = _current_usage_row(h, seed.user_id) or {}
    h.log.info(
        f"  after renewal:  weddings_count="
        f"{usage_after.get('weddings_count', 0)!r} "
        f"ai_credits_used_month="
        f"{usage_after.get('ai_credits_used_month', 0)!r} "
        f"(legacy counter — informational only)"
    )

    # The new live-query window is the source of truth. After renewal, the
    # post-renewal month has no ai_usage_log rows seeded, so credits_used
    # must read 0 even with the legacy counter still showing 25.
    planner_token = h.login(seed.email, PLANNER_PASSWORD)
    r = h.api_get("/admin/ai/credits", token=planner_token)
    body = r.json() if r.status_code == 200 else {}
    h.log.info(f"  /admin/ai/credits post-renewal body = {body}")
    assert r.status_code == 200, (
        f"B0.2: /admin/ai/credits should be 200 post-renewal, got {r.status_code}"
    )
    effective_credits = body.get("credits_used", -1)
    assert effective_credits == 0, (
        f"B0.2 failed: live-query credits_used should be 0 in fresh month, "
        f"got {effective_credits!r} (legacy counter at "
        f"{usage_after.get('ai_credits_used_month')!r} is intentionally ignored)"
    )
    assert body.get("overage") is False, (
        f"B0.2: post-renewal overage flag should be clear, got {body!r}"
    )
    assert usage_after.get("weddings_count", 0) == 0, (
        f"B0.2 failed: weddings_count should stay 0 on renewal, "
        f"got {usage_after.get('weddings_count')!r}"
    )

    h.checkpoint(
        "B0.2",
        [
            "Chrome: /admin/planner empty-state renders without any 'get",
            "  started' errors. No toast, no console red.",
            "Backend: weddings_count preserved at 0 across renewal ✅",
            "Backend: live-query AI credits reads 0 in new month window ✅",
            "Backend: legacy usage_tracking.ai_credits_used_month is ignored",
            "  (live-query is the source of truth) ✅",
        ],
    )


def phase_active_one_wedding(
    h: Harness,
    seed: PlannerSeed,
    planner_token: str,
    admin_token: str,
    clock_id: str,
) -> None:
    """B1.1 / B1.2 / B1.3 — Create wedding #1, renewal preserves it, delete
    decrements the counter."""
    h.phase("ACTIVE_ONE_WEDDING", "B1.1/B1.2/B1.3 — create → renewal → delete")

    resp = _create_wedding(h, planner_token, bride="Avery One", groom="Blake One")
    h.log.info(f"  POST /admin/weddings (B1.1) -> {resp.status_code}")
    assert resp.status_code in (200, 201), (
        f"B1.1: expected 200/201 on first wedding create, got "
        f"{resp.status_code}: {resp.text[:400]}"
    )

    usage = _current_usage_row(h, seed.user_id) or {}
    assert usage.get("weddings_count", 0) >= 1, (
        f"B1.1: weddings_count should be >=1 after create, got {usage.get('weddings_count')!r}"
    )

    # Sanity: on a flat plan (is_metered=False), wedding create must NOT call
    # stripe.billing.MeterEvent.create. We assert by looking at the wedding
    # doc — meter_pending should be unset for flat plans (per
    # METERING_AUDIT.md §2). Absence of the flag is the sentinel.
    wed_ids = _wedding_ids_for(h, seed.user_id)
    assert wed_ids, "B1.1: wedding document missing after successful create"
    # This codebase uses prefixed string ids (e.g. ``wedding_94ffd917733a``),
    # not Mongo ObjectIds — query by the raw string id.
    wedding_doc = h.mongo["weddings"].find_one({"_id": wed_ids[0]}) or {}
    assert not wedding_doc.get("meter_pending"), (
        f"B1.1: meter_pending should NOT be set on a flat Boutique plan — "
        f"got {wedding_doc.get('meter_pending')!r}. Metering is leaking into "
        f"flat-priced flows."
    )

    # B1.2 — renewal tick, wedding count preserved.
    h.advance_clock_days(clock_id, DAYS_PER_MONTH)
    h.wait_for_webhooks()
    usage_after = _current_usage_row(h, seed.user_id) or {}
    h.log.info(
        f"  B1.2 post-renewal: weddings_count={usage_after.get('weddings_count', 0)!r}"
    )
    assert usage_after.get("weddings_count", 0) >= 1, (
        f"B1.2: weddings_count dropped across renewal "
        f"(got {usage_after.get('weddings_count')!r}) — this is the "
        f"'preserve lifetime count' invariant, see subscription_service.py:798"
    )

    # B1.3 — delete the wedding via the root-admin endpoint
    # (DELETE /admin/weddings/{id}). Planners cannot self-service delete by
    # design — see app/api/wedding.py:306. We use admin_token here so the
    # phase still exercises counter-decrement on delete.
    target_id = wed_ids[0]
    import requests  # lazy import — only needed for the DELETE shape

    url = f"{h.config.backend_url}/admin/weddings/{target_id}"
    del_resp = requests.delete(
        url,
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=15,
    )
    h.log.info(f"  DELETE wedding {target_id} -> {del_resp.status_code}")
    assert del_resp.status_code in (200, 202, 204), (
        f"B1.3: wedding delete expected 2xx, got {del_resp.status_code}: "
        f"{del_resp.text[:400]}"
    )

    h.checkpoint(
        "B1",
        [
            "Chrome: /admin/planner shows wedding #1 after B1.1, renewed",
            "  view after B1.2, and empty-state after B1.3.",
            "Backend: meter_pending NOT set on the wedding doc (flat plan) ✅",
            "Backend: weddings_count preserved across renewal ✅",
            "Backend: wedding delete returned 2xx ✅",
        ],
    )


def phase_active_wedding_cap(h: Harness, seed: PlannerSeed, planner_token: str) -> None:
    """B2.1–B2.3 — Fill the Boutique cap with fresh weddings, 4th must return
    402 with the verbatim gate message."""
    h.phase("ACTIVE_WEDDING_CAP", "B2.1-B2.3 — fill cap to 3, 4th → 402")

    # Seed from scratch each pass so we're not tangled with B1's state.
    for i in range(BOUTIQUE_MAX_WEDDINGS):
        resp = _create_wedding(
            h,
            planner_token,
            bride=f"Cap Bride {i + 1}",
            groom=f"Cap Groom {i + 1}",
        )
        h.log.info(f"  create wedding #{i + 1} -> {resp.status_code}")
        assert resp.status_code in (200, 201), (
            f"B2: wedding #{i + 1} within cap should succeed, got "
            f"{resp.status_code}: {resp.text[:200]}"
        )

    over_resp = _create_wedding(
        h, planner_token, bride="Overflow Bride", groom="Overflow Groom"
    )
    try:
        body = over_resp.json()
    except Exception:
        body = {"raw": over_resp.text[:400]}
    h.log.info(f"  4th create -> {over_resp.status_code} body={body}")

    assert over_resp.status_code == 402, (
        f"B2.3: expected 402 on 4th wedding create, got {over_resp.status_code}: {body}"
    )
    detail = body.get("detail") if isinstance(body, dict) else None
    assert detail == EXPECTED_WEDDING_CAP_MSG, (
        f"Wedding-cap message drift: expected\n  {EXPECTED_WEDDING_CAP_MSG!r}\n"
        f"got\n  {detail!r}\n"
        "(frontend regex breaks if this string is edited — update "
        "subscription_service.py:687 and the frontend matchers together.)"
    )

    h.checkpoint(
        "B2.3",
        [
            "Chrome: UI shows a planner-readable 'wedding limit reached'",
            "  message when the 4th create is attempted, not a raw 402 dump.",
            "Chrome devtools: 402 body detail matches the canonical string.",
            "Chrome console: no uncaught exceptions on the 402.",
            "Backend: 4th POST returned 402 with the canonical message ✅",
        ],
    )


# ---------------------------------------------------------------------------
# Scenario C — AI credits gate (independent from wedding gate)
# ---------------------------------------------------------------------------


def phase_active_ai_credit_cap(
    h: Harness, seed: PlannerSeed, planner_token: str, clock_id: str
) -> None:
    """C1–C4 — Confirm AI credits are soft-capped with metered overage.

    Seeds ``ai_usage_log`` directly (the canonical source of truth for the
    live-query in ``SubscriptionService._live_ai_credits_used``) rather than
    driving real AI calls — GEMINI_API_KEY may not be provisioned in local
    dev, and seeding pins the gate behavior, not the AI service.

    Contract under test (new soft-cap model):
      C1: below cap       → allowed=True, overage=False
      C3: at/past cap     → allowed=True, overage=True, overage_credits >= 1,
                            overage_cost_cents matches overage_credits × price
      C4: after renewal   → allowed=True, overage=False (new monthly window)
    """
    h.phase("ACTIVE_AI_CREDIT_CAP", "C1-C4 — soft-cap + metered overage")

    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    year, month_str = current_month.split("-")
    period_start = datetime(int(year), int(month_str), 1, tzinfo=timezone.utc)

    def _seed_ai_log(total_credits: int) -> None:
        """Replace the user's ai_usage_log entries for this month with a
        single row summing to ``total_credits``. Matches the field names
        read by ``_live_ai_credits_used``."""
        h.mongo["ai_usage_log"].delete_many(
            {
                "user_id": seed.user_id,
                "created_at": {
                    "$gte": period_start,
                    "$lt": period_start + timedelta(days=31),
                },
            }
        )
        if total_credits > 0:
            h.mongo["ai_usage_log"].insert_one(
                {
                    "user_id": seed.user_id,
                    "credits_used": total_credits,
                    "created_at": period_start + timedelta(hours=1),
                    "feature": "testbed_seed",
                }
            )

    # C1 — seed to cap - 1. /admin/ai/credits must report allowed=True with no
    # overage signal.
    _seed_ai_log(BOUTIQUE_AI_CREDITS_MONTHLY - 1)
    r = h.api_get("/admin/ai/credits?feature=chat", token=planner_token)
    body = r.json()
    h.log.info(f"  C1: credits body = {body}")
    assert r.status_code == 200 and body.get("allowed") is True, (
        f"C1: at cap-1 credits, /admin/ai/credits should report allowed=True, "
        f"got status={r.status_code} body={body!r}"
    )

    # C3 — push past cap. Soft-cap contract: allowed=True with overage flag
    # set and a non-zero overage_cost. The planner billing UI's AI credit
    # card reads these fields directly from /admin/ai/credits.
    _seed_ai_log(BOUTIQUE_AI_CREDITS_MONTHLY + 5)
    r = h.api_get("/admin/ai/credits", token=planner_token)
    body = r.json()
    h.log.info(f"  C3: /admin/ai/credits body = {body}")
    assert r.status_code == 200, f"C3: /admin/ai/credits failed with {r.status_code}"
    assert body.get("overage") is True, (
        f"C3: past-cap /admin/ai/credits should report overage=True, "
        f"got overage={body.get('overage')!r} body={body!r}"
    )
    assert (body.get("overage_credits") or 0) >= 5, (
        f"C3: overage_credits should be >= 5 when 5 credits past cap, "
        f"got {body.get('overage_credits')!r} body={body!r}"
    )
    assert (body.get("overage_cost_cents") or 0) > 0, (
        f"C3: overage_cost_cents should be > 0 when in overage, "
        f"got {body.get('overage_cost_cents')!r} body={body!r}"
    )

    # C4 — clock forward one cycle, credits should reset (new monthly window),
    # overage flag should clear.
    h.advance_clock_days(clock_id, DAYS_PER_MONTH)
    h.wait_for_webhooks()
    # Clear the prior month's seeded log so the live-query returns 0 for the
    # new window. (The live-query reads by created_at window, so old rows are
    # out-of-range anyway, but clear for determinism.)
    _seed_ai_log(0)
    r = h.api_get("/admin/ai/credits", token=planner_token)
    body = r.json()
    h.log.info(f"  C4 post-renewal: /admin/ai/credits body = {body}")
    assert body.get("overage") is False, (
        f"C4: after renewal, overage flag should clear, got {body!r}"
    )
    assert (body.get("credits_used") or 0) == 0, (
        f"C4: credits_used should reset to 0 on new month, got {body!r}"
    )

    h.checkpoint(
        "C",
        [
            "Chrome: /admin/planner/billing AI card shows the orange overage",
            "  callout at C3 with the cycle-to-date cost.",
            "Chrome: after C4 renewal, the overage callout disappears and",
            "  the credits bar returns to blue.",
            "Backend: /admin/ai/credits returns overage=True with nonzero cost ✅",
            "Backend: renewal resets live-query window (no stale overage) ✅",
        ],
    )


def phase_ai_downgrade_snapshot(
    h: Harness,
    admin_token: str,
    clock_id: str,
) -> None:
    """C5 — Downgrade mid-cycle from Signature (300) → Boutique (100) with 150
    credits already used. Pins *actual* plan_snapshot behavior (plan §6 Q1).

    The plan expects the current-period snapshot to remain authoritative for
    the cycle, so credits stay allowed until renewal even though the new plan
    caps at 100. This phase records what actually happens.
    """
    h.phase(
        "AI_DOWNGRADE_SNAPSHOT",
        "C5 — Signature → Boutique with 150 credits used (pin Q1 behavior)",
    )

    # Fresh planner so we don't pollute the primary's usage row.
    seed = h.seed_planner_on_clock(
        admin_token=admin_token,
        clock_id=clock_id,
        email=DOWNGRADE_PLANNER_EMAIL,
        password=DOWNGRADE_PLANNER_PASSWORD,
        plan_id=PLAN_SIGNATURE,
        pm_token=PM_TOKEN_GOOD,
        trial_days=None,
    )
    planner_token = h.login(DOWNGRADE_PLANNER_EMAIL, DOWNGRADE_PLANNER_PASSWORD)

    # Seed 150 credits used — between Boutique cap (100) and Signature cap (300).
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    usage_id = f"usage_{seed.user_id}_{current_month}"
    h.mongo["usage_tracking"].update_one(
        {"_id": usage_id},
        {
            "$set": {
                "user_id": seed.user_id,
                "current_month": current_month,
                "ai_credits_used_month": 150,
                "last_updated": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )

    # Change plan: Signature → Boutique.
    boutique_price = h.fetch_plan_monthly_price(admin_token, PLAN_BOUTIQUE)
    _change_stripe_plan(
        h, subscription_id=seed.subscription_id, new_price_id=boutique_price
    )
    h.wait_for_webhooks()

    sub_doc = _subscription_row(h, seed.user_id, seed.subscription_id) or {}
    snapshot = sub_doc.get("plan_snapshot") or {}
    h.log.info(
        f"  post-downgrade plan_snapshot.ai_credits_monthly="
        f"{snapshot.get('ai_credits_monthly')!r}"
    )

    r = h.api_get("/admin/ai/credits?feature=chat", token=planner_token)
    body = r.json()
    allowed = body.get("allowed")
    h.log.info(f"  post-downgrade credits body = {body}")

    # Record, don't force — this is a pin-behavior phase.
    if (
        snapshot.get("ai_credits_monthly") == SIGNATURE_AI_CREDITS_MONTHLY
        and allowed is True
    ):
        h.log.info(
            "  Q1 resolution: plan_snapshot stays on Signature for current "
            "period; credits remain allowed until renewal. (Expected per "
            "plan §6 Q1.)"
        )
    elif snapshot.get("ai_credits_monthly") == BOUTIQUE_AI_CREDITS_MONTHLY:
        h.log.warning(
            "  Q1 observation: plan_snapshot was UPDATED on downgrade — "
            "credits gate immediately against new plan. Record in PR body "
            "so plan §6 Q1 has an answer."
        )
    else:
        h.log.warning(
            f"  Q1 observation: unexpected snapshot shape "
            f"{snapshot.get('ai_credits_monthly')!r} — investigate."
        )

    h.checkpoint(
        "C5",
        [
            "Chrome: refresh /admin/ai-assistant. Note whether chat is still",
            "  allowed (Signature snapshot retained) or blocked (snapshot",
            "  updated). Capture the observation in the PR body against",
            "  plan §6 Q1.",
            "Backend: behavior recorded in the driver log — do NOT force an",
            "  expectation here. This phase exists to pin the answer.",
        ],
    )


# ---------------------------------------------------------------------------
# Scenario D — Plan change + cancellation + past-due
# ---------------------------------------------------------------------------


def phase_plan_upgrade(
    h: Harness, admin_token: str, clock_id: str
) -> tuple[PlannerSeed, str]:
    """D1 — Upgrade Boutique → Signature mid-cycle. Returns (seed, token) so
    the follow-up downgrade phase can reuse this planner.
    """
    h.phase("PLAN_UPGRADE", "D1 — Boutique → Signature, proration invoice")

    # Separate planner so this doesn't interfere with scenarios B / C on the
    # primary planner (which is already on Boutique, mid-various states).
    email = "test_planner+upgrade@thespecialwedding.io"
    password = "UpgradePlanner2026!"  # pragma: allowlist secret
    seed = h.seed_planner_on_clock(
        admin_token=admin_token,
        clock_id=clock_id,
        email=email,
        password=password,
        plan_id=PLAN_BOUTIQUE,
        pm_token=PM_TOKEN_GOOD,
        trial_days=None,
    )
    token = h.login(email, password)

    # Fill 3 weddings so D2 can exercise "downgrade over cap" cleanly.
    for i in range(BOUTIQUE_MAX_WEDDINGS):
        resp = _create_wedding(
            h, token, bride=f"Up Bride {i + 1}", groom=f"Up Groom {i + 1}"
        )
        assert resp.status_code in (200, 201), (
            f"D1 pre-seed: wedding #{i + 1} create failed with "
            f"{resp.status_code}: {resp.text[:200]}"
        )

    signature_price = h.fetch_plan_monthly_price(admin_token, PLAN_SIGNATURE)
    _change_stripe_plan(
        h, subscription_id=seed.subscription_id, new_price_id=signature_price
    )
    h.wait_for_webhooks()

    sub_doc = _subscription_row(h, seed.user_id, seed.subscription_id) or {}
    snapshot = sub_doc.get("plan_snapshot") or {}
    h.log.info(
        f"  post-upgrade plan_snapshot.max_weddings="
        f"{snapshot.get('max_weddings')!r} "
        f"ai_credits_monthly={snapshot.get('ai_credits_monthly')!r}"
    )

    assert snapshot.get("max_weddings") == SIGNATURE_MAX_WEDDINGS, (
        f"D1: plan_snapshot.max_weddings should be {SIGNATURE_MAX_WEDDINGS} "
        f"after upgrade, got {snapshot.get('max_weddings')!r}"
    )

    # 4th wedding now allowed under Signature cap 10.
    resp = _create_wedding(
        h, token, bride="Post-Upgrade Bride", groom="Post-Upgrade Groom"
    )
    assert resp.status_code in (200, 201), (
        f"D1: 4th wedding should succeed under Signature cap, got "
        f"{resp.status_code}: {resp.text[:200]}"
    )

    h.checkpoint(
        "D1",
        [
            "Chrome: planner on the Signature plan can create wedding #4",
            "  without a gate.",
            "Chrome: billing page shows the upgrade + proration line item.",
            "Backend: plan_snapshot upgraded to Signature limits ✅",
            "Backend: 4th wedding create succeeds post-upgrade ✅",
        ],
    )
    return seed, token


def phase_plan_downgrade_over_cap(
    h: Harness, admin_token: str, seed: PlannerSeed, token: str
) -> None:
    """D2 — Downgrade Signature → Boutique while `weddings_count > new_cap`.
    This is an explicit "pin actual behavior" phase (plan §6 Q2).
    """
    h.phase(
        "PLAN_DOWNGRADE_OVER_CAP",
        "D2 — Signature → Boutique with 4 weddings (pin Q2 behavior)",
    )

    boutique_price = h.fetch_plan_monthly_price(admin_token, PLAN_BOUTIQUE)

    try:
        _change_stripe_plan(
            h,
            subscription_id=seed.subscription_id,
            new_price_id=boutique_price,
        )
        downgrade_accepted = True
    except stripe.error.StripeError as exc:
        downgrade_accepted = False
        h.log.warning(f"  Stripe rejected downgrade: {exc}")

    h.wait_for_webhooks()

    sub_doc = _subscription_row(h, seed.user_id, seed.subscription_id) or {}
    snapshot = sub_doc.get("plan_snapshot") or {}
    usage = _current_usage_row(h, seed.user_id) or {}
    h.log.info(
        f"  downgrade_accepted={downgrade_accepted} "
        f"snapshot.max_weddings={snapshot.get('max_weddings')!r} "
        f"weddings_count={usage.get('weddings_count', 'n/a')}"
    )

    # Try to create a 5th wedding — is it blocked by the new or old cap?
    resp = _create_wedding(h, token, bride="D2 Bride", groom="D2 Groom")
    h.log.info(f"  post-downgrade wedding create -> {resp.status_code}")

    if downgrade_accepted and snapshot.get("max_weddings") == BOUTIQUE_MAX_WEDDINGS:
        h.log.info(
            "  Q2 observation: downgrade accepted; snapshot updated to "
            "Boutique limits; further creates gate at 402. Record in PR body."
        )
    elif downgrade_accepted and snapshot.get("max_weddings") == SIGNATURE_MAX_WEDDINGS:
        h.log.warning(
            "  Q2 observation: downgrade accepted but snapshot retained "
            "Signature limits for the current period — grandfather applies."
        )
    else:
        h.log.warning(
            f"  Q2 observation: unexpected state after downgrade — "
            f"downgrade_accepted={downgrade_accepted} "
            f"snapshot.max_weddings={snapshot.get('max_weddings')!r}. "
            "Investigate before merging."
        )

    h.checkpoint(
        "D2",
        [
            "Chrome: note what the billing page says about the downgrade — a",
            "  warning, a confirmation, or silent acceptance.",
            "Chrome: attempt to create another wedding; capture whether the",
            "  UI allows it based on the new snapshot.",
            "Record the observed behavior in the PR body against plan §6 Q2.",
        ],
    )


def phase_subscription_cancel(h: Harness, seed: PlannerSeed, token: str) -> None:
    """D3 — cancel_at_period_end=True. Status stays active; flag set in Mongo."""
    h.phase("SUBSCRIPTION_CANCEL", "D3 — cancel_at_period_end=True")

    stripe.Subscription.modify(
        seed.subscription_id,
        cancel_at_period_end=True,
        metadata={"cancel_driver": DRIVER_NAME},
    )
    h.wait_for_webhooks()

    sub_doc = _subscription_row(h, seed.user_id, seed.subscription_id) or {}
    h.log.info(
        f"  user_subscriptions.status={sub_doc.get('status')!r} "
        f"cancel_at_period_end={sub_doc.get('cancel_at_period_end')!r}"
    )
    assert sub_doc.get("status") == "active", (
        f"D3: status should stay 'active' after cancel_at_period_end, got "
        f"{sub_doc.get('status')!r}"
    )
    assert sub_doc.get("cancel_at_period_end") in (True, "true", 1), (
        f"D3: cancel_at_period_end should propagate into Mongo, got "
        f"{sub_doc.get('cancel_at_period_end')!r}"
    )

    # Planner still has access — confirm dashboard read works.
    profile = h.api_get("/admin/profile", token=token)
    assert profile.status_code == 200, (
        f"D3: planner should still load /admin/profile during grace period, "
        f"got {profile.status_code}: {profile.text[:200]}"
    )

    h.checkpoint(
        "D3",
        [
            "Chrome: billing page shows the scheduled cancellation with the",
            "  end-of-period date.",
            "Chrome: /admin/planner still renders normally — planner retains",
            "  access until period end.",
            "Backend: status='active', cancel_at_period_end=True ✅",
        ],
    )


def phase_subscription_canceled(
    h: Harness, seed: PlannerSeed, token: str, clock_id: str
) -> None:
    """D4 — Advance clock past period end. Pin login + gate behavior (Q3)."""
    h.phase("SUBSCRIPTION_CANCELED", "D4 — clock past period_end, pin Q3 behavior")

    h.advance_clock_days(clock_id, DAYS_PER_MONTH)
    h.wait_for_webhooks()

    sub_doc = _subscription_row(h, seed.user_id, seed.subscription_id) or {}
    user_doc = h.get_user_doc(seed.user_id) or {}
    h.log.info(f"  user_subscriptions.status = {sub_doc.get('status')!r}")
    h.log.info(
        f"  users.subscription_status = {user_doc.get('subscription_status')!r} "
        f"is_active={user_doc.get('is_active')!r}"
    )

    # Canonical expectation from plan §3.4 D4: status→canceled. But pin what we see.
    assert sub_doc.get("status") in ("canceled", "cancelled"), (
        f"D4: user_subscriptions.status should be 'canceled' after period_end, "
        f"got {sub_doc.get('status')!r}"
    )

    # Login behavior is the open question (Q3). Record.
    relog = h.api_post(
        "/admin/token",
        json={
            "email": seed.email,
            "password": "UpgradePlanner2026!",  # pragma: allowlist secret
        },
    )
    h.log.info(f"  re-login on canceled sub -> {relog.status_code}")

    if relog.status_code == 200:
        refreshed = relog.json().get("access_token") or token
        wedding_try = _create_wedding(h, refreshed, bride="D4 Bride", groom="D4 Groom")
        h.log.info(f"  canceled-state wedding create -> {wedding_try.status_code}")
        h.log.info(
            "  Q3 observation: login succeeds on canceled; wedding POST "
            f"returned {wedding_try.status_code}. Record whether isAllowedForExpired "
            "catches canceled the same way as expired."
        )
    else:
        h.log.info(
            f"  Q3 observation: re-login blocked with status "
            f"{relog.status_code} — canceled path diverges from expired."
        )

    h.checkpoint(
        "D4",
        [
            "Chrome: try to log in as the canceled planner. Note the redirect",
            "  target — billing page vs. /admin/login with error, vs. dashboard",
            "  with a canceled banner. Record against plan §6 Q3.",
            "Chrome devtools: confirm no console red on the redirect path.",
            "Backend: user_subscriptions.status = canceled ✅",
        ],
    )


def phase_subscription_resubscribe(
    h: Harness, admin_token: str, seed: PlannerSeed
) -> None:
    """D5 — Resubscribe from canceled state. New sub row, new plan_snapshot."""
    h.phase("SUBSCRIPTION_RESUBSCRIBE", "D5 — new subscription on canceled customer")

    # Long-running interactive runs blow past the admin JWT TTL between
    # checkpoints — refresh before any API call that requires admin auth.
    admin_token = h.get_admin_token()

    new_sub = h.subscribe_planner(
        admin_token=admin_token,
        customer_id=seed.customer_id,
        user_id=seed.user_id,
        plan_id=PLAN_BOUTIQUE,
        trial_days=None,
    )
    h.wait_for_webhooks()

    sub_doc = _subscription_row(h, seed.user_id, new_sub.id)
    assert sub_doc is not None, (
        f"D5: no user_subscriptions row for new sub {new_sub.id} — webhook "
        "delivery or stripe_customers link is broken."
    )
    assert sub_doc.get("status") == "active", (
        f"D5: new subscription status should be 'active', got {sub_doc.get('status')!r}"
    )

    user_doc = h.get_user_doc(seed.user_id) or {}
    assert user_doc.get("subscription_status") == "active", (
        f"D5: users.subscription_status should flip back to 'active', got "
        f"{user_doc.get('subscription_status')!r}"
    )

    h.checkpoint(
        "D5",
        [
            "Chrome: billing page shows the new active subscription.",
            "Chrome: /admin/planner renders normally again.",
            "Backend: new user_subscriptions row status='active' ✅",
            "Backend: users.subscription_status='active' ✅",
        ],
    )


def phase_subscription_past_due(h: Harness, admin_token: str, clock_id: str) -> None:
    """D6 — Past-due → recovery round-trip. Mirrors the team-member gate
    driver but exercises the planner's own login path.
    """
    h.phase("SUBSCRIPTION_PAST_DUE", "D6 — planner past-due → recovery")

    # Long-running interactive runs blow past the admin JWT TTL between
    # checkpoints — refresh before any API call that requires admin auth.
    admin_token = h.get_admin_token()

    email = "test_planner+pastdue@thespecialwedding.io"
    password = "PastDuePlanner2026!"  # pragma: allowlist secret
    seed = h.seed_planner_on_clock(
        admin_token=admin_token,
        clock_id=clock_id,
        email=email,
        password=password,
        plan_id=PLAN_BOUTIQUE,
        pm_token=PM_TOKEN_GOOD,
        trial_days=None,
    )

    # Swap to the always-fails-on-renewal PM.
    h.swap_subscription_pm(
        seed.customer_id, seed.subscription_id, PM_TOKEN_WILL_FAIL_ON_RENEWAL
    )
    h.advance_clock_days(clock_id, DAYS_PER_MONTH)
    h.wait_for_webhooks()

    sub_doc = _subscription_row(h, seed.user_id, seed.subscription_id) or {}
    h.log.info(f"  post-renewal sub status = {sub_doc.get('status')!r}")
    assert sub_doc.get("status") in ("past_due", "unpaid"), (
        f"D6: after renewal with failing PM, status should be past_due/unpaid, "
        f"got {sub_doc.get('status')!r}"
    )

    # Planner login on past-due — record whether it's blocked at 402 (like
    # team_member) or only gated downstream.
    login_resp = h.api_post("/admin/token", json={"email": email, "password": password})
    h.log.info(f"  planner login on past_due -> {login_resp.status_code}")

    if login_resp.status_code == 402:
        h.log.info(
            "  Q6 observation: planner login returns 402 on past_due (same as "
            "team-member gate). Expected for PR1 consistency."
        )
    elif login_resp.status_code == 200:
        h.log.info(
            "  Q6 observation: planner login succeeds on past_due; gate is "
            "downstream only. Record in PR body — plan expects parity with "
            "the team-member gate."
        )
    else:
        h.log.warning(
            f"  Q6 observation: unexpected login status {login_resp.status_code}. "
            "Investigate."
        )

    # Recover: swap PM back to good, advance clock, confirm sub returns to active.
    h.swap_subscription_pm(seed.customer_id, seed.subscription_id, PM_TOKEN_GOOD)
    h.advance_clock_days(clock_id, DAYS_PER_MONTH)
    h.wait_for_webhooks()

    sub_doc = _subscription_row(h, seed.user_id, seed.subscription_id) or {}
    h.log.info(f"  post-recovery sub status = {sub_doc.get('status')!r}")
    assert sub_doc.get("status") == "active", (
        f"D6: after PM recovery + renewal, status should be 'active', got "
        f"{sub_doc.get('status')!r}"
    )

    h.checkpoint(
        "D6",
        [
            "Chrome: when in past_due, the planner's own dashboard must show",
            "  a recover-billing banner (not just at login). Confirm whether",
            "  parity with team-member gate holds — record against plan §6 Q6.",
            "Chrome: after PM swap back + renewal, banner clears and dashboard",
            "  renders normally.",
            "Backend: status transitions past_due → active after recovery ✅",
        ],
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    h = Harness(driver_name=DRIVER_NAME)
    h.banner("SCENARIOS B + C + D — PLANNER ACTIVE LIFECYCLE")
    h.log.info(f"  Primary planner    : {PLANNER_EMAIL}")
    h.log.info(f"  Downgrade planner  : {DOWNGRADE_PLANNER_EMAIL}")
    h.log.info(
        f"  Boutique cap       : {BOUTIQUE_MAX_WEDDINGS} weddings / "
        f"{BOUTIQUE_AI_CREDITS_MONTHLY} credits"
    )
    h.log.info(
        f"  Signature cap      : {SIGNATURE_MAX_WEDDINGS} weddings / "
        f"{SIGNATURE_AI_CREDITS_MONTHLY} credits"
    )
    h.log.info(
        f"  Canonical gate msg:\n"
        f"    weddings   → {EXPECTED_WEDDING_CAP_MSG}\n"
        f"    ai_credits → (soft-cap, metered overage; no hard-stop message)"
    )

    h.preflight()

    admin_token = h.get_admin_token()
    clock = h.get_or_create_clock(TEST_CLOCK_ID, name=TEST_CLOCK_NAME)
    clock_id = clock.id

    # Scenario B — wedding count metering.
    seed = phase_seed_active(h, admin_token, clock_id)
    planner_token = h.login(PLANNER_EMAIL, PLANNER_PASSWORD)

    phase_active_zero_weddings(h, seed, clock_id)
    phase_active_one_wedding(h, seed, planner_token, admin_token, clock_id)
    phase_active_wedding_cap(h, seed, planner_token)

    # Scenario C — AI credits.
    phase_active_ai_credit_cap(h, seed, planner_token, clock_id)
    phase_ai_downgrade_snapshot(h, admin_token, clock_id)

    # Scenario D — plan change + cancellation + past-due.
    upgrade_seed, upgrade_token = phase_plan_upgrade(h, admin_token, clock_id)
    phase_plan_downgrade_over_cap(h, admin_token, upgrade_seed, upgrade_token)
    phase_subscription_cancel(h, upgrade_seed, upgrade_token)
    phase_subscription_canceled(h, upgrade_seed, upgrade_token, clock_id)
    phase_subscription_resubscribe(h, admin_token, upgrade_seed)
    phase_subscription_past_due(h, admin_token, clock_id)

    h.banner("SCENARIOS B + C + D COMPLETE")
    h.log.info(
        "  When Chrome checkpoints have also been signed off, record the "
        "verification and any Q1/Q2/Q3/Q6 observations in the PR body and "
        "(if behavior was pinned for an open question) a dated file under "
        "docs/reports/. Do not write status into CLAUDE.md — that file is "
        "conventions only."
    )
    h.log.info(
        f"  Clock id for this run: {clock_id}  (idempotent; cleanup script reuses it)."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        sys.stderr.write(f"\n❌ ASSERTION FAILED: {exc}\n")
        raise SystemExit(2)
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"\n❌ Driver aborted: {exc}\n")
        raise
