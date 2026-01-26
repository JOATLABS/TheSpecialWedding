"""MongoDB repository for messaging - replaces Firestore implementation."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId

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
from app.core.database import mongo

logger = logging.getLogger(__name__)


class MessagingRepositoryError(RuntimeError):
    """Base error for messaging repository issues."""


class MongoMessagingRepository:
    """MongoDB persistence for messaging conversations and messages.

    This is a drop-in replacement for FirestoreMessagingRepository,
    providing the same interface but using MongoDB for storage.
    """

    def __init__(self):
        self._conversations = mongo.get_conversations_collection()
        self._messages = mongo.get_messages_collection()

    # ---- Conversation operations -------------------------------------------------

    async def create_conversation(
        self,
        payload: ConversationCreateRequest,
        *,
        created_by: str,
    ) -> ConversationResponse:
        """Create a conversation with embedded participants."""
        now = datetime.now(timezone.utc)
        participant_ids = sorted({p.user_id for p in payload.participants})

        participants_docs = [
            self._participant_to_document(p) for p in payload.participants
        ]

        conversation_doc = {
            "wedding_id": payload.wedding_id,
            "channel": payload.channel.value,
            "subject": payload.subject,
            "created_at": now,
            "updated_at": now,
            "created_by": created_by,
            "metadata": payload.metadata or {},
            "participant_count": len(participant_ids),
            "participant_ids": participant_ids,
            "participants": participants_docs,
            "last_message_at": None,
            "last_message_summary": None,
        }

        try:
            result = await self._conversations.insert_one(conversation_doc)
            conversation_id = str(result.inserted_id)
        except Exception as exc:
            logger.error("Failed to create conversation in MongoDB: %s", exc)
            raise MessagingRepositoryError("Failed to create conversation") from exc

        return ConversationResponse(
            conversation_id=conversation_id,
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

    async def list_conversations(
        self,
        *,
        wedding_id: Optional[str] = None,
        participant_id: Optional[str] = None,
        limit: int = 50,
        cursor: Optional[str] = None,
    ) -> Tuple[List[ConversationResponse], Optional[str]]:
        """List conversations filtered by wedding or participant."""
        query: Dict[str, Any] = {}

        if wedding_id:
            query["wedding_id"] = wedding_id

        if participant_id:
            query["participant_ids"] = participant_id

        # Cursor-based pagination using _id
        if cursor:
            try:
                query["_id"] = {"$lt": ObjectId(cursor)}
            except Exception:
                logger.warning("Invalid cursor %s; returning first page", cursor)

        try:
            cursor_result = self._conversations.find(query).sort([
                ("updated_at", -1),
                ("_id", -1)
            ]).limit(limit)

            docs = await cursor_result.to_list(length=limit)
        except Exception as exc:
            logger.error("Failed to list conversations: %s", exc)
            raise MessagingRepositoryError("Failed to list conversations") from exc

        conversations = [self._document_to_conversation(doc) for doc in docs]
        next_cursor = str(docs[-1]["_id"]) if len(docs) == limit else None

        return conversations, next_cursor

    async def append_message(
        self,
        conversation_id: str,
        payload: MessageCreateRequest,
    ) -> MessageResponse:
        """Append a message to an existing conversation."""
        now = datetime.now(timezone.utc)

        message_doc = {
            "conversation_id": conversation_id,
            "sender_id": payload.sender_id,
            "sender_role": payload.sender_role.value,
            "body": payload.body,
            "created_at": now,
            "attachments": [
                att.model_dump(mode="json", exclude_none=True)
                for att in (payload.attachments or [])
            ],
            "linked_resource": (
                payload.linked_resource.model_dump(mode="json", exclude_none=True)
                if payload.linked_resource else None
            ),
            "delivery_status": payload.delivery_status,
        }

        try:
            # Insert message
            result = await self._messages.insert_one(message_doc)
            message_id = str(result.inserted_id)

            # Update conversation metadata
            await self._conversations.update_one(
                {"_id": ObjectId(conversation_id)},
                {
                    "$set": {
                        "updated_at": now,
                        "last_message_at": now,
                        "last_message_summary": payload.body[:280],
                    }
                }
            )
        except Exception as exc:
            logger.error("Failed to append message to conversation %s: %s", conversation_id, exc)
            raise MessagingRepositoryError("Failed to append message") from exc

        return MessageResponse(
            message_id=message_id,
            conversation_id=conversation_id,
            sender_id=payload.sender_id,
            sender_role=payload.sender_role,
            body=payload.body,
            created_at=now,
            attachments=list(payload.attachments or []),
            linked_resource=payload.linked_resource,
            delivery_status=payload.delivery_status,
        )

    async def get_conversation(self, conversation_id: str) -> Optional[ConversationResponse]:
        """Fetch a conversation by ID."""
        try:
            doc = await self._conversations.find_one({"_id": ObjectId(conversation_id)})
        except Exception as exc:
            logger.error("Failed to get conversation %s: %s", conversation_id, exc)
            raise MessagingRepositoryError("Failed to get conversation") from exc

        if not doc:
            return None

        return self._document_to_conversation(doc)

    async def list_messages(
        self,
        conversation_id: str,
        *,
        limit: int = 50,
        cursor: Optional[str] = None,
    ) -> Tuple[List[MessageResponse], Optional[str]]:
        """Return paginated messages for a conversation."""
        query: Dict[str, Any] = {"conversation_id": conversation_id}

        if cursor:
            try:
                query["_id"] = {"$gt": ObjectId(cursor)}
            except Exception:
                logger.warning("Invalid message cursor %s for conversation %s", cursor, conversation_id)

        try:
            cursor_result = self._messages.find(query).sort([
                ("created_at", 1),
                ("_id", 1)
            ]).limit(limit)

            docs = await cursor_result.to_list(length=limit)
        except Exception as exc:
            logger.error("Failed to list messages for %s: %s", conversation_id, exc)
            raise MessagingRepositoryError("Failed to list messages") from exc

        messages = [self._document_to_message(doc) for doc in docs]
        next_cursor = str(docs[-1]["_id"]) if len(docs) == limit else None

        return messages, next_cursor

    async def acknowledge_read(
        self,
        conversation_id: str,
        participant_id: str,
        *,
        read_at: Optional[datetime] = None,
    ) -> ConversationParticipant:
        """Update the participant read receipt for a conversation."""
        timestamp = read_at or datetime.now(timezone.utc)

        try:
            # Find the conversation and participant
            doc = await self._conversations.find_one({"_id": ObjectId(conversation_id)})
        except Exception as exc:
            logger.error(
                "Failed to load conversation %s for read receipt: %s",
                conversation_id,
                exc,
            )
            raise MessagingRepositoryError("Failed to load conversation") from exc

        if not doc:
            raise MessagingRepositoryError("Conversation not found")

        # Find participant in embedded array
        participants = doc.get("participants", [])
        participant_data = None
        participant_index = -1

        for i, p in enumerate(participants):
            if p.get("user_id") == participant_id:
                participant_data = p
                participant_index = i
                break

        if participant_data is None:
            raise MessagingRepositoryError("Participant is not part of the conversation")

        # Check existing read time and keep the later one
        existing_last_read = participant_data.get("last_read_at")
        if isinstance(existing_last_read, datetime):
            if existing_last_read.tzinfo is None:
                existing_last_read = existing_last_read.replace(tzinfo=timezone.utc)
            timestamp = max(timestamp, existing_last_read)

        try:
            # Update the specific participant in the array
            await self._conversations.update_one(
                {"_id": ObjectId(conversation_id)},
                {"$set": {f"participants.{participant_index}.last_read_at": timestamp}}
            )
        except Exception as exc:
            logger.error(
                "Failed to update read receipt for %s in conversation %s: %s",
                participant_id,
                conversation_id,
                exc,
            )
            raise MessagingRepositoryError("Failed to update read receipt") from exc

        return self._document_to_participant({**participant_data, "last_read_at": timestamp})

    # ---- Internal helpers -------------------------------------------------------

    def _document_to_participant(self, data: Dict[str, Any]) -> ConversationParticipant:
        """Convert a MongoDB document to a ConversationParticipant."""
        role_value = data.get("role", ParticipantRole.PLANNER.value)
        try:
            role = ParticipantRole(role_value)
        except ValueError:
            logger.warning("Unknown participant role '%s'; defaulting to planner", role_value)
            role = ParticipantRole.PLANNER

        joined_at = data.get("joined_at") or datetime.now(timezone.utc)
        if isinstance(joined_at, datetime) and joined_at.tzinfo is None:
            joined_at = joined_at.replace(tzinfo=timezone.utc)

        last_read_at = data.get("last_read_at")
        if isinstance(last_read_at, datetime) and last_read_at.tzinfo is None:
            last_read_at = last_read_at.replace(tzinfo=timezone.utc)

        return ConversationParticipant(
            user_id=data.get("user_id", ""),
            role=role,
            joined_at=joined_at,
            mute=data.get("mute", False),
            last_read_at=last_read_at,
        )

    def _participant_to_document(self, participant: ConversationParticipant) -> Dict[str, Any]:
        """Convert a ConversationParticipant to a MongoDB document."""
        return {
            "user_id": participant.user_id,
            "role": participant.role.value,
            "joined_at": participant.joined_at,
            "mute": participant.mute,
            "last_read_at": participant.last_read_at,
        }

    def _document_to_conversation(self, doc: Dict[str, Any]) -> ConversationResponse:
        """Convert a MongoDB document to a ConversationResponse."""
        channel_value = doc.get("channel", ConversationChannel.CHAT.value)
        try:
            channel = ConversationChannel(channel_value)
        except ValueError:
            logger.warning("Unknown channel '%s'; defaulting to chat", channel_value)
            channel = ConversationChannel.CHAT

        created_at = doc.get("created_at", datetime.now(timezone.utc))
        updated_at = doc.get("updated_at", created_at)

        if isinstance(created_at, datetime) and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if isinstance(updated_at, datetime) and updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)

        last_message_at = doc.get("last_message_at")
        if isinstance(last_message_at, datetime) and last_message_at.tzinfo is None:
            last_message_at = last_message_at.replace(tzinfo=timezone.utc)

        participants = [
            self._document_to_participant(p)
            for p in doc.get("participants", [])
        ]

        return ConversationResponse(
            conversation_id=str(doc["_id"]),
            wedding_id=doc.get("wedding_id"),
            channel=channel,
            subject=doc.get("subject"),
            created_at=created_at,
            updated_at=updated_at,
            last_message_at=last_message_at,
            last_message_summary=doc.get("last_message_summary"),
            metadata=doc.get("metadata", {}),
            participants=participants,
        )

    def _document_to_message(self, doc: Dict[str, Any]) -> MessageResponse:
        """Convert a MongoDB document to a MessageResponse."""
        attachments: List[MessageAttachment] = []
        for item in doc.get("attachments", []) or []:
            try:
                attachments.append(MessageAttachment.model_validate(item))
            except ValidationError as exc:
                logger.warning("Skipping invalid attachment: %s", exc)

        linked_resource = None
        if doc.get("linked_resource"):
            try:
                linked_resource = LinkedResource.model_validate(doc["linked_resource"])
            except ValidationError as exc:
                logger.warning("Invalid linked resource: %s", exc)

        role_value = doc.get("sender_role", ParticipantRole.PLANNER.value)
        try:
            sender_role = ParticipantRole(role_value)
        except ValueError:
            logger.warning("Unknown sender role '%s'; defaulting to planner", role_value)
            sender_role = ParticipantRole.PLANNER

        created_at = doc.get("created_at", datetime.now(timezone.utc))
        if isinstance(created_at, datetime) and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        return MessageResponse(
            message_id=str(doc["_id"]),
            conversation_id=doc.get("conversation_id", ""),
            sender_id=doc.get("sender_id"),
            sender_role=sender_role,
            body=doc.get("body", ""),
            created_at=created_at,
            attachments=attachments,
            linked_resource=linked_resource,
            delivery_status=doc.get("delivery_status"),
        )
