from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from bson import ObjectId
from fastapi import HTTPException

from app.services import support_service as support_service_module
from app.services.support_service import SupportService


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
    def __init__(self, documents: list[dict], find_one_result: dict | None = None) -> None:
        self.documents = documents
        self.find_one_result = find_one_result
        self.count_queries: list[dict] = []
        self.find_queries: list[dict] = []
        self.last_find_one_query: dict | None = None
        self.last_update_query: dict | None = None
        self.last_update_payload: dict | None = None

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


@pytest.mark.asyncio
async def test_get_tickets_excludes_sms_and_limits_to_active_statuses() -> None:
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
        exclude_sms=True,
        active_statuses=["open", "in_progress"],
    )

    expected_query = {
        "created_by": "planner@example.com",
        "$or": [{"source": {"$exists": False}}, {"source": {"$ne": "sms"}}],
        "status": {"$in": ["open", "in_progress"]},
    }
    assert tickets_collection.count_queries[0] == expected_query
    assert tickets_collection.find_queries[0] == expected_query


@pytest.mark.asyncio
async def test_add_comment_rejects_sms_support_tickets() -> None:
    service = SupportService()
    ticket = {
        "_id": ObjectId(),
        "created_by": "planner@example.com",
        "source": "sms",
        "status": "new",
    }
    service.tickets_collection = FakeTicketsCollection([], find_one_result=ticket)

    with pytest.raises(HTTPException) as exc_info:
        await service.add_comment(
            ticket_id=str(ticket["_id"]),
            comment_data={"message": "Replying from the wrong endpoint", "is_internal": False},
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
    }
    tickets_collection = FakeTicketsCollection([], find_one_result=ticket)
    activity_logs = FakeActivityLogsCollection()

    service = SupportService()
    service.tickets_collection = tickets_collection
    service.users_collection = FakeUsersCollection()
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
        comment_data={"message": "We are investigating this now.", "is_internal": False},
        current_user=SimpleNamespace(role="ROOT_ADMIN", email="root@example.com"),
    )

    assert result["message"] == "Comment added successfully"
    assert tickets_collection.last_update_payload is not None
    assert tickets_collection.last_update_payload["$set"]["status"] == "in_progress"
    assert tickets_collection.last_update_payload["$push"]["comments"]["message"] == (
        "We are investigating this now."
    )
