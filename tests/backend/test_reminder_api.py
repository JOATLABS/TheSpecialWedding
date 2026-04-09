import pytest
from fastapi import HTTPException

from app.api import reminder as reminder_module


def test_get_reminder_service_returns_503_when_twilio_not_configured(monkeypatch):
    for key in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER"):
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(HTTPException) as exc_info:
        reminder_module.get_reminder_service()

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "SMS reminders are not configured"
