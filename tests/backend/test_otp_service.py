from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from bson.objectid import ObjectId

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


class _FakeCollection:
    def __init__(self, result=None):
        self.result = result
        self.find_one_queries = []
        self.deleted_query = None

    async def find_one(self, query):
        self.find_one_queries.append(query)
        return self.result

    async def delete_one(self, query):
        self.deleted_query = query


class _FakeTwilio:
    def __init__(self):
        self.sent_to = None

    def _send_sms(self, phone, message):
        self.sent_to = phone
        return {"status": "success"}


def _build_contact_otp_service(guest, otp_record=None):
    service = otp_module.OTPService.__new__(otp_module.OTPService)
    service.guest_collection = _FakeCollection(guest)
    service.otp_collection = _FakeCollection(otp_record)
    service.email_service = SimpleNamespace(
        send_email=AsyncMock(return_value={"success": True})
    )
    service.generate_otp = AsyncMock(return_value="123456")
    service._ensure_indexes = AsyncMock(return_value=None)
    return service


@pytest.mark.asyncio
async def test_send_otp_by_contact_matches_email_case_insensitively():
    guest_id = ObjectId()
    service = _build_contact_otp_service(
        {
            "_id": guest_id,
            "wedding_id": "wed_1",
            "name": "Guest",
            "email": "guest@example.com",
        }
    )

    result = await service.send_otp_by_contact("wed_1", "GUEST@EXAMPLE.COM")

    assert result == {"success": True, "contact_type": "email"}
    assert service.guest_collection.find_one_queries[0]["$or"][1]["email"] == {
        "$regex": "^GUEST@EXAMPLE\\.COM$",
        "$options": "i",
    }
    service.generate_otp.assert_awaited_once_with(str(guest_id), contact_type="email")
    service.email_service.send_email.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_otp_by_contact_normalizes_formatted_phone():
    guest_id = ObjectId()
    service = _build_contact_otp_service(
        {
            "_id": guest_id,
            "wedding_id": "wed_1",
            "name": "Guest",
            "phone": "+15551234567",
        }
    )
    twilio = _FakeTwilio()
    service._get_twilio_service = lambda: twilio

    result = await service.send_otp_by_contact("wed_1", "(555) 123-4567")

    assert result == {
        "success": True,
        "contact_type": "phone",
        "fallback_used": False,
    }
    assert (
        "+15551234567"
        in service.guest_collection.find_one_queries[0]["$or"][0]["phone"]["$in"]
    )
    service.generate_otp.assert_awaited_once_with(str(guest_id), contact_type="phone")
    assert twilio.sent_to == "+15551234567"


@pytest.mark.asyncio
async def test_verify_otp_matches_email_case_insensitively():
    guest_id = ObjectId()
    service = _build_contact_otp_service(
        {
            "_id": guest_id,
            "wedding_id": "wed_1",
            "name": "Guest",
            "email": "guest@example.com",
        },
        otp_record={"_id": ObjectId(), "guest_id": str(guest_id), "otp": "123456"},
    )

    result = await service.verify_otp("wed_1", "GUEST@EXAMPLE.COM", " 123456 ")

    assert result["success"] is True
    assert result["auth_method"] == "email_otp"
    assert result["guest"]["id"] == str(guest_id)
    assert service.otp_collection.deleted_query == {
        "_id": service.otp_collection.result["_id"]
    }


@pytest.mark.asyncio
async def test_verify_otp_matches_formatted_phone():
    guest_id = ObjectId()
    service = _build_contact_otp_service(
        {
            "_id": guest_id,
            "wedding_id": "wed_1",
            "name": "Guest",
            "phone": "+15551234567",
        },
        otp_record={"_id": ObjectId(), "guest_id": str(guest_id), "otp": "123456"},
    )

    result = await service.verify_otp("wed_1", "(555) 123-4567", "123456")

    assert result["success"] is True
    assert result["auth_method"] == "phone_otp"
