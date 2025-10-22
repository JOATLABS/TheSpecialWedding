from datetime import datetime
from typing import Any, Dict, Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException

from app.core.database import mongo


class MessagingService:
    """Service for managing conversations and messages."""

    def __init__(self) -> None:
        self.conversations = mongo.db["conversations"]
        self.messages = mongo.db["messages"]

    def _normalize_conversation_id(self, conversation_id: Any) -> ObjectId:
        """Ensure the conversation identifier is stored as a BSON ObjectId."""
        if isinstance(conversation_id, ObjectId):
            return conversation_id
        if not conversation_id:
            raise HTTPException(status_code=400, detail="conversation_id is required")
        try:
            return ObjectId(conversation_id)
        except (InvalidId, TypeError):
            raise HTTPException(status_code=400, detail="Invalid conversation_id")

    def get_conversation(self, conversation_id: Any) -> Dict[str, Any]:
        normalized_id = self._normalize_conversation_id(conversation_id)
        conversation = self.conversations.find_one({"_id": normalized_id})
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        conversation["id"] = str(conversation["_id"])
        conversation.pop("_id", None)
        return conversation

    def add_message(
        self,
        *,
        conversation_id: Any,
        body: str,
        sender: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Persist a message in a conversation and return the saved document."""
        normalized_conversation_id = self._normalize_conversation_id(conversation_id)
        message_doc: Dict[str, Any] = {
            "conversation_id": normalized_conversation_id,
            "body": body,
            "sender": sender,
            "metadata": metadata or {},
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        result = self.messages.insert_one(message_doc)

        message_doc["id"] = str(result.inserted_id)
        message_doc["conversation_id"] = str(normalized_conversation_id)
        return message_doc
