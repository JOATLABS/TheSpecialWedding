from __future__ import annotations

from urllib.parse import quote


def build_guest_otp_url(frontend_url: str, slug: str, token: str) -> str:
    """Build the public guest OTP verification URL for RSVP entry."""
    base_url = (frontend_url or "").strip().rstrip("/")
    if not base_url:
        raise ValueError("frontend_url is required to build a guest OTP URL")

    return (
        f"{base_url}/otp/verify"
        f"?slug={quote(str(slug), safe='')}"
        f"&token={quote(str(token), safe='')}"
    )
