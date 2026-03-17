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

    This mirrors the logic in get_current_user_extended but accepts a raw token
    string instead of reading from the Authorization header, because the browser
    EventSource API cannot send custom headers.
    """
    try:
        payload = verify_token(token)
    except Exception as e:
        logger.warning(f"SSE auth: token verification failed: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    email = payload.get("sub")
    if not email:
        logger.warning("SSE auth: no 'sub' claim in token payload")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    role = payload.get("role", "wedding_planner")
    root_admin_email = os.getenv("ROOT_ADMIN_EMAIL", "")

    user = await mongo.get_users_collection().find_one({"email": email})
    if not user:
        logger.warning(f"SSE auth: user not found in DB for email={email}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if email == root_admin_email:
        role = "ROOT_ADMIN"
        logger.debug(f"SSE auth: root admin authenticated: {email}")
    else:
        role = user.get("role", "wedding_planner")

        # Check if account is active
        if not user.get("is_active", True):
            logger.warning(f"SSE auth: account deactivated for {email}")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is deactivated")

        # Check email verification
        if not user.get("email_verified"):
            logger.warning(f"SSE auth: email not verified for {email}, email_verified={user.get('email_verified')}")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email not verified")

        # Check trial expiration for wedding planners
        if role == "wedding_planner" and user.get("subscription_status") == "trial":
            from datetime import datetime, timezone
            trial_end_date = user.get("trial_end_date")
            if trial_end_date:
                if isinstance(trial_end_date, str):
                    try:
                        trial_end_date = datetime.fromisoformat(trial_end_date.replace('Z', '+00:00'))
                    except ValueError:
                        trial_end_date = datetime.fromisoformat(trial_end_date).replace(tzinfo=timezone.utc)
                elif isinstance(trial_end_date, datetime) and trial_end_date.tzinfo is None:
                    trial_end_date = trial_end_date.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > trial_end_date:
                    raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Trial expired")

    user_data = user.copy()
    if "_id" in user_data and isinstance(user_data["_id"], ObjectId):
        user_data["_id"] = str(user_data["_id"])

    return ExtendedAuthUser(email=email, role=role, user_data=user_data)


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
