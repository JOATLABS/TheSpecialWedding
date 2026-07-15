from __future__ import annotations

from types import SimpleNamespace

import pytest
from bson import ObjectId
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.guest_help import GuestHelpRequest
from app.services.guest_help_service import GuestHelpRequestService


class FakeCollection:
    def __init__(self, find_one_result: dict | None = None) -> None:
        self.find_one_result = find_one_result
        self.find_one_queries: list[dict] = []
        self.inserted: list[dict] = []
        self.updated: list[tuple[dict, dict]] = []

    async def find_one(self, query: dict, *_args, **_kwargs) -> dict | None:
        self.find_one_queries.append(query)
        return self.find_one_result

    async def insert_one(self, document: dict) -> SimpleNamespace:
        document.setdefault("_id", ObjectId("65f000000000000000000001"))
        self.inserted.append(document)
        return SimpleNamespace(inserted_id=document["_id"])

    async def update_one(self, query: dict, update: dict) -> SimpleNamespace:
        self.updated.append((query, update))
        if self.inserted:
            self.inserted[0].update(update.get("$set", {}))
        return SimpleNamespace(modified_count=1)


class FakeSMSService:
    def __init__(self, *, success: bool = True) -> None:
        self.success = success
        self.sent: list[tuple[str, str]] = []

    def send_sms(self, to_phone: str, message: str) -> dict:
        self.sent.append((to_phone, message))
        if not self.success:
            return {"success": False, "provider": "twilio", "error": "not configured"}
        return {"success": True, "provider": "twilio", "message_id": "SM-help-1"}

    def get_provider_name(self) -> str:
        return "twilio"


class FakeNotificationService:
    def __init__(self) -> None:
        self.created: list[dict] = []

    async def create_notification(self, **kwargs) -> dict:
        self.created.append(kwargs)
        return {"id": "notification-1"}


def make_service(
    *,
    wedding: dict | None,
    guest: dict | None = None,
    sms_service: FakeSMSService | None = None,
) -> tuple[
    GuestHelpRequestService,
    FakeCollection,
    FakeCollection,
    FakeSMSService,
    FakeNotificationService,
]:
    service = GuestHelpRequestService()
    wedding_collection = FakeCollection(wedding)
    guest_collection = FakeCollection(guest)
    ticket_collection = FakeCollection()
    sms = sms_service or FakeSMSService()
    notification_service = FakeNotificationService()
    service.weddings_collection = wedding_collection
    service.guests_collection = guest_collection
    service.support_tickets_collection = ticket_collection
    service.sms_service_factory = lambda: sms
    service.notification_service_factory = lambda: notification_service
    service._memory_rate_limits.clear()
    return service, guest_collection, ticket_collection, sms, notification_service


@pytest.mark.asyncio
async def test_public_guest_help_request_creates_planner_scoped_sms_ticket_and_ack() -> (
    None
):
    wedding = {
        "_id": "wedding-1",
        "slug": "peace-emmanuel",
        "couple_names": "Peace & Emmanuel",
        "assigned_planner_email": "planner@example.com",
    }
    guest = {
        "_id": ObjectId("65f000000000000000000010"),
        "wedding_id": "wedding-1",
        "name": "Ayo Guest",
    }
    service, guest_collection, ticket_collection, sms, notifications = make_service(
        wedding=wedding, guest=guest
    )

    result = await service.create_help_request(
        slug="peace-emmanuel",
        full_name="Ayo Guest",
        phone="(682) 234-9448",
        relationship_to_couple="Bride's cousin",
    )

    assert result == {
        "success": True,
        "message": "Thanks. We sent you a text so the planner can help from the wedding inbox.",
        "ticket_id": "65f000000000000000000001",
    }
    assert guest_collection.find_one_queries[0]["wedding_id"] == "wedding-1"
    ticket = ticket_collection.inserted[0]
    assert ticket["phone"] == "+16822349448"
    assert ticket["guest_name"] == "Ayo Guest"
    assert ticket["guest_id"] == "65f000000000000000000010"
    assert ticket["wedding_id"] == "wedding-1"
    assert ticket["assigned_to"] == "planner@example.com"
    assert ticket["source"] == "sms"
    assert ticket["origin"] == "public_help_form"
    assert ticket["type"] == "help_request"
    assert ticket["priority"] == "high"
    assert ticket["is_read"] is False
    assert ticket["acknowledgment_sms"]["status"] == "sent"
    assert ticket_collection.updated[0][0] == {
        "_id": ObjectId("65f000000000000000000001"),
        "conversation_kind": "guest_sms",
        "source": "sms",
    }
    assert sms.sent == [
        (
            "+16822349448",
            "Thanks Ayo Guest. Reply to this text with your question for Peace & Emmanuel's planner. They will respond from the wedding inbox.",
        )
    ]
    assert notifications.created
    assert notifications.created[0]["planner_id"] == "planner@example.com"
    assert notifications.created[0]["metadata"]["ticket_id"] == result["ticket_id"]
    assert (
        notifications.created[0]["action_url"]
        == f"/admin/communications/inbox?conversation=sms_support&ticket_id={result['ticket_id']}&wedding_id=wedding-1"
    )


