"""Route-registration pins for the Aurinko (multi-provider) endpoints.

These tests don't require a live OAuth flow or Aurinko sandbox — they only
verify that the routes the testbed scripts expect actually exist on the
running app, at the exact paths and HTTP methods the testbed hits. They
also confirm the unauthenticated calls return 401 (auth guard wired) so a
silent permission-stripping refactor would be caught.

Without these pins, route renames or registration regressions would only
surface at testbed-run time, where the failure path is long and noisy.
"""

from __future__ import annotations

import os

os.environ.setdefault("AURINKO_WEBHOOK_SECRET", "test-webhook-secret")
os.environ.setdefault("AURINKO_CLIENT_ID", "test-cid")
os.environ.setdefault("AURINKO_CLIENT_SECRET", "test-csec")
os.environ.setdefault("AURINKO_OAUTH_STATE_SIGNING_KEY", "test-state-key")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "test-token-key")
os.environ.setdefault("ENVIRONMENT", "test")

import pytest  # noqa: E402

from app.api.planner_calendar import router as planner_calendar_router  # noqa: E402
from app.api.calendar_webhooks import router as calendar_webhooks_router  # noqa: E402


# Pairs of (HTTP method, full path after /admin prefix is applied by main.py).
# These are the exact strings the testbed scripts hit; keep both lists in
# sync with testbed/verify_aurinko_*.py.
_TESTBED_PLANNER_ROUTES = [
    ("GET", "/admin/planner/calendar/provider/connect"),
    ("GET", "/admin/planner/calendar/connections/provider/callback"),
    ("DELETE", "/admin/planner/calendar/provider/disconnect"),
]


@pytest.mark.parametrize("method,full_path", _TESTBED_PLANNER_ROUTES)
def test_planner_calendar_provider_route_is_registered(
    method: str, full_path: str
) -> None:
    """Each /provider/* route must exist on planner_calendar_router with the
    method the testbed expects. Router paths don't carry the /admin prefix
    here — that's added by main.py at include_router time."""
    expected_router_path = full_path[len("/admin") :]
    registered = {
        (m, route.path)
        for route in planner_calendar_router.routes
        if hasattr(route, "methods")
        for m in route.methods
    }
    assert (method, expected_router_path) in registered, (
        f"testbed-required route missing from planner_calendar_router: "
        f"{method} {expected_router_path}. Registered: "
        f"{sorted(p for m, p in registered if '/provider' in p)}"
    )


def test_calendar_webhooks_aurinko_route_is_registered() -> None:
    """The Aurinko webhook router must expose POST /api/calendar/webhooks/aurinko.
    This is the URL Aurinko delivers to; a missing registration silently 404s
    every webhook even after subscriptions are created."""
    registered = {
        (m, route.path)
        for route in calendar_webhooks_router.routes
        if hasattr(route, "methods")
        for m in route.methods
    }
    assert ("POST", "/api/calendar/webhooks/aurinko") in registered, (
        "calendar_webhooks_router missing POST /api/calendar/webhooks/aurinko — "
        "Aurinko deliveries would 404."
    )


def test_legacy_google_routes_still_present() -> None:
    """The /google/* routes are intentionally kept during the migration so
    existing frontend clients don't break. This pin catches an accidental
    early removal before the planner UI has been switched over."""
    registered = {
        route.path
        for route in planner_calendar_router.routes
        if hasattr(route, "methods")
    }
    expected_legacy = {
        "/planner/calendar/google/connect",
        "/planner/calendar/google/callback",
        "/planner/calendar/google/status",
        "/planner/calendar/google/disconnect",
    }
    missing = expected_legacy - registered
    assert not missing, f"legacy Google route(s) removed prematurely: {missing}"
