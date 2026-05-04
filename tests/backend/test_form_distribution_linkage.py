"""Tests for FormResponse <-> FormDistribution linkage (Item 3).

Item 3 of the forms gap-closure plan: every per-recipient email send
emits a URL containing ``?dist={distribution_id}``; submissions persist
the resolved distribution_id on FormResponse and use it (in preference
to email-match) to mark the matching FormDistribution as submitted.

This file also covers the new ``GET /forms/{id}/distributions`` listing
that powers the planner's "who has not responded" surface.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
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

import app.services.form_service as form_service_module  # noqa: E402
from app.models.form import (  # noqa: E402
    EmailDistributionSettings,
    SendFormRequest,
    SubmitFormRequest,
)


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


class StubEmailService:
    def __init__(self) -> None:
        self.configured = True
        self.sent: list[Dict[str, Any]] = []

    async def send_email(self, **kwargs) -> Dict[str, Any]:
        self.sent.append(kwargs)
        return {"success": True, "email_id": f"email_{len(self.sent)}"}


def _form_doc(
    *,
    form_id: str = "form_1",
    created_by: str = "planner@example.com",
    allow_multiple_submissions: bool = True,
) -> Dict[str, Any]:
    return {
        "_id": form_id,
        "name": "Guest RSVP",
        "settings": {
            "title": "Guest RSVP",
            "description": "Let us know",
            "submit_button_text": "Submit",
            "success_message": "Thanks!",
            "allow_multiple_submissions": allow_multiple_submissions,
            "collect_email": True,
            "is_public": True,
            "requires_auth": False,
        },
        "fields": [
            {
                "id": "name",
                "label": "Name",
                "type": "text",
                "required": True,
                "order": 1,
            }
        ],
        "created_by": created_by,
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
    service.email_service = StubEmailService()

    async def _noop_notify(*args, **kwargs):
        return None

    monkeypatch.setattr(service, "_notify_planner_form_submission", _noop_notify)

    return service, database


# =============================================================================
# Submission linkage
# =============================================================================


@pytest.mark.asyncio
async def test_submit_with_valid_distribution_id_persists_linkage(
    configured_form_service,
):
    service, database = configured_form_service
    database["forms"].insert_one(_form_doc())
    database["form_distributions"].insert_one(
        {
            "_id": "dist-1",
            "form_id": "form_1",
            "recipient_email": "guest@example.com",
            "sent_at": datetime.utcnow(),
            "status": "sent",
        }
    )

    request = SubmitFormRequest(
        responses={"name": "Jamie"},
        submitted_by_email="guest@example.com",
        distribution_id="dist-1",
    )
    result = await service.submit_form_response("form_1", request)

    response = database["form_responses"].find_one({"_id": result["id"]})
    assert response["distribution_id"] == "dist-1"

    distribution = database["form_distributions"].find_one({"_id": "dist-1"})
    assert distribution["status"] == "submitted"
    assert distribution["submitted_at"] is not None


@pytest.mark.asyncio
async def test_submit_with_distribution_id_marks_correct_distribution_when_email_matches_multiple(
    configured_form_service,
):
    """The dist_id is more reliable than email when one address gets multiple sends."""
    service, database = configured_form_service
    database["forms"].insert_one(_form_doc())
    now = datetime.utcnow()
    database["form_distributions"].insert_many(
        [
            {
                "_id": "dist-old",
                "form_id": "form_1",
                "recipient_email": "guest@example.com",
                "sent_at": now,
                "status": "sent",
            },
            {
                "_id": "dist-new",
                "form_id": "form_1",
                "recipient_email": "guest@example.com",
                "sent_at": now,
                "status": "sent",
            },
        ]
    )

    request = SubmitFormRequest(
        responses={"name": "Jamie"},
        submitted_by_email="guest@example.com",
        distribution_id="dist-new",
    )
    await service.submit_form_response("form_1", request)

    new_dist = database["form_distributions"].find_one({"_id": "dist-new"})
    old_dist = database["form_distributions"].find_one({"_id": "dist-old"})
    assert new_dist["status"] == "submitted"
    assert old_dist["status"] == "sent"  # Untouched


@pytest.mark.asyncio
async def test_submit_with_unknown_distribution_id_drops_it_and_falls_back_to_email(
    configured_form_service,
):
    service, database = configured_form_service
    database["forms"].insert_one(_form_doc())
    database["form_distributions"].insert_one(
        {
            "_id": "real-dist",
            "form_id": "form_1",
            "recipient_email": "guest@example.com",
            "sent_at": datetime.utcnow(),
            "status": "sent",
        }
    )

    request = SubmitFormRequest(
        responses={"name": "Jamie"},
        submitted_by_email="guest@example.com",
        distribution_id="not-a-real-id",
    )
    result = await service.submit_form_response("form_1", request)

    response = database["form_responses"].find_one({"_id": result["id"]})
    assert response["distribution_id"] is None  # Bogus id silently dropped

    # Email-match fallback still marked the real distribution
    real = database["form_distributions"].find_one({"_id": "real-dist"})
    assert real["status"] == "submitted"


@pytest.mark.asyncio
async def test_submit_with_distribution_id_for_other_form_is_dropped(
    configured_form_service,
):
    """Cross-form distribution_id replay must not link a submission to the wrong form."""
    service, database = configured_form_service
    database["forms"].insert_many([_form_doc(form_id="form_1"), _form_doc(form_id="form_2")])
    database["form_distributions"].insert_one(
        {
            "_id": "dist-other-form",
            "form_id": "form_2",  # Note: not form_1
            "recipient_email": "guest@example.com",
            "sent_at": datetime.utcnow(),
            "status": "sent",
        }
    )

    request = SubmitFormRequest(
        responses={"name": "Jamie"},
        submitted_by_email="guest@example.com",
        distribution_id="dist-other-form",
    )
    result = await service.submit_form_response("form_1", request)

    response = database["form_responses"].find_one({"_id": result["id"]})
    assert response["distribution_id"] is None  # Cross-form id rejected

    # form_2's distribution must remain untouched
    other = database["form_distributions"].find_one({"_id": "dist-other-form"})
    assert other["status"] == "sent"


@pytest.mark.asyncio
async def test_submit_without_distribution_id_falls_back_to_email_match(
    configured_form_service,
):
    """Legacy flow (no per-recipient link) keeps working via email-match."""
    service, database = configured_form_service
    database["forms"].insert_one(_form_doc())
    database["form_distributions"].insert_one(
        {
            "_id": "dist-1",
            "form_id": "form_1",
            "recipient_email": "guest@example.com",
            "sent_at": datetime.utcnow(),
            "status": "sent",
        }
    )

    request = SubmitFormRequest(
        responses={"name": "Jamie"},
        submitted_by_email="guest@example.com",
    )
    result = await service.submit_form_response("form_1", request)

    response = database["form_responses"].find_one({"_id": result["id"]})
    assert response["distribution_id"] is None

    distribution = database["form_distributions"].find_one({"_id": "dist-1"})
    assert distribution["status"] == "submitted"


@pytest.mark.asyncio
async def test_submit_anonymous_with_distribution_id_links_without_email(
    configured_form_service,
):
    """Anonymous tokenized submissions still produce reliable linkage."""
    service, database = configured_form_service
    database["forms"].insert_one(_form_doc())
    database["form_distributions"].insert_one(
        {
            "_id": "dist-anon",
            "form_id": "form_1",
            "recipient_email": "guest@example.com",
            "sent_at": datetime.utcnow(),
            "status": "sent",
        }
    )

    request = SubmitFormRequest(
        responses={"name": "Anonymous Jamie"},
        distribution_id="dist-anon",
    )
    result = await service.submit_form_response("form_1", request)

    response = database["form_responses"].find_one({"_id": result["id"]})
    assert response["distribution_id"] == "dist-anon"
    assert response["submitted_by_email"] is None

    distribution = database["form_distributions"].find_one({"_id": "dist-anon"})
    assert distribution["status"] == "submitted"


# =============================================================================
# Send: per-recipient URL carries ?dist=
# =============================================================================


@pytest.mark.asyncio
async def test_send_form_email_url_carries_distribution_id(configured_form_service):
    service, database = configured_form_service
    database["forms"].insert_one(_form_doc())

    request = SendFormRequest(
        recipient_emails=["a@example.com", "b@example.com"],
        email_settings=EmailDistributionSettings(
            subject="Please respond",
            message="Hi",
            sender_name="Wedding Planner",
        ),
    )
    await service.send_form("form_1", request, "planner@example.com")

    distributions = list(database["form_distributions"].find({"form_id": "form_1"}))
    assert len(distributions) == 2

    # Each recipient's email body should include ?dist=<their distribution id>
    for sent in service.email_service.sent:
        html = sent["html_content"]
        recipient = sent["to_email"]
        their_dist = next(
            d for d in distributions if d["recipient_email"] == recipient
        )
        assert f"?dist={their_dist['_id']}" in html


# =============================================================================
# Distributions listing endpoint
# =============================================================================


@pytest.mark.asyncio
async def test_get_form_distributions_returns_all_for_owned_form(
    configured_form_service,
):
    service, database = configured_form_service
    database["forms"].insert_one(_form_doc())
    now = datetime.utcnow()
    database["form_distributions"].insert_many(
        [
            {
                "_id": "d1",
                "form_id": "form_1",
                "recipient_email": "a@example.com",
                "sent_at": now,
                "status": "sent",
            },
            {
                "_id": "d2",
                "form_id": "form_1",
                "recipient_email": "b@example.com",
                "sent_at": now,
                "status": "submitted",
            },
            {
                "_id": "d3",
                "form_id": "other_form",
                "recipient_email": "c@example.com",
                "sent_at": now,
                "status": "sent",
            },
        ]
    )

    result = await service.get_form_distributions("form_1", "planner@example.com")
    ids = sorted(d["id"] for d in result)
    assert ids == ["d1", "d2"]


@pytest.mark.asyncio
async def test_get_form_distributions_filters_by_status(configured_form_service):
    service, database = configured_form_service
    database["forms"].insert_one(_form_doc())
    now = datetime.utcnow()
    database["form_distributions"].insert_many(
        [
            {
                "_id": "d1",
                "form_id": "form_1",
                "recipient_email": "a@example.com",
                "sent_at": now,
                "status": "sent",
            },
            {
                "_id": "d2",
                "form_id": "form_1",
                "recipient_email": "b@example.com",
                "sent_at": now,
                "status": "submitted",
            },
        ]
    )

    result = await service.get_form_distributions(
        "form_1", "planner@example.com", status="sent"
    )
    assert [d["id"] for d in result] == ["d1"]


@pytest.mark.asyncio
async def test_get_form_distributions_rejects_invalid_status(configured_form_service):
    service, database = configured_form_service
    database["forms"].insert_one(_form_doc())

    with pytest.raises(HTTPException) as exc_info:
        await service.get_form_distributions(
            "form_1", "planner@example.com", status="not-a-status"
        )

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_get_form_distributions_rejects_non_owner(configured_form_service):
    service, database = configured_form_service
    database["forms"].insert_one(_form_doc(created_by="owner@example.com"))

    with pytest.raises(HTTPException):
        await service.get_form_distributions("form_1", "intruder@example.com")


# =============================================================================
# Per-recipient access tokens (Item 4)
# =============================================================================


@pytest.mark.asyncio
async def test_send_form_issues_unique_token_and_url_carries_it(
    configured_form_service,
):
    service, database = configured_form_service
    database["forms"].insert_one(_form_doc())

    request = SendFormRequest(
        recipient_emails=["a@example.com", "b@example.com"],
        email_settings=EmailDistributionSettings(
            subject="Please respond",
            message="Hi",
            sender_name="Wedding Planner",
        ),
    )
    await service.send_form("form_1", request, "planner@example.com")

    distributions = list(database["form_distributions"].find({"form_id": "form_1"}))
    assert len(distributions) == 2

    hashes = {d["access_token_hash"] for d in distributions}
    assert None not in hashes  # both got a hash
    assert len(hashes) == 2  # tokens are distinct
    for d in distributions:
        assert d["token_expires_at"] is not None

    for sent in service.email_service.sent:
        html = sent["html_content"]
        assert "?dist=" in html
        assert "&t=" in html


@pytest.mark.asyncio
async def test_submit_with_valid_token_succeeds_and_marks_submitted(
    configured_form_service,
):
    service, database = configured_form_service
    database["forms"].insert_one(_form_doc())
    raw_token = "tok-1234"
    database["form_distributions"].insert_one(
        {
            "_id": "dist-1",
            "form_id": "form_1",
            "recipient_email": "guest@example.com",
            "sent_at": datetime.utcnow(),
            "status": "sent",
            "access_token_hash": service._hash_form_access_token(raw_token),
            "token_expires_at": datetime.now(timezone.utc) + timedelta(days=10),
        }
    )

    request = SubmitFormRequest(
        responses={"name": "Jamie"},
        distribution_id="dist-1",
        access_token=raw_token,
    )
    await service.submit_form_response("form_1", request)

    dist = database["form_distributions"].find_one({"_id": "dist-1"})
    assert dist["status"] == "submitted"
    assert dist["submitted_at"] is not None


@pytest.mark.asyncio
async def test_submit_with_wrong_token_returns_403(configured_form_service):
    service, database = configured_form_service
    database["forms"].insert_one(_form_doc())
    real_token = "real-token"
    database["form_distributions"].insert_one(
        {
            "_id": "dist-1",
            "form_id": "form_1",
            "recipient_email": "guest@example.com",
            "sent_at": datetime.utcnow(),
            "status": "sent",
            "access_token_hash": service._hash_form_access_token(real_token),
            "token_expires_at": datetime.now(timezone.utc) + timedelta(days=10),
        }
    )

    request = SubmitFormRequest(
        responses={"name": "Jamie"},
        distribution_id="dist-1",
        access_token="forged-token",
    )
    with pytest.raises(HTTPException) as exc_info:
        await service.submit_form_response("form_1", request)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_submit_with_expired_token_returns_410(configured_form_service):
    service, database = configured_form_service
    database["forms"].insert_one(_form_doc())
    raw_token = "expired-token"
    database["form_distributions"].insert_one(
        {
            "_id": "dist-1",
            "form_id": "form_1",
            "recipient_email": "guest@example.com",
            "sent_at": datetime.utcnow(),
            "status": "sent",
            "access_token_hash": service._hash_form_access_token(raw_token),
            "token_expires_at": datetime.now(timezone.utc) - timedelta(days=1),
        }
    )

    request = SubmitFormRequest(
        responses={"name": "Jamie"},
        distribution_id="dist-1",
        access_token=raw_token,
    )
    with pytest.raises(HTTPException) as exc_info:
        await service.submit_form_response("form_1", request)
    assert exc_info.value.status_code == 410


@pytest.mark.asyncio
async def test_submit_token_enforces_single_submission_even_with_multiple_allowed(
    configured_form_service,
):
    """Tokenized links are one-shot per distribution, regardless of form-level setting."""
    service, database = configured_form_service
    # allow_multiple_submissions=True at the form level on purpose
    database["forms"].insert_one(_form_doc(allow_multiple_submissions=True))
    raw_token = "tok-once"
    database["form_distributions"].insert_one(
        {
            "_id": "dist-1",
            "form_id": "form_1",
            "recipient_email": "guest@example.com",
            "sent_at": datetime.utcnow(),
            "status": "submitted",  # already submitted
            "submitted_at": datetime.utcnow(),
            "access_token_hash": service._hash_form_access_token(raw_token),
            "token_expires_at": datetime.now(timezone.utc) + timedelta(days=10),
        }
    )

    request = SubmitFormRequest(
        responses={"name": "Second attempt"},
        distribution_id="dist-1",
        access_token=raw_token,
    )
    with pytest.raises(HTTPException) as exc_info:
        await service.submit_form_response("form_1", request)
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_submit_with_token_for_unknown_distribution_returns_403(
    configured_form_service,
):
    service, database = configured_form_service
    database["forms"].insert_one(_form_doc())

    request = SubmitFormRequest(
        responses={"name": "Forged"},
        distribution_id="not-a-real-id",
        access_token="some-token",
    )
    with pytest.raises(HTTPException) as exc_info:
        await service.submit_form_response("form_1", request)
    assert exc_info.value.status_code == 403


# Token-less submissions still fall through cleanly even when distribution exists
@pytest.mark.asyncio
async def test_submit_without_token_when_distribution_has_token_still_works_via_email(
    configured_form_service,
):
    """Forwards-compat: a recipient who manually pastes /forms/{id} (stripped link)
    can still submit; without a token, no per-distribution enforcement applies."""
    service, database = configured_form_service
    database["forms"].insert_one(_form_doc(allow_multiple_submissions=True))
    raw_token = "tok-1"
    database["form_distributions"].insert_one(
        {
            "_id": "dist-1",
            "form_id": "form_1",
            "recipient_email": "guest@example.com",
            "sent_at": datetime.utcnow(),
            "status": "sent",
            "access_token_hash": service._hash_form_access_token(raw_token),
            "token_expires_at": datetime.now(timezone.utc) + timedelta(days=10),
        }
    )

    request = SubmitFormRequest(
        responses={"name": "Jamie"},
        submitted_by_email="guest@example.com",
        # No distribution_id, no access_token
    )
    result = await service.submit_form_response("form_1", request)
    assert "id" in result
    dist = database["form_distributions"].find_one({"_id": "dist-1"})
    assert dist["status"] == "submitted"  # email-match fallback


# =============================================================================
# check_form_distribution_link
# =============================================================================


@pytest.mark.asyncio
async def test_check_link_returns_valid_for_unused_token(configured_form_service):
    service, database = configured_form_service
    raw_token = "ok-tok"
    database["form_distributions"].insert_one(
        {
            "_id": "dist-1",
            "form_id": "form_1",
            "recipient_email": "guest@example.com",
            "recipient_name": "Jamie",
            "sent_at": datetime.utcnow(),
            "status": "sent",
            "access_token_hash": service._hash_form_access_token(raw_token),
            "token_expires_at": datetime.now(timezone.utc) + timedelta(days=10),
        }
    )

    result = await service.check_form_distribution_link("form_1", "dist-1", raw_token)
    assert result["valid"] is True
    assert result["expired"] is False
    assert result["already_submitted"] is False
    assert result["recipient_name"] == "Jamie"

    # First valid check stamps clicked_at
    dist = database["form_distributions"].find_one({"_id": "dist-1"})
    assert dist["clicked_at"] is not None
    assert dist["status"] == "clicked"


@pytest.mark.asyncio
async def test_check_link_returns_expired(configured_form_service):
    service, database = configured_form_service
    raw_token = "expired"
    database["form_distributions"].insert_one(
        {
            "_id": "dist-1",
            "form_id": "form_1",
            "recipient_email": "guest@example.com",
            "sent_at": datetime.utcnow(),
            "status": "sent",
            "access_token_hash": service._hash_form_access_token(raw_token),
            "token_expires_at": datetime.now(timezone.utc) - timedelta(days=1),
        }
    )

    result = await service.check_form_distribution_link("form_1", "dist-1", raw_token)
    assert result["valid"] is False
    assert result["expired"] is True


@pytest.mark.asyncio
async def test_check_link_returns_already_submitted(configured_form_service):
    service, database = configured_form_service
    raw_token = "tok"
    database["form_distributions"].insert_one(
        {
            "_id": "dist-1",
            "form_id": "form_1",
            "recipient_email": "guest@example.com",
            "sent_at": datetime.utcnow(),
            "submitted_at": datetime.utcnow(),
            "status": "submitted",
            "access_token_hash": service._hash_form_access_token(raw_token),
            "token_expires_at": datetime.now(timezone.utc) + timedelta(days=10),
        }
    )

    result = await service.check_form_distribution_link("form_1", "dist-1", raw_token)
    assert result["valid"] is False
    assert result["already_submitted"] is True


@pytest.mark.asyncio
async def test_check_link_returns_404_for_wrong_token(configured_form_service):
    service, database = configured_form_service
    real_token = "real-token"
    database["form_distributions"].insert_one(
        {
            "_id": "dist-1",
            "form_id": "form_1",
            "recipient_email": "guest@example.com",
            "sent_at": datetime.utcnow(),
            "status": "sent",
            "access_token_hash": service._hash_form_access_token(real_token),
            "token_expires_at": datetime.now(timezone.utc) + timedelta(days=10),
        }
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.check_form_distribution_link("form_1", "dist-1", "forged")
    assert exc_info.value.status_code == 404  # Indistinguishable from "missing"


@pytest.mark.asyncio
async def test_check_link_returns_404_for_unknown_distribution(
    configured_form_service,
):
    service, database = configured_form_service
    with pytest.raises(HTTPException) as exc_info:
        await service.check_form_distribution_link("form_1", "missing", "anything")
    assert exc_info.value.status_code == 404


# =============================================================================
# Hardening sweep: F8 (status enum) + F9 (CSV truncation surface)
# =============================================================================


@pytest.mark.asyncio
async def test_get_form_distributions_rejects_unknown_status_filter(
    configured_form_service,
):
    """F8: status filter is sourced from FormDistributionStatus, not a free-form set."""
    service, database = configured_form_service
    database["forms"].insert_one(_form_doc())

    with pytest.raises(HTTPException) as exc_info:
        await service.get_form_distributions(
            "form_1", "planner@example.com", status="totally-bogus"
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_get_form_distributions_accepts_each_canonical_status(
    configured_form_service,
):
    """F8: every FormDistributionStatus value is a valid filter."""
    from app.models.form import FormDistributionStatus

    service, database = configured_form_service
    database["forms"].insert_one(_form_doc())

    for status in FormDistributionStatus:
        # Should not raise; empty result is fine.
        result = await service.get_form_distributions(
            "form_1", "planner@example.com", status=status.value
        )
        assert isinstance(result, list)


@pytest.mark.asyncio
async def test_send_form_writes_canonical_status_strings(configured_form_service):
    """F8: send_form populates only valid enum values, not free-form strings."""
    from app.models.form import FormDistributionStatus

    service, database = configured_form_service
    database["forms"].insert_one(_form_doc())

    request = SendFormRequest(
        recipient_emails=["a@example.com", "b@example.com"],
        email_settings=EmailDistributionSettings(
            subject="Please respond",
            message="Hi",
            sender_name="Wedding Planner",
        ),
    )
    await service.send_form("form_1", request, "planner@example.com")

    valid = {s.value for s in FormDistributionStatus}
    for dist in database["form_distributions"].find({"form_id": "form_1"}):
        assert dist["status"] in valid
