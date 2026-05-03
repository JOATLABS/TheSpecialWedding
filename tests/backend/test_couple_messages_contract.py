"""Contract tests for the couple<->planner messaging endpoints.

These tests lock in the behaviors that regressed in the "logged out, logged
back in, my own message came back as an incoming message" bug:

- Inserts stamp `sender_role` and `sender_email` from the authenticated
  principal, not from a role-based sentinel or reverse lookup.
- GET responses expose `sender_email` so the frontend can compare message
  authorship against the logged-in principal's email (the load-bearing
  identity) instead of trusting role-only server routing.
- GETs include a `next_cursor` so clients can walk older history without
  guessing the cursor field name from the sort order.
- Planner notification is a *best-effort* side-effect: a failure in the
  notification service (or in the planner-email lookup) must NOT 500 the
  couple's send once the message has persisted.
- `sender_role` filters in mark-read, unread-count, and the conversations
  aggregation route through the centralized enum constants.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from bson import ObjectId

from app.api import couple_portal as couple_portal_api
from app.dependencies.auth_extended import ExtendedAuthUser
from app.utils.messaging_roles import SENDER_ROLE_COUPLE, SENDER_ROLE_PLANNER


# ---------------------------------------------------------------------------
# Fakes — minimal Mongo shims that just capture calls and return fixtures.
# ---------------------------------------------------------------------------


class _FakeCursor:
    """Mimics the async chain `collection.find(q).sort(...).limit(...)`."""

    def __init__(self, docs: list[dict]) -> None:
        # Store a copy so test-local mutations don't mutate the fixture.
        self._docs = [copy.deepcopy(d) for d in docs]
        self._sort_key: str | None = None
        self._sort_dir: int = 1
        self._limit: int | None = None

    def sort(self, key: str, direction: int) -> "_FakeCursor":
        self._sort_key = key
        self._sort_dir = direction
        return self

    def limit(self, n: int) -> "_FakeCursor":
        self._limit = n
        return self

    def __aiter__(self) -> "_FakeCursor":
        if self._sort_key is not None:
            self._docs.sort(
                key=lambda d: d.get(self._sort_key),
                reverse=self._sort_dir < 0,
            )
        if self._limit is not None:
            self._docs = self._docs[: self._limit]
        self._iter = iter(self._docs)
        return self

    async def __anext__(self) -> dict:
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class _FakeMessagesCollection:
    """Fake for `mongo.db['couple_messages']`."""

    def __init__(self, seed: list[dict] | None = None) -> None:
        self.docs: list[dict] = [copy.deepcopy(d) for d in (seed or [])]
        self.insert_calls: list[dict] = []
        self.update_many_calls: list[tuple[dict, dict]] = []
        self.count_calls: list[dict] = []
        self.aggregate_calls: list[list[dict]] = []

    async def insert_one(self, doc: dict) -> SimpleNamespace:
        captured = copy.deepcopy(doc)
        self.insert_calls.append(captured)
        inserted_id = ObjectId()
        stored = copy.deepcopy(doc)
        stored["_id"] = inserted_id
        self.docs.append(stored)
        return SimpleNamespace(inserted_id=inserted_id)

    def find(self, query: dict) -> _FakeCursor:
        self.last_find_query = copy.deepcopy(query)
        matching: list[dict] = []
        for doc in self.docs:
            if self._matches(doc, query):
                matching.append(doc)
        return _FakeCursor(matching)

    async def update_many(self, query: dict, update: dict) -> SimpleNamespace:
        self.update_many_calls.append((copy.deepcopy(query), copy.deepcopy(update)))
        modified = 0
        for doc in self.docs:
            if self._matches(doc, query):
                for key, value in update.get("$set", {}).items():
                    doc[key] = value
                modified += 1
        return SimpleNamespace(modified_count=modified)

    async def count_documents(self, query: dict) -> int:
        self.count_calls.append(copy.deepcopy(query))
        return sum(1 for doc in self.docs if self._matches(doc, query))

    def aggregate(self, pipeline: list[dict]) -> "_FakeAggregateCursor":
        self.aggregate_calls.append(copy.deepcopy(pipeline))
        # We don't execute the pipeline — tests inspect the pipeline shape
        # directly via `.aggregate_calls` and use this fake only to satisfy
        # the `.to_list(length=None)` call.
        return _FakeAggregateCursor()

    @staticmethod
    def _matches(doc: dict, query: dict) -> bool:
        for key, expected in query.items():
            actual = doc.get(key)
            if isinstance(expected, dict) and "$lt" in expected:
                if actual is None or not (actual < expected["$lt"]):
                    return False
                continue
            if actual != expected:
                return False
        return True


class _FakeUpdatesCollection:
    """Fake for `mongo.db['couple_updates']`."""

    def __init__(self) -> None:
        self.insert_calls: list[dict] = []

    async def insert_one(self, doc: dict) -> SimpleNamespace:
        self.insert_calls.append(copy.deepcopy(doc))
        return SimpleNamespace(inserted_id=ObjectId())


class _FakeAggregateCursor:
    async def to_list(self, length: int | None = None) -> list[dict]:
        return []


class _FakeToListCursor:
    """Cursor whose `.to_list(...)` returns a configured list of docs."""

    def __init__(self, docs: list[dict]) -> None:
        self._docs = docs

    async def to_list(self, length: int | None = None) -> list[dict]:
        return [copy.deepcopy(d) for d in self._docs]


class _FakeCouplesCollection:
    """Fake for `mongo.db['couple_users']`.

    Supports `.find_one(...)` (used by planner-send) and `.find(...).to_list(...)`
    (used by planner-list-conversations).
    """

    def __init__(self, docs: list[dict] | None = None) -> None:
        self.docs: list[dict] = list(docs or [])

    async def find_one(
        self, query: dict, projection: dict | None = None
    ) -> dict | None:
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                return copy.deepcopy(doc)
        return None

    def find(self, *_args: Any, **_kwargs: Any) -> _FakeToListCursor:
        return _FakeToListCursor(self.docs)


class _FakeDB:
    def __init__(
        self,
        messages: _FakeMessagesCollection,
        couples: _FakeCouplesCollection | None = None,
        updates: _FakeUpdatesCollection | None = None,
    ) -> None:
        self._messages = messages
        self._couples = couples or _FakeCouplesCollection()
        self._updates = updates or _FakeUpdatesCollection()

    def __getitem__(self, name: str) -> Any:
        if name == "couple_messages":
            return self._messages
        if name == "couple_users":
            return self._couples
        if name == "couple_updates":
            return self._updates
        raise KeyError(name)


class _ImmediateBestEffort:
    async def run(self, coro_factory):
        try:
            return await coro_factory()
        except Exception:
            return None


def _immediate_best_effort(**_kwargs) -> _ImmediateBestEffort:
    return _ImmediateBestEffort()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def couple_doc() -> dict:
    return {
        "_id": "couple-1",
        "email": "emmanuel@example.com",
        "wedding_id": "wedding-1",
        "partner1_name": "Emmanuel",
        "partner2_name": "Partner",
        "wedding_archived": False,
    }


@pytest.fixture
def planner_user() -> ExtendedAuthUser:
    user = ExtendedAuthUser(
        "planner@example.com",
        "wedding_planner",
        {"_id": "owner-1", "first_name": "Pat", "last_name": "Planner"},
    )
    user.team_permissions = {"message_couples": True, "manage_couple_portal": True}
    return user


@pytest.fixture
def messages_collection() -> _FakeMessagesCollection:
    return _FakeMessagesCollection()


@pytest.fixture
def patched_mongo(
    monkeypatch: pytest.MonkeyPatch,
    messages_collection: _FakeMessagesCollection,
) -> _FakeMessagesCollection:
    """Install a fake mongo on `couple_portal` for the duration of the test."""

    async def _find_one(query: dict, projection: dict | None = None) -> dict:
        return {"_id": "wedding-1"}

    fake_mongo = SimpleNamespace(
        db=_FakeDB(messages_collection),
        get_weddings_collection=lambda: SimpleNamespace(find_one=_find_one),
    )
    monkeypatch.setattr(couple_portal_api, "mongo", fake_mongo)
    return messages_collection


@pytest.fixture
def stub_broadcasts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub out the broadcast helpers; tests here don't cover SSE wiring."""
    monkeypatch.setattr(
        couple_portal_api,
        "_broadcast_couple_message_change",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        couple_portal_api,
        "_resolve_couple_planner_email",
        AsyncMock(return_value="planner@example.com"),
    )


