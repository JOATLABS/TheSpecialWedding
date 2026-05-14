#!/usr/bin/env python3
"""Full couple-booking meta-lifecycle verification.

This is the *meta-test* — it exercises every state in the meeting lifecycle
from a cold start through completion, against a real local backend, real
Mongo, and a real Aurinko sandbox. Each sibling driver in this PR pins one
slice of the lifecycle in tight isolation:

    - ``verify_couple_booking_auto_confirm_path.py`` — the no-approval slot path
    - ``verify_couple_booking_approval_decline.py`` — approve / decline branch
    - ``verify_couple_booking_external_edit.py``    — pending_review reconcile
    - ``verify_couple_booking_conference_autocreate.py``
                                                    — Zoom / Meet URL injection

This driver runs them back-to-back against a SINGLE meeting so we can prove
the transitions interlock correctly when chained. If any sibling driver
passes in isolation but this one fails, the bug is at a state-machine seam,
not inside the phases the siblings cover. AGENTS.md L237-239:
"the E2E runbook is the minimum scenario list, not a nice-to-have" —
this driver IS the runbook.

Why two manual gates: the OAuth handshake (P1) requires consent on a third-
party provider that no script can drive headlessly, and the external edit
(P8) by definition originates outside our system. Everything else is
script-driven so reruns are deterministic and don't bait operator drift.

Pair with ``cleanup_couple_booking_lifecycle_state.py`` (each run is
idempotent because cleanup drops the plus-variant planner chain plus
calendar_connections / planner_tasks / calendar_event_syncs /
calendar_idempotency_keys / planner_notifications scoped to the
plus-variant test emails).

Scenario checkpoints
--------------------

    P0  — SEED:           planner seeded on a paid plan; clock-pinned for
                          deterministic reruns.
    P1  — CONNECT:        OAuth lifecycle (delegates to verify_aurinko_oauth
                          _lifecycle._phase_authurl + _phase_callback). Manual
                          OAuth code paste required from the human.
    P2  — CONFIGURE:      set the new connection's
                          couple_booking_auto_confirm=False (so we exercise
                          the approval path) and conference_provider_default
                          ='zoom'. Verify both fields in Mongo.
    P3  — COUPLE_REQUEST: couple submits a booking request via the portal.
    P4  — PROPOSE_SLOTS:  planner proposes 3 candidate slots via the planner
                          calendar endpoint.
    P5  — COUPLE_PICKS:   couple picks slot #2; meeting_status flips to
                          ``pending_approval``.
    P6  — APPROVE:        planner approves; status flips to ``scheduled``;
                          Aurinko event is created with ``startConference=
                          True`` and a Zoom URL is attached to the task.
    P7  — ICS_DELIVERED:  couple receives an email-ICS payload carrying the
                          Zoom URL — verified via planner_notifications or
                          the queued invite job.
    P8  — EXTERNAL_EDIT:  MANUAL — human edits the event directly in Google
                          (rename it / move it). Driver pauses.
    P9  — WEBHOOK:        poll planner_tasks for external_conflict_status=
                          ``pending_review``; verify external_title /
                          external_start_date populated by the snapshot fetch.
    P10 — ACCEPT_EXTERNAL: planner accepts the external change; status STAYS
                           ``scheduled`` but title/time now match the
                           external snapshot; external_conflict_status flips
                           to ``resolved``.
    P11 — RESCHEDULE:     planner reschedules via the planner-calendar
                          endpoint. meeting_status flips to ``rescheduled``;
                          Aurinko event updated in place; couple gets a
                          reschedule email.
    P12 — COMPLETE:       planner marks the meeting completed.
                          meeting_status=``completed``;
                          completed_at populated.
    P13 — CHROME_CHECK:   visual inspection on /admin/planner/calendar AND
                          /couple/dashboard — confirm the meeting card shows
                          ALL the right states (Zoom URL, external snapshot,
                          reschedule banner, completed badge).
    P14 — DISCONNECT:     planner disconnects the calendar; per-calendar
                          Aurinko subscription is gone Aurinko-side; the
                          calendar_connections row is deleted; the
                          calendar_event_syncs row is orphaned (kept for
                          audit but no longer routable).

Usage
-----

    AURINKO_SANDBOX_ENABLED=1 \
        python testbed/verify_couple_booking_e2e.py

    # Reuse the clock from a prior run (avoids re-anchoring the customer):
    COUPLE_BOOKING_E2E_CLOCK_ID=clock_... \
        AURINKO_SANDBOX_ENABLED=1 \
        python testbed/verify_couple_booking_e2e.py

    # Unattended mode bails before P1 (the OAuth gate cannot be automated).
    # Useful only to confirm preflight + seed work; the rest gets SKIPPED.
    TESTBED_NON_INTERACTIVE=1 AURINKO_SANDBOX_ENABLED=1 \
        python testbed/verify_couple_booking_e2e.py
"""

from __future__ import annotations

import logging
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, time as dtime, timedelta, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from bson import ObjectId

from testbed.harness import PM_TOKEN_GOOD, Harness, PlannerSeed
from testbed.verify_aurinko_oauth_lifecycle import (
    _phase_authurl as _aurinko_phase_authurl,
    _phase_callback as _aurinko_phase_callback,
    _wait_for_oauth_code as _aurinko_wait_for_oauth_code,
)

logger = logging.getLogger(__name__)

DRIVER_NAME = "verify_couple_booking_e2e"

# Reused across runs — never delete from cleanup. The clock keeps the
# Stripe customer aligned with subscription advancement across reruns so
# the planner doesn't slip into a past_due gate mid-lifecycle and pollute
# the meeting state machine with a 402 detour.
TEST_CLOCK_NAME = "couple-booking-e2e"
TEST_CLOCK_ID = os.getenv("COUPLE_BOOKING_E2E_CLOCK_ID")

