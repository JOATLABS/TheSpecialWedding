"""Unit tests for the Aurinko webhook service.

Signature verification and replay-window checks are pure functions that can
be exercised without a live database.

Aurinko's spec
(docs.aurinko.io/unified-apis/webhooks-api/authentication):

    base_string = "v0:{X-Aurinko-Request-Timestamp}:{raw_body}"
    signature   = HMAC-SHA256(signing_secret, base_string).hex()

The signing secret is the *Signing secret* shown on the app dashboard
(distinct from the client secret used for OAuth).
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from datetime import UTC, datetime, timedelta

os.environ.setdefault("AURINKO_WEBHOOK_SECRET", "test-webhook-secret")
os.environ.setdefault("ENVIRONMENT", "test")

from app.services.calendar_webhook_service import calendar_webhook_service  # noqa: E402


def _sign(
    body: bytes,
    timestamp: str,
    secret: str = "test-webhook-secret",
) -> str:
    """Reproduce Aurinko's signature algorithm exactly: v0:{ts}:{body}."""
    base_string = b"v0:" + timestamp.encode("utf-8") + b":" + body
    return hmac.new(secret.encode("utf-8"), base_string, hashlib.sha256).hexdigest()


def test_verify_signature_accepts_valid_v0_signature() -> None:
    body = b'{"subscription":1217,"resource":"/calendars/c/events","accountId":1,"payloads":[]}'
    timestamp = str(int(time.time()))
    signature = _sign(body, timestamp)
    assert calendar_webhook_service.verify_signature(body, signature, timestamp) is True


def test_verify_signature_rejects_signature_computed_without_timestamp_prefix() -> None:
    """Naive HMAC over the body alone (the pre-rewrite scheme) must fail —
    catches regressions back to the old implementation."""
    body = b'{"id":"d1"}'
    timestamp = str(int(time.time()))
    plain_hmac = hmac.new(b"test-webhook-secret", body, hashlib.sha256).hexdigest()
    assert (
        calendar_webhook_service.verify_signature(body, plain_hmac, timestamp) is False
    )


def test_verify_signature_rejects_when_timestamp_missing() -> None:
    """Spec REQUIRES the timestamp to reconstruct the base string. Missing
    timestamp = unverifiable = reject (not permit)."""
    body = b'{"id":"d1"}'
    timestamp = str(int(time.time()))
    valid_signature = _sign(body, timestamp)
    assert (
        calendar_webhook_service.verify_signature(body, valid_signature, None) is False
    )
    assert calendar_webhook_service.verify_signature(body, valid_signature, "") is False


def test_verify_signature_rejects_missing_or_bad_signature() -> None:
    body = b'{"id":"d1"}'
    timestamp = str(int(time.time()))
    assert calendar_webhook_service.verify_signature(body, None, timestamp) is False
    assert (
        calendar_webhook_service.verify_signature(body, "not-the-real-hmac", timestamp)
        is False
    )


def test_verify_signature_is_sensitive_to_body_tampering() -> None:
    body = b'{"id":"d1"}'
    tampered = b'{"id":"d2"}'  # one byte changed
    timestamp = str(int(time.time()))
    signature = _sign(body, timestamp)
    assert (
        calendar_webhook_service.verify_signature(tampered, signature, timestamp)
        is False
    )


def test_verify_signature_is_sensitive_to_timestamp_tampering() -> None:
    """An attacker can't swap the timestamp without invalidating the hash —
    this is the replay-protection guarantee at the cryptographic layer."""
    body = b'{"id":"d1"}'
    timestamp = str(int(time.time()))
    signature = _sign(body, timestamp)
    tampered_ts = str(int(time.time()) - 10000)
    assert (
        calendar_webhook_service.verify_signature(body, signature, tampered_ts) is False
    )


def test_replay_window_rejects_old_deliveries_datetime() -> None:
    very_old = datetime.now(UTC) - timedelta(hours=1)
    assert calendar_webhook_service.is_within_replay_window(very_old) is False


def test_replay_window_rejects_old_deliveries_unix_seconds_string() -> None:
    """X-Aurinko-Request-Timestamp is delivered as a numeric string."""
    long_ago = str(int(time.time()) - 3600)
    assert calendar_webhook_service.is_within_replay_window(long_ago) is False