# ---------------------------------------------------------------------------
# C1/H1/H2 — couple-send stamps identity correctly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_couple_send_stamps_couple_role_email_and_display_name(
    couple_doc: dict,
    patched_mongo: _FakeMessagesCollection,
    stub_broadcasts: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.planner_notification_service.planner_notification_service.create_notification",
        AsyncMock(return_value={}),
    )

    data = couple_portal_api.SendMessageRequest(content="Hello planner")

    response = await couple_portal_api.couple_send_message(data, couple=couple_doc)

    assert response["message"] == "Message sent"
    assert "message_id" in response

    assert len(patched_mongo.insert_calls) == 1
    inserted = patched_mongo.insert_calls[0]
    # The load-bearing identity claim — this is what the bug broke.
    assert inserted["sender_role"] == SENDER_ROLE_COUPLE
    assert inserted["sender_email"] == "emmanuel@example.com"
    assert inserted["sender_name"] == "Emmanuel & Partner"
    assert inserted["wedding_id"] == "wedding-1"
    assert inserted["read_by_couple"] is True
    assert inserted["read_by_planner"] is False


@pytest.mark.asyncio
async def test_couple_send_falls_back_to_email_when_names_missing(
    patched_mongo: _FakeMessagesCollection,
    stub_broadcasts: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.planner_notification_service.planner_notification_service.create_notification",
        AsyncMock(return_value={}),
    )
    nameless_couple = {
        "_id": "couple-2",
        "email": "nameless@example.com",
        "wedding_id": "wedding-1",
        "partner1_name": "",
        "partner2_name": "",
    }
    data = couple_portal_api.SendMessageRequest(content="hi")

    await couple_portal_api.couple_send_message(data, couple=nameless_couple)

    inserted = patched_mongo.insert_calls[0]
    assert inserted["sender_name"] == "nameless@example.com"
    assert inserted["sender_email"] == "nameless@example.com"


