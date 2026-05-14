#!/usr/bin/env python3
"""External-edit resolution flow verification.

Pins the contract for the "modified externally" tray. Aurinko delivers a
webhook saying an event was modified outside our system; the planner sees
a tray badge and clicks Accept (adopt external as canonical) or Reject
(overwrite Aurinko with canonical). Each branch lands in
``calendar_webhook_service.handle_event_change`` first (flips
``external_conflict_status=pending_review`` and populates ``external_*``),
then the planner POSTs accept-external-change or reject-external-change
with ``expected_version``. A stale token must 409.

Each branch runs on its own fixture (separate task ids) so the two
post-conditions don't fight over the same planner_task row. Both share
the same connected calendar — the connection seed is reused from
``verify_aurinko_oauth_lifecycle.py``.

Scenario checkpoints
--------------------

    P0  — SEED:           planner + Aurinko connection + two SCHEDULED
                          meeting fixtures with synced events.
    P1  — EXTERNAL_EDIT:  manual gate (or TRIGGER_VIA_AURINKO=1).
    P2  — WEBHOOK_FIRED:  poll for pending_review + external_* populated.
                          30s budget, exponential backoff.
    P3  — UI_SHOWS_BADGE: Chrome — badge visible on the meeting card.
    P4a — ACCEPT_CALL    / P4b — REJECT_CALL.
    P5a — CANONICAL_UPDATED (canonical adopts external) /
    P5b — AURINKO_OVERWRITTEN (Aurinko reverts to canonical).
    P6a — NO_AURINKO_PUSHBACK / P6b — CANONICAL_PRESERVED.
    P7  — STALE_VERSION:  stale expected_version → 409.
    P8  — CHROME_CHECK:   inspect the resolved tray UI.

Usage
-----

    AURINKO_SANDBOX_ENABLED=1 \\
        python testbed/verify_external_edit_resolution.py

    TRIGGER_VIA_AURINKO=1 AURINKO_SANDBOX_ENABLED=1 \\
        python testbed/verify_external_edit_resolution.py
"""

from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
import requests
from bson import ObjectId

from testbed.harness import PM_TOKEN_GOOD, Harness

logger = logging.getLogger(__name__)

DRIVER_NAME = "verify_external_edit_resolution"
PLANNER_EMAIL = "test_planner+external_edit@thespecialwedding.io"
PLANNER_PASSWORD = "AurinkoExternalEdit2026!"  # pragma: allowlist secret
PLAN_ID = os.getenv("EXTERNAL_EDIT_PLAN_ID", "plan_signature")

INTERACTIVE = os.getenv("TESTBED_NON_INTERACTIVE", "0") not in ("1", "true", "yes")
SANDBOX_ENABLED = os.getenv("AURINKO_SANDBOX_ENABLED", "0") in ("1", "true", "yes")
TRIGGER_VIA_AURINKO = os.getenv("TRIGGER_VIA_AURINKO", "0") in ("1", "true", "yes")

POLL_TIMEOUT_SECONDS = 30
POLL_INITIAL_INTERVAL = 1.0
POLL_BACKOFF_FACTOR = 1.5
POLL_MAX_INTERVAL = 5.0

FIXTURE_TITLE_ACCEPT = "ExtEdit-Accept-Fixture"
FIXTURE_TITLE_REJECT = "ExtEdit-Reject-Fixture"


def _checkpoint(h: Harness, name: str, ok: bool, detail: str = "") -> None:
    marker = "PASS" if ok else "FAIL"
    h.log.info("CHECKPOINT %s [%s] %s", name, marker, detail)
    if not ok:
        raise SystemExit(f"FAIL {name}: {detail}")


def _public_webhook_url_ok() -> tuple[bool, str]:
    base = (os.getenv("NEXT_PUBLIC_API_BASE_URL") or "").rstrip("/")
    if not base:
        return False, "NEXT_PUBLIC_API_BASE_URL is unset"
    if "localhost" in base or "127.0.0.1" in base:
        return False, (
            f"NEXT_PUBLIC_API_BASE_URL={base!r} is local — Aurinko cannot reach it. "
            "Run `ngrok http 8000` and set NEXT_PUBLIC_API_BASE_URL to the tunnel URL."
        )
    return True, base


