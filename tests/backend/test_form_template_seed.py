"""Tests for Phase D: catalog auto-seed on planner email verification.

Validates:
- ``FormService.seed_catalog_templates_for_planner`` writes one form
  per catalog template, owned by the planner, marked
  ``seeded_from_catalog=True`` with ``catalog_template_id``.
- Idempotent: a second call adds zero new forms.
- Owner-scoped: a different planner's seeds don't conflict.
- Resilient: a malformed template entry is skipped, never raises.
- Each seeded form's fields parse through ``FormField`` (same Pydantic
  v2 contract the runtime uses), per the validation rules confirmed
  against the Pydantic v2 docs at
  https://pydantic.dev/docs/validation/latest/concepts/validators/.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import mongomock
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("FRONTEND_URL", "https://app.example.com")

import app.services.form_service as form_service_module  # noqa: E402
from app.models.form import FormField  # noqa: E402
from app.services.form_template_catalog import FORM_TEMPLATES  # noqa: E402


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

    async def update_many(self, *args, **kwargs):
        return self.collection.update_many(*args, **kwargs)

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


@pytest.fixture
def configured_form_service(monkeypatch):
    client = mongomock.MongoClient()
    database = client["wedding_forms"]
    fake_mongo = FakeMongo(database)
    monkeypatch.setattr(form_service_module, "mongo", fake_mongo)
    monkeypatch.setattr(
        form_service_module.rate_limiter,
        "check_rate_limit",
        lambda *a, **kw: True,
    )
    service = form_service_module.FormService()
    return service, database


# =============================================================================
# Happy path
# =============================================================================


@pytest.mark.asyncio
async def test_seed_writes_one_form_per_catalog_template(
    configured_form_service,
):
    service, database = configured_form_service

    result = await service.seed_catalog_templates_for_planner(
        "planner@example.com"
    )

    assert result["seeded"] == len(FORM_TEMPLATES)
    assert result["skipped"] == 0
    assert result["total"] == len(FORM_TEMPLATES)

    forms = list(database["forms"].find({"created_by": "planner@example.com"}))
    assert len(forms) == len(FORM_TEMPLATES)


@pytest.mark.asyncio
async def test_seed_marks_each_form_with_catalog_provenance(
    configured_form_service,
):
    service, database = configured_form_service

    await service.seed_catalog_templates_for_planner("planner@example.com")

    forms = list(database["forms"].find({"created_by": "planner@example.com"}))
    for form in forms:
        assert form.get("seeded_from_catalog") is True
        assert form.get("catalog_template_id") in {t["id"] for t in FORM_TEMPLATES}
        assert form.get("catalog_seeded_at") is not None
        assert form["created_by"] == "planner@example.com"
        assert form["is_active"] is True
        assert form["submission_count"] == 0


@pytest.mark.asyncio
async def test_seed_uses_hashed_planner_state_key(configured_form_service):
    """F6 hardening: planner_state must be keyed by the SHA256 hash, not the
    legacy email-with-dots-replaced shape."""
    service, database = configured_form_service

    await service.seed_catalog_templates_for_planner("alice.smith@example.com")

    expected_key = service._planner_state_key("alice.smith@example.com")
    forms = list(
        database["forms"].find({"created_by": "alice.smith@example.com"})
    )
    for form in forms:
        assert expected_key in form["planner_state"]


# =============================================================================
# Idempotence
# =============================================================================


@pytest.mark.asyncio
async def test_seed_is_idempotent_on_repeat_call(configured_form_service):
    """Re-running the seeder for the same planner adds zero new forms.

    This is what makes it safe to call from verify_email even if the
    verification link gets clicked twice."""
    service, database = configured_form_service

    first = await service.seed_catalog_templates_for_planner(
        "planner@example.com"
    )
    second = await service.seed_catalog_templates_for_planner(
        "planner@example.com"
    )

    assert first["seeded"] == len(FORM_TEMPLATES)
    assert second["seeded"] == 0
    assert second["skipped"] == len(FORM_TEMPLATES)

    # No duplicates in Mongo
    forms = list(database["forms"].find({"created_by": "planner@example.com"}))
    assert len(forms) == len(FORM_TEMPLATES)


@pytest.mark.asyncio
async def test_seed_is_owner_scoped(configured_form_service):
    """Two different planners both get the full catalog; their seeds do not
    interact (the idempotence check is per-planner, not global)."""
    service, database = configured_form_service

    await service.seed_catalog_templates_for_planner("alice@example.com")
    await service.seed_catalog_templates_for_planner("bob@example.com")

    alice_forms = list(database["forms"].find({"created_by": "alice@example.com"}))
    bob_forms = list(database["forms"].find({"created_by": "bob@example.com"}))
    assert len(alice_forms) == len(FORM_TEMPLATES)
    assert len(bob_forms) == len(FORM_TEMPLATES)
    assert {f["catalog_template_id"] for f in alice_forms} == {
        t["id"] for t in FORM_TEMPLATES
    }


@pytest.mark.asyncio
async def test_seed_does_not_count_planner_authored_forms_as_seeded(
    configured_form_service,
):
    """A planner-created form (no seeded_from_catalog flag) sharing a name
    with a catalog template should NOT make the seeder skip its
    catalog twin."""
    service, database = configured_form_service

    # Planner manually created a form before catalog seed ran.
    database["forms"].insert_one(
        {
            "_id": "form_manual_1",
            "name": "Couple Intake Questionnaire",  # collides on name only
            "settings": {},
            "fields": [],
            "created_by": "planner@example.com",
            "is_active": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "submission_count": 0,
            "planner_state": {},
            # Crucially, no seeded_from_catalog / catalog_template_id flags.
        }
    )

    result = await service.seed_catalog_templates_for_planner(
        "planner@example.com"
    )
    # All catalog templates seeded — the manual form was unrelated.
    assert result["seeded"] == len(FORM_TEMPLATES)


# =============================================================================
# Edge cases / resilience
# =============================================================================


@pytest.mark.asyncio
async def test_seed_returns_zero_for_missing_email(configured_form_service):
    service, database = configured_form_service

    for bad_email in (None, "", "   "):
        result = await service.seed_catalog_templates_for_planner(bad_email)
        assert result == {"seeded": 0, "skipped": 0, "total": 0}

    assert database["forms"].count_documents({}) == 0


@pytest.mark.asyncio
async def test_seed_normalizes_email_case_and_whitespace(
    configured_form_service,
):
    service, database = configured_form_service

    await service.seed_catalog_templates_for_planner("  Alice@Example.COM  ")

    # Every seeded form is owned by the lowercased / stripped email.
    forms = list(database["forms"].find({"created_by": "alice@example.com"}))
    assert len(forms) == len(FORM_TEMPLATES)

    # Re-running with the *normalized* form is still idempotent.
    second = await service.seed_catalog_templates_for_planner(
        "alice@example.com"
    )
    assert second["seeded"] == 0


@pytest.mark.asyncio
async def test_seeded_form_fields_pass_form_field_validator(
    configured_form_service,
):
    """Every persisted field must round-trip through FormField — the same
    Pydantic v2 model the runtime uses on submission. This protects
    against any accidental schema drift between catalog and stored
    forms."""
    service, database = configured_form_service

    await service.seed_catalog_templates_for_planner("planner@example.com")

    forms = list(database["forms"].find({"created_by": "planner@example.com"}))
    for form in forms:
        for field in form["fields"]:
            FormField.model_validate(field)


@pytest.mark.asyncio
async def test_seed_skips_template_with_invalid_fields(
    configured_form_service, monkeypatch
):
    """A corrupt catalog entry is logged and skipped, never raises.

    This isolation matters: a future bad entry should not block account
    verification for everyone."""
    service, database = configured_form_service

    bad_template = {
        "id": "intentionally_bad",
        "name": "Bad",
        "description": "",
        "category": "intake",
        "fields": [
            # Missing required ``id``, ``label``, ``type`` — the FormField
            # validator will reject this entire field, and the seeder
            # should skip the whole template.
            {"required": True, "order": 1},
        ],
    }
    monkeypatch.setattr(
        "app.services.form_service.FORM_TEMPLATES",
        [bad_template],
        raising=False,
    )
    # Patch the import inside the seeder body so we exercise the bad entry.
    monkeypatch.setattr(
        "app.services.form_template_catalog.FORM_TEMPLATES",
        [bad_template],
        raising=True,
    )

    result = await service.seed_catalog_templates_for_planner(
        "planner@example.com"
    )
    assert result["seeded"] == 0
    assert result["skipped"] == 1
    assert database["forms"].count_documents({}) == 0
