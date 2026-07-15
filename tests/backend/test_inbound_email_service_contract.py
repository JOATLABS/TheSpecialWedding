from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from bson import ObjectId

from app.api import inbound_emails as inbound_api
from app.services import inbound_email_service as inbound_module
from app.services.inbound_email_service import InboundEmailService


class FakeCursor:
    def __init__(self, documents: list[dict]) -> None:
        self.documents = documents
        self._iterator = iter(())

    def sort(self, *_args) -> "FakeCursor":
        return self

    def __aiter__(self) -> "FakeCursor":
        self._iterator = iter(self.documents)
        return self

    async def __anext__(self) -> dict:
        try:
            return next(self._iterator)
        except StopIteration as error:
            raise StopAsyncIteration from error


class FakeCollection:
    def __init__(
        self,
        documents: list[dict] | None = None,
        find_one_result: dict | None = None,
    ) -> None:
        self.documents = documents or []
        self.find_one_result = find_one_result
        self.find_queries: list[dict] = []
        self.find_one_calls: list[tuple[dict, dict | None]] = []

    def find(self, query: dict) -> FakeCursor:
        self.find_queries.append(query)
        return FakeCursor(self.documents)

    async def find_one(
        self, query: dict, projection: dict | None = None
    ) -> dict | None:
        self.find_one_calls.append((query, projection))
        return self.find_one_result


def test_assigned_team_member_inbound_scope_is_limited_to_assigned_weddings() -> None:
    scope = InboundEmailService._planner_scope(
        "planner@example.com",
        accessible_wedding_ids=["wedding-a", "wedding-b"],
    )

    assert scope == {
        "$and": [
            {
                "$or": [
                    {"thread_context.assigned_planner_email": "planner@example.com"},
                    {
                        "thread_context.assigned_planner_email": {"$exists": False},
                        "thread_context.planner_id": "planner@example.com",
                    },
                ]
            },
            {"thread_context.wedding_id": {"$in": ["wedding-a", "wedding-b"]}},
        ]
    }


def test_assigned_team_member_with_no_weddings_gets_fail_closed_scope() -> None:
    scope = InboundEmailService._planner_scope(
        "planner@example.com",
        accessible_wedding_ids=[],
    )

    assert scope["$and"][1] == {"thread_context.wedding_id": {"$in": []}}


@pytest.mark.asyncio
async def test_inbox_route_passes_team_owner_and_assignment_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_inbox = AsyncMock(return_value={"emails": []})
    monkeypatch.setattr(
        inbound_api,
        "inbound_email_service",
        SimpleNamespace(get_inbox=get_inbox),
    )
    team_member = SimpleNamespace(
        email="teammate@example.com",
        is_root_admin=False,
        is_wedding_planner=False,
        is_team_member=True,
        team_owner_email="planner@example.com",
        team_wedding_access="assigned",
        team_assigned_wedding_ids=["wedding-a"],
    )

    await inbound_api.get_inbox(
        page=1,
        limit=20,
        wedding_id=None,
        unread_only=False,
        current_user=team_member,
    )

    get_inbox.assert_awaited_once_with(
        planner_id="planner@example.com",
        wedding_id=None,
        page=1,
        limit=20,
        unread_only=False,
        accessible_wedding_ids=["wedding-a"],
    )


@pytest.mark.asyncio
async def test_thread_does_not_return_global_outbound_logs_without_owned_inbound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inbound = FakeCollection([])
    outbound = FakeCollection(
        [
            {
                "_id": ObjectId(),
                "thread_id": "wedding-shared-slug",
                "wedding_id": "foreign-wedding",
                "subject": "Foreign tenant email",
                "sent_at": datetime.now(timezone.utc),
            }
        ]
    )
    monkeypatch.setattr(
        inbound_module,
        "mongo",
        SimpleNamespace(
            db={"inbound_emails": inbound, "email_logs": outbound},
        ),
    )

    result = await InboundEmailService().get_thread(
        "wedding-shared-slug",
        "planner@example.com",
    )

    assert result["emails"] == []
    assert outbound.find_queries == []


@pytest.mark.asyncio
async def test_reply_context_uses_canonical_wedding_owner_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wedding_id = ObjectId()
    weddings = FakeCollection(
        find_one_result={
            "_id": wedding_id,
            "assigned_planner_id": "planner-user-1",
            "assigned_planner_email": "planner@example.com",
        }
    )
    guests = FakeCollection()
    monkeypatch.setattr(
        inbound_module,
        "mongo",
        SimpleNamespace(
            db={"weddings": weddings},
            get_guest_collection=lambda: guests,
        ),
    )

    context = await InboundEmailService()._decode_reply_to_and_resolve(
        "reply+wedding-slug@thespecialwedding.io",
        "guest@example.com",
    )

    assert context["assigned_planner_id"] == "planner-user-1"
    assert context["assigned_planner_email"] == "planner@example.com"
    assert "planner_id" not in context
    projection = weddings.find_one_calls[0][1]
    assert projection is not None
    assert "assigned_planner_id" in projection
    assert "assigned_planner_email" in projection
