"""Unit tests for calendar_provider_service.

Pure-function helpers (event normalization, error classification, OAuth-state
round-trip, scheduler-policy normalization) are exercised here without any
external HTTP or database access.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from bson import ObjectId

os.environ.setdefault("AURINKO_CLIENT_ID", "test-client-id")
os.environ.setdefault("AURINKO_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("AURINKO_OAUTH_STATE_SIGNING_KEY", "test-state-signing-key")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "test-token-encryption-key")
os.environ.setdefault("ENVIRONMENT", "test")

from app.services.calendar_provider_service import (  # noqa: E402
    CalendarProviderService,
    _normalize_event_for_aggregation,
    calendar_provider_service,
)


def test_normalize_event_canonical_shape_for_iso_datetimes() -> None:
    raw = {
        "id": "evt-1",
        "subject": "Demo",
        "description": "Body",
        "location": {"displayName": "HQ"},
        "when": {
            "start": "2026-05-06T15:00:00+00:00",
            "end": "2026-05-06T16:00:00+00:00",
            "timeZone": "UTC",
        },
        "etag": "abc",
        "attendees": [{"emailAddress": "a@b.io"}],
        "lastModifiedDateTime": "2026-05-06T15:30:00+00:00",
    }

    out = _normalize_event_for_aggregation(raw, provider="google")

    assert out["id"] == "evt-1"
    assert out["summary"] == "Demo"
    assert out["start"]["dateTime"] == "2026-05-06T15:00:00+00:00"
    assert out["end"]["dateTime"] == "2026-05-06T16:00:00+00:00"
    assert out["start"]["timeZone"] == "UTC"
    assert out["location"] == "HQ"
    assert out["_provider"] == "google"


def test_normalize_event_handles_all_day_dates() -> None:
    raw = {
        "id": "evt-2",
        "subject": "All-day",
        "when": {"start": "2026-05-06", "end": "2026-05-07"},
    }

    out = _normalize_event_for_aggregation(raw, provider="office365")

    assert out["start"] == {"date": "2026-05-06"}
    assert out["end"] == {"date": "2026-05-07"}


def test_classify_aurinko_exception_status_codes() -> None:
    request = httpx.Request("GET", "https://api.aurinko.io/v1/calendars")

    # 429 → rate limited, retryable
    response_429 = httpx.Response(429, json={"message": "rate"}, request=request)
    err_429 = httpx.HTTPStatusError("429", request=request, response=response_429)
    classification = calendar_provider_service._classify_aurinko_exception(err_429)
    assert classification["error_category"] == "rate_limited"
    assert classification["retryable"] is True

    # 401 → auth_revoked, not retryable
    response_401 = httpx.Response(401, json={"message": "no"}, request=request)
    err_401 = httpx.HTTPStatusError("401", request=request, response=response_401)
    classification = calendar_provider_service._classify_aurinko_exception(err_401)
    assert classification["error_category"] == "auth_revoked"
    assert classification["retryable"] is False

    # 500 → temporary, retryable
    response_500 = httpx.Response(500, json={"message": "x"}, request=request)
    err_500 = httpx.HTTPStatusError("500", request=request, response=response_500)
    classification = calendar_provider_service._classify_aurinko_exception(err_500)
    assert classification["error_category"] == "temporary"
    assert classification["retryable"] is True


def test_classify_transport_error_is_retryable() -> None:
    err = httpx.RequestError("connection reset")
    classification = calendar_provider_service._classify_aurinko_exception(err)
    assert classification["error_category"] == "temporary"
    assert classification["retryable"] is True


def test_oauth_state_round_trip() -> None:
    state = calendar_provider_service._build_state(
        user_id="u1",
        user_email="u@example.com",
        owner_id="o1",
        owner_email="o@example.com",
        redirect_to="/admin/planner/calendar",
    )
    payload = calendar_provider_service._decode_state(state)
    assert payload["sub"] == "u1"
    assert payload["user_email"] == "u@example.com"
    assert payload["owner_id"] == "o1"


def test_oauth_state_rejects_tampered_token() -> None:
    state = calendar_provider_service._build_state(
        user_id="u1",
        user_email="u@example.com",
        owner_id="o1",
        owner_email="o@example.com",
    )
    tampered = state[:-2] + ("aa" if state[-2:] != "aa" else "bb")
    with pytest.raises(Exception):
        calendar_provider_service._decode_state(tampered)


def test_token_encryption_round_trip() -> None:
    encrypted = calendar_provider_service._encrypt_token("aurinko-account-token")
    assert encrypted is not None
    assert encrypted != "aurinko-account-token"
    assert (
        calendar_provider_service._decrypt_token(encrypted) == "aurinko-account-token"
    )


def test_map_aurinko_service_to_provider_label() -> None:
    assert (
        calendar_provider_service._map_aurinko_service_to_provider("Google") == "google"
    )
    assert (
        calendar_provider_service._map_aurinko_service_to_provider("Office365")
        == "office365"
    )
    assert (
        calendar_provider_service._map_aurinko_service_to_provider("iCloud") == "icloud"
    )
    assert (
        calendar_provider_service._map_aurinko_service_to_provider("unknown_thing")
        == "unknown"
    )
    assert calendar_provider_service._map_aurinko_service_to_provider(None) == "unknown"


def test_is_writable_calendar_recognizes_common_shapes() -> None:
    assert (
        calendar_provider_service._is_writable_calendar({"accessRole": "owner"}) is True
    )
    assert (
        calendar_provider_service._is_writable_calendar({"accessRole": "writer"})
        is True
    )
    assert (
        calendar_provider_service._is_writable_calendar({"access": "ReadWrite"}) is True
    )
    assert (
        calendar_provider_service._is_writable_calendar(
            {"capabilities": {"canEdit": True}}
        )
        is True
    )
    assert (
        calendar_provider_service._is_writable_calendar({"accessRole": "reader"})
        is False
    )
    assert calendar_provider_service._is_writable_calendar({}) is False


def test_event_body_construction_for_timed_event() -> None:
    task: dict[str, Any] = {
        "title": "Test",
        "description": "Notes",
        "start_date": datetime(2026, 5, 6, 14, 0, tzinfo=UTC),
        "end_date": datetime(2026, 5, 6, 15, 0, tzinfo=UTC),
        "timezone": "UTC",
    }
    body = calendar_provider_service._build_event_body(task, ["a@b.io"])
    assert body["subject"] == "Test"
    assert body["when"]["type"] == "datetime"
    assert body["when"]["start"] == "2026-05-06T14:00:00+00:00"
    assert body["when"]["timeZone"] == "UTC"
    assert body["attendees"] == [{"emailAddress": "a@b.io"}]


def test_event_body_construction_for_all_day_event() -> None:
    task: dict[str, Any] = {
        "title": "All-day",
        "start_date": datetime(2026, 5, 6, tzinfo=UTC),
        "end_date": datetime(2026, 5, 6, tzinfo=UTC),
        "all_day": True,
        "timezone": "UTC",
    }
    body = calendar_provider_service._build_event_body(task)
    assert body["when"]["type"] == "date"
    assert body["when"]["start"] == "2026-05-06"
    # End date is exclusive — next-day for one-day events
    assert body["when"]["end"] == "2026-05-07"


# ============================================================================
# AurinkoClient HTTP contract tests — pin endpoint paths, methods, and bodies
# against Aurinko's documented API so accidental refactors can't drift back to
# pre-rewrite assumptions (e.g. /calendars/events?calendarId=... or PUT-update).
# ============================================================================


from unittest.mock import AsyncMock, patch  # noqa: E402

from app.services.calendar_provider_service import AurinkoClient  # noqa: E402


class _RecordingClient:
    """Minimal stand-in for httpx.AsyncClient that records the last request."""

    def __init__(self, response: httpx.Response) -> None:
        self.response = response
        self.last_method: str | None = None
        self.last_url: str | None = None
        self.last_params: dict[str, Any] | None = None
        self.last_json: dict[str, Any] | None = None
        self.last_auth: tuple[str, str] | None = None
        self.last_headers: dict[str, str] | None = None
        self.is_closed = False

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        self.last_method = method
        self.last_url = url
        self.last_params = kwargs.get("params")
        self.last_json = kwargs.get("json")
        self.last_auth = kwargs.get("auth")
        self.last_headers = kwargs.get("headers")
        return self.response


def _make_response(
    status_code: int, body: dict[str, Any] | None = None
) -> httpx.Response:
    request = httpx.Request("GET", "https://api.aurinko.io/v1/_test")
    return httpx.Response(status_code, json=body or {}, request=request)


class _MemoryCursor:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def sort(self, *_args: Any, **_kwargs: Any) -> "_MemoryCursor":
        return self

    async def to_list(self, length: int | None = None) -> list[dict[str, Any]]:
        return list(self.rows[:length] if length is not None else self.rows)


class _MemoryCollection:
    def __init__(self, docs: list[dict[str, Any]] | None = None) -> None:
        self.docs = docs or []
        self.update_many_calls: list[tuple[dict[str, Any], dict[str, Any]]] = []
        self.delete_many_calls: list[dict[str, Any]] = []
        self.delete_one_calls: list[dict[str, Any]] = []

    def _matches(self, doc: dict[str, Any], query: dict[str, Any]) -> bool:
        for key, expected in query.items():
            actual = doc.get(key)
            if isinstance(expected, dict):
                if "$in" in expected and actual not in expected["$in"]:
                    return False
                if "$nin" in expected and actual in expected["$nin"]:
                    return False
                if "$ne" in expected and actual == expected["$ne"]:
                    return False
                if "$gt" in expected and not (actual and actual > expected["$gt"]):
                    return False
                continue
            if actual != expected:
                return False
        return True

    async def find_one(
        self, query: dict[str, Any], *_args: Any, **_kwargs: Any
    ) -> dict[str, Any] | None:
        return next((doc for doc in self.docs if self._matches(doc, query)), None)

    def find(self, query: dict[str, Any]) -> _MemoryCursor:
        return _MemoryCursor([doc for doc in self.docs if self._matches(doc, query)])

    async def update_one(
        self,
        query: dict[str, Any],
        update: dict[str, Any],
        upsert: bool = False,
    ) -> None:
        doc = await self.find_one(query)
        if doc is None:
            if not upsert:
                return
            doc = {
                key: value
                for key, value in query.items()
                if not isinstance(value, dict)
            }
            doc.setdefault("_id", ObjectId())
            doc.update(update.get("$setOnInsert", {}))
            self.docs.append(doc)
        doc.update(update.get("$set", {}))
        for key in update.get("$unset", {}):
            doc.pop(key, None)

    async def update_many(self, query: dict[str, Any], update: dict[str, Any]) -> None:
        self.update_many_calls.append((query, update))
        for doc in list(self.docs):
            if self._matches(doc, query):
                doc.update(update.get("$set", {}))
                for key in update.get("$unset", {}):
                    doc.pop(key, None)

    async def delete_one(self, query: dict[str, Any]) -> None:
        self.delete_one_calls.append(query)
        self.docs = [doc for doc in self.docs if not self._matches(doc, query)]

    async def delete_many(self, query: dict[str, Any]) -> None:
        self.delete_many_calls.append(query)
        self.docs = [doc for doc in self.docs if not self._matches(doc, query)]

    async def bulk_write(self, operations: list[Any], ordered: bool = False) -> None:
        for operation in operations:
            await self.update_one(
                operation._filter,
                operation._doc,
                upsert=bool(operation._upsert),
            )


class _SubscriptionClient:
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []
        self.deleted: list[dict[str, Any]] = []

    async def create_subscription(
        self,
        *,
        account_token: str,
        webhook_url: str,
        calendar_id: str | None = None,
        resource: str | None = None,
    ) -> dict[str, Any]:
        if resource is None:
            resource = f"/calendars/{calendar_id}/events"
        subscription_id = f"sub-{len(self.created) + 1}"
        self.created.append(
            {
                "account_token": account_token,
                "resource": resource,
                "webhook_url": webhook_url,
            }
        )
        return {"id": subscription_id}

    async def delete_subscription(
        self, *, account_token: str, subscription_id: str
    ) -> None:
        self.deleted.append(
            {"account_token": account_token, "subscription_id": subscription_id}
        )


@pytest.mark.asyncio
async def test_commit_calendar_selection_anchors_task_and_contact_sync_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = CalendarProviderService.__new__(CalendarProviderService)
    encrypted_token = calendar_provider_service._encrypt_token("account-token")
    draft_id = "draft-token"
    service.drafts_collection = _MemoryCollection(
        [
            {
                "_id": ObjectId(),
                "draft_token": draft_id,
                "owner_planner_id": "planner-1",
                "owner_planner_email": "planner@example.com",
                "user_id": "user-1",
                "user_email": "planner@example.com",
                "provider": "google",
                "provider_account_email": "planner@gmail.com",
                "provider_account_name": "Planner Gmail",
                "aurinko_account_id": "acct-1",
                "aurinko_access_token_encrypted": encrypted_token,
                "calendars_payload": [
                    {
                        "id": "cal-1",
                        "name": "Primary",
                        "accessRole": "owner",
                        "primary": True,
                    },
                    {
                        "id": "cal-2",
                        "name": "Work",
                        "accessRole": "writer",
                    },
                ],
                "tasklists_payload": [
                    {"id": "tasks-default", "name": "Tasks", "default": True}
                ],
                "contact_books_payload": [
                    {"id": "default", "name": "Default contacts", "default": True}
                ],
                "default_write_calendar_id": "cal-1",
                "connection_scopes": [
                    "Calendar.ReadWrite",
                    "Tasks.ReadWrite",
                    "Contacts.ReadWrite",
                ],
                "redirect_to": "/admin/planner/calendar",
            }
        ]
    )
    service.connections_collection = _MemoryCollection()
    service.syncs_collection = _MemoryCollection()
    service.task_sync_records_collection = _MemoryCollection()
    service.contact_sync_records_collection = _MemoryCollection()
    service.client = _SubscriptionClient()
    service._webhook_url = lambda: "https://example.test/calendar/webhook"
    monkeypatch.setattr(
        "app.services.calendar_provider_service.calendar_audit_service.log",
        AsyncMock(return_value=None),
    )

    result = await service.commit_calendar_selection(
        draft_id=draft_id,
        user_id="user-1",
        picks=[
            {"aurinko_calendar_id": "cal-1"},
            {"aurinko_calendar_id": "cal-2", "is_default_write_target": True},
        ],
        task_picks=[{"aurinko_tasklist_id": "tasks-default"}],
        contact_picks=[{"aurinko_contact_book_id": "default"}],
    )

    assert result["connected"] is True
    assert result["connections_created"] == 2
    enabled_task_rows = [
        row for row in service.connections_collection.docs if row["task_sync_enabled"]
    ]
    enabled_contact_rows = [
        row
        for row in service.connections_collection.docs
        if row["contact_sync_enabled"]
    ]
    assert [row["aurinko_calendar_id"] for row in enabled_task_rows] == ["cal-2"]
    assert [row["aurinko_calendar_id"] for row in enabled_contact_rows] == ["cal-2"]
    created_resources = [entry["resource"] for entry in service.client.created]
    assert created_resources.count("/tasklists/tasks-default/tasks") == 1
    assert created_resources.count("/contacts") == 1


@pytest.mark.asyncio
async def test_update_connection_moves_task_sync_off_account_siblings() -> None:
    service = CalendarProviderService.__new__(CalendarProviderService)
    encrypted_token = calendar_provider_service._encrypt_token("account-token")
    current_id = ObjectId()
    sibling_id = ObjectId()
    service.connections_collection = _MemoryCollection(
        [
            {
                "_id": current_id,
                "owner_planner_id": "planner-1",
                "owner_planner_email": "planner@example.com",
                "user_id": "user-1",
                "user_email": "planner@example.com",
                "aurinko_account_id": "acct-1",
                "aurinko_access_token_encrypted": encrypted_token,
                "aurinko_calendar_id": "cal-1",
                "calendar_name": "Primary",
                "provider": "google",
                "is_writable": True,
                "sync_enabled": True,
                "task_sync_enabled": False,
            },
            {
                "_id": sibling_id,
                "owner_planner_id": "planner-1",
                "owner_planner_email": "planner@example.com",
                "user_id": "user-1",
                "user_email": "planner@example.com",
                "aurinko_account_id": "acct-1",
                "aurinko_access_token_encrypted": encrypted_token,
                "aurinko_calendar_id": "cal-2",
                "calendar_name": "Work",
                "provider": "google",
                "is_writable": True,
                "sync_enabled": True,
                "task_sync_enabled": True,
                "task_sync_tasklist_id": "tasks-default",
                "task_sync_subscription_id": "sub-old-task",
            },
        ]
    )
    service.task_sync_records_collection = _MemoryCollection(
        [{"connection_id": str(sibling_id), "sync_status": "synced"}]
    )
    service.contact_sync_records_collection = _MemoryCollection()
    service.client = _SubscriptionClient()
    service._webhook_url = lambda: "https://example.test/calendar/webhook"

    async def _noop_invalidate(_connection_id: str) -> None:
        return None

    service.invalidate_connection_events_cache = _noop_invalidate

    result = await service.update_connection(
        str(current_id),
        {
            "task_sync_enabled": True,
            "task_sync_tasklist_id": "tasks-default",
            "task_sync_tasklist_name": "Tasks",
        },
    )

    sibling = await service.connections_collection.find_one({"_id": sibling_id})
    current = await service.connections_collection.find_one({"_id": current_id})
    assert result["task_sync_enabled"] is True
    assert current["task_sync_subscription_id"] == "sub-1"
    assert sibling["task_sync_enabled"] is False
    assert sibling["task_sync_tasklist_id"] is None
    assert sibling["task_sync_subscription_id"] is None
    assert service.client.deleted == [
        {"account_token": "account-token", "subscription_id": "sub-old-task"}
    ]
    assert service.task_sync_records_collection.docs[0]["sync_status"] == "orphaned"


@pytest.mark.asyncio
async def test_authorize_url_advertises_ews_not_exchange() -> None:
    """Aurinko's hosted-auth provider id for on-prem Exchange is "EWS";
    sending "Exchange" silently drops the provider. Pin that EWS is the
    canonical spelling we use anywhere serviceType is built."""
    # The exact serviceType value sent is whatever resolve_service_type
    # produces; here the test verifies the EWS spelling is correct in the
    # mapping, regardless of the default-fallback value.
    assert AurinkoClient.resolve_service_type("ews") == "EWS"
    assert "Exchange" not in {
        AurinkoClient.resolve_service_type(p)
        for p in ("google", "office365", "icloud", "ews")
    }


@pytest.mark.asyncio
async def test_authorize_url_uses_space_separated_scopes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Aurinko's hosted-auth ``/v1/auth/authorize`` REQUIRES space-separated
    scopes. Live-verified 2026-05-13 against api.aurinko.io:

        comma-separated  → 400 "Unable to parse Scopes: ..."
        space-separated  → 303 redirect (success)

    This corrects an earlier comment + test in this file that pinned
    comma-separated based on an untested assumption. Pin space-separated
    here so we don't drift back to comma and re-trigger live OAuth failures.
    """
    # Patch the settings object held by calendar_provider_service directly
    # (os.environ.setdefault at module level is too late — settings attributes
    # are class-level os.getenv() calls evaluated at first import time).
    import app.services.calendar_provider_service as _cps_mod

    monkeypatch.setattr(_cps_mod.settings, "AURINKO_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(
        _cps_mod.settings, "AURINKO_CLIENT_SECRET", "test-client-secret"
    )
    client = AurinkoClient()
    url = await client.authorize_url(
        scopes=["Calendar.ReadWrite", "Contacts.Read"],
        return_url="http://localhost:3000/cb",
        state="state-token",
    )
    # Space is URL-encoded to `+` inside an httpx-built query value (or %20
    # — either is accepted by Aurinko's parser; %2C is the broken form).
    assert (
        "scopes=Calendar.ReadWrite+Contacts.Read" in url
        or "scopes=Calendar.ReadWrite%20Contacts.Read" in url
    ), f"scopes must be space-separated (+ or %20). URL: {url}"
    # Must NOT emit comma-separated — that's the form Aurinko rejects.
    assert "Calendar.ReadWrite%2CContacts.Read" not in url
    assert "Calendar.ReadWrite,Contacts.Read" not in url


