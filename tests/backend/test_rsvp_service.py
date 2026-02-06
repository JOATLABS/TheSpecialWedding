from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import mongomock
import pytest
from bson import ObjectId
from fastapi import BackgroundTasks

# Mock the mongo module before importing RSVPService
# This patch ensures that when RSVPService imports mongo, it gets a mock
with patch("app.core.database.mongo") as mock_mongo:
    from app.models.rsvp import PlusOneInputModel, RSVPModel
    from app.services.rsvp_service import RSVPService


class AsyncMockCollection:
    def __init__(self, collection):
        self.collection = collection

    async def find_one(self, *args, **kwargs):
        return self.collection.find_one(*args, **kwargs)

    async def update_one(self, *args, **kwargs):
        return self.collection.update_one(*args, **kwargs)

    async def insert_many(self, *args, **kwargs):
        return self.collection.insert_many(*args, **kwargs)

    async def count_documents(self, *args, **kwargs):
        return self.collection.count_documents(*args, **kwargs)


@pytest.fixture
def mock_mongo_db():
    return mongomock.MongoClient().db


@pytest.fixture
def rsvp_service(mock_mongo_db):
    # We need to re-patch here because the fixture setup happens after imports
    with patch("app.services.rsvp_service.mongo") as mock_mongo_ref:

        # Create async wrappers for collections
        guests_col = AsyncMockCollection(mock_mongo_db.guests)
        rsvps_col = AsyncMockCollection(mock_mongo_db.rsvps)
        plus_ones_col = AsyncMockCollection(mock_mongo_db.plus_ones)
        weddings_col = AsyncMockCollection(mock_mongo_db.weddings)

        # Mock get_guest_collection
        mock_mongo_ref.get_guest_collection.return_value = guests_col

        # Mock db access via __getitem__
        # Because the code does mongo.db["collection_name"]

        # Create a mock for 'db' that handles __getitem__
        mock_db = MagicMock()

        def get_collection(name):
            if name == "rsvps":
                return rsvps_col
            if name == "plus_ones":
                return plus_ones_col
            if name == "weddings":
                return weddings_col
            return MagicMock()  # Fallback

        mock_db.__getitem__.side_effect = get_collection
        mock_mongo_ref.db = mock_db

        service = RSVPService()
        return service


@pytest.mark.asyncio
async def test_submit_rsvp_synchronous(rsvp_service, mock_mongo_db):
    """Test that submit_rsvp awaits notification when no background_tasks provided"""

    # Setup data
    wedding_id = ObjectId()
    guest_id = ObjectId()
    token = "test_token_sync"

    mock_mongo_db.guests.insert_one(
        {
            "_id": guest_id,
            "token": token,
            "wedding_id": str(wedding_id),
            "name": "John Doe",
            "plus_one_allowed": True,
            "number_of_plus_ones_allowed": 1,
        }
    )

    mock_mongo_db.weddings.insert_one(
        {
            "_id": str(wedding_id),  # Stored as string in service
            "assigned_planner_email": "planner@example.com",
            "couple_names": "A & B",
        }
    )

    rsvp_data = RSVPModel(
        attending=["reception"], dietary="None", phone="1234567890", plus_ones=[]
    )

    # Mock _notify_planner_rsvp to verify it's called
    with patch.object(
        rsvp_service, "_notify_planner_rsvp", new_callable=AsyncMock
    ) as mock_notify:
        await rsvp_service.submit_rsvp(token, rsvp_data)

        # Verify notification was called
        mock_notify.assert_awaited_once()


@pytest.mark.asyncio
async def test_submit_rsvp_background_task(rsvp_service, mock_mongo_db):
    """Test that submit_rsvp uses background_tasks when provided"""

    # Setup data
    wedding_id = ObjectId()
    guest_id = ObjectId()
    token = "test_token_async"

    mock_mongo_db.guests.insert_one(
        {
            "_id": guest_id,
            "token": token,
            "wedding_id": str(wedding_id),
            "name": "Jane Doe",
            "plus_one_allowed": True,
            "number_of_plus_ones_allowed": 1,
        }
    )

    mock_mongo_db.weddings.insert_one(
        {
            "_id": str(wedding_id),
            "assigned_planner_email": "planner@example.com",
            "couple_names": "C & D",
        }
    )

    rsvp_data = RSVPModel(
        attending=["reception"], dietary="None", phone="0987654321", plus_ones=[]
    )

    background_tasks = BackgroundTasks()

    # Mock _notify_planner_rsvp
    # We want to verify it is NOT awaited, but added to background tasks
    with patch.object(
        rsvp_service, "_notify_planner_rsvp", new_callable=AsyncMock
    ) as mock_notify:
        # Pass background_tasks to submit_rsvp
        await rsvp_service.submit_rsvp(
            token, rsvp_data, background_tasks=background_tasks
        )

        # Verify notification was NOT awaited directly
        mock_notify.assert_not_awaited()

        # Verify it was added to background tasks
        assert len(background_tasks.tasks) == 1
        # We can inspect the task to ensure it's correct, but length 1 is a good start
