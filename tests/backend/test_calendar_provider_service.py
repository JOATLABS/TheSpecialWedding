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

os.environ.setdefault("AURINKO_CLIENT_ID", "test-client-id")
os.environ.setdefault("AURINKO_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("AURINKO_OAUTH_STATE_SIGNING_KEY", "test-state-signing-key")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "test-token-encryption-key")
os.environ.setdefault("ENVIRONMENT", "test")

from app.services.calendar_provider_service import (  # noqa: E402
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


from unittest.mock import patch  # noqa: E402

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


@pytest.mark.asyncio
async def test_authorize_url_advertises_ews_not_exchange() -> None:
    """Aurinko's hosted-auth provider id for on-prem Exchange is "EWS".
    Sending "Exchange" silently drops the provider from the picker."""
    client = AurinkoClient()
    url = await client.authorize_url(
        scopes=["Calendar.ReadWrite", "AccountInfo.Read"],
        return_url="http://localhost:3000/cb",
        state="state-token",
    )
    assert "serviceType=Google%2COffice365%2CiCloud%2CEWS" in url
    assert "Exchange" not in url.split("serviceType=")[1].split("&")[0]


@pytest.mark.asyncio
async def test_authorize_url_uses_comma_separated_scopes() -> None:
    """Aurinko's scope parser rejects space-separated scope lists once the URL
    has round-tripped through `+` encoding. Comma is the canonical separator;
    pin it so we don't drift back to space and re-trigger ``badRequest:
    Unable to parse Scopes`` from /v1/auth/authorize."""
    client = AurinkoClient()
    url = await client.authorize_url(
        scopes=["Calendar.ReadWrite", "Contacts.Read"],
        return_url="http://localhost:3000/cb",
        state="state-token",
    )
    # Comma is URL-encoded to %2C inside a query value.
    assert "scopes=Calendar.ReadWrite%2CContacts.Read" in url
    # Make sure we never emit the space-separated form (encoded as `+` or %20).
    assert "Calendar.ReadWrite+Contacts.Read" not in url
    assert "Calendar.ReadWrite%20Contacts.Read" not in url


@pytest.mark.asyncio
async def test_get_authorization_url_parses_env_scopes_string() -> None:
    """The production callsite passes ``settings.AURINKO_SCOPES`` (a string)
    into ``client.authorize_url`` which expects ``list[str]``. Without the
    string→list parse the URL ends up with comma-joined CHARACTERS:
    ``scopes=C,a,l,e,n,d,a,r,...``. Pin the production path so this can't
    regress. .env may use either space or comma as separator."""
    import os

    # Patch the env var with a space-separated string (matches the repo's
    # .env shape today). Then call get_authorization_url which reads it.
    saved = os.environ.get("AURINKO_SCOPES")
    saved_redirect = os.environ.get("AURINKO_REDIRECT_URI")
    saved_signing = os.environ.get("AURINKO_OAUTH_STATE_SIGNING_KEY")
    try:
        os.environ["AURINKO_SCOPES"] = (
            "Calendar.ReadWrite Mail.Read Mail.Send Contacts.ReadWrite"
        )
        os.environ["AURINKO_REDIRECT_URI"] = "http://localhost:3000/cb"
        os.environ.setdefault("AURINKO_OAUTH_STATE_SIGNING_KEY", "sk")
        # Reload settings so the patched env is picked up.
        import importlib
        from app.core import config as _config_mod

        importlib.reload(_config_mod)
        # Also reload the provider module so its module-level singleton
        # reads the refreshed settings.
        from app.services import calendar_provider_service as _cps_mod

        importlib.reload(_cps_mod)
        svc = _cps_mod.CalendarProviderService()
        url = await svc.get_authorization_url(
            user_id="u1",
            user_email="u@example.com",
            owner_id="o1",
            owner_email="o@example.com",
        )
        # The scopes parameter should contain comma-joined scope NAMES, not
        # comma-joined CHARACTERS. Look for at least one full scope name.
        assert "Calendar.ReadWrite" in url, f"scope name not preserved: {url[:200]}"
        # The bug signature: comma between every character.
        assert "C,a,l,e,n,d,a,r" not in url, (
            "regression: scopes string joined character-by-character"
        )
    finally:
        if saved is None:
            os.environ.pop("AURINKO_SCOPES", None)
        else:
            os.environ["AURINKO_SCOPES"] = saved
        if saved_redirect is None:
            os.environ.pop("AURINKO_REDIRECT_URI", None)
        else:
            os.environ["AURINKO_REDIRECT_URI"] = saved_redirect
        if saved_signing is None:
            os.environ.pop("AURINKO_OAUTH_STATE_SIGNING_KEY", None)
        else:
            os.environ["AURINKO_OAUTH_STATE_SIGNING_KEY"] = saved_signing


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
