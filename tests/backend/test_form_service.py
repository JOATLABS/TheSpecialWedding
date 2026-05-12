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

import app.services.form_service as form_service_module  # noqa: E402
from app.models.form import DuplicateFormRequest  # noqa: E402


class FakeMongo:
    def __init__(self, database):
        self.db = AsyncMockDatabase(database)

    def get_forms_collection(self):
        return self.db["forms"]


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
    planner_key = form_service_module.FormService._planner_state_key(created_by)
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


@pytest.mark.asyncio
async def test_duplicate_form_copies_structure_and_resets_submission_state(
    form_service,
):
    service, database = form_service
    planner_email = "planner@example.com"

    database["forms"].insert_one(_sample_form_doc(planner_email))

    request = DuplicateFormRequest(new_name="Vendor Intake Copy")
    result = await service.duplicate_form("form_original", request, planner_email)

    assert "id" in result
    duplicated = database["forms"].find_one({"_id": result["id"]})
    assert duplicated is not None
    assert duplicated["name"] == "Vendor Intake Copy"
    assert duplicated["submission_count"] == 0
    planner_key = form_service_module.FormService._planner_state_key(planner_email)
    assert duplicated["planner_state"][planner_key]["last_viewed_submission_count"] == 0
    assert duplicated["fields"][0]["id"] == "company_name"
    assert duplicated["created_by"] == planner_email


@pytest.mark.asyncio
async def test_mark_form_viewed_updates_planner_state_and_unread_counter(form_service):
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

    forms_before = await service.get_forms(planner_email)
    assert forms_before[0]["unread_responses"] == 3

    result = await service.mark_form_viewed(
        "form_original", planner_email, "responses", submission_count=5
    )
    assert result["unread_responses"] == 0

    stored = database["forms"].find_one({"_id": "form_original"})
    planner_key = form_service_module.FormService._planner_state_key(planner_email)
    assert stored["planner_state"][planner_key]["last_viewed_submission_count"] == 5
    assert stored["planner_state"][planner_key]["last_viewed_responses_at"] is not None

    forms_after = await service.get_forms(planner_email)
    assert forms_after[0]["unread_responses"] == 0


@pytest.mark.asyncio
async def test_mark_form_viewed_rejects_invalid_scope(form_service):
    service, database = form_service
    planner_email = "planner@example.com"

    database["forms"].insert_one(_sample_form_doc(planner_email))

    with pytest.raises(HTTPException) as exc_info:
        await service.mark_form_viewed("form_original", planner_email, "unknown")

    assert exc_info.value.status_code == 400


# =============================================================================
# Items 3, 7, 1 (audit fixes): create-form shape + CSV date filter
# =============================================================================


@pytest.mark.asyncio
async def test_create_form_does_not_double_assign_form_type(form_service):
    """Item 3 audit fix: form_type appears exactly once in the persisted
    document. Previously line 399 wrote a default that line 410 would
    immediately overwrite."""
    from app.models.form import CreateFormRequest, FormSettings

    service, database = form_service
    request = CreateFormRequest(
        name="One-shot",
        settings=FormSettings(
            title="Test",
            description="",
            submit_button_text="Send",
            success_message="Thanks",
            collect_email=True,
            is_public=True,
            requires_auth=False,
        ),
        fields=[],
    )
    result = await service.create_form(request, "planner@example.com")
    stored = database["forms"].find_one({"_id": result["id"]})
    # exactly one form_type key; no template_type leak from the defunct
    # double-assignment.
    assert "form_type" in stored
    assert stored["form_type"] == "general"


