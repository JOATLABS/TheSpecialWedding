import asyncio
import copy
import os
import sys
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, Response
from starlette.requests import Request

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import app.api.couple_auth as couple_auth_module  # noqa: E402
import app.dependencies.couple_auth as couple_auth_dependency  # noqa: E402
from app.utils.auth_utils import verify_token  # noqa: E402


class FakeCursor:
    def __init__(self, documents: list[dict]):
        self.documents = [copy.deepcopy(document) for document in documents]

    async def to_list(self, length=None):
        if length is None:
            return [copy.deepcopy(document) for document in self.documents]
        return [copy.deepcopy(document) for document in self.documents[:length]]


class FakeCoupleUsersCollection:
    def __init__(self, documents: list[dict]):
        self.documents = [copy.deepcopy(document) for document in documents]
        self.update_calls: list[tuple[dict, dict]] = []

    def _matches(self, document: dict, query: dict) -> bool:
        for key, value in query.items():
            document_value = document.get(key)
            if isinstance(value, dict):
                if "$gt" in value and not (
                    document_value and document_value > value["$gt"]
                ):
                    return False
                if "$in" in value and document_value not in value["$in"]:
                    return False
                continue
            if document_value != value:
                return False
        return True

    async def find_one(self, query, projection=None):
        for document in self.documents:
            if self._matches(document, query):
                return copy.deepcopy(document)
        return None

    def find(self, query, projection=None):
        matches = [
            copy.deepcopy(document)
            for document in self.documents
            if self._matches(document, query)
        ]
        return FakeCursor(matches)

    async def update_one(self, query, update):
        self.update_calls.append((copy.deepcopy(query), copy.deepcopy(update)))
        for document in self.documents:
            if self._matches(document, query):
                for key, value in update.get("$set", {}).items():
                    document[key] = value
                for key in update.get("$unset", {}):
                    document.pop(key, None)
                return SimpleNamespace(modified_count=1)
        return SimpleNamespace(modified_count=0)


class FakeWeddingsCollection:
    async def find_one(self, query, projection=None):
        return None


class FakeMongo:
    def __init__(self, couple_documents: list[dict]):
        self.db = {"couple_users": FakeCoupleUsersCollection(couple_documents)}
        self._weddings = FakeWeddingsCollection()

    def get_weddings_collection(self):
        return self._weddings


@pytest.fixture
def sample_couple_doc():
    return {
        "_id": "couple-1",
        "email": "couple@example.com",
        "partner1_name": "Alex",
        "partner2_name": "Jordan",
        "wedding_id": "wedding-1",
        "password_hash": couple_auth_module.get_password_hash("Password123!"),
        "setup_completed": True,
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
    }


def _active_access():
    return {
        "state": "active",
        "blocked": False,
        "detail": None,
    }


def _make_request_with_bearer_token(token: str) -> Request:
    return Request(
        {
            "type": "http",
            "headers": [(b"authorization", f"Bearer {token}".encode("utf-8"))],
        }
    )


def test_set_couple_session_cookie_uses_couple_record_id_subject(sample_couple_doc):
    response = Response()

    token = couple_auth_module._set_couple_session_cookie(response, sample_couple_doc)
    payload = verify_token(token)

    assert payload["sub"] == "couple-1"
    assert payload["role"] == "couple"
    assert payload["wedding_id"] == "wedding-1"


def test_require_couple_auth_loads_by_couple_record_id_subject(
    monkeypatch, sample_couple_doc
):
    fake_mongo = FakeMongo([sample_couple_doc])
    monkeypatch.setattr(couple_auth_dependency, "mongo", fake_mongo)
    monkeypatch.setattr(
        couple_auth_dependency,
        "verify_token",
        lambda token: {"sub": "couple-1", "role": "couple"},
    )
    monkeypatch.setattr(
        couple_auth_dependency.couple_lifecycle_service,
        "resolve_effective_state",
        AsyncMock(return_value=_active_access()),
    )

    result = asyncio.run(
        couple_auth_dependency.require_couple_auth(_make_request_with_bearer_token("x"))
    )

    assert result["email"] == "couple@example.com"


