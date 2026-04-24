import os
import sys
from pathlib import Path

import mongomock
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("API_KEY", "test-api-key")

import app.services.budget_service as budget_module


class FakeMongo:
    def __init__(self, database):
        self.db = AsyncMockDatabase(database)

    def get_weddings_collection(self):
        return self.db["weddings"]


class AsyncMockCursor:
    def __init__(self, cursor):
        self.cursor = cursor

    def sort(self, *args, **kwargs):
        self.cursor.sort(*args, **kwargs)
        return self

    def limit(self, *args, **kwargs):
        self.cursor.limit(*args, **kwargs)
        return self

    def skip(self, *args, **kwargs):
        self.cursor.skip(*args, **kwargs)
        return self

    async def to_list(self, length=None):
        return list(self.cursor)


class AsyncMockCollection:
    def __init__(self, collection):
        self.collection = collection

    def find(self, *args, **kwargs):
        return AsyncMockCursor(self.collection.find(*args, **kwargs))

    async def find_one(self, *args, **kwargs):
        return self.collection.find_one(*args, **kwargs)

    async def insert_one(self, *args, **kwargs):
        return self.collection.insert_one(*args, **kwargs)

    async def update_one(self, *args, **kwargs):
        return self.collection.update_one(*args, **kwargs)

    async def delete_one(self, *args, **kwargs):
        return self.collection.delete_one(*args, **kwargs)


class AsyncMockDatabase:
    def __init__(self, database):
        self.db = database
        self.collections = {}

    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = AsyncMockCollection(self.db[name])
        return self.collections[name]


def _build_service(monkeypatch):
    client = mongomock.MongoClient()
    database = client["wedding_budget"]
    fake_mongo = FakeMongo(database)
    monkeypatch.setattr(budget_module, "mongo", fake_mongo)
    service = budget_module.BudgetService()
    return service, database


@pytest.fixture()
def budget_service(monkeypatch):
    return _build_service(monkeypatch)


@pytest.mark.asyncio
async def test_create_budget_template_persists_document(budget_service):
    service, database = budget_service

    payload = {
        "name": "Signature Coastal Celebration",
        "description": "Glass-inspired template for elevated seaside weddings.",
        "wedding_type": "destination",
        "target_budget_min": 45000,
        "target_budget_max": 90000,
        "guest_count_range": {"min": 60, "max": 140},
        "categories": [
            {"name": "Venue & Catering", "percentage": 45, "priority": 1},
            {"name": "Design & Decor", "percentage": 18, "priority": 2},
            {"name": "Entertainment", "percentage": 12, "priority": 3},
            {"name": "Planning & Staffing", "percentage": 10, "priority": 2},
            {"name": "Photography & Video", "percentage": 10, "priority": 2},
            {"name": "Wellness & Beauty", "percentage": 5, "priority": 3},
        ],
        "is_public": False,
    }

    result = await service.create_budget_template(
        payload, created_by="planner@example.com"
    )

    assert result["name"] == payload["name"]
    assert result["created_by"] == "planner@example.com"
    assert result["guest_count_range"] == {"min": 60, "max": 140}
    assert result["categories"][0]["priority"] == 1
    assert result["is_public"] is False
    assert "_id" in result and result["_id"]

    stored = database["budget_templates"].find_one({"name": payload["name"]})
    assert stored is not None
    assert stored["created_by"] == "planner@example.com"
    assert stored["guest_count_range"] == {"min": 60, "max": 140}
    assert len(stored["categories"]) == len(payload["categories"])


@pytest.mark.asyncio
async def test_create_budget_template_validates_percentages(budget_service):
    service, _ = budget_service

    payload = {
        "name": "Imbalanced Celebration",
        "wedding_type": "modern",
        "target_budget_min": 20000,
        "target_budget_max": 40000,
        "guest_count_range": {"min": 50, "max": 120},
        "categories": [
            {"name": "Venue", "percentage": 40, "priority": 1},
            {"name": "Decor", "percentage": 35, "priority": 2},
            {"name": "Entertainment", "percentage": 15, "priority": 3},
        ],
    }

    with pytest.raises(ValueError, match="total 100%"):
        await service.create_budget_template(payload, created_by="planner@example.com")


@pytest.mark.asyncio
async def test_create_budget_template_requires_unique_names(budget_service):
    service, _ = budget_service

    payload = {
        "name": "Duplicate Categories",
        "wedding_type": "intimate",
        "target_budget_min": 15000,
        "target_budget_max": 30000,
        "guest_count_range": {"min": 20, "max": 60},
        "categories": [
            {"name": "Venue", "percentage": 60, "priority": 1},
            {"name": "venue", "percentage": 40, "priority": 2},
        ],
    }

    with pytest.raises(ValueError, match="unique"):
        await service.create_budget_template(payload, created_by="planner@example.com")
