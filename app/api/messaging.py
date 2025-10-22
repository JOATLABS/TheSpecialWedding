from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import AuthUser, get_current_user
from app.models.messaging import Conversation, Message, SendMessageRequest
from app.services.messaging_service import MessagingService

router = APIRouter(prefix="/messaging", tags=["Messaging"])
service = MessagingService()


def _ensure_participation(conversation: Conversation, participant_id: str) -> None:
    """Make sure the authenticated user is part of the conversation."""

    if participant_id not in conversation.participants:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only conversation participants may send messages.",
        )


@router.post(
    "/weddings/{wedding_id}/conversations/{conversation_id}/messages",
    response_model=Message,
    status_code=status.HTTP_201_CREATED,
)
def send_message(
    wedding_id: str,
    conversation_id: str,
    payload: SendMessageRequest,
    current_user: AuthUser = Depends(get_current_user),
) -> Message:
    """Send a new message in the context of a wedding conversation."""

    conversation: Conversation = service.get_conversation(wedding_id, conversation_id)
    participant_id = current_user.email
    _ensure_participation(conversation, participant_id)

    return service.send_message(wedding_id, conversation_id, participant_id, payload)
