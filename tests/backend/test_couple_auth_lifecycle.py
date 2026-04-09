import asyncio
import copy
import os
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import app.api.couple_auth as couple_auth_module  # noqa: E402


class FakeCoupleUsersCollection:
    def __init__(self, document: dict | list[dict] | None):
        if isinstance(document, list):
            self.documents = copy.deepcopy(document)
        elif document is None:
            self.documents = []
        else:
            self.documents = [copy.deepcopy(document)]
        self.update_calls: list[tuple[dict, dict]] = []

    @property
    def document(self):
        return self.documents[0] if self.documents else None

    def _matches(self, document: dict, query: dict) -> bool:
        for key, value in query.items():
            document_value = document.get(key)
            if isinstance(value, dict):
                if "$gt" in value and not (
                    document_value and document_value > value["$gt"]
                ):
                    return False
                continue
            if document_value != value:
                return False
        return True

    async def find_one(self, query):
        for document in self.documents:
            if self._matches(document, query):
                return copy.deepcopy(document)
        return None

    def find(self, query):
        matches = [
            copy.deepcopy(document)
            for document in self.documents
            if self._matches(document, query)
        ]
        return SimpleNamespace(to_list=AsyncMock(return_value=matches))

    async def update_one(self, query, update):
        self.update_calls.append((copy.deepcopy(query), copy.deepcopy(update)))
        for document in self.documents:
            if not self._matches(document, query):
                continue

            for key, value in update.get("$set", {}).items():
                document[key] = value
            for key in update.get("$unset", {}):
                document.pop(key, None)

            return SimpleNamespace(modified_count=1)

        return SimpleNamespace(modified_count=0)


class FakeMongo:
    def __init__(self, couple_document: dict | None):
        self.db = {"couple_users": FakeCoupleUsersCollection(couple_document)}


def _login_request(
    password: str = "Password123!",
) -> couple_auth_module.CoupleLoginRequest:
    return couple_auth_module.CoupleLoginRequest(
        email="couple@example.com",
        password=password,
    )


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
    }


def test_couple_login_rejects_owner_cancelled_accounts(monkeypatch, sample_couple_doc):
    fake_mongo = FakeMongo(sample_couple_doc)
    monkeypatch.setattr(couple_auth_module, "mongo", fake_mongo)
    monkeypatch.setattr(
        couple_auth_module,
        "_resolve_portal_access",
        AsyncMock(
            return_value=(
                None,
                {
                    "state": "owner_cancelled",
                    "blocked": True,
                    "detail": "This wedding portal is unavailable because your planner's account is inactive. Please contact your planner.",
                },
            )
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(couple_auth_module.couple_login(_login_request(), ResponseStub()))

    assert exc_info.value.status_code == 403
    assert "planner's account is inactive" in exc_info.value.detail
    assert fake_mongo.db["couple_users"].update_calls == []


def test_setup_couple_password_rejects_archived_weddings(
    monkeypatch, sample_couple_doc
):
    invite_doc = {
        **sample_couple_doc,
        "password_hash": None,
        "setup_completed": False,
        "is_active": False,
        "invite_token": "invite-token",
        "invite_token_expires": datetime.now(timezone.utc) + timedelta(days=1),
    }
    fake_mongo = FakeMongo(invite_doc)
    monkeypatch.setattr(couple_auth_module, "mongo", fake_mongo)
    monkeypatch.setattr(
        couple_auth_module,
        "_resolve_portal_access",
        AsyncMock(
            return_value=(
                None,
                {
                    "state": "archived_readonly",
                    "blocked": False,
                    "detail": "This wedding has been archived. You can still view your wedding details.",
                },
            )
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            couple_auth_module.setup_couple_password(
                couple_auth_module.CoupleSetupPasswordRequest(
                    token="invite-token",
                    password="NewPassword123!",
                ),
                ResponseStub(),
            )
        )

    assert exc_info.value.status_code == 403
    assert "archived" in exc_info.value.detail.lower()
    assert fake_mongo.db["couple_users"].update_calls == []


def test_couple_login_allows_archived_readonly_accounts(monkeypatch, sample_couple_doc):
    fake_mongo = FakeMongo(sample_couple_doc)
    monkeypatch.setattr(couple_auth_module, "mongo", fake_mongo)
    monkeypatch.setattr(
        couple_auth_module,
        "_resolve_portal_access",
        AsyncMock(
            return_value=(
                None,
                {
                    "state": "archived_readonly",
                    "blocked": False,
                    "detail": "This wedding has been archived. You can still view your wedding details.",
                },
            )
        ),
    )
    monkeypatch.setattr(
        couple_auth_module,
        "_set_couple_session_cookie",
        lambda response, couple: "test-couple-token",
    )

    result = asyncio.run(
        couple_auth_module.couple_login(_login_request(), ResponseStub())
    )

    assert result["access_token"] == "test-couple-token"
    assert result["couple"]["email"] == "couple@example.com"
    assert fake_mongo.db["couple_users"].update_calls


def test_couple_profile_uses_canonical_wedding_owner_for_planner_id(
    monkeypatch, sample_couple_doc
):
    monkeypatch.setattr(
        couple_auth_module,
        "_load_wedding_for_couple",
        AsyncMock(
            return_value={
                "_id": "wedding-1",
                "assigned_planner_id": "planner-canonical",
                "assigned_planner_email": "planner@example.com",
            }
        ),
    )
    monkeypatch.setattr(
        couple_auth_module,
        "resolve_wedding_owner_identity",
        AsyncMock(
            return_value={
                "planner_id": "planner-canonical",
                "planner_email": "planner@example.com",
            }
        ),
    )

    result = asyncio.run(
        couple_auth_module.get_couple_profile(
            {
                **sample_couple_doc,
                "planner_id": "planner-stale-mirror",
                "_portal_access_state": "active",
                "_portal_access_detail": None,
            }
        )
    )

    assert result["planner_id"] == "planner-canonical"


class ResponseStub:
    headers = None
