"""Pydantic models for the messaging domain."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, constr


class ParticipantRole(str, Enum):
    """Roles that can participate in a conversation."""

    PLANNER = "planner"
    VENDOR = "vendor"
    COUPLE = "couple"
    WEDDING_PARTY = "wedding_party"


class ConversationChannel(str, Enum):
    """Supported conversation channels."""

    CHAT = "chat"
    EMAIL = "email"


class MessageAttachment(BaseModel):
    """Attachment metadata for messages."""

    type: constr(strip_whitespace=True, min_length=1) = Field(..., description="Attachment type identifier")
    reference_id: Optional[str] = Field(
        default=None,
        description="Identifier of the referenced resource (form, budget, etc.)",
    )
    url: Optional[str] = Field(default=None, description="Public URL for file-based attachments")
    label: Optional[str] = Field(default=None, description="Human readable label for the attachment")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary structured metadata")


class LinkedResource(BaseModel):
    """Explicit linkage to a workflow entity."""

    resource_type: constr(strip_whitespace=True, min_length=1)
    resource_id: constr(strip_whitespace=True, min_length=1)
    snapshot: Dict[str, Any] = Field(default_factory=dict)


class ConversationParticipant(BaseModel):
    """Participant entry stored under the conversation document."""

    user_id: constr(strip_whitespace=True, min_length=1)
    role: ParticipantRole
    joined_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    mute: bool = False
    last_read_at: Optional[datetime] = None


class ConversationCreateRequest(BaseModel):
    """Payload for creating a new conversation."""

    wedding_id: constr(strip_whitespace=True, min_length=1)
    channel: ConversationChannel = ConversationChannel.CHAT
    subject: Optional[str] = None
    participants: List[ConversationParticipant]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MessageCreateRequest(BaseModel):
    """Payload for sending a message."""

    sender_id: constr(strip_whitespace=True, min_length=1)
    sender_role: ParticipantRole
    body: constr(strip_whitespace=True, min_length=1)
    attachments: List[MessageAttachment] = Field(default_factory=list)
    linked_resource: Optional[LinkedResource] = None
    delivery_status: Optional[str] = Field(default="sent")


class ConversationResponse(BaseModel):
    """API response for conversations."""

    id: str = Field(..., alias="conversation_id")
    wedding_id: str
    channel: ConversationChannel
    subject: Optional[str]
    created_at: datetime
    updated_at: datetime
    last_message_at: Optional[datetime] = None
    last_message_summary: Optional[str] = None
    metadata: Dict[str, Any]
    participants: List[ConversationParticipant]

    model_config = {
        "populate_by_name": True,
    }


class MessageResponse(BaseModel):
    """API response for messages."""

    id: str = Field(..., alias="message_id")
    conversation_id: str
    sender_id: str
    sender_role: ParticipantRole
    body: str
    created_at: datetime
    attachments: List[MessageAttachment] = Field(default_factory=list)
    linked_resource: Optional[LinkedResource] = None
    delivery_status: Optional[str] = None

    model_config = {
        "populate_by_name": True,
    }


class ConversationListResponse(BaseModel):
    """Paginated response for conversations."""

    items: List[ConversationResponse]
    next_cursor: Optional[str] = None


class MessageListResponse(BaseModel):
    """Paginated response for messages."""

    messages: List[MessageResponse]
    next_cursor: Optional[str] = None
