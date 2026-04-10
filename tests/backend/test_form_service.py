import os
import sys
from datetime import datetime
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

import app.services.form_service as form_service_module
from app.models.form import DuplicateFormRequest


class FakeMongo:
    def __init__(self, database):
        self.db = database

    def get_forms_collection(self):
        return self.db["forms"]


def _utc_now() -> datetime:
    return datetime.utcnow()


@pytest.fixture
def form_service(monkeypatch):
    client = mongomock.MongoClient()
    database = client["wedding_forms"]
    fake_mongo = FakeMongo(database)
    monkeypatch.setattr(form_service_module, "mongo", fake_mongo)
    monkeypatch.setattr(
        form_service_module.rate_limiter,
        "check_rate_limit",
        lambda *args, **kwargs: True,
    )

    service = form_service_module.FormService()
    return service, database


def _sample_form_doc(created_by: str, **overrides):
    now = _utc_now()
    planner_key = created_by.replace(".", "_")
    return {
        "_id": overrides.get("_id", "form_original"),
        "name": overrides.get("name", "Vendor Intake"),
        "settings": overrides.get(
            "settings",
            {
                "title": "Vendor Intake",
                "description": "Collect vendor proposals",
                "submit_button_text": "Submit",
                "success_message": "Thank you!",
                "allow_multiple_submissions": False,
                "collect_email": True,
                "is_public": True,
                "requires_auth": False,
            },
        ),
        "fields": overrides.get(
            "fields",
            [
                {
                    "id": "company_name",
                    "label": "Company name",
                    "type": "text",
                    "required": True,
                    "order": 1,
                }
            ],
        ),
        "created_by": created_by,
        "wedding_id": overrides.get("wedding_id"),
        "template_type": overrides.get("template_type"),
        "is_active": True,
        "created_at": overrides.get("created_at", now),
        "updated_at": overrides.get("updated_at", now),
        "submission_count": overrides.get("submission_count", 0),
        "planner_state": overrides.get(
            "planner_state",
            {
                planner_key: {
                    "last_viewed_submission_count": overrides.get(
                        "last_viewed_submission_count", 0
                    ),
                    "last_viewed_responses_at": overrides.get(
                        "last_viewed_responses_at"
                    ),
                    "last_viewed_analytics_at": overrides.get(
                        "last_viewed_analytics_at"
                    ),
                }
            },
        ),
    }


def test_duplicate_form_copies_structure_and_resets_submission_state(form_service):
    service, database = form_service
    planner_email = "planner@example.com"

    database["forms"].insert_one(_sample_form_doc(planner_email))

    request = DuplicateFormRequest(new_name="Vendor Intake Copy")
    result = service.duplicate_form("form_original", request, planner_email)

    assert "id" in result
    duplicated = database["forms"].find_one({"_id": result["id"]})
    assert duplicated is not None
    assert duplicated["name"] == "Vendor Intake Copy"
    assert duplicated["submission_count"] == 0
    planner_key = planner_email.replace(".", "_")
    assert duplicated["planner_state"][planner_key]["last_viewed_submission_count"] == 0
    assert duplicated["fields"][0]["id"] == "company_name"
    assert duplicated["created_by"] == planner_email


def test_mark_form_viewed_updates_planner_state_and_unread_counter(form_service):
    service, database = form_service
    planner_email = "planner@example.com"

    database["forms"].insert_one(
        _sample_form_doc(
            planner_email,
            submission_count=5,
            planner_state={
                planner_email: {
                    "last_viewed_submission_count": 2,
                    "last_viewed_responses_at": None,
                    "last_viewed_analytics_at": None,
                }
            },
        )
    )

    forms_before = service.get_forms(planner_email)
    assert forms_before[0]["unread_responses"] == 3

    result = service.mark_form_viewed(
        "form_original", planner_email, "responses", submission_count=5
    )
    assert result["unread_responses"] == 0

    stored = database["forms"].find_one({"_id": "form_original"})
    planner_key = planner_email.replace(".", "_")
    assert stored["planner_state"][planner_key]["last_viewed_submission_count"] == 5
    assert stored["planner_state"][planner_key]["last_viewed_responses_at"] is not None

    forms_after = service.get_forms(planner_email)
    assert forms_after[0]["unread_responses"] == 0


def test_mark_form_viewed_rejects_invalid_scope(form_service):
    service, database = form_service
    planner_email = "planner@example.com"

    database["forms"].insert_one(_sample_form_doc(planner_email))

    with pytest.raises(HTTPException) as exc_info:
        service.mark_form_viewed("form_original", planner_email, "unknown")

    assert exc_info.value.status_code == 400
