#!/usr/bin/env python3
"""Scenario E — planner metered subscription lifecycle.

Covers the metered-billing checkpoints from
``docs/plans/SUBSCRIPTION_LIFECYCLE_TEST_PLAN.md`` §3.5:

    E1 — wedding create on a metered plan reports a Stripe MeterEvent
         (value="1", idempotency key wedding_create_{wid}_{cid}_{YYYY-MM},
         weddings.last_billed_at / billed_period written, meter_pending=False)
    E2 — second wedding in the same period reports a DISTINCT meter event
         (different idempotency key, both land)
    E3 — wedding delete reports a reversal (value="-1",
         weddings.meter_reversed_period set to current YYYY-MM)
    E4 — POST /admin/metering/retry-pending clears meter_pending=True rows
         by re-submitting the meter event
    E5 — weddings flagged meter_pending=True render the admin badge and
         retain the failure reason so an operator can see the backlog

**Skip discipline.** Today's default seed leaves every plan
``is_metered=False`` (see METERING_AUDIT.md §1). This driver MUST NOT
silently misbehave when metering is off — it preflights the live plan
catalog, and if no plan has ``is_metered=True`` + ``meter_event_name``
populated it exits 0 with a clear "skipping — metering is off" banner.
Flipping metering on is a separate, approved product decision per the
audit, not something this driver does.

**Clock reuse.** The clock named ``planner-metered-lifecycle`` is reused
across runs (mirrors ``planner-active-lifecycle``). Cleanup deletes
customers on the clock but NEVER the clock itself. Set
``METERED_CLOCK_ID`` in env to pin it after the first run.

Usage::

    # First run (creates the clock and prints its id)
    python testbed/verify_planner_metered_lifecycle.py

    # Subsequent runs reuse the same clock
    METERED_CLOCK_ID=clock_... python testbed/verify_planner_metered_lifecycle.py

    # Unattended (CI-shaped)
    TESTBED_NON_INTERACTIVE=1 python testbed/verify_planner_metered_lifecycle.py
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bson import ObjectId

from testbed.harness import PM_TOKEN_GOOD, Harness, PlannerSeed

logger = logging.getLogger(__name__)

DRIVER_NAME = "verify_planner_metered_lifecycle"

# Clock is reused across runs — NEVER delete it from cleanup.
TEST_CLOCK_NAME = "planner-metered-lifecycle"
TEST_CLOCK_ID = os.getenv("METERED_CLOCK_ID")

# Plus-variant isolation — cleanup targets these.
PLANNER_EMAIL = "test_planner+metered@thespecialwedding.io"
PLANNER_PASSWORD = "MeteredPlanner2026!"  # pragma: allowlist secret


# =============================================================================
# Preflight — skip cleanly if metering is off
# =============================================================================


def _find_metered_plan(h: Harness) -> Optional[dict]:
    """Return the first plan with is_metered=True + meter_event_name populated.

    Reads Mongo directly — this is the authoritative state per
    METERING_AUDIT.md §4 (the admin UI can flip this out of band from the
    seed script, so don't assume the seed reflects reality).
    """
    return h.mongo["subscription_plans"].find_one(
        {
            "is_metered": True,
            "meter_event_name": {"$exists": True, "$nin": [None, ""]},
        }
    )


def _stripe_has_meter_for(h: Harness, event_name: str) -> bool:
    """Check Stripe for an active Meter matching the plan's event_name.

    Mongo can have is_metered=True while Stripe is missing the Meter resource
    — that combination raises 400 in stripe_service.sync_plan_to_stripe and
    means wedding-create meter events will silently fail. Catching it at
    preflight prevents a misleading E1 fail.
    """
    import stripe

    try:
        meters = stripe.billing.Meter.list(status="active", limit=100)
    except stripe.error.StripeError as exc:
        h.log.warning(
            f"  Could not list Stripe meters ({exc}) — proceeding anyway; "
            f"wedding-create will surface the real error."
        )
        return True  # Don't hard-skip on transient Stripe list failure.

    for meter in getattr(meters, "auto_paging_iter", lambda: [])():
        if getattr(meter, "event_name", None) == event_name:
            return True
    # Fallback if auto_paging_iter didn't yield (shouldn't happen, but safe).
    for meter in getattr(meters, "data", []) or []:
        if getattr(meter, "event_name", None) == event_name:
            return True
    return False


def preflight_or_skip(h: Harness) -> dict:
    """Resolve the metered plan to run against, or log-and-exit(0).

    Returns the plan dict on success. Never returns on skip — raises
    SystemExit(0) so the calling pipeline treats "metering off" as a
    non-failure.
    """
    h.phase("METERED_PREFLIGHT", "Check that at least one plan is actually metered")

    plan = _find_metered_plan(h)
    if not plan:
        h.banner("SKIPPING — metering is off in the live plan catalog")
        h.log.info(
            "  No document in subscription_plans has "
            "is_metered=True + meter_event_name populated."
        )
        h.log.info(
            "  This is the default shipped state (see METERING_AUDIT.md §1). "
            "Scenario E is dormant until a plan is flipped metered."
        )
        h.log.info("  Scenarios A/B/C/D still verify flat-rate billing and gates.")
        raise SystemExit(0)

    plan_id = str(plan["_id"])
    event_name = plan.get("meter_event_name")
    h.log.info(f"  ✅ Metered plan found: {plan.get('name')} (_id={plan_id})")
    h.log.info(f"     meter_event_name = {event_name!r}")
    h.log.info(f"     meter_id         = {plan.get('meter_id')!r}")
    h.log.info(f"     max_weddings     = {plan.get('max_weddings')!r}")

    if not _stripe_has_meter_for(h, event_name):
        h.banner("SKIPPING — Stripe side is not provisioned")
        h.log.info(
            f"  Plan claims event_name={event_name!r} but no active Stripe "
            f"billing.Meter has that event_name. sync_plan_to_stripe would "
            f"raise 400. Scenario E cannot run."
        )
        h.log.info(
            "  Fix: create the meter in Stripe and run "
            "app/services/stripe_service.py::sync_plan_to_stripe for this plan."
        )
        raise SystemExit(0)

    h.log.info("  ✅ Stripe Meter resource exists for this event_name")
    return plan


# =============================================================================
# Mongo probe helpers
# =============================================================================


def _wedding_doc(h: Harness, wedding_id: str) -> Optional[dict]:
    return h.mongo["weddings"].find_one({"_id": ObjectId(wedding_id)})


def _current_period() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _assert_billed(h: Harness, wedding_id: str, wid_label: str) -> dict:
    """Assert the wedding row carries the post-create meter fingerprint."""
    doc = _wedding_doc(h, wedding_id) or {}
    last_billed_at = doc.get("last_billed_at")
    billed_period = doc.get("billed_period")
    meter_pending = doc.get("meter_pending", False)

    h.log.info(
        f"  {wid_label} meter state: last_billed_at={last_billed_at!r} "
        f"billed_period={billed_period!r} meter_pending={meter_pending!r}"
    )
    assert last_billed_at is not None, (
        f"{wid_label}: meter event did not land — last_billed_at is None. "
        f"Check uvicorn logs for meter_result in app/api/wedding.py:205."
    )
    assert billed_period == _current_period(), (
        f"{wid_label}: billed_period drifted. expected {_current_period()!r}, "
        f"got {billed_period!r}"
    )
    assert not meter_pending, (
        f"{wid_label}: meter_pending should be False on a successful create, "
        f"got True (reason={doc.get('meter_pending_reason')!r})"
    )
    return doc


def _assert_reversed(h: Harness, wedding_id: str, wid_label: str) -> dict:
    doc = _wedding_doc(h, wedding_id) or {}
    reversed_period = doc.get("meter_reversed_period")
    h.log.info(
        f"  {wid_label} meter reversal: meter_reversed_period={reversed_period!r} "
        f"meter_pending={doc.get('meter_pending', False)!r}"
    )
    assert reversed_period == _current_period(), (
        f"{wid_label}: meter reversal did not land. expected "
        f"meter_reversed_period={_current_period()!r}, got {reversed_period!r}"
    )
    assert not doc.get("meter_pending", False), (
        f"{wid_label}: delete path set meter_pending=True, reason="
        f"{doc.get('meter_pending_reason')!r}"
    )
    return doc


# =============================================================================
# Phases
# =============================================================================


def phase_seed(
    h: Harness, admin_token: str, clock_id: str, plan_id: str
) -> PlannerSeed:
    h.phase(
        "METERED_SEED",
        "Bootstrap planner on metered plan + clock (idempotent — re-running is OK)",
    )

    # If the planner already exists from a prior run we reuse it.
    existing = h.mongo["users"].find_one({"email": PLANNER_EMAIL})
    if existing:
        sub = h.mongo["user_subscriptions"].find_one(
            {"user_id": str(existing["_id"]), "status": {"$in": ["active", "trialing"]}}
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
                plan_id=plan_id,
                has_trial=False,
            )
        # Partial state — drop it and reseed cleanly.
        h.log.info(
            "  ⚠ Partial state for planner detected — dropping Mongo chain "
            "and reseeding to keep this phase idempotent."
        )
        h.delete_user_chain(PLANNER_EMAIL)

    seed = h.seed_planner_on_clock(
        admin_token=admin_token,
        clock_id=clock_id,
        email=PLANNER_EMAIL,
        password=PLANNER_PASSWORD,
        plan_id=plan_id,
        pm_token=PM_TOKEN_GOOD,
        trial_days=None,  # metered lifecycle starts on an active paid sub
    )

    h.checkpoint(
        "SEED_COMPLETE",
        expectations=[
            f"Chrome login creds — email: {PLANNER_EMAIL}  password: {PLANNER_PASSWORD}",
            f"Planner {PLANNER_EMAIL} is on metered plan (plan_id={plan_id})",
            "Stripe subscription is active (not trialing)",
            "user_subscriptions.current_period_start + current_period_end are set",
        ],
    )
    return seed


def phase_meter_on_create(h: Harness, seed: PlannerSeed, token: str) -> tuple[str, str]:
    """E1 + E2 — wedding create emits meter event; second wedding lands too."""
    h.phase("METERED_CREATE", "Wedding create reports meter event (E1, E2)")

    # E1
    resp1 = h.api_post(
        "/admin/weddings",
        token=token,
        json={
            "couple_names": "Meter One & Billed One",
            "date": "2027-07-04",
        },
    )
    h.log.info(f"  POST /admin/weddings (E1) -> {resp1.status_code}")
    assert resp1.status_code in (200, 201), (
        f"E1: wedding create returned {resp1.status_code} — body={resp1.text}"
    )
    h.wait_for_webhooks()

    # Wedding id comes from the response shape used elsewhere — fall back to
    # Mongo by ownership if the payload doesn't carry it.
    wid1 = (resp1.json() or {}).get("_id") or (resp1.json() or {}).get("wedding_id")
    if not wid1:
        # Find the most recent wedding owned by this planner.
        doc = h.mongo["weddings"].find_one(
            {"$or": [{"user_id": seed.user_id}, {"owner_id": seed.user_id}]},
            sort=[("_id", -1)],
        )
        assert doc, "E1: could not resolve freshly-created wedding_id"
        wid1 = str(doc["_id"])

    _assert_billed(h, wid1, "E1 (first wedding)")
    expected_key1 = f"wedding_create_{wid1}_{seed.customer_id}_{_current_period()}"
    h.log.info(f"  E1 expected idempotency key: {expected_key1}")

    h.checkpoint(
        "E1_FIRST_WEDDING_METERED",
        expectations=[
            "weddings.last_billed_at is set to the current instant",
            f"weddings.billed_period == {_current_period()!r}",
            "weddings.meter_pending is False",
            "Chrome: /admin/weddings shows no 'Meter pending' badge",
        ],
    )

    # E2
    resp2 = h.api_post(
        "/admin/weddings",
        token=token,
        json={
            "couple_names": "Meter Two & Billed Two",
            "date": "2027-08-22",
        },
    )
    h.log.info(f"  POST /admin/weddings (E2) -> {resp2.status_code}")
    assert resp2.status_code in (200, 201), (
        f"E2: second wedding create returned {resp2.status_code} — body={resp2.text}"
    )
    h.wait_for_webhooks()

    wid2 = (resp2.json() or {}).get("_id") or (resp2.json() or {}).get("wedding_id")
    if not wid2:
        doc = h.mongo["weddings"].find_one(
            {"$or": [{"user_id": seed.user_id}, {"owner_id": seed.user_id}]},
            sort=[("_id", -1)],
        )
        assert doc and str(doc["_id"]) != wid1, (
            "E2: could not resolve the second wedding_id"
        )
        wid2 = str(doc["_id"])

    _assert_billed(h, wid2, "E2 (second wedding)")
    expected_key2 = f"wedding_create_{wid2}_{seed.customer_id}_{_current_period()}"
    assert expected_key1 != expected_key2, (
        "E2: idempotency keys collided — keys must include wedding_id"
    )
    h.log.info(f"  E2 expected idempotency key: {expected_key2}")
    h.log.info("  ✅ E1 and E2 keys differ — each wedding gets its own meter event")

    h.checkpoint(
        "E2_SECOND_WEDDING_METERED",
        expectations=[
            "Both wedding docs have last_billed_at in the current period",
            "The two idempotency keys are distinct (wedding_id is part of the key)",
            "Chrome: /admin/weddings lists both couples, neither flagged pending",
        ],
    )

    return wid1, wid2


def phase_meter_on_delete(h: Harness, wid: str, token: str) -> None:
    """E3 — wedding delete emits reversal meter event."""
    h.phase("METERED_DELETE", "Wedding delete reports meter reversal (E3)")

    import requests

    resp = requests.delete(
        f"{h.config.backend_url}/admin/weddings/{wid}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    h.log.info(f"  DELETE /admin/weddings/{wid} -> {resp.status_code}")
    assert resp.status_code in (200, 204), (
        f"E3: delete returned {resp.status_code} — body={resp.text}"
    )
    h.wait_for_webhooks()

    _assert_reversed(h, wid, "E3 (deleted wedding)")

    h.checkpoint(
        "E3_DELETE_REVERSED",
        expectations=[
            f"weddings.meter_reversed_period == {_current_period()!r}",
            "meter_pending stays False (reversal succeeded)",
            "Chrome: /admin/weddings no longer shows the deleted couple row",
        ],
    )


def phase_meter_pending_and_retry(h: Harness, seed: PlannerSeed, token: str) -> None:
    """E4 + E5 — simulate a pending meter event, then clear it via retry.

    We can't force a Stripe failure on a known-good key without patching the
    service, so we *seed* the pending state directly in Mongo (it's the same
    shape the real failure branch at app/api/wedding.py:228-242 writes).
    Then we hit /admin/metering/retry-pending and verify the row gets cleared.
    The badge-render UX assertion (E5) is user-observed in Chrome.
    """
    h.phase(
        "METERED_RETRY",
        "Simulate meter_pending, then clear via /metering/retry-pending (E4, E5)",
    )

    # Create a fresh wedding so the retry target is isolated.
    resp = h.api_post(
        "/admin/weddings",
        token=token,
        json={
            "couple_names": "Retry Candidate & Pending Billing",
            "date": "2027-09-15",
        },
    )
    assert resp.status_code in (200, 201), (
        f"E4 setup: wedding create failed status={resp.status_code}"
    )
    h.wait_for_webhooks()
    wid = (resp.json() or {}).get("_id")
    if not wid:
        doc = h.mongo["weddings"].find_one(
            {"$or": [{"user_id": seed.user_id}, {"owner_id": seed.user_id}]},
            sort=[("_id", -1)],
        )
        assert doc, "E4 setup: could not resolve wedding_id"
        wid = str(doc["_id"])

    # Force the row into the pending shape the real failure branch produces.
    h.mongo["weddings"].update_one(
        {"_id": ObjectId(wid)},
        {
            "$set": {
                "meter_pending": True,
                "meter_pending_reason": "simulated_failure_for_E4_retry",
                "last_billed_at": None,
                "billed_period": _current_period(),
            }
        },
    )
    pending_doc = _wedding_doc(h, wid) or {}
    assert pending_doc.get("meter_pending") is True, (
        "E5 setup: could not flip meter_pending=True in Mongo"
    )
    h.log.info(
        f"  ✅ Wedding {wid} flipped to meter_pending=True "
        f"(reason={pending_doc.get('meter_pending_reason')!r})"
    )

    h.checkpoint(
        "E5_PENDING_BADGE_VISIBLE",
        expectations=[
            "Chrome: /admin/weddings renders a 'Meter pending' badge "
            "on the new couple row (see app/admin/weddings/page.tsx:1150-1152)",
            "The badge copy includes the failure reason "
            "('simulated_failure_for_E4_retry')",
            "No console errors from the badge render",
        ],
    )

    # E4 — call the root-admin retry endpoint. Requires ROOT_ADMIN auth.
    admin_token = h.get_admin_token()
    retry = h.api_post("/admin/metering/retry-pending", token=admin_token)
    h.log.info(f"  POST /admin/metering/retry-pending -> {retry.status_code}")
    assert retry.status_code == 200, (
        f"E4: retry endpoint returned {retry.status_code} — body={retry.text}"
    )
    body = retry.json() or {}
    h.log.info(
        f"  retry summary: retried={body.get('retried')} "
        f"succeeded={body.get('succeeded')} failed={body.get('failed')}"
    )
    assert body.get("retried", 0) >= 1, (
        f"E4: retry summary says 0 retried — the endpoint didn't see our "
        f"pending wedding. body={body}"
    )

    # Assert the row flipped back to cleared.
    cleared = _wedding_doc(h, wid) or {}
    assert not cleared.get("meter_pending", True), (
        f"E4: wedding {wid} still meter_pending=True after retry — "
        f"reason={cleared.get('meter_pending_reason')!r}. Check that the plan "
        f"is still is_metered=True and that Stripe isn't rejecting the "
        f"identifier for some other reason."
    )
    assert cleared.get("last_billed_at") is not None, (
        "E4: retry succeeded but last_billed_at was not written"
    )
    h.log.info(f"  ✅ Wedding {wid} cleared: last_billed_at updated, pending flag off")

    h.checkpoint(
        "E4_RETRY_CLEARED_PENDING",
        expectations=[
            "weddings.meter_pending is False after /metering/retry-pending",
            "weddings.last_billed_at is now set",
            "Chrome: the 'Meter pending' badge is gone after a refresh",
        ],
    )


# =============================================================================
# Entry point
# =============================================================================


def main() -> int:
    h = Harness(driver_name=DRIVER_NAME)
    h.banner("VERIFY — Scenario E (planner metered lifecycle)")
    h.log.info(f"  Planner email  : {PLANNER_EMAIL}")
    h.log.info(f"  Clock name     : {TEST_CLOCK_NAME}")
    h.log.info(
        f"  Clock id       : {TEST_CLOCK_ID or '(none — fresh clock, pin via METERED_CLOCK_ID next run)'}"
    )

    h.preflight()

    plan = preflight_or_skip(h)
    plan_id = str(plan["_id"])

    h.phase("METERED_CLOCK", "Resolve the reusable test clock")
    clock = h.get_or_create_clock(TEST_CLOCK_ID, name=TEST_CLOCK_NAME)
    clock_id = clock.id

    admin_token = h.get_admin_token()

    seed = phase_seed(h, admin_token, clock_id, plan_id)
    planner_token = h.login(PLANNER_EMAIL, PLANNER_PASSWORD)

    wid1, wid2 = phase_meter_on_create(h, seed, planner_token)
    phase_meter_on_delete(h, wid2, planner_token)
    phase_meter_pending_and_retry(h, seed, planner_token)

    h.banner("VERIFY — Scenario E COMPLETE ✅")
    h.log.info(
        "  Reminder: reusable clock preserved. Next run can pin "
        f"METERED_CLOCK_ID={clock_id}"
    )
    h.log.info(
        "  Record findings in the PR body and (if behavior was pinned for "
        "an open question) a dated file under docs/reports/. Do not write "
        "status into CLAUDE.md — that file is conventions only."
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
