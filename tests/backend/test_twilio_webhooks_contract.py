from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock
import sys

import pytest
from starlette.datastructures import FormData, UploadFile

from app.api import twilio_webhooks


class FakeRequest:
    def __init__(self, form_data: FormData, path: str) -> None:
        self._form_data = form_data
        self.headers: dict[str, str] = {}
        self.url = SimpleNamespace(path=path)

    async def form(self) -> FormData:
        return self._form_data


class FakeRemindersLogCollection:
    def __init__(self, *, matched_count: int = 1) -> None:
        self.matched_count = matched_count
        self.last_query: dict[str, object] | None = None
        self.last_update: dict[str, object] | None = None

    async def update_one(
        self, query: dict[str, object], update: dict[str, object]
    ) -> SimpleNamespace:
        self.last_query = query
        self.last_update = update
        return SimpleNamespace(matched_count=self.matched_count)


class FakeGuestCollection:
    def __init__(self) -> None:
        self.updated_queries: list[dict[str, object]] = []
        self.updated_payloads: list[dict[str, object]] = []

    async def find_one(self, _query: dict[str, object]) -> None:
        return None

    async def update_many(
        self, query: dict[str, object], payload: dict[str, object]
    ) -> SimpleNamespace:
        self.updated_queries.append(query)
        self.updated_payloads.append(payload)
        return SimpleNamespace(modified_count=1)


def _build_upload_file() -> UploadFile:
    return UploadFile(file=BytesIO(b"unexpected"), filename="unexpected.txt")


def test_normalize_twilio_form_data_ignores_upload_files(
    caplog: pytest.LogCaptureFixture,
) -> None:
    form_data = FormData(
        [
            ("From", "+15551234567"),
            ("Body", "Help"),
            ("MessageSid", "SM123"),
            ("Media", _build_upload_file()),
        ]
    )

    normalized = twilio_webhooks._normalize_twilio_form_data(form_data)

    assert normalized == {
        "From": "+15551234567",
        "Body": "Help",
        "MessageSid": "SM123",
    }
    assert "Ignoring unexpected uploaded file" in caplog.text


@pytest.mark.asyncio
async def test_status_callback_parses_error_code_once_and_calls_failure_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log_collection = FakeRemindersLogCollection()
    failure_handler = AsyncMock()

    monkeypatch.setattr(
        twilio_webhooks, "_validate_twilio_signature", lambda *_args, **_kwargs: True
    )
    monkeypatch.setattr(twilio_webhooks, "_handle_delivery_failure", failure_handler)
    monkeypatch.setattr(
        twilio_webhooks,
        "mongo",
        SimpleNamespace(db={"reminders_sent": log_collection}),
    )

    request = FakeRequest(
        FormData(
            {
                "MessageSid": "SM123",
                "MessageStatus": "failed",
                "ErrorCode": "30004",
                "To": "+15551234567",
            }
        ),
        "/webhook/twilio/status",
    )

    result = await twilio_webhooks.handle_twilio_status_callback(request, None)

    assert result["status"] == "success"
    assert log_collection.last_query == {"message_sid": "SM123"}
    assert log_collection.last_update is not None
    assert log_collection.last_update["$set"]["error_code"] == 30004
    assert log_collection.last_update["$push"]["delivery_events"]["error_code"] == 30004
    failure_handler.assert_awaited_once()
    assert failure_handler.await_args.kwargs["error_code"] == 30004


@pytest.mark.asyncio
async def test_status_callback_missing_error_code_skips_failure_handling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log_collection = FakeRemindersLogCollection()
    failure_handler = AsyncMock()

    monkeypatch.setattr(
        twilio_webhooks, "_validate_twilio_signature", lambda *_args, **_kwargs: True
    )
    monkeypatch.setattr(twilio_webhooks, "_handle_delivery_failure", failure_handler)
    monkeypatch.setattr(
        twilio_webhooks,
        "mongo",
        SimpleNamespace(db={"reminders_sent": log_collection}),
    )

    request = FakeRequest(
        FormData({"MessageSid": "SM123", "MessageStatus": "failed"}),
        "/webhook/twilio/status",
    )

    result = await twilio_webhooks.handle_twilio_status_callback(request, None)

    assert result["status"] == "success"
    assert log_collection.last_update is not None
    assert "error_code" not in log_collection.last_update["$set"]
    assert log_collection.last_update["$push"]["delivery_events"]["error_code"] is None
    failure_handler.assert_not_awaited()


@pytest.mark.asyncio
async def test_status_callback_invalid_error_code_does_not_raise(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    log_collection = FakeRemindersLogCollection()
    failure_handler = AsyncMock()

    monkeypatch.setattr(
        twilio_webhooks, "_validate_twilio_signature", lambda *_args, **_kwargs: True
    )
    monkeypatch.setattr(twilio_webhooks, "_handle_delivery_failure", failure_handler)
    monkeypatch.setattr(
        twilio_webhooks,
        "mongo",
        SimpleNamespace(db={"reminders_sent": log_collection}),
    )

    request = FakeRequest(
        FormData(
            {
                "MessageSid": "SM123",
                "MessageStatus": "failed",
                "ErrorCode": "abc",
            }
        ),
        "/webhook/twilio/status",
    )

    result = await twilio_webhooks.handle_twilio_status_callback(request, None)

    assert result["status"] == "success"
    assert log_collection.last_update is not None
    assert "error_code" not in log_collection.last_update["$set"]
    assert log_collection.last_update["$push"]["delivery_events"]["error_code"] is None
    failure_handler.assert_not_awaited()
    assert (
        "Ignoring invalid integer value for Twilio webhook field ErrorCode"
        in caplog.text
    )


@pytest.mark.asyncio
async def test_incoming_webhook_uses_normalized_string_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guest_collection = FakeGuestCollection()
    sent_messages: list[tuple[str, str]] = []

    class FakeSMSService:
        def send_sms(self, to_number: str, message: str) -> None:
            sent_messages.append((to_number, message))

    monkeypatch.setattr(
        twilio_webhooks, "_validate_twilio_signature", lambda *_args, **_kwargs: True
    )
    monkeypatch.setattr(
        twilio_webhooks,
        "mongo",
        SimpleNamespace(
            get_guest_collection=lambda: guest_collection,
            db={"weddings": object()},
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "app.services.sms_service",
        SimpleNamespace(SMSService=FakeSMSService),
    )

    request = FakeRequest(
        FormData(
            [
                ("From", "+15551234567"),
                ("Body", "stop"),
                ("MessageSid", "SM123"),
                ("Media", _build_upload_file()),
            ]
        ),
        "/webhook/twilio/incoming",
    )

    result = await twilio_webhooks.handle_twilio_incoming_message(request, None)

    assert result == {"status": "ok", "action": "opt_out", "modified": 1}
    assert guest_collection.updated_queries
    assert sent_messages
    assert sent_messages[0][0] == "+15551234567"
