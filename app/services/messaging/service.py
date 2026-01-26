"""Domain-level messaging service with MongoDB + Soketi real-time events."""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status

from app.models.messaging import (
    ConversationCreateRequest,
    ConversationListResponse,
    ConversationResponse,
    MessageCreateRequest,
    MessageListResponse,
    MessageResponse,
    ReadReceiptResponse,
    ReadReceiptUpdateRequest,
)
from app.services.messaging.mongo_repository import (
    MongoMessagingRepository,
    MessagingRepositoryError,
)
from app.services.messaging.soketi_client import get_soketi_client


class MessagingService:
    """Facade for messaging operations with real-time event triggering.

    This service:
    1. Persists messages/conversations to MongoDB
    2. Triggers Soketi events for real-time updates
    3. Handles authorization at the API layer (not here)

    Channel naming convention:
    - private-conversation-{id} : For conversation messages
    - private-wedding-{id}-inbox : For wedding-wide notifications
    - presence-conversation-{id} : For typing indicators / online status
    """

    def __init__(self, repository: Optional[MongoMessagingRepository] = None) -> None:
        self._repository = repository or MongoMessagingRepository()
        self._soketi = get_soketi_client()

    async def create_conversation(
        self,
        payload: ConversationCreateRequest,
        *,
        created_by: str,
    ) -> ConversationResponse:
        """Create a conversation and notify participants."""
        try:
            conversation = await self._repository.create_conversation(
                payload,
                created_by=created_by,
            )
        except MessagingRepositoryError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc)
            ) from exc

        # Trigger real-time event for each participant
        for participant in conversation.participants:
            await self._soketi.trigger(
                channel=f"private-user-{participant.user_id}",
                event="conversation-created",
                data={
                    "conversation_id": conversation.conversation_id,
                    "subject": conversation.subject,
                    "wedding_id": conversation.wedding_id,
                    "created_by": created_by,
                },
            )

        return conversation

    async def send_message(
        self,
        conversation_id: str,
        payload: MessageCreateRequest,
        *,
        socket_id: Optional[str] = None,
    ) -> MessageResponse:
        """Send a message and broadcast to conversation channel.

        Args:
            conversation_id: The conversation to send to
            payload: Message content
            socket_id: Optional sender's socket ID to exclude from broadcast
        """
        try:
            message = await self._repository.append_message(conversation_id, payload)
        except MessagingRepositoryError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc)
            ) from exc

        # Broadcast to conversation channel (excluding sender if socket_id provided)
        await self._soketi.trigger(
            channel=f"private-conversation-{conversation_id}",
            event="new-message",
            data={
                "message_id": message.message_id,
                "conversation_id": message.conversation_id,
                "sender_id": message.sender_id,
                "sender_role": message.sender_role.value,
                "body": message.body,
                "created_at": message.created_at.isoformat(),
                "attachments": [
                    att.model_dump(mode="json", exclude_none=True)
                    for att in message.attachments
                ],
                "linked_resource": (
                    message.linked_resource.model_dump(mode="json", exclude_none=True)
                    if message.linked_resource else None
                ),
            },
            socket_id=socket_id,
        )

        return message

    async def get_conversation(self, conversation_id: str) -> ConversationResponse:
        """Fetch a conversation by ID."""
        try:
            result = await self._repository.get_conversation(conversation_id)
        except MessagingRepositoryError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc)
            ) from exc

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        return result

    async def list_conversations(
        self,
        *,
        wedding_id: Optional[str] = None,
        participant_id: Optional[str] = None,
        limit: int = 50,
        cursor: Optional[str] = None,
    ) -> ConversationListResponse:
        """List conversations for a wedding or participant."""
        try:
            conversations, next_cursor = await self._repository.list_conversations(
                wedding_id=wedding_id,
                participant_id=participant_id,
                limit=limit,
                cursor=cursor,
            )
        except MessagingRepositoryError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc)
            ) from exc

        return ConversationListResponse(items=conversations, next_cursor=next_cursor)

    async def list_messages(
        self,
        conversation_id: str,
        *,
        limit: int = 50,
        cursor: Optional[str] = None,
    ) -> MessageListResponse:
        """List messages for a conversation."""
        try:
            messages, next_cursor = await self._repository.list_messages(
                conversation_id,
                limit=limit,
                cursor=cursor,
            )
        except MessagingRepositoryError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc)
            ) from exc

        return MessageListResponse(messages=messages, next_cursor=next_cursor)

    async def acknowledge_read(
        self,
        conversation_id: str,
        participant_id: str,
        payload: ReadReceiptUpdateRequest,
    ) -> ReadReceiptResponse:
        """Update read receipt and broadcast to conversation."""
        try:
            participant = await self._repository.acknowledge_read(
                conversation_id,
                participant_id,
                read_at=payload.last_read_at,
            )
        except MessagingRepositoryError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc)
            ) from exc

        if participant.last_read_at is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update read receipt",
            )

        # Broadcast read receipt to conversation participants
        await self._soketi.trigger(
            channel=f"private-conversation-{conversation_id}",
            event="read-receipt",
            data={
                "conversation_id": conversation_id,
                "participant_id": participant.user_id,
                "last_read_at": participant.last_read_at.isoformat(),
            },
        )

        return ReadReceiptResponse(
            conversation_id=conversation_id,
            participant_id=participant.user_id,
            last_read_at=participant.last_read_at,
        )

    async def broadcast_typing(
        self,
        conversation_id: str,
        user_id: str,
        is_typing: bool,
        *,
        socket_id: Optional[str] = None,
    ) -> None:
        """Broadcast typing indicator to conversation participants."""
        await self._soketi.trigger(
            channel=f"private-conversation-{conversation_id}",
            event="typing",
            data={
                "user_id": user_id,
                "is_typing": is_typing,
            },
            socket_id=socket_id,
        )
