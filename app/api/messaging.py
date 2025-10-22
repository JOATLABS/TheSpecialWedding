from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import AuthUser, get_current_user
from app.models.messaging import (
    ConversationParticipant,
    ConversationResponse,
    MessageCreateRequest,
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

    conversation: ConversationResponse = await service.get_conversation(conversation_id)

    if conversation.wedding_id and conversation.wedding_id != wedding_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    participant_id = current_user.email
    participant = _get_participant(conversation, participant_id)

    message_request = MessageCreateRequest(
        sender_id=participant_id,
        sender_role=participant.role,
        body=payload.body,
        attachments=payload.attachments,
        linked_resource=payload.linked_resource,
        delivery_status=payload.delivery_status,
    )

    return await service.send_message(conversation_id, message_request)
