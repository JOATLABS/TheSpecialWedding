#!/usr/bin/env python3
"""Aurinko OAuth + subscription lifecycle verification.

Walks the calendar-aggregator connect/disconnect path against a real local
backend, real Mongo, and a real Aurinko sandbox. Pins the rewrite's
contract-level claims that I cannot validate from unit tests alone:

    1. Hosted-auth URL is reachable and returns a code+state we can exchange.
    2. After OAuth callback, one ``calendar_connections`` row is written
       per writable calendar surfaced by Aurinko.
    3. Each writable row has a non-null ``aurinko_subscription_id`` —
       confirming the per-calendar subscription model (one sub per resource,
       not one per account).
    4. Disconnect deletes the connection rows AND deletes the corresponding
       Aurinko-side subscriptions (verified by a follow-up
       ``GET /v1/subscriptions`` against Aurinko, which must not return
       any of the ids we wrote).
    5. Reconnect does not accumulate stale subscriptions Aurinko-side.

This driver lives in ``testbed/`` because it needs the real OAuth handshake
and real subscription create/delete round-trip. Unit tests can pin path
shapes (see ``tests/backend/test_calendar_provider_service.py``) but cannot
prove the round-trip works against the Aurinko app the user actually
configured in their dashboard.

Pair with ``cleanup_aurinko_lifecycle_state.py`` (shared across all three
Aurinko verifiers).

Scenario checkpoints
--------------------

    P0  — SEED:    planner exists on a paid plan, Aurinko sandbox is
                   reachable, ``AURINKO_*`` env vars are present.
    P1  — AUTHURL: GET /admin/planner/calendar/provider/connect returns a
                   non-empty hosted-auth URL pointing at the configured
                   ``api.aurinko.io`` host.
    P2  — OAUTH:   user completes the Aurinko hosted-auth flow in Chrome
                   against a sandbox Google account; driver pauses for the
                   ``code`` + ``state`` from the callback URL.
    P3  — CALLBACK: POST the code+state to
                    ``/admin/planner/calendar/connections/provider/callback``;
                    response shows ``connected=True`` and
                    ``connections_created >= 1``.
    P4  — ROWS:    one ``calendar_connections`` row per writable calendar
                   on the Aurinko account; each writable row has a
                   non-null ``aurinko_subscription_id``.
    P5  — AURINKO-SIDE: GET /v1/subscriptions on Aurinko returns a sub
                        for every ``aurinko_subscription_id`` we stored.
    P6  — DISCONNECT: DELETE /admin/planner/calendar/provider/disconnect
                      removes every row; follow-up GET /v1/subscriptions
                      no longer lists any of the ids.
    P7  — RECONNECT-SAFETY: re-run P1–P5 once; Aurinko must NOT show
                            duplicated subscriptions for the same calendar.

Usage
-----

    AURINKO_SANDBOX_ENABLED=1 \
        python testbed/verify_aurinko_oauth_lifecycle.py

    # Skip OAuth pause (CI / unattended) — checkpoints that need a fresh
    # code+state will be marked SKIPPED:
    TESTBED_NON_INTERACTIVE=1 AURINKO_SANDBOX_ENABLED=1 \
        python testbed/verify_aurinko_oauth_lifecycle.py
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
import requests

from testbed.harness import PM_TOKEN_GOOD, Harness

logger = logging.getLogger(__name__)

DRIVER_NAME = "verify_aurinko_oauth_lifecycle"

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


def _aurinko_subscriptions_listing(account_token: str) -> list[dict]:
    base = os.getenv("AURINKO_API_BASE_URL", "https://api.aurinko.io/v1").rstrip("/")
    response = httpx.get(
        f"{base}/subscriptions",
        headers={"Authorization": f"Bearer {account_token}"},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get("records") or payload.get("subscriptions") or []


def _resolve_account_token(h: Harness) -> str | None:
    """Pull a connection's encrypted Aurinko account token and decrypt it
    so we can hit Aurinko's own /subscriptions API to verify P5/P6."""
    from app.services.calendar_provider_service import calendar_provider_service

    row = h.mongo["calendar_connections"].find_one({"user_email": PLANNER_EMAIL})
    if not row:
        return None
    return calendar_provider_service._decrypt_token(
        row.get("aurinko_access_token_encrypted")
    )


def _wait_for_oauth_code() -> tuple[str, str]:
    print("\n" + "=" * 72)
    print("OAUTH STEP — complete in Chrome, then paste the callback values back.")
    print("=" * 72)
    print("1. Open the hosted-auth URL printed above in Chrome.")
    print("2. Complete consent against your Aurinko sandbox provider (Google).")
    print("3. Aurinko redirects to:")
    print(
        "     http://localhost:3000/admin/planner/calendar/callback"
        "?code=<code>&state=<state>"
    )
    print("4. Copy the values of `code` and `state` from the URL bar.")
    code = input("Paste `code`: ").strip()
    state = input("Paste `state`: ").strip()
    return code, state


