from app.services import otp_service as otp_module


class _BrokenTwilioService:
    def __init__(self):
        raise RuntimeError("twilio missing")


def test_otp_service_does_not_crash_when_twilio_is_unconfigured(monkeypatch):
    monkeypatch.setattr(otp_module, "TwilioReminderService", _BrokenTwilioService)

    service = otp_module.OTPService()

    assert service.twilio_service is None
    assert service._get_twilio_service() is None
    assert service._twilio_unavailable_error == "twilio missing"
