from types import SimpleNamespace
from unittest.mock import AsyncMock
from datetime import datetime, timedelta, timezone

import pytest
from bson.objectid import ObjectId

from app.api import otp as otp_api
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


def test_otp_success_response_exposes_reused_existing_code():
    response = otp_api._build_otp_success_response(
        {"success": True, "contact_type": "phone", "reused_existing": True}
    )

    assert response == {
        "message": "OTP sent successfully",
        "contact_type": "phone",
        "reused_existing": True,
    }


class _FakeCollection:
    def __init__(self, result=None):
        self.result = result
        self.find_one_queries = []
        self.deleted_query = None
        self.deleted_many_query = None
        self.updated_query = None
        self.updated_payload = None

    async def find_one(self, query):
        self.find_one_queries.append(query)
        return self.result

    async def delete_one(self, query):
        self.deleted_query = query

    async def delete_many(self, query):
        self.deleted_many_query = query
        return SimpleNamespace(deleted_count=1)

    async def update_one(self, query, payload):
        self.updated_query = query
        self.updated_payload = payload
        return SimpleNamespace(matched_count=1, modified_count=1)


class _FakeTwilio:
    def __init__(self):
        self.sent_to = None
        self.message = None
        self.result = {"status": "success"}

    def _send_sms(self, phone, message):
        self.sent_to = phone
        self.message = message
        return self.result


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
async def test_send_otp_by_contact_resends_active_code_after_cooldown(monkeypatch):
    guest_id = ObjectId()
    existing_otp = {
        "_id": ObjectId(),
        "guest_id": str(guest_id),
        "otp": "654321",
        "contact_type": "phone",
        "created_at": datetime.now(timezone.utc)
        - timedelta(seconds=otp_module.settings.rate_limit_auth_period + 5),
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=3),
    }
    service = _build_contact_otp_service(
        {
            "_id": guest_id,
            "wedding_id": "wed_1",
            "name": "Guest",
            "phone": "+15551234567",
        },
        otp_record=existing_otp,
    )
    twilio = _FakeTwilio()
    service._get_twilio_service = lambda: twilio

    result = await service.send_otp_by_contact("wed_1", "(555) 123-4567")

    assert result == {
        "success": True,
        "contact_type": "phone",
        "fallback_used": False,
        "reused_existing": True,
    }
    service.generate_otp.assert_not_awaited()
    assert "654321" in twilio.message


@pytest.mark.asyncio
async def test_send_otp_by_contact_cleans_generated_code_when_sms_fails():
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
    twilio.result = {"status": "failed", "error_code": "service_unavailable"}
    service._get_twilio_service = lambda: twilio

    result = await service.send_otp_by_contact("wed_1", "+15551234567")

    assert result["success"] is False
    assert result["error_code"] == "service_unavailable"
    assert service.otp_collection.deleted_many_query == {"guest_id": str(guest_id)}


@pytest.mark.asyncio
async def test_send_otp_by_contact_endpoint_maps_structured_errors(monkeypatch):
    monkeypatch.setattr(
        otp_api.otp_service,
        "send_otp_by_contact",
        AsyncMock(
            return_value={
                "success": False,
                "error": "Text messaging is not set up yet.",
                "error_code": "not_configured",
            }
        ),
    )

    with pytest.raises(otp_api.HTTPException) as exc:
        await otp_api.send_otp_by_contact(
            otp_api.OTPRequestByContact(wedding_id="wed_1", contact="+15551234567")
        )

    assert exc.value.status_code == 503
    assert exc.value.detail == {
        "message": "Text messaging is not set up yet.",
        "error_code": "not_configured",
    }


@pytest.mark.asyncio
async def test_send_otp_resends_active_session_code_after_cooldown():
    guest_id = ObjectId()
    existing_otp = {
        "_id": ObjectId(),
        "guest_id": str(guest_id),
        "otp": "987654",
        "contact_type": "phone",
        "created_at": datetime.now(timezone.utc)
        - timedelta(seconds=otp_module.settings.rate_limit_auth_period + 5),
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=3),
    }
    service = _build_contact_otp_service(
        {
            "_id": guest_id,
            "wedding_id": "wed_1",
            "name": "Guest",
            "phone": "+15551234567",
        },
        otp_record=existing_otp,
    )
    twilio = _FakeTwilio()
    service._get_twilio_service = lambda: twilio

    result = await service.send_otp(str(guest_id))

    assert result == {
        "success": True,
        "contact_type": "phone",
        "fallback_used": False,
        "reused_existing": True,
    }
    service.generate_otp.assert_not_awaited()
    assert "987654" in twilio.message


@pytest.mark.asyncio
async def test_send_otp_cleans_generated_code_when_sms_fails_without_fallback():
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
    twilio.result = {"status": "failed", "error_code": "service_unavailable"}
    service._get_twilio_service = lambda: twilio

    result = await service.send_otp(str(guest_id))

    assert result["success"] is False
    assert result["error_code"] == "service_unavailable"
    assert service.otp_collection.deleted_many_query == {"guest_id": str(guest_id)}


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
