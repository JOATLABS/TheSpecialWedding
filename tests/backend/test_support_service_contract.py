from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from bson import ObjectId
from fastapi import HTTPException

from app.services import support_service as support_service_module
from app.services import notification_service as notification_service_module
from app.services.support_service import SupportService
from app.api import support_management as support_management_module


class FakeCursor:
    def __init__(self, documents: list[dict]) -> None:
        self.documents = documents
        self._iterator = iter(())

    def sort(self, *_args, **_kwargs) -> "FakeCursor":
        return self

    def skip(self, *_args, **_kwargs) -> "FakeCursor":
        return self

    def limit(self, *_args, **_kwargs) -> "FakeCursor":
        return self

    def __aiter__(self) -> "FakeCursor":
        self._iterator = iter(self.documents)
        return self

    async def __anext__(self) -> dict:
        try:
            return next(self._iterator)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class FakeTicketsCollection:
    def __init__(
        self, documents: list[dict], find_one_result: dict | None = None
    ) -> None:
        self.documents = documents
        self.find_one_result = find_one_result
        self.count_queries: list[dict] = []
        self.find_queries: list[dict] = []
        self.last_find_one_query: dict | None = None
        self.last_update_query: dict | None = None
        self.last_update_payload: dict | None = None
        self.inserted_document: dict | None = None

    async def count_documents(self, query: dict) -> int:
        self.count_queries.append(query)
        return len(self.documents)

    def find(self, query: dict) -> FakeCursor:
        self.find_queries.append(query)
        return FakeCursor(self.documents)

    async def find_one(self, query: dict) -> dict | None:
        self.last_find_one_query = query
        return self.find_one_result

    async def update_one(self, query: dict, update: dict) -> SimpleNamespace:
        self.last_update_query = query
        self.last_update_payload = update
        return SimpleNamespace(modified_count=1)

    async def insert_one(self, document: dict) -> SimpleNamespace:
        self.inserted_document = document
        return SimpleNamespace(inserted_id=document["_id"])


class FakeUsersCollection:
    async def find_one(self, *_args, **_kwargs) -> dict:
        return {
            "first_name": "Taylor",
            "last_name": "Planner",
            "company_name": "Taylor Weddings",
        }


class FakeActivityLogsCollection:
    def __init__(self) -> None:
        self.records: list[dict] = []

    async def insert_one(self, payload: dict) -> None:
        self.records.append(payload)


class FakeReadStatesCollection:
    def __init__(self) -> None:
        self.states: dict[tuple[str, str], dict] = {}

    async def find_one(self, query: dict) -> dict | None:
        return self.states.get((query["ticket_id"], query["actor_key"]))

    async def update_one(
        self, query: dict, update: dict, *, upsert: bool = False
    ) -> SimpleNamespace:
        assert upsert is True
        self.states[(query["ticket_id"], query["actor_key"])] = update["$set"]
        return SimpleNamespace(modified_count=1)


@pytest.mark.asyncio
async def test_create_ticket_notification_links_root_to_exact_support_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_notifications: list[dict] = []

    class FakeNotificationService:
        async def create_notification(self, notification_data: dict, created_by: str):
            captured_notifications.append(notification_data)
            return {"id": "notification-1"}

    tickets_collection = FakeTicketsCollection([])
    service = SupportService()
    service.tickets_collection = tickets_collection
    service.read_states_collection = FakeReadStatesCollection()
    monkeypatch.setattr(
        notification_service_module,
        "NotificationService",
        FakeNotificationService,
    )
    monkeypatch.setattr(
        support_service_module,
        "mongo",
        SimpleNamespace(db={"activity_logs": FakeActivityLogsCollection()}),
    )
    monkeypatch.setattr(service, "_send_new_ticket_notification", AsyncMock())

    result = await service.create_ticket(
        ticket_data={
            "subject": "Need help",
            "description": "Please review this issue.",
            "priority": "high",
            "category": "technical",
        },
        current_user=SimpleNamespace(
            email="planner@example.com",
            role="wedding_planner",
            user_data={"_id": "planner-user-1"},
            is_wedding_planner=True,
            is_team_member=False,
            parent_planner_id=None,
        ),
    )

    assert captured_notifications[0]["action_url"] == (
        "/admin/communications/inbox?conversation=support_ticket"
        f"&ticket_id={result['id']}"
    )
    assert tickets_collection.inserted_document is not None
    assert tickets_collection.inserted_document["conversation_kind"] == (
        "platform_support"
    )
    assert tickets_collection.inserted_document["creator_user_id"] == ("planner-user-1")
    assert tickets_collection.inserted_document["creator_role"] == ("wedding_planner")
    assert tickets_collection.inserted_document["owner_planner_id"] == (
        "planner-user-1"
    )


