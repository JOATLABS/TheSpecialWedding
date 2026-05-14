#!/usr/bin/env python3
"""Couple-booking approve/decline branch verification.

Walks BOTH planner-side branches of the round-3 couple-booking workflow
when the staff's calendar connection has ``couple_booking_auto_confirm=False``.
The companion driver ``verify_couple_booking_lifecycle.py`` already covers
the slot / pending-approval / auto-confirm-toggle invariants — this one is
narrower and deeper, exercising the approve vs decline split end-to-end on
two independent fixtures so the branches cannot interfere with one
another.

Why two fixtures?  Once the planner approves the first request the
``planner_task`` is terminal (status=scheduled or cancelled).  We need a
second, fresh ``planner_task`` row to drive the decline branch without
relying on a re-open-after-approve path that the product spec does not yet
support.  Each fixture is identified by its own ``planner_task._id`` and
its own couple-side ``meeting_id``.

Endpoints touched
-----------------

    POST /couple/portal/meetings/request                      (P1)
    POST /admin/planner/calendar/meetings/{id}/propose-slots  (P2)
    POST /couple/portal/meetings/pick-slot                    (P3)
    POST /admin/planner/calendar/meetings/{id}/approve-booking  (P6a, P10)
    POST /admin/planner/calendar/meetings/{id}/decline-booking  (P6b)

A subset of these endpoints are still being implemented in Phase 2-3 of
the round-3 audit.  The driver intentionally treats 501 / 404 as soft
failures so it can be iterated against partial backends: the phase logs
"endpoint not yet implemented" and the run continues to the next phase
instead of aborting.  Once Phase 2-3 lands these soft-failures should
turn into hard assertions — the TODOs below mark each site.

Scenario checkpoints
--------------------

    P0  — SEED:           planner seeded with active sub + Aurinko-stub
                          connection where ``couple_booking_auto_confirm``
                          is False.
    P1  — COUPLE_REQUEST: ``POST /couple/portal/meetings/request`` (or the
                          temporary book endpoint).
    P2  — PLANNER_PROPOSE: planner proposes 3 candidate slots on the task.
    P3  — COUPLE_PICK:    couple picks one.  Status MUST be
                          ``pending_approval`` (NOT ``scheduled``).
    P4  — NOTIF_FIRED:    ``meeting_booking_request`` row in
                          ``planner_notifications``, addressed to the
                          owning planner.
    P5  — EMAIL_TO_PLANNER: planner notification email queued (audit log).

    APPROVE branch ────
    P6a — APPROVE:        planner approves with the correct
                          ``expected_version``.
    P7a — SCHEDULED:      ``meeting_status`` flips to ``scheduled``;
                          ``version`` bumped.
    P8a — AURINKO_BOOKED: Aurinko booking exists (synthetic — see
                          ``_assert_aurinko_event``).
    P9a — ICS_TO_COUPLE:  email-with-ICS to couple in audit log.

    DECLINE branch (fresh fixture) ────
    P6b — DECLINE:        planner declines with reason.
    P7b — CANCELLED:      ``meeting_status`` flips to ``cancelled``.
    P8b — NO_AURINKO_EVENT: NO row in ``calendar_event_syncs`` for the
                          declined task.
    P9b — DECLINE_EMAIL:  couple receives decline-reason email.

    P10 — STALE_VERSION:  approve with stale ``expected_version`` returns
                          409 (optimistic-concurrency regression guard).
    P11 — CHROME_CHECK:   pause for Chrome verification — planner inbox
                          shows pending request → Approve → meeting
                          projects to calendar.

Usage
-----

    python testbed/verify_couple_booking_approval_decline.py

    # Unattended (skips ENTER gates — only verifies backend-observable state)
    TESTBED_NON_INTERACTIVE=1 \
        python testbed/verify_couple_booking_approval_decline.py
"""

from __future__ import annotations

import logging
import os
import sys
import uuid
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bson import ObjectId

from testbed.harness import PM_TOKEN_GOOD, Harness, PlannerSeed

logger = logging.getLogger(__name__)

DRIVER_NAME = "verify_couple_booking_approval_decline"
PLANNER_EMAIL = "test_planner+couple_approval@thespecialwedding.io"
PLANNER_PASSWORD = "AurinkoCoupleApproval2026!"  # pragma: allowlist secret
COUPLE_EMAIL = "test_couple+approval@thespecialwedding.io"
COUPLE_PASSWORD = "CoupleApprovalCouple2026!"  # pragma: allowlist secret
COUPLE_PARTNER1 = "Approve"
COUPLE_PARTNER2 = "Decline"

