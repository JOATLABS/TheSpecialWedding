#!/usr/bin/env python3
"""Aurinko task-sync lifecycle verification.

Pre-condition: run the OAuth lifecycle driver and enable task sync on at least
one writable connection. This driver then verifies:

    P0 — planner + task-sync-enabled connection exist
    P1 — planner task create mirrors to Aurinko Tasks
    P2 — planner task edit updates the Aurinko task
    P3 — Aurinko-side edit applies back to planner_tasks
    P4 — planner task delete removes the Aurinko task

Usage:

    AURINKO_SANDBOX_ENABLED=1 python testbed/verify_aurinko_tasks_lifecycle.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
import requests
from bson import ObjectId

from testbed.harness import PM_TOKEN_GOOD, Harness

DRIVER_NAME = "verify_aurinko_tasks_lifecycle"

PLANNER_EMAIL = "test_planner+aurinko_oauth@thespecialwedding.io"
PLANNER_PASSWORD = "AurinkoOAuth2026!"  # pragma: allowlist secret
PLAN_ID = os.getenv("AURINKO_OAUTH_PLAN_ID", "plan_signature")

SANDBOX_ENABLED = os.getenv("AURINKO_SANDBOX_ENABLED", "0") in ("1", "true", "yes")


def _checkpoint(h: Harness, name: str, ok: bool, detail: str = "") -> None:
    marker = "PASS" if ok else "FAIL"
    h.log.info("CHECKPOINT %s [%s] %s", name, marker, detail)
    if not ok:
        raise SystemExit(f"FAIL {name}: {detail}")


def _connection_for_planner(h: Harness) -> dict | None:
    return h.mongo["calendar_connections"].find_one(
        {
            "user_email": PLANNER_EMAIL,
            "task_sync_enabled": True,
            "task_sync_tasklist_id": {"$nin": [None, ""]},
        }
    )


def _account_token(connection: dict) -> str | None:
    from app.services.calendar_provider_service import calendar_provider_service

    return calendar_provider_service._decrypt_token(
        connection.get("aurinko_access_token_encrypted")
    )


def _aurinko_get_task(
    account_token: str, tasklist_id: str, task_id: str
) -> httpx.Response:
    base = os.getenv("AURINKO_API_BASE_URL", "https://api.aurinko.io/v1").rstrip("/")
    url = (
        f"{base}/tasklists/{quote(tasklist_id, safe='')}"
        f"/tasks/{quote(task_id, safe='')}"
    )
    return httpx.get(
        url, headers={"Authorization": f"Bearer {account_token}"}, timeout=20
    )


def _aurinko_patch_task(
    account_token: str, tasklist_id: str, task_id: str, body: dict
) -> dict:
    base = os.getenv("AURINKO_API_BASE_URL", "https://api.aurinko.io/v1").rstrip("/")
    url = (
        f"{base}/tasklists/{quote(tasklist_id, safe='')}"
        f"/tasks/{quote(task_id, safe='')}"
    )
    response = httpx.patch(
        url,
        headers={"Authorization": f"Bearer {account_token}"},
        json=body,
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def _create_planner_task(h: Harness, planner_token: str) -> str:
    start = datetime.now(UTC) + timedelta(days=2)
    payload = {
        "title": f"Aurinko-task-{int(start.timestamp())}",
        "category": "other",
        "priority": "medium",
        "status": "pending",
        "start_date": start.isoformat(),
        "end_date": start.isoformat(),
        "all_day": False,
        "external_sync_requested": True,
        "schedule_item_type": "task",
        "timezone": "UTC",
    }
    response = requests.post(
        f"{h.config.backend_url}/admin/planner/calendar/tasks",
        json=payload,
        headers={"Authorization": f"Bearer {planner_token}"},
        timeout=30,
    )
    body = response.json() if response.ok else {"error": response.text}
    task_id = str(body.get("id") or "")
    _checkpoint(h, "P1a_CREATE_HTTP", response.ok and bool(task_id), f"body={body}")
    return task_id


def _task_sync_row(h: Harness, task_id: str) -> dict:
    row = h.mongo["task_sync_records"].find_one({"planner_task_id": task_id})
    _checkpoint(h, "P1b_SYNC_ROW", row is not None, f"task_id={task_id}")
    assert row is not None
    return row


def _update_planner_task(h: Harness, planner_token: str, task_id: str) -> str:
    new_title = f"Aurinko-task-updated-{int(datetime.now(UTC).timestamp())}"
    response = requests.patch(
        f"{h.config.backend_url}/admin/planner/calendar/tasks/{task_id}",
        json={"title": new_title, "status": "in_progress"},
        headers={"Authorization": f"Bearer {planner_token}"},
        timeout=30,
    )
    _checkpoint(h, "P2a_UPDATE_HTTP", response.ok, f"status={response.status_code}")
    return new_title


def _delete_planner_task(h: Harness, planner_token: str, task_id: str) -> None:
    response = requests.delete(
        f"{h.config.backend_url}/admin/planner/calendar/tasks/{task_id}",
        headers={"Authorization": f"Bearer {planner_token}"},
        timeout=30,
    )
    _checkpoint(h, "P4a_DELETE_HTTP", response.ok, f"status={response.status_code}")


async def _apply_external_edit(
    connection_id: str, aurinko_task_id: str, snapshot: dict
) -> None:
    from app.services.aurinko_tasks_sync_service import aurinko_tasks_sync_service

    await aurinko_tasks_sync_service.apply_external_task_change(
        connection_id=connection_id,
        aurinko_task_id=aurinko_task_id,
        change_type="updated",
        snapshot=snapshot,
    )


def main() -> int:
    if not SANDBOX_ENABLED:
        sys.stderr.write("AURINKO_SANDBOX_ENABLED must be set to run this driver.\n")
        return 2

    h = Harness(driver_name=DRIVER_NAME)
    h.banner("VERIFY — Aurinko Tasks Lifecycle")
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

    connection = _connection_for_planner(h)
    _checkpoint(
        h,
        "P0b_PRECONDITION",
        connection is not None,
        "task_sync_enabled connection required",
    )
    assert connection is not None
    account_token = _account_token(connection)
    _checkpoint(h, "P0c_TOKEN", bool(account_token), "decryptable account token")
    assert account_token is not None
    tasklist_id = str(connection["task_sync_tasklist_id"])

    task_id = _create_planner_task(h, planner_token)
    sync_row = _task_sync_row(h, task_id)
    aurinko_task_id = str(sync_row["aurinko_task_id"])
    probe = _aurinko_get_task(account_token, tasklist_id, aurinko_task_id)
    _checkpoint(
        h, "P1c_AURINKO_PRESENT", probe.status_code == 200, str(probe.status_code)
    )

    expected_title = _update_planner_task(h, planner_token, task_id)
    probe = _aurinko_get_task(account_token, tasklist_id, aurinko_task_id)
    body = probe.json() if probe.status_code == 200 else {}
    _checkpoint(
        h,
        "P2b_AURINKO_UPDATED",
        probe.status_code == 200 and body.get("title") == expected_title,
        f"status={probe.status_code} title={body.get('title')}",
    )

    external_title = f"Aurinko-external-{int(datetime.now(UTC).timestamp())}"
    snapshot = _aurinko_patch_task(
        account_token,
        tasklist_id,
        aurinko_task_id,
        {"title": external_title, "status": "completed"},
    )
    asyncio.run(_apply_external_edit(str(connection["_id"]), aurinko_task_id, snapshot))
    local = h.mongo["planner_tasks"].find_one({"_id": ObjectId(task_id)})
    _checkpoint(
        h,
        "P3_PLANNER_UPDATED",
        bool(local and local.get("title") == external_title),
        f"title={(local or {}).get('title')}",
    )

    _delete_planner_task(h, planner_token, task_id)
    probe = _aurinko_get_task(account_token, tasklist_id, aurinko_task_id)
    _checkpoint(
        h,
        "P4b_AURINKO_DELETED",
        probe.status_code in (404, 410),
        f"status={probe.status_code}",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
