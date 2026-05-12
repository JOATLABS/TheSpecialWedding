from pathlib import Path

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.routing import Match

from app.api.guest_verification import router as guest_verification_router
from app.dependencies.guest_access import (
    GUEST_ACCESS_COOKIE_NAME,
    create_guest_access_session_token,
    get_guest_access_session,
)

ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text()


def _request_with_cookie(token: str) -> Request:
    return Request(
        {
            "type": "http",
            "headers": [
                (b"cookie", f"{GUEST_ACCESS_COOKIE_NAME}={token}".encode("utf-8")),
            ],
        }
    )


def test_guest_access_session_round_trips_through_cookie_claims() -> None:
    token = create_guest_access_session_token(
        wedding_slug="maya-and-jordan",
        wedding_id="w_123",
        guest_id="507f1f77bcf86cd799439011",
        auth_method="token",
        otp_verified=False,
    )

    session = get_guest_access_session(
        _request_with_cookie(token),
        slug="maya-and-jordan",
        require_guest=True,
    )

    assert session.wedding_slug == "maya-and-jordan"
    assert session.wedding_id == "w_123"
    assert session.guest_id == "507f1f77bcf86cd799439011"
    assert session.auth_method == "token"
    assert session.otp_verified is False


def test_guest_access_session_rejects_slug_mismatch() -> None:
    token = create_guest_access_session_token(
        wedding_slug="maya-and-jordan",
        wedding_id="w_123",
        guest_id="507f1f77bcf86cd799439011",
        auth_method="token",
        otp_verified=False,
    )

    with pytest.raises(HTTPException) as exc_info:
        get_guest_access_session(
            _request_with_cookie(token),
            slug="different-wedding",
        )

    assert exc_info.value.status_code == 403


def test_guest_invite_page_exchanges_path_token_without_query_redirect() -> None:
    invite_page = _read("app/[slug]/invite/[token]/page.tsx")

    assert "exchangeGuestInviteToken(slug, token)" in invite_page
    assert "router.replace(`/${slug}#rsvp`)" in invite_page
    assert "?rsvp_token=" not in invite_page


def test_guest_landing_page_uses_session_exchange_instead_of_browser_storage() -> None:
    landing_page = _read("app/[slug]/page.tsx")

    assert "exchangeGuestInviteToken(slug, rsvpTokenParam)" in landing_page
    assert "fetchGuestSessionAccess(slug)" in landing_page
    assert "sessionStorage" not in landing_page
    assert "rsvp_token_" not in landing_page


def test_guest_session_route_precedes_token_catchall() -> None:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/weddings/guest-access/session/josh-and-esther",
        "root_path": "",
        "headers": [],
        "query_string": b"",
        "server": ("testserver", 80),
        "scheme": "http",
        "client": ("testclient", 50000),
    }

    for route in guest_verification_router.routes:
        match, _ = route.matches(scope)
        if match == Match.FULL:
            assert route.endpoint.__name__ == "get_wedding_with_session_access"
            return

    pytest.fail("No guest access session route matched the session URL")


def test_guest_session_endpoints_and_token_redaction_are_pinned() -> None:
    guest_verification_api = _read("app/api/guest_verification.py")
    otp_api = _read("app/api/otp.py")
    rsvp_api = _read("app/api/rspv.py")
    guest_verification_service = _read("app/services/guest_verification_service.py")
    otp_service = _read("app/services/otp_service.py")
    public_gallery = _read("app/utils/publicGallery.ts")

    assert "/weddings/guest-access/{slug}/{token}/exchange" in guest_verification_api
    assert "/weddings/guest-access/session/{slug}" in guest_verification_api
    assert "/otp/request/session" in otp_api
    assert "/otp/verify/session" in otp_api
    assert "/session/{slug}/rsvp" in rsvp_api
    assert 'guest_response.pop("token", None)' in guest_verification_service
    assert 'guest_response.pop("token", None)' in otp_service
    assert "credentials: 'include'" in public_gallery
    assert "guest.token" not in public_gallery
