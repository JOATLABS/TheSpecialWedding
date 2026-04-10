import os
import sys
from datetime import datetime
from importlib import reload
from pathlib import Path

import mongomock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("ROOT_ADMIN_EMAIL", "thedeveloper@thespecialwedding.com")


class AsyncMockCursor:
    def __init__(self, cursor):
        self.cursor = cursor

    def sort(self, *args, **kwargs):
        self.cursor.sort(*args, **kwargs)
        return self

    async def to_list(self, length=None):
        return list(self.cursor)


class AsyncMockCollection:
    def __init__(self, collection, database):
        self.collection = collection
        self.database = database

    def find(self, *args, **kwargs):
        return AsyncMockCursor(self.collection.find(*args, **kwargs))

    async def find_one(self, *args, **kwargs):
        return self.collection.find_one(*args, **kwargs)

    async def insert_one(self, *args, **kwargs):
        return self.collection.insert_one(*args, **kwargs)

    async def update_one(self, *args, **kwargs):
        return self.collection.update_one(*args, **kwargs)


class AsyncMockDatabase:
    def __init__(self, database):
        self.database = database
        self.collections = {}

    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = AsyncMockCollection(self.database[name], self)
        return self.collections[name]


class FakeMongo:
    def __init__(self, database):
        self.db = AsyncMockDatabase(database)

    def get_forms_collection(self):
        return self.db["forms"]


@pytest.fixture
def api_client(monkeypatch):
    client = mongomock.MongoClient()
    database = client["wedding_forms"]
    fake_mongo = FakeMongo(database)

    import app.services.form_service as form_service_module

    reload(form_service_module)

    monkeypatch.setattr(form_service_module, "mongo", fake_mongo)
    monkeypatch.setattr(
        form_service_module.rate_limiter,
        "check_rate_limit",
        lambda *args, **kwargs: True,
    )

    import app.api.forms as forms_module

    reload(forms_module)

    async def _noop_security_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(forms_module, "form_service", form_service_module.FormService())
    monkeypatch.setattr(
        forms_module.rate_limiter, "check_rate_limit", lambda *args, **kwargs: True
    )
    monkeypatch.setattr(
        forms_module.security_audit, "log_security_event", _noop_security_audit
    )

    app = FastAPI()
    app.include_router(forms_module.router, prefix="/admin")

    client = TestClient(app)

    def override_user(user):
        async def _override():
            return user

        app.dependency_overrides[forms_module.require_team_or_planner] = _override

    yield client, database, forms_module, override_user

    app.dependency_overrides.clear()


def _form_document(created_by: str, **overrides):
    now = datetime.utcnow()
    return {
        "_id": overrides.get("_id", f"form_{int(now.timestamp() * 1000)}"),
        "name": overrides.get("name", "Inquiry"),
        "settings": overrides.get(
            "settings",
            {
                "title": "Inquiry",
                "description": "",
                "is_public": False,
            },
        ),
        "fields": overrides.get("fields", []),
        "created_by": created_by,
        "wedding_id": overrides.get("wedding_id"),
        "template_type": overrides.get("template_type"),
        "is_active": overrides.get("is_active", True),
        "created_at": overrides.get("created_at", now),
        "updated_at": overrides.get("updated_at", now),
        "submission_count": overrides.get("submission_count", 0),
        "planner_state": overrides.get("planner_state", {}),
    }


def test_root_admin_can_view_all_forms(api_client):
    client, database, forms_module, override_user = api_client

    forms_collection = database["forms"]
    forms_collection.insert_many(
        [
            _form_document("planner.one@example.com", _id="form_planner_one"),
            _form_document(
                "planner.two@example.com", _id="form_planner_two", submission_count=3
            ),
        ]
    )

    root_admin = forms_module.ExtendedAuthUser(
        email=os.environ["ROOT_ADMIN_EMAIL"],
        role="ROOT_ADMIN",
        user_data={"role": "ROOT_ADMIN"},
    )
    override_user(root_admin)

    response = client.get("/admin/forms")

    assert response.status_code == 200
    payload = response.json()

    assert isinstance(payload, list)
    ids = {item["id"] for item in payload}
    assert ids == {"form_planner_one", "form_planner_two"}
    assert all(item.get("unread_responses", 0) == 0 for item in payload)


