"""
Inbound Email Models

Models for handling inbound emails received via Resend's inbound webhook.
Supports two-way email communication between planners and guests.

Threading: Emails are linked via reply-to address encoding:
  reply+{wedding_slug}--{guest_id}@thespecialwedding.io
"""

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pydantic import BaseModel, Field


class EmailAttachmentMetadata(BaseModel):
    """Metadata about an email attachment (from webhook, before content fetch)"""

    filename: str = Field(..., max_length=255)
    content_type: str = Field(..., max_length=100)
    size: int | None = Field(None, ge=0)
    content_disposition: str | None = None


class InboundEmailContent(BaseModel):
    """Full email content retrieved from Resend API after webhook"""

    html_body: str | None = None
    text_body: str | None = None
    headers: dict[str, Any] = Field(default_factory=dict)
    reply_to: list[str] | None = None
    cc: list[str] = Field(default_factory=list)
    bcc: list[str] = Field(default_factory=list)
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    message_id: str | None = None
    raw_download_url: str | None = None


class InboundEmailThreadContext(BaseModel):
    """Context linking an inbound email to a wedding, planner, and guest"""

    wedding_id: str | None = Field(None, description="ObjectId of wedding")
    wedding_slug: str | None = Field(None, description="Wedding URL slug")
    assigned_planner_id: str | None = Field(
        None, description="Canonical planner user ID"
    )
    assigned_planner_email: str | None = Field(
        None, description="Canonical planner email snapshot"
    )
    thread_id: str | None = Field(None, description="Thread identifier: wedding-{slug}")
    guest_id: str | None = Field(None, description="ObjectId of guest if identifiable")
    guest_name: str | None = Field(None, description="Guest name for quick display")


class InboundEmailResponse(BaseModel):
    """API response model for inbox listing"""

    id: str
    from_address: str
    from_name: str | None = None
    subject: str
    preview: str
    thread_id: str | None = None
    guest_name: str | None = None
    wedding_slug: str | None = None
    wedding_id: str | None = None
    is_read: bool
    planner_response_sent: bool
    created_at: str
    has_attachments: bool
    status: str


class InboundEmailDetailResponse(InboundEmailResponse):
    """API response model for single email with full content"""

    html_body: str | None = None
    text_body: str | None = None
    attachments: list[dict[str, Any]] = Field(default_factory=list)


class ReplyModel(BaseModel):
    """Request model for sending a reply to an inbound email"""

    html_content: str = Field(..., min_length=1, max_length=50000)
    text_content: str | None = Field(None, max_length=50000)


def create_inbound_email_document(
    resend_email_id: str,
    from_address: str,
    to_address: str,
    subject: str,
    from_name: str | None = None,
    attachments_metadata: list[dict] | None = None,
    thread_context: dict | None = None,
    svix_id: str | None = None,
) -> dict:
    """
    Create an inbound email document for MongoDB insertion.

    Called when email.received webhook fires. Content is fetched
    separately and updated later.
    """
    now = datetime.now(UTC)

    return {
        "_id": ObjectId(),
        # Metadata from webhook
        "resend_email_id": resend_email_id,
        "from_address": from_address,
        "from_name": from_name,
        "to_address": to_address,
        "subject": subject or "(No subject)",
        "attachments_metadata": attachments_metadata or [],
        # Content (populated after API fetch)
        "content": None,
        # Threading
        "thread_context": thread_context or {},
        # Processing status
        "status": "received",  # received | content_fetched | processed | error
        "content_fetch_attempts": 0,
        "content_fetch_last_error": None,
        # Planner state
        "is_read": False,
        "read_at": None,
        "planner_response_sent": False,
        # Timestamps
        "created_at": now,
        "content_fetched_at": None,
        "updated_at": now,
        # Deduplication
        "svix_id": svix_id,
    }
