from __future__ import annotations

from datetime import datetime, timezone
import sys
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from bson import ObjectId
from starlette.datastructures import FormData, UploadFile

from app.api.support_management import SMSResponseModel
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
    def __init__(self, find_one_result: dict | None = None) -> None:
        self.find_one_result = find_one_result
        self.updated_queries: list[dict[str, object]] = []
        self.updated_payloads: list[dict[str, object]] = []

    async def find_one(self, _query: dict[str, object]) -> dict | None:
        return self.find_one_result

    async def update_many(
        self, query: dict[str, object], payload: dict[str, object]
    ) -> SimpleNamespace:
        self.updated_queries.append(query)
        self.updated_payloads.append(payload)
        return SimpleNamespace(modified_count=1)


class FakeCursor:
    def __init__(self, docs: list[dict]) -> None:
        self.docs = list(docs)
        self._limit: int | None = None

    def sort(self, sort_fields):
        if isinstance(sort_fields, tuple):
            sort_fields = [sort_fields]
        for key, direction in reversed(sort_fields):
            self.docs.sort(
                key=lambda doc: (
                    doc.get(key) or datetime.min.replace(tzinfo=timezone.utc)
                ),
                reverse=direction < 0,
            )
        return self

    def limit(self, limit: int):
        self._limit = limit
        return self

    async def to_list(self, length: int | None = None) -> list[dict]:
        limit = self._limit if self._limit is not None else length
        return self.docs[:limit] if limit is not None else self.docs


class FakeCollection:
    def __init__(self, docs: list[dict] | None = None) -> None:
        self.docs = docs or []
        self.inserted: list[dict] = []
        self.updated: list[tuple[dict, dict]] = []

    @staticmethod
    def _value_matches(actual: object, expected: object) -> bool:
        if isinstance(expected, dict):
            if "$in" in expected:
                return actual in expected["$in"] or str(actual) in {
                    str(item) for item in expected["$in"]
                }
            if "$nin" in expected:
                return actual not in expected["$nin"] and str(actual) not in {
                    str(item) for item in expected["$nin"]
                }
            return False
        return actual == expected or str(actual) == str(expected)

    @classmethod
    def _matches(cls, doc: dict, query: dict) -> bool:
        for key, expected in query.items():
            if key == "$or":
                if not any(cls._matches(doc, clause) for clause in expected):
                    return False
                continue
            if not cls._value_matches(doc.get(key), expected):
                return False
        return True

    async def find_one(self, query: dict, *args, **kwargs) -> dict | None:
        matches = [doc for doc in self.docs if self._matches(doc, query)]
        sort = kwargs.get("sort")
        if sort:
            for key, direction in reversed(sort):
                matches.sort(
                    key=lambda doc: (
                        doc.get(key) or datetime.min.replace(tzinfo=timezone.utc)
                    ),
                    reverse=direction < 0,
                )
        return matches[0] if matches else None

    def find(self, query: dict) -> FakeCursor:
        return FakeCursor([doc for doc in self.docs if self._matches(doc, query)])

    async def insert_one(self, document: dict) -> SimpleNamespace:
        document.setdefault("_id", ObjectId())
        self.docs.append(document)
        self.inserted.append(document)
        return SimpleNamespace(inserted_id=document["_id"])

    async def update_one(self, query: dict, update: dict) -> SimpleNamespace:
        self.updated.append((query, update))
        doc = await self.find_one(query)
        if not doc:
            return SimpleNamespace(matched_count=0, modified_count=0)
        for key, value in update.get("$set", {}).items():
            doc[key] = value
        for key in update.get("$unset", {}):
            doc.pop(key, None)
        for key, value in update.get("$push", {}).items():
            if isinstance(value, dict) and "$each" in value:
                doc.setdefault(key, []).extend(value["$each"])
            else:
                doc.setdefault(key, []).append(value)
        return SimpleNamespace(matched_count=1, modified_count=1)


def _build_upload_file() -> UploadFile:
    return UploadFile(file=BytesIO(b"unexpected"), filename="unexpected.txt")


def test_sms_response_does_not_mark_resolved_by_default() -> None:
    response = SMSResponseModel(message="Did you receive the RSVP link?")

    assert response.mark_resolved is False


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


def test_twilio_signature_validation_fails_closed_without_auth_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv(
        twilio_webhooks.TWILIO_UNSIGNED_WEBHOOK_BYPASS_ENV, raising=False
    )
    monkeypatch.setenv("ENVIRONMENT", "development")
    request = FakeRequest(FormData({"MessageSid": "SM123"}), "/webhook/twilio/status")

    assert (
        twilio_webhooks._validate_twilio_signature(
            request, None, {"MessageSid": "SM123"}
        )
        is False
    )