def test_planner_blank_form_creation_sanitises_payload(api_client):
    client, database, forms_module, override_user = api_client

    planner = forms_module.ExtendedAuthUser(
        email="planner@example.com",
        role="wedding_planner",
        user_data={"role": "wedding_planner"},
    )
    override_user(planner)

    response = client.post(
        "/admin/forms",
        json={
            "name": "  RSVP Intake  ",
            "settings": {
                "title": "  RSVP Intake  ",
                "description": "Gather replies",
                "submit_button_text": "Submit",
                "success_message": "Thanks!",
                "allow_multiple_submissions": False,
                "collect_email": True,
                "is_public": False,
                "requires_auth": False,
            },
            "fields": [],
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert "id" in result

    stored = database["forms"].find_one({"_id": result["id"]})
    assert stored is not None
    assert stored["name"] == "RSVP Intake"
    assert stored["created_by"] == "planner@example.com"
    assert stored["submission_count"] == 0

    planner_state_key = "planner@example.com".replace(".", "_")
    planner_state = stored["planner_state"][planner_state_key]
    assert planner_state["last_viewed_submission_count"] == 0
    assert planner_state["last_viewed_responses_at"] is None
    assert planner_state["last_viewed_analytics_at"] is None

    assert stored["settings"]["collect_email"] is True
    assert stored["fields"] == []


def test_planner_cannot_update_view_state_for_other_form(api_client):
    client, database, forms_module, override_user = api_client

    owner_email = "owner@example.com"
    intruder_email = "intruder@example.com"
    planner_state_key = owner_email.replace(".", "_")

    database["forms"].insert_one(
        _form_document(
            owner_email,
            _id="form_shared",
            submission_count=4,
            planner_state={
                planner_state_key: {
                    "last_viewed_submission_count": 1,
                    "last_viewed_responses_at": None,
                }
            },
        )
    )

    intruder = forms_module.ExtendedAuthUser(
        email=intruder_email,
        role="wedding_planner",
        user_data={"role": "wedding_planner"},
    )
    override_user(intruder)

    response = client.post(
        "/admin/forms/form_shared/views",
        json={"scope": "responses", "submission_count": 4},
    )

    assert response.status_code == 403
    payload = response.json()
    assert payload["detail"] == "Access denied to form"

    stored = database["forms"].find_one({"_id": "form_shared"})
    state = stored["planner_state"][planner_state_key]
    assert state["last_viewed_submission_count"] == 1
    assert "intruder@example_com" not in stored["planner_state"]


def test_planner_updates_own_view_state(api_client):
    client, database, forms_module, override_user = api_client

    planner_email = "planner@example.com"
    planner_state_key = planner_email.replace(".", "_")

    database["forms"].insert_one(
        _form_document(
            planner_email,
            _id="form_personal",
            submission_count=6,
            planner_state={
                planner_state_key: {
                    "last_viewed_submission_count": 2,
                    "last_viewed_responses_at": None,
                }
            },
        )
    )

    planner = forms_module.ExtendedAuthUser(
        email=planner_email,
        role="wedding_planner",
        user_data={"role": "wedding_planner"},
    )
    override_user(planner)

    response = client.post(
        "/admin/forms/form_personal/views",
        json={"scope": "responses", "submission_count": 5},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["unread_responses"] == 1

    stored = database["forms"].find_one({"_id": "form_personal"})
    state = stored["planner_state"][planner_state_key]
    assert state["last_viewed_submission_count"] == 5
    assert state["last_viewed_responses_at"] is not None


def test_root_admin_can_mark_form_viewed(api_client):
    client, database, forms_module, override_user = api_client

    owner_email = "owner@example.com"
    planner_state_key = owner_email.replace(".", "_")

    database["forms"].insert_one(
        _form_document(
            owner_email,
            _id="form_admin_view",
            submission_count=3,
            planner_state={
                planner_state_key: {
                    "last_viewed_submission_count": 0,
                    "last_viewed_responses_at": None,
                }
            },
        )
    )

    root_admin = forms_module.ExtendedAuthUser(
        email=os.environ["ROOT_ADMIN_EMAIL"],
        role="ROOT_ADMIN",
        user_data={"role": "ROOT_ADMIN"},
    )
    override_user(root_admin)

    response = client.post(
        "/admin/forms/form_admin_view/views",
        json={"scope": "analytics"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Form view recorded"

    stored = database["forms"].find_one({"_id": "form_admin_view"})
    # Root admin updates their own email state, but original owner data should remain
    assert (
        stored["planner_state"][planner_state_key]["last_viewed_submission_count"] == 0
    )
    admin_key = os.environ["ROOT_ADMIN_EMAIL"].lower().replace(".", "_")
    assert stored["planner_state"][admin_key]["last_viewed_analytics_at"] is not None
