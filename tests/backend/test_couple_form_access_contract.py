from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.api import couple_portal as couple_portal_api


class FakeFormsCollection:
    def __init__(self, documents: list[dict]):
        self.documents = documents

    @staticmethod
    def _matches(document: dict, query: dict) -> bool:
        for key, value in query.items():
            if key == "$or":
                if not any(
                    FakeFormsCollection._matches(document, clause) for clause in value
                ):
                    return False
                continue

            document_value = document.get(key)
            if document_value != value:
                return False

        return True

    async def find_one(self, query, projection=None):
        for document in self.documents:
            if self._matches(document, query):
                return document.copy()
        return None


class FakeFormSubmissionsCollection:
    def __init__(self):
        self.documents: list[dict] = []

    async def find_one(self, query):
        for document in self.documents:
            if all(document.get(key) == value for key, value in query.items()):
                return document.copy()
        return None

    async def insert_one(self, document):
        stored = document.copy()
        stored["_id"] = "submission-1"
        self.documents.append(stored)
        return SimpleNamespace(inserted_id="submission-1")

    async def update_one(self, query, update):
        for document in self.documents:
            if all(document.get(key) == value for key, value in query.items()):
                for key, value in update.get("$set", {}).items():
                    document[key] = value
                return SimpleNamespace(modified_count=1)
        return SimpleNamespace(modified_count=0)


def _fake_mongo(forms: list[dict]):
    return SimpleNamespace(
        db={
            "forms": FakeFormsCollection(forms),
            "form_submissions": FakeFormSubmissionsCollection(),
        }
    )


def _sample_couple() -> dict:
    return {
        "_id": "couple-1",
        "email": "couple@example.com",
        "partner1_name": "Alex",
        "partner2_name": "Jordan",
        "wedding_id": "wedding-1",
    }


def _sample_form(**overrides) -> dict:
    base = {
        "_id": couple_portal_api.ObjectId("507f1f77bcf86cd799439011"),
        "wedding_id": "wedding-1",
        "title": "Planner Intake",
        "description": "Tell us more",
        "fields": [{"id": "favorite-song", "label": "Favorite song", "type": "text"}],
        "created_at": datetime.now(timezone.utc),
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_get_form_details_rejects_unshared_form(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(couple_portal_api, "mongo", _fake_mongo([_sample_form()]))

    with pytest.raises(HTTPException) as exc_info:
        await couple_portal_api.get_form_details(
            "507f1f77bcf86cd799439011",
            couple=_sample_couple(),
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Form not found or not shared with you"


@pytest.mark.asyncio
async def test_submit_form_rejects_unshared_form(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(couple_portal_api, "mongo", _fake_mongo([_sample_form()]))

    with pytest.raises(HTTPException) as exc_info:
        await couple_portal_api.submit_form(
            couple_portal_api.FormSubmissionRequest(
                form_id="507f1f77bcf86cd799439011",
                responses={"favorite-song": "At Last"},
            ),
            couple=_sample_couple(),
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Form not found or not shared with you"


@pytest.mark.asyncio
async def test_get_form_details_allows_shared_form(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        couple_portal_api,
        "mongo",
        _fake_mongo([_sample_form(shared_with_couple=True)]),
    )

    result = await couple_portal_api.get_form_details(
        "507f1f77bcf86cd799439011",
        couple=_sample_couple(),
    )

    assert result["form"]["title"] == "Planner Intake"
    assert result["existing_responses"] is None


@pytest.mark.asyncio
async def test_submit_form_allows_shared_form(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        couple_portal_api,
        "mongo",
        _fake_mongo([_sample_form(target_audience="couple")]),
    )
    monkeypatch.setattr(
        couple_portal_api,
        "_resolve_couple_planner_email",
        AsyncMock(return_value=None),
    )

    result = await couple_portal_api.submit_form(
        couple_portal_api.FormSubmissionRequest(
            form_id="507f1f77bcf86cd799439011",
            responses={"favorite-song": "At Last"},
        ),
        couple=_sample_couple(),
    )

    assert result["submission_id"] == "submission-1"


@pytest.mark.asyncio
async def test_get_form_details_rejects_invalid_form_id() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await couple_portal_api.get_form_details(
            "not-a-valid-object-id",
            couple=_sample_couple(),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid form ID format"


@pytest.mark.asyncio
async def test_submit_form_rejects_invalid_form_id() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await couple_portal_api.submit_form(
            couple_portal_api.FormSubmissionRequest(
                form_id="not-a-valid-object-id",
                responses={"favorite-song": "At Last"},
            ),
            couple=_sample_couple(),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid form ID format"