def test_twilio_signature_validation_allows_explicit_nonproduction_bypass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv(twilio_webhooks.TWILIO_UNSIGNED_WEBHOOK_BYPASS_ENV, "true")
    request = FakeRequest(FormData({"MessageSid": "SM123"}), "/webhook/twilio/status")

    assert (
        twilio_webhooks._validate_twilio_signature(
            request, None, {"MessageSid": "SM123"}
        )
        is True
    )


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


@pytest.mark.asyncio
async def test_incoming_guest_reply_appends_to_existing_public_help_ticket_without_auto_ack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ticket_id = ObjectId("65f000000000000000000101")
    now = datetime.now(timezone.utc)
    support_ticket = {
        "_id": ticket_id,
        "phone": "+15551234567",
        "message": "Public help request from Ayo Guest (Friend).",
        "guest_name": "Ayo Guest",
        "wedding_id": "wedding-1",
        "wedding_name": "Ayo & Casey",
        "assigned_to": "planner-a@example.com",
        "status": "new",
        "source": "sms",
        "origin": "public_help_form",
        "created_at": now,
        "updated_at": now,
        "is_read": True,
    }
    support_tickets = FakeCollection([support_ticket])
    planner_notifications = FakeCollection()
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
            get_guest_collection=lambda: FakeGuestCollection(),
            get_users_collection=lambda: FakeCollection(),
            db={
                "weddings": FakeCollection(),
                "support_tickets": support_tickets,
                "planner_notifications": planner_notifications,
                "errors": FakeCollection(),
            },
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "app.services.sms_service",
        SimpleNamespace(SMSService=FakeSMSService),
    )

    request = FakeRequest(
        FormData(
            {
                "From": "+15551234567",
                "Body": "Hello, I cannot RSVP",
                "MessageSid": "SM-inbound-help-reply-1",
            }
        ),
        "/webhook/twilio/incoming",
    )

    result = await twilio_webhooks.handle_twilio_incoming_message(request, None)

    assert result == {
        "status": "ok",
        "action": "support_ticket_reply",
        "ticket_id": str(ticket_id),
    }
    assert support_tickets.inserted == []
    assert sent_messages == []
    assert support_ticket["is_read"] is False
    assert support_ticket["status"] == "new"
    assert support_ticket["message_sid"] == "SM-inbound-help-reply-1"
    assert support_ticket["guest_messages"][-1]["message"] == "Hello, I cannot RSVP"
    assert planner_notifications.inserted
    assert planner_notifications.inserted[0]["planner_id"] == "planner-a@example.com"
    assert planner_notifications.inserted[0]["type"] == "guest_message"
    assert f"ticket_id={ticket_id}" in planner_notifications.inserted[0]["action_url"]


@pytest.mark.asyncio
async def test_incoming_guest_reply_duplicate_message_sid_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ticket_id = ObjectId("65f000000000000000000105")
    now = datetime.now(timezone.utc)
    support_ticket = {
        "_id": ticket_id,
        "phone": "+15551234567",
        "message": "Public help request from Ayo Guest (Friend).",
        "guest_name": "Ayo Guest",
        "wedding_id": "wedding-1",
        "wedding_name": "Ayo & Casey",
        "assigned_to": "planner-a@example.com",
        "status": "new",
        "source": "sms",
        "origin": "public_help_form",
        "created_at": now,
        "updated_at": now,
        "is_read": True,
        "guest_messages": [],
    }
    support_tickets = FakeCollection([support_ticket])
    planner_notifications = FakeCollection()

    class FakeSMSService:
        def send_sms(self, _to_number: str, _message: str) -> None:
            raise AssertionError("existing-thread replies should not auto-ack")

    monkeypatch.setattr(
        twilio_webhooks, "_validate_twilio_signature", lambda *_args, **_kwargs: True
    )
    monkeypatch.setattr(
        twilio_webhooks,
        "mongo",
        SimpleNamespace(
            get_guest_collection=lambda: FakeGuestCollection(),
            get_users_collection=lambda: FakeCollection(),
            db={
                "weddings": FakeCollection(),
                "support_tickets": support_tickets,
                "planner_notifications": planner_notifications,
                "errors": FakeCollection(),
            },
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "app.services.sms_service",
        SimpleNamespace(SMSService=FakeSMSService),
    )

    request = FakeRequest(
        FormData(
            {
                "From": "+15551234567",
                "Body": "Hello, I cannot RSVP",
                "MessageSid": "SM-inbound-help-retry-1",
            }
        ),
        "/webhook/twilio/incoming",
    )

    first = await twilio_webhooks.handle_twilio_incoming_message(request, None)
    second = await twilio_webhooks.handle_twilio_incoming_message(request, None)

    assert first["action"] == "support_ticket_reply"
    assert second["action"] == "support_ticket_reply"
    assert len(support_ticket["guest_messages"]) == 1
    assert support_ticket["guest_messages"][0]["message_sid"] == "SM-inbound-help-retry-1"
    assert len(planner_notifications.inserted) == 1


@pytest.mark.asyncio
async def test_help_keyword_appends_to_existing_public_help_ticket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ticket_id = ObjectId("65f000000000000000000106")
    now = datetime.now(timezone.utc)
    support_ticket = {
        "_id": ticket_id,
        "phone": "+15551234567",
        "message": "Public help request from Ayo Guest (Friend).",
        "guest_name": "Ayo Guest",
        "wedding_id": "wedding-1",
        "wedding_name": "Ayo & Casey",
        "assigned_to": "planner-a@example.com",
        "status": "new",
        "source": "sms",
        "origin": "public_help_form",
        "created_at": now,
        "updated_at": now,
        "is_read": True,
        "guest_messages": [],
    }
    support_tickets = FakeCollection([support_ticket])
    planner_notifications = FakeCollection()
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
            get_guest_collection=lambda: FakeGuestCollection(),
            get_users_collection=lambda: FakeCollection(),
            db={
                "weddings": FakeCollection(),
                "support_tickets": support_tickets,
                "planner_notifications": planner_notifications,
                "errors": FakeCollection(),
            },
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "app.services.sms_service",
        SimpleNamespace(SMSService=FakeSMSService),
    )

    request = FakeRequest(
        FormData(
            {
                "From": "+15551234567",
                "Body": "HELP",
                "MessageSid": "SM-inbound-help-keyword-1",
            }
        ),
        "/webhook/twilio/incoming",
    )

    result = await twilio_webhooks.handle_twilio_incoming_message(request, None)

    assert result == {
        "status": "ok",
        "action": "help_existing_ticket",
        "ticket_id": str(ticket_id),
    }
    assert sent_messages
    assert "the planner will respond by text" in sent_messages[0][1]
    assert support_ticket["guest_messages"][-1]["message"] == "HELP"
    assert planner_notifications.inserted[0]["planner_id"] == "planner-a@example.com"


