import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import mongomock
import pytest
from fastapi import HTTPException

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("API_KEY", "test-api-key")

import app.services.form_service as form_module  # noqa: E402
from app.models.form import CreateFormRequest, FormSettings  # noqa: E402


class DummyEmailService:
    def __init__(self, *_, **__):
        self.sent = []


class FakeMongo:
    def __init__(self, database):
        self.db = database

    def get_forms_collection(self):
        return self.db["forms"]


@pytest.fixture()
def form_service(monkeypatch):
    client = mongomock.MongoClient()
    database = client["wedding_forms"]
    fake_mongo = FakeMongo(database)

    monkeypatch.setattr(form_module, "mongo", fake_mongo)
    monkeypatch.setattr(form_module, "ResendEmailService", DummyEmailService)
    monkeypatch.setattr(form_module.rate_limiter, "check_rate_limit", lambda *_, **__: True)

    service = form_module.FormService()
    return service, database


def test_create_blank_form_persists_document(form_service):
    service, database = form_service

    request = CreateFormRequest(
        name="Vendor Intake",
        settings=FormSettings(
            title="Vendor Intake",
            description="Collect company details and availability.",
            submit_button_text="Send",
            success_message="Thank you!",
            allow_multiple_submissions=False,
            collect_email=True,
            is_public=True,
            requires_auth=False,
        ),
        fields=[],
    )

    result = service.create_form(request, created_by="planner@example.com")

    assert result["message"] == "Form created successfully"
    stored = database["forms"].find_one({"_id": result["id"]})
    assert stored is not None
    assert stored["name"] == "Vendor Intake"
    assert stored["created_by"] == "planner@example.com"
    assert stored["settings"]["title"] == "Vendor Intake"
    assert stored["submission_count"] == 0
    assert stored["is_active"] is True


def test_duplicate_form_copies_settings_and_resets_counters(form_service):
    service, database = form_service

    original_id = "form_1700000000000"
    database["forms"].insert_one(
        {
            "_id": original_id,
            "name": "Guest Feedback",
            "settings": {
                "title": "Guest Feedback",
                "description": "Capture guest experience",
                "submit_button_text": "Share",
                "success_message": "We appreciate your insight!",
                "allow_multiple_submissions": False,
                "collect_email": True,
                "is_public": True,
                "requires_auth": False,
            },
            "fields": [
                {
                    "id": "experience",
                    "label": "Overall experience",
                    "type": "text",
                    "required": True,
                    "order": 1,
                }
            ],
            "created_by": "planner@example.com",
            "wedding_id": "wedding-123",
            "template_type": "custom",
            "is_active": True,
            "created_at": datetime.utcnow() - timedelta(days=2),
            "updated_at": datetime.utcnow() - timedelta(days=1),
            "submission_count": 12,
        }
    )

    result = service.duplicate_form(
        form_id=original_id,
        new_name="Guest Feedback Copy",
        created_by="planner@example.com",
    )

    assert result["message"] == "Form duplicated successfully"
    duplicate = database["forms"].find_one({"name": "Guest Feedback Copy"})
    assert duplicate is not None
    assert duplicate["_id"] != original_id
    assert duplicate["created_by"] == "planner@example.com"
    assert duplicate["wedding_id"] == "wedding-123"
    assert duplicate["submission_count"] == 0
    assert duplicate["fields"][0]["id"] == "experience"


def test_duplicate_form_requires_ownership(form_service):
    service, _ = form_service

    with pytest.raises(HTTPException) as exc:
        service.duplicate_form(
            form_id="form_999",
            new_name="Unauthorized Copy",
            created_by="unauthorized@example.com",
        )

    assert exc.value.status_code == 404


def test_root_admin_can_duplicate_other_users_form(form_service):
    service, database = form_service

    original_id = "form_1800000000000"
    database["forms"].insert_one(
        {
            "_id": original_id,
            "name": "Planner Intake",
            "settings": {
                "title": "Planner Intake",
                "submit_button_text": "Submit",
                "success_message": "Thanks",
                "allow_multiple_submissions": False,
                "collect_email": True,
                "is_public": False,
                "requires_auth": True,
            },
            "fields": [
                {
                    "id": "agency_name",
                    "label": "Agency name",
                    "type": "text",
                    "required": True,
                    "order": 1,
                }
            ],
            "created_by": "planner@example.com",
            "is_active": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "submission_count": 3,
        }
    )

    result = service.duplicate_form(
        form_id=original_id,
        new_name="Planner Intake Copy",
        created_by="root@example.com",
        is_root_admin=True,
    )

    assert result["message"] == "Form duplicated successfully"
    duplicate = database["forms"].find_one({"name": "Planner Intake Copy"})
    assert duplicate is not None
    assert duplicate["created_by"] == "root@example.com"
    assert duplicate["settings"]["requires_auth"] is True