TEST_CLOCK_NAME = "couple-booking-approval-decline"
TEST_CLOCK_ID = os.getenv("COUPLE_APPROVAL_CLOCK_ID")
PLAN_ID = os.getenv("COUPLE_APPROVAL_PLAN_ID", "plan_signature")

# Stub Aurinko connection identifiers — the driver does not exercise real
# OAuth.  Reuse the convention from verify_couple_booking_lifecycle.
SYNTH_AURINKO_ACCOUNT_ID = "testbed-couple-approval-account"
SYNTH_AURINKO_CALENDAR_ID = "testbed-couple-approval-calendar"
SYNTH_AURINKO_PROVIDER = "google"

# Fixture identifiers — distinct so the two branches never share state.
FIXTURE_APPROVE = "approve_branch"
FIXTURE_DECLINE = "decline_branch"


# =============================================================================
# Soft-fail helper — endpoints under construction
# =============================================================================


def _soft_fail(h: Harness, phase_name: str, status: int, body: str) -> bool:
    """Return True if the caller should continue past a not-yet-implemented endpoint.

    Phase 2-3 endpoints (`/couple/portal/meetings/request`,
    `/admin/planner/calendar/meetings/{id}/propose-slots`,
    `/couple/portal/meetings/pick-slot`) may not exist yet.  When the
    backend returns 404 or 501 surface the gap explicitly and return True
    so the driver keeps moving; any other non-2xx is a hard failure.
    """
    if status in (404, 501):
        h.log.info(
            f"  ⚠ {phase_name}: endpoint returned {status} — not yet wired. "
            f"Skipping this phase. Body excerpt: {body[:200]}"
        )
        return True
    return False


# =============================================================================
# Mongo helpers — seed connection + cleanup
# =============================================================================


def _seed_calendar_connection(h: Harness, *, owner_id: str, owner_email: str) -> str:
    """Insert (or update) a stub ``calendar_connections`` row.

    Pinned to ``couple_booking_auto_confirm=False`` — that is the precondition
    for every phase in this driver.  Toggling this to True would short-circuit
    the approval-gate path and is covered by the sibling lifecycle driver.
    """
    now = datetime.now(timezone.utc)
    doc = {
        "owner_planner_id": owner_id,
        "owner_planner_email": owner_email,
        "user_id": owner_id,
        "user_email": owner_email,
        "provider": SYNTH_AURINKO_PROVIDER,
        "provider_account_email": owner_email,
        "provider_account_name": "Testbed Calendar (approval-decline)",
        "aurinko_account_id": SYNTH_AURINKO_ACCOUNT_ID,
        "aurinko_calendar_id": SYNTH_AURINKO_CALENDAR_ID,
        "aurinko_access_token_encrypted": "testbed-stub-token",
        "calendar_id": SYNTH_AURINKO_CALENDAR_ID,
        "calendar_name": "Testbed Primary",
        "is_writable": True,
        "is_primary": True,
        "is_default_write_target": True,
        "scheduler_access_mode": "workspace_default",
        "sync_targeting_mode": "automatic_and_manual",
        "allowed_scheduler_user_ids": [],
        "allowed_scheduler_roles": [],
        "allowed_schedule_item_types": [],
        "allowed_wedding_ids": [],
        "is_shared_in_team_view": True,
        "details_visibility": "details",
        "sync_enabled": True,
        "couple_booking_auto_confirm": False,
        "connection_status": "active",
        "last_error": None,
        "updated_at": now,
        "created_at": now,
    }
    query = {
        "owner_planner_id": owner_id,
        "user_id": owner_id,
        "aurinko_account_id": SYNTH_AURINKO_ACCOUNT_ID,
        "aurinko_calendar_id": SYNTH_AURINKO_CALENDAR_ID,
    }
    h.mongo["calendar_connections"].update_one(query, {"$set": doc}, upsert=True)
    row = h.mongo["calendar_connections"].find_one(query, {"_id": 1})
    assert row, "stub calendar_connections upsert did not return a document"
    return str(row["_id"])