@pytest.mark.asyncio
async def test_public_guest_help_request_fails_closed_without_planner_owner() -> None:
    wedding = {
        "_id": "wedding-1",
        "slug": "peace-emmanuel",
        "couple_names": "Peace & Emmanuel",
    }
    service, _guest_collection, ticket_collection, sms, _notifications = make_service(
        wedding=wedding
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.create_help_request(
            slug="peace-emmanuel",
            full_name="Ayo Guest",
            phone="6822349448",
            relationship_to_couple="Friend",
        )

    assert exc_info.value.status_code == 409
    assert ticket_collection.inserted == []
    assert sms.sent == []


@pytest.mark.asyncio
async def test_public_guest_help_request_records_ticket_when_sms_ack_fails() -> None:
    wedding = {
        "_id": "wedding-1",
        "slug": "peace-emmanuel",
        "couple_names": "Peace & Emmanuel",
        "assigned_planner_email": "planner@example.com",
    }
    service, _guest_collection, ticket_collection, sms, _notifications = make_service(
        wedding=wedding,
        sms_service=FakeSMSService(success=False),
    )

    result = await service.create_help_request(
        slug="peace-emmanuel",
        full_name="Ayo Guest",
        phone="6822349448",
        relationship_to_couple="Friend",
    )

    assert result["success"] is True
    ticket = ticket_collection.inserted[0]
    assert ticket["acknowledgment_sms"]["status"] == "failed"
    assert ticket["acknowledgment_sms"]["error"] == "not configured"
    assert sms.sent


@pytest.mark.asyncio
async def test_public_guest_help_request_rate_limits_duplicate_slug_phone() -> None:
    wedding = {
        "_id": "wedding-1",
        "slug": "peace-emmanuel",
        "couple_names": "Peace & Emmanuel",
        "assigned_planner_email": "planner@example.com",
    }
    (
        service,
        _guest_collection,
        ticket_collection,
        _sms,
        _notifications,
    ) = make_service(wedding=wedding)
    service.max_help_requests_per_window = 1

    await service.create_help_request(
        slug="peace-emmanuel",
        full_name="Ayo Guest",
        phone="6822349448",
        relationship_to_couple="Friend",
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.create_help_request(
            slug="peace-emmanuel",
            full_name="Ayo Guest",
            phone="+1 (682) 234-9448",
            relationship_to_couple="Friend",
        )

    assert exc_info.value.status_code == 429
    assert len(ticket_collection.inserted) == 1


def test_public_guest_help_request_rejects_client_supplied_planner_identity() -> None:
    with pytest.raises(ValidationError):
        GuestHelpRequest(
            slug="peace-emmanuel",
            full_name="Ayo Guest",
            phone="6822349448",
            relationship_to_couple="Friend",
            assigned_to="other-planner@example.com",
        )
