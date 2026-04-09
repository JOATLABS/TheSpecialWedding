"""
Couple SSE Notification Stream Endpoint

Streams real-time couple-portal data change events to authenticated couples.
Uses the existing `couple_token` HttpOnly session cookie for EventSource auth.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.dependencies.couple_auth import require_couple_auth
from app.services.sse_manager import sse_manager
from app.utils.couple_realtime import couple_sse_channel
from app.utils.id_utils import to_str_id

logger = logging.getLogger(__name__)

router = APIRouter()

HEARTBEAT_INTERVAL = 30


async def _event_stream(couple_id: str, request: Request):
    queue = sse_manager.connect(couple_sse_channel(couple_id))

    try:
        while True:
            if await request.is_disconnected():
                break

            try:
                event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_INTERVAL)
                if event["type"] == "data-change":
                    yield f"event: data-change\ndata: {json.dumps(event['data'])}\n\n"
            except asyncio.TimeoutError:
                yield ": heartbeat\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        sse_manager.disconnect(couple_sse_channel(couple_id), queue)


@router.get("/couple/notifications/stream", tags=["Couple Notifications SSE"])
async def couple_notification_stream(
    request: Request,
    couple: dict = Depends(require_couple_auth),
):
    return StreamingResponse(
        _event_stream(to_str_id(couple), request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