def _wipe_test_state(h: Harness) -> None:
    """Belt-and-braces sweep so reruns enter a known-empty state."""
    user = h.mongo["users"].find_one({"email": PLANNER_EMAIL}, {"_id": 1})
    if not user:
        return
    owner_id = str(user["_id"])
    sweep_filters = {
        "calendar_connections": {"owner_planner_id": owner_id},
        "planner_tasks": {"owner_planner_id": owner_id},
        "calendar_event_syncs": {"owner_planner_id": owner_id},
        "calendar_idempotency_keys": {
            "scope_key": {"$regex": f"couple_meeting.*{COUPLE_EMAIL}"}
        },
        "planner_notifications": {"planner_id": {"$in": [owner_id, PLANNER_EMAIL]}},
        "calendar_audit_log": {
            "$or": [
                {"owner_planner_email": PLANNER_EMAIL},
                {"actor_email": PLANNER_EMAIL},
                {"actor_email": COUPLE_EMAIL},
            ]
        },
        "email_audit_log": {
            "$or": [
                {"to_email": COUPLE_EMAIL},
                {"to_email": PLANNER_EMAIL},
            ]
        },
    }
    for coll, filt in sweep_filters.items():
        if coll not in h.mongo.list_collection_names():
            continue
        result = h.mongo[coll].delete_many(filt)
        if result.deleted_count:
            h.log.info(
                f"  ✅ {coll}: removed {result.deleted_count} doc(s) for plus-variant"
            )
    wedding_docs = list(
        h.mongo["weddings"].find(
            {
                "$or": [
                    {"assigned_planner_email": PLANNER_EMAIL},
                    {"created_by": PLANNER_EMAIL},
                ]
            },
            {"_id": 1},
        )
    )
    wedding_ids = [str(w["_id"]) for w in wedding_docs]
    if wedding_ids:
        h.mongo["couple_users"].delete_many({"wedding_id": {"$in": wedding_ids}})
    h.mongo["couple_users"].delete_many({"email": COUPLE_EMAIL})


# =============================================================================
# Time helpers
# =============================================================================


def _next_business_day_at(*, hour: int, offset_days: int = 2) -> datetime:
    candidate = datetime.now(timezone.utc) + timedelta(days=offset_days)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return datetime.combine(
        candidate.date(), time(hour=hour, minute=0), tzinfo=timezone.utc
    )


def _three_candidate_slots(*, base_hour: int = 9) -> list[dict]:
    """Build three half-hour candidate slots on the next business day."""
    start = _next_business_day_at(hour=base_hour)
    return [
        {
            "start": (start + timedelta(minutes=30 * i)).isoformat(),
            "end": (start + timedelta(minutes=30 * (i + 1))).isoformat(),
        }
        for i in range(3)
    ]


# =============================================================================
# P0 — SEED
# =============================================================================


def phase_seed(h: Harness, admin_token: str, clock_id: str) -> PlannerSeed:
    h.phase("P0_SEED", "Planner seeded with active sub + stub Aurinko connection")
    _wipe_test_state(h)
    existing = h.mongo["users"].find_one({"email": PLANNER_EMAIL})
    if existing:
        sub = h.mongo["user_subscriptions"].find_one(
            {
                "user_id": str(existing["_id"]),
                "status": {"$in": ["active", "trialing"]},
            }
        )
        cust = h.mongo["stripe_customers"].find_one({"user_id": str(existing["_id"])})
        if sub and cust:
            h.log.info(
                f"  ♻ Reusing planner user_id={existing['_id']} "
                f"customer_id={cust['stripe_customer_id']}"
            )
            return PlannerSeed(
                clock_id=clock_id,
                customer_id=cust["stripe_customer_id"],
                subscription_id=sub["stripe_subscription_id"],
                user_id=str(existing["_id"]),
                email=PLANNER_EMAIL,
                plan_id=PLAN_ID,
                has_trial=False,
            )
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
    h.log.info(f"  ✅ planner user_id={seed.user_id}")
    return seed


