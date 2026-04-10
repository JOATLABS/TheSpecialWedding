"""
Inbound Email API Routes

REST endpoints for planner inbox — viewing, reading, and replying
to inbound emails received from guests via Resend.

All endpoints require planner or admin authentication.
Planners can only see emails linked to their weddings.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.dependencies.auth_extended import ExtendedAuthUser, require_admin_or_planner
from app.services.inbound_email_service import inbound_email_service

logger = logging.getLogger(__name__)
router = APIRouter()


class ReplyRequest(BaseModel):
    """Request body for sending a reply"""

    html_content: str = Field(
        ..., min_length=1, max_length=50000, description="HTML content of reply"
    )
    text_content: Optional[str] = Field(
        None, max_length=50000, description="Plain text fallback"
    )


# ==================== INBOX ENDPOINTS ====================


@router.get("/inbound-emails/inbox", tags=["Inbound Emails"])
async def get_inbox(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    wedding_id: Optional[str] = Query(None, description="Filter by wedding ID"),
    unread_only: bool = Query(False, description="Show only unread emails"),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    Get planner's inbox with pagination.

    Returns list of inbound emails sorted by newest first,
    with unread count for badge display.
    """
    return await inbound_email_service.get_inbox(
        planner_id=current_user.email,
        wedding_id=wedding_id,
        page=page,
        limit=limit,
        unread_only=unread_only,
    )


@router.get("/inbound-emails/unread-count", tags=["Inbound Emails"])
async def get_unread_count(
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """Get unread email count for badge/notification display"""
    return await inbound_email_service.get_unread_count(current_user.email)


# ==================== SINGLE EMAIL ENDPOINTS ====================


@router.get("/inbound-emails/{email_id}", tags=["Inbound Emails"])
async def get_email(
    email_id: str, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Get a single inbound email with full content.

    Automatically marks the email as read.
    """
    return await inbound_email_service.get_email(email_id, current_user.email)


@router.get("/inbound-emails/threads/{thread_id}", tags=["Inbound Emails"])
async def get_thread(
    thread_id: str, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Get full email thread — both inbound and outbound messages.

    Merges inbound emails with outbound emails from email_logs,
    sorted chronologically to show the full conversation.
    """
    return await inbound_email_service.get_thread(thread_id, current_user.email)


# ==================== ACTION ENDPOINTS ====================


@router.put("/inbound-emails/{email_id}/read", tags=["Inbound Emails"])
async def mark_as_read(
    email_id: str, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Mark a single email as read"""
    return await inbound_email_service.mark_as_read(email_id, current_user.email)


@router.put("/inbound-emails/read-all", tags=["Inbound Emails"])
async def mark_all_as_read(
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """Mark all unread emails as read"""
    return await inbound_email_service.mark_all_as_read(current_user.email)


@router.post("/inbound-emails/{email_id}/reply", tags=["Inbound Emails"])
async def send_reply(
    email_id: str,
    reply: ReplyRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    Send a reply to an inbound email.

    The reply is sent via Resend with the same reply-to address
    encoding to maintain the conversation thread.
    """
    return await inbound_email_service.send_reply(
        email_id=email_id,
        planner_id=current_user.email,
        reply_html=reply.html_content,
        reply_text=reply.text_content,
    )
