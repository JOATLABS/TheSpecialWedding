from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.models.form import CreateFormRequest, FormField, FormSettings
from app.services.form_service import FormService


class FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def sort(self, *_args, **_kwargs):
        return self

    async def to_list(self, length=None):
        return list(self._docs)


@pytest.mark.asyncio
async def test_create_form_preserves_owner_scope_and_actor_email() -> None:
    inserted_docs: list[dict] = []

    class FakeFormsCollection:
        async def insert_one(self, document):
            inserted_docs.append(document.copy())
            return SimpleNamespace(inserted_id=document["_id"])

    service = FormService()
    service.forms_collection = FakeFormsCollection()

    request = CreateFormRequest(
        name="Shared Planning Form",
        settings=FormSettings(title="Shared Planning Form"),
        fields=[FormField(id="name", label="Name", type="text", required=True)],
        wedding_id="wedding-1",
    )

    await service.create_form(
        request,
        "owner@example.com",
        actor_email="team@example.com",
    )

    assert inserted_docs
    assert inserted_docs[0]["created_by"] == "owner@example.com"
    assert inserted_docs[0]["created_by_actor"] == "team@example.com"


@pytest.mark.asyncio
async def test_get_forms_uses_owner_alias_scope_and_viewer_specific_unread_counts() -> (
    None
):
    captured_query: dict[str, object] = {}

    class FakeFormsCollection:
        def find(self, query):
            captured_query.update(query)
            return FakeCursor(
                [
                    {
                        "_id": "form-1",
                        "name": "Shared Planning Form",
                        "is_active": True,
                        "created_by": "owner@example.com",
                        "submission_count": 5,
                        "planner_state": {
                            "team@example_com": {
                                "last_viewed_submission_count": 2,
                            }
                        },
                    }
                ]
            )

    service = FormService()
    service.forms_collection = FakeFormsCollection()

    result = await service.get_forms(
        "owner@example.com",
        viewer_email="team@example.com",
        owner_alias_emails=["owner@example.com", "team@example.com"],
    )

    assert captured_query["created_by"] == {
        "$in": ["owner@example.com", "team@example.com"]
    }
    assert result[0]["unread_responses"] == 3
