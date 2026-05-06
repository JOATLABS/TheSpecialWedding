"""Unit tests for calendar_provider_service.

Pure-function helpers (event normalization, error classification, OAuth-state
round-trip, scheduler-policy normalization) are exercised here without any
external HTTP or database access.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
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
    assert calendar_provider_service._decrypt_token(encrypted) == "aurinko-account-token"


def test_map_aurinko_service_to_provider_label() -> None:
    assert calendar_provider_service._map_aurinko_service_to_provider("Google") == "google"
    assert calendar_provider_service._map_aurinko_service_to_provider("Office365") == "office365"
    assert calendar_provider_service._map_aurinko_service_to_provider("iCloud") == "icloud"
    assert calendar_provider_service._map_aurinko_service_to_provider("unknown_thing") == "unknown"
    assert calendar_provider_service._map_aurinko_service_to_provider(None) == "unknown"


def test_is_writable_calendar_recognizes_common_shapes() -> None:
    assert calendar_provider_service._is_writable_calendar({"accessRole": "owner"}) is True
    assert calendar_provider_service._is_writable_calendar({"accessRole": "writer"}) is True
    assert calendar_provider_service._is_writable_calendar({"access": "ReadWrite"}) is True
    assert calendar_provider_service._is_writable_calendar(
        {"capabilities": {"canEdit": True}}
    ) is True
    assert calendar_provider_service._is_writable_calendar({"accessRole": "reader"}) is False
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