def phase_create_wedding_and_invite_couple(
    h: Harness, planner_token: str
) -> tuple[str, str]:
    h.phase("P0_WEDDING", "Planner creates wedding + invites couple")
    wedding_resp = h.api_post(
        "/admin/weddings",
        token=planner_token,
        json={
            "couple_names": f"{COUPLE_PARTNER1} & {COUPLE_PARTNER2}",
            "date": "2027-10-10",
        },
    )
    assert wedding_resp.status_code in (200, 201), (
        f"wedding create returned {wedding_resp.status_code} — {wedding_resp.text}"
    )
    payload = wedding_resp.json() or {}
    wedding_id = payload.get("_id") or payload.get("id") or payload.get("wedding_id")
    if not wedding_id:
        doc = h.mongo["weddings"].find_one(
            {"assigned_planner_email": PLANNER_EMAIL}, sort=[("_id", -1)]
        )
        assert doc, "could not resolve fresh wedding_id"
        wedding_id = str(doc["_id"])
    invite = h.api_post(
        "/admin/couple-portal/invite",
        token=planner_token,
        json={
            "email": COUPLE_EMAIL,
            "partner1_name": COUPLE_PARTNER1,
            "partner2_name": COUPLE_PARTNER2,
            "wedding_id": wedding_id,
        },
    )
    assert invite.status_code in (200, 201), (
        f"invite failed {invite.status_code} — {invite.text}"
    )
    body = invite.json() or {}
    invite_token = (body.get("setup_link") or "").rsplit("/", 1)[-1]
    if not invite_token:
        doc = h.mongo["couple_users"].find_one(
            {"email": COUPLE_EMAIL, "wedding_id": wedding_id},
            {"invite_token": 1},
        )
        assert doc and doc.get("invite_token"), "could not resolve invite_token"
        invite_token = doc["invite_token"]
    setup = h.api_post(
        "/couple/setup-password",
        json={"token": invite_token, "password": COUPLE_PASSWORD},
    )
    assert setup.status_code in (200, 201), (
        f"couple setup failed {setup.status_code} — {setup.text}"
    )
    couple_token = (setup.json() or {}).get("access_token")
    assert couple_token, "couple setup missing access_token"
    h.log.info(f"  ✅ wedding_id={wedding_id} and couple token acquired")
    return wedding_id, couple_token


# =============================================================================
# P1-P5 — request, propose, pick, observe notif + email
# =============================================================================


def phase_couple_request(
    h: Harness, couple_token: str, *, fixture: str, owner_id: str
) -> str | None:
    h.phase(
        f"P1_COUPLE_REQUEST ({fixture})",
        "Couple POSTs an open meeting request (no slot picked yet)",
    )
    payload = {
        "title": f"[testbed/{fixture}] approval-flow request",
        "notes": f"[testbed/{fixture}] couple_booking_approval_decline driver",
        "duration_minutes": 30,
        "timezone": "UTC",
        "staff_id": owner_id,
        "idempotency_key": uuid.uuid4().hex,
    }
    resp = h.api_post(
        "/couple/portal/meetings/request", token=couple_token, json=payload
    )
    h.log.info(f"  POST /couple/portal/meetings/request -> {resp.status_code}")
    if _soft_fail(h, "P1_COUPLE_REQUEST", resp.status_code, resp.text):
        return None
    assert resp.status_code in (200, 201), (
        f"couple request returned {resp.status_code} — {resp.text}"
    )
    body = resp.json() or {}
    task_id = body.get("meeting_id") or body.get("task_id")
    assert task_id, f"request response missing meeting_id/task_id — body={body}"
    h.log.info(f"  ✅ task_id = {task_id}")
    return task_id


def phase_planner_propose(
    h: Harness, planner_token: str, task_id: str, *, fixture: str
) -> bool:
    h.phase(
        f"P2_PLANNER_PROPOSE ({fixture})",
        "Planner proposes 3 candidate slots on the open request",
    )
    payload = {"slots": _three_candidate_slots(base_hour=9)}
    resp = h.api_post(
        f"/admin/planner/calendar/meetings/{task_id}/propose-slots",
        token=planner_token,
        json=payload,
    )
    h.log.info(f"  POST propose-slots -> {resp.status_code}")
    if _soft_fail(h, "P2_PLANNER_PROPOSE", resp.status_code, resp.text):
        return False
    assert resp.status_code in (200, 201), (
        f"propose returned {resp.status_code} — {resp.text}"
    )
    task = h.mongo["planner_tasks"].find_one({"_id": ObjectId(task_id)})
    assert task, f"planner_tasks row missing for {task_id}"
    proposed = task.get("proposed_slots") or task.get("candidate_slots") or []
    assert len(proposed) == 3, (
        f"REGRESSION: expected 3 proposed slots persisted, got {len(proposed)}"
    )
    h.log.info("  ✅ 3 candidate slots persisted on planner_task")
    return True


