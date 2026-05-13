"""Public webhook endpoint for Aurinko delivery notifications.

Provider-facing only. Planner-authenticated mutation endpoints (accept /
reject of an external change) live in ``planner_calendar.py``.

Aurinko delivery contract (per docs.aurinko.io/unified-apis/webhooks-api):

    {
        "subscription": "<subscription-id>",
        "resource":     "/calendars/{calId}/events",
        "accountId":    "<aurinko-account-id>",
        "payloads": [
            {"id": "<external-event-id>", "changeType": "created|updated|deleted"},
            ...
        ]
    }

Notes:
* No event snapshot is included — only ``id`` + ``changeType`` per item.
* ``calendarId`` is encoded inside ``resource`` and must be extracted there.
* Multiple changes can be batched in a single delivery.
* Aurinko retries any response that is not 200 or 422 (1, 2, 4, 8 ... seconds,
  capped at 10 minutes). Permanent rejections must use 422 explicitly so we
  don't loop indefinitely on malformed deliveries.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime
from typing import Any, Optional
from urllib.parse import unquote

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response

from app.services.calendar_idempotency_service import calendar_idempotency_service
from app.services.calendar_webhook_service import calendar_webhook_service

logger = logging.getLogger(__name__)

router = APIRouter()


# Resource string is "/calendars/{calId}/events" — calId may be url-encoded
# (some providers use email-style ids that contain "@") so we accept anything
# that isn't a literal "/".
_CALENDAR_RESOURCE_RE = re.compile(r"^/calendars/([^/]+)/events/?$")


def _coerce_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _extract_calendar_id(resource: Optional[str]) -> Optional[str]:
    if not resource:
        return None
    match = _CALENDAR_RESOURCE_RE.match(resource)
    if not match:
        return None
    # Aurinko URL-encodes ids that contain reserved chars (e.g. an @-form
    # email-style calendar id). We store the decoded id in Mongo at OAuth
    # callback time, so decode here to make the connection lookup match.
    return unquote(match.group(1))


@router.post(
    "/api/calendar/webhooks/aurinko",
    tags=["Calendar Webhooks"],
    include_in_schema=False,
)
async def aurinko_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> Response:
    """Aurinko webhook receiver.

    Verifies the signature, rejects replays older than the configured window,
    deduplicates by delivery id, and ack-200s before dispatching each change
    in ``payloads`` to a background task that resolves the snapshot.
    """
    raw_body = await request.body()
    signature = request.headers.get("X-Aurinko-Signature") or request.headers.get(
        "X-Webhook-Signature"
    )
    # X-Aurinko-Request-Timestamp is the unix-seconds value Aurinko signs
    # alongside the body. Per the spec the signature is over
    # ``v0:{timestamp}:{raw_body}`` — without the timestamp the hash cannot
    # be reconstructed.
    timestamp_header = request.headers.get("X-Aurinko-Request-Timestamp")
    if not calendar_webhook_service.verify_signature(
        raw_body, signature, timestamp_header
    ):
        # 401 keeps Aurinko retrying — appropriate for transient secret-rotation
        # races. Sustained 401s indicate a verifier mismatch (see SKILL note in
        # calendar_webhook_service.verify_signature).
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = await request.json()
    except Exception as exc:
        # Malformed JSON is permanent — 422 tells Aurinko to stop retrying.
        raise HTTPException(status_code=422, detail="Invalid JSON payload") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Webhook payload must be an object")

    # Aurinko does NOT include a deliveryId in webhook payloads (verified
    # against docs.aurinko.io/unified-apis/webhooks-api — the documented
    # body shape is {subscription, resource, accountId, payloads[]} with
    # no top-level delivery id). To dedupe, we derive a stable key from
    # the signed-request timestamp + body hash. Two genuine retries from
    # Aurinko hit the same key; two distinct events differ in body bytes.
    explicit_delivery_id = (
        payload.get("deliveryId")
        or payload.get("delivery_id")
        or request.headers.get("X-Aurinko-Delivery-Id")
    )
    if explicit_delivery_id:
        delivery_id: str = str(explicit_delivery_id)
    else:
        body_digest = hashlib.sha256(raw_body).hexdigest()
        subscription_part = str(payload.get("subscription") or "no-sub")
        ts_part = (timestamp_header or "no-ts").strip()
        delivery_id = f"aurinko:{subscription_part}:{ts_part}:{body_digest}"

    # Replay window is enforced against the signed timestamp (header) — the
    # value the signature actually covers. Falling back to a payload-internal
    # timestamp would let an attacker who captures one delivery resubmit it
    # any number of times outside the window.
    delivery_timestamp: Any = timestamp_header or _coerce_datetime(
        payload.get("timestamp") or payload.get("time")
    )

    # Replay-window and dedupe checks short-circuit with 200 (success) so
    # Aurinko stops retrying.
    if not calendar_webhook_service.is_within_replay_window(delivery_timestamp):
        return Response(status_code=200)

    if await calendar_webhook_service.is_duplicate_delivery(str(delivery_id)):
        return Response(status_code=200)

    try:
        aurinko_account_id = str(payload.get("accountId") or "")
        resource = payload.get("resource")
        aurinko_calendar_id = _extract_calendar_id(
            resource if isinstance(resource, str) else None
        )
        items = payload.get("payloads")

        # Lifecycle events (subscription health) arrive in the same delivery
        # channel but carry ``lifecycleEvent`` instead of ``payloads`` — see
        # https://docs.aurinko.io/unified-apis/webhooks-api ("Lifecycle events").
        # Ack 200 so Aurinko stops retrying; the polling drift-check job will
        # repair any lapsed subscription when credentials are refreshed.
        lifecycle_event = payload.get("lifecycleEvent")
        if lifecycle_event and not isinstance(items, list):
            await calendar_webhook_service.mark_delivery_processed(str(delivery_id))
            logger.info(
                "Aurinko lifecycle event ack 200: delivery=%s event=%s "
                "account=%s resource=%s err=%s",
                delivery_id,
                lifecycle_event,
                aurinko_account_id or "<unknown>",
                resource or "<unknown>",
                payload.get("error"),
            )
            return Response(status_code=200)

        # Signal-mode deliveries (subscriptions created with
        # ``detailLevel=signal``) arrive WITHOUT a ``payloads`` array — just
        # the {subscription, resource, accountId} envelope as a "ping that
        # something changed, fetch your own delta." We don't currently create
        # signal subscriptions, but if anyone ever does, returning 422 here
        # would PERMANENTLY UNSUBSCRIBE per Aurinko's 422 contract. Defensive
        # branch: when payloads is absent but the envelope is otherwise valid
        # (accountId + calendar resource present, no lifecycleEvent), ack 200
        # and rely on the drift-check job to backfill the actual change.
        if (
            aurinko_account_id
            and aurinko_calendar_id
            and items is None
            and not lifecycle_event
        ):
            await calendar_webhook_service.mark_delivery_processed(str(delivery_id))
            logger.info(
                "Aurinko signal-mode delivery ack 200 (no payloads): "
                "delivery=%s account=%s calendar=%s",
                delivery_id,
                aurinko_account_id,
                aurinko_calendar_id,
            )
            return Response(status_code=200)

        if (
            not aurinko_account_id
            or not aurinko_calendar_id
            or not isinstance(items, list)
        ):
            raise HTTPException(
                status_code=422,
                detail="Webhook missing accountId, resource, or payloads array",
            )

        queued = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            external_event_id = str(item.get("id") or "")
            change_type = str(item.get("changeType") or "updated").lower()
            if not external_event_id:
                continue
            # BackgroundTasks runs after the response is sent — Aurinko gets its
            # 200 ack immediately, snapshot fetch + planner_task update happen
            # off the request path.
            background_tasks.add_task(
                calendar_webhook_service.process_event_change_async,
                aurinko_account_id=aurinko_account_id,
                aurinko_calendar_id=aurinko_calendar_id,
                external_event_id=external_event_id,
                change_type=change_type,
            )
            queued += 1

        # Mark delivery processed before responding so a quick retry from Aurinko
        # short-circuits at the dedupe check rather than re-queueing background
        # tasks.
        await calendar_webhook_service.mark_delivery_processed(str(delivery_id))
        logger.info(
            "Aurinko webhook ack 200: delivery=%s items=%d queued=%d account=%s calendar=%s",
            delivery_id,
            len(items),
            queued,
            aurinko_account_id,
            aurinko_calendar_id,
        )
    except HTTPException:
        # Permanent client errors (422) — mark the idempotency record failed so
        # Aurinko can stop retrying and subsequent retries with the same
        # delivery_id are not suppressed as in_progress.
        await calendar_idempotency_service.fail(
            scope_key="aurinko_webhook",
            idempotency_key=str(delivery_id),
            error_detail="invalid_payload",
        )
        raise
    except Exception as exc:
        # Transient server errors — mark failed so retries are not suppressed.
        await calendar_idempotency_service.fail(
            scope_key="aurinko_webhook",
            idempotency_key=str(delivery_id),
            error_detail=str(exc),
        )
        raise

    return Response(status_code=200)
