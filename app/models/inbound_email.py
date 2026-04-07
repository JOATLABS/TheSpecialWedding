"""
Inbound Email Models

Models for handling inbound emails received via Resend's inbound webhook.
Supports two-way email communication between planners and guests.

Threading: Emails are linked via reply-to address encoding:
  reply+{wedding_slug}--{guest_id}@thespecialwedding.io
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from bson import ObjectId


class EmailAttachmentMetadata(BaseModel):
    """Metadata about an email attachment (from webhook, before content fetch)"""

    filename: str = Field(..., max_length=255)
    content_type: str = Field(..., max_length=100)
    size: Optional[int] = Field(None, ge=0)
    content_disposition: Optional[str] = None


class InboundEmailContent(BaseModel):
    """Full email content retrieved from Resend API after webhook"""

    html_body: Optional[str] = None
    text_body: Optional[str] = None
    headers: Dict[str, Any] = Field(default_factory=dict)
    reply_to: Optional[List[str]] = None
    cc: List[str] = Field(default_factory=list)
    bcc: List[str] = Field(default_factory=list)
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    message_id: Optional[str] = None
    raw_download_url: Optional[str] = None


class InboundEmailThreadContext(BaseModel):
    """Context linking an inbound email to a wedding, planner, and guest"""

    wedding_id: Optional[str] = Field(None, description="ObjectId of wedding")
    wedding_slug: Optional[str] = Field(None, description="Wedding URL slug")
    planner_id: Optional[str] = Field(None, description="Planner email/ID")
    thread_id: Optional[str] = Field(
        None, description="Thread identifier: wedding-{slug}"
    )
    guest_id: Optional[str] = Field(
        None, description="ObjectId of guest if identifiable"
    )
    guest_name: Optional[str] = Field(None, description="Guest name for quick display")


class InboundEmailResponse(BaseModel):
    """API response model for inbox listing"""

    id: str
    from_address: str
    from_name: Optional[str] = None
    subject: str
    preview: str
    thread_id: Optional[str] = None
    guest_name: Optional[str] = None
    wedding_slug: Optional[str] = None
    wedding_id: Optional[str] = None
    is_read: bool
    planner_response_sent: bool
    created_at: str
    has_attachments: bool
    status: str


class InboundEmailDetailResponse(InboundEmailResponse):
    """API response model for single email with full content"""

    html_body: Optional[str] = None
    text_body: Optional[str] = None
    attachments: List[Dict[str, Any]] = Field(default_factory=list)


class ReplyModel(BaseModel):
    """Request model for sending a reply to an inbound email"""

    html_content: str = Field(..., min_length=1, max_length=50000)
    text_content: Optional[str] = Field(None, max_length=50000)


def create_inbound_email_document(
    resend_email_id: str,
    from_address: str,
    to_address: str,
    subject: str,
    from_name: Optional[str] = None,
    attachments_metadata: Optional[List[Dict]] = None,
    thread_context: Optional[Dict] = None,
    svix_id: Optional[str] = None,
) -> dict:
    """
    Create an inbound email document for MongoDB insertion.

    Called when email.received webhook fires. Content is fetched
    separately and updated later.
    """
    now = datetime.now(timezone.utc)

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