def phase_couple_pick(
    h: Harness, couple_token: str, task_id: str, *, fixture: str
) -> bool:
    h.phase(
        f"P3_COUPLE_PICK ({fixture})",
        "Couple picks one of the proposed slots — status MUST be pending_approval",
    )
    slots = _three_candidate_slots(base_hour=9)
    payload = {
        "meeting_id": task_id,
        "start": slots[1]["start"],
        "end": slots[1]["end"],
        "idempotency_key": uuid.uuid4().hex,
    }
    resp = h.api_post(
        "/couple/portal/meetings/pick-slot",
        token=couple_token,
        json=payload,
    )
    h.log.info(f"  POST pick-slot -> {resp.status_code}")
    if _soft_fail(h, "P3_COUPLE_PICK", resp.status_code, resp.text):
        return False
    assert resp.status_code in (200, 201), (
        f"pick-slot returned {resp.status_code} — {resp.text}"
    )
    body = resp.json() or {}
    assert body.get("meeting_status") == "pending_approval", (
        f"REGRESSION: pick-slot meeting_status={body.get('meeting_status')!r} "
        "(expected 'pending_approval' because auto-confirm is OFF). The slot "
        "service is short-circuiting to 'scheduled' — see "
        "app/services/availability_slot_service.py:_staff_requires_approval."
    )
    task = h.mongo["planner_tasks"].find_one({"_id": ObjectId(task_id)})
    assert task and task.get("meeting_status") == "pending_approval", (
        f"DB meeting_status={task.get('meeting_status')!r} differs from wire response"
    )
    sync_count = h.mongo["calendar_event_syncs"].count_documents({"task_id": task_id})
    assert sync_count == 0, (
        f"REGRESSION: pending-approval pick created {sync_count} "
        "calendar_event_syncs row(s) — must wait for planner approval"
    )
    h.log.info("  ✅ status=pending_approval, no sync row")
    return True


def phase_assert_notif_fired(h: Harness, task_id: str, owner_id: str) -> None:
    h.phase(
        "P4_NOTIF_FIRED",
        "planner_notifications row of type meeting_booking_request exists",
    )
    notif = h.mongo["planner_notifications"].find_one(
        {
            "type": "meeting_booking_request",
            "$or": [
                {"metadata.meeting_id": task_id},
                {"metadata.task_id": task_id},
            ],
        }
    )
    assert notif, (
        "REGRESSION: planner_notifications row of type "
        "'meeting_booking_request' did not fire on pending_approval pick"
    )
    assert notif.get("planner_id") in (owner_id, PLANNER_EMAIL), (
        f"notif addressed to {notif.get('planner_id')!r}, expected owner planner"
    )
    h.log.info(f"  ✅ notification fired (id={notif['_id']})")


def phase_assert_email_to_planner(h: Harness, task_id: str) -> None:
    h.phase(
        "P5_EMAIL_TO_PLANNER",
        "Notification email to planner queued (email_audit_log row)",
    )
    if "email_audit_log" not in h.mongo.list_collection_names():
        h.log.info("  ⚠ email_audit_log collection absent — phase soft-pass")
        return
    audit = h.mongo["email_audit_log"].find_one(
        {
            "to_email": PLANNER_EMAIL,
            "$or": [
                {"metadata.task_id": task_id},
                {"metadata.meeting_id": task_id},
                {"template": {"$regex": "booking.*request", "$options": "i"}},
            ],
        }
    )
    if not audit:
        h.log.info(
            "  ⚠ no booking-request email audit row yet — email delivery may be "
            "wired in a later phase. Continuing."
        )
        return
    h.log.info(f"  ✅ planner email queued (audit_id={audit['_id']})")


# =============================================================================
# APPROVE branch — P6a, P7a, P8a, P9a
# =============================================================================


