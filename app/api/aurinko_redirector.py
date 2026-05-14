"""Intermediate redirect endpoint for Aurinko's Google OAuth flow.

Aurinko's docs (docs.aurinko.io/authentication/oauth-flow/account-oauth-flow,
"Intermediate Redirect URL" section) call out the problem this endpoint
solves:

    Google app registrations allow only authorized redirect URIs under a
    domain you own so Aurinko's default Redirect URI
    https://api.aurinko.io/v1/auth/callback won't work for you in
    production.

    Create a dedicated intermediate redirect page that will be redirecting
    all callback requests to Aurinko's
    https://api.aurinko.io/v1/auth/callback with the URL parameters state,
    code, and scope.

    Specify the page url in the Aurinko app settings (override the default
    url).

OAuth hop sequence:

    Browser → Aurinko /v1/auth/authorize
           → redirects to Google with redirect_uri=THIS_ENDPOINT
           → Google auth → Google redirects to THIS_ENDPOINT?code+state+scope
    THIS_ENDPOINT → 302 to https://api.aurinko.io/v1/auth/callback?<same>
    Aurinko → processes Google code, redirects user to our returnUrl
              (the /admin/planner/calendar/callback page).

DNS expectation: ``aurinko.thespecialwedding.io`` is a CNAME / A record
pointing at this backend host. The backend serves this exact path
without any /admin prefix so the URL Google sees is

    https://aurinko.thespecialwedding.io/v1/auth/callback

and that's what's registered in the Google Cloud OAuth client's
Authorized redirect URIs list AND in the Aurinko app settings
"Intermediate Redirect URL" override field.

Local dev variant: the route also serves on localhost:8000 if you point
DNS-or-/etc-hosts ``aurinko.localtest.me`` at 127.0.0.1, but for dev the
simpler approach is to add ``https://api.aurinko.io/v1/auth/callback``
to the Google client directly and skip this redirector entirely.
"""

from __future__ import annotations

import logging
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

logger = logging.getLogger(__name__)

router = APIRouter()


# The canonical Aurinko callback URL the user-pasted/registered redirector
# should ultimately funnel to. Hard-coded because this is the Aurinko-side
# fixture, not anything we configure — Aurinko expects to be hit at exactly
# this URL with the Google-side ``code`` / ``state`` / ``scope`` params.
_AURINKO_CALLBACK_URL = "https://api.aurinko.io/v1/auth/callback"


@router.get(
    "/v1/auth/callback",
    tags=["Aurinko OAuth"],
    include_in_schema=False,
)
async def aurinko_oauth_intermediate_redirect(request: Request) -> RedirectResponse:
    """Forward Google's OAuth callback to Aurinko's canonical callback.

    Preserves every query parameter Google attached (``code``, ``state``,
    ``scope``, ``authuser``, ``hd``, ``prompt``, etc.) so Aurinko's side
    of the OAuth handshake sees the exact same URL shape Google sent.
    """
    # request.url.query is the raw query string (already URL-encoded).
    # Building from `request.query_params.items()` would re-encode and
    # potentially reorder; using the raw string preserves byte-for-byte
    # what Google attached.
    raw_query = request.url.query
    target = (
        f"{_AURINKO_CALLBACK_URL}?{raw_query}" if raw_query else _AURINKO_CALLBACK_URL
    )

    logger.info(
        "Aurinko OAuth intermediate redirect: forwarding to Aurinko "
        "callback (query_param_count=%d)",
        len(request.query_params),
    )

    # 302 (default) is correct for an OAuth code-exchange handoff —
    # the browser's GET → 302 → GET pattern is what Google expects.
    return RedirectResponse(url=target, status_code=302)


# Convenience helper for tests / observability. Not exposed as a route.
def build_aurinko_callback_url(query_params: dict[str, str]) -> str:
    """Build the absolute Aurinko callback URL with the given params."""
    if not query_params:
        return _AURINKO_CALLBACK_URL
    return f"{_AURINKO_CALLBACK_URL}?{urlencode(query_params)}"
