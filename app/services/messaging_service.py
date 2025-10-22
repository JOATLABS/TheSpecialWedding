from __future__ import annotations

from datetime import datetime
from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status

from app.core.database import mongo
from app.models.messaging import Conversation, Message, SendMessageRequest


class MessagingService:
    """Service layer responsible for messaging persistence and retrieval."""

    def __init__(self) -> None:
        self._conversation_collection = mongo.db["conversations"]
        self._message_collection = mongo.db["messages"]

    def _serialize_conversation(self, document: dict) -> Conversation:
        return Conversation(
            id=str(document["_id"]),
            wedding_id=document["wedding_id"],
            participants=document.get("participants", []),
            title=document.get("title"),
            created_at=document.get("created_at"),
        )

    def _serialize_message(self, document: dict) -> Message:
        return Message(
            id=str(document["_id"]),
            wedding_id=document["wedding_id"],
            conversation_id=document["conversation_id"],
            sender_id=document["sender_id"],
            body=document["body"],
            created_at=document.get("created_at", datetime.utcnow()),
        )

    def get_conversation(self, wedding_id: str, conversation_id: str) -> Conversation:
        """Fetch a single conversation by its identifiers."""

        try:
            object_id = ObjectId(conversation_id)
        except (InvalidId, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid conversation identifier provided.",
            )

        document: Optional[dict] = self._conversation_collection.find_one(
            {"_id": object_id, "wedding_id": wedding_id}
        )
        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
        return self._serialize_conversation(document)

    def send_message(
        self, wedding_id: str, conversation_id: str, sender_id: str, payload: SendMessageRequest
    ) -> Message:
        """Persist a new message within a conversation."""

        new_document = {
            "wedding_id": wedding_id,
            "conversation_id": conversation_id,
            "sender_id": sender_id,
            "body": payload.body,
            "created_at": datetime.utcnow(),
        }
        result = self._message_collection.insert_one(new_document)
        new_document["_id"] = result.inserted_id
        return self._serialize_message(new_document)
