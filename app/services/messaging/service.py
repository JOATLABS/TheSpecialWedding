"""Domain-level messaging service that orchestrates repository access."""

from __future__ import annotations

import asyncio
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
from app.services.messaging.repository import (
    FirestoreMessagingRepository,
    MessagingRepositoryError,
)


class MessagingService:
    """Facade for messaging operations used by API routes."""

    def __init__(self, repository: Optional[FirestoreMessagingRepository] = None) -> None:
        self._repository = repository or FirestoreMessagingRepository()

    async def create_conversation(
        self,
        payload: ConversationCreateRequest,
        *,
        created_by: str,
    ) -> ConversationResponse:
        try:
            return await asyncio.to_thread(
                self._repository.create_conversation,
                payload,
                created_by=created_by,
            )
        except MessagingRepositoryError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    async def send_message(
        self,
        conversation_id: str,
        payload: MessageCreateRequest,
    ) -> MessageResponse:
        try:
            return await asyncio.to_thread(
                self._repository.append_message,
                conversation_id,
                payload,
            )
        except MessagingRepositoryError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    async def get_conversation(self, conversation_id: str) -> ConversationResponse:
        try:
            result = await asyncio.to_thread(self._repository.get_conversation, conversation_id)
        except MessagingRepositoryError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
        return result

    async def list_conversations(
        self,
        *,
        wedding_id: Optional[str] = None,
        participant_id: Optional[str] = None,
        limit: int = 50,
        cursor: Optional[str] = None,
    ) -> ConversationListResponse:
        try:
            conversations, next_cursor = await asyncio.to_thread(
                self._repository.list_conversations,
                wedding_id=wedding_id,
                participant_id=participant_id,
                limit=limit,
                cursor=cursor,
            )
        except MessagingRepositoryError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

        return ConversationListResponse(items=conversations, next_cursor=next_cursor)

    async def list_messages(
        self,
        conversation_id: str,
        *,
        limit: int = 50,
        cursor: Optional[str] = None,
    ) -> MessageListResponse:
        try:
            messages, next_cursor = await asyncio.to_thread(
                self._repository.list_messages,
                conversation_id,
                limit=limit,
                cursor=cursor,
            )
        except MessagingRepositoryError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

        return MessageListResponse(messages=messages, next_cursor=next_cursor)

    async def acknowledge_read(
        self,
        conversation_id: str,
        participant_id: str,
        payload: ReadReceiptUpdateRequest,
    ) -> ReadReceiptResponse:
        try:
            participant = await asyncio.to_thread(
                self._repository.acknowledge_read,
                conversation_id,
                participant_id,
                read_at=payload.last_read_at,
            )
        except MessagingRepositoryError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

        if participant.last_read_at is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update read receipt",
            )

        return ReadReceiptResponse(
            conversation_id=conversation_id,
            participant_id=participant.user_id,
            last_read_at=participant.last_read_at,
        )
