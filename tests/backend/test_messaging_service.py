from datetime import datetime, timezone
import asyncio
from pathlib import Path
from unittest.mock import MagicMock
import os
import sys
import types

import pytest
from fastapi import HTTPException

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017/test")

google_module = types.ModuleType("google")
cloud_module = types.ModuleType("google.cloud")
firestore_module = types.ModuleType("google.cloud.firestore")
firestore_module.Client = object

sys.modules.setdefault("google", google_module)
sys.modules.setdefault("google.cloud", cloud_module)
sys.modules.setdefault("google.cloud.firestore", firestore_module)
cloud_module.firestore = firestore_module

pydantic_settings_module = types.ModuleType("pydantic_settings")


class _BaseSettings:
    model_config: dict = {}

    def __init__(self, **kwargs):  # pragma: no cover - trivial stub initializer
        for key, value in kwargs.items():
            setattr(self, key, value)


pydantic_settings_module.BaseSettings = _BaseSettings
sys.modules.setdefault("pydantic_settings", pydantic_settings_module)

firebase_admin_module = types.ModuleType("firebase_admin")
firebase_admin_module.initialize_app = MagicMock(return_value=MagicMock())
credentials_module = types.ModuleType("firebase_admin.credentials")
credentials_module.Certificate = MagicMock(side_effect=lambda data: data)
firestore_admin_module = types.ModuleType("firebase_admin.firestore")
firestore_admin_module.client = MagicMock()
app_module = types.ModuleType("firebase_admin.app")

class _DummyApp:  # pragma: no cover - simple stand-in for typing expectations
    pass

app_module.App = _DummyApp
auth_module = types.ModuleType("firebase_admin.auth")
auth_module.create_custom_token = MagicMock(return_value=b"token")

sys.modules.setdefault("firebase_admin", firebase_admin_module)
firebase_admin_module.App = _DummyApp
sys.modules.setdefault("firebase_admin.credentials", credentials_module)
sys.modules.setdefault("firebase_admin.firestore", firestore_admin_module)
sys.modules.setdefault("firebase_admin.app", app_module)
sys.modules.setdefault("firebase_admin.auth", auth_module)

from pydantic import ValidationError

from app.models.messaging import (
    ConversationChannel,
    ConversationCreateRequest,
    ConversationListResponse,
    ConversationParticipant,
    ConversationResponse,
    MessageCreateRequest,
    MessageAttachment,
    MessageListResponse,
    MessageResponse,
    ParticipantRole,
    SendMessageRequest,
)
from app.services.messaging import MessagingRepositoryError, MessagingService


def test_list_conversations_returns_paginated_response():
    repository = MagicMock()
    participant = ConversationParticipant(user_id="user-1", role=ParticipantRole.PLANNER)
    conversation = ConversationResponse(
        conversation_id="convo-1",
        wedding_id="wed-1",
        channel=ConversationChannel.CHAT,
        subject=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        last_message_at=None,
        last_message_summary=None,
        metadata={},
        participants=[participant],
    )
    repository.list_conversations.return_value = ([conversation], "cursor-1")

    service = MessagingService(repository=repository)

    result = asyncio.run(
        service.list_conversations(wedding_id="wed-1", participant_id="user-1", limit=10)
    )

    assert isinstance(result, ConversationListResponse)
    assert result.items == [conversation]
    assert result.next_cursor == "cursor-1"
    repository.list_conversations.assert_called_once_with(
        wedding_id="wed-1",
        participant_id="user-1",
        limit=10,
        cursor=None,
    )


def test_list_conversations_raises_on_repository_error():
    repository = MagicMock()
    repository.list_conversations.side_effect = MessagingRepositoryError("boom")

    service = MessagingService(repository=repository)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.list_conversations(wedding_id="wed-1", participant_id="user-1"))

    assert exc.value.status_code == 502


def test_list_messages_returns_paginated_response():
    repository = MagicMock()
    message = MessageResponse(
        message_id="msg-1",
        conversation_id="convo-1",
        sender_id="user-1",
        sender_role=ParticipantRole.PLANNER,
        body="Hello",
        created_at=datetime.now(timezone.utc),
        attachments=[MessageAttachment(type="form", reference_id="form-1")],
        linked_resource=None,
        delivery_status="sent",
    )
    repository.list_messages.return_value = ([message], None)

    service = MessagingService(repository=repository)

    result = asyncio.run(service.list_messages("convo-1", limit=25))

    assert isinstance(result, MessageListResponse)
    assert result.messages == [message]
    assert result.next_cursor is None
    repository.list_messages.assert_called_once_with("convo-1", limit=25, cursor=None)


def test_list_messages_raises_on_repository_error():
    repository = MagicMock()
    repository.list_messages.side_effect = MessagingRepositoryError("failure")

    service = MessagingService(repository=repository)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.list_messages("convo-1"))

    assert exc.value.status_code == 502


def test_create_conversation_invokes_repository():
    repository = MagicMock()
    participant = ConversationParticipant(user_id="user-1", role=ParticipantRole.PLANNER)
    payload = ConversationCreateRequest(
        wedding_id="wed-1",
        participants=[participant],
        channel=ConversationChannel.CHAT,
    )
    conversation = ConversationResponse(
        conversation_id="convo-1",
        wedding_id="wed-1",
        channel=ConversationChannel.CHAT,
        subject="Subject",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        last_message_at=None,
        last_message_summary=None,
        metadata={},
        participants=[participant],
    )
    repository.create_conversation.return_value = conversation

    service = MessagingService(repository=repository)

    result = asyncio.run(service.create_conversation(payload, created_by="user-1"))

    assert result == conversation
    repository.create_conversation.assert_called_once_with(payload, created_by="user-1")


def test_create_conversation_raises_on_repository_error():
    repository = MagicMock()
    participant = ConversationParticipant(user_id="user-1", role=ParticipantRole.PLANNER)
    payload = ConversationCreateRequest(
        wedding_id="wed-1",
        participants=[participant],
        channel=ConversationChannel.CHAT,
    )
    repository.create_conversation.side_effect = MessagingRepositoryError("fail")

    service = MessagingService(repository=repository)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.create_conversation(payload, created_by="user-1"))

    assert exc.value.status_code == 502


def test_send_message_request_strips_whitespace() -> None:
    payload = SendMessageRequest(body="  Hello world  ")

    assert payload.body == "Hello world"


def test_send_message_request_rejects_blank_body() -> None:
    with pytest.raises(ValidationError):
        SendMessageRequest(body="   \n  ")


def test_message_create_request_enforces_bounds() -> None:
    payload = MessageCreateRequest(
        sender_id="user-1",
        body="  trimmed body  ",
    )

    assert payload.body == "trimmed body"


def test_message_create_request_rejects_long_body() -> None:
    with pytest.raises(ValidationError):
        MessageCreateRequest(sender_id="user-1", body="x" * 6000)
