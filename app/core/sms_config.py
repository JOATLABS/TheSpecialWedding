# app/core/sms_config.py
"""
SMS Provider Configuration

Controls which SMS provider (Twilio or Telnyx) is used for sending
SMS messages across the platform (reminders, OTP, notifications).

Configuration:
    Set the SMS_PROVIDER environment variable:
    - SMS_PROVIDER=twilio  (default) — Uses Twilio Messaging API
    - SMS_PROVIDER=telnyx  — Uses Telnyx Messaging API

    Each provider requires its own set of credentials:

    Twilio:
        TWILIO_ACCOUNT_SID     - Twilio Account SID
        TWILIO_AUTH_TOKEN       - Twilio Auth Token
        TWILIO_PHONE_NUMBER     - Sender phone number (E.164 format)
        TWILIO_MESSAGING_SERVICE_SID - (optional) Messaging Service SID for bulk
        SMS_THROTTLE_DELAY_MS   - (optional) Delay between sends in ms (default 350)
                                  350ms = ~2.8 req/s (safe for toll-free 3 MPS limit)
                                  100ms = 10 req/s (25+ MPS toll-free)
                                   50ms = 20 req/s (short codes)

    Telnyx:
        TELNYX_API_KEY          - Telnyx API Key
        TELNYX_PHONE_NUMBER     - Sender phone number (E.164 format)

Provider Selection:
    The provider is determined at import time from the environment variable.
    There is no runtime switching — a server restart is required to change providers.
    This is intentional to prevent accidental mid-conversation provider switches.

Usage:
    from app.core.sms_config import get_active_sms_provider, SMSProvider

    provider = get_active_sms_provider()
    if provider == SMSProvider.TWILIO:
        # Use Twilio client
    elif provider == SMSProvider.TELNYX:
        # Use Telnyx client
"""

import logging
import os
from enum import Enum

logger = logging.getLogger(__name__)


class SMSProvider(Enum):
    TWILIO = "twilio"
    TELNYX = "telnyx"


def get_active_sms_provider() -> SMSProvider:
    """
    Get the active SMS provider from environment variable.
    Defaults to TWILIO for backward compatibility.

    Set SMS_PROVIDER=telnyx in .env to switch to Telnyx.
    """
    provider = os.getenv("SMS_PROVIDER", "twilio").lower()

    if provider == "telnyx":
        logger.info("SMS provider: Telnyx")
        return SMSProvider.TELNYX
    elif provider == "twilio":
        return SMSProvider.TWILIO
    else:
        logger.warning(
            f"Unknown SMS_PROVIDER '{provider}' — falling back to Twilio. "
            f"Valid options: 'twilio', 'telnyx'"
        )
        return SMSProvider.TWILIO


def is_telnyx_active() -> bool:
    """Check if Telnyx is the active SMS provider"""
    return get_active_sms_provider() == SMSProvider.TELNYX


def is_twilio_active() -> bool:
    """Check if Twilio is the active SMS provider"""
    return get_active_sms_provider() == SMSProvider.TWILIO
