#!/usr/bin/env python3
"""Aurinko webhook round-trip verification.

Pins the rewrite's webhook claims that I cannot validate from unit tests
alone — specifically the contract between Aurinko's actual notification
delivery and our handler:

    1. An external edit on a connected calendar (made via Aurinko's API
       under a separate session, or made directly in Google Calendar's
       UI when running fully manually) results in an Aurinko delivery to
       ``<NEXT_PUBLIC_API_BASE_URL>/api/calendar/webhooks/aurinko``.
    2. The handler verifies the signature, returns 200, and queues a
       background snapshot fetch.
    3. The snapshot fetch succeeds, populating ``planner_tasks.external_*``
       fields and flipping ``external_conflict_status=pending_review``.
    4. Aurinko stops retrying after the 200 ack (no duplicate delivery
       processing visible in the audit log within a short soak window).

Pre-condition: a connected, sync-enabled, writable calendar exists for
the test planner, with a planner_task already projected to it. Run both
``verify_aurinko_oauth_lifecycle.py`` and ``verify_aurinko_event_crud.py``
first.

WEBHOOK PUBLIC URL — required. Aurinko cannot reach localhost. Run
something like ``ngrok http 8000`` and set
``NEXT_PUBLIC_API_BASE_URL=https://<your-tunnel>.ngrok-free.app`` in your
``.env`` BEFORE creating the connection (the URL is captured into the
subscription at create time and cannot be changed later without a fresh
subscription). The driver detects ``localhost`` in the configured base
URL and exits with a hint if you forgot.

Pair with ``cleanup_aurinko_lifecycle_state.py`` (shared across all three
Aurinko verifiers).

Scenario checkpoints
--------------------

    P0  — SEED:    planner exists, projected planner_task exists, public
                   webhook URL is configured (not localhost).
    P1  — TRIGGER: human or scripted external edit hits the connected
                   calendar's event (via Aurinko PATCH or Google UI).
    P2  — DELIVERY: ``calendar_idempotency_keys`` shows the delivery id
                    landed and was marked processed (200 ack).
    P3  — SNAPSHOT: planner_task ``external_conflict_status=pending_review``
                    AND ``external_title`` / ``external_start_date``
                    populated by the background fetch (NOT empty).
    P4  — NO-DUPES: re-poll for 30s; no second processed-delivery row
                    appears for the same change (proves Aurinko stopped
                    retrying after the 200 ack).

Usage
-----

    AURINKO_SANDBOX_ENABLED=1 \
        python testbed/verify_aurinko_webhook_roundtrip.py

    # Override the trigger to PATCH the event from this script (uses the
    # planner's own Aurinko token; bypasses the human step but still
    # exercises the delivery path):
    TRIGGER_VIA_AURINKO=1 AURINKO_SANDBOX_ENABLED=1 \
        python testbed/verify_aurinko_webhook_roundtrip.py
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from testbed.harness import PM_TOKEN_GOOD, Harness

logger = logging.getLogger(__name__)

DRIVER_NAME = "verify_aurinko_webhook_roundtrip"

PLANNER_EMAIL = "test_planner+aurinko_oauth@thespecialwedding.io"
PLANNER_PASSWORD = "AurinkoOAuth2026!"  # pragma: allowlist secret
PLAN_ID = os.getenv("AURINKO_OAUTH_PLAN_ID", "plan_signature")

INTERACTIVE = os.getenv("TESTBED_NON_INTERACTIVE", "0") not in ("1", "true", "yes")
SANDBOX_ENABLED = os.getenv("AURINKO_SANDBOX_ENABLED", "0") in ("1", "true", "yes")
TRIGGER_VIA_AURINKO = os.getenv("TRIGGER_VIA_AURINKO", "0") in ("1", "true", "yes")

POLL_TIMEOUT_SECONDS = 60
POLL_INTERVAL_SECONDS = 2
DUPE_WATCH_SECONDS = 30


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


def _resolve_account_token(h: Harness):
    from app.services.calendar_provider_service import calendar_provider_service

    row = h.mongo["calendar_connections"].find_one(
        {
            "user_email": PLANNER_EMAIL,
            "is_writable": True,
            "sync_enabled": True,
        }
    )
    if not row:
        return None, None, None
    token = calendar_provider_service._decrypt_token(
        row.get("aurinko_access_token_encrypted")
    )
    return token, str(row.get("aurinko_calendar_id")), row


def _trigger_external_edit_via_aurinko(
    account_token: str, calendar_id: str, event_id: str
) -> None:
    """Use Aurinko's PATCH endpoint directly to simulate an external edit.

    The point is to fire Aurinko's webhook delivery path without needing a
    human in front of Google's web UI. From Aurinko's perspective the edit
    came from "the API", which is identical to "any other client" for
    notification purposes.
    """
    from urllib.parse import quote

    base = os.getenv("AURINKO_API_BASE_URL", "https://api.aurinko.io/v1").rstrip("/")
    url = (
        f"{base}/calendars/{quote(calendar_id, safe='')}"
        f"/events/{quote(event_id, safe='')}"
    )
    response = httpx.patch(
        url,
        headers={
            "Authorization": f"Bearer {account_token}",
            "Content-Type": "application/json",
        },
        json={"description": f"webhook-roundtrip touch {time.time():.0f}"},
        timeout=20,
    )
    if not response.is_success:
        raise SystemExit(
            f"FAIL P1_TRIGGER_AURINKO_PATCH: status={response.status_code} "
            f"body={response.text[:200]}"
        )


def _wait_for_external_conflict(h: Harness, task_id: str) -> dict | None:
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        from bson import ObjectId

        try:
            oid = ObjectId(task_id)
        except Exception:
            return None
        task = h.mongo["planner_tasks"].find_one({"_id": oid})
        if (
            task
            and task.get("external_conflict_status") == "pending_review"
            and task.get("external_title")
        ):
            return task
        time.sleep(POLL_INTERVAL_SECONDS)
    return None


def _phase_dupes_silent(h: Harness, after: float) -> int:
    """No duplicate processed-delivery row appears within the dupe window.

    Returns the count of duplicates seen (0 = good).
    """
    deadline = time.monotonic() + DUPE_WATCH_SECONDS
    duplicate_count = 0
    while time.monotonic() < deadline:
        rows = list(
            h.mongo["calendar_idempotency_keys"].find(
                {
                    "scope_key": "aurinko_webhook",
                    "completed_at": {"$gte": after},
                }
            )
        )
        if len(rows) > 1:
            duplicate_count = len(rows) - 1
            break
        time.sleep(POLL_INTERVAL_SECONDS)
    return duplicate_count


def main() -> int:
    if not SANDBOX_ENABLED:
        sys.stderr.write("AURINKO_SANDBOX_ENABLED must be set to run this driver.\n")
        return 2

    h = Harness(driver_name=DRIVER_NAME)
    h.banner("VERIFY — Aurinko Webhook Round-trip")
    h.log.info(f"  Planner email : {PLANNER_EMAIL}")

    public_ok, detail_or_url = _public_webhook_url_ok()
    _checkpoint(h, "P0a_PUBLIC_URL", public_ok, detail_or_url)

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
    _checkpoint(h, "P0b_SEED", bool(planner_token), "planner login")

    token, calendar_id, _connection = _resolve_account_token(h)
    _checkpoint(
        h,
        "P0c_PRECONDITION",
        bool(token and calendar_id),
        "writable + sync_enabled connection required",
    )

    sync_row = h.mongo["calendar_event_syncs"].find_one(
        {"target_user_email": PLANNER_EMAIL, "external_event_id": {"$nin": [None, ""]}}
    )
    _checkpoint(
        h,
        "P0d_PROJECTED_TASK",
        sync_row is not None,
        "verify_aurinko_event_crud.py must have left a projected task",
    )
    assert sync_row is not None
    external_event_id = str(sync_row["external_event_id"])
    task_id = str(sync_row["task_id"])

    triggered_at = time.time()
    if TRIGGER_VIA_AURINKO:
        assert token and calendar_id
        _trigger_external_edit_via_aurinko(token, calendar_id, external_event_id)
    else:
        if not INTERACTIVE:
            _checkpoint(
                h,
                "P1_TRIGGER",
                False,
                "non-interactive mode requires TRIGGER_VIA_AURINKO=1",
            )
        print("\n" + "=" * 72)
        print("EXTERNAL EDIT — make a change to the projected event in Google")
        print("Calendar UI now (rename it, move it, change description), then")
        print("press ENTER to continue.")
        print("=" * 72)
        input("Press ENTER once the edit has been saved on Google's side: ")

    task = _wait_for_external_conflict(h, task_id)
    _checkpoint(
        h,
        "P3_SNAPSHOT",
        task is not None,
        f"task_id={task_id} polled_for={POLL_TIMEOUT_SECONDS}s",
    )

    if task is not None:
        _checkpoint(
            h,
            "P3a_FIELDS_POPULATED",
            bool(task.get("external_title"))
            and bool(task.get("external_last_modified_at")),
            f"title={task.get('external_title')!r}",
        )

    delivery_row = h.mongo["calendar_idempotency_keys"].find_one(
        {"scope_key": "aurinko_webhook", "response_status_code": 200}
    )
    _checkpoint(
        h,
        "P2_DELIVERY",
        delivery_row is not None,
        "no aurinko_webhook idempotency row found — webhook never reached us",
    )

    duplicate_count = _phase_dupes_silent(h, triggered_at)
    _checkpoint(
        h,
        "P4_NO_DUPES",
        duplicate_count == 0,
        f"duplicates_in_{DUPE_WATCH_SECONDS}s={duplicate_count}",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
