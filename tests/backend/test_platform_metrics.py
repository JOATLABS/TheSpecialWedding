from datetime import datetime, timedelta
from pathlib import Path
import os
from types import SimpleNamespace
import sys

import mongomock
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("API_KEY", "test-api-key")

import app.api.saas_config as saas_config  # noqa: E402
import app.api.platform_metrics as platform_metrics_api  # noqa: E402
from app.core.config import settings  # noqa: E402
import app.core.database as database_module  # noqa: E402
from app.dependencies.auth import require_admin  # noqa: E402
from app.dependencies.auth_extended import require_root_admin  # noqa: E402
from app.services.platform_metrics_service import PlatformMetricsService  # noqa: E402
import app.services.platform_metrics_service as platform_metrics_service  # noqa: E402


class FakeMongo:
    """In-memory stand-in for the production Mongo connector."""

    def __init__(self, database):
        self.db = database

    def get_users_collection(self):
        return self.db["users"]

    def get_subscription_plans_collection(self):
        return self.db["subscription_plans"]

    def get_platform_metrics_collection(self):
        return self.db["platform_metrics"]

    def get_guest_collection(self):
        return self.db["guests"]

    def get_weddings_collection(self):
        return self.db["weddings"]

    def get_rsvps_collection(self):
        return self.db["rsvps"]

    def get_forms_collection(self):
        return self.db["forms"]

    def get_form_responses_collection(self):
        return self.db["form_responses"]

    def get_ai_usage_collection(self):
        return self.db["ai_usage"]


@pytest.fixture
def mongo_fixture(monkeypatch):
    client = mongomock.MongoClient()
    database = client["wedding_webapp"]
    fake = FakeMongo(database)
    monkeypatch.setattr(saas_config, "mongo", fake)
    return fake, database


@pytest.fixture
def anyio_backend():
    """Constrain anyio-backed tests to asyncio only."""
    return "asyncio"


@pytest.fixture
def snapshot_test_client(monkeypatch):
    client = mongomock.MongoClient()
    database = client["wedding_webapp"]
    fake = FakeMongo(database)

    service = PlatformMetricsService(fake)
    monkeypatch.setattr(platform_metrics_service, "service", service)
    monkeypatch.setattr(platform_metrics_api, "metrics_service", service)
    monkeypatch.setattr(settings, "PLATFORM_METRICS_TOKEN", "metrics-test-token")
    monkeypatch.setattr(database_module, "mongo", fake)

    app = FastAPI()
    app.include_router(platform_metrics_api.router)

    async def override_require_admin():
        return SimpleNamespace(role="admin", is_root_admin=True)

    app.dependency_overrides[require_admin] = override_require_admin
    app.dependency_overrides[require_root_admin] = override_require_admin

    return TestClient(app)