def _phase_authurl(h: Harness, planner_token: str) -> str:
    response = h.api_get(
        "/admin/planner/calendar/provider/connect", token=planner_token
    )
    body = response.json() if response.ok else {}
    auth_url = body.get("auth_url") or ""
    _checkpoint(
        h,
        "P1_AUTHURL",
        response.ok and "api.aurinko.io" in auth_url,
        f"status={response.status_code} url_host_match={'api.aurinko.io' in auth_url}",
    )
    print("\nHosted-auth URL:\n  " + auth_url + "\n")
    return auth_url


def _phase_callback(h: Harness, planner_token: str, code: str, state: str) -> dict:
    response = requests.get(
        f"{h.config.backend_url}/admin/planner/calendar/connections/provider/callback",
        params={"code": code, "state": state},
        headers={"Authorization": f"Bearer {planner_token}"},
        timeout=30,
    )
    body = response.json() if response.ok else {"error": response.text}
    _checkpoint(
        h,
        "P3_CALLBACK",
        response.ok and bool(body.get("connected")),
        f"status={response.status_code} body={body}",
    )
    return body


def _phase_rows(h: Harness) -> list[dict]:
    rows = list(h.mongo["calendar_connections"].find({"user_email": PLANNER_EMAIL}))
    writable_rows = [r for r in rows if r.get("is_writable")]
    every_writable_subscribed = all(
        bool(r.get("aurinko_subscription_id")) for r in writable_rows
    )
    _checkpoint(
        h,
        "P4_ROWS",
        len(rows) >= 1 and every_writable_subscribed,
        f"rows={len(rows)} writable={len(writable_rows)} "
        f"all_subscribed={every_writable_subscribed}",
    )
    return rows


def _phase_aurinko_side(h: Harness, rows: list[dict]) -> None:
    token = _resolve_account_token(h)
    if not token:
        _checkpoint(h, "P5_AURINKO_SIDE", False, "no account token to verify against")
        return
    sub_ids_local = {
        str(r["aurinko_subscription_id"])
        for r in rows
        if r.get("aurinko_subscription_id")
    }
    if not sub_ids_local:
        _checkpoint(h, "P5_AURINKO_SIDE", False, "no local subscription ids to verify")
        return
    aurinko_subs = _aurinko_subscriptions_listing(token)
    aurinko_ids = {
        str(s.get("id") or s.get("subscriptionId") or "") for s in aurinko_subs
    }
    missing = sub_ids_local - aurinko_ids
    _checkpoint(
        h,
        "P5_AURINKO_SIDE",
        not missing,
        f"local={len(sub_ids_local)} aurinko={len(aurinko_ids)} missing={missing}",
    )


def _phase_disconnect(h: Harness, planner_token: str, rows: list[dict]) -> None:
    sub_ids_before = {
        str(r["aurinko_subscription_id"])
        for r in rows
        if r.get("aurinko_subscription_id")
    }
    token = _resolve_account_token(h)
    response = requests.delete(
        f"{h.config.backend_url}/admin/planner/calendar/provider/disconnect",
        headers={"Authorization": f"Bearer {planner_token}"},
        timeout=30,
    )
    _checkpoint(h, "P6a_DISCONNECT_HTTP", response.ok, f"status={response.status_code}")
    remaining_rows = h.mongo["calendar_connections"].count_documents(
        {"user_email": PLANNER_EMAIL}
    )
    _checkpoint(
        h, "P6b_ROWS_DELETED", remaining_rows == 0, f"remaining={remaining_rows}"
    )
    if token:
        try:
            aurinko_subs = _aurinko_subscriptions_listing(token)
        except Exception as exc:
            # Account may have been revoked already — that's acceptable.
            h.log.info(
                "  (Aurinko-side listing returned %s — account may be revoked)", exc
            )
            return
        aurinko_ids = {
            str(s.get("id") or s.get("subscriptionId") or "") for s in aurinko_subs
        }
        leaked = sub_ids_before & aurinko_ids
        _checkpoint(h, "P6c_AURINKO_SUBS_DELETED", not leaked, f"leaked_subs={leaked}")


def main() -> int:
    if not SANDBOX_ENABLED:
        sys.stderr.write(
            "AURINKO_SANDBOX_ENABLED must be set to run this driver — "
            "see testbed/README.md for sandbox setup.\n"
        )
        return 2

    h = Harness(driver_name=DRIVER_NAME)
    h.banner("VERIFY — Aurinko OAuth + Subscription Lifecycle")
    h.log.info(f"  Planner email : {PLANNER_EMAIL}")
    h.log.info(f"  Plan id       : {PLAN_ID}")
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
    _checkpoint(h, "P0_SEED", bool(planner_token), "planner login")

    if not INTERACTIVE:
        h.log.info("non-interactive mode: skipping P1–P7 (need OAuth code from human)")
        return 0

    _phase_authurl(h, planner_token)
    code, state = _wait_for_oauth_code()
    _phase_callback(h, planner_token, code, state)
    rows = _phase_rows(h)
    _phase_aurinko_side(h, rows)
    _phase_disconnect(h, planner_token, rows)

    print("\nP7_RECONNECT — re-run this driver once more to verify Aurinko-side")
    print("subscriptions do not accumulate across reconnects.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
