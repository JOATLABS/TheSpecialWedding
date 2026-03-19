"""
SSE Notification Stream Endpoint

Streams real-time notification count updates to connected admin/planner users.
Replaces the 60-second polling pattern in TopHeader.tsx.

Authentication: Accepts JWT via query parameter (?token=...) because the browser
EventSource API does not support custom headers. The token is validated identically
to the Authorization header used by REST endpoints.
"""

import asyncio
import json
import logging
import os
from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from app.utils.auth_utils import verify_token
from app.core.database import mongo
from app.dependencies.auth_extended import ExtendedAuthUser
from app.services.sse_manager import sse_manager
from app.services.notification_service import NotificationService
from app.services.planner_notification_service import planner_notification_service
from bson import ObjectId

logger = logging.getLogger(__name__)

router = APIRouter()
notification_service = NotificationService()

# Heartbeat interval (seconds) — keeps the connection alive through proxies/load balancers
HEARTBEAT_INTERVAL = 30


async def _authenticate_from_query(token: str) -> ExtendedAuthUser:
    """Validate a JWT passed as a query parameter and return an ExtendedAuthUser.

    Reuses get_current_user_extended by constructing a fake credentials object,
    so SSE auth stays in sync with the main auth logic automatically.
    The browser EventSource API cannot send custom headers, so the token
    comes via query parameter instead.
    """
    from fastapi.security import HTTPAuthorizationCredentials
    from app.dependencies.auth_extended import get_current_user_extended

    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    try:
        return await get_current_user_extended(credentials=credentials)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"SSE auth failed: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed")


async def _get_combined_count(user_email: str, user_role: str) -> dict:
    """Fetch combined notification count from both services."""
    total_unread = 0

    try:
        platform_counts = await notification_service.get_user_notification_count(
            user_email=user_email, user_role=user_role
        )
        total_unread += platform_counts.get("unread", 0)
    except Exception as e:
        logger.warning(f"SSE: Failed to get platform notification count: {e}")

    try:
        activity_counts = await planner_notification_service.get_notification_count(
            planner_id=user_email
        )
        total_unread += activity_counts.get("unread", 0)
    except Exception:
        pass  # Expected for root admin

    return {"unread": total_unread}


async def _event_stream(user_email: str, user_role: str, request: Request):
    """Generator that yields SSE events."""

    queue = sse_manager.connect(user_email)

    try:
        # Send initial count immediately on connection
        initial = await _get_combined_count(user_email, user_role)
        yield f"event: notification-count\ndata: {json.dumps(initial)}\n\n"

        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                break

            try:
                # Wait for an event with a timeout (heartbeat interval)
                event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_INTERVAL)

                if event["type"] == "notification-count":
                    yield f"event: notification-count\ndata: {json.dumps(event['data'])}\n\n"
                elif event["type"] == "notification-new":
                    # Push the new notification detail AND the updated count
                    yield f"event: notification-new\ndata: {json.dumps(event['data'])}\n\n"
                    # Also send an updated count
                    counts = await _get_combined_count(user_email, user_role)
                    yield f"event: notification-count\ndata: {json.dumps(counts)}\n\n"
                elif event["type"] == "data-change":
                    # Real-time data invalidation signal — tells the frontend
                    # which resource changed so it can refetch the relevant data.
                    yield f"event: data-change\ndata: {json.dumps(event['data'])}\n\n"

            except asyncio.TimeoutError:
                # No events — send heartbeat to keep connection alive
                yield f": heartbeat\n\n"

    except asyncio.CancelledError:
        pass
    finally:
        sse_manager.disconnect(user_email, queue)


@router.get("/notifications/stream", tags=["Notifications SSE"])
async def notification_stream(
    request: Request,
    token: str = Query(..., description="JWT auth token (EventSource cannot send headers)"),
):
    """
    SSE endpoint for real-time notification count updates.

    Pass your JWT as `?token=<jwt>` since the browser EventSource API cannot
    send Authorization headers.

    Streams events:
    - `notification-count`: { unread: number } — sent on connect and whenever count changes
    - `notification-new`: { title, message, type, ... } — sent when a new notification arrives

    Heartbeat comments sent every 30s to keep the connection alive.
    """
    current_user = await _authenticate_from_query(token)

    return StreamingResponse(
        _event_stream(current_user.email, current_user.role, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