@pytest.mark.asyncio
async def test_create_ticket_route_rejects_inaccessible_wedding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_ticket = AsyncMock()
    monkeypatch.setattr(
        support_management_module,
        "check_wedding_access",
        AsyncMock(return_value=False),
        raising=False,
    )
    monkeypatch.setattr(
        support_management_module.support_service,
        "create_ticket",
        create_ticket,
    )
    ticket_data = support_management_module.TicketCreateModel(
        subject="Wedding-specific issue",
        description="This wedding is outside the caller scope.",
        wedding_id="foreign-wedding",
    )
    current_user = SimpleNamespace(
        email="planner@example.com",
        role="wedding_planner",
        is_root_admin=False,
    )

    with pytest.raises(HTTPException) as exc_info:
        await support_management_module.create_ticket(ticket_data, current_user)

    assert exc_info.value.status_code == 403
    create_ticket.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_tickets_selects_platform_support_and_limits_to_active_statuses() -> (
    None
):
    service = SupportService()
    documents = [
        {
            "_id": ObjectId(),
            "ticket_number": "TKT-20260408-1234",
            "subject": "Need help",
            "priority": "medium",
            "status": "open",
            "created_at": support_service_module.datetime.now(
                support_service_module.timezone.utc
            ),
            "created_by": "planner@example.com",
            "comments": [],
            "category": "general",
        }
    ]
    tickets_collection = FakeTicketsCollection(documents)
    service.tickets_collection = tickets_collection
    service.users_collection = FakeUsersCollection()

    await service.get_tickets(
        page=1,
        limit=20,
        filters={"created_by": "planner@example.com"},
        platform_support_only=True,
        active_statuses=["open", "in_progress"],
    )

    expected_query = {
        "created_by": "planner@example.com",
        "conversation_kind": "platform_support",
        "status": {"$in": ["open", "in_progress"]},
    }
    assert tickets_collection.count_queries[0] == expected_query
    assert tickets_collection.find_queries[0] == expected_query


@pytest.mark.asyncio
async def test_planner_ticket_list_hides_internal_comments_and_reports_unread() -> None:
    service = SupportService()
    ticket_id = ObjectId()
    documents = [
        {
            "_id": ticket_id,
            "ticket_number": "TKT-20260408-9876",
            "conversation_kind": "platform_support",
            "subject": "Need help",
            "priority": "medium",
            "status": "open",
            "created_at": support_service_module.datetime.now(
                support_service_module.timezone.utc
            ),
            "updated_at": support_service_module.datetime.now(
                support_service_module.timezone.utc
            ),
            "created_by": "planner@example.com",
            "comments": [
                {"message": "Visible response", "is_internal": False},
                {"message": "Private root note", "is_internal": True},
            ],
            "category": "general",
        }
    ]
    service.tickets_collection = FakeTicketsCollection(documents)
    service.users_collection = FakeUsersCollection()
    service.read_states_collection = FakeReadStatesCollection()

    result = await service.get_tickets(
        filters={"created_by": "planner@example.com"},
        platform_support_only=True,
        current_user=SimpleNamespace(
            email="planner@example.com",
            user_data={"_id": "planner-user-1"},
        ),
        include_internal_comments=False,
    )

    assert [comment["message"] for comment in result["tickets"][0]["comments"]] == [
        "Visible response"
    ]
    assert result["tickets"][0]["is_read"] is False
    assert result["unread_count"] == 1


@pytest.mark.asyncio
async def test_add_comment_rejects_sms_support_tickets() -> None:
    service = SupportService()
    ticket = {
        "_id": ObjectId(),
        "created_by": "planner@example.com",
        "source": "sms",
        "conversation_kind": "guest_sms",
        "status": "new",
    }
    service.tickets_collection = FakeTicketsCollection([], find_one_result=ticket)

    with pytest.raises(HTTPException) as exc_info:
        await service.add_comment(
            ticket_id=str(ticket["_id"]),
            comment_data={
                "message": "Replying from the wrong endpoint",
                "is_internal": False,
            },
            current_user=SimpleNamespace(role="ROOT_ADMIN", email="root@example.com"),
        )

    assert exc_info.value.status_code == 400
    assert "SMS support tickets" in exc_info.value.detail


