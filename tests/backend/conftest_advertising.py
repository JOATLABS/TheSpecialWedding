"""
Shared fixtures and async-mock helpers for advertising campaign tests.

Provides:
- AsyncMock wrappers for mongomock (cursor, collection, database)
- FakeMongo connector matching the real MongoConnector interface
- Helper factories for creating test campaigns, creatives, users
- Fake auth user builders for vendor and admin roles
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import mongomock
import pytest
from bson import ObjectId

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("ROOT_ADMIN_EMAIL", "thedeveloper@thespecialwedding.io")


# =============================================================================
# ASYNC MOCK WRAPPERS (mongomock is synchronous, our services are async)
# =============================================================================


class AsyncMockCursor:
    """Wraps a synchronous mongomock cursor to support async iteration."""

    def __init__(self, cursor):
        self._cursor = cursor

    def sort(self, *args, **kwargs):
        self._cursor = self._cursor.sort(*args, **kwargs)
        return self

    def limit(self, *args, **kwargs):
        self._cursor = self._cursor.limit(*args, **kwargs)
        return self

    def skip(self, *args, **kwargs):
        self._cursor = self._cursor.skip(*args, **kwargs)
        return self

    async def to_list(self, length=None):
        return list(self._cursor)

    def __aiter__(self):
        self._iter = iter(self._cursor)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


class AsyncMockCollection:
    """Wraps a synchronous mongomock collection with async methods."""

    def __init__(self, collection):
        self._col = collection

    def find(self, *args, **kwargs):
        return AsyncMockCursor(self._col.find(*args, **kwargs))

    async def find_one(self, *args, **kwargs):
        return self._col.find_one(*args, **kwargs)

    async def find_one_and_update(self, *args, **kwargs):
        return self._col.find_one_and_update(*args, **kwargs)

    async def insert_one(self, *args, **kwargs):
        return self._col.insert_one(*args, **kwargs)

    async def update_one(self, *args, **kwargs):
        return self._col.update_one(*args, **kwargs)

    async def update_many(self, *args, **kwargs):
        return self._col.update_many(*args, **kwargs)

    async def delete_one(self, *args, **kwargs):
        return self._col.delete_one(*args, **kwargs)

    async def delete_many(self, *args, **kwargs):
        return self._col.delete_many(*args, **kwargs)

    async def count_documents(self, *args, **kwargs):
        return self._col.count_documents(*args, **kwargs)

    async def distinct(self, *args, **kwargs):
        return self._col.distinct(*args, **kwargs)

    async def create_index(self, *args, **kwargs):
        return self._col.create_index(*args, **kwargs)

    def aggregate(self, pipeline, **kwargs):
        """
        mongomock supports basic aggregation.
        Returns an AsyncMockCursor over the pipeline results.
        """
        return AsyncMockCursor(self._col.aggregate(pipeline, **kwargs))


class AsyncMockDatabase:
    """Wraps a mongomock database to return AsyncMockCollections."""

    def __init__(self, database):
        self._db = database
        self._collections = {}

    def __getitem__(self, name):
        if name not in self._collections:
            self._collections[name] = AsyncMockCollection(self._db[name])
        return self._collections[name]


class FakeMongo:
    """Fake MongoConnector matching the real interface."""

    def __init__(self, database):
        self.db = AsyncMockDatabase(database)

    def get_users_collection(self):
        return self.db["users"]

    def get_weddings_collection(self):
        return self.db["weddings"]

    def get_vendors_collection(self):
        return self.db["vendors"]


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_db():
    """Create a fresh async-wrapped mongomock database."""
    client = mongomock.MongoClient()
    raw_db = client["test_advertising"]
    return AsyncMockDatabase(raw_db)


@pytest.fixture
def raw_db():
    """Create a fresh raw mongomock database (synchronous, for seeding)."""
    client = mongomock.MongoClient()
    return client["test_advertising"]


# =============================================================================
# TEST DATA FACTORIES
# =============================================================================

VENDOR_ID = str(ObjectId())
VENDOR_EMAIL = "florist@example.com"
VENDOR_NAME = "Bloom & Petal Florals"
ADMIN_EMAIL = "thedeveloper@thespecialwedding.io"


def make_campaign(
    vendor_id=VENDOR_ID,
    vendor_email=VENDOR_EMAIL,
    vendor_name=VENDOR_NAME,
    status="draft",
    **overrides,
):
    """Create a campaign document matching AdCampaign schema."""
    now = datetime.now(timezone.utc)
    doc = {
        "vendor_id": vendor_id,
        "vendor_email": vendor_email,
        "vendor_name": vendor_name,
        "campaign_name": "Spring Wedding Collection",
        "campaign_description": "Elegant spring arrangements",
        "goal": "profile_visits",
        "status": status,
        "target_categories": ["florist"],
        "target_wedding_stages": [],
        "target_placements": [],
        "target_regions": ["Dallas, TX"],
        "target_budget_min": None,
        "target_budget_max": None,
        "daily_budget": 0.0,
        "total_budget": 0.0,
        "budget_consumed": 0.0,
        "pacing_strategy": "even",
        "start_date": None,
        "end_date": None,
        "bid_amount": 0.0,
        "bid_strategy": "fixed",
        "quality_score": 50,
        "impression_count": 0,
        "click_count": 0,
        "lead_count": 0,
        "conversion_count": 0,
        "primary_creative_id": None,
        "creative_ids": [],
        "submitted_at": None,
        "reviewed_at": None,
        "reviewed_by": None,
        "review_notes": None,
        "vendor_category": "florist",
        "vendor_service_area": "Dallas, TX",
        "vendor_logo_url": None,
        "created_by": vendor_email,
        "metadata": {},
        "created_at": now,
        "updated_at": now,
    }
    doc.update(overrides)
    return doc


def make_creative(campaign_id, vendor_id=VENDOR_ID, **overrides):
    """Create a creative document matching AdCreative schema."""
    now = datetime.now(timezone.utc)
    doc = {
        "campaign_id": str(campaign_id),
        "vendor_id": vendor_id,
        "creative_type": "image",
        "image_url": "https://cdn.example.com/ads/florist-spring.jpg",
        "image_alt_text": "Spring bouquet arrangement",
        "headline": "Elegant Spring Arrangements",
        "description": "Hand-tied bouquets starting at $150",
        "offer": "Free consultation for weddings over 100 guests",
        "call_to_action": "View Portfolio",
        "review_status": "pending",
        "submitted_at": now,
        "reviewed_at": None,
        "reviewed_by": None,
        "review_notes": None,
        "is_primary": False,
        "metadata": {},
        "created_at": now,
        "updated_at": now,
    }
    doc.update(overrides)
    return doc


def make_ad_event(campaign_id, event_type="impression_served", **overrides):
    """Create an ad_event document."""
    now = datetime.now(timezone.utc)
    doc = {
        "event_type": event_type,
        "sponsored_vendor_id": str(ObjectId()),
        "vendor_profile_id": str(ObjectId()),
        "placement": "vendor_rail",
        "campaign_id": str(campaign_id),
        "creative_id": None,
        "wedding_id": None,
        "planner_id": None,
        "session_id": None,
        "click_id": None,
        "metadata": {},
        "created_at": now,
        "updated_at": now,
    }
    doc.update(overrides)
    return doc


def make_ad_lead(campaign_id, lead_type="quote_request", **overrides):
    """Create an ad_lead document."""
    now = datetime.now(timezone.utc)
    doc = {
        "sponsored_vendor_id": str(ObjectId()),
        "vendor_profile_id": str(ObjectId()),
        "campaign_id": str(campaign_id),
        "planner_id": "planner@example.com",
        "wedding_id": None,
        "lead_type": lead_type,
        "status": "pending",
        "click_id": None,
        "placement": "vendor_rail",
        "message": "I'd like a quote for my June wedding",
        "quote_amount": None,
        "responded_at": None,
        "converted_at": None,
        "metadata": {},
        "created_at": now,
        "updated_at": now,
    }
    doc.update(overrides)
    return doc


def make_vendor_user(vendor_id=VENDOR_ID, **overrides):
    """Create an advertising vendor user document."""
    doc = {
        "_id": ObjectId(vendor_id),
        "email": VENDOR_EMAIL,
        "name": VENDOR_NAME,
        "role": "advertising_vendor",
        "is_active": True,
        "email_verified": True,
        "created_at": datetime.now(timezone.utc),
    }
    doc.update(overrides)
    return doc