def _resolve_writable_connection(h: Harness) -> dict | None:
    return h.mongo["calendar_connections"].find_one(
        {"user_email": PLANNER_EMAIL, "is_writable": True, "sync_enabled": True}
    )


def _decrypt_token(connection: dict) -> str | None:
    from app.services.calendar_provider_service import calendar_provider_service

    return calendar_provider_service._decrypt_token(
        connection.get("aurinko_access_token_encrypted")
    )


def _aurinko_url(calendar_id: str, event_id: str) -> str:
    base = os.getenv("AURINKO_API_BASE_URL", "https://api.aurinko.io/v1").rstrip("/")
    return (
        f"{base}/calendars/{quote(calendar_id, safe='')}"
        f"/events/{quote(event_id, safe='')}"
    )


def _create_meeting_fixture(
    h: Harness, planner_token: str, *, title: str
) -> tuple[str, str]:
    """POST /admin/planner/calendar/tasks with external_sync_requested.
    Returns (task_id, external_event_id) once the sync row lands."""
    start = datetime.now(timezone.utc) + timedelta(days=2)
    payload = {
        "title": title,
        "category": "meeting",
        "priority": "low",
        "status": "pending",
        "start_date": start.isoformat(),
        "end_date": (start + timedelta(hours=1)).isoformat(),
        "all_day": False,
        "external_sync_requested": True,
        "schedule_item_type": "meeting",
        "timezone": "UTC",
    }
    response = requests.post(
        f"{h.config.backend_url}/admin/planner/calendar/tasks",
        json=payload,
        headers={
            "Authorization": f"Bearer {planner_token}",
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    body = response.json() if response.ok else {"err": response.text[:200]}
    task_id = str(body.get("id") or body.get("_id") or "")
    _checkpoint(
        h,
        f"P0_FIXTURE_CREATE[{title}]",
        response.ok and bool(task_id),
        f"status={response.status_code}",
    )
    # Sync row appears after projection runs — poll briefly.
    deadline = time.monotonic() + 15
    sync_row: dict | None = None
    while time.monotonic() < deadline:
        sync_row = h.mongo["calendar_event_syncs"].find_one({"task_id": task_id})
        if sync_row and sync_row.get("external_event_id"):
            break
        time.sleep(0.5)
    external_event_id = str((sync_row or {}).get("external_event_id") or "")
    _checkpoint(
        h,
        f"P0_FIXTURE_SYNCED[{title}]",
        bool(external_event_id),
        f"task_id={task_id} ext_event_id={external_event_id}",
    )
    return task_id, external_event_id


def _trigger_external_edit_via_aurinko(
    account_token: str, calendar_id: str, event_id: str, *, new_subject: str
) -> None:
    """PATCH the event via Aurinko's API. From Aurinko's notification path
    this is identical to a human edit in Google's web UI."""
    response = httpx.patch(
        _aurinko_url(calendar_id, event_id),
        headers={
            "Authorization": f"Bearer {account_token}",
            "Content-Type": "application/json",
        },
        json={"subject": new_subject},
        timeout=20,
    )
    if not response.is_success:
        raise SystemExit(
            f"FAIL P1_TRIGGER_AURINKO_PATCH: status={response.status_code} "
            f"body={response.text[:200]}"
        )


def _print_manual_edit_instructions(
    title: str, calendar_id: str, event_id: str
) -> None:
    print("\n" + "=" * 72)
    print(f"EXTERNAL EDIT REQUIRED — fixture: {title!r}")
    print("=" * 72)
    print("Open the Google Calendar / Microsoft 365 web UI for the connected")
    print(f"account; find the event titled {title!r}.")
    print("Edit it DIRECTLY in the provider UI (NOT via our app):")
    print("  - rename it (e.g. add ' [ext]')")
    print("  - optionally move it 30 minutes later")
    print("  - save the change")
    print(f"Aurinko ids: calendar={calendar_id}  event={event_id}")
    print("=" * 72)
    input("Press ENTER once the edit has been SAVED on the provider side: ")


def _poll_for_pending_review(h: Harness, task_id: str) -> dict | None:
    """Wait up to POLL_TIMEOUT_SECONDS for the webhook handler to flip the
    planner_task into pending_review with external_* fields populated.
    Exponential backoff — fast at first, easing as we wait."""
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    interval = POLL_INITIAL_INTERVAL
    try:
        oid = ObjectId(task_id)
    except Exception:
        return None
    while time.monotonic() < deadline:
        task = h.mongo["planner_tasks"].find_one({"_id": oid})
        if (
            task
            and task.get("external_conflict_status") == "pending_review"
            and task.get("external_title")
            and task.get("external_start_date")
        ):
            return task
        time.sleep(interval)
        interval = min(interval * POLL_BACKOFF_FACTOR, POLL_MAX_INTERVAL)
    return None


def _fetch_aurinko_event(
    account_token: str, calendar_id: str, event_id: str
) -> dict | None:
    response = httpx.get(
        _aurinko_url(calendar_id, event_id),
        headers={"Authorization": f"Bearer {account_token}"},
        timeout=20,
    )
    if not response.is_success:
        return None
    return response.json()


def _post_resolution(
    h: Harness, planner_token: str, task_id: str, *, action: str, expected_version: int
) -> requests.Response:
    """POST accept-external-change or reject-external-change. action ∈
    {'accept', 'reject'}. expected_version goes on the query string."""
    path = (
        f"/admin/planner/calendar/meetings/{task_id}/{action}-external-change"
        f"?expected_version={expected_version}"
    )
    return requests.post(
        f"{h.config.backend_url}{path}",
        headers={
            "Authorization": f"Bearer {planner_token}",
            "Content-Type": "application/json",
        },
        timeout=30,
    )


def _phase_external_edit(
    h: Harness,
    *,
    fixture_title: str,
    account_token: str,
    calendar_id: str,
    external_event_id: str,
) -> None:
    h.phase(
        f"P1_EXTERNAL_EDIT[{fixture_title}]",
        "Out-of-band edit so Aurinko fires a webhook delivery",
    )
    if TRIGGER_VIA_AURINKO:
        new_subject = f"{fixture_title}-ext-{int(time.time())}"
        _trigger_external_edit_via_aurinko(
            account_token, calendar_id, external_event_id, new_subject=new_subject
        )
        h.log.info(f"  Aurinko PATCH fired: new subject={new_subject!r}")
        return
    if not INTERACTIVE:
        _checkpoint(
            h,
            f"P1_TRIGGER[{fixture_title}]",
            False,
            "non-interactive mode requires TRIGGER_VIA_AURINKO=1",
        )
    _print_manual_edit_instructions(fixture_title, calendar_id, external_event_id)


def _phase_resolve_accept(h: Harness, planner_token: str, task_id: str) -> None:
    h.phase("P4a_ACCEPT", "Adopt external snapshot as canonical")
    before = h.mongo["planner_tasks"].find_one({"_id": ObjectId(task_id)})
    assert before is not None, "ACCEPT fixture vanished between P2 and P4a"
    pre_version = int(before.get("version") or 1)
    ext = {
        "title": before.get("external_title"),
        "start_date": before.get("external_start_date"),
        "end_date": before.get("external_end_date"),
    }
    # No-pushback check: count audit rows for Aurinko update before/after.
    pushback_filter = {
        "owner_planner_email": PLANNER_EMAIL,
        "action": {"$regex": "aurinko.*update|external_event_update"},
    }
    pushback_before = h.mongo["calendar_audit_log"].count_documents(pushback_filter)

    response = _post_resolution(
        h, planner_token, task_id, action="accept", expected_version=pre_version
    )
    _checkpoint(
        h,
        "P4a_ACCEPT_CALL",
        response.status_code in (200, 204),
        f"status={response.status_code} body={response.text[:200]}",
    )

    after = h.mongo["planner_tasks"].find_one({"_id": ObjectId(task_id)})
    assert after is not None
    matches = (
        after.get("title") == ext["title"]
        and after.get("start_date") == ext["start_date"]
        and after.get("end_date") == ext["end_date"]
    )
    _checkpoint(
        h,
        "P5a_CANONICAL_UPDATED",
        matches
        and after.get("external_conflict_status") == "resolved"
        and int(after.get("version") or 0) > pre_version,
        f"title={after.get('title')!r} status={after.get('external_conflict_status')!r} "
        f"version={pre_version}->{after.get('version')}",
    )

    pushback_after = h.mongo["calendar_audit_log"].count_documents(pushback_filter)
    _checkpoint(
        h,
        "P6a_NO_AURINKO_PUSHBACK",
        pushback_after == pushback_before,
        f"aurinko_update_audit_rows before={pushback_before} after={pushback_after}",
    )


def _phase_resolve_reject(
    h: Harness,
    planner_token: str,
    task_id: str,
    *,
    account_token: str,
    calendar_id: str,
    external_event_id: str,
) -> None:
    h.phase("P4b_REJECT", "Overwrite Aurinko with canonical")
    before = h.mongo["planner_tasks"].find_one({"_id": ObjectId(task_id)})
    assert before is not None, "REJECT fixture vanished between P2 and P4b"
    pre_version = int(before.get("version") or 1)
    canonical = {
        "title": before.get("title"),
        "start_date": before.get("start_date"),
        "end_date": before.get("end_date"),
    }

    response = _post_resolution(
        h, planner_token, task_id, action="reject", expected_version=pre_version
    )
    _checkpoint(
        h,
        "P4b_REJECT_CALL",
        response.status_code in (200, 204),
        f"status={response.status_code} body={response.text[:200]}",
    )

    # Allow the Aurinko PATCH to land before we GET the event back.
    time.sleep(2)
    aurinko_event = _fetch_aurinko_event(account_token, calendar_id, external_event_id)
    aurinko_subject = (aurinko_event or {}).get("subject") or (aurinko_event or {}).get(
        "title"
    )
    _checkpoint(
        h,
        "P5b_AURINKO_OVERWRITTEN",
        aurinko_event is not None and aurinko_subject == canonical["title"],
        f"aurinko_subject={aurinko_subject!r} expected={canonical['title']!r}",
    )

    after = h.mongo["planner_tasks"].find_one({"_id": ObjectId(task_id)})
    assert after is not None
    unchanged = (
        after.get("title") == canonical["title"]
        and after.get("start_date") == canonical["start_date"]
        and after.get("end_date") == canonical["end_date"]
    )
    _checkpoint(
        h,
        "P6b_CANONICAL_PRESERVED",
        unchanged
        and after.get("external_conflict_status") == "resolved"
        and int(after.get("version") or 0) > pre_version,
        f"title={after.get('title')!r} status={after.get('external_conflict_status')!r} "
        f"version={pre_version}->{after.get('version')}",
    )


def _phase_stale_version(h: Harness, planner_token: str, task_id: str) -> None:
    h.phase("P7_STALE_VERSION", "Stale expected_version → 409")
    # By now this task's version has bumped past 1 — sending 1 is stale.
    stale = _post_resolution(
        h, planner_token, task_id, action="accept", expected_version=1
    )
    _checkpoint(
        h,
        "P7_STALE_VERSION",
        stale.status_code == 409,
        f"status={stale.status_code} body={stale.text[:200]}",
    )


def main() -> int:
    if not SANDBOX_ENABLED:
        sys.stderr.write("AURINKO_SANDBOX_ENABLED must be set to run this driver.\n")
        return 2

    h = Harness(driver_name=DRIVER_NAME)
    h.banner("VERIFY — External-Edit Resolution (accept + reject)")
    h.log.info(f"  Planner email      : {PLANNER_EMAIL}")
    h.log.info(f"  Trigger via Aurinko: {TRIGGER_VIA_AURINKO}")
    h.log.info(f"  Interactive        : {INTERACTIVE}")

    public_ok, detail_or_url = _public_webhook_url_ok()
    _checkpoint(h, "P0_PUBLIC_URL", public_ok, detail_or_url)

    h.preflight()
    admin_token = h.get_admin_token()
    h.seed_planner(
        admin_token=admin_token,
        email=PLANNER_EMAIL,
        password=PLANNER_PASSWORD,
        plan_id=PLAN_ID,
        pm_token=PM_TOKEN_GOOD,
    )
    planner_token = h.login(PLANNER_EMAIL, PLANNER_PASSWORD)
    _checkpoint(h, "P0_PLANNER_LOGIN", bool(planner_token), "planner login")

    connection = _resolve_writable_connection(h)
    _checkpoint(
        h,
        "P0_PRECONDITION",
        connection is not None,
        "writable + sync_enabled connection required — run "
        "verify_aurinko_oauth_lifecycle.py first if missing",
    )
    assert connection is not None
    account_token = _decrypt_token(connection)
    calendar_id = str(connection.get("aurinko_calendar_id"))
    _checkpoint(
        h,
        "P0_CONNECTION_TOKEN",
        bool(account_token and calendar_id),
        f"calendar_id={calendar_id} token_present={bool(account_token)}",
    )
    assert account_token

    h.phase("P0_FIXTURES", "Create two SCHEDULED meetings with synced events")
    accept_task_id, accept_event_id = _create_meeting_fixture(
        h, planner_token, title=FIXTURE_TITLE_ACCEPT
    )
    reject_task_id, reject_event_id = _create_meeting_fixture(
        h, planner_token, title=FIXTURE_TITLE_REJECT
    )

    # ACCEPT branch
    _phase_external_edit(
        h,
        fixture_title=FIXTURE_TITLE_ACCEPT,
        account_token=account_token,
        calendar_id=calendar_id,
        external_event_id=accept_event_id,
    )
    h.phase("P2a_WEBHOOK_FIRED", f"Poll pending_review on {FIXTURE_TITLE_ACCEPT}")
    accept_task = _poll_for_pending_review(h, accept_task_id)
    _checkpoint(
        h,
        "P2a_PENDING_REVIEW",
        accept_task is not None,
        f"task_id={accept_task_id} polled_for={POLL_TIMEOUT_SECONDS}s",
    )
    assert accept_task is not None
    _checkpoint(
        h,
        "P2a_FIELDS_POPULATED",
        bool(accept_task.get("external_title"))
        and bool(accept_task.get("external_start_date")),
        f"external_title={accept_task.get('external_title')!r}",
    )
    h.checkpoint(
        "P3a_UI_BADGE",
        expectations=[
            f"Open the planner calendar UI for {PLANNER_EMAIL}.",
            f"Find the meeting card titled {FIXTURE_TITLE_ACCEPT!r}.",
            "The card must show a 'modified externally' badge.",
            "Click the card — side panel shows external snapshot alongside",
            "canonical values, with Accept and Reject buttons.",
        ],
    )
    _phase_resolve_accept(h, planner_token, accept_task_id)

    # REJECT branch
    _phase_external_edit(
        h,
        fixture_title=FIXTURE_TITLE_REJECT,
        account_token=account_token,
        calendar_id=calendar_id,
        external_event_id=reject_event_id,
    )
    h.phase("P2b_WEBHOOK_FIRED", f"Poll pending_review on {FIXTURE_TITLE_REJECT}")
    reject_task = _poll_for_pending_review(h, reject_task_id)
    _checkpoint(
        h,
        "P2b_PENDING_REVIEW",
        reject_task is not None,
        f"task_id={reject_task_id} polled_for={POLL_TIMEOUT_SECONDS}s",
    )
    assert reject_task is not None
    _checkpoint(
        h,
        "P2b_FIELDS_POPULATED",
        bool(reject_task.get("external_title"))
        and bool(reject_task.get("external_start_date")),
        f"external_title={reject_task.get('external_title')!r}",
    )
    _phase_resolve_reject(
        h,
        planner_token,
        reject_task_id,
        account_token=account_token,
        calendar_id=calendar_id,
        external_event_id=reject_event_id,
    )

    # P7 + P8 — reuse accept fixture (version is now > 1 → stale=1 → 409).
    _phase_stale_version(h, planner_token, accept_task_id)

    h.checkpoint(
        "P8_CHROME_TRAY_CHECK",
        expectations=[
            "Reload the planner calendar UI for a clean view.",
            f"{FIXTURE_TITLE_ACCEPT!r}: canonical fields now match the external",
            "    snapshot; badge cleared; history shows 'accepted external'.",
            f"{FIXTURE_TITLE_REJECT!r}: canonical title preserved; badge",
            "    cleared; Google's calendar shows the same canonical title;",
            "    history shows 'rejected external / pushed canonical to provider'.",
            "Devtools network: no 5xx, no console errors.",
        ],
    )

    h.banner("ALL CHECKPOINTS PASSED — external-edit resolution verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
