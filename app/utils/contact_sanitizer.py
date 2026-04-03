# app/utils/contact_sanitizer.py

"""
Contact information sanitization utilities.

Used by both Pydantic model validators (on insert/update) and
send-time code paths (defense-in-depth before calling Twilio/Telnyx/Resend).
"""

import re
from typing import Optional


def sanitize_phone(phone: Optional[str]) -> Optional[str]:
    """
    Sanitize a phone number by stripping whitespace and common delimiters.

    Handles formats like:
      " +1 (234) 567-8901 "  →  "+12345678901"
      "123.456.7890"          →  "1234567890"
      " 123-456-7890\t"       →  "1234567890"

    Returns None if the input is None or empty after sanitization.
    """
    if not phone:
        return None

    # Strip leading/trailing whitespace
    phone = phone.strip()

    if not phone:
        return None

    # Preserve leading '+' if present
    has_plus = phone.startswith("+")

    # Remove all non-digit characters
    digits_only = re.sub(r"[^\d]", "", phone)

    if not digits_only:
        return None

    # Restore the '+' prefix
    return f"+{digits_only}" if has_plus else digits_only


def normalize_phone_e164(phone: Optional[str], default_country_code: str = "1") -> Optional[str]:
    """
    Sanitize and normalize a phone number to E.164 format for Twilio/Telnyx.

    Steps:
      1. sanitize_phone() — strip whitespace and delimiters
      2. Ensure '+' prefix with country code

    Args:
        phone: Raw phone number string
        default_country_code: Country code to prepend if missing (default "1" for US)

    Returns:
        E.164 formatted phone (e.g. "+12345678901") or None if invalid
    """
    phone = sanitize_phone(phone)
    if not phone:
        return None

    if not phone.startswith("+"):
        phone = f"+{default_country_code}{phone}"

    return phone


def validate_phone_format(phone: str) -> bool:
    """
    Validate that a sanitized phone number has a valid digit count.

    Expects a sanitized phone (digits only, optional leading '+').
    Valid: 10-15 digits (per E.164 spec, max 15 digits including country code).
    """
    if not phone:
        return False

    digits = re.sub(r"[^\d]", "", phone)
    return 10 <= len(digits) <= 15


def sanitize_email(email: Optional[str]) -> Optional[str]:
    """
    Sanitize an email address by stripping whitespace and lowercasing.

    Returns None if the input is None or empty after sanitization.
    """
    if not email:
        return None

    email = email.strip().lower()

    if not email:
        return None

    return email


def validate_email_format(email: str) -> bool:
    """
    Validate email format. Matches the pattern used in PlusOneModel.

    Returns True if valid, False otherwise.
    """
    if not email:
        return False

    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))
