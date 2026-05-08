#!/usr/bin/env python3
"""Aurinko event CRUD verification.

Walks the create / update / delete cycle for a planner_task that fans out
to a connected Aurinko calendar. Pins the rewrite's path-shape and
verb-shape claims that I cannot validate from unit tests alone:

    1. POST /v1/calendars/{calId}/events lands a real event.
    2. PATCH /v1/calendars/{calId}/events/{eventId} updates that event
       (NOT PUT — Aurinko's docs explicitly say PATCH).
    3. DELETE /v1/calendars/{calId}/events/{eventId} removes it.
    4. The path always carries calendarId in the URL path, never as a
       query param.

Pre-condition: a connected, sync-enabled, writable calendar exists for
the test planner. Run ``verify_aurinko_oauth_lifecycle.py`` first if you
do not already have one.

Pair with ``cleanup_aurinko_lifecycle_state.py`` (shared across all three
Aurinko verifiers).

Scenario checkpoints
--------------------

    P0  — SEED:   planner exists, at least one writable connection row,
                  Aurinko sandbox reachable.
    P1  — CREATE: POST /admin/planner/calendar/tasks with
                  ``external_sync_requested=True`` results in a
                  ``calendar_event_syncs`` row pointing at a real
                  Aurinko event id; Aurinko-side GET on that id returns
                  matching subject + start/end.
    P2  — UPDATE: PATCH the task locally; PATCH lands at Aurinko (not
                  PUT) and the Aurinko-side event reflects the new
                  fields.
    P3  — DELETE: DELETE the task locally; Aurinko-side GET on the
                  event id returns 404.

Usage
-----

    AURINKO_SANDBOX_ENABLED=1 \
        python testbed/verify_aurinko_event_crud.py

    # Skip browser inspection gates:
    TESTBED_NON_INTERACTIVE=1 AURINKO_SANDBOX_ENABLED=1 \
        python testbed/verify_aurinko_event_crud.py
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

from testbed.harness import PM_TOKEN_GOOD, Harness

logger = logging.getLogger(__name__)

DRIVER_NAME = "verify_aurinko_event_crud"

# Match the OAuth-lifecycle planner so a single connection covers both runs.
PLANNER_EMAIL = "test_planner+aurinko_oauth@thespecialwedding.io"
PLANNER_PASSWORD = "AurinkoOAuth2026!"  # pragma: allowlist secret
PLAN_ID = os.getenv("AURINKO_OAUTH_PLAN_ID", "plan_signature")

INTERACTIVE = os.getenv("TESTBED_NON_INTERACTIVE", "0") not in ("1", "true", "yes")
SANDBOX_ENABLED = os.getenv("AURINKO_SANDBOX_ENABLED", "0") in ("1", "true", "yes")


def _checkpoint(h: Harness, name: str, ok: bool, detail: str = "") -> None:
    marker = "PASS" if ok else "FAIL"
    h.log.info("CHECKPOINT %s [%s] %s", name, marker, detail)
    if not ok:
        raise SystemExit(f"FAIL {name}: {detail}")


def _writable_connection_for_planner(h: Harness) -> dict | None:
    return h.mongo["calendar_connections"].find_one(
        {
            "user_email": PLANNER_EMAIL,
            "is_writable": True,
            "sync_enabled": True,
        }
    )


def _aurinko_get_event(account_token: str, calendar_id: str, event_id: str):
    """Probe Aurinko directly to verify the event landed / is gone."""
    import httpx
    from urllib.parse import quote

    base = os.getenv("AURINKO_API_BASE_URL", "https://api.aurinko.io/v1").rstrip("/")
    url = (
        f"{base}/calendars/{quote(calendar_id, safe='')}"
        f"/events/{quote(event_id, safe='')}"
    )
    return httpx.get(
        url,
        headers={"Authorization": f"Bearer {account_token}"},
        timeout=20,
    )


def _phase_create(h: Harness, planner_token: str) -> tuple[str, str]:
    start = datetime.now(timezone.utc) + timedelta(days=1)
    end = start + timedelta(hours=1)
    payload = {
        "title": f"Aurinko-CRUD-{int(start.timestamp())}",
        "category": "meeting",
        "priority": "low",
        "status": "pending",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
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
    body = response.json() if response.ok else {"err": response.text}
    task_id = str(body.get("id") or "")
    _checkpoint(h, "P1a_CREATE_HTTP", response.ok and bool(task_id), f"body={body}")

    sync_row = h.mongo["calendar_event_syncs"].find_one({"task_id": task_id})
    external_event_id = str((sync_row or {}).get("external_event_id") or "")
    _checkpoint(
        h,
        "P1b_SYNC_ROW",
        sync_row is not None and bool(external_event_id),
        f"sync_row={'yes' if sync_row else 'no'} ext_event_id={external_event_id}",
    )
    return task_id, external_event_id


def _phase_update(h: Harness, planner_token: str, task_id: str) -> None:
    new_title = f"Aurinko-CRUD-updated-{int(datetime.now().timestamp())}"
    response = requests.patch(
        f"{h.config.backend_url}/admin/planner/calendar/tasks/{task_id}",
        json={"title": new_title},
        headers={
            "Authorization": f"Bearer {planner_token}",
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    _checkpoint(h, "P2_UPDATE_HTTP", response.ok, f"status={response.status_code}")


def _phase_delete(h: Harness, planner_token: str, task_id: str) -> None:
    response = requests.delete(
        f"{h.config.backend_url}/admin/planner/calendar/tasks/{task_id}",
        headers={"Authorization": f"Bearer {planner_token}"},
        timeout=30,
    )
    _checkpoint(h, "P3a_DELETE_HTTP", response.ok, f"status={response.status_code}")


def _phase_aurinko_assertions(
    h: Harness, calendar_id: str, external_event_id: str, *, expect_present: bool
) -> None:
    from app.services.calendar_provider_service import calendar_provider_service

    row = h.mongo["calendar_connections"].find_one({"user_email": PLANNER_EMAIL})
    if not row:
        _checkpoint(
            h, "AURINKO_PROBE", False, "no connection row to probe Aurinko with"
        )
        return
    token = calendar_provider_service._decrypt_token(
        row.get("aurinko_access_token_encrypted")
    )
    if not token:
        _checkpoint(h, "AURINKO_PROBE", False, "no decryptable account token")
        return
    response = _aurinko_get_event(token, calendar_id, external_event_id)
    if expect_present:
        _checkpoint(
            h,
            "AURINKO_PROBE_PRESENT",
            response.status_code == 200,
            f"status={response.status_code}",
        )
    else:
        _checkpoint(
            h,
            "AURINKO_PROBE_DELETED",
            response.status_code in (404, 410),
            f"status={response.status_code}",
        )


def main() -> int:
    if not SANDBOX_ENABLED:
        sys.stderr.write("AURINKO_SANDBOX_ENABLED must be set to run this driver.\n")
        return 2

    h = Harness(driver_name=DRIVER_NAME)
    h.banner("VERIFY — Aurinko Event CRUD")
    h.log.info(f"  Planner email : {PLANNER_EMAIL}")
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
    _checkpoint(h, "P0a_SEED", bool(planner_token), "planner login")

    connection = _writable_connection_for_planner(h)
    _checkpoint(
        h,
        "P0b_PRECONDITION",
        connection is not None,
        "writable + sync_enabled connection required — "
        "run verify_aurinko_oauth_lifecycle.py first",
    )
    assert connection is not None  # for type checker
    calendar_id = str(connection["aurinko_calendar_id"])

    task_id, external_event_id = _phase_create(h, planner_token)
    _phase_aurinko_assertions(h, calendar_id, external_event_id, expect_present=True)
    _phase_update(h, planner_token, task_id)
    _phase_aurinko_assertions(h, calendar_id, external_event_id, expect_present=True)
    _phase_delete(h, planner_token, task_id)
    _phase_aurinko_assertions(h, calendar_id, external_event_id, expect_present=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