def test_replay_window_accepts_recent_deliveries_datetime() -> None:
    fresh = datetime.now(UTC) - timedelta(seconds=10)
    assert calendar_webhook_service.is_within_replay_window(fresh) is True


def test_replay_window_accepts_recent_deliveries_unix_seconds_string() -> None:
    fresh = str(int(time.time()) - 5)
    assert calendar_webhook_service.is_within_replay_window(fresh) is True


def test_replay_window_accepts_missing_timestamp() -> None:
    """Without a timestamp we can't verify replay; permit and rely on
    signature + dedupe."""
    assert calendar_webhook_service.is_within_replay_window(None) is True


# ============================================================================
# Webhook handler payload-parser tests — pin the parser against Aurinko's
# documented delivery shape: {subscription, resource, accountId, payloads[]}.
# ============================================================================


from app.api.calendar_webhooks import (  # noqa: E402
    _extract_calendar_id,
    _extract_tasklist_id,
    _resource_kind,
)


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
    assert _extract_calendar_id("/tasklists/default/tasks") is None
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


def test_extract_tasklist_id_from_task_resource() -> None:
    assert _extract_tasklist_id("/tasklists/default/tasks") == "default"
    assert _extract_tasklist_id("/tasklists/list-123/tasks/") == "list-123"


def test_extract_tasklist_id_decodes_url_encoded_tasklist() -> None:
    assert (
        _extract_tasklist_id("/tasklists/user%40example.com/tasks")
        == "user@example.com"
    )


def test_resource_kind_classifies_supported_resources() -> None:
    assert _resource_kind("/calendars/cal-abc/events") == ("calendar", "cal-abc")
    assert _resource_kind("/tasklists/default/tasks") == ("tasklist", "default")
    assert _resource_kind("/contacts") == ("contacts", "contacts")
    assert _resource_kind("/unknown/resource") == (None, None)


# ============================================================================
# Signal-mode delivery handling (defensive branch).
# ============================================================================
#
# Aurinko subscriptions support ``detailLevel=signal`` which delivers a
# webhook without a ``payloads`` array — the envelope is just
# ``{subscription, resource, accountId}``. We don't currently create
# signal subscriptions, but the handler must NOT 422 on them, because
# Aurinko's 422 contract is "unsubscribe permanently." These tests pin the
# defensive branch.


def _signed_post(client, body_bytes: bytes, ts: str, secret: str):
    """Helper: POST raw bytes with a valid Aurinko v0 signature header."""
    import hmac as _hmac
    import hashlib as _hashlib

    base = b"v0:" + ts.encode("utf-8") + b":" + body_bytes
    sig = _hmac.new(secret.encode("utf-8"), base, _hashlib.sha256).hexdigest()
    return client.post(
        "/api/calendar/webhooks/aurinko",
        content=body_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Aurinko-Signature": sig,
            "X-Aurinko-Request-Timestamp": ts,
        },
    )


def test_signal_mode_envelope_is_accepted_without_payloads_array() -> None:
    """If a signal-mode delivery ever lands, the handler ack-200s instead of
    422-unsubscribing. Hits the real FastAPI route via TestClient with a
    properly-signed body so the full handler runs. Requires a reachable
    Mongo for the idempotency store; skip if not available rather than
    fail (so unit-test runs without infra still pass the rest of this file)."""
    import time as _time
    import pytest as _pytest
    from fastapi.testclient import TestClient
    from app.main import app

    secret = os.environ["AURINKO_WEBHOOK_SECRET"]
    ts = str(int(_time.time()))
    # Signal-mode envelope: no `payloads`, no `lifecycleEvent`.
    body = (
        b'{"subscription":1217,"resource":"/calendars/cal-abc/events","accountId":1532}'
    )
    try:
        with TestClient(app) as client:
            r = _signed_post(client, body, ts, secret)
    except RuntimeError as exc:
        if "MongoDB" in str(exc) or "Mongo" in str(exc):
            _pytest.skip(f"Mongo not reachable in this env: {exc}")
        raise
    assert r.status_code == 200, (
        f"signal-mode delivery must ack 200 to avoid the Aurinko 422-unsubscribe "
        f"footgun. Got {r.status_code}: {r.text[:200]}"
    )
