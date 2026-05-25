import pytest

from app.services.email_service_resend import ResendEmailService
from app.services.reminder_service_twilio import TwilioReminderService
from app.utils.wedding_event_types import (
    ALL_WEDDING_EVENTS,
    attending_matches_reminder_event,
)


class AsyncCursor:
    def __init__(self, docs):
        self.docs = list(docs)
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.docs):
            raise StopAsyncIteration
        doc = self.docs[self.index]
        self.index += 1
        return doc

    async def to_list(self, length=None):
        if length is None:
            return list(self.docs)
        return list(self.docs[:length])


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])
        self.inserted = []

    def find(self, query=None, projection=None):
        return AsyncCursor(
            [doc for doc in self.docs if self._matches(doc, query or {})]
        )

    async def find_one(self, query=None, projection=None):
        for doc in self.docs:
            if self._matches(doc, query or {}):
                return doc
        return None

    async def insert_many(self, docs):
        self.inserted.extend(docs)

    def _matches(self, doc, query):
        for key, expected in query.items():
            value = doc.get(key)
            if isinstance(expected, dict) and "$in" in expected:
                if value not in expected["$in"]:
                    return False
            elif value != expected:
                return False
        return True


@pytest.mark.asyncio
async def test_twilio_all_events_sends_once_per_attendee_and_scopes_to_wedding():
    service = TwilioReminderService.__new__(TwilioReminderService)
    service.guest_collection = FakeCollection(
        [
            {
                "_id": "guest-one",
                "wedding_id": "wedding-one",
                "phone": "+15550000001",
                "sms_opt_in": True,
            },
            {
                "_id": "guest-two",
                "wedding_id": "wedding-one",
                "phone": "+15550000002",
                "sms_opt_in": True,
            },
            {
                "_id": "guest-other-wedding",
                "wedding_id": "wedding-two",
                "phone": "+15550000003",
                "sms_opt_in": True,
            },
        ]
    )
    service.rsvp_collection = FakeCollection(
        [
            {
                "guest_id": "guest-one",
                "attending": ["traditional", "white_wedding", "reception"],
            },
            {"guest_id": "guest-two", "attending": []},
            {"guest_id": "guest-other-wedding", "attending": ["traditional"]},
        ]
    )
    service.plus_one_collection = FakeCollection(
        [
            {
                "guest_id": "guest-one",
                "phone": "+15550000004",
                "sms_opt_in": True,
                "attending": ["white_wedding", "reception"],
            },
            {
                "guest_id": "guest-other-wedding",
                "phone": "+15550000005",
                "sms_opt_in": True,
                "attending": ["traditional"],
            },
        ]
    )
    service.log_collection = FakeCollection()
    sent_to = []

    def fake_send_sms(phone, message):
        sent_to.append(phone)
        return {"status": "success", "message_sid": None, "initial_status": "queued"}

    service._send_sms = fake_send_sms

    result = await service.send_reminders(
        ALL_WEDDING_EVENTS, "Reminder", "all", "wedding-one"
    )

    assert result["sent"] == 2
    assert sent_to == ["+15550000001", "+15550000004"]
    assert [log["event_type"] for log in service.log_collection.inserted] == [
        ALL_WEDDING_EVENTS,
        ALL_WEDDING_EVENTS,
    ]
    assert {log["wedding_id"] for log in service.log_collection.inserted} == {
        "wedding-one"
    }


@pytest.mark.asyncio
async def test_twilio_specific_event_keeps_existing_attendance_filter():
    service = TwilioReminderService.__new__(TwilioReminderService)
    service.guest_collection = FakeCollection(
        [
            {
                "_id": "guest-one",
                "wedding_id": "wedding-one",
                "phone": "+15550000001",
                "sms_opt_in": True,
            },
            {
                "_id": "guest-two",
                "wedding_id": "wedding-one",
                "phone": "+15550000002",
                "sms_opt_in": True,
            },
        ]
    )
    service.rsvp_collection = FakeCollection(
        [
            {"guest_id": "guest-one", "attending": ["traditional", "reception"]},
            {"guest_id": "guest-two", "attending": ["reception"]},
        ]
    )
    service.plus_one_collection = FakeCollection()
    service.log_collection = FakeCollection()
    sent_to = []
    service._send_sms = lambda phone, message: sent_to.append(phone) or "success"

    result = await service.send_reminders(
        "traditional", "Reminder", "guests", "wedding-one"
    )

    assert result["sent"] == 1
    assert sent_to == ["+15550000001"]


@pytest.mark.asyncio
async def test_email_all_events_sends_one_email_for_multi_event_guest(monkeypatch):
    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr("app.services.email_service_resend.asyncio.sleep", no_sleep)

    service = ResendEmailService.__new__(ResendEmailService)
    service.wedding_collection = FakeCollection(
        [
            {
                "_id": "wedding-one",
                "slug": "wedding-one-slug",
                "date": "2026-06-01",
                "couple_names": "A & B",
                "events": [
                    {"type": "traditional", "date": "2026-06-01"},
                    {"type": "reception", "date": "2026-06-02"},
                ],
            }
        ]
    )
    service.guest_collection = FakeCollection(
        [
            {
                "_id": "guest-one",
                "wedding_id": "wedding-one",
                "name": "Guest One",
                "email": "guest1@example.com",
                "email_opt_in": True,
            },
            {
                "_id": "guest-two",
                "wedding_id": "wedding-one",
                "email": "guest2@example.com",
                "email_opt_in": True,
            },
        ]
    )
    service.rsvp_collection = FakeCollection(
        [
            {"guest_id": "guest-one", "attending": ["traditional", "reception"]},
            {"guest_id": "guest-two", "attending": []},
        ]
    )
    sent_messages = []

    async def fake_send_email(**kwargs):
        sent_messages.append(kwargs)
        return {"success": True, "id": "email-id"}

    service.send_email = fake_send_email

    result = await service.send_reminders(
        wedding_slug="wedding-one-slug",
        event_type=ALL_WEDDING_EVENTS,
        custom_html="Hi {name}, {event_type}",
        target_group="guests",
    )

    assert result["sent"] == 1
    assert sent_messages[0]["to_email"] == "guest1@example.com"
    assert sent_messages[0]["subject"] == "Reminder: All Events - 2026-06-01"
    assert sent_messages[0]["html_content"] == "Hi Guest One, All Events"


def test_all_events_matches_any_non_empty_legacy_attendance_shape():
    assert attending_matches_reminder_event(["traditional", "reception"], "all")
    assert attending_matches_reminder_event(
        {"traditional": False, "reception": True}, "all"
    )
    assert not attending_matches_reminder_event([], "all")
    assert not attending_matches_reminder_event({"traditional": False}, "all")