@pytest.mark.anyio("asyncio")
async def test_platform_metrics_compiles_expected_totals(mongo_fixture):
    fake_mongo, db = mongo_fixture
    now = datetime.utcnow()

    # Users
    users = fake_mongo.get_users_collection()
    users.insert_many(
        [
            {
                "_id": "u1",
                "role": "wedding_planner",
                "is_active": True,
                "created_at": now - timedelta(days=3),
            },
            {
                "_id": "u2",
                "role": "vendor",
                "is_active": False,
                "created_at": now - timedelta(days=40),
            },
            {
                "_id": "u3",
                "role": "wedding_planner",
                "is_active": True,
                "created_at": now - timedelta(days=1),
            },
        ]
    )

    # Subscription plans and assignments
    plans = fake_mongo.get_subscription_plans_collection()
    plans.insert_one(
        {
            "_id": "plan_basic",
            "name": "Basic",
            "price_monthly": 50,
            "price_yearly": 540,
            "is_active": True,
        }
    )

    subscriptions = db.get_collection("user_subscriptions")
    subscriptions.insert_many(
        [
            {"_id": "sub1", "plan_id": "plan_basic", "status": "active", "billing_interval": "monthly"},
            {"_id": "sub2", "plan_id": "plan_basic", "status": "trial", "billing_interval": "monthly"},
        ]
    )

    # Weddings and related records
    weddings = fake_mongo.get_weddings_collection()
    weddings.insert_many(
        [
            {
                "_id": "wed1",
                "status": "active",
                "date": (now + timedelta(days=10)).strftime("%Y-%m-%d"),
                "guest_count": 120,
                "created_at": now - timedelta(days=3),
            },
            {
                "_id": "wed2",
                "status": "cancelled",
                "date": (now - timedelta(days=5)).strftime("%Y-%m-%d"),
                "guest_count": 30,
                "created_at": now - timedelta(days=12),
            },
        ]
    )

    fake_mongo.get_guest_collection().insert_many([{ "_id": "guest1" }, { "_id": "guest2" }])
    fake_mongo.get_rsvps_collection().insert_many([{ "_id": "rsvp1" }, { "_id": "rsvp2" }])

    forms = fake_mongo.get_forms_collection()
    forms.insert_one(
        {
            "_id": "form1",
            "is_active": True,
            "created_at": now - timedelta(days=2),
        }
    )

    fake_mongo.get_form_responses_collection().insert_one(
        {"_id": "resp1", "submitted_at": now - timedelta(days=1)}
    )

    db.get_collection("notifications").insert_one(
        {"_id": "notif1", "status": "sent", "sent_at": now - timedelta(days=1)}
    )
    db.get_collection("email_logs").insert_one(
        {"_id": "email1", "status": "success", "sent_at": now - timedelta(days=1)}
    )
    fake_mongo.get_ai_usage_collection().insert_one(
        {"_id": "ai1", "created_at": now - timedelta(hours=4)}
    )

    metrics = await saas_config.get_platform_metrics(
        timeframe="7d", current_user=SimpleNamespace()
    )

    assert metrics["users"]["total"] == 3
    assert metrics["users"]["new_in_period"] == 2
    assert metrics["subscriptions"]["status_breakdown"]["active"] == 1
    assert metrics["subscriptions"]["monthly_recurring_revenue"] == pytest.approx(50)
    assert metrics["subscriptions"]["projected_annual_revenue"] == pytest.approx(600)
    assert metrics["operations"]["weddings"]["total"] == 2
    assert metrics["operations"]["weddings"]["upcoming"] == 1
    assert metrics["operations"]["weddings"]["created_in_period"] == 1
    assert metrics["operations"]["forms"]["responses_in_period"] == 1
    assert metrics["operations"]["communications"]["emails_sent_in_period"] == 1
    assert metrics["operations"]["communications"]["ai_events_in_period"] == 1


@pytest.mark.anyio("asyncio")
async def test_platform_metrics_rejects_invalid_timeframe(monkeypatch):
    fake = FakeMongo(mongomock.MongoClient()["test"])
    monkeypatch.setattr(saas_config, "mongo", fake)

    with pytest.raises(HTTPException):
        await saas_config.get_platform_metrics(
            timeframe="15d", current_user=SimpleNamespace()
        )


def test_metrics_snapshot_endpoints_roundtrip(snapshot_test_client):
    client = snapshot_test_client
    headers = {"Authorization": "Bearer metrics-test-token"}

    payload = {
        "snapshot_time": "2024-01-01T12:00:00Z",
        "metrics": {"users": {"total": 5}},
    }

    ingest_response = client.post("/metrics/snapshot", json=payload, headers=headers)
    assert ingest_response.status_code == 200
    body = ingest_response.json()
    assert body["metrics"]["users"]["total"] == 5
    assert body["snapshot_time"].startswith("2024-01-01T12:00:00")
    assert body["ingested_at"]

    snapshot_response = client.get("/metrics/snapshot", headers=headers)
    assert snapshot_response.status_code == 200
    latest = snapshot_response.json()
    assert latest["id"] == body["id"]

    admin_response = client.get("/admin/platform/metrics")
    assert admin_response.status_code == 200
    assert admin_response.json()["id"] == body["id"]

    history_response = client.get(
        "/admin/platform/metrics/history",
        params={"start_date": "2023-12-01T00:00:00Z"},
    )
    assert history_response.status_code == 200
    history = history_response.json()
    assert history and history[0]["id"] == body["id"]


def test_metrics_snapshot_endpoints_handle_empty(snapshot_test_client, monkeypatch):
    client = snapshot_test_client
    headers = {"Authorization": "Bearer metrics-test-token"}

    # Mock live health generation to succeed
    async def mock_get_health(current_user):
        return {
            "health": {"status": "healthy"},
            "metrics": {},
            "timestamp": "2024-01-01T00:00:00Z"
        }

    monkeypatch.setattr("app.api.admin_platform_metrics.get_platform_health", mock_get_health)

    response = client.get("/metrics/snapshot", headers=headers)
    assert response.status_code == 404

    # Admin endpoint should fall back to live health data (200), not 404
    admin_response = client.get("/admin/platform/metrics")
    assert admin_response.status_code == 200
    assert admin_response.json()["metrics"] == {"health": {"status": "healthy"}, "metrics": {}, "timestamp": "2024-01-01T00:00:00Z"}

    history_response = client.get("/admin/platform/metrics/history")
    assert history_response.status_code == 200
    assert history_response.json() == []
