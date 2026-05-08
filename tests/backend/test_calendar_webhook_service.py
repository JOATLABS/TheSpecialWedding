"""Unit tests for the Aurinko webhook service.

Signature verification and replay-window checks are pure functions that can
be exercised without a live database.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import UTC, datetime, timedelta

os.environ.setdefault("AURINKO_WEBHOOK_SECRET", "test-webhook-secret")
os.environ.setdefault("ENVIRONMENT", "test")

from app.services.calendar_webhook_service import calendar_webhook_service  # noqa: E402


def _sign(body: bytes, secret: str = "test-webhook-secret") -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def test_verify_signature_accepts_valid_hmac() -> None:
    body = b'{"id":"d1"}'
    signature = _sign(body)
    assert calendar_webhook_service.verify_signature(body, signature) is True


def test_verify_signature_rejects_missing_or_bad_signature() -> None:
    body = b'{"id":"d1"}'
    assert calendar_webhook_service.verify_signature(body, None) is False
    assert calendar_webhook_service.verify_signature(body, "not-the-real-hmac") is False


def test_replay_window_rejects_old_deliveries() -> None:
    very_old = datetime.now(UTC) - timedelta(hours=1)
    assert calendar_webhook_service.is_within_replay_window(very_old) is False


def test_replay_window_accepts_recent_deliveries() -> None:
    fresh = datetime.now(UTC) - timedelta(seconds=10)
    assert calendar_webhook_service.is_within_replay_window(fresh) is True


def test_replay_window_accepts_missing_timestamp() -> None:
    """Without a timestamp we can't verify replay; permit and rely on signature + dedupe."""
    assert calendar_webhook_service.is_within_replay_window(None) is True


# ============================================================================
# Webhook handler payload-parser tests — pin the parser against Aurinko's
# documented delivery shape: {subscription, resource, accountId, payloads[]}.
# ============================================================================


from app.api.calendar_webhooks import _extract_calendar_id  # noqa: E402


def test_extract_calendar_id_from_specific_calendar_resource() -> None:
    assert _extract_calendar_id("/calendars/cal-abc/events") == "cal-abc"


def test_extract_calendar_id_from_primary_resource() -> None:
    assert _extract_calendar_id("/calendars/primary/events") == "primary"


def test_extract_calendar_id_handles_trailing_slash() -> None:
    assert _extract_calendar_id("/calendars/cal-abc/events/") == "cal-abc"


def test_extract_calendar_id_rejects_non_calendar_resource() -> None:
    """Aurinko subscribes to other resources too (mail, contacts) — the calendar
    parser must not match them."""
    assert _extract_calendar_id("/email/messages") is None
    assert _extract_calendar_id("/contacts") is None
    assert _extract_calendar_id("") is None
    assert _extract_calendar_id(None) is None


def test_extract_calendar_id_handles_url_encoded_calendar() -> None:
    """Some providers use email-style ids — Aurinko url-encodes them inside
    the resource string. We decode so the result matches the value stored
    in Mongo at OAuth callback time."""
    assert (
        _extract_calendar_id("/calendars/user%40example.com/events")
        == "user@example.com"
    )
