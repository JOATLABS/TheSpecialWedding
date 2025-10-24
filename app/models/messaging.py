from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


MAX_MESSAGE_BODY_LENGTH = 5000


def _normalize_message_body(value: str) -> str:
    """Trim message bodies and ensure they contain meaningful content."""

    if not isinstance(value, str):
        raise TypeError("Message body must be a string.")

    stripped = value.strip()
    if not stripped:
        raise ValueError("Message body must include non-whitespace characters.")

    if len(stripped) > MAX_MESSAGE_BODY_LENGTH:
        raise ValueError(
            f"Message body must not exceed {MAX_MESSAGE_BODY_LENGTH} characters after trimming whitespace."
        )

    return stripped


def _utcnow() -> datetime:
    """Return an aware UTC timestamp for default field factories."""

    return datetime.now(timezone.utc)


class ParticipantRole(str, Enum):
    """Supported participant roles within a conversation."""

    PLANNER = "planner"
    VENDOR = "vendor"
    COUPLE = "couple"
    WEDDING_PARTY = "wedding_party"


class ConversationChannel(str, Enum):
    """Transport channel used by the conversation."""

    CHAT = "chat"
    EMAIL = "email"


class MessageAttachment(BaseModel):
    """Structured attachment included in a message."""

    type: str = Field(..., description="Domain identifier for the attachment type")
    reference_id: Optional[str] = Field(default=None, description="Primary identifier of the attached resource")
    title: Optional[str] = Field(default=None, description="Human readable name for the attachment")
    url: Optional[str] = Field(default=None, description="Optional deep link to the attached resource")
    metadata: Optional[Dict[str, object]] = Field(default=None, description="Additional attachment metadata")


class LinkedResource(BaseModel):
    """Contextual workflow artefact associated with a message."""

    resource_type: str = Field(..., description="Type of linked entity (form, budget, reminder, etc.)")
    resource_id: str = Field(..., description="Identifier of the linked entity")
    title: Optional[str] = Field(default=None, description="Optional display name for the linked resource")


class ConversationParticipant(BaseModel):
    """Participant metadata persisted with a conversation."""

    user_id: str = Field(..., description="Identifier for the participant user")
    role: ParticipantRole = Field(default=ParticipantRole.PLANNER, description="Role assigned to the participant")
    joined_at: datetime = Field(default_factory=_utcnow, description="Timestamp when the participant joined")
    mute: bool = Field(default=False, description="Whether notifications are muted for the participant")
    last_read_at: Optional[datetime] = Field(default=None, description="Last time the participant read the conversation")


class ConversationCreateRequest(BaseModel):
    """Payload required to create a conversation."""

    wedding_id: str = Field(..., description="Owning wedding identifier")
    channel: ConversationChannel = Field(default=ConversationChannel.CHAT, description="Conversation channel")
    subject: Optional[str] = Field(default=None, description="Optional subject or title for the conversation")
    participants: List[ConversationParticipant] = Field(..., description="Participants who should be added to the conversation")
    metadata: Optional[Dict[str, object]] = Field(default=None, description="Arbitrary metadata for the conversation")


class ConversationResponse(BaseModel):
    """Represents a persisted conversation."""

    conversation_id: str = Field(..., description="Unique identifier of the conversation")
    wedding_id: Optional[str] = Field(default=None, description="Owning wedding identifier")
    channel: ConversationChannel = Field(default=ConversationChannel.CHAT, description="Conversation channel")
    subject: Optional[str] = Field(default=None, description="Conversation subject or title")
    created_at: datetime = Field(default_factory=_utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=_utcnow, description="Last update timestamp")
    last_message_at: Optional[datetime] = Field(default=None, description="Timestamp of the most recent message")
    last_message_summary: Optional[str] = Field(default=None, description="Preview of the latest message body")
    metadata: Dict[str, object] = Field(default_factory=dict, description="Arbitrary metadata for the conversation")
    participants: List[ConversationParticipant] = Field(default_factory=list, description="Participants for the conversation")


class ConversationListResponse(BaseModel):
    """Paginated conversation listing."""

    items: List[ConversationResponse] = Field(default_factory=list, description="Returned conversations")
    next_cursor: Optional[str] = Field(default=None, description="Cursor to request the next page of results")


class MessageCreateRequest(BaseModel):
    """Payload required to append a message to a conversation."""

    sender_id: str = Field(..., description="Identifier of the user sending the message")
    sender_role: ParticipantRole = Field(default=ParticipantRole.PLANNER, description="Role of the sender")
    body: str = Field(
        ...,
        description="Content of the message (up to 5000 characters after trimming)",
    )
    attachments: Optional[List[MessageAttachment]] = Field(default=None, description="Attachments included with the message")
    linked_resource: Optional[LinkedResource] = Field(default=None, description="Contextual linked resource")
    delivery_status: Optional[str] = Field(default=None, description="Delivery state from downstream providers")

    @field_validator("body", mode="before")
    @classmethod
    def _prepare_message_body(cls, value: str) -> str:
        return _normalize_message_body(value)


class MessageResponse(BaseModel):
    """Represents a persisted message."""

    message_id: str = Field(..., description="Unique identifier of the message")
    conversation_id: str = Field(..., description="Conversation identifier")
    sender_id: Optional[str] = Field(default=None, description="Identifier of the sender")
    sender_role: ParticipantRole = Field(default=ParticipantRole.PLANNER, description="Role of the sender")
    body: str = Field(..., description="Content of the message")
    created_at: datetime = Field(default_factory=_utcnow, description="Creation timestamp")
    attachments: List[MessageAttachment] = Field(default_factory=list, description="Attachments included with the message")
    linked_resource: Optional[LinkedResource] = Field(default=None, description="Contextual linked resource")
    delivery_status: Optional[str] = Field(default=None, description="Delivery state from downstream providers")


class MessageListResponse(BaseModel):
    """Paginated message listing."""

    messages: List[MessageResponse] = Field(default_factory=list, description="Returned messages")
    next_cursor: Optional[str] = Field(default=None, description="Cursor to request the next page of results")


class SendMessageRequest(BaseModel):
    """API payload for sending a message from the authenticated participant."""

    body: str = Field(
        ...,
        description="Content of the outbound message (up to 5000 characters after trimming)",
    )
    attachments: Optional[List[MessageAttachment]] = Field(default=None, description="Attachments included with the message")
    linked_resource: Optional[LinkedResource] = Field(default=None, description="Contextual linked resource")
    delivery_status: Optional[str] = Field(default=None, description="Optional delivery state supplied by the client")

    @field_validator("body", mode="before")
    @classmethod
    def _prepare_send_body(cls, value: str) -> str:
        return _normalize_message_body(value)