@pytest.mark.asyncio
async def test_create_form_does_not_write_legacy_template_type(form_service):
    """Item 7 audit fix: template_type is no longer written on new
    forms. The migration helper still tolerates it for legacy reads."""
    from app.models.form import CreateFormRequest, FormSettings

    service, database = form_service
    await service.create_form(
        CreateFormRequest(
            name="Sans legacy",
            settings=FormSettings(
                title="Test",
                description="",
                submit_button_text="Send",
                success_message="Thanks",
                collect_email=True,
                is_public=True,
                requires_auth=False,
            ),
            fields=[],
        ),
        "planner@example.com",
    )
    forms = list(database["forms"].find({}))
    assert forms
    # Item 7 — legacy field is no longer written; either absent or None.
    assert all(f.get("template_type") in (None, "") for f in forms)


@pytest.mark.asyncio
async def test_csv_export_applies_date_from_to_filter(form_service):
    """Item 1 audit fix (CRITICAL): date_from / date_to actually scope
    the exported dataset. Previously parsed but never applied."""
    from datetime import datetime, timedelta, timezone

    service, database = form_service
    planner_email = "planner@example.com"
    database["forms"].insert_one(_sample_form_doc(planner_email))

    # Three responses across a week.
    base = datetime(2026, 5, 1, tzinfo=timezone.utc)
    for offset, rid in enumerate(["r_old", "r_mid", "r_new"]):
        database["form_responses"].insert_one(
            {
                "_id": rid,
                "form_id": "form_original",
                "responses": {"company_name": rid},
                "submitted_at": base + timedelta(days=offset * 2),
                "submitted_by_email": None,
                "submitted_by_name": None,
            }
        )

    # Window covers only r_mid (May 3) and excludes r_old (May 1) and r_new (May 5).
    result = await service.export_form_responses_csv(
        form_id="form_original",
        created_by=planner_email,
        date_from="2026-05-02",
        date_to="2026-05-04",
    )

    assert result["total_response_count"] == 1
    assert result["truncated"] is False
    assert "r_mid" in result["content"]
    assert "r_old" not in result["content"]
    assert "r_new" not in result["content"]


# =============================================================================
# Codex review P2 (PR #299) follow-up — /forms/from-template path must
# preserve conditional_logic. This is the integration test the
# integration-review agent flagged as missing: a manually-created copy
# of a conditional template (via FormSecurityValidator → create_form,
# which is exactly the code path /forms/from-template hits) needs to
# end up with the same show_when rules as the auto-seeded copy.
# =============================================================================


@pytest.mark.asyncio
async def test_create_form_preserves_conditional_logic_through_validator(form_service):
    """Sends a CreateFormRequest with a conditional rule through the
    full FormService.create_form path (which runs every field through
    FormSecurityValidator.validate_form_field) and reads the persisted
    Mongo doc back to confirm the rule survives."""
    from app.models.form import CreateFormRequest, FormField, FormSettings

    service, database = form_service

    rule = {
        "show_when": {
            "all": [{"field_id": "diet", "operator": "equals", "value": "vegetarian"}]
        }
    }

    request = CreateFormRequest(
        name="With conditional",
        settings=FormSettings(
            title="Vegetarian intake",
            description="",
            submit_button_text="Send",
            success_message="Thanks",
            collect_email=True,
            is_public=True,
            requires_auth=False,
        ),
        fields=[
            FormField(
                id="diet",
                label="Diet",
                type="select",
                required=True,
                options=["omnivore", "vegetarian"],
                order=1,
            ),
            FormField(
                id="veg_kind",
                label="What kind of vegetarian?",
                type="text",
                required=True,
                order=2,
                conditional_logic=rule,
            ),
        ],
    )

    result = await service.create_form(request, "planner@example.com")
    stored = database["forms"].find_one({"_id": result["id"]})

    veg_field = next(f for f in stored["fields"] if f["id"] == "veg_kind")
    assert veg_field.get("conditional_logic") == rule, (
        "FormService.create_form must preserve conditional_logic "
        "through FormSecurityValidator.validate_form_field — "
        "/forms/from-template uses this same path."
    )
    # The non-conditional sibling stays unconditional.
    diet_field = next(f for f in stored["fields"] if f["id"] == "diet")
    assert "conditional_logic" not in diet_field
