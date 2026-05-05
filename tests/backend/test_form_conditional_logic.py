"""Tests for the FormField.conditional_logic runtime evaluator.

Covers:
- Pure evaluator behavior (operators, all/any, malformed-logic fallback).
- Integration with submit_form_response: hidden required fields are not
  enforced, and hidden values are stripped from the persisted response.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import mongomock
import pytest
from fastapi import HTTPException

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("FRONTEND_URL", "https://app.example.com")

from app.utils.form_conditional_logic import (  # noqa: E402
    filter_responses_to_visible,
    is_field_visible,
)
import app.services.form_service as form_service_module  # noqa: E402
from app.models.form import SubmitFormRequest  # noqa: E402


# =============================================================================
# Pure evaluator
# =============================================================================


@pytest.mark.parametrize(
    "field_logic,responses,expected",
    [
        # No logic = always visible
        (None, {}, True),
        ({}, {}, True),
        # show_when.all with one matching equals condition
        (
            {
                "show_when": {
                    "all": [
                        {"field_id": "diet", "operator": "equals", "value": "veg"}
                    ]
                }
            },
            {"diet": "veg"},
            True,
        ),
        # show_when.all condition unmet
        (
            {
                "show_when": {
                    "all": [
                        {"field_id": "diet", "operator": "equals", "value": "veg"}
                    ]
                }
            },
            {"diet": "non-veg"},
            False,
        ),
        # show_when.all with multiple conditions, all true
        (
            {
                "show_when": {
                    "all": [
                        {"field_id": "diet", "operator": "equals", "value": "veg"},
                        {"field_id": "age", "operator": "in", "value": [18, 21]},
                    ]
                }
            },
            {"diet": "veg", "age": 21},
            True,
        ),
        # show_when.all with one condition false
        (
            {
                "show_when": {
                    "all": [
                        {"field_id": "diet", "operator": "equals", "value": "veg"},
                        {"field_id": "age", "operator": "in", "value": [18, 21]},
                    ]
                }
            },
            {"diet": "veg", "age": 30},
            False,
        ),
        # show_when.any: at least one true
        (
            {
                "show_when": {
                    "any": [
                        {"field_id": "a", "operator": "equals", "value": "x"},
                        {"field_id": "b", "operator": "equals", "value": "y"},
                    ]
                }
            },
            {"a": "z", "b": "y"},
            True,
        ),
        # show_when.any: none true
        (
            {
                "show_when": {
                    "any": [
                        {"field_id": "a", "operator": "equals", "value": "x"},
                        {"field_id": "b", "operator": "equals", "value": "y"},
                    ]
                }
            },
            {"a": "z", "b": "z"},
            False,
        ),
        # is_empty / is_not_empty
        (
            {
                "show_when": {
                    "all": [
                        {"field_id": "notes", "operator": "is_not_empty"}
                    ]
                }
            },
            {"notes": "hi"},
            True,
        ),
        (
            {
                "show_when": {
                    "all": [{"field_id": "notes", "operator": "is_empty"}]
                }
            },
            {"notes": ""},
            True,
        ),
        # contains on string
        (
            {
                "show_when": {
                    "all": [
                        {
                            "field_id": "name",
                            "operator": "contains",
                            "value": "smith",
                        }
                    ]
                }
            },
            {"name": "john smith"},
            True,
        ),
        # contains on list
        (
            {
                "show_when": {
                    "all": [
                        {
                            "field_id": "allergies",
                            "operator": "contains",
                            "value": "nuts",
                        }
                    ]
                }
            },
            {"allergies": ["dairy", "nuts"]},
            True,
        ),
        # not_in
        (
            {
                "show_when": {
                    "all": [
                        {
                            "field_id": "size",
                            "operator": "not_in",
                            "value": ["xs", "s"],
                        }
                    ]
                }
            },
            {"size": "m"},
            True,
        ),
        # Unknown operator falls back to visible
        (
            {
                "show_when": {
                    "all": [{"field_id": "x", "operator": "weird", "value": 1}]
                }
            },
            {"x": 1},
            True,
        ),
        # Empty conditions list defaults to visible
        ({"show_when": {"all": []}}, {}, True),
        ({"show_when": {"any": []}}, {}, True),
    ],
)
def test_is_field_visible(field_logic, responses, expected):
    field = {"id": "target", "conditional_logic": field_logic}
    assert is_field_visible(field, responses) is expected


def test_filter_responses_to_visible_drops_hidden_field_values():
    fields = [
        {"id": "diet", "required": True},
        {
            "id": "veg_kind",
            "required": False,
            "conditional_logic": {
                "show_when": {
                    "all": [
                        {"field_id": "diet", "operator": "equals", "value": "veg"}
                    ]
                }
            },
        },
    ]
    responses = {"diet": "non-veg", "veg_kind": "vegan"}
    filtered = filter_responses_to_visible(fields, responses)
    assert filtered == {"diet": "non-veg"}


def test_filter_responses_keeps_unrelated_keys_when_opted_in():
    """``keep_unknown=True`` retains keys that don't match any defined
    field — opt-in for callers that need historical-schema reconstruction.
    Default behavior changed in the Item 5 audit fix: orphan keys are
    dropped unless explicitly preserved."""
    fields = [{"id": "diet", "required": True}]
    responses = {"diet": "veg", "metadata_marker": "x"}
    filtered = filter_responses_to_visible(fields, responses, keep_unknown=True)
    assert filtered == {"diet": "veg", "metadata_marker": "x"}


# =============================================================================
# Submission integration
# =============================================================================


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


def _form_with_conditional(allow_multiple: bool = True) -> Dict[str, Any]:
    return {
        "_id": "form_1",
        "name": "Diet survey",
        "settings": {
            "title": "Diet survey",
            "description": "",
            "submit_button_text": "Submit",
            "success_message": "Thanks!",
            "allow_multiple_submissions": allow_multiple,
            "collect_email": True,
            "is_public": True,
            "requires_auth": False,
        },
        "fields": [
            {
                "id": "diet",
                "label": "Diet",
                "type": "select",
                "required": True,
                "order": 1,
                "options": ["veg", "non-veg"],
            },
            {
                "id": "veg_kind",
                "label": "Vegetarian sub-type",
                "type": "select",
                "required": True,
                "order": 2,
                "options": ["vegan", "lacto", "ovo"],
                "conditional_logic": {
                    "show_when": {
                        "all": [
                            {
                                "field_id": "diet",
                                "operator": "equals",
                                "value": "veg",
                            }
                        ]
                    }
                },
            },
        ],
        "created_by": "planner@example.com",
        "wedding_id": None,
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "submission_count": 0,
        "planner_state": {},
    }


@pytest.fixture
def configured_form_service(monkeypatch):
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

    async def _noop_notify(*args, **kwargs):
        return None

    monkeypatch.setattr(service, "_notify_planner_form_submission", _noop_notify)

    return service, database


@pytest.mark.asyncio
async def test_submit_does_not_require_hidden_field(configured_form_service):
    """A required field hidden by conditional_logic must not block submission."""
    service, database = configured_form_service
    database["forms"].insert_one(_form_with_conditional())

    request = SubmitFormRequest(responses={"diet": "non-veg"})
    result = await service.submit_form_response("form_1", request)

    response = database["form_responses"].find_one({"_id": result["id"]})
    assert response is not None
    assert response["responses"] == {"diet": "non-veg"}


@pytest.mark.asyncio
async def test_submit_strips_hidden_field_values(configured_form_service):
    """Even if a client posts a stale hidden-field value, it is dropped server-side."""
    service, database = configured_form_service
    database["forms"].insert_one(_form_with_conditional())

    request = SubmitFormRequest(
        responses={"diet": "non-veg", "veg_kind": "vegan"}
    )
    result = await service.submit_form_response("form_1", request)

    response = database["form_responses"].find_one({"_id": result["id"]})
    assert "veg_kind" not in response["responses"]
    assert response["responses"]["diet"] == "non-veg"


@pytest.mark.asyncio
async def test_submit_still_requires_visible_required_field(
    configured_form_service,
):
    """When the conditional triggers, the required child field IS enforced."""
    service, database = configured_form_service
    database["forms"].insert_one(_form_with_conditional())

    request = SubmitFormRequest(responses={"diet": "veg"})
    with pytest.raises(HTTPException) as exc_info:
        await service.submit_form_response("form_1", request)
    assert exc_info.value.status_code == 400
    assert "Vegetarian sub-type" in exc_info.value.detail


@pytest.mark.asyncio
async def test_submit_accepts_full_branch_responses(configured_form_service):
    service, database = configured_form_service
    database["forms"].insert_one(_form_with_conditional())

    request = SubmitFormRequest(
        responses={"diet": "veg", "veg_kind": "vegan"}
    )
    result = await service.submit_form_response("form_1", request)

    response = database["form_responses"].find_one({"_id": result["id"]})
    assert response["responses"]["diet"] == "veg"
    assert response["responses"]["veg_kind"] == "vegan"


# =============================================================================
# Item 5 (audit fix): orphan / unknown response keys
# =============================================================================


def test_filter_responses_drops_unknown_keys_by_default():
    """A response key that doesn't match any defined field is dropped by
    default. Catches the case where a planner removes a field after
    responses have been collected — the orphan column no longer pollutes
    CSV exports."""
    fields = [{"id": "diet", "required": True}]
    responses = {"diet": "veg", "ghost_field": "stale_value"}
    out = filter_responses_to_visible(fields, responses)
    assert out == {"diet": "veg"}


def test_filter_responses_keeps_unknown_when_opted_in():
    """``keep_unknown=True`` preserves orphan keys for the rare caller
    that wants the historical-schema reconstruction."""
    fields = [{"id": "diet", "required": True}]
    responses = {"diet": "veg", "ghost_field": "stale_value"}
    out = filter_responses_to_visible(fields, responses, keep_unknown=True)
    assert out == {"diet": "veg", "ghost_field": "stale_value"}