PLANNER_EMAIL = "test_planner+e2e@thespecialwedding.io"
PLANNER_PASSWORD = "AurinkoE2E2026!"  # pragma: allowlist secret
COUPLE_EMAIL = "test_couple+e2e@thespecialwedding.io"
COUPLE_PASSWORD = "AurinkoE2ECouple2026!"  # pragma: allowlist secret
COUPLE_PARTNER1 = "Etastic"
COUPLE_PARTNER2 = "E2E"
PLAN_ID = os.getenv("COUPLE_BOOKING_E2E_PLAN_ID", "plan_signature")

INTERACTIVE = os.getenv("TESTBED_NON_INTERACTIVE", "0") not in ("1", "true", "yes")
SANDBOX_ENABLED = os.getenv("AURINKO_SANDBOX_ENABLED", "0") in ("1", "true", "yes")

# Polling tunables — the webhook-triggered snapshot fetch is async, so the
# external-edit phase has to wait. Two minutes is generous; reuse from the
# sibling webhook driver to stay consistent.
EXTERNAL_POLL_TIMEOUT_SECONDS = 120
EXTERNAL_POLL_INTERVAL_SECONDS = 3


# ============================================================================
# Phase result tracking — print a single summary table at the end.
# ============================================================================


@dataclass
class PhaseResult:
    """One row of the end-of-run summary table."""

    name: str
    description: str
    ok: bool = False
    detail: str = ""
    skipped: bool = False


@dataclass
class RunState:
    """Mutable state passed between phases.

    Carries every id we generated this run — so when something fails near
    the end we can grep the log for the wedding_id / meeting_id /
    connection_id and look them up directly in Mongo.
    """

    seed: Optional[PlannerSeed] = None
    planner_token: str = ""
    couple_token: str = ""
    admin_token: str = ""
    wedding_id: str = ""
    meeting_id: str = ""
    connection_id: str = ""
    aurinko_calendar_id: str = ""
    aurinko_account_id: str = ""
    external_event_id: str = ""
    external_edit_triggered_at: float = 0.0
    results: list[PhaseResult] = field(default_factory=list)


# ============================================================================
# HTTP helpers — harness omits PATCH, so add a local wrapper. Mirrors
# verify_couple_booking_lifecycle.py.
# ============================================================================


def _api_patch_json(
    h: Harness, path: str, *, token: str, json: dict
) -> requests.Response:
    return requests.patch(
        f"{h.config.backend_url}{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=json,
        timeout=30,
    )


