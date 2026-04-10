#!/usr/bin/env python3
"""Post-deploy smoke verification for Coolify staging and production."""

from __future__ import annotations

import argparse
import sys
import time
from typing import Optional

import requests
import urllib3

DEFAULT_TIMEOUT = 15


def log_step(message: str) -> None:
    print(f"[verify] {message}", flush=True)


def build_auth_headers(token: Optional[str]) -> dict[str, str]:
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def ensure_response_ok(response: requests.Response, label: str) -> None:
    if response.ok:
        return

    body = response.text[:400].strip()
    raise RuntimeError(f"{label} failed with HTTP {response.status_code}: {body}")


def request(
    session: requests.Session, method: str, url: str, **kwargs
) -> requests.Response:
    return session.request(method, url, timeout=DEFAULT_TIMEOUT, **kwargs)


def wait_for_http_ok(
    session: requests.Session,
    url: str,
    label: str,
    attempts: int = 20,
    delay: int = 15,
) -> None:
    last_error: Optional[str] = None

    for attempt in range(1, attempts + 1):
        try:
            response = request(session, "GET", url)
            if response.ok:
                log_step(f"{label} is healthy on attempt {attempt}")
                return
            body = response.text[:200].strip().replace("\n", " ")
            last_error = f"HTTP {response.status_code}: {body}"
        except requests.RequestException as exc:
            last_error = str(exc)

        log_step(f"{label} not ready on attempt {attempt}/{attempts}: {last_error}")
        time.sleep(delay)

    raise RuntimeError(f"{label} never became healthy: {last_error}")


def verify_public_route(
    session: requests.Session, frontend_base: str, slug: str
) -> None:
    url = f"{frontend_base.rstrip('/')}/{slug.lstrip('/')}"
    response = request(session, "GET", url)
    ensure_response_ok(response, f"public wedding route {url}")
    log_step(f"Public wedding route OK: {url}")


def verify_health(session: requests.Session, api_base: str, frontend_base: str) -> None:
    wait_for_http_ok(session, f"{frontend_base.rstrip('/')}/", "frontend")
    wait_for_http_ok(
        session, f"{api_base.rstrip('/')}/health/livez", "backend liveness"
    )

    ready_response = request(session, "GET", f"{api_base.rstrip('/')}/health/readyz")
    ensure_response_ok(ready_response, "backend readiness")
    log_step("Backend readiness OK")


def login_admin(
    session: requests.Session, api_base: str, email: str, password: str
) -> str:
    response = request(
        session,
        "POST",
        f"{api_base.rstrip('/')}/admin/token",
        json={"email": email, "password": password},
    )
    ensure_response_ok(response, "admin login")

    payload = response.json()
    token = payload.get("access_token")
    if not token:
        raise RuntimeError("admin login succeeded but no access_token was returned")

    headers = build_auth_headers(token)

    profile_response = request(
        session,
        "GET",
        f"{api_base.rstrip('/')}/admin/profile",
        headers=headers,
    )
    ensure_response_ok(profile_response, "admin profile")

    weddings_response = request(
        session,
        "GET",
        f"{api_base.rstrip('/')}/admin/planner/weddings?page=1&limit=1",
        headers=headers,
    )
    ensure_response_ok(weddings_response, "planner weddings read")

    log_step("Admin login and planner read checks passed")
    return token


def verify_sse(
    session: requests.Session, api_base: str, token: str, timeout_seconds: int = 25
) -> None:
    response = session.get(
        f"{api_base.rstrip('/')}/admin/notifications/stream",
        headers={
            **build_auth_headers(token),
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
        },
        timeout=(DEFAULT_TIMEOUT, timeout_seconds + 5),
        stream=True,
    )
    ensure_response_ok(response, "notification SSE connect")

    content_type = response.headers.get("content-type", "")
    if "text/event-stream" not in content_type:
        raise RuntimeError(
            f"notification SSE returned unexpected content type: {content_type}"
        )

    deadline = time.monotonic() + timeout_seconds
    saw_notification_event = False

    try:
        for raw_line in response.iter_lines(decode_unicode=True):
            if raw_line is None:
                continue

            line = raw_line.strip()
            if line.startswith("event: notification-count"):
                saw_notification_event = True
                continue

            if saw_notification_event and line.startswith("data:"):
                log_step("Notification SSE emitted initial notification-count event")
                return

            if time.monotonic() > deadline:
                break
    finally:
        response.close()

    raise RuntimeError(
        "notification SSE did not emit an initial notification-count event"
    )


def login_couple(
    session: requests.Session, api_base: str, email: str, password: str
) -> str:
    response = request(
        session,
        "POST",
        f"{api_base.rstrip('/')}/couple/login",
        json={"email": email, "password": password},
    )
    ensure_response_ok(response, "couple login")

    payload = response.json()
    token = payload.get("access_token")
    if not token:
        raise RuntimeError("couple login succeeded but no access_token was returned")

    headers = build_auth_headers(token)

    profile_response = request(
        session,
        "GET",
        f"{api_base.rstrip('/')}/couple/profile",
        headers=headers,
    )
    ensure_response_ok(profile_response, "couple profile")

    dashboard_response = request(
        session,
        "GET",
        f"{api_base.rstrip('/')}/couple/portal/dashboard",
        headers=headers,
    )
    ensure_response_ok(dashboard_response, "couple dashboard")

    log_step("Couple login and dashboard checks passed")
    return token


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify a deployed frontend/backend environment"
    )
    parser.add_argument("--frontend-base", required=True)
    parser.add_argument("--api-base", required=True)
    parser.add_argument("--admin-email", required=True)
    parser.add_argument("--admin-password", required=True)
    parser.add_argument("--couple-email")
    parser.add_argument("--couple-password")
    parser.add_argument("--public-slug")
    parser.add_argument("--skip-sse", action="store_true")
    parser.add_argument("--allow-insecure-tls", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    session = requests.Session()
    if args.allow_insecure_tls:
        session.verify = False
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        log_step("TLS certificate verification disabled for this environment")

    verify_health(session, args.api_base, args.frontend_base)

    if args.public_slug:
        verify_public_route(session, args.frontend_base, args.public_slug)

    admin_session = requests.Session()
    admin_session.verify = session.verify
    admin_token = login_admin(
        admin_session, args.api_base, args.admin_email, args.admin_password
    )

    if not args.skip_sse:
        verify_sse(admin_session, args.api_base, admin_token)

    if args.couple_email or args.couple_password:
        if not (args.couple_email and args.couple_password):
            raise RuntimeError(
                "Both --couple-email and --couple-password are required together"
            )

        couple_session = requests.Session()
        couple_session.verify = session.verify
        login_couple(
            couple_session, args.api_base, args.couple_email, args.couple_password
        )

    log_step("Environment verification passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"[verify] ERROR: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1)
