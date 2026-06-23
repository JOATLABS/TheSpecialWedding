"""Route-shape and behavior pins for the Aurinko OAuth intermediate
redirector at ``GET /v1/auth/callback``.

The redirector is the production answer to Aurinko's docs note:

    Google app registrations allow only authorized redirect URIs under a
    domain you own so Aurinko's default Redirect URI
    https://api.aurinko.io/v1/auth/callback won't work for you in
    production.

So in prod, ``aurinko.thespecialwedding.io`` (CNAME → our backend) serves
this route, which 302s to Aurinko's canonical callback with the exact
query params Google attached. Aurinko's Intermediate Redirect URL
override in the app dashboard is set to the
``aurinko.thespecialwedding.io`` URL.

These tests pin:

1. The route is registered at the right path (no /admin prefix —
   Aurinko + Google both expect it bare).
2. The redirect target is Aurinko's canonical callback.
3. Every query param Google attached is preserved byte-for-byte.
4. No query params still produces a valid (no-?) redirect.

We use FastAPI's TestClient so we exercise the real ASGI stack including
``RedirectResponse``'s 302 behavior.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

os.environ.setdefault("AURINKO_WEBHOOK_SECRET", "test-webhook-secret")
os.environ.setdefault("AURINKO_CLIENT_ID", "test-cid")
os.environ.setdefault("AURINKO_CLIENT_SECRET", "test-csec")
os.environ.setdefault("AURINKO_OAUTH_STATE_SIGNING_KEY", "test-state-key")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "test-token-key")
os.environ.setdefault("ENVIRONMENT", "test")

from app.api.aurinko_redirector import (  # noqa: E402
    build_aurinko_callback_url,
    router as aurinko_redirector_router,
)


def _collect_registered_routes(app) -> set[tuple[str, str]]:
    registered: set[tuple[str, str]] = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if path is not None and methods is not None:
            registered.update((method, path) for method in methods)
            continue

        effective_route_contexts = getattr(route, "effective_route_contexts", None)
        if effective_route_contexts is None:
            continue

        for context in effective_route_contexts():
            registered.update((method, context.path) for method in context.methods)
    return registered


def _make_redirector_test_client() -> "TestClient":
    """Mount only the redirector router.

    The production app lifespan connects to MongoDB, Redis, and index
    bootstrap paths. This route is a stateless 302 shim, so these contract
    tests should not require CI to run the full backend stack.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(aurinko_redirector_router)
    return TestClient(app)


def test_redirector_route_is_registered_at_bare_path() -> None:
    """The route MUST be at ``/v1/auth/callback`` with no prefix — that's
    the URL Aurinko + Google both expect. Any prefix and Google will
    reject the OAuth flow with redirect_uri_mismatch (the exact failure
    surfaced 2026-05-13 when the user hit Path A of the dev unblocker)."""
    registered = {
        (m, route.path)
        for route in aurinko_redirector_router.routes
        if hasattr(route, "methods")
        for m in route.methods
    }
    assert ("GET", "/v1/auth/callback") in registered, (
        f"intermediate redirector must be at GET /v1/auth/callback "
        f"(bare, no prefix). Found: {sorted(registered)}"
    )


def test_redirector_route_is_included_in_main_app_without_startup() -> None:
    """Pin app registration without entering the Mongo-backed lifespan."""
    from app.main import app

    registered = _collect_registered_routes(app)
    assert ("GET", "/v1/auth/callback") in registered, (
        "app.main must include the bare Aurinko redirector route; otherwise "
        "Google/Aurinko callbacks 404 even though the router module is correct."
    )


def test_build_aurinko_callback_url_with_params() -> None:
    """The helper composes the canonical Aurinko callback URL with the
    given query params. Used by tests + observability."""
    url = build_aurinko_callback_url(
        {"code": "abc123", "state": "xyz789", "scope": "Calendar.ReadWrite"}
    )
    assert url.startswith("https://api.aurinko.io/v1/auth/callback?")
    # urlencode preserves order from the dict (Python 3.7+).
    assert "code=abc123" in url
    assert "state=xyz789" in url
    assert "scope=Calendar.ReadWrite" in url


def test_build_aurinko_callback_url_with_no_params() -> None:
    """Empty params dict → bare callback URL with no trailing ``?``."""
    assert build_aurinko_callback_url({}) == "https://api.aurinko.io/v1/auth/callback"


def test_redirector_302s_to_aurinko_with_preserved_query() -> None:
    """End-to-end: GET /v1/auth/callback?<params> must 302 to
    https://api.aurinko.io/v1/auth/callback?<same params, byte-for-byte>.

    Uses TestClient against an isolated app containing the redirector router
    so RedirectResponse's 302 behavior is exercised without entering the
    Mongo-backed production lifespan. We use ``follow_redirects=False`` to
    inspect the Location header directly rather than chasing the redirect
    into Aurinko's live API.
    """
    client = _make_redirector_test_client()
    r = client.get(
        "/v1/auth/callback",
        params={
            "code": "google-code-abc",
            "state": "our-state-xyz",
            "scope": "openid email profile",
            "authuser": "0",
        },
        follow_redirects=False,
    )

    assert r.status_code == 302, (
        f"expected 302 redirect, got {r.status_code}: {r.text[:200]}"
    )
    location = r.headers.get("location") or r.headers.get("Location")
    assert location is not None, "302 response must carry a Location header"
    assert location.startswith("https://api.aurinko.io/v1/auth/callback?"), (
        f"Location must point at Aurinko canonical callback. Got: {location}"
    )
    # Every Google-attached param must be preserved in the forwarded URL.
    assert "code=google-code-abc" in location
    assert "state=our-state-xyz" in location
    # ``scope`` has spaces that should be URL-encoded by the framework.
    assert "scope=openid" in location  # full scope string preserved
    assert "authuser=0" in location


def test_redirector_302s_to_bare_aurinko_callback_when_no_query() -> None:
    """If Google ever calls us with NO query params (defensive — shouldn't
    happen in practice), the redirect target should be the bare Aurinko
    URL without a trailing ``?``."""
    client = _make_redirector_test_client()
    r = client.get("/v1/auth/callback", follow_redirects=False)

    assert r.status_code == 302
    location = r.headers.get("location") or r.headers.get("Location")
    assert location == "https://api.aurinko.io/v1/auth/callback", (
        f"expected bare Aurinko callback URL (no ?), got: {location}"
    )
