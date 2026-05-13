"""
Tests for OTP RSVP link generation across all three services.

Ensures newly generated links point to /otp/verify?slug=...&token=...
instead of the legacy /{slug}/invite/{token} route.

These tests use source inspection to avoid importing the full service stack
(which requires a live MongoDB connection).
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote

# Paths to the three service files
_SERVICES_DIR = Path(__file__).resolve().parents[2] / "app" / "services"
_EXPORT_SRC = (_SERVICES_DIR / "guest_export_service.py").read_text()
_VERIFY_SRC = (_SERVICES_DIR / "guest_verification_service.py").read_text()
_REMINDER_SRC = (_SERVICES_DIR / "reminder_utilities.py").read_text()
_REMINDER_TWILIO_SRC = (_SERVICES_DIR / "reminder_service_twilio.py").read_text()
_REMINDER_TELNYX_SRC = (_SERVICES_DIR / "reminder_utilities_telnyx.py").read_text()
_EMAIL_SRC = (_SERVICES_DIR / "email_service_resend.py").read_text()
_API_EMAIL_REMINDERS_SRC = (
    Path(__file__).resolve().parents[2] / "app" / "api" / "email_reminders.py"
).read_text()
_ADMIN_GUESTS_SRC = (
    Path(__file__).resolve().parents[2] / "app" / "admin" / "guests" / "page.tsx"
).read_text()
_ADMIN_COMMUNICATIONS_REMINDERS_SRC = (
    Path(__file__).resolve().parents[2]
    / "app"
    / "admin"
    / "communications"
    / "components"
    / "CommunicationsRemindersView.tsx"
).read_text()
_TWILIO_WEBHOOK_SRC = (
    Path(__file__).resolve().parents[2] / "app" / "api" / "twilio_webhooks.py"
).read_text()


# ---------------------------------------------------------------------------
# URL-building logic (mirrors the production implementation, stdlib only)
# ---------------------------------------------------------------------------


def _build_otp_url(frontend_url: str, slug: str, token: str) -> str:
    """Reference implementation matching what the services now generate."""
    base = frontend_url.rstrip("/")
    return (
        f"{base}/otp/verify?slug={quote(slug, safe='')}&token={quote(token, safe='')}"
    )


def _assert_no_legacy_invite_pattern(source: str, file_name: str) -> None:
    """Assert that no non-comment line in *source* contains a legacy invite path.

    Checks for both ``}/invite/`` and ``/invite/`` patterns to catch
    direct f-string constructions such as ``f"{base}/{slug}/invite/{token}"``.
    """
    for line in source.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        assert "/invite/" not in line, (
            f"Legacy /invite/ pattern still present in {file_name}: {line!r}"
        )


# ---------------------------------------------------------------------------
# Direct logic tests (no heavy imports)
# ---------------------------------------------------------------------------


def test_otp_url_basic():
    url = _build_otp_url("https://example.io", "summer-wedding", "abc123")
    assert url == "https://example.io/otp/verify?slug=summer-wedding&token=abc123"
    assert "/invite/" not in url


def test_otp_url_trims_trailing_slash():
    url = _build_otp_url("https://example.io/", "my-wedding", "tok456")
    assert "//otp" not in url
    assert url.startswith("https://example.io/otp/verify")


def test_otp_url_encodes_special_characters():
    url = _build_otp_url("https://example.io", "my wedding", "tok en+1")
    assert "my%20wedding" in url
    assert "tok%20en%2B1" in url


def test_otp_url_with_default_fallback():
    frontend_url = os.getenv("FRONTEND_URL", "https://thespecialwedding.io")
    url = _build_otp_url(frontend_url, "fallback-slug", "fallback-token")
    assert "/otp/verify" in url
    assert "slug=fallback-slug" in url
    assert "token=fallback-token" in url


def test_shared_guest_otp_url_helper_encodes_slug_and_token():
    from app.utils.rsvp_links import build_guest_otp_url

    url = build_guest_otp_url(
        "https://thespecialwedding.io/",
        "my wedding",
        "tok en+1",
    )

    assert url == (
        "https://thespecialwedding.io/otp/verify?slug=my%20wedding&token=tok%20en%2B1"
    )
    assert "/invite/" not in url


# ---------------------------------------------------------------------------
# Source-inspection tests — verify each file was updated correctly
# ---------------------------------------------------------------------------


def test_guest_export_service_uses_otp_route_in_source():
    assert "/otp/verify" in _EXPORT_SRC, (
        "guest_export_service.py must generate /otp/verify links"
    )


def test_guest_export_service_no_legacy_invite_route_in_source():
    _assert_no_legacy_invite_pattern(_EXPORT_SRC, "guest_export_service.py")


def test_guest_export_service_imports_quote():
    assert "from urllib.parse import quote" in _EXPORT_SRC


def test_guest_verification_service_uses_otp_route_in_source():
    assert "/otp/verify" in _VERIFY_SRC, (
        "guest_verification_service.py must generate /otp/verify links"
    )


def test_guest_verification_service_no_legacy_invite_route_in_source():
    _assert_no_legacy_invite_pattern(_VERIFY_SRC, "guest_verification_service.py")


def test_guest_verification_service_imports_quote():
    assert "from urllib.parse import quote" in _VERIFY_SRC


def test_reminder_utilities_uses_otp_route_in_source():
    assert "/otp/verify" in _REMINDER_SRC, (
        "reminder_utilities.py must generate /otp/verify links"
    )


def test_reminder_utilities_no_legacy_invite_route_in_source():
    _assert_no_legacy_invite_pattern(_REMINDER_SRC, "reminder_utilities.py")


def test_reminder_utilities_imports_quote():
    assert "from urllib.parse import quote" in _REMINDER_SRC


def test_email_and_sms_reminder_sources_do_not_generate_legacy_invite_links():
    checked_sources = {
        "email_service_resend.py": _EMAIL_SRC,
        "email_reminders.py": _API_EMAIL_REMINDERS_SRC,
        "reminder_service_twilio.py": _REMINDER_TWILIO_SRC,
        "reminder_utilities_telnyx.py": _REMINDER_TELNYX_SRC,
    }

    for file_name, source in checked_sources.items():
        assert "/otp/verify" in source or "build_guest_otp_url" in source, (
            f"{file_name} must generate OTP RSVP links"
        )
        _assert_no_legacy_invite_pattern(source, file_name)


def test_admin_guest_and_communications_prefills_use_production_safe_otp_links():
    checked_sources = {
        "app/admin/guests/page.tsx": _ADMIN_GUESTS_SRC,
        "app/admin/communications/components/CommunicationsRemindersView.tsx": (
            _ADMIN_COMMUNICATIONS_REMINDERS_SRC
        ),
    }

    for file_name, source in checked_sources.items():
        assert "/otp/verify" in source or "buildGuestOtpVerifyUrl" in source, (
            f"{file_name} must preview OTP RSVP links"
        )
        _assert_no_legacy_invite_pattern(source, file_name)
        assert "window.location.origin" not in source, (
            f"{file_name} must not build guest RSVP links from browser origin"
        )


def test_lost_link_sms_default_includes_help_instructions():
    assert "Reply HELP" in _VERIFY_SRC
    assert "use Get Help on the wedding website" in _VERIFY_SRC


def test_bulk_sms_defaults_include_help_instructions_without_custom_templates():
    for source in (_REMINDER_SRC, _REMINDER_TWILIO_SRC, _REMINDER_TELNYX_SRC):
        assert "if custom_message" in source
        assert "Reply HELP" in source
        assert "use Get Help on the wedding website" in source


def test_default_rsvp_email_includes_help_instructions():
    assert "Need help with your invitation?" in _EMAIL_SRC
    assert "Get Help" in _EMAIL_SRC


def test_sms_help_auto_reply_routes_back_to_text_thread_not_phone_call():
    assert "Reply with your question " in _TWILIO_WEBHOOK_SRC
    assert "the planner will respond by text" in _TWILIO_WEBHOOK_SRC
    assert "Please respond from the communications inbox" in _TWILIO_WEBHOOK_SRC
    assert "For support, call" not in _TWILIO_WEBHOOK_SRC
    assert "For urgent matters, call" not in _TWILIO_WEBHOOK_SRC