@pytest.mark.asyncio
async def test_authorize_url_default_serviceType_falls_back_to_google(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Aurinko's hosted-auth ``/v1/auth/authorize`` accepts a SINGLE
    serviceType value only. Live-verified 2026-05-13:

        serviceType=Google,Office365,iCloud,EWS  → 400 "customapi.notfound"
        serviceType=Google                       → 303 redirect to Google OAuth

    There is no native picker mode. The planner UI provides its own
    four-button picker (one per provider). Without an explicit
    service_type, we fall back to "Google" — a safe default that
    produces a valid Aurinko URL instead of erroring out.

    This corrects an earlier test that pinned the comma-separated
    multi-value form (broken in prod, never live-tested).
    """
    import app.services.calendar_provider_service as _cps_mod

    monkeypatch.setattr(_cps_mod.settings, "AURINKO_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(
        _cps_mod.settings, "AURINKO_CLIENT_SECRET", "test-client-secret"
    )
    client = AurinkoClient()
    url = await client.authorize_url(
        scopes=["Calendar.ReadWrite"],
        return_url="http://localhost:3000/cb",
        state="state-token",
    )
    # Default → "Google" (single value).
    assert "serviceType=Google&" in url or url.endswith("serviceType=Google"), (
        f"default serviceType must be exactly 'Google' (single value). URL: {url}"
    )
    # Must NOT contain comma-separated multi-value form.
    assert "%2C" not in url.split("serviceType=")[1].split("&")[0]


@pytest.mark.asyncio
async def test_authorize_url_passes_single_serviceType_when_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When a per-provider button calls /provider/connect?service_type=google
    we want Aurinko to skip its picker and jump straight to Google's OAuth
    screen. That requires sending ONLY ``Google`` in serviceType, not the
    full list."""
    import app.services.calendar_provider_service as _cps_mod

    monkeypatch.setattr(_cps_mod.settings, "AURINKO_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(
        _cps_mod.settings, "AURINKO_CLIENT_SECRET", "test-client-secret"
    )
    client = AurinkoClient()
    url = await client.authorize_url(
        scopes=["Calendar.ReadWrite"],
        return_url="http://localhost:3000/cb",
        state="state-token",
        service_type="Google",
    )
    assert "serviceType=Google&" in url or url.endswith("serviceType=Google")
    # Must NOT contain the rest of the picker list (Aurinko would still show
    # the picker if it saw multiple values).
    assert "Office365" not in url
    assert "iCloud" not in url
    assert "EWS" not in url


def test_resolve_service_type_maps_planner_provider_ids_to_aurinko_enum() -> None:
    """Planner-facing ids ("google"/"office365"/"icloud"/"ews") map to the
    exact Aurinko serviceType enum values (case-sensitive)."""
    assert AurinkoClient.resolve_service_type("google") == "Google"
    assert AurinkoClient.resolve_service_type("GOOGLE") == "Google"
    assert AurinkoClient.resolve_service_type("office365") == "Office365"
    assert AurinkoClient.resolve_service_type("icloud") == "iCloud"
    assert AurinkoClient.resolve_service_type("ews") == "EWS"


def test_resolve_service_type_falls_back_to_google_for_unknown_or_none() -> None:
    """None, empty, or an unrecognized id resolves to "Google" — a single
    valid Aurinko serviceType value. The previous fallback (comma-separated
    multi-value) returned 400 "customapi.notfound" live; verified 2026-05-13.
    Single-Google is the only safe default — caller can always re-init OAuth
    to pick a different provider from the planner UI's per-provider buttons.
    """
    assert AurinkoClient.resolve_service_type(None) == "Google"
    assert AurinkoClient.resolve_service_type("") == "Google"
    assert AurinkoClient.resolve_service_type("bogus") == "Google"


@pytest.mark.asyncio
async def test_get_authorization_url_parses_env_scopes_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The production callsite passes ``settings.AURINKO_SCOPES`` (a string)
    into ``client.authorize_url`` which expects ``list[str]``. Without the
    string→list parse the URL ends up with comma-joined CHARACTERS:
    ``scopes=C,a,l,e,n,d,a,r,...``. Pin the production path so this can't
    regress. .env may use either space or comma as separator."""
    monkeypatch.setattr(
        "app.services.calendar_provider_service.settings.AURINKO_SCOPES",
        "Calendar.ReadWrite Mail.Read Mail.Send Contacts.ReadWrite",
    )
    monkeypatch.setattr(
        "app.services.calendar_provider_service.settings.AURINKO_REDIRECT_URI",
        "http://localhost:3000/cb",
    )
    monkeypatch.setattr(
        "app.services.calendar_provider_service.settings.AURINKO_OAUTH_STATE_SIGNING_KEY",
        "sk",
    )

    svc = CalendarProviderService()
    url = await svc.get_authorization_url(
        user_id="u1",
        user_email="u@example.com",
        owner_id="o1",
        owner_email="o@example.com",
    )
    # The scopes parameter should contain scope NAMES, not comma-joined
    # CHARACTERS. Look for at least one full scope name.
    assert "Calendar.ReadWrite" in url, f"scope name not preserved: {url[:200]}"
    # The bug signature: comma between every character.
    assert "C,a,l,e,n,d,a,r" not in url, (
        "regression: scopes string joined character-by-character"
    )


@pytest.mark.asyncio
async def test_create_event_uses_path_calendar_id() -> None:
    """Aurinko paths put calendarId in the URL, not as a query param."""
    recorder = _RecordingClient(_make_response(200, {"id": "evt-1"}))
    client = AurinkoClient()
    with patch(
        "app.services.calendar_provider_service._get_aurinko_http_client",
        return_value=recorder,
    ):
        await client.create_event(
            account_token="tok",
            calendar_id="my-calendar-id",
            body={"subject": "x"},
        )
    assert recorder.last_method == "POST"
    assert recorder.last_url is not None
    assert recorder.last_url.endswith("/calendars/my-calendar-id/events")
    # No leftover ?calendarId=... query param.
    assert recorder.last_params is None or "calendarId" not in (
        recorder.last_params or {}
    )


@pytest.mark.asyncio
async def test_update_event_uses_patch_not_put() -> None:
    """Aurinko docs: 'Use PATCH request to update existing events.' PUT 404s."""
    recorder = _RecordingClient(_make_response(200, {"id": "evt-1", "etag": "v2"}))
    client = AurinkoClient()
    with patch(
        "app.services.calendar_provider_service._get_aurinko_http_client",
        return_value=recorder,
    ):
        await client.update_event(
            account_token="tok",
            calendar_id="cal",
            external_event_id="evt-1",
            body={"subject": "y"},
        )
    assert recorder.last_method == "PATCH"
    assert recorder.last_url is not None
    assert recorder.last_url.endswith("/calendars/cal/events/evt-1")


@pytest.mark.asyncio
async def test_delete_event_uses_path_calendar_id() -> None:
    recorder = _RecordingClient(_make_response(204))
    client = AurinkoClient()
    with patch(
        "app.services.calendar_provider_service._get_aurinko_http_client",
        return_value=recorder,
    ):
        await client.delete_event(
            account_token="tok",
            calendar_id="cal",
            external_event_id="evt-1",
        )
    assert recorder.last_method == "DELETE"
    assert recorder.last_url is not None
    assert recorder.last_url.endswith("/calendars/cal/events/evt-1")


@pytest.mark.asyncio
async def test_list_events_uses_path_calendar_id_and_drops_calendar_query() -> None:
    recorder = _RecordingClient(_make_response(200, {"records": []}))
    client = AurinkoClient()
    with patch(
        "app.services.calendar_provider_service._get_aurinko_http_client",
        return_value=recorder,
    ):
        await client.list_events(
            account_token="tok",
            calendar_id="cal",
            time_min=datetime(2026, 5, 6, tzinfo=UTC),
            time_max=datetime(2026, 5, 7, tzinfo=UTC),
            max_results=50,
        )
    assert recorder.last_method == "GET"
    assert recorder.last_url is not None
    assert recorder.last_url.endswith("/calendars/cal/events")
    assert recorder.last_params is not None
    assert "calendarId" not in recorder.last_params
    assert recorder.last_params.get("start") == "2026-05-06T00:00:00+00:00"


@pytest.mark.asyncio
async def test_create_subscription_resource_is_per_calendar() -> None:
    """Aurinko subscriptions are per-resource. The only valid calendar resource
    strings are /calendars/primary/events and /calendars/{calId}/events. The
    pre-rewrite "/calendars/events" path does not exist."""
    recorder = _RecordingClient(_make_response(200, {"id": "sub-9"}))
    client = AurinkoClient()
    with patch(
        "app.services.calendar_provider_service._get_aurinko_http_client",
        return_value=recorder,
    ):
        await client.create_subscription(
            account_token="tok",
            calendar_id="cal-99",
            webhook_url="https://example.com/webhooks",
        )
    assert recorder.last_method == "POST"
    assert recorder.last_url is not None
    assert recorder.last_url.endswith("/subscriptions")
    assert recorder.last_json is not None
    assert recorder.last_json["resource"] == "/calendars/cal-99/events"
    assert recorder.last_json["notificationUrl"] == "https://example.com/webhooks"


@pytest.mark.asyncio
async def test_create_subscription_accepts_task_resource() -> None:
    recorder = _RecordingClient(_make_response(200, {"id": "sub-task"}))
    client = AurinkoClient()
    with patch(
        "app.services.calendar_provider_service._get_aurinko_http_client",
        return_value=recorder,
    ):
        await client.create_subscription(
            account_token="tok",
            resource="/tasklists/default/tasks",
            webhook_url="https://example.com/webhooks",
        )
    assert recorder.last_method == "POST"
    assert recorder.last_json is not None
    assert recorder.last_json["resource"] == "/tasklists/default/tasks"


@pytest.mark.asyncio
async def test_create_subscription_accepts_contacts_resource() -> None:
    recorder = _RecordingClient(_make_response(200, {"id": "sub-contact"}))
    client = AurinkoClient()
    with patch(
        "app.services.calendar_provider_service._get_aurinko_http_client",
        return_value=recorder,
    ):
        await client.create_subscription(
            account_token="tok",
            resource="/contacts",
            webhook_url="https://example.com/webhooks",
        )
    assert recorder.last_method == "POST"
    assert recorder.last_json is not None
    assert recorder.last_json["resource"] == "/contacts"


@pytest.mark.asyncio
async def test_task_crud_uses_tasklist_path_and_patch() -> None:
    recorder = _RecordingClient(_make_response(200, {"id": "task-1", "etag": "v2"}))
    client = AurinkoClient()
    with patch(
        "app.services.calendar_provider_service._get_aurinko_http_client",
        return_value=recorder,
    ):
        await client.update_task(
            account_token="tok",
            tasklist_id="default",
            task_id="task-1",
            body={"title": "Updated"},
            etag="v1",
        )
    assert recorder.last_method == "PATCH"
    assert recorder.last_url is not None
    assert recorder.last_url.endswith("/tasklists/default/tasks/task-1")
    assert recorder.last_json == {"title": "Updated"}
    assert recorder.last_headers is not None
    assert recorder.last_headers["If-Match"] == "v1"


@pytest.mark.asyncio
async def test_create_task_uses_tasklist_path() -> None:
    recorder = _RecordingClient(_make_response(200, {"id": "task-1"}))
    client = AurinkoClient()
    with patch(
        "app.services.calendar_provider_service._get_aurinko_http_client",
        return_value=recorder,
    ):
        await client.create_task(
            account_token="tok",
            tasklist_id="default",
            body={"title": "Task"},
        )
    assert recorder.last_method == "POST"
    assert recorder.last_url is not None
    assert recorder.last_url.endswith("/tasklists/default/tasks")
    assert recorder.last_json == {"title": "Task"}


@pytest.mark.asyncio
async def test_task_sync_uses_tasklist_scoped_delta_contract() -> None:
    recorder = _RecordingClient(
        _make_response(
            200,
            {
                "ready": True,
                "syncUpdatedToken": "updated-token",
                "syncDeletedToken": "deleted-token",
            },
        )
    )
    client = AurinkoClient()
    with patch(
        "app.services.calendar_provider_service._get_aurinko_http_client",
        return_value=recorder,
    ):
        result = await client.start_task_sync(
            account_token="tok",
            tasklist_id="default",
            skip_completed_before_date=datetime(2026, 5, 1, tzinfo=UTC),
            await_ready=False,
        )
    assert result["syncUpdatedToken"] == "updated-token"
    assert recorder.last_method == "POST"
    assert recorder.last_url is not None
    assert recorder.last_url.endswith("/tasklists/default/sync")
    assert recorder.last_params == {
        "skipCompletedBeforeDate": "2026-05-01T00:00:00+00:00",
        "awaitReady": "false",
    }

    with patch(
        "app.services.calendar_provider_service._get_aurinko_http_client",
        return_value=recorder,
    ):
        await client.list_task_sync_changes(
            account_token="tok",
            tasklist_id="default",
            change_set="updated",
            delta_token="updated-token",
        )
    assert recorder.last_method == "GET"
    assert recorder.last_url is not None
    assert recorder.last_url.endswith("/tasklists/default/sync/updated")
    assert recorder.last_params == {"deltaToken": "updated-token"}


@pytest.mark.asyncio
async def test_delete_task_treats_404_as_idempotent() -> None:
    recorder = _RecordingClient(_make_response(404, {"message": "gone"}))
    client = AurinkoClient()
    with patch(
        "app.services.calendar_provider_service._get_aurinko_http_client",
        return_value=recorder,
    ):
        await client.delete_task(
            account_token="tok",
            tasklist_id="default",
            task_id="task-1",
        )
    assert recorder.last_method == "DELETE"
    assert recorder.last_url is not None
    assert recorder.last_url.endswith("/tasklists/default/tasks/task-1")


@pytest.mark.asyncio
async def test_contact_crud_uses_contacts_path_and_if_match() -> None:
    recorder = _RecordingClient(_make_response(200, {"id": "contact-1"}))
    client = AurinkoClient()
    with patch(
        "app.services.calendar_provider_service._get_aurinko_http_client",
        return_value=recorder,
    ):
        await client.update_contact(
            account_token="tok",
            contact_id="contact-1",
            body={"givenName": "Ada"},
            etag="etag-1",
        )
    assert recorder.last_method == "PATCH"
    assert recorder.last_url is not None
    assert recorder.last_url.endswith("/contacts/contact-1")
    assert recorder.last_json == {"givenName": "Ada"}
    assert recorder.last_headers is not None
    assert recorder.last_headers["If-Match"] == "etag-1"


@pytest.mark.asyncio
async def test_contacts_sync_uses_documented_delta_contract() -> None:
    recorder = _RecordingClient(
        _make_response(
            200,
            {
                "ready": True,
                "syncUpdatedToken": "contact-updated",
                "syncDeletedToken": "contact-deleted",
            },
        )
    )
    client = AurinkoClient()
    with patch(
        "app.services.calendar_provider_service._get_aurinko_http_client",
        return_value=recorder,
    ):
        result = await client.start_contacts_sync(
            account_token="tok",
            await_ready=False,
        )
    assert result["syncDeletedToken"] == "contact-deleted"
    assert recorder.last_method == "POST"
    assert recorder.last_url is not None
    assert recorder.last_url.endswith("/contacts/sync")
    assert recorder.last_params == {"awaitReady": "false"}

    with patch(
        "app.services.calendar_provider_service._get_aurinko_http_client",
        return_value=recorder,
    ):
        await client.list_contact_sync_changes(
            account_token="tok",
            change_set="deleted",
            page_token="next-page",
        )
    assert recorder.last_method == "GET"
    assert recorder.last_url is not None
    assert recorder.last_url.endswith("/contacts/sync/deleted")
    assert recorder.last_params == {"pageToken": "next-page"}


@pytest.mark.asyncio
async def test_delete_contact_treats_404_as_idempotent() -> None:
    recorder = _RecordingClient(_make_response(404, {"message": "gone"}))
    client = AurinkoClient()
    with patch(
        "app.services.calendar_provider_service._get_aurinko_http_client",
        return_value=recorder,
    ):
        await client.delete_contact(account_token="tok", contact_id="contact-1")
    assert recorder.last_method == "DELETE"
    assert recorder.last_url is not None
    assert recorder.last_url.endswith("/contacts/contact-1")
