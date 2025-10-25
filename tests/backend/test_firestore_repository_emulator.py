"""Integration tests against the Firestore emulator for messaging repository."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
import pytest
from google.auth.credentials import AnonymousCredentials
from google.cloud.firestore import Client as FirestoreClient

from app.models.messaging import (
    ConversationChannel,
    ConversationCreateRequest,
    ConversationParticipant,
    MessageCreateRequest,
    ParticipantRole,
)
from app.services.messaging.repository import FirestoreMessagingRepository

pytestmark = pytest.mark.skipif(
    os.getenv("FIRESTORE_EMULATOR_HOST") is None,
    reason="Firestore emulator host not configured",
)


@pytest.fixture(scope="module")
def firestore_client() -> FirestoreClient:
    project_id = os.getenv("FIRESTORE_PROJECT_ID", "demo-wedding-app")
    return FirestoreClient(project=project_id, credentials=AnonymousCredentials())


@pytest.fixture(autouse=True)
def clean_firestore(firestore_client: FirestoreClient):
    yield
    for collection in ("conversations",):
        docs = list(firestore_client.collection(collection).stream())
        for doc in docs:
            # Delete participant and message subcollections before removing parent.
            participants = firestore_client.collection(f"{collection}/{doc.id}/participants")
            for participant in list(participants.stream()):
                participant.reference.delete()

            messages = firestore_client.collection(f"{collection}/{doc.id}/messages")
            for message in list(messages.stream()):
                message.reference.delete()

            doc.reference.delete()


def test_conversation_round_trip(firestore_client: FirestoreClient) -> None:
    repository = FirestoreMessagingRepository(client=firestore_client)

    participant = ConversationParticipant(user_id="planner@example.com", role=ParticipantRole.PLANNER)
    payload = ConversationCreateRequest(
        wedding_id="wed-integration",
        channel=ConversationChannel.CHAT,
        subject="Planning",
        participants=[participant],
    )

    conversation = repository.create_conversation(payload, created_by="planner@example.com")

    fetched = repository.get_conversation(conversation.conversation_id)
    assert fetched is not None
    assert fetched.wedding_id == "wed-integration"
    assert fetched.participants[0].user_id == "planner@example.com"


def test_append_message_persists_to_emulator(firestore_client: FirestoreClient) -> None:
    repository = FirestoreMessagingRepository(client=firestore_client)

    participant = ConversationParticipant(user_id="vendor@example.com", role=ParticipantRole.VENDOR)
    conversation = repository.create_conversation(
        ConversationCreateRequest(
            wedding_id="wed-integration",
            channel=ConversationChannel.CHAT,
            participants=[participant],
        ),
        created_by="vendor@example.com",
    )

    message = repository.append_message(
        conversation.conversation_id,
        MessageCreateRequest(
            sender_id="vendor@example.com",
            sender_role=ParticipantRole.VENDOR,
            body="Hello from emulator",
        ),
    )

    assert message.conversation_id == conversation.conversation_id
    assert message.body == "Hello from emulator"

    messages, _ = repository.list_messages(conversation.conversation_id, limit=10)
    assert len(messages) == 1
    assert messages[0].sender_id == "vendor@example.com"


def test_list_conversations_filters_by_participant(firestore_client: FirestoreClient) -> None:
    repository = FirestoreMessagingRepository(client=firestore_client)

    participants = [
        ConversationParticipant(user_id="planner@example.com", role=ParticipantRole.PLANNER),
        ConversationParticipant(user_id="assistant@example.com", role=ParticipantRole.WEDDING_PARTY),
    ]

    repository.create_conversation(
        ConversationCreateRequest(
            wedding_id="wed-team",
            channel=ConversationChannel.CHAT,
            participants=participants,
        ),
        created_by="planner@example.com",
    )

    repository.create_conversation(
        ConversationCreateRequest(
            wedding_id="wed-other",
            channel=ConversationChannel.CHAT,
            participants=[ConversationParticipant(user_id="someone@example.com", role=ParticipantRole.VENDOR)],
        ),
        created_by="someone@example.com",
    )

    conversations, _ = repository.list_conversations(wedding_id="wed-team", participant_id="planner@example.com", limit=5)

    assert len(conversations) == 1
    assert conversations[0].wedding_id == "wed-team"
    assert conversations[0].participants[0].user_id == "planner@example.com"


def test_acknowledge_read_updates_last_read_at(firestore_client: FirestoreClient) -> None:
    repository = FirestoreMessagingRepository(client=firestore_client)

    participant = ConversationParticipant(user_id="reader@example.com", role=ParticipantRole.PLANNER)
    conversation = repository.create_conversation(
        ConversationCreateRequest(
            wedding_id="wed-read",
            channel=ConversationChannel.CHAT,
            participants=[participant],
        ),
        created_by="reader@example.com",
    )

    first_timestamp = datetime.now(timezone.utc).replace(microsecond=0)
    updated_participant = repository.acknowledge_read(
        conversation.conversation_id,
        "reader@example.com",
        read_at=first_timestamp,
    )

    assert updated_participant.last_read_at == first_timestamp

    conversation_state = repository.get_conversation(conversation.conversation_id)
    assert conversation_state is not None
    assert conversation_state.participants[0].last_read_at == first_timestamp

    earlier = first_timestamp - timedelta(days=1)
    monotonic_participant = repository.acknowledge_read(
        conversation.conversation_id,
        "reader@example.com",
        read_at=earlier,
    )

    assert monotonic_participant.last_read_at == first_timestamp
