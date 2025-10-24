from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies.auth import AuthUser, get_current_user
from app.models.messaging import (
    ConversationCreateRequest,
    ConversationListResponse,
    ConversationParticipant,
    ConversationResponse,
    MessageCreateRequest,
    MessageListResponse,
    MessageResponse,
    SendMessageRequest,
)
from app.services.messaging import MessagingRepositoryError, MessagingService

router = APIRouter(prefix="/messaging", tags=["Messaging"])


def get_messaging_service() -> MessagingService:
    """Construct a messaging service instance backed by Firestore."""

    try:
        return MessagingService()
    except MessagingRepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


def _get_participant(
    conversation: ConversationResponse, participant_id: str
) -> ConversationParticipant:
    """Return the participant object for the authenticated user."""

    for participant in conversation.participants:
        if participant.user_id == participant_id:
            return participant

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Only conversation participants may send messages.",
    )


@router.post(
    "/weddings/{wedding_id}/conversations/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    wedding_id: str,
    conversation_id: str,
    payload: SendMessageRequest,
    current_user: AuthUser = Depends(get_current_user),
    service: MessagingService = Depends(get_messaging_service),
) -> MessageResponse:
    """Send a new message in the context of a wedding conversation."""

    conversation, participant = await _get_authorized_conversation(
        wedding_id,
        conversation_id,
        current_user,
        service,
    )

    message_request = MessageCreateRequest(
        sender_id=current_user.email,
        sender_role=participant.role,
        body=payload.body,
        attachments=payload.attachments,
        linked_resource=payload.linked_resource,
        delivery_status=payload.delivery_status,
    )

    return await service.send_message(conversation_id, message_request)


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