def test_require_couple_auth_rejects_ambiguous_legacy_email_subject(
    monkeypatch, sample_couple_doc
):
    duplicate = {
        **sample_couple_doc,
        "_id": "couple-2",
        "wedding_id": "wedding-2",
    }
    fake_mongo = FakeMongo([sample_couple_doc, duplicate])
    monkeypatch.setattr(couple_auth_dependency, "mongo", fake_mongo)
    monkeypatch.setattr(
        couple_auth_dependency,
        "verify_token",
        lambda token: {"sub": "couple@example.com", "role": "couple"},
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            couple_auth_dependency.require_couple_auth(
                _make_request_with_bearer_token("legacy")
            )
        )

    assert exc_info.value.status_code == 401
    assert "multiple couple accounts" in exc_info.value.detail


def test_couple_login_rejects_ambiguous_duplicate_email_matches(
    monkeypatch, sample_couple_doc
):
    duplicate = {
        **sample_couple_doc,
        "_id": "couple-2",
        "wedding_id": "wedding-2",
    }
    fake_mongo = FakeMongo([sample_couple_doc, duplicate])
    monkeypatch.setattr(couple_auth_module, "mongo", fake_mongo)
    monkeypatch.setattr(
        couple_auth_module,
        "_resolve_portal_access",
        AsyncMock(return_value=(None, _active_access())),
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            couple_auth_module.couple_login(
                couple_auth_module.CoupleLoginRequest(
                    email="couple@example.com",
                    password="Password123!",
                ),
                Response(),
            )
        )

    assert exc_info.value.status_code == 409
    assert "multiple wedding portal accounts" in exc_info.value.detail


def test_couple_login_selects_only_portal_eligible_duplicate_email_match(
    monkeypatch, sample_couple_doc
):
    blocked = {
        **sample_couple_doc,
        "_id": "couple-blocked",
        "wedding_id": "wedding-blocked",
    }
    eligible = {
        **sample_couple_doc,
        "_id": "couple-eligible",
        "wedding_id": "wedding-eligible",
    }
    fake_mongo = FakeMongo([blocked, eligible])
    monkeypatch.setattr(couple_auth_module, "mongo", fake_mongo)

    async def resolve_access(couple):
        if couple["_id"] == "couple-blocked":
            return None, {
                "state": "owner_cancelled",
                "blocked": True,
                "detail": "This wedding portal is unavailable because your planner's account is inactive.",
            }
        return None, _active_access()

    monkeypatch.setattr(couple_auth_module, "_resolve_portal_access", resolve_access)
    monkeypatch.setattr(
        couple_auth_module,
        "_set_couple_session_cookie",
        lambda response, couple: f"token-for-{couple['_id']}",
    )

    result = asyncio.run(
        couple_auth_module.couple_login(
            couple_auth_module.CoupleLoginRequest(
                email="couple@example.com",
                password="Password123!",
            ),
            Response(),
        )
    )

    assert result["access_token"] == "token-for-couple-eligible"
    assert result["couple"]["id"] == "couple-eligible"


def test_couple_forgot_password_skips_ambiguous_duplicate_email_accounts(
    monkeypatch, sample_couple_doc
):
    duplicate = {
        **sample_couple_doc,
        "_id": "couple-2",
        "wedding_id": "wedding-2",
    }
    fake_mongo = FakeMongo([sample_couple_doc, duplicate])
    monkeypatch.setattr(couple_auth_module, "mongo", fake_mongo)
    monkeypatch.setattr(
        couple_auth_module,
        "_resolve_portal_access",
        AsyncMock(return_value=(None, _active_access())),
    )

    result = asyncio.run(
        couple_auth_module.couple_forgot_password(
            couple_auth_module.CoupleForgotPasswordRequest(email="couple@example.com")
        )
    )

    assert "If an account with this email exists" in result["message"]
    assert fake_mongo.db["couple_users"].update_calls == []
