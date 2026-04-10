import os
import sys
from datetime import UTC, datetime, timedelta
from typing import Tuple

import mongomock
import pytest
from bson import ObjectId
from fastapi import HTTPException

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("API_KEY", "test-api-key")

import app.services.vendor_dashboard_service as vendor_dashboard_module


class FakeMongo:
    """Minimal stand-in for the Mongo connector used in the service."""

    def __init__(self, database):
        self.db = database

    def get_vendors_collection(self):
        return self.db["vendors"]

    def get_weddings_collection(self):
        return self.db["weddings"]

    def get_wedding_checklist_collection(self):
        return self.db["wedding_checklist"]


@pytest.fixture
def vendor_service(
    monkeypatch,
) -> Tuple[vendor_dashboard_module.VendorDashboardService, mongomock.database.Database]:
    client = mongomock.MongoClient()
    database = client["wedding_vendor_dashboard"]
    fake_mongo = FakeMongo(database)

    monkeypatch.setattr(vendor_dashboard_module, "mongo", fake_mongo)

    service = vendor_dashboard_module.VendorDashboardService()
    return service, database


def test_dashboard_aggregates_tasks_and_forms(vendor_service):
    service, database = vendor_service

    vendor_id = str(ObjectId())
    wedding_id = str(ObjectId())

    database["vendors"].insert_one(
        {
            "_id": ObjectId(vendor_id),
            "name": "Aurora Photography",
            "email": "vendor@example.com",
            "service_type": "photographer",
            "wedding_id": wedding_id,
        }
    )

    database["weddings"].insert_one(
        {
            "_id": ObjectId(wedding_id),
            "couple_names": "Avery & Sky",
            "date": datetime(2025, 6, 14),
            "status": "active",
            "location": "Palm Springs",
        }
    )

    database["wedding_checklist"].insert_many(
        [
            {
                "_id": ObjectId(),
                "wedding_id": wedding_id,
                "category": "Photography",
                "task": "Upload insurance certificate",
                "assigned_vendor_id": vendor_id,
                "status": "pending",
                "due_date": datetime.now(UTC) + timedelta(days=5),
            },
            {
                "_id": ObjectId(),
                "wedding_id": wedding_id,
                "category": "Photography",
                "task": "Share shot list",
                "assigned_vendor_id": vendor_id,
                "status": "completed",
                "due_date": datetime.now(UTC) - timedelta(days=2),
            },
        ]
    )

    form_id = str(ObjectId())
    database["vendor_forms"].insert_one(
        {
            "_id": ObjectId(form_id),
            "wedding_id": wedding_id,
            "form_name": "Photography Questionnaire",
            "vendor_email": "vendor@example.com",
            "vendor_type": "photographer",
            "fields": [{"id": "portfolio"}],
            "status": "sent",
            "access_token": "token-123",
        }
    )

    database["vendor_submissions"].insert_one(
        {
            "_id": ObjectId(),
            "form_id": form_id,
            "vendor_email": "vendor@example.com",
            "submission_data": {},
            "submitted_at": datetime.now(UTC),
        }
    )

    dashboard = service.get_dashboard(
        vendor_email="vendor@example.com",
        assigned_wedding_ids=[wedding_id],
    )

    assert dashboard["profile"]["email"] == "vendor@example.com"
    assert dashboard["stats"]["total_tasks"] == 2
    assert dashboard["stats"]["completed_tasks"] == 1
    assert dashboard["stats"]["pending_forms"] == 1
    assert len(dashboard["weddings"]) == 1
    assert dashboard["weddings"][0]["name"] == "Avery & Sky"
    assert dashboard["forms"]["pending"][0]["form_name"] == "Photography Questionnaire"


def test_update_task_status_enforces_assignment(vendor_service):
    service, database = vendor_service

    vendor_id = str(ObjectId())
    other_vendor = str(ObjectId())
    wedding_id = "wed-001"

    database["wedding_checklist"].insert_one(
        {
            "_id": ObjectId("65abcdef1234567890abcdef"),
            "wedding_id": wedding_id,
            "category": "Catering",
            "task": "Confirm menu",
            "assigned_vendor_id": other_vendor,
            "status": "pending",
        }
    )

    with pytest.raises(HTTPException) as exc:
        service.update_task_status(
            task_id="65abcdef1234567890abcdef",
            new_status="completed",
            actor_email="vendor@example.com",
            allowed_vendor_ids=[vendor_id],
            allowed_wedding_ids=[],
        )

    assert exc.value.status_code == 403

    updated = service.update_task_status(
        task_id="65abcdef1234567890abcdef",
        new_status="in_progress",
        actor_email="planner@example.com",
        allowed_vendor_ids=[vendor_id],
        allowed_wedding_ids=[wedding_id],
        bypass_permission=True,
    )

    assert updated["status"] == "in_progress"
