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


# ---------------------------------------------------------------------------
# URL-building logic (mirrors the production implementation, stdlib only)
# ---------------------------------------------------------------------------

def _build_otp_url(frontend_url: str, slug: str, token: str) -> str:
    """Reference implementation matching what the services now generate."""
    base = frontend_url.rstrip("/")
    return (
        f"{base}/otp/verify"
        f"?slug={quote(slug, safe='')}"
        f"&token={quote(token, safe='')}"
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
