"""Firestore repository for messaging artefacts."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple

from google.cloud.firestore import Client
from pydantic import ValidationError

from app.models.messaging import (
    ConversationCreateRequest,
    ConversationParticipant,
    ConversationResponse,
    ConversationChannel,
    MessageCreateRequest,
    MessageResponse,
    MessageAttachment,
    LinkedResource,
    ParticipantRole,
)
from app.services.firebase.client import FirebaseInitializationError, get_firestore_client

logger = logging.getLogger(__name__)


class MessagingRepositoryError(RuntimeError):
    """Base error for messaging repository issues."""

class FirestoreMessagingRepository:
    """Firestore persistence for messaging conversations and messages."""

    def __init__(self, client: Optional[Client] = None):
        try:
            self._client = client or get_firestore_client()
        except FirebaseInitializationError as exc:
            raise MessagingRepositoryError(str(exc)) from exc

    # ---- Conversation operations -------------------------------------------------

    def create_conversation(
        self,
        payload: ConversationCreateRequest,
        *,
        created_by: str,
    ) -> ConversationResponse:
        """Create a conversation and persist participants."""
        now = datetime.now(timezone.utc)
        doc_ref = self._client.collection("conversations").document()
        participant_ids = sorted({participant.user_id for participant in payload.participants})
        conversation_doc = {
            "weddingId": payload.wedding_id,
            "channel": payload.channel.value,
            "subject": payload.subject,
            "createdAt": now,
            "updatedAt": now,
            "createdBy": created_by,
            "metadata": payload.metadata or {},
            "participantCount": len(participant_ids),
            "participantIds": participant_ids,
        }

        batch = self._client.batch()
        batch.set(doc_ref, conversation_doc)

        participants_path = doc_ref.collection("participants")
        for participant in payload.participants:
            participant_doc = self._participant_to_document(participant)
            participant_ref = participants_path.document(participant.user_id)
            batch.set(participant_ref, participant_doc)

        try:
            batch.commit()
        except Exception as exc:  # pragma: no cover - depends on Firestore runtime
            logger.error("Failed to create conversation in Firestore: %s", exc)
            raise MessagingRepositoryError("Failed to create conversation") from exc

        return ConversationResponse(
            conversation_id=doc_ref.id,
            wedding_id=payload.wedding_id,
            channel=payload.channel,
            subject=payload.subject,
            created_at=now,
            updated_at=now,
            last_message_at=None,
            last_message_summary=None,
            metadata=payload.metadata or {},
            participants=list(payload.participants),
        )

    def list_conversations(
        self,
        *,
        wedding_id: Optional[str] = None,
        participant_id: Optional[str] = None,
        limit: int = 50,
        cursor: Optional[str] = None,
    ) -> Tuple[List[ConversationResponse], Optional[str]]:
        """List conversations filtered by wedding or participant."""
        query = self._client.collection("conversations")

        if wedding_id:
            query = query.where("weddingId", "==", wedding_id)

        if participant_id:
            query = query.where("participantIds", "array_contains", participant_id)

        query = query.order_by("updatedAt", direction="DESCENDING").order_by("__name__").limit(limit)

        if cursor:
            cursor_snapshot = self._client.collection("conversations").document(cursor).get()
            if cursor_snapshot.exists:
                query = query.start_after(cursor_snapshot)
            else:
                logger.warning("Conversation cursor %s does not exist; returning first page", cursor)

        try:
            snapshots = list(query.stream())
        except Exception as exc:  # pragma: no cover - Firestore client handles specific errors
            logger.error("Failed to list conversations: %s", exc)
            raise MessagingRepositoryError("Failed to list conversations") from exc

        conversations = [self._snapshot_to_conversation(snapshot) for snapshot in snapshots]
        next_cursor = snapshots[-1].id if len(snapshots) == limit else None

        return conversations, next_cursor

    def append_message(
        self,
        conversation_id: str,
        payload: MessageCreateRequest,
    ) -> MessageResponse:
        """Append a message to an existing conversation."""
        now = datetime.now(timezone.utc)
        convo_ref = self._client.collection("conversations").document(conversation_id)
        message_ref = convo_ref.collection("messages").document()

        message_doc = self._message_to_document(payload, now)

        batch = self._client.batch()
        batch.set(message_ref, message_doc)
        batch.update(convo_ref, {
            "updatedAt": now,
            "lastMessageSummary": payload.body[:280],
            "lastMessageAt": now,
        })

        try:
            batch.commit()
        except Exception as exc:  # pragma: no cover
            logger.error("Failed to append message to conversation %s: %s", conversation_id, exc)
            raise MessagingRepositoryError("Failed to append message") from exc

        return MessageResponse(
            message_id=message_ref.id,
            conversation_id=conversation_id,
            sender_id=payload.sender_id,
            sender_role=payload.sender_role,
            body=payload.body,
            created_at=now,
            attachments=payload.attachments,
            linked_resource=payload.linked_resource,
            delivery_status=payload.delivery_status,
        )

    def get_conversation(self, conversation_id: str) -> Optional[ConversationResponse]:
        """Fetch a conversation and participants."""
        doc_ref = self._client.collection("conversations").document(conversation_id)
        snapshot = doc_ref.get()
        if not snapshot.exists:
            return None

        return self._snapshot_to_conversation(snapshot)

    def list_messages(
        self,
        conversation_id: str,
        *,
        limit: int = 50,
        cursor: Optional[str] = None,
    ) -> Tuple[List[MessageResponse], Optional[str]]:
        """Return paginated messages for a conversation."""
        convo_ref = self._client.collection("conversations").document(conversation_id)

        query = (
            convo_ref.collection("messages")
            .order_by("createdAt")
            .order_by("__name__")
            .limit(limit)
        )

        if cursor:
            cursor_snapshot = convo_ref.collection("messages").document(cursor).get()
            if cursor_snapshot.exists:
                query = query.start_after(cursor_snapshot)
            else:
                logger.warning("Message cursor %s does not exist for conversation %s", cursor, conversation_id)

        try:
            snapshots = list(query.stream())
        except Exception as exc:  # pragma: no cover
            logger.error("Failed to list messages for %s: %s", conversation_id, exc)
            raise MessagingRepositoryError("Failed to list messages") from exc

        messages = [self._snapshot_to_message(conversation_id, snapshot) for snapshot in snapshots]
        next_cursor = snapshots[-1].id if len(snapshots) == limit else None
        return messages, next_cursor

    # ---- Internal helpers -------------------------------------------------------

    def _participant_to_document(self, participant: ConversationParticipant) -> Dict:
        return {
            "userId": participant.user_id,
            "role": participant.role.value,
            "joinedAt": participant.joined_at,
            "mute": participant.mute,
            "lastReadAt": participant.last_read_at,
        }

    def _message_to_document(self, payload: MessageCreateRequest, timestamp: datetime) -> Dict:
        document: Dict[str, object] = {
            "senderId": payload.sender_id,
            "senderRole": payload.sender_role.value,
            "body": payload.body,
            "createdAt": timestamp,
        }

        if payload.attachments:
            document["attachments"] = [
                attachment.model_dump(mode="json", exclude_none=True)
                for attachment in payload.attachments
            ]

        if payload.linked_resource:
            document["linkedResource"] = payload.linked_resource.model_dump(mode="json", exclude_none=True)

        if payload.delivery_status:
            document["deliveryStatus"] = payload.delivery_status

        return document

    def _iter_participants(self, doc_ref) -> Iterable[ConversationParticipant]:
        snapshots = doc_ref.collection("participants").order_by("joinedAt").stream()
        participants: list[ConversationParticipant] = []
        for item in snapshots:
            data = item.to_dict() or {}
            role_value = data.get("role", ParticipantRole.PLANNER.value)
            try:
                role = ParticipantRole(role_value)
            except ValueError:
                logger.warning(
                    "Unknown participant role '%s' in conversation %s; defaulting to planner",
                    role_value,
                    doc_ref.id,
                )
                role = ParticipantRole.PLANNER

            joined_at = data.get("joinedAt") or datetime.now(timezone.utc)
            last_read_at = data.get("lastReadAt")

            participants.append(
                ConversationParticipant(
                    user_id=data.get("userId") or data.get("user_id") or item.id,
                    role=role,
                    joined_at=joined_at,
                    mute=data.get("mute", False),
                    last_read_at=last_read_at,
                )
            )
        return participants

    def _snapshot_to_conversation(self, snapshot) -> ConversationResponse:
        data = snapshot.to_dict() or {}
        doc_ref = snapshot.reference

        channel_value = data.get("channel", ConversationChannel.CHAT.value)
        try:
            channel = ConversationChannel(channel_value)
        except ValueError:
            logger.warning(
                "Unknown channel '%s' for conversation %s; defaulting to chat",
                channel_value,
                snapshot.id,
            )
            channel = ConversationChannel.CHAT

        created_at = data.get("createdAt", datetime.now(timezone.utc))
        updated_at = data.get("updatedAt", created_at)
        last_message_at = data.get("lastMessageAt")
        last_message_summary = data.get("lastMessageSummary")

        participants = list(self._iter_participants(doc_ref))

        return ConversationResponse(
            conversation_id=snapshot.id,
            wedding_id=data.get("weddingId"),
            channel=channel,
            subject=data.get("subject"),
            created_at=created_at,
            updated_at=updated_at,
            last_message_at=last_message_at,
            last_message_summary=last_message_summary,
            metadata=data.get("metadata", {}),
            participants=participants,
        )

    def _snapshot_to_message(self, conversation_id: str, snapshot) -> MessageResponse:
        data = snapshot.to_dict() or {}

        attachments: List[MessageAttachment] = []
        for item in data.get("attachments", []) or []:
            try:
                attachments.append(MessageAttachment.model_validate(item))
            except ValidationError as exc:
                logger.warning(
                    "Skipping invalid attachment on message %s in conversation %s: %s",
                    snapshot.id,
                    conversation_id,
                    exc,
                )

        linked_resource = None
        if data.get("linkedResource"):
            try:
                linked_resource = LinkedResource.model_validate(data["linkedResource"])
            except ValidationError as exc:
                logger.warning(
                    "Invalid linked resource on message %s in conversation %s: %s",
                    snapshot.id,
                    conversation_id,
                    exc,
                )

        role_value = data.get("senderRole", ParticipantRole.PLANNER.value)
        try:
            sender_role = ParticipantRole(role_value)
        except ValueError:
            logger.warning(
                "Unknown sender role '%s' for message %s; defaulting to planner",
                role_value,
                snapshot.id,
            )
            sender_role = ParticipantRole.PLANNER

        created_at = data.get("createdAt", datetime.now(timezone.utc))

        return MessageResponse(
            message_id=snapshot.id,
            conversation_id=conversation_id,
            sender_id=data.get("senderId"),
            sender_role=sender_role,
            body=data.get("body", ""),
            created_at=created_at,
            attachments=attachments,
            linked_resource=linked_resource,
            delivery_status=data.get("deliveryStatus"),
        )
