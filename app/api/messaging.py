"""Messaging API endpoints for Firebase-backed conversations."""

from __future__ import annotations

from typing import Dict, List, Optional, Set

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies.auth_extended import (
    ExtendedAuthUser,
    get_current_user_extended,
)
from app.models.messaging import (
    ConversationCreateRequest,
    ConversationParticipant,
    ConversationResponse,
    ConversationListResponse,
    MessageCreateRequest,
    MessageResponse,
    MessageListResponse,
    ParticipantRole,
)
from app.services.firebase import FirebaseAuthService
from app.services.messaging.repository import MessagingRepositoryError
from app.services.messaging.service import MessagingService

router = APIRouter()


def _resolve_user_id(user: ExtendedAuthUser) -> str:
    if user.user_data and user.user_data.get("_id"):
        return str(user.user_data["_id"])
    return user.email


def _resolve_participant_role(user: ExtendedAuthUser) -> ParticipantRole:
    if user.is_root_admin or user.is_wedding_planner or user.is_legacy_admin:
        return ParticipantRole.PLANNER

    if user.is_vendor:
        return ParticipantRole.VENDOR

    role = (user.user_data or {}).get("role") or user.role
    role_map = {
        "planner": ParticipantRole.PLANNER,
        "wedding_planner": ParticipantRole.PLANNER,
        "vendor": ParticipantRole.VENDOR,
        "couple": ParticipantRole.COUPLE,
        "wedding_party": ParticipantRole.WEDDING_PARTY,
    }
    return role_map.get(str(role), ParticipantRole.PLANNER)


def _collect_wedding_scope(user: ExtendedAuthUser) -> List[str]:
    """Return the list of wedding IDs a user can access."""
    if user.is_root_admin:
        return ["*"]

    data = user.user_data or {}
    wedding_ids: List[str] = []

    if user.is_wedding_planner:
        planner_weddings = data.get("weddings") or data.get("wedding_ids") or []
        wedding_ids.extend(str(w) for w in planner_weddings)

    if user.is_vendor:
        vendor_weddings = data.get("assigned_wedding_ids") or data.get("wedding_ids") or []
        wedding_ids.extend(str(w) for w in vendor_weddings)

    if not wedding_ids and data.get("wedding_id"):
        wedding_ids.append(str(data["wedding_id"]))

    return list({w for w in wedding_ids if w})


def _ensure_wedding_permission(user: ExtendedAuthUser, wedding_id: str) -> None:
    """Ensure the authenticated user can access the provided wedding."""
    if user.is_root_admin:
        return

    allowed_ids = set(_collect_wedding_scope(user))
    if "*" in allowed_ids:
        return

    if wedding_id not in allowed_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Wedding access denied")


@router.post("/messaging/firebase-token", response_model=Dict[str, str], tags=["Messaging"])
async def mint_firebase_custom_token(
    current_user: ExtendedAuthUser = Depends(get_current_user_extended),
):
    """Create a Firebase custom token for the authenticated user."""
    auth_service = FirebaseAuthService()
    uid = _resolve_user_id(current_user)

    claims: Dict[str, Optional[str] | List[str]] = {
        "email": current_user.email,
        "role": current_user.role,
    }

    wedding_scope = _collect_wedding_scope(current_user)
    if wedding_scope:
        claims["wedding_ids"] = wedding_scope

    try:
        token = await auth_service.create_custom_token(uid, claims)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return {"token": token}


def _get_messaging_service() -> MessagingService:
    try:
        return MessagingService()
    except MessagingRepositoryError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.post(
    "/messaging/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Messaging"],
)
async def create_conversation(
    payload: ConversationCreateRequest,
    current_user: ExtendedAuthUser = Depends(get_current_user_extended),
    service: MessagingService = Depends(_get_messaging_service),
):
    _ensure_wedding_permission(current_user, payload.wedding_id)

    if not payload.participants:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="At least one participant is required")

    participant_ids: Set[str] = {participant.user_id for participant in payload.participants}
    if len(participant_ids) != len(payload.participants):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Duplicate participants are not allowed")

    # Ensure the creator is part of the conversation
    creator_id = _resolve_user_id(current_user)
    if all(participant.user_id != creator_id for participant in payload.participants):
        payload.participants.append(
            ConversationParticipant(
                user_id=creator_id,
                role=_resolve_participant_role(current_user),
            )
        )

    return await service.create_conversation(payload, created_by=creator_id)


@router.get(
    "/messaging/conversations/{conversation_id}",
    response_model=ConversationResponse,
    tags=["Messaging"],
)
async def get_conversation(
    conversation_id: str,
    current_user: ExtendedAuthUser = Depends(get_current_user_extended),
    service: MessagingService = Depends(_get_messaging_service),
):
    conversation = await service.get_conversation(conversation_id)
    _ensure_wedding_permission(current_user, conversation.wedding_id)
    return conversation


@router.get(
    "/messaging/conversations",
    response_model=ConversationListResponse,
    tags=["Messaging"],
)
async def list_conversations(
    wedding_id: Optional[str] = None,
    participant_id: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: Optional[str] = None,
    current_user: ExtendedAuthUser = Depends(get_current_user_extended),
    service: MessagingService = Depends(_get_messaging_service),
):
    if wedding_id:
        _ensure_wedding_permission(current_user, wedding_id)

    resolved_user_id = _resolve_user_id(current_user)

    if participant_id and participant_id != resolved_user_id and not current_user.is_root_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Participant access denied")

    resolved_participant = participant_id
    if not participant_id and not current_user.is_root_admin:
        resolved_participant = resolved_user_id

    return await service.list_conversations(
        wedding_id=wedding_id,
        participant_id=resolved_participant,
        limit=limit,
        cursor=cursor,
    )


@router.post(
    "/messaging/conversations/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Messaging"],
)
async def send_message(
    conversation_id: str,
    payload: MessageCreateRequest,
    current_user: ExtendedAuthUser = Depends(get_current_user_extended),
    service: MessagingService = Depends(_get_messaging_service),
):
    conversation = await service.get_conversation(conversation_id)
    _ensure_wedding_permission(current_user, conversation.wedding_id)

    creator_id = _resolve_user_id(current_user)
    if payload.sender_id != creator_id and not current_user.is_root_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sender mismatch")

    expected_role = _resolve_participant_role(current_user)
    if payload.sender_role != expected_role and not current_user.is_root_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sender role mismatch")

    return await service.send_message(conversation_id, payload)


@router.get(
    "/messaging/conversations/{conversation_id}/messages",
    response_model=MessageListResponse,
    tags=["Messaging"],
)
async def list_messages(
    conversation_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: Optional[str] = None,
    current_user: ExtendedAuthUser = Depends(get_current_user_extended),
    service: MessagingService = Depends(_get_messaging_service),
):
    conversation = await service.get_conversation(conversation_id)
    _ensure_wedding_permission(current_user, conversation.wedding_id)

    if not current_user.is_root_admin:
        requester_id = _resolve_user_id(current_user)
        if all(participant.user_id != requester_id for participant in conversation.participants):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a conversation participant")

    return await service.list_messages(conversation_id, limit=limit, cursor=cursor)
