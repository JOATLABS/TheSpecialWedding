"""Public webhook endpoint for Aurinko delivery notifications.

Provider-facing only. Planner-authenticated mutation endpoints (accept /
reject of an external change) live in ``planner_calendar.py``.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request, Response

from app.services.calendar_webhook_service import calendar_webhook_service

logger = logging.getLogger(__name__)

router = APIRouter()


def _coerce_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


@router.post(
    "/api/calendar/webhooks/aurinko",
    tags=["Calendar Webhooks"],
    include_in_schema=False,
)
async def aurinko_webhook(request: Request) -> Response:
    """Aurinko webhook receiver.

    Verifies the HMAC signature, rejects replays older than the configured
    window, deduplicates by delivery ID, and dispatches the change to
    ``calendar_webhook_service`` for application to ``planner_tasks``.
    """
    raw_body = await request.body()
    signature = request.headers.get("X-Aurinko-Signature") or request.headers.get(
        "X-Webhook-Signature"
    )
    if not calendar_webhook_service.verify_signature(raw_body, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Webhook payload must be an object")

    delivery_id = (
        payload.get("deliveryId")
        or payload.get("delivery_id")
        or payload.get("id")
        or request.headers.get("X-Aurinko-Delivery-Id")
    )
    delivery_timestamp = _coerce_datetime(
        payload.get("timestamp") or payload.get("time")
    )

    if not delivery_id:
        raise HTTPException(status_code=400, detail="Webhook missing delivery id")

    if not calendar_webhook_service.is_within_replay_window(delivery_timestamp):
        return Response(status_code=204)

    if await calendar_webhook_service.is_duplicate_delivery(str(delivery_id)):
        return Response(status_code=204)

    aurinko_account_id = str(
        payload.get("accountId") or payload.get("account_id") or ""
    )
    aurinko_calendar_id = str(
        payload.get("calendarId")
        or payload.get("calendar_id")
        or (payload.get("subscription") or {}).get("calendarId")
        or ""
    )
    external_event_id = str(
        payload.get("eventId")
        or payload.get("event_id")
        or (payload.get("event") or {}).get("id")
        or ""
    )
    change_type = str(
        payload.get("changeType")
        or payload.get("change_type")
        or payload.get("type")
        or "updated"
    ).lower()
    snapshot = payload.get("event") or payload.get("snapshot") or {}

    if not aurinko_account_id or not aurinko_calendar_id or not external_event_id:
        raise HTTPException(
            status_code=400,
            detail="Webhook missing account/calendar/event id",
        )

    result = await calendar_webhook_service.handle_event_change(
        aurinko_account_id=aurinko_account_id,
        aurinko_calendar_id=aurinko_calendar_id,
        external_event_id=external_event_id,
        change_type=change_type,
        snapshot=snapshot,
    )
    await calendar_webhook_service.mark_delivery_processed(str(delivery_id))
    logger.info("Aurinko webhook processed: %s", result)
    return Response(status_code=204)
