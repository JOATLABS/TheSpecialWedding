#!/usr/bin/env python3
"""Couple-booking AUTO-CONFIRM lifecycle verification.

Pins the contract for the auto-confirm branch of the round-2 couple-booking
workflow. When the planner's writable ``calendar_connection`` row carries
``couple_booking_auto_confirm=True``, a couple's slot pick is implicitly
approved — no planner gate, no PENDING_APPROVAL state, no
``meeting_booking_request`` notification. The meeting projects to the
planner's external calendar via Aurinko on the same wire-call, and an
ICS-delivery audit row is emitted to the couple.

This is the inverse-twin of ``verify_couple_booking_lifecycle.py`` (which
exercises the approval-gated path with auto_confirm=False). Both drivers
must pass for the round-2 workflow to be considered shipped — they share
the cleanup script ``cleanup_couple_booking_lifecycle_state.py`` but seed
distinct plus-variant planner / couple pairs.

Auto-confirm semantics
----------------------

* ``POST /couple/portal/meetings/request`` accepts a topic + duration +
  preferred-window; returns 201 with a ``request_id``.
* ``POST /admin/planner/calendar/booking-requests/{id}/propose`` writes
  up to N slots and emits a ``SlotsProposed`` audit event.
* ``GET /couple/portal/availability?request_id=X`` returns those slots.
* ``POST /couple/portal/meetings/book`` lands as
  ``meeting_status=scheduled`` immediately (auto_confirm skipped
  ``pending_approval``); NO ``meeting_booking_request`` planner ping;
  Aurinko-side event present; ICS-delivery audit row addressed to couple.

Pass / fail
-----------

PASS — every checkpoint P0–P6 emits ``[PASS]`` and the human at P7
confirms the couple portal shows the meeting in its schedule, the planner
calendar feed shows it, and no notification badge appears.

FAIL — any [FAIL] terminates the run with the failing detail. The most
likely early failure while the feature is still being built is a
``404 Not Found`` from one of the booking-request endpoints (Phase 2 &
3 of the feature PR build them); the script reports the missing route
verbatim so the user can see exactly which phase blocks progress.

Usage
-----

    AURINKO_SANDBOX_ENABLED=1 \
        python testbed/verify_couple_booking_auto_confirm.py

    # CI / unattended (skips P7 human-watch-Chrome gate):
    TESTBED_NON_INTERACTIVE=1 AURINKO_SANDBOX_ENABLED=1 \
        python testbed/verify_couple_booking_auto_confirm.py

Pair with ``cleanup_couple_booking_lifecycle_state.py``.
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

from testbed.harness import PM_TOKEN_GOOD, Harness

logger = logging.getLogger(__name__)

DRIVER_NAME = "verify_couple_booking_auto_confirm"
PLANNER_EMAIL = "test_planner+couple_auto_confirm@thespecialwedding.io"
PLANNER_PASSWORD = "AurinkoCoupleAuto2026!"  # pragma: allowlist secret
COUPLE_EMAIL = "test_couple+auto_confirm@thespecialwedding.io"
COUPLE_PASSWORD = "AutoConfirmCouple2026!"  # pragma: allowlist secret
COUPLE_PARTNER1 = "Auto"
COUPLE_PARTNER2 = "Confirm"
PLAN_ID = os.getenv("AURINKO_OAUTH_PLAN_ID", "plan_signature")

SYNTH_AURINKO_ACCOUNT_ID = "testbed-auto-confirm-account"
SYNTH_AURINKO_CALENDAR_ID = "testbed-auto-confirm-calendar"
SYNTH_AURINKO_PROVIDER = "google"

INTERACTIVE = os.getenv("TESTBED_NON_INTERACTIVE", "0") not in ("1", "true", "yes")
SANDBOX_ENABLED = os.getenv("AURINKO_SANDBOX_ENABLED", "0") in ("1", "true", "yes")

COUPLE_PORTAL_URL_TEMPLATE = "http://localhost:3000/portal/{slug}/dashboard"
PLANNER_CALENDAR_URL = "http://localhost:3000/admin/planner/calendar?tab=requests"


def _checkpoint(h: Harness, name: str, ok: bool, detail: str = "") -> None:
    marker = "PASS" if ok else "FAIL"
    h.log.info("CHECKPOINT %s [%s] %s", name, marker, detail)
    if not ok:
        raise SystemExit(f"FAIL {name}: {detail}")


def _human_gate(prompt: str) -> None:
    if not INTERACTIVE:
        logger.info("  (non-interactive: skipping human gate — %s)", prompt[:64])
        return
    print("\n" + "=" * 72)
    print(prompt)
    print("=" * 72)
    input("Press ENTER once Chrome verification is complete… ")


def _seed_auto_confirm_connection(h: Harness, owner_id: str) -> str:
    """Upsert a stub calendar_connection row with auto_confirm=True."""
    now = datetime.now(timezone.utc)
    doc = {
        "owner_planner_id": owner_id,
        "owner_planner_email": PLANNER_EMAIL,
        "user_id": owner_id,
        "user_email": PLANNER_EMAIL,
        "provider": SYNTH_AURINKO_PROVIDER,
        "provider_account_email": PLANNER_EMAIL,
        "provider_account_name": "Testbed Auto-Confirm Calendar",
        "aurinko_account_id": SYNTH_AURINKO_ACCOUNT_ID,
        "aurinko_calendar_id": SYNTH_AURINKO_CALENDAR_ID,
        "aurinko_access_token_encrypted": "testbed-stub-token",
        "calendar_id": SYNTH_AURINKO_CALENDAR_ID,
        "calendar_name": "Testbed Auto-Confirm Primary",
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
        "couple_booking_auto_confirm": True,
        "connection_status": "active",
        "last_error": None,
        "updated_at": now,
        "created_at": now,
    }
    query = {
        "owner_planner_id": owner_id,
        "aurinko_account_id": SYNTH_AURINKO_ACCOUNT_ID,
        "aurinko_calendar_id": SYNTH_AURINKO_CALENDAR_ID,
    }
    h.mongo["calendar_connections"].update_one(query, {"$set": doc}, upsert=True)
    row = h.mongo["calendar_connections"].find_one(query, {"_id": 1})
    assert row, "stub calendar_connection upsert did not return a document"
    return str(row["_id"])


def _create_wedding_and_couple(h: Harness, planner_token: str) -> tuple[str, str, str]:
    """Create a wedding + invite couple. Return (wedding_id, slug, couple_token)."""
    resp = h.api_post(
        "/admin/weddings",
        token=planner_token,
        json={
            "couple_names": f"{COUPLE_PARTNER1} & {COUPLE_PARTNER2}",
            "date": "2027-11-11",
        },
    )
    assert resp.status_code in (200, 201), (
        f"wedding create — {resp.status_code} {resp.text}"
    )
    body = resp.json() or {}
    wedding_id = body.get("_id") or body.get("id") or body.get("wedding_id")
    if not wedding_id:
        doc = h.mongo["weddings"].find_one(
            {"assigned_planner_email": PLANNER_EMAIL}, sort=[("_id", -1)]
        )
        assert doc, "could not resolve freshly-created wedding_id"
        wedding_id = str(doc["_id"])
    w_doc = h.mongo["weddings"].find_one({"_id": ObjectId(wedding_id)}) or {}
    slug = w_doc.get("portal_slug") or w_doc.get("slug") or wedding_id

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
        f"invite — {invite.status_code} {invite.text}"
    )
    invite_token = (invite.json() or {}).get("setup_link", "").rsplit("/", 1)[-1]
    if not invite_token:
        doc = h.mongo["couple_users"].find_one(
            {"email": COUPLE_EMAIL, "wedding_id": wedding_id}, {"invite_token": 1}
        )
        assert doc and doc.get("invite_token"), "could not resolve invite_token"
        invite_token = doc["invite_token"]

    setup = h.api_post(
        "/couple/setup-password",
        json={"token": invite_token, "password": COUPLE_PASSWORD},
    )
    assert setup.status_code in (200, 201), f"setup — {setup.status_code} {setup.text}"
    couple_token = (setup.json() or {}).get("access_token")
    assert couple_token, "couple setup missing access_token"
    return wedding_id, slug, couple_token


def _next_business_window() -> tuple[datetime, datetime]:
    candidate = datetime.now(timezone.utc) + timedelta(days=2)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    start = datetime.combine(
        candidate.date(), time(hour=9, minute=0), tzinfo=timezone.utc
    )
    return start, start + timedelta(hours=4)


def _fail_on_missing_route(h: Harness, name: str, status: int, route: str) -> None:
    if status == 404:
        _checkpoint(h, name, False, f"404 Not Found — {route} is not implemented yet")
    if status == 501:
        _checkpoint(h, name, False, f"501 Not Implemented — {route} is stubbed only")


# ---------------------------------------------------------------------------
# Phases
# ---------------------------------------------------------------------------


def phase_seed(h: Harness) -> tuple[str, str, str, str]:
    """P0 — planner + active sub + auto_confirm=True connection."""
    admin_token = h.get_admin_token()
    h.seed_planner(
        admin_token=admin_token,
        email=PLANNER_EMAIL,
        password=PLANNER_PASSWORD,
        plan_id=PLAN_ID,
        pm_token=PM_TOKEN_GOOD,
    )
    planner_token = h.login(PLANNER_EMAIL, PLANNER_PASSWORD)
    user = h.mongo["users"].find_one({"email": PLANNER_EMAIL}, {"_id": 1})
    assert user, "planner not present in Mongo post-seed"
    owner_id = str(user["_id"])

    conn_id = _seed_auto_confirm_connection(h, owner_id=owner_id)
    conn = h.mongo["calendar_connections"].find_one(
        {"_id": ObjectId(conn_id)}, {"couple_booking_auto_confirm": 1}
    )
    _checkpoint(
        h,
        "P0_SEED",
        bool(planner_token)
        and conn
        and conn.get("couple_booking_auto_confirm") is True,
        f"conn_id={conn_id} auto_confirm={conn and conn.get('couple_booking_auto_confirm')}",
    )

    _wedding_id, slug, couple_token = _create_wedding_and_couple(h, planner_token)
    return planner_token, couple_token, owner_id, slug


def phase_couple_request(h: Harness, couple_token: str) -> str:
    """P1 — couple POSTs a booking request; 201 with request_id."""
    win_start, win_end = _next_business_window()
    resp = h.api_post(
        "/couple/portal/meetings/request",
        token=couple_token,
        json={
            "topic": "Walkthrough — venue logistics",
            "duration_minutes": 30,
            "preferred_window": {
                "start": win_start.isoformat(),
                "end": win_end.isoformat(),
            },
            "notes": "[testbed] auto_confirm driver",
            "idempotency_key": uuid.uuid4().hex,
        },
    )
    h.log.info("  POST /couple/portal/meetings/request -> %s", resp.status_code)
    _fail_on_missing_route(
        h, "P1_COUPLE_REQUEST", resp.status_code, "/couple/portal/meetings/request"
    )
    _checkpoint(
        h,
        "P1_COUPLE_REQUEST",
        resp.status_code == 201,
        f"status={resp.status_code} body={resp.text[:240]}",
    )
    request_id = (resp.json() or {}).get("request_id") or (resp.json() or {}).get("id")
    assert request_id, "response missing request_id"
    return request_id


def phase_planner_propose(
    h: Harness, planner_token: str, request_id: str, owner_id: str
) -> None:
    """P2 — planner proposes 3 slots; SlotsProposed audit row fires."""
    base_start, _ = _next_business_window()
    slots = [
        {
            "staff_id": owner_id,
            "start": (base_start + timedelta(hours=h_)).isoformat(),
            "end": (base_start + timedelta(hours=h_, minutes=30)).isoformat(),
        }
        for h_ in (1, 2, 3)
    ]
    route = f"/admin/planner/calendar/booking-requests/{request_id}/propose"
    resp = h.api_post(route, token=planner_token, json={"slots": slots})
    h.log.info("  POST %s -> %s", route, resp.status_code)
    _fail_on_missing_route(h, "P2_PLANNER_PROPOSE", resp.status_code, route)
    _checkpoint(
        h,
        "P2a_PROPOSE_HTTP",
        resp.status_code in (200, 201),
        f"status={resp.status_code} body={resp.text[:240]}",
    )
    audit = h.mongo["calendar_audit_log"].find_one(
        {"action": "SlotsProposed", "metadata.request_id": request_id}
    )
    _checkpoint(
        h,
        "P2b_SLOTS_PROPOSED_AUDIT",
        bool(audit),
        f"audit_row={'present' if audit else 'MISSING'} request_id={request_id}",
    )


def phase_couple_pick(h: Harness, couple_token: str, request_id: str) -> str:
    """P3 — couple fetches proposed slots, books; lands as scheduled."""
    avail = h.api_get(
        f"/couple/portal/availability?request_id={request_id}", token=couple_token
    )
    h.log.info(
        "  GET /couple/portal/availability?request_id=… -> %s", avail.status_code
    )
    _checkpoint(
        h,
        "P3a_PROPOSED_VISIBLE",
        avail.status_code == 200,
        f"status={avail.status_code} body={avail.text[:240]}",
    )
    proposed = (avail.json() or {}).get("slots") or []
    assert proposed, "no proposed slots returned for request"
    chosen = proposed[0]

    resp = h.api_post(
        "/couple/portal/meetings/book",
        token=couple_token,
        json={
            "request_id": request_id,
            "staff_id": chosen.get("staff_id"),
            "start": chosen.get("start"),
            "end": chosen.get("end"),
            "title": "[testbed] auto_confirm — couple pick",
            "notes": "[testbed] auto_confirm driver",
            "timezone": "UTC",
            "idempotency_key": uuid.uuid4().hex,
        },
    )
    h.log.info("  POST /couple/portal/meetings/book -> %s", resp.status_code)
    _checkpoint(
        h,
        "P3b_BOOK_HTTP",
        resp.status_code == 201,
        f"status={resp.status_code} body={resp.text[:240]}",
    )
    body = resp.json() or {}
    meeting_id = body.get("meeting_id") or body.get("id")
    assert meeting_id, "book response missing meeting_id"

    _checkpoint(
        h,
        "P3c_SCHEDULED_WIRE",
        body.get("meeting_status") == "scheduled"
        and body.get("requires_approval") is False,
        f"meeting_status={body.get('meeting_status')!r} requires_approval={body.get('requires_approval')!r}",
    )
    task = h.mongo["planner_tasks"].find_one({"_id": ObjectId(meeting_id)})
    _checkpoint(
        h,
        "P3d_SCHEDULED_DB",
        bool(task) and task.get("meeting_status") == "scheduled",
        f"db_meeting_status={task and task.get('meeting_status')!r} (must be 'scheduled')",
    )
    return meeting_id


def phase_aurinko_booked(h: Harness, meeting_id: str) -> None:
    """P4 — Aurinko event exists for this booking."""
    sync = h.mongo["calendar_event_syncs"].find_one({"task_id": meeting_id})
    _checkpoint(
        h,
        "P4a_SYNC_ROW",
        bool(sync) and bool(sync.get("aurinko_event_id")),
        f"sync_row={'present' if sync else 'MISSING'} "
        f"aurinko_event_id={sync and sync.get('aurinko_event_id')}",
    )
    if not sync or not sync.get("aurinko_event_id"):
        return

    # With SANDBOX_ENABLED=1 against a real Aurinko sandbox, probe the live
    # event. Under the stub-connection path the sync row alone is sufficient.
    try:
        import httpx
        from urllib.parse import quote
        from app.services.calendar_provider_service import calendar_provider_service

        row = h.mongo["calendar_connections"].find_one(
            {"user_email": PLANNER_EMAIL, "is_writable": True}
        )
        token = calendar_provider_service._decrypt_token(
            row.get("aurinko_access_token_encrypted")
        )
        if token == "testbed-stub-token" or not token:
            h.log.info("  (stub token — skipping live Aurinko probe)")
            return
        base = os.getenv("AURINKO_API_BASE_URL", "https://api.aurinko.io/v1").rstrip(
            "/"
        )
        url = (
            f"{base}/calendars/{quote(row['aurinko_calendar_id'], safe='')}"
            f"/events/{quote(sync['aurinko_event_id'], safe='')}"
        )
        response = httpx.get(
            url, headers={"Authorization": f"Bearer {token}"}, timeout=15
        )
        _checkpoint(
            h,
            "P4b_AURINKO_GET",
            response.status_code == 200,
            f"GET …/events/{sync['aurinko_event_id'][:12]}… status={response.status_code}",
        )
    except Exception as exc:  # noqa: BLE001
        _checkpoint(h, "P4b_AURINKO_GET", False, f"probe error: {exc}")


def phase_no_planner_notif(h: Harness, meeting_id: str) -> None:
    """P5 — auto_confirm must NOT fire meeting_booking_request."""
    notif = h.mongo["planner_notifications"].find_one(
        {"type": "meeting_booking_request", "metadata.meeting_id": meeting_id}
    )
    _checkpoint(
        h,
        "P5_NO_NOTIF",
        notif is None,
        f"notif={'PRESENT (regression)' if notif else 'absent (correct)'}",
    )


def phase_ics_to_couple(h: Harness, meeting_id: str) -> None:
    """P6 — ICS-delivery audit row addressed to the couple."""
    audit = h.mongo["calendar_audit_log"].find_one(
        {
            "action": {"$in": ["IcsDelivered", "ics_delivered", "EmailIcsDelivered"]},
            "metadata.meeting_id": meeting_id,
        }
    )
    recipient = (audit or {}).get("metadata", {}).get("recipient_email") or (
        audit or {}
    ).get("recipient_email")
    _checkpoint(
        h,
        "P6_ICS_TO_COUPLE",
        bool(audit) and recipient == COUPLE_EMAIL,
        f"audit_row={'present' if audit else 'MISSING'} recipient={recipient!r} "
        f"(expected {COUPLE_EMAIL})",
    )


def phase_chrome_check(h: Harness, slug: str) -> None:
    """P7 — human verifies the UX state in Chrome."""
    couple_url = COUPLE_PORTAL_URL_TEMPLATE.format(slug=slug)
    h.log.info("  Inspect in Chrome:")
    h.log.info("    Couple portal   : %s", couple_url)
    h.log.info("    Planner calendar: %s", PLANNER_CALENDAR_URL)
    _human_gate(
        "P7 — Chrome verification\n"
        f"  1. Couple portal ({couple_url}): meeting appears in the couple's\n"
        "     schedule with status 'Scheduled' (no 'Pending approval' badge).\n"
        f"  2. Planner calendar ({PLANNER_CALENDAR_URL}): same meeting renders\n"
        "     in the calendar feed.\n"
        "  3. Planner notification bell shows NO new badge for this meeting\n"
        "     (auto-confirm bypasses the approval ping)."
    )
    _checkpoint(h, "P7_CHROME_CHECK", True, "human-verified")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    if not SANDBOX_ENABLED:
        sys.stderr.write(
            "AURINKO_SANDBOX_ENABLED must be set to run this driver — set it to\n"
            "'1' to gate the Aurinko-bound phases on explicit opt-in. See\n"
            "testbed/README.md for sandbox setup.\n"
        )
        return 2

    h = Harness(driver_name=DRIVER_NAME)
    h.banner("VERIFY — Couple Booking AUTO-CONFIRM Lifecycle")
    h.log.info("  Planner email : %s", PLANNER_EMAIL)
    h.log.info("  Couple email  : %s", COUPLE_EMAIL)
    h.log.info("  Plan id       : %s", PLAN_ID)
    h.log.info("  Interactive   : %s", "YES" if INTERACTIVE else "NO")
    h.log.info("  Started at    : %s", datetime.now(timezone.utc).isoformat())
    h.preflight()

    planner_token, couple_token, owner_id, slug = phase_seed(h)
    request_id = phase_couple_request(h, couple_token)
    phase_planner_propose(h, planner_token, request_id, owner_id)
    meeting_id = phase_couple_pick(h, couple_token, request_id)
    phase_aurinko_booked(h, meeting_id)
    phase_no_planner_notif(h, meeting_id)
    phase_ics_to_couple(h, meeting_id)
    phase_chrome_check(h, slug)

    h.banner("VERIFY — Couple Booking AUTO-CONFIRM COMPLETE")
    h.log.info(
        "  Cleanup: python testbed/cleanup_couple_booking_lifecycle_state.py "
        "(extend its plus-variant list to include +couple_auto_confirm)."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"\nDriver aborted: {exc}\n")
        raise SystemExit(1)