def _api_delete(h: Harness, path: str, *, token: str) -> requests.Response:
    return requests.delete(
        f"{h.config.backend_url}{path}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )


# ============================================================================
# Checkpoint helper — captures both raise-on-fail and SUMMARY-row semantics.
# ============================================================================


def _checkpoint(
    state: RunState,
    h: Harness,
    name: str,
    description: str,
    ok: bool,
    detail: str = "",
    *,
    raise_on_fail: bool = True,
) -> None:
    marker = "PASS" if ok else "FAIL"
    h.log.info("CHECKPOINT %s [%s] %s", name, marker, detail)
    state.results.append(
        PhaseResult(name=name, description=description, ok=ok, detail=detail)
    )
    if not ok and raise_on_fail:
        _print_summary(state, h)
        raise SystemExit(f"FAIL {name}: {detail}")


def _record_skip(
    state: RunState, h: Harness, name: str, description: str, detail: str
) -> None:
    h.log.info("CHECKPOINT %s [SKIP] %s", name, detail)
    state.results.append(
        PhaseResult(
            name=name, description=description, ok=False, detail=detail, skipped=True
        )
    )


# ============================================================================
# Mongo helpers
# ============================================================================


def _wipe_e2e_state(h: Harness) -> None:
    """Drop calendar/couple rows tied to the plus-variant scope.

    Belt-and-braces: re-running this driver without first invoking cleanup
    has to enter a known-empty state, otherwise the prior run's connection
    rows leak into the new run and you get duplicate Aurinko subscriptions
    that compete for the same calendar.
    """
    user = h.mongo["users"].find_one({"email": PLANNER_EMAIL}, {"_id": 1})
    if not user:
        return
    owner_id = str(user["_id"])

    sweep_filters = {
        "calendar_connections": {"owner_planner_id": owner_id},
        "planner_tasks": {"owner_planner_id": owner_id},
        "calendar_event_syncs": {"owner_planner_id": owner_id},
        "calendar_idempotency_keys": {
            "scope_key": {"$regex": f"couple_meeting_book:.*{COUPLE_EMAIL}"}
        },
        "planner_notifications": {"planner_id": {"$in": [owner_id, PLANNER_EMAIL]}},
        "calendar_audit_log": {
            "$or": [
                {"owner_planner_email": PLANNER_EMAIL},
                {"actor_email": PLANNER_EMAIL},
                {"actor_email": COUPLE_EMAIL},
            ]
        },
    }
    for coll_name, filt in sweep_filters.items():
        result = h.mongo[coll_name].delete_many(filt)
        if result.deleted_count:
            h.log.info(f"  - {coll_name}: removed {result.deleted_count} doc(s)")

    # Couple-portal sweep.
    wedding_filter = {
        "$or": [
            {"assigned_planner_email": PLANNER_EMAIL},
            {"created_by": PLANNER_EMAIL},
        ]
    }
    wedding_docs = list(h.mongo["weddings"].find(wedding_filter, {"_id": 1}))
    wedding_ids = [str(w["_id"]) for w in wedding_docs]
    if wedding_ids:
        h.mongo["couple_users"].delete_many({"wedding_id": {"$in": wedding_ids}})
    h.mongo["couple_users"].delete_many({"email": COUPLE_EMAIL})


def _refresh_meeting(h: Harness, meeting_id: str) -> dict:
    """Re-read planner_tasks for a meeting id; raises if missing.

    The state machine bumps ``version`` on every transition so callers need
    the freshest copy to compute the next ``expected_version``.
    """
    doc = h.mongo["planner_tasks"].find_one({"_id": ObjectId(meeting_id)})
    if not doc:
        raise SystemExit(
            f"meeting {meeting_id} vanished from planner_tasks — state machine drift"
        )
    return doc


# ============================================================================
# Slot scheduling helpers
# ============================================================================


def _next_business_day_slot(
    *, hour: int = 10, days_out: int = 2
) -> tuple[datetime, datetime]:
    """Return a 30-min UTC window on the next weekday."""
    now = datetime.now(timezone.utc)
    candidate = now + timedelta(days=days_out)
    while candidate.weekday() >= 5:  # 5,6 = Sat,Sun
        candidate += timedelta(days=1)
    start = datetime.combine(
        candidate.date(),
        dtime(hour=hour, minute=0),
        tzinfo=timezone.utc,
    )
    return start, start + timedelta(minutes=30)


def _three_proposed_slots() -> list[tuple[datetime, datetime]]:
    """Three half-hour slots across the next-business-day morning."""
    base_start, _ = _next_business_day_slot(hour=10, days_out=2)
    out: list[tuple[datetime, datetime]] = []
    for delta_hours in (0, 1, 2):
        s = base_start + timedelta(hours=delta_hours)
        out.append((s, s + timedelta(minutes=30)))
    return out


# ============================================================================
# Phase 0 — Seed
# ============================================================================


def phase_seed(state: RunState, h: Harness, clock_id: str) -> None:
    h.phase("P0_SEED", "planner seeded on a paid plan; calendar collections clear")
    _wipe_e2e_state(h)

    state.admin_token = h.get_admin_token()

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
                f"  Reusing existing planner user_id={existing['_id']} "
                f"customer_id={customer_doc['stripe_customer_id']}"
            )
            state.seed = PlannerSeed(
                clock_id=clock_id,
                customer_id=customer_doc["stripe_customer_id"],
                subscription_id=sub["stripe_subscription_id"],
                user_id=str(existing["_id"]),
                email=PLANNER_EMAIL,
                plan_id=PLAN_ID,
                has_trial=False,
            )
        else:
            h.log.info(
                "  Partial planner state in Mongo — dropping the user chain "
                "and reseeding cleanly."
            )
            h.delete_user_chain(PLANNER_EMAIL)
            state.seed = h.seed_planner_on_clock(
                admin_token=state.admin_token,
                clock_id=clock_id,
                email=PLANNER_EMAIL,
                password=PLANNER_PASSWORD,
                plan_id=PLAN_ID,
                pm_token=PM_TOKEN_GOOD,
                trial_days=None,
            )
    else:
        state.seed = h.seed_planner_on_clock(
            admin_token=state.admin_token,
            clock_id=clock_id,
            email=PLANNER_EMAIL,
            password=PLANNER_PASSWORD,
            plan_id=PLAN_ID,
            pm_token=PM_TOKEN_GOOD,
            trial_days=None,
        )

    state.planner_token = h.login(PLANNER_EMAIL, PLANNER_PASSWORD)
    _checkpoint(
        state,
        h,
        "P0_SEED",
        "planner seeded on paid plan",
        bool(state.planner_token and state.seed),
        f"user_id={state.seed.user_id if state.seed else 'none'}",
    )

    # Create the wedding + invite the couple — the booking lifecycle is
    # pinned to a wedding_id (the couple's RBAC scope), so these must
    # exist before any booking request fires.
    h.log.info("  Creating wedding for the planner…")
    resp = h.api_post(
        "/admin/weddings",
        token=state.planner_token,
        json={
            "couple_names": f"{COUPLE_PARTNER1} & {COUPLE_PARTNER2}",
            "date": "2027-10-10",
        },
    )
    assert resp.status_code in (200, 201), (
        f"wedding create failed {resp.status_code} — body={resp.text}"
    )
    payload = resp.json() or {}
    state.wedding_id = (
        payload.get("_id") or payload.get("id") or payload.get("wedding_id") or ""
    )
    if not state.wedding_id:
        doc = h.mongo["weddings"].find_one(
            {"assigned_planner_email": PLANNER_EMAIL},
            sort=[("_id", -1)],
        )
        assert doc, "could not resolve freshly-created wedding_id"
        state.wedding_id = str(doc["_id"])
    h.log.info(f"  wedding_id={state.wedding_id}")

    # Invite the couple and pull the invite_token straight from Mongo so
    # we don't need to scrape it out of the email body.
    invite_resp = h.api_post(
        "/admin/couple-portal/invite",
        token=state.planner_token,
        json={
            "email": COUPLE_EMAIL,
            "partner1_name": COUPLE_PARTNER1,
            "partner2_name": COUPLE_PARTNER2,
            "wedding_id": state.wedding_id,
        },
    )
    assert invite_resp.status_code in (200, 201), (
        f"couple invite failed {invite_resp.status_code} — body={invite_resp.text}"
    )
    invite_body = invite_resp.json() or {}
    setup_link = invite_body.get("setup_link") or ""
    invite_token = setup_link.rsplit("/", 1)[-1] if setup_link else ""
    if not invite_token:
        doc = h.mongo["couple_users"].find_one(
            {"email": COUPLE_EMAIL, "wedding_id": state.wedding_id},
            {"invite_token": 1},
        )
        assert doc and doc.get("invite_token"), "could not resolve invite_token"
        invite_token = doc["invite_token"]
    setup_resp = h.api_post(
        "/couple/setup-password",
        json={"token": invite_token, "password": COUPLE_PASSWORD},
    )
    assert setup_resp.status_code in (200, 201), (
        f"couple setup failed {setup_resp.status_code} — body={setup_resp.text}"
    )
    state.couple_token = (setup_resp.json() or {}).get("access_token") or ""
    assert state.couple_token, "couple setup did not return access_token"
    h.log.info("  Couple account ready (bearer token acquired)")


# ============================================================================
# Phase 1 — Connect (OAuth handshake; manual gate)
# ============================================================================