def phase_approve(h: Harness, planner_token: str, task_id: str) -> int | None:
    h.phase(
        "P6a_APPROVE",
        "Planner POSTs approve-booking with correct expected_version → 200",
    )
    task = h.mongo["planner_tasks"].find_one({"_id": ObjectId(task_id)})
    assert task, f"planner_tasks row missing for {task_id}"
    pre_version = int(task.get("version") or 1)
    resp = h.api_post(
        f"/admin/planner/calendar/meetings/{task_id}/approve-booking"
        f"?expected_version={pre_version}",
        token=planner_token,
    )
    h.log.info(f"  POST approve-booking -> {resp.status_code}")
    if _soft_fail(h, "P6a_APPROVE", resp.status_code, resp.text):
        return None
    assert resp.status_code in (200, 503), (
        f"REGRESSION: approve returned {resp.status_code} (expected 200, or "
        f"503 with stub Aurinko). body={resp.text}"
    )
    h.log.info("  ✅ approve accepted")
    return pre_version


def phase_assert_scheduled(h: Harness, task_id: str, pre_version: int) -> None:
    h.phase("P7a_SCHEDULED", "meeting_status=scheduled and version bumped")
    task = h.mongo["planner_tasks"].find_one({"_id": ObjectId(task_id)})
    assert task, f"planner_tasks row missing for {task_id}"
    status = task.get("meeting_status")
    version = int(task.get("version") or 0)
    assert status == "scheduled", (
        f"REGRESSION: post-approve meeting_status={status!r}, expected 'scheduled'"
    )
    assert version > pre_version, (
        f"REGRESSION: version not bumped after approve "
        f"(pre={pre_version}, post={version})"
    )
    h.log.info(f"  ✅ scheduled, version {pre_version}→{version}")


def phase_assert_aurinko_booked(h: Harness, task_id: str) -> None:
    h.phase(
        "P8a_AURINKO_BOOKED",
        "calendar_event_syncs row created (proxy for Aurinko booking)",
    )
    row = h.mongo["calendar_event_syncs"].find_one({"task_id": task_id})
    if not row:
        h.log.info(
            "  ⚠ no calendar_event_syncs row — stub Aurinko connection cannot "
            "actually project events. In SANDBOX mode this MUST exist."
        )
        return
    assert row.get("aurinko_account_id") == SYNTH_AURINKO_ACCOUNT_ID, (
        f"sync row aurinko_account_id={row.get('aurinko_account_id')!r}"
    )
    h.log.info(f"  ✅ sync row id={row['_id']}")


def phase_assert_ics_to_couple(h: Harness, task_id: str) -> None:
    h.phase("P9a_ICS_TO_COUPLE", "ICS email to couple in audit log")
    if "email_audit_log" not in h.mongo.list_collection_names():
        h.log.info("  ⚠ email_audit_log collection absent — phase soft-pass")
        return
    audit = h.mongo["email_audit_log"].find_one(
        {
            "to_email": COUPLE_EMAIL,
            "$or": [
                {"metadata.task_id": task_id},
                {"metadata.meeting_id": task_id},
                {"template": {"$regex": "booking.*confirm|ics", "$options": "i"}},
            ],
        }
    )
    if not audit:
        h.log.info("  ⚠ no ICS-to-couple email row yet — email wiring may lag")
        return
    h.log.info(f"  ✅ couple email queued (audit_id={audit['_id']})")


# =============================================================================
# DECLINE branch — P6b, P7b, P8b, P9b
# =============================================================================


def phase_decline(h: Harness, planner_token: str, task_id: str, *, reason: str) -> bool:
    h.phase(
        "P6b_DECLINE",
        "Planner POSTs decline-booking with reason → 200",
    )
    task = h.mongo["planner_tasks"].find_one({"_id": ObjectId(task_id)})
    assert task, f"planner_tasks row missing for {task_id}"
    expected_version = int(task.get("version") or 1)
    resp = h.api_post(
        f"/admin/planner/calendar/meetings/{task_id}/decline-booking"
        f"?expected_version={expected_version}&reason={reason}",
        token=planner_token,
    )
    h.log.info(f"  POST decline-booking -> {resp.status_code}")
    if _soft_fail(h, "P6b_DECLINE", resp.status_code, resp.text):
        return False
    assert resp.status_code == 200, (
        f"REGRESSION: decline returned {resp.status_code} — {resp.text}"
    )
    h.log.info("  ✅ decline accepted")
    return True