# ---------------------------------------------------------------------------
# M1 — best-effort notification: message still persists when notifier fails
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_couple_send_returns_success_when_notification_service_fails(
    couple_doc: dict,
    patched_mongo: _FakeMessagesCollection,
    stub_broadcasts: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If notification retries all fail, the send still returns 200.

    This is the M1 contract: the message is the source of truth for the
    operation, the notification is a side-effect. We verify by checking the
    message persists and the HTTP handler returns normally.
    """
    failing_notify = AsyncMock(side_effect=RuntimeError("service down"))
    monkeypatch.setattr(
        "app.services.planner_notification_service.planner_notification_service.create_notification",
        failing_notify,
    )

    data = couple_portal_api.SendMessageRequest(content="still sends")

    response = await couple_portal_api.couple_send_message(data, couple=couple_doc)

    assert response["message"] == "Message sent"
    assert len(patched_mongo.insert_calls) == 1
    # Retries: initial + 2 retries = 3 attempts total (default max_retries=3).
    assert failing_notify.await_count == 3


@pytest.mark.asyncio
async def test_couple_send_returns_success_when_planner_lookup_fails(
    couple_doc: dict,
    patched_mongo: _FakeMessagesCollection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the planner-email lookup raises, the send must still return 200.

    This locks in the Critical #1 fix: the lookup is inside the best-effort
    block, not outside it.
    """
    monkeypatch.setattr(
        couple_portal_api,
        "_broadcast_couple_message_change",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        couple_portal_api,
        "_resolve_couple_planner_email",
        AsyncMock(side_effect=RuntimeError("mongo blip")),
    )

    data = couple_portal_api.SendMessageRequest(content="persist me")

    response = await couple_portal_api.couple_send_message(data, couple=couple_doc)

    assert response["message"] == "Message sent"
    # Message persisted even though the lookup blew up on every retry.
    assert len(patched_mongo.insert_calls) == 1


# ---------------------------------------------------------------------------
# C2 + M2 — couple GET exposes sender_email and next_cursor
# ---------------------------------------------------------------------------


def _seed_messages(
    collection: _FakeMessagesCollection, *, n: int, wedding_id: str = "wedding-1"
) -> list[ObjectId]:
    """Insert `n` messages alternating couple/planner; return ids oldest→newest."""
    ids: list[ObjectId] = []
    base = datetime(2026, 4, 1, 0, 0, 0, tzinfo=timezone.utc)
    for i in range(n):
        oid = ObjectId()
        role = SENDER_ROLE_COUPLE if i % 2 == 0 else SENDER_ROLE_PLANNER
        email = (
            "emmanuel@example.com"
            if role == SENDER_ROLE_COUPLE
            else "planner@example.com"
        )
        name = "Emmanuel & Partner" if role == SENDER_ROLE_COUPLE else "Pat Planner"
        collection.docs.append(
            {
                "_id": oid,
                "wedding_id": wedding_id,
                "sender_role": role,
                "sender_email": email,
                "sender_name": name,
                "content": f"msg {i}",
                "read_by_couple": role == SENDER_ROLE_COUPLE,
                "read_by_planner": role == SENDER_ROLE_PLANNER,
                "created_at": base,
            }
        )
        ids.append(oid)
    return ids


@pytest.mark.asyncio
async def test_couple_get_strips_sender_email_on_every_message(
    couple_doc: dict,
    patched_mongo: _FakeMessagesCollection,
) -> None:
    """SECURITY: Planner/team login emails must never be exposed on the
    couple-facing GET response. Identity-first authorship on the couple
    dashboard falls back to `sender_role` comparison
    (see app/types/messaging.ts → `isSelfAuthored`).

    The planner-facing GET still projects `sender_email` — that surface is
    covered by `test_planner_get_exposes_sender_email_and_next_cursor`.
    """
    _seed_messages(patched_mongo, n=3)

    response = await couple_portal_api.couple_get_messages(
        couple=couple_doc, limit=50, before=None
    )

    assert len(response["messages"]) == 3
    for msg in response["messages"]:
        assert "sender_email" not in msg, (
            "sender_email leak on couple-facing GET — planner/team login "
            "emails must not be exposed to the couple portal"
        )


@pytest.mark.asyncio
async def test_couple_get_returns_next_cursor_when_page_is_full(
    couple_doc: dict,
    patched_mongo: _FakeMessagesCollection,
) -> None:
    ids = _seed_messages(patched_mongo, n=5)

    response = await couple_portal_api.couple_get_messages(
        couple=couple_doc, limit=3, before=None
    )

    assert len(response["messages"]) == 3
    # next_cursor points to the oldest of the returned page (i.e., the one to
    # pass as `before=` on the next request). Seeded oldest→newest is ids[0]
    # through ids[4]; sort is `_id` DESC, so newest 3 = ids[4], ids[3], ids[2];
    # after chronological reverse: ids[2], ids[3], ids[4]; cursor = ids[2].
    assert response["next_cursor"] == str(ids[2])


@pytest.mark.asyncio
async def test_couple_get_returns_null_cursor_when_page_not_full(
    couple_doc: dict,
    patched_mongo: _FakeMessagesCollection,
) -> None:
    _seed_messages(patched_mongo, n=2)

    response = await couple_portal_api.couple_get_messages(
        couple=couple_doc, limit=50, before=None
    )

    assert len(response["messages"]) == 2
    assert response["next_cursor"] is None


@pytest.mark.asyncio
async def test_couple_get_orders_messages_chronologically_oldest_first(
    couple_doc: dict,
    patched_mongo: _FakeMessagesCollection,
) -> None:
    _seed_messages(patched_mongo, n=3)

    response = await couple_portal_api.couple_get_messages(
        couple=couple_doc, limit=50, before=None
    )
    contents = [m["content"] for m in response["messages"]]
    assert contents == ["msg 0", "msg 1", "msg 2"]


# ---------------------------------------------------------------------------
# H1 — mark-read and unread-count queries use the centralized enum
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_couple_mark_read_filters_on_planner_role_constant(
    couple_doc: dict,
    patched_mongo: _FakeMessagesCollection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        couple_portal_api,
        "_broadcast_couple_message_change",
        AsyncMock(return_value=None),
    )

    await couple_portal_api.couple_mark_messages_read(couple=couple_doc)

    assert len(patched_mongo.update_many_calls) == 1
    query, update = patched_mongo.update_many_calls[0]
    assert query["sender_role"] == SENDER_ROLE_PLANNER
    assert query["read_by_couple"] is False
    assert update == {"$set": {"read_by_couple": True}}


@pytest.mark.asyncio
async def test_couple_unread_count_filters_on_planner_role_constant(
    couple_doc: dict,
    patched_mongo: _FakeMessagesCollection,
) -> None:
    _seed_messages(patched_mongo, n=4)

    response = await couple_portal_api.couple_unread_count(couple=couple_doc)

    assert "unread_count" in response
    assert patched_mongo.count_calls[-1]["sender_role"] == SENDER_ROLE_PLANNER
    assert patched_mongo.count_calls[-1]["read_by_couple"] is False


# ---------------------------------------------------------------------------
# Planner-side mirror: C2 + M2 + H1 + identity stamping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_planner_send_stamps_planner_role_and_email(
    planner_user: ExtendedAuthUser,
    patched_mongo: _FakeMessagesCollection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        couple_portal_api,
        "check_wedding_access",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        couple_portal_api,
        "_broadcast_couple_message_change",
        AsyncMock(return_value=None),
    )

    data = couple_portal_api.PlannerSendMessageRequest(
        wedding_id="wedding-1", content="planner reply"
    )
    response = await couple_portal_api.planner_send_message(
        data=data, current_user=planner_user
    )

    assert response["message"] == "Message sent"
    inserted = patched_mongo.insert_calls[0]
    assert inserted["sender_role"] == SENDER_ROLE_PLANNER
    assert inserted["sender_email"] == "planner@example.com"
    assert inserted["sender_name"] == "Pat Planner"


