# app/core/sms_config.py

import os
from enum import Enum


class SMSProvider(Enum):
    TWILIO = "twilio"
    TELNYX = "telnyx"


def get_active_sms_provider() -> SMSProvider:
    """
    Get the active SMS provider from environment variable.
    Defaults to TWILIO for backward compatibility.
    
    Set SMS_PROVIDER=telnyx in .env to switch to Telnyx
    """
    provider = os.getenv("SMS_PROVIDER", "twilio").lower()
    
    if provider == "telnyx":
        return SMSProvider.TELNYX
    else:
        return SMSProvider.TWILIO


def is_telnyx_active() -> bool:
    """Check if Telnyx is the active SMS provider"""
    return get_active_sms_provider() == SMSProvider.TELNYX


def is_twilio_active() -> bool:
    """Check if Twilio is the active SMS provider"""
    return get_active_sms_provider() == SMSProvider.TWILIO