#!/usr/bin/env python3
"""Aurinko contacts mirror lifecycle verification.

Pre-condition: run the OAuth lifecycle driver and enable contact sync on at
least one connection. This driver verifies the planner vendor mutation hooks:

    P0 — planner + contact-sync-enabled connection exist
    P1 — vendor create mirrors to Aurinko Contacts
    P2 — vendor edit updates the Aurinko contact
    P3 — vendor delete removes the Aurinko contact

Usage:

    AURINKO_SANDBOX_ENABLED=1 python testbed/verify_aurinko_contacts_lifecycle.py
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
import requests

from testbed.harness import PM_TOKEN_GOOD, Harness

DRIVER_NAME = "verify_aurinko_contacts_lifecycle"

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
        {"user_email": PLANNER_EMAIL, "contact_sync_enabled": True}
    )


def _account_token(connection: dict) -> str | None:
    from app.services.calendar_provider_service import calendar_provider_service

    return calendar_provider_service._decrypt_token(
        connection.get("aurinko_access_token_encrypted")
    )


def _aurinko_get_contact(account_token: str, contact_id: str) -> httpx.Response:
    base = os.getenv("AURINKO_API_BASE_URL", "https://api.aurinko.io/v1").rstrip("/")
    url = f"{base}/contacts/{quote(contact_id, safe='')}"
    return httpx.get(
        url, headers={"Authorization": f"Bearer {account_token}"}, timeout=20
    )


def _create_vendor(h: Harness, planner_token: str) -> str:
    suffix = int(datetime.now(UTC).timestamp())
    payload = {
        "business_name": f"Aurinko Florals {suffix}",
        "contact_name": "Contact Mirror",
        "email": f"aurinko-contact-{suffix}@example.com",
        "phone": "+15551234567",
        "website": "https://example.com",
        "service_category": "florist",
        "service_description": "Lifecycle verification vendor",
    }
    response = requests.post(
        f"{h.config.backend_url}/admin/directory",
        json=payload,
        headers={"Authorization": f"Bearer {planner_token}"},
        timeout=30,
    )
    body = response.json() if response.ok else {"error": response.text}
    vendor_id = str(body.get("_id") or body.get("id") or "")
    _checkpoint(h, "P1a_CREATE_VENDOR_HTTP", response.ok and bool(vendor_id), str(body))
    return vendor_id


def _update_vendor(h: Harness, planner_token: str, vendor_id: str) -> str:
    new_name = f"Updated Mirror {int(datetime.now(UTC).timestamp())}"
    response = requests.put(
        f"{h.config.backend_url}/admin/directory/{vendor_id}",
        json={"contact_name": new_name, "phone": "+15557654321"},
        headers={"Authorization": f"Bearer {planner_token}"},
        timeout=30,
    )
    _checkpoint(
        h, "P2a_UPDATE_VENDOR_HTTP", response.ok, f"status={response.status_code}"
    )
    return new_name


def _delete_vendor(h: Harness, planner_token: str, vendor_id: str) -> None:
    response = requests.delete(
        f"{h.config.backend_url}/admin/directory/{vendor_id}",
        headers={"Authorization": f"Bearer {planner_token}"},
        timeout=30,
    )
    _checkpoint(
        h, "P3a_DELETE_VENDOR_HTTP", response.ok, f"status={response.status_code}"
    )


def _contact_sync_row(h: Harness, vendor_id: str) -> dict:
    row = h.mongo["contact_sync_records"].find_one(
        {"source_type": "vendor", "source_id": vendor_id}
    )
    _checkpoint(h, "P1b_SYNC_ROW", row is not None, f"vendor_id={vendor_id}")
    assert row is not None
    return row


def main() -> int:
    if not SANDBOX_ENABLED:
        sys.stderr.write("AURINKO_SANDBOX_ENABLED must be set to run this driver.\n")
        return 2

    h = Harness(driver_name=DRIVER_NAME)
    h.banner("VERIFY — Aurinko Contacts Lifecycle")
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
        "contact_sync_enabled connection required",
    )
    assert connection is not None
    account_token = _account_token(connection)
    _checkpoint(h, "P0c_TOKEN", bool(account_token), "decryptable account token")
    assert account_token is not None

    vendor_id = _create_vendor(h, planner_token)
    sync_row = _contact_sync_row(h, vendor_id)
    contact_id = str(sync_row["aurinko_contact_id"])
    probe = _aurinko_get_contact(account_token, contact_id)
    body = probe.json() if probe.status_code == 200 else {}
    _checkpoint(
        h,
        "P1c_AURINKO_PRESENT",
        probe.status_code == 200 and "TheSpecialWedding" in body.get("keywords", []),
        f"status={probe.status_code} keywords={body.get('keywords')}",
    )

    expected_name = _update_vendor(h, planner_token, vendor_id)
    probe = _aurinko_get_contact(account_token, contact_id)
    body = probe.json() if probe.status_code == 200 else {}
    full_name = " ".join(
        str(body.get(key) or "").strip() for key in ("givenName", "surname")
    ).strip()
    _checkpoint(
        h,
        "P2b_AURINKO_UPDATED",
        probe.status_code == 200 and full_name == expected_name,
        f"status={probe.status_code} name={full_name}",
    )

    _delete_vendor(h, planner_token, vendor_id)
    probe = _aurinko_get_contact(account_token, contact_id)
    _checkpoint(
        h,
        "P3b_AURINKO_DELETED",
        probe.status_code in (404, 410),
        f"status={probe.status_code}",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