@pytest.mark.asyncio
async def test_planner_send_sends_best_effort_push_to_couple_principal(
    planner_user: ExtendedAuthUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = _FakeMessagesCollection()
    couples = _FakeCouplesCollection(
        [
            {
                "_id": "couple-1",
                "email": "couple@example.com",
                "wedding_id": "wedding-1",
                "is_active": True,
                "setup_completed": True,
                "wedding_archived": False,
            }
        ]
    )
    monkeypatch.setattr(
        couple_portal_api,
        "mongo",
        SimpleNamespace(db=_FakeDB(messages, couples)),
    )
    monkeypatch.setattr(
        couple_portal_api,
        "check_wedding_access",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        couple_portal_api,
        "_broadcast_couple_message_change",
        AsyncMock(return_value=None),
    )
    send_notification = AsyncMock(return_value={"success": True, "sent": 1})
    monkeypatch.setattr(
        couple_portal_api,
        "web_push_service",
        SimpleNamespace(enabled=True, send_notification=send_notification),
    )

    data = couple_portal_api.PlannerSendMessageRequest(
        wedding_id="wedding-1",
        content="Planner reply for the couple",
    )

    response = await couple_portal_api.planner_send_message(
        data=data,
        current_user=planner_user,
    )

    assert response["message"] == "Message sent"
    send_notification.assert_awaited_once()
    assert send_notification.await_args.kwargs["user_id"] == "couple::couple-1"
    assert (
        send_notification.await_args.kwargs["title"] == "New message from Pat Planner"
    )
    assert (
        send_notification.await_args.kwargs["url"] == "/couple/dashboard?section=inbox"
    )
    assert send_notification.await_args.kwargs["tag"] == "couple_message"


@pytest.mark.asyncio
async def test_planner_send_still_succeeds_when_couple_push_fails(
    planner_user: ExtendedAuthUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = _FakeMessagesCollection()
    couples = _FakeCouplesCollection(
        [
            {
                "_id": "couple-1",
                "email": "couple@example.com",
                "wedding_id": "wedding-1",
                "is_active": True,
                "setup_completed": True,
                "wedding_archived": False,
            }
        ]
    )
    monkeypatch.setattr(
        couple_portal_api,
        "mongo",
        SimpleNamespace(db=_FakeDB(messages, couples)),
    )
    monkeypatch.setattr(
        couple_portal_api,
        "check_wedding_access",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        couple_portal_api,
        "_broadcast_couple_message_change",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(couple_portal_api, "best_effort", _immediate_best_effort)
    monkeypatch.setattr(
        couple_portal_api,
        "web_push_service",
        SimpleNamespace(
            enabled=True,
            send_notification=AsyncMock(side_effect=RuntimeError("push provider down")),
        ),
    )

    data = couple_portal_api.PlannerSendMessageRequest(
        wedding_id="wedding-1",
        content="This message must still persist",
    )

    response = await couple_portal_api.planner_send_message(
        data=data,
        current_user=planner_user,
    )

    assert response["message"] == "Message sent"
    assert len(messages.insert_calls) == 1


@pytest.mark.asyncio
async def test_planner_update_sends_best_effort_push_to_couple_principal(
    planner_user: ExtendedAuthUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    updates = _FakeUpdatesCollection()
    couples = _FakeCouplesCollection(
        [
            {
                "_id": "couple-1",
                "email": "couple@example.com",
                "wedding_id": "wedding-1",
                "is_active": True,
                "setup_completed": True,
                "wedding_archived": False,
            }
        ]
    )
    monkeypatch.setattr(
        couple_portal_api,
        "mongo",
        SimpleNamespace(db=_FakeDB(_FakeMessagesCollection(), couples, updates)),
    )
    monkeypatch.setattr(
        couple_portal_api,
        "check_wedding_access",
        AsyncMock(return_value=True),
    )
    send_notification = AsyncMock(return_value={"success": True, "sent": 1})
    monkeypatch.setattr(
        couple_portal_api,
        "web_push_service",
        SimpleNamespace(enabled=True, send_notification=send_notification),
    )

    data = couple_portal_api.CreateUpdateRequest(
        wedding_id="wedding-1",
        title="Timeline updated",
        content="The ceremony arrival time moved to 4:30 PM.",
    )

    response = await couple_portal_api.create_update(
        data=data,
        current_user=planner_user,
    )

    assert "update_id" in response
    assert len(updates.insert_calls) == 1
    send_notification.assert_awaited_once()
    assert send_notification.await_args.kwargs["user_id"] == "couple::couple-1"
    assert send_notification.await_args.kwargs["title"] == "Timeline updated"
    assert send_notification.await_args.kwargs["body"] == (
        "The ceremony arrival time moved to 4:30 PM."
    )
    assert (
        send_notification.await_args.kwargs["url"] == "/couple/dashboard?section=inbox"
    )
    assert send_notification.await_args.kwargs["tag"] == "couple_update"


@pytest.mark.asyncio
async def test_planner_update_still_succeeds_when_couple_push_lookup_fails(
    planner_user: ExtendedAuthUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    updates = _FakeUpdatesCollection()
    failing_couples = SimpleNamespace(
        find_one=AsyncMock(side_effect=RuntimeError("couple lookup unavailable"))
    )
    monkeypatch.setattr(
        couple_portal_api,
        "mongo",
        SimpleNamespace(
            db=_FakeDB(_FakeMessagesCollection(), failing_couples, updates)
        ),
    )
    monkeypatch.setattr(
        couple_portal_api,
        "check_wedding_access",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(couple_portal_api, "best_effort", _immediate_best_effort)
    monkeypatch.setattr(
        couple_portal_api,
        "web_push_service",
        SimpleNamespace(enabled=True, send_notification=AsyncMock()),
    )

    data = couple_portal_api.CreateUpdateRequest(
        wedding_id="wedding-1",
        title="Timeline updated",
        content="This update must still persist",
    )

    response = await couple_portal_api.create_update(
        data=data,
        current_user=planner_user,
    )

    assert "update_id" in response
    assert len(updates.insert_calls) == 1


@pytest.mark.asyncio
async def test_planner_get_exposes_sender_email_and_next_cursor(
    planner_user: ExtendedAuthUser,
    patched_mongo: _FakeMessagesCollection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        couple_portal_api,
        "check_wedding_access",
        AsyncMock(return_value=True),
    )
    ids = _seed_messages(patched_mongo, n=4)

    response = await couple_portal_api.planner_get_messages(
        wedding_id="wedding-1",
        limit=2,
        before=None,
        current_user=planner_user,
    )

    assert len(response["messages"]) == 2
    for msg in response["messages"]:
        assert "sender_email" in msg
    # 4 seeded, limit=2, DESC _id → ids[3], ids[2]; reversed → ids[2], ids[3];
    # cursor = oldest of the page = ids[2].
    assert response["next_cursor"] == str(ids[2])


@pytest.mark.asyncio
async def test_planner_mark_read_filters_on_couple_role_constant(
    planner_user: ExtendedAuthUser,
    patched_mongo: _FakeMessagesCollection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        couple_portal_api,
        "check_wedding_access",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        couple_portal_api,
        "_broadcast_couple_message_change",
        AsyncMock(return_value=None),
    )

    data = couple_portal_api.PlannerMarkMessagesReadRequest(wedding_id="wedding-1")
    await couple_portal_api.planner_mark_messages_read(
        data=data, current_user=planner_user
    )

    assert len(patched_mongo.update_many_calls) == 1
    query, update = patched_mongo.update_many_calls[0]
    assert query["sender_role"] == SENDER_ROLE_COUPLE
    assert query["read_by_planner"] is False
    assert update == {"$set": {"read_by_planner": True}}


@pytest.mark.asyncio
async def test_planner_unread_count_filters_on_couple_role_constant(
    planner_user: ExtendedAuthUser,
    patched_mongo: _FakeMessagesCollection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        couple_portal_api,
        "check_wedding_access",
        AsyncMock(return_value=True),
    )

    response = await couple_portal_api.planner_unread_count(
        wedding_id="wedding-1", current_user=planner_user
    )

    assert "unread_count" in response
    assert patched_mongo.count_calls[-1]["sender_role"] == SENDER_ROLE_COUPLE
    assert patched_mongo.count_calls[-1]["read_by_planner"] is False


# ---------------------------------------------------------------------------
# Aggregation pipeline — unread-count branch uses the centralized enum
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_planner_conversations_aggregation_pipeline_references_couple_enum(
    planner_user: ExtendedAuthUser,
    patched_mongo: _FakeMessagesCollection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The `$eq` branch that counts couple-authored unread messages must use
    the SENDER_ROLE_COUPLE constant, not the string literal "couple". This
    regression would not be caught by the endpoint returning results —
    renaming the constant without updating the aggregation would silently
    break unread counts.
    """
    monkeypatch.setattr(
        couple_portal_api,
        "_get_accessible_couple_wedding_ids",
        AsyncMock(return_value=["wedding-1"]),
    )

    # Seed a couple so the route doesn't early-return before aggregating.
    # The fixture's _FakeDB exposes couple_users via this same collection.
    patched_mongo  # keep reference for clarity
    couples_collection = couple_portal_api.mongo.db["couple_users"]
    couples_collection.docs.append(
        {
            "_id": "couple-1",
            "email": "emmanuel@example.com",
            "partner1_name": "Emmanuel",
            "partner2_name": "Partner",
            "wedding_id": "wedding-1",
        }
    )

    await couple_portal_api.planner_list_conversations(
        wedding_id="wedding-1", current_user=planner_user
    )

    assert len(patched_mongo.aggregate_calls) == 1
    pipeline = patched_mongo.aggregate_calls[0]

    # Walk the pipeline looking for the $cond's $eq comparing sender_role.
    found_couple_ref = False
    for stage in pipeline:
        group = stage.get("$group")
        if not group:
            continue
        unread_expr = group.get("unread_count")
        if not unread_expr:
            continue
        # Expected shape:
        # {"$sum": {"$cond": [{"$and": [{"$eq": ["$sender_role", <val>]}, ...]}, 1, 0]}}
        cond_args = unread_expr["$sum"]["$cond"][0]["$and"]
        for predicate in cond_args:
            if "$eq" in predicate and predicate["$eq"][0] == "$sender_role":
                assert predicate["$eq"][1] == SENDER_ROLE_COUPLE
                found_couple_ref = True
    assert found_couple_ref, (
        "Aggregation pipeline must reference SENDER_ROLE_COUPLE constant, "
        "not a string literal"
    )