@pytest.mark.asyncio
async def test_add_comment_sets_ticket_in_progress_for_root_admin_public_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ticket = {
        "_id": ObjectId(),
        "created_by": "planner@example.com",
        "status": "open",
        "ticket_number": "TKT-20260408-4321",
        "subject": "Planner issue",
        "source": None,
        "conversation_kind": "platform_support",
    }
    tickets_collection = FakeTicketsCollection([], find_one_result=ticket)
    activity_logs = FakeActivityLogsCollection()

    service = SupportService()
    service.tickets_collection = tickets_collection
    service.users_collection = FakeUsersCollection()
    service.read_states_collection = FakeReadStatesCollection()
    monkeypatch.setattr(
        service,
        "_notify_planner_ticket_response",
        AsyncMock(),
    )
    monkeypatch.setattr(
        support_service_module,
        "mongo",
        SimpleNamespace(db={"activity_logs": activity_logs}),
    )

    result = await service.add_comment(
        ticket_id=str(ticket["_id"]),
        comment_data={
            "message": "We are investigating this now.",
            "is_internal": False,
        },
        current_user=SimpleNamespace(
            role="ROOT_ADMIN",
            email="root@example.com",
            user_data={"_id": "root-user"},
            is_root_admin=True,
        ),
    )

    assert result["message"] == "Comment added successfully"
    assert tickets_collection.last_update_payload is not None
    assert tickets_collection.last_update_payload["$set"]["status"] == "in_progress"
    assert tickets_collection.last_update_payload["$push"]["comments"]["message"] == (
        "We are investigating this now."
    )


@pytest.mark.asyncio
async def test_update_ticket_rejects_foreign_non_root_content_update() -> None:
    ticket = {
        "_id": ObjectId(),
        "created_by": "owner@example.com",
        "source": None,
        "conversation_kind": "platform_support",
        "status": "open",
    }
    service = SupportService()
    service.tickets_collection = FakeTicketsCollection([], find_one_result=ticket)

    with pytest.raises(HTTPException) as exc_info:
        await service.update_ticket(
            ticket_id=str(ticket["_id"]),
            update_data={
                "subject": "Changed by another planner",
                "description": "This ticket belongs to someone else.",
            },
            current_user=SimpleNamespace(
                role="WEDDING_PLANNER",
                email="other-planner@example.com",
            ),
        )

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_update_ticket_uses_stable_creator_id_before_email_snapshot() -> None:
    ticket = {
        "_id": ObjectId(),
        "created_by": "shared@example.com",
        "creator_user_id": "original-user",
        "conversation_kind": "platform_support",
        "status": "open",
    }
    service = SupportService()
    service.tickets_collection = FakeTicketsCollection([], find_one_result=ticket)

    with pytest.raises(HTTPException) as exc_info:
        await service.update_ticket(
            ticket_id=str(ticket["_id"]),
            update_data={"subject": "Attempted takeover"},
            current_user=SimpleNamespace(
                role="wedding_planner",
                email="shared@example.com",
                user_data={"_id": "replacement-user"},
                is_root_admin=False,
            ),
        )

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_update_ticket_does_not_trust_unverified_root_role_string() -> None:
    ticket = {
        "_id": ObjectId(),
        "created_by": "owner@example.com",
        "source": None,
        "conversation_kind": "platform_support",
        "status": "open",
    }
    service = SupportService()
    service.tickets_collection = FakeTicketsCollection([], find_one_result=ticket)

    with pytest.raises(HTTPException) as exc_info:
        await service.update_ticket(
            ticket_id=str(ticket["_id"]),
            update_data={"status": "resolved"},
            current_user=SimpleNamespace(
                role="ROOT_ADMIN",
                email="forged-root@example.com",
                is_root_admin=False,
            ),
        )

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_update_ticket_allows_verified_root_operational_fields() -> None:
    ticket = {
        "_id": ObjectId(),
        "created_by": "owner@example.com",
        "source": None,
        "conversation_kind": "platform_support",
        "status": "open",
    }
    tickets_collection = FakeTicketsCollection([], find_one_result=ticket)
    service = SupportService()
    service.tickets_collection = tickets_collection

    result = await service.update_ticket(
        ticket_id=str(ticket["_id"]),
        update_data={"status": "resolved"},
        current_user=SimpleNamespace(
            role="ROOT_ADMIN",
            email="root@example.com",
            is_root_admin=True,
        ),
    )

    assert result["message"] == "Ticket updated successfully"
    assert tickets_collection.last_update_query == {
        "_id": ticket["_id"],
        "conversation_kind": "platform_support",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("status", "resolved"),
        ("priority", "urgent"),
        ("assigned_to", "root@example.com"),
    ],
)
async def test_update_ticket_rejects_root_only_fields_from_ticket_owner(
    field: str,
    value: str,
) -> None:
    ticket = {
        "_id": ObjectId(),
        "created_by": "planner@example.com",
        "source": None,
        "conversation_kind": "platform_support",
        "status": "open",
    }
    service = SupportService()
    service.tickets_collection = FakeTicketsCollection([], find_one_result=ticket)

    with pytest.raises(HTTPException) as exc_info:
        await service.update_ticket(
            ticket_id=str(ticket["_id"]),
            update_data={field: value},
            current_user=SimpleNamespace(
                role="WEDDING_PLANNER",
                email="planner@example.com",
            ),
        )

    assert exc_info.value.status_code == 403
