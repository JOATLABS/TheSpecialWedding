"""Messaging API routes with Soketi auth webhook.

This module provides:
1. REST endpoints for conversation/message CRUD
2. Soketi auth webhook for channel authorization

Real-time functionality is handled by Soketi (not WebSockets here).
The frontend connects directly to Soketi for real-time events.
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, Form, UploadFile, File

from app.dependencies.auth import AuthUser, get_current_user
from app.models.messaging import (
    ConversationCreateRequest,
    ConversationListResponse,
    ConversationParticipant,
    ConversationResponse,
    MessageCreateRequest,
    MessageListResponse,
    MessageResponse,
    ReadReceiptResponse,
    ReadReceiptUpdateRequest,
    SendMessageRequest,
    MessageAttachment,
)
from app.services.messaging import MessagingService, get_soketi_client
from app.core.r2 import upload_to_r2
from pydantic import BaseModel


router = APIRouter(prefix="/messaging", tags=["Messaging"])


# ---- Dependency injection ----

def get_messaging_service() -> MessagingService:
    """Construct a messaging service instance."""
    return MessagingService()


def _get_participant(
    conversation: ConversationResponse, participant_id: str
) -> ConversationParticipant:
    """Return the participant object for the authenticated user."""
    for participant in conversation.participants:
        if participant.user_id == participant_id:
            return participant

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Only conversation participants may access this conversation.",
    )


async def _get_authorized_conversation(
    wedding_id: str,
    conversation_id: str,
    current_user: AuthUser,
    service: MessagingService,
) -> tuple[ConversationResponse, ConversationParticipant]:
    """Return the conversation if the authenticated user has access."""
    conversation: ConversationResponse = await service.get_conversation(conversation_id)

    if conversation.wedding_id and conversation.wedding_id != wedding_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    participant = _get_participant(conversation, current_user.email)
    return conversation, participant


# ---- Soketi Auth Webhook ----

class SoketiAuthRequest(BaseModel):
    """Request body for Soketi channel auth."""
    socket_id: str
    channel_name: str


class SoketiAuthResponse(BaseModel):
    """Response for successful Soketi auth."""
    auth: str
    channel_data: Optional[str] = None


@router.post("/pusher/auth", response_model=SoketiAuthResponse)
async def pusher_auth(
    socket_id: str = Form(...),
    channel_name: str = Form(...),
    current_user: AuthUser = Depends(get_current_user),
    service: MessagingService = Depends(get_messaging_service),
) -> SoketiAuthResponse:
    """Authenticate a Soketi/Pusher channel subscription.

    This endpoint is called by the Pusher client when subscribing to
    private or presence channels. It verifies the user has access
    to the requested channel.

    Channel naming convention:
    - private-conversation-{conversation_id} : Conversation messages
    - private-user-{user_id} : User-specific notifications
    - presence-conversation-{conversation_id} : Online status / typing
    """
    soketi = get_soketi_client()

    # Handle different channel types
    if channel_name.startswith("private-conversation-"):
        # Verify user is a participant in the conversation
        conversation_id = channel_name.replace("private-conversation-", "")
        try:
            conversation = await service.get_conversation(conversation_id)
            _get_participant(conversation, current_user.email)
        except HTTPException:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to subscribe to this channel",
            )

        auth_response = soketi.generate_auth_token(socket_id, channel_name)

    elif channel_name.startswith("private-user-"):
        # User can only subscribe to their own channel
        user_id = channel_name.replace("private-user-", "")
        if user_id != current_user.email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot subscribe to another user's channel",
            )

        auth_response = soketi.generate_auth_token(socket_id, channel_name)

    elif channel_name.startswith("presence-conversation-"):
        # Verify user is a participant for presence channels
        conversation_id = channel_name.replace("presence-conversation-", "")
        try:
            conversation = await service.get_conversation(conversation_id)
            participant = _get_participant(conversation, current_user.email)
        except HTTPException:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to subscribe to this channel",
            )

        # Include user data for presence channels
        user_data = {
            "user_id": current_user.email,
            "user_info": {
                "role": participant.role.value,
            }
        }
        auth_response = soketi.generate_auth_token(
            socket_id, channel_name, user_data=user_data
        )

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown channel type: {channel_name}",
        )

    return SoketiAuthResponse(**auth_response)


# ---- Conversation endpoints ----

@router.post(
    "/weddings/{wedding_id}/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    wedding_id: str,
    payload: ConversationCreateRequest,
    current_user: AuthUser = Depends(get_current_user),
    service: MessagingService = Depends(get_messaging_service),
) -> ConversationResponse:
    """Create a conversation ensuring the requester is a participant."""
    if payload.wedding_id and payload.wedding_id != wedding_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload wedding_id must match requested wedding.",
        )

    participant_ids = {participant.user_id for participant in payload.participants}
    if current_user.email not in participant_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authenticated user must be a participant in the conversation.",
        )

    normalized_payload = payload
    if payload.wedding_id != wedding_id:
        normalized_payload = payload.model_copy(update={"wedding_id": wedding_id})

    return await service.create_conversation(normalized_payload, created_by=current_user.email)


@router.get(
    "/weddings/{wedding_id}/conversations",
    response_model=ConversationListResponse,
)
async def list_conversations(
    wedding_id: str,
    limit: int = Query(50, ge=1, le=100),
    cursor: Optional[str] = Query(default=None),
    current_user: AuthUser = Depends(get_current_user),
    service: MessagingService = Depends(get_messaging_service),
) -> ConversationListResponse:
    """List conversations for the authenticated participant within a wedding."""
    return await service.list_conversations(
        wedding_id=wedding_id,
        participant_id=current_user.email,
        limit=limit,
        cursor=cursor,
    )


@router.get(
    "/weddings/{wedding_id}/conversations/{conversation_id}",
    response_model=ConversationResponse,
)
async def get_conversation(
    wedding_id: str,
    conversation_id: str,
    current_user: AuthUser = Depends(get_current_user),
    service: MessagingService = Depends(get_messaging_service),
) -> ConversationResponse:
    """Return a conversation if the authenticated user participates."""
    conversation, _ = await _get_authorized_conversation(
        wedding_id,
        conversation_id,
        current_user,
        service,
    )
    return conversation


# ---- Message endpoints ----

@router.post(
    "/weddings/{wedding_id}/conversations/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    wedding_id: str,
    conversation_id: str,
    body: str = Form(...),
    socket_id: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    current_user: AuthUser = Depends(get_current_user),
    service: MessagingService = Depends(get_messaging_service),
) -> MessageResponse:
    """Send a new message in the context of a wedding conversation.

    The optional socket_id parameter can be passed to exclude the sender
    from receiving the real-time broadcast (they already have the message).
    """
    conversation, participant = await _get_authorized_conversation(
        wedding_id,
        conversation_id,
        current_user,
        service,
    )

    attachments = []
    if file:
        file_url = upload_to_r2(file, current_user.email)
        attachments.append(MessageAttachment(type="file", url=file_url, title=file.filename))

    message_request = MessageCreateRequest(
        sender_id=current_user.email,
        sender_role=participant.role,
        body=body,
        attachments=attachments,
    )

    return await service.send_message(
        conversation_id,
        message_request,
        socket_id=socket_id,
    )


@router.get(
    "/weddings/{wedding_id}/conversations/{conversation_id}/messages",
    response_model=MessageListResponse,
)
async def list_messages(
    wedding_id: str,
    conversation_id: str,
    limit: int = Query(50, ge=1, le=200),
    cursor: Optional[str] = Query(default=None),
    current_user: AuthUser = Depends(get_current_user),
    service: MessagingService = Depends(get_messaging_service),
) -> MessageListResponse:
    """List messages for a conversation after verifying participation."""
    await _get_authorized_conversation(wedding_id, conversation_id, current_user, service)

    return await service.list_messages(
        conversation_id,
        limit=limit,
        cursor=cursor,
    )


# ---- Read receipts ----

@router.post(
    "/weddings/{wedding_id}/conversations/{conversation_id}/read-receipts",
    response_model=ReadReceiptResponse,
)
async def acknowledge_read_receipt(
    wedding_id: str,
    conversation_id: str,
    payload: ReadReceiptUpdateRequest,
    current_user: AuthUser = Depends(get_current_user),
    service: MessagingService = Depends(get_messaging_service),
) -> ReadReceiptResponse:
    """Update the authenticated participant's read receipt for a conversation."""
    _, participant = await _get_authorized_conversation(
        wedding_id,
        conversation_id,
        current_user,
        service,
    )

    return await service.acknowledge_read(conversation_id, participant.user_id, payload)


# ---- Typing indicators ----

class TypingRequest(BaseModel):
    """Request body for typing indicator."""
    is_typing: bool
    socket_id: Optional[str] = None


@router.post(
    "/weddings/{wedding_id}/conversations/{conversation_id}/typing",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def broadcast_typing(
    wedding_id: str,
    conversation_id: str,
    payload: TypingRequest,
    current_user: AuthUser = Depends(get_current_user),
    service: MessagingService = Depends(get_messaging_service),
) -> None:
    """Broadcast typing indicator to conversation participants."""
    await _get_authorized_conversation(wedding_id, conversation_id, current_user, service)

    await service.broadcast_typing(
        conversation_id,
        current_user.email,
        payload.is_typing,
        socket_id=payload.socket_id,
    )
