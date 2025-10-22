from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class Conversation(BaseModel):
    """Represents a messaging conversation in the system."""

    id: str = Field(..., description="Unique identifier of the conversation")
    wedding_id: str = Field(..., description="Identifier of the owning wedding")
    participants: List[str] = Field(default_factory=list, description="User identifiers allowed to interact")
    title: Optional[str] = Field(default=None, description="Display name for the conversation")
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")


class Message(BaseModel):
    """Represents a single message belonging to a conversation."""

    id: str = Field(..., description="Unique identifier of the message")
    wedding_id: str = Field(..., description="Identifier of the owning wedding")
    conversation_id: str = Field(..., description="Identifier of the conversation")
    sender_id: str = Field(..., description="Identifier of the user who sent the message")
    body: str = Field(..., description="Message contents")
    created_at: datetime = Field(..., description="Creation timestamp")


class SendMessageRequest(BaseModel):
    """Payload required to create a new outbound message."""

    body: str = Field(..., description="Message contents")