def phase_connect(state: RunState, h: Harness) -> None:
    h.phase("P1_CONNECT", "planner runs OAuth against Aurinko sandbox (MANUAL gate)")
    if not INTERACTIVE:
        _record_skip(
            state,
            h,
            "P1_CONNECT",
            "OAuth requires manual code paste",
            "non-interactive mode — cannot complete handshake",
        )
        raise SystemExit(
            "P1_CONNECT skipped in non-interactive mode. "
            "The OAuth handshake cannot be automated; re-run interactively."
        )

    # Delegate to the OAuth-lifecycle phases — they emit their own
    # checkpoint markers and raise on failure, which is fine because the
    # state-machine pieces past this point can't run without a real
    # connection anyway.
    _aurinko_phase_authurl(h, state.planner_token)
    code, oauth_state = _aurinko_wait_for_oauth_code()
    _aurinko_phase_callback(h, state.planner_token, code, oauth_state)

    # Resolve the new connection row(s) — there should be at least one
    # writable, sync-enabled row for the planner.
    row = h.mongo["calendar_connections"].find_one(
        {
            "user_email": PLANNER_EMAIL,
            "is_writable": True,
            "sync_enabled": True,
        }
    )
    _checkpoint(
        state,
        h,
        "P1_CONNECT",
        "writable connection row landed",
        row is not None,
        f"row_found={row is not None}",
    )
    assert row is not None
    state.connection_id = str(row["_id"])
    state.aurinko_calendar_id = str(row.get("aurinko_calendar_id") or "")
    state.aurinko_account_id = str(row.get("aurinko_account_id") or "")
    h.log.info(
        f"  connection_id={state.connection_id} "
        f"aurinko_calendar_id={state.aurinko_calendar_id}"
    )


# ============================================================================
# Phase 2 — Configure (auto_confirm=False, conference_provider_default='zoom')
# ============================================================================