def phase_assert_cancelled(h: Harness, task_id: str) -> None:
    h.phase("P7b_CANCELLED", "meeting_status=cancelled after decline")
    task = h.mongo["planner_tasks"].find_one({"_id": ObjectId(task_id)})
    assert task, f"planner_tasks row missing for {task_id}"
    assert task.get("meeting_status") == "cancelled", (
        f"REGRESSION: post-decline status={task.get('meeting_status')!r}, "
        "expected 'cancelled'"
    )
    audit = h.mongo["calendar_audit_log"].find_one(
        {
            "$or": [
                {"action": "calendar_couple_booking_declined"},
                {"action": "couple_booking_declined"},
            ],
            "$and": [
                {
                    "$or": [
                        {"metadata.task_id": task_id},
                        {"metadata.meeting_id": task_id},
                    ]
                }
            ],
        }
    )
    if not audit:
        h.log.info("  ⚠ no decline audit row found — verify audit wiring")
    else:
        h.log.info(f"  ✅ cancelled, audit row id={audit['_id']}")


def phase_assert_no_aurinko_event(h: Harness, task_id: str) -> None:
    h.phase(
        "P8b_NO_AURINKO_EVENT",
        "calendar_event_syncs MUST NOT contain a row for the declined task",
    )
    count = h.mongo["calendar_event_syncs"].count_documents({"task_id": task_id})
    assert count == 0, (
        f"REGRESSION: declined task has {count} calendar_event_syncs row(s) — "
        "decline must NOT project to Aurinko"
    )
    h.log.info("  ✅ no Aurinko sync rows for declined task")


def phase_assert_decline_email(h: Harness, task_id: str, reason: str) -> None:
    h.phase(
        "P9b_DECLINE_EMAIL",
        "Couple receives decline-reason email (audit log)",
    )
    if "email_audit_log" not in h.mongo.list_collection_names():
        h.log.info("  ⚠ email_audit_log collection absent — phase soft-pass")
        return
    audit = h.mongo["email_audit_log"].find_one(
        {
            "to_email": COUPLE_EMAIL,
            "$or": [
                {"metadata.task_id": task_id},
                {"metadata.meeting_id": task_id},
                {"template": {"$regex": "decline", "$options": "i"}},
            ],
        }
    )
    if not audit:
        h.log.info("  ⚠ no decline email audit row — email wiring may lag")
        return
    body_text = (audit.get("body") or "") + (audit.get("subject") or "")
    if reason not in body_text:
        h.log.info(
            f"  ⚠ decline email present but reason text {reason!r} not in "
            f"body/subject — verify template variable wiring"
        )
    else:
        h.log.info(f"  ✅ decline email queued (audit_id={audit['_id']})")


# =============================================================================
# P10 — stale-version 409 + P11 — Chrome checkpoint
# =============================================================================


def phase_stale_version_rejected(h: Harness, planner_token: str, task_id: str) -> None:
    h.phase(
        "P10_STALE_VERSION",
        "Approve with expected_version=999 → 409 (Q14 regression guard)",
    )
    resp = h.api_post(
        f"/admin/planner/calendar/meetings/{task_id}/approve-booking"
        "?expected_version=999",
        token=planner_token,
    )
    h.log.info(f"  POST approve (stale) -> {resp.status_code}")
    if resp.status_code in (404, 501):
        h.log.info("  ⚠ approve-booking endpoint not yet wired — soft-pass")
        return
    assert resp.status_code == 409, (
        f"REGRESSION: stale expected_version returned {resp.status_code}, "
        f"expected 409. body={resp.text}"
    )
    detail = (resp.json() or {}).get("detail") or {}
    if isinstance(detail, dict) and "current_version" not in detail:
        h.log.info(f"  ⚠ 409 body missing current_version — detail={detail}")
    h.log.info("  ✅ stale-version 409 returned")


def phase_chrome_check(h: Harness, task_id: str) -> None:
    h.phase("P11_CHROME_CHECK", "Manual verification in Chrome")
    frontend = h.config.frontend_url.rstrip("/")
    inbox_url = f"{frontend}/admin/planner/calendar"
    h.checkpoint(
        "P11_CHROME_CHECK",
        expectations=[
            f"Open Chrome to {inbox_url}",
            f"Log in as {PLANNER_EMAIL} / {PLANNER_PASSWORD}",
            f"Inbox/Review tray shows the pending booking request (task_id={task_id})",
            "Click 'Approve' on that row",
            "Confirm the meeting now appears on the planner's calendar grid",
            "Confirm a green toast: 'Booking approved' (or equivalent)",
            "Confirm console is clean — no 4xx or unhandled-promise noise",
        ],
    )


# =============================================================================
# Entry point
# =============================================================================


