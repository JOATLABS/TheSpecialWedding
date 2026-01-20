import os
import sys
from datetime import datetime
from importlib import reload
from pathlib import Path

import mongomock
import pytest
from bson import ObjectId
from fastapi import FastAPI
from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("ROOT_ADMIN_EMAIL", "thedeveloper@thespecialwedding.com")


# --- Async Wrappers for mongomock ---

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

    def __aiter__(self):
        self._iterator = iter(self.cursor)
        return self

    async def __anext__(self):
        try:
            return next(self._iterator)
        except StopIteration:
            raise StopAsyncIteration


class AsyncMockCollection:
    def __init__(self, collection):
        self.collection = collection

    def find(self, *args, **kwargs):
        cursor = self.collection.find(*args, **kwargs)
        return AsyncMockCursor(cursor)

    async def find_one(self, *args, **kwargs):
        return self.collection.find_one(*args, **kwargs)

    async def insert_one(self, *args, **kwargs):
        return self.collection.insert_one(*args, **kwargs)

    async def update_one(self, *args, **kwargs):
        return self.collection.update_one(*args, **kwargs)

    async def delete_one(self, *args, **kwargs):
        return self.collection.delete_one(*args, **kwargs)

    async def delete_many(self, *args, **kwargs):
        return self.collection.delete_many(*args, **kwargs)

    async def count_documents(self, *args, **kwargs):
        return self.collection.count_documents(*args, **kwargs)


class AsyncMockDatabase:
    def __init__(self, database):
        self.db = database
        self.collections = {}

    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = AsyncMockCollection(self.db[name])
        return self.collections[name]


class FakeMongo:
    def __init__(self, database):
        self.db = AsyncMockDatabase(database)

    def get_weddings_collection(self):
        return self.db["weddings"]

    def get_vendors_collection(self):
        return self.db["vendors"]


@pytest.fixture
def budget_api_client(monkeypatch):
    client = mongomock.MongoClient()
    database = client["wedding_budget"]
    fake_mongo = FakeMongo(database)

    import app.services.budget_service as budget_service_module
    reload(budget_service_module)
    monkeypatch.setattr(budget_service_module, "mongo", fake_mongo)

    import app.dependencies.auth_extended as auth_module
    reload(auth_module)
    monkeypatch.setattr(auth_module, "mongo", fake_mongo)

    import app.api.budget as budget_api_module
    reload(budget_api_module)
    monkeypatch.setattr(budget_api_module, "budget_service", budget_service_module.BudgetService())

    app = FastAPI()
    app.include_router(budget_api_module.router, prefix="/admin")

    client = TestClient(app)

    def override_user(user):
        async def _override():
            return user

        app.dependency_overrides[budget_api_module.get_current_user_extended] = _override

    yield client, database, budget_api_module, override_user

    app.dependency_overrides.clear()


def _insert_category(database, *, category_id: str, wedding_id: str, actual_spent: float = 0.0, budgeted_amount: float = 1000.0):
    categories = database["budget_categories"]
    categories.insert_one(
        {
            "_id": ObjectId(category_id),
            "wedding_id": wedding_id,
            "name": "Catering",
            "budgeted_amount": budgeted_amount,
            "actual_spent": actual_spent,
            "payment_status": "pending",
        }
    )


def _insert_wedding(database, *, wedding_id: str, planner_email: str):
    weddings = database["weddings"]
    weddings.insert_one(
        {
            "_id": wedding_id,
            "assigned_planner_email": planner_email,
            "name": "Smith-Jones Celebration",
            "date": datetime(2025, 6, 1),
        }
    )


def test_planner_can_record_payment_for_owned_wedding(budget_api_client):
    client, database, budget_module, override_user = budget_api_client

    planner_email = "planner@example.com"
    wedding_id = "wedding_owned"
    category_id = str(ObjectId())

    _insert_wedding(database, wedding_id=wedding_id, planner_email=planner_email)
    _insert_category(database, category_id=category_id, wedding_id=wedding_id, actual_spent=200.0, budgeted_amount=1000.0)

    planner = budget_module.ExtendedAuthUser(
        email=planner_email,
        role="wedding_planner",
        user_data={"role": "wedding_planner"},
    )
    override_user(planner)

    payload = {
        "vendor_name": "Dream Catering",
        "amount": 300.0,
        "payment_method": "card",
        "payment_date": "2025-03-01T12:00:00Z",
        "description": "Final tasting invoice",
        "notes": "Paid via corporate card",
    }

    response = client.post(f"/admin/budget/category/{category_id}/payment", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Payment recorded successfully"

    records = list(database["payment_records"].find({"category_id": category_id}))
    assert len(records) == 1
    assert records[0]["amount"] == pytest.approx(300.0)
    assert records[0]["vendor_name"] == "Dream Catering"

    category = database["budget_categories"].find_one({"_id": ObjectId(category_id)})
    assert category["actual_spent"] == pytest.approx(500.0)
    assert category["payment_status"] == "partial"


def test_planner_cannot_record_payment_for_other_wedding(budget_api_client):
    client, database, budget_module, override_user = budget_api_client

    owner_email = "owner@example.com"
    intruder_email = "intruder@example.com"
    wedding_id = "wedding_owned"
    category_id = str(ObjectId())

    _insert_wedding(database, wedding_id=wedding_id, planner_email=owner_email)
    _insert_category(database, category_id=category_id, wedding_id=wedding_id)

    intruder = budget_module.ExtendedAuthUser(
        email=intruder_email,
        role="wedding_planner",
        user_data={"role": "wedding_planner"},
    )
    override_user(intruder)

    response = client.post(
        f"/admin/budget/category/{category_id}/payment",
        json={
            "amount": 150.0,
            "payment_method": "transfer",
            "payment_date": "2025-03-02T09:00:00Z",
        },
    )

    assert response.status_code == 403
    payload = response.json()
    assert payload["detail"] == "Access to this wedding denied"

    records = list(database["payment_records"].find({}))
    assert records == []


def test_record_payment_returns_not_found_for_missing_category(budget_api_client):
    client, database, budget_module, override_user = budget_api_client

    planner_email = "planner@example.com"
    wedding_id = "wedding_owned"
    _insert_wedding(database, wedding_id=wedding_id, planner_email=planner_email)

    planner = budget_module.ExtendedAuthUser(
        email=planner_email,
        role="wedding_planner",
        user_data={"role": "wedding_planner"},
    )
    override_user(planner)

    response = client.post(
        f"/admin/budget/category/{ObjectId()}/payment",
        json={
            "amount": 50.0,
            "payment_method": "cash",
            "payment_date": "2025-03-03T10:00:00Z",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Budget category not found"
    assert database["payment_records"].count_documents({}) == 0