@pytest.mark.asyncio
async def test_incoming_guest_reply_reopens_resolved_sms_ticket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ticket_id = ObjectId("65f000000000000000000102")
    now = datetime.now(timezone.utc)
    support_ticket = {
        "_id": ticket_id,
        "phone": "+15557654321",
        "message": "Public help request from Lee Guest (Cousin).",
        "guest_name": "Lee Guest",
        "wedding_id": "wedding-2",
        "wedding_name": "Lee & Morgan",
        "assigned_to": "planner-b@example.com",
        "status": "resolved",
        "source": "sms",
        "created_at": now,
        "updated_at": now,
        "resolved_at": now,
        "is_read": True,
        "responses": [{"message": "Try this link", "sent_at": now}],
    }
    support_tickets = FakeCollection([support_ticket])
    planner_notifications = FakeCollection()
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
            get_guest_collection=lambda: FakeGuestCollection(),
            get_users_collection=lambda: FakeCollection(),
            db={
                "weddings": FakeCollection(),
                "support_tickets": support_tickets,
                "planner_notifications": planner_notifications,
                "errors": FakeCollection(),
            },
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "app.services.sms_service",
        SimpleNamespace(SMSService=FakeSMSService),
    )

    request = FakeRequest(
        FormData(
            {
                "From": "+15557654321",
                "Body": "No, I still need help",
                "MessageSid": "SM-inbound-reopen-1",
            }
        ),
        "/webhook/twilio/incoming",
    )

    result = await twilio_webhooks.handle_twilio_incoming_message(request, None)

    assert result["action"] == "support_ticket_reply"
    assert support_tickets.inserted == []
    assert sent_messages == []
    assert support_ticket["status"] == "new"
    assert "resolved_at" not in support_ticket
    assert support_ticket["is_read"] is False
    assert support_ticket["guest_messages"][-1]["message"] == "No, I still need help"
    assert planner_notifications.inserted[0]["planner_id"] == "planner-b@example.com"


@pytest.mark.asyncio
async def test_inbound_sms_thread_lookup_rejects_ambiguous_cross_planner_phone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(timezone.utc)
    support_tickets = FakeCollection(
        [
            {
                "_id": ObjectId("65f000000000000000000103"),
                "phone": "+15558675309",
                "wedding_id": "wedding-a",
                "assigned_to": "planner-a@example.com",
                "status": "new",
                "source": "sms",
                "updated_at": now,
                "created_at": now,
            },
            {
                "_id": ObjectId("65f000000000000000000104"),
                "phone": "+15558675309",
                "wedding_id": "wedding-b",
                "assigned_to": "planner-b@example.com",
                "status": "new",
                "source": "sms",
                "updated_at": now,
                "created_at": now,
            },
        ]
    )
    monkeypatch.setattr(
        twilio_webhooks,
        "mongo",
        SimpleNamespace(db={"support_tickets": support_tickets}),
    )

    ticket = await twilio_webhooks._find_existing_sms_ticket_for_inbound("+15558675309")

    assert ticket is None