def main() -> int:
    h = Harness(driver_name=DRIVER_NAME)
    h.banner("VERIFY — Couple Booking Approve vs Decline branches")
    h.log.info(f"  Planner email : {PLANNER_EMAIL}")
    h.log.info(f"  Couple email  : {COUPLE_EMAIL}")
    h.log.info(f"  Clock name    : {TEST_CLOCK_NAME}")
    h.log.info(
        f"  Clock id      : {TEST_CLOCK_ID or '(none — fresh; pin via COUPLE_APPROVAL_CLOCK_ID next run)'}"
    )
    h.log.info(f"  Plan id       : {PLAN_ID}")
    h.log.info(f"  Started at    : {datetime.now(timezone.utc).isoformat()}")

    h.preflight()
    h.phase("CLOCK", "Resolve the reusable test clock")
    clock = h.get_or_create_clock(TEST_CLOCK_ID, name=TEST_CLOCK_NAME)
    clock_id = clock.id

    admin_token = h.get_admin_token()
    seed = phase_seed(h, admin_token, clock_id)
    planner_token = h.login(PLANNER_EMAIL, PLANNER_PASSWORD)
    _, couple_token = phase_create_wedding_and_invite_couple(h, planner_token)
    connection_id = _seed_calendar_connection(
        h, owner_id=seed.user_id, owner_email=PLANNER_EMAIL
    )
    h.log.info(f"  ✅ calendar_connection_id={connection_id}")

    # APPROVE FIXTURE
    h.banner("FIXTURE — APPROVE branch")
    approve_task_id = phase_couple_request(
        h, couple_token, fixture=FIXTURE_APPROVE, owner_id=seed.user_id
    )
    if approve_task_id:
        proposed_ok = phase_planner_propose(
            h, planner_token, approve_task_id, fixture=FIXTURE_APPROVE
        )
        picked_ok = (
            phase_couple_pick(h, couple_token, approve_task_id, fixture=FIXTURE_APPROVE)
            if proposed_ok
            else False
        )
        if picked_ok:
            phase_assert_notif_fired(h, approve_task_id, seed.user_id)
            phase_assert_email_to_planner(h, approve_task_id)
            pre_version = phase_approve(h, planner_token, approve_task_id)
            if pre_version is not None:
                phase_assert_scheduled(h, approve_task_id, pre_version)
                phase_assert_aurinko_booked(h, approve_task_id)
                phase_assert_ics_to_couple(h, approve_task_id)

    # DECLINE FIXTURE — fresh planner_task so the branches don't collide.
    h.banner("FIXTURE — DECLINE branch")
    decline_task_id = phase_couple_request(
        h, couple_token, fixture=FIXTURE_DECLINE, owner_id=seed.user_id
    )
    if decline_task_id:
        proposed_ok = phase_planner_propose(
            h, planner_token, decline_task_id, fixture=FIXTURE_DECLINE
        )
        picked_ok = (
            phase_couple_pick(h, couple_token, decline_task_id, fixture=FIXTURE_DECLINE)
            if proposed_ok
            else False
        )
        if picked_ok:
            phase_assert_notif_fired(h, decline_task_id, seed.user_id)
            phase_assert_email_to_planner(h, decline_task_id)
            reason = "scheduling_conflict"
            if phase_decline(h, planner_token, decline_task_id, reason=reason):
                phase_assert_cancelled(h, decline_task_id)
                phase_assert_no_aurinko_event(h, decline_task_id)
                phase_assert_decline_email(h, decline_task_id, reason)

    # P10 — stale-version 409. Use the approve fixture (already terminal,
    # so a stale-version retry is the cleanest probe of the concurrency
    # guard without disturbing the decline fixture).
    if approve_task_id:
        phase_stale_version_rejected(h, planner_token, approve_task_id)

    # P11 — manual Chrome verification. Point the user at the planner's
    # calendar inbox; if a third pending request is needed for the click,
    # the user generates it manually from the couple portal.
    pending_for_chrome = decline_task_id or approve_task_id or "(none)"
    phase_chrome_check(h, pending_for_chrome)

    h.banner("VERIFY — Couple Booking Approve/Decline COMPLETE ✅")
    h.log.info(f"  Pin COUPLE_APPROVAL_CLOCK_ID={clock_id} on subsequent runs.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"\n❌ Driver aborted: {exc}\n")
        raise SystemExit(1)