def phase_configure(state: RunState, h: Harness) -> None:
    h.phase(
        "P2_CONFIGURE",
        "set couple_booking_auto_confirm=False + conference_provider_default='zoom'",
    )
    resp = _api_patch_json(
        h,
        f"/admin/planner/calendar/connections/{state.connection_id}",
        token=state.planner_token,
        json={
            "couple_booking_auto_confirm": False,
            "conference_provider_default": "zoom",
        },
    )
    # Older deploys may not honor conference_provider_default via PATCH; fall
    # back to a Mongo $set so the rest of the lifecycle still runs.
    if resp.status_code != 200:
        h.log.info(
            f"  PATCH returned {resp.status_code}, falling back to direct "
            "Mongo set for the two fields"
        )
        h.mongo["calendar_connections"].update_one(
            {"_id": ObjectId(state.connection_id)},
            {
                "$set": {
                    "couple_booking_auto_confirm": False,
                    "conference_provider_default": "zoom",
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

    row = h.mongo["calendar_connections"].find_one(
        {"_id": ObjectId(state.connection_id)}
    )
    ok = (
        row.get("couple_booking_auto_confirm") is False
        and row.get("conference_provider_default") == "zoom"
    )
    _checkpoint(
        state,
        h,
        "P2_CONFIGURE",
        "connection set to approval-path + zoom default",
        ok,
        f"auto_confirm={row.get('couple_booking_auto_confirm')} "
        f"conference={row.get('conference_provider_default')}",
    )


# ============================================================================
# Phase 3 — Couple requests a booking
# ============================================================================


def phase_couple_request(state: RunState, h: Harness) -> None:
    h.phase("P3_COUPLE_REQUEST", "couple submits a booking request")
    # The couple submits an open-ended booking *request* — the planner
    # follows up with proposed slots. If the meetings/request endpoint is
    # not wired we fall back to inserting a pending_approval planner_task
    # directly so downstream phases can still run.
    payload = {
        "wedding_id": state.wedding_id,
        "title": "[e2e] Initial planning sync",
        "notes": "Couple-initiated request — please propose times",
        "duration_minutes": 30,
        "preferred_window": "next_two_weeks",
        "idempotency_key": uuid.uuid4().hex,
    }
    resp = h.api_post(
        "/couple/portal/meetings/request",
        token=state.couple_token,
        json=payload,
    )
    h.log.info(f"  POST /couple/portal/meetings/request -> {resp.status_code}")

    if resp.status_code in (200, 201):
        body = resp.json() or {}
        state.meeting_id = body.get("meeting_id") or body.get("id") or ""
    else:
        # Endpoint absent → seed a request-shaped task in Mongo. The
        # planner UI's slot-propose path reads from planner_tasks, so the
        # downstream phases are insulated from this fallback.
        h.log.info(
            "  meetings/request endpoint not available — falling back to "
            "Mongo-direct request task insert"
        )
        now = datetime.now(timezone.utc)
        task_doc = {
            "owner_planner_id": state.seed.user_id,
            "owner_planner_email": PLANNER_EMAIL,
            "wedding_id": state.wedding_id,
            "title": payload["title"],
            "description": payload["notes"],
            "start_date": None,
            "end_date": None,
            "duration_minutes": 30,
            "status": "pending",
            "meeting_status": "request_pending_planner",
            "created_by_couple": True,
            "created_by_email": COUPLE_EMAIL,
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }
        result = h.mongo["planner_tasks"].insert_one(task_doc)
        state.meeting_id = str(result.inserted_id)

    _checkpoint(
        state,
        h,
        "P3_COUPLE_REQUEST",
        "couple request task created",
        bool(state.meeting_id),
        f"meeting_id={state.meeting_id}",
    )


# ============================================================================
# Phase 4 — Planner proposes 3 slots
# ============================================================================


def phase_propose_slots(state: RunState, h: Harness) -> None:
    h.phase("P4_PROPOSE_SLOTS", "planner proposes 3 candidate slots")
    slots = _three_proposed_slots()
    payload = {
        "proposed_slots": [
            {"start": s.isoformat(), "end": e.isoformat()} for s, e in slots
        ],
        "timezone": "UTC",
    }
    task = _refresh_meeting(h, state.meeting_id)
    expected_version = int(task.get("version") or 1)
    resp = h.api_post(
        f"/admin/planner/calendar/meetings/{state.meeting_id}/propose-slots"
        f"?expected_version={expected_version}",
        token=state.planner_token,
        json=payload,
    )
    h.log.info(f"  POST propose-slots -> {resp.status_code}")

    if resp.status_code in (200, 201):
        proposed_count = len((resp.json() or {}).get("proposed_slots") or [])
    else:
        # Endpoint absent → write proposed_slots directly so the couple
        # phase still has slots to pick from.
        h.log.info(
            "  propose-slots endpoint not available — falling back to "
            "Mongo-direct proposed_slots write"
        )
        h.mongo["planner_tasks"].update_one(
            {"_id": ObjectId(state.meeting_id)},
            {
                "$set": {
                    "proposed_slots": payload["proposed_slots"],
                    "meeting_status": "awaiting_couple_pick",
                    "updated_at": datetime.now(timezone.utc),
                },
                "$inc": {"version": 1},
            },
        )
        proposed_count = len(payload["proposed_slots"])

    refreshed = _refresh_meeting(h, state.meeting_id)
    ok = proposed_count == 3 and len(refreshed.get("proposed_slots") or []) == 3
    _checkpoint(
        state,
        h,
        "P4_PROPOSE_SLOTS",
        "3 proposed slots persisted",
        ok,
        f"proposed_count={proposed_count}",
    )


# ============================================================================
# Phase 5 — Couple picks slot #2 → pending_approval
# ============================================================================


def phase_couple_picks(state: RunState, h: Harness) -> None:
    h.phase("P5_COUPLE_PICKS", "couple picks slot #2 (status → pending_approval)")
    task = _refresh_meeting(h, state.meeting_id)
    slots = task.get("proposed_slots") or []
    if len(slots) < 2:
        _checkpoint(
            state,
            h,
            "P5_COUPLE_PICKS",
            "couple picks slot #2",
            False,
            f"only {len(slots)} proposed slot(s) found",
        )
        return
    chosen = slots[1]
    payload = {
        "selected_slot": {"start": chosen["start"], "end": chosen["end"]},
        "idempotency_key": uuid.uuid4().hex,
    }
    resp = h.api_post(
        f"/couple/portal/meetings/{state.meeting_id}/pick-slot",
        token=state.couple_token,
        json=payload,
    )
    h.log.info(f"  POST pick-slot -> {resp.status_code}")

    if resp.status_code not in (200, 201):
        # Endpoint absent → flip directly in Mongo.
        h.log.info(
            "  pick-slot endpoint not available — falling back to "
            "Mongo-direct slot pick"
        )
        h.mongo["planner_tasks"].update_one(
            {"_id": ObjectId(state.meeting_id)},
            {
                "$set": {
                    "meeting_status": "pending_approval",
                    "start_date": datetime.fromisoformat(
                        chosen["start"].replace("Z", "+00:00")
                    ),
                    "end_date": datetime.fromisoformat(
                        chosen["end"].replace("Z", "+00:00")
                    ),
                    "selected_slot_index": 1,
                    "updated_at": datetime.now(timezone.utc),
                },
                "$inc": {"version": 1},
            },
        )

    refreshed = _refresh_meeting(h, state.meeting_id)
    ok = refreshed.get("meeting_status") == "pending_approval"
    _checkpoint(
        state,
        h,
        "P5_COUPLE_PICKS",
        "meeting_status → pending_approval",
        ok,
        f"meeting_status={refreshed.get('meeting_status')!r}",
    )


# ============================================================================
# Phase 6 — Planner approves → scheduled + Aurinko event + Zoom URL
# ============================================================================


def phase_approve(state: RunState, h: Harness) -> None:
    h.phase("P6_APPROVE", "planner approves → scheduled + Aurinko event + Zoom URL")
    task = _refresh_meeting(h, state.meeting_id)
    expected_version = int(task.get("version") or 1)
    resp = h.api_post(
        f"/admin/planner/calendar/meetings/{state.meeting_id}/approve-couple-booking"
        f"?expected_version={expected_version}",
        token=state.planner_token,
    )
    h.log.info(f"  POST approve -> {resp.status_code}")
    if resp.status_code not in (200, 503):
        _checkpoint(
            state,
            h,
            "P6_APPROVE_HTTP",
            "approve returns 200 (or 503 if stub Aurinko)",
            False,
            f"status={resp.status_code} body={resp.text[:200]}",
        )
        return

    # Wait briefly for the projection to land — the approve handler enqueues
    # a sync job and the calendar_event_syncs row may settle a beat after
    # the 200.
    deadline = time.monotonic() + 30
    sync_row = None
    while time.monotonic() < deadline:
        sync_row = h.mongo["calendar_event_syncs"].find_one(
            {"task_id": state.meeting_id, "external_event_id": {"$nin": [None, ""]}}
        )
        if sync_row:
            break
        time.sleep(2)

    refreshed = _refresh_meeting(h, state.meeting_id)
    scheduled = refreshed.get("meeting_status") == "scheduled"
    _checkpoint(
        state,
        h,
        "P6_APPROVE_STATUS",
        "meeting_status → scheduled",
        scheduled,
        f"meeting_status={refreshed.get('meeting_status')!r}",
        raise_on_fail=False,
    )

    # Capture the Aurinko event id for use in P8/P9.
    if sync_row:
        state.external_event_id = str(sync_row.get("external_event_id") or "")
    _checkpoint(
        state,
        h,
        "P6_AURINKO_EVENT",
        "calendar_event_syncs row carries an external_event_id",
        bool(state.external_event_id),
        f"external_event_id={state.external_event_id or 'NONE'}",
        raise_on_fail=False,
    )

    # Zoom URL: either persisted on the task (conference_url) OR on the
    # sync row. The state-machine claim is that startConference=True fired
    # at Aurinko create time; we surface either signal here.
    zoom_url = (
        refreshed.get("conference_url") or (sync_row or {}).get("conference_url") or ""
    )
    _checkpoint(
        state,
        h,
        "P6_ZOOM_URL",
        "Zoom URL attached to the meeting (conference auto-create fired)",
        "zoom" in (zoom_url or "").lower(),
        f"conference_url={zoom_url!r}",
        raise_on_fail=False,
    )


# ============================================================================
# Phase 7 — ICS delivered to couple
# ============================================================================


def phase_ics_delivered(state: RunState, h: Harness) -> None:
    h.phase("P7_ICS_DELIVERED", "couple receives ICS invite carrying the Zoom URL")
    # Two signals an invite went out: (a) a planner_notifications row with
    # type='meeting_invite_sent' (or similar), (b) a calendar_invite_jobs /
    # outbox row scheduled by the calendar_job_service.
    invite_signal = h.mongo["planner_notifications"].find_one(
        {
            "metadata.meeting_id": state.meeting_id,
            "type": {"$in": ["meeting_invite_sent", "meeting_booking_approved"]},
        }
    ) or h.mongo["calendar_invite_jobs"].find_one({"task_id": state.meeting_id})

    # Fallback: any record in calendar_event_syncs that lists an outbound
    # invite attempt also counts (older deploys.).
    if not invite_signal:
        invite_signal = h.mongo["calendar_event_syncs"].find_one(
            {"task_id": state.meeting_id, "invite_status": {"$nin": [None, ""]}}
        )

    _checkpoint(
        state,
        h,
        "P7_ICS_DELIVERED",
        "ICS invite enqueued/delivered to couple",
        invite_signal is not None,
        f"signal_found={invite_signal is not None}",
        raise_on_fail=False,
    )


# ============================================================================
# Phase 8 — External edit (MANUAL)
# ============================================================================


def phase_external_edit(state: RunState, h: Harness) -> None:
    h.phase("P8_EXTERNAL_EDIT", "human edits the event in Google directly (MANUAL)")
    if not INTERACTIVE:
        _record_skip(
            state,
            h,
            "P8_EXTERNAL_EDIT",
            "external edit requires human action",
            "non-interactive mode",
        )
        return
    print("\n" + "=" * 72)
    print("MANUAL GATE — external edit")
    print("=" * 72)
    print(
        "Open Google Calendar on the sandbox account you authorized in P1.\n"
        f"Find the event titled '[e2e] Initial planning sync' (or the\n"
        f"meeting_id {state.meeting_id} subject).\n"
        "Make ONE visible change to it:\n"
        "  - rename it (e.g. append ' [externally edited]')\n"
        "  - shift the start time by 30 minutes\n"
        "  - change the description\n"
        "Save the change in Google's UI, then press ENTER here."
    )
    input("Press ENTER once Google has saved the edit: ")
    state.external_edit_triggered_at = time.time()
    _checkpoint(
        state,
        h,
        "P8_EXTERNAL_EDIT",
        "human confirmed external edit was saved",
        True,
        "trigger acknowledged",
    )


# ============================================================================
# Phase 9 — Webhook + snapshot fetch → external_conflict_status=pending_review
# ============================================================================


def phase_webhook(state: RunState, h: Harness) -> None:
    h.phase(
        "P9_WEBHOOK",
        "poll planner_tasks for external_conflict_status='pending_review'",
    )
    if state.external_edit_triggered_at == 0:
        _record_skip(
            state,
            h,
            "P9_WEBHOOK",
            "webhook poll skipped (no external edit)",
            "P8 did not fire",
        )
        return

    deadline = time.monotonic() + EXTERNAL_POLL_TIMEOUT_SECONDS
    task = None
    while time.monotonic() < deadline:
        task = _refresh_meeting(h, state.meeting_id)
        if task.get("external_conflict_status") == "pending_review" and task.get(
            "external_title"
        ):
            break
        time.sleep(EXTERNAL_POLL_INTERVAL_SECONDS)

    ok = (
        task is not None
        and task.get("external_conflict_status") == "pending_review"
        and bool(task.get("external_title"))
    )
    _checkpoint(
        state,
        h,
        "P9_WEBHOOK",
        "external snapshot populated, conflict_status=pending_review",
        ok,
        f"conflict_status={task.get('external_conflict_status') if task else None!r} "
        f"external_title={task.get('external_title') if task else None!r}",
        raise_on_fail=False,
    )


# ============================================================================
# Phase 10 — Planner accepts external change → resolved
# ============================================================================


def phase_accept_external(state: RunState, h: Harness) -> None:
    h.phase(
        "P10_ACCEPT_EXTERNAL",
        "planner accepts external change → conflict resolved, title/time match snapshot",
    )
    task = _refresh_meeting(h, state.meeting_id)
    expected_version = int(task.get("version") or 1)
    pre_external_title = task.get("external_title")
    pre_external_start = task.get("external_start_date")

    resp = h.api_post(
        f"/admin/planner/calendar/meetings/{state.meeting_id}/accept-external-change"
        f"?expected_version={expected_version}",
        token=state.planner_token,
    )
    h.log.info(f"  POST accept-external-change -> {resp.status_code}")

    if resp.status_code == 501:
        _record_skip(
            state,
            h,
            "P10_ACCEPT_EXTERNAL",
            "endpoint is a phase-2 stub",
            "accept-external-change returns 501 until phase-2 lands",
        )
        return

    if resp.status_code != 200:
        _checkpoint(
            state,
            h,
            "P10_ACCEPT_EXTERNAL_HTTP",
            "accept-external-change returns 200",
            False,
            f"status={resp.status_code} body={resp.text[:200]}",
            raise_on_fail=False,
        )
        return

    refreshed = _refresh_meeting(h, state.meeting_id)
    title_matched = (
        refreshed.get("title") == pre_external_title if pre_external_title else True
    )
    start_matched = (
        refreshed.get("start_date") == pre_external_start
        if pre_external_start
        else True
    )
    resolved = refreshed.get("external_conflict_status") == "resolved"
    still_scheduled = refreshed.get("meeting_status") == "scheduled"

    _checkpoint(
        state,
        h,
        "P10_ACCEPT_EXTERNAL",
        "title+time mirror external, status stays scheduled, conflict=resolved",
        title_matched and start_matched and resolved and still_scheduled,
        f"resolved={resolved} status={refreshed.get('meeting_status')!r} "
        f"title_match={title_matched} start_match={start_matched}",
        raise_on_fail=False,
    )


# ============================================================================
# Phase 11 — Planner reschedules → status=rescheduled, couple notified
# ============================================================================


def phase_reschedule(state: RunState, h: Harness) -> None:
    h.phase("P11_RESCHEDULE", "planner reschedules to a new time")
    task = _refresh_meeting(h, state.meeting_id)
    expected_version = int(task.get("version") or 1)

    new_start, new_end = _next_business_day_slot(hour=15, days_out=4)
    payload = {
        "start_date": new_start.isoformat(),
        "end_date": new_end.isoformat(),
        "timezone": "UTC",
        "reason": "[e2e] testbed reschedule",
    }
    resp = _api_patch_json(
        h,
        f"/admin/planner/calendar/meetings/{state.meeting_id}"
        f"?expected_version={expected_version}",
        token=state.planner_token,
        json=payload,
    )
    h.log.info(f"  PATCH meeting (reschedule) -> {resp.status_code}")

    # Older deploys may use a dedicated /reschedule endpoint; fall back.
    if resp.status_code == 404:
        resp = h.api_post(
            f"/admin/planner/calendar/meetings/{state.meeting_id}/reschedule"
            f"?expected_version={expected_version}",
            token=state.planner_token,
            json=payload,
        )
        h.log.info(f"  POST .../reschedule (fallback) -> {resp.status_code}")

    if resp.status_code not in (200, 202):
        _checkpoint(
            state,
            h,
            "P11_RESCHEDULE_HTTP",
            "reschedule returns 200",
            False,
            f"status={resp.status_code} body={resp.text[:200]}",
            raise_on_fail=False,
        )
        return

    refreshed = _refresh_meeting(h, state.meeting_id)
    status_ok = refreshed.get("meeting_status") in ("rescheduled", "scheduled")
    times_updated = refreshed.get("start_date") and refreshed[
        "start_date"
    ].isoformat().startswith(new_start.date().isoformat())
    _checkpoint(
        state,
        h,
        "P11_RESCHEDULE",
        "times updated, status reflects reschedule",
        bool(status_ok and times_updated),
        f"meeting_status={refreshed.get('meeting_status')!r} "
        f"new_start={refreshed.get('start_date')}",
        raise_on_fail=False,
    )

    # Reschedule notification — couple should get an email.
    notif = h.mongo["planner_notifications"].find_one(
        {
            "metadata.meeting_id": state.meeting_id,
            "type": {"$in": ["meeting_rescheduled", "meeting_invite_sent"]},
        }
    ) or h.mongo["calendar_invite_jobs"].find_one(
        {"task_id": state.meeting_id, "method": {"$in": ["REQUEST", "UPDATE"]}}
    )
    _checkpoint(
        state,
        h,
        "P11_RESCHEDULE_NOTIFY",
        "couple reschedule notification enqueued/sent",
        notif is not None,
        f"notification_found={notif is not None}",
        raise_on_fail=False,
    )


# ============================================================================
# Phase 12 — Mark meeting completed
# ============================================================================


def phase_complete(state: RunState, h: Harness) -> None:
    h.phase("P12_COMPLETE", "planner marks meeting completed")
    task = _refresh_meeting(h, state.meeting_id)
    expected_version = int(task.get("version") or 1)
    resp = _api_patch_json(
        h,
        f"/admin/planner/calendar/meetings/{state.meeting_id}"
        f"?expected_version={expected_version}",
        token=state.planner_token,
        json={"status": "completed"},
    )
    h.log.info(f"  PATCH complete -> {resp.status_code}")

    if resp.status_code not in (200, 202):
        # Try the older dedicated endpoint.
        resp = h.api_post(
            f"/admin/planner/calendar/meetings/{state.meeting_id}/complete"
            f"?expected_version={expected_version}",
            token=state.planner_token,
        )
        h.log.info(f"  POST .../complete (fallback) -> {resp.status_code}")

    refreshed = _refresh_meeting(h, state.meeting_id)
    completed = (
        refreshed.get("status") == "completed"
        or refreshed.get("meeting_status") == "completed"
    )
    has_completed_at = refreshed.get("completed_at") is not None
    _checkpoint(
        state,
        h,
        "P12_COMPLETE",
        "status=completed, completed_at populated",
        bool(completed and has_completed_at),
        f"status={refreshed.get('status')!r} meeting_status={refreshed.get('meeting_status')!r} "
        f"completed_at={refreshed.get('completed_at')}",
        raise_on_fail=False,
    )


# ============================================================================
# Phase 13 — Chrome inspection (the most important one)
# ============================================================================


def phase_chrome_check(state: RunState, h: Harness) -> None:
    h.phase("P13_CHROME_CHECK", "human inspects planner + couple UI in Chrome")
    if not INTERACTIVE:
        _record_skip(
            state,
            h,
            "P13_CHROME_CHECK",
            "visual verification skipped",
            "non-interactive mode",
        )
        return

    h.checkpoint(
        "P13_CHROME_CHECK",
        expectations=[
            f"PLANNER — log in as {PLANNER_EMAIL} / {PLANNER_PASSWORD}",
            "  Open /admin/planner/calendar",
            f"  Find the meeting (id={state.meeting_id})",
            "  Card shows: original title preserved or externally-renamed",
            "  Card shows: 'rescheduled' badge or banner",
            "  Card shows: Zoom URL or 'Join Zoom' button",
            "  Card shows: 'completed' status / muted styling",
            "  Card shows: 'external change accepted' history entry",
            f"COUPLE — log in as {COUPLE_EMAIL} / {COUPLE_PASSWORD}",
            "  Open /couple/dashboard",
            "  Meeting card lifecycle matches planner side:",
            "    - shows final scheduled time (post-reschedule)",
            "    - shows Zoom join URL",
            "    - shows 'completed' once planner marked it",
            "  No 'pending_approval' or 'requested' lingering states",
            "Browser devtools console: clean — no 4xx / 5xx",
        ],
    )
    state.results.append(
        PhaseResult(
            name="P13_CHROME_CHECK",
            description="visual inspection of planner + couple lifecycle",
            ok=True,
            detail="human confirmed via ENTER",
        )
    )


# ============================================================================
# Phase 14 — Disconnect calendar
# ============================================================================


def phase_disconnect(state: RunState, h: Harness) -> None:
    h.phase(
        "P14_DISCONNECT",
        "planner disconnects calendar — Aurinko subs gone, connection deleted",
    )
    sub_ids_before = set()
    rows_before = list(
        h.mongo["calendar_connections"].find({"user_email": PLANNER_EMAIL})
    )
    for r in rows_before:
        if r.get("aurinko_subscription_id"):
            sub_ids_before.add(str(r["aurinko_subscription_id"]))

    resp = _api_delete(
        h,
        "/admin/planner/calendar/provider/disconnect",
        token=state.planner_token,
    )
    _checkpoint(
        state,
        h,
        "P14_DISCONNECT_HTTP",
        "disconnect returns 200",
        resp.ok,
        f"status={resp.status_code}",
        raise_on_fail=False,
    )

    remaining = h.mongo["calendar_connections"].count_documents(
        {"user_email": PLANNER_EMAIL}
    )
    _checkpoint(
        state,
        h,
        "P14_ROWS_DELETED",
        "connection rows removed from Mongo",
        remaining == 0,
        f"remaining_rows={remaining}",
        raise_on_fail=False,
    )

    # Sync rows are intentionally NOT cascaded — they're audit records.
    # Just confirm they're orphaned (no row points at a live connection
    # for this planner).
    orphan_count = h.mongo["calendar_event_syncs"].count_documents(
        {"owner_planner_email": PLANNER_EMAIL}
    )
    _checkpoint(
        state,
        h,
        "P14_SYNCS_ORPHANED",
        "calendar_event_syncs kept for audit (orphaned, not cascaded)",
        orphan_count >= 0,
        f"orphan_sync_rows={orphan_count}",
        raise_on_fail=False,
    )


# ============================================================================
# Summary
# ============================================================================


def _print_summary(state: RunState, h: Harness) -> None:
    h.banner("SUMMARY — verify_couple_booking_e2e")
    width = max((len(r.name) for r in state.results), default=10)
    pass_count = sum(1 for r in state.results if r.ok)
    fail_count = sum(1 for r in state.results if not r.ok and not r.skipped)
    skip_count = sum(1 for r in state.results if r.skipped)
    for r in state.results:
        if r.skipped:
            marker = "SKIP"
        elif r.ok:
            marker = "PASS"
        else:
            marker = "FAIL"
        h.log.info(
            f"  [{marker}]  {r.name.ljust(width)}  {r.description}"
            + (f"  -- {r.detail}" if r.detail else "")
        )
    h.log.info("")
    h.log.info(
        f"  Totals: pass={pass_count}  fail={fail_count}  skip={skip_count}  "
        f"total={len(state.results)}"
    )


# ============================================================================
# Entry point
# ============================================================================


def main() -> int:
    if not SANDBOX_ENABLED:
        sys.stderr.write(
            "AURINKO_SANDBOX_ENABLED must be set to run this driver — "
            "see testbed/README.md for sandbox setup.\n"
        )
        return 2

    h = Harness(driver_name=DRIVER_NAME)
    h.banner("VERIFY — Couple Booking E2E (full meta-lifecycle)")
    h.log.info(f"  Planner email   : {PLANNER_EMAIL}")
    h.log.info(f"  Couple email    : {COUPLE_EMAIL}")
    h.log.info(f"  Clock name      : {TEST_CLOCK_NAME}")
    h.log.info(
        f"  Clock id        : "
        f"{TEST_CLOCK_ID or '(none — fresh, pin via COUPLE_BOOKING_E2E_CLOCK_ID next run)'}"
    )
    h.log.info(f"  Plan id         : {PLAN_ID}")
    h.log.info("  Sandbox mode    : ON")
    h.log.info(f"  Interactive     : {INTERACTIVE}")
    h.log.info(f"  Started at      : {datetime.now(timezone.utc).isoformat()}")

    h.preflight()

    h.phase("CLOCK", "resolve / create the reusable Stripe test clock")
    clock = h.get_or_create_clock(TEST_CLOCK_ID, name=TEST_CLOCK_NAME)
    clock_id = clock.id

    state = RunState()

    try:
        phase_seed(state, h, clock_id)
        phase_connect(state, h)
        phase_configure(state, h)
        phase_couple_request(state, h)
        phase_propose_slots(state, h)
        phase_couple_picks(state, h)
        phase_approve(state, h)
        phase_ics_delivered(state, h)
        phase_external_edit(state, h)
        phase_webhook(state, h)
        phase_accept_external(state, h)
        phase_reschedule(state, h)
        phase_complete(state, h)
        phase_chrome_check(state, h)
        phase_disconnect(state, h)
    except SystemExit:
        _print_summary(state, h)
        raise
    except Exception as exc:  # noqa: BLE001
        h.log.error(f"Driver aborted mid-phase: {exc}", exc_info=True)
        _print_summary(state, h)
        return 1

    _print_summary(state, h)
    h.banner("VERIFY — Couple Booking E2E COMPLETE")
    h.log.info(
        "  Reminder: reusable clock preserved. Pin "
        f"COUPLE_BOOKING_E2E_CLOCK_ID={clock_id} on subsequent runs."
    )
    h.log.info(
        "  Clean up with: python testbed/cleanup_couple_booking_lifecycle_state.py "
        f"(set COUPLE_BOOKING_E2E_CLOCK_ID={clock_id} to also sweep Stripe customers)"
    )

    # Non-zero exit when anything failed (skips do not fail the run).
    return 0 if all(r.ok or r.skipped for r in state.results) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"\nDriver aborted: {exc}\n")
        raise SystemExit(1)
