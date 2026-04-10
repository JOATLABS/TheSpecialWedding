import asyncio
import os
import sys
from datetime import datetime, timedelta
from types import SimpleNamespace

import mongomock
import pytest
from fastapi import HTTPException, status

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("API_KEY", "test-api-key")

import app.dependencies.auth_extended as auth_extended
import app.services.trial_expiration_service as trial_service_module


class DummyEmailService:
    def __init__(self):
        self.configured = True
        self.sent_payloads = []

    def send_email(self, **payload):
        self.sent_payloads.append(payload)
        return {"success": True}


class FakeMongo:
    def __init__(self, database):
        self.db = database

    def get_users_collection(self):
        return self.db["users"]

    def get_admin_users_collection(self):
        return self.db["admin_users"]


@pytest.fixture
def mongo_database():
    client = mongomock.MongoClient()
    return client["trial_expiration_tests"]


@pytest.fixture
def trial_service(monkeypatch, mongo_database):
    fake_mongo = FakeMongo(mongo_database)
    monkeypatch.setattr(trial_service_module, "mongo", fake_mongo)

    email_service = DummyEmailService()
    monkeypatch.setattr(
        trial_service_module, "ResendEmailService", lambda: email_service
    )

    service = trial_service_module.TrialExpirationService()
    return service, mongo_database, email_service


def test_expired_trials_are_deactivated_and_notified(trial_service):
    service, database, email_service = trial_service
    users = database["users"]
    now = datetime.utcnow()

    users.insert_many(
        [
            {
                "_id": "expired-user",
                "email": "expired@example.com",
                "subscription_status": "trial",
                "trial_end_date": now - timedelta(days=1),
                "is_active": True,
                "email_verified": True,
            },
            {
                "_id": "active-user",
                "email": "active@example.com",
                "subscription_status": "trial",
                "trial_end_date": now + timedelta(days=5),
                "is_active": True,
                "email_verified": True,
            },
        ]
    )

    result = service.check_and_expire_trials()

    assert result["expired_trials"] == 1
    expired_record = users.find_one({"_id": "expired-user"})
    assert expired_record["subscription_status"] == "expired"
    assert expired_record["is_active"] is False
    assert "trial_expired_at" in expired_record

    active_record = users.find_one({"_id": "active-user"})
    assert active_record["subscription_status"] == "trial"
    assert active_record["is_active"] is True

    assert email_service.sent_payloads
    assert email_service.sent_payloads[0]["to_email"] == "expired@example.com"
    assert email_service.sent_payloads[0]["email_type"] == "trial_expired"


def test_warning_emails_sent_within_window(trial_service):
    service, database, email_service = trial_service
    users = database["users"]
    now = datetime.utcnow()

    users.insert_many(
        [
            {
                "_id": "warn-user",
                "email": "warning@example.com",
                "subscription_status": "trial",
                "trial_end_date": now + timedelta(days=3),
                "is_active": True,
                "email_verified": True,
            },
            {
                "_id": "far-user",
                "email": "future@example.com",
                "subscription_status": "trial",
                "trial_end_date": now + timedelta(days=14),
                "is_active": True,
                "email_verified": True,
            },
        ]
    )

    result = service.send_trial_warning_emails()

    assert result["warnings_sent"] == 1

    warned = users.find_one({"_id": "warn-user"})
    assert warned.get("trial_warning_sent") is True
    assert "warning_sent_at" in warned

    not_warned = users.find_one({"_id": "far-user"})
    assert not_warned.get("trial_warning_sent") is None

    assert email_service.sent_payloads
    assert email_service.sent_payloads[0]["email_type"] == "trial_warning"


def test_expiration_respects_disabled_setting(trial_service):
    service, database, email_service = trial_service
    database["saas_config"].insert_one(
        {
            "type": "main_config",
            "trial_settings": {
                "auto_expire_trials": False,
                "default_trial_days": 14,
                "trial_warning_days": 3,
            },
        }
    )

    database["users"].insert_one(
        {
            "_id": "pending-user",
            "email": "pending@example.com",
            "subscription_status": "trial",
            "trial_end_date": datetime.utcnow() - timedelta(days=2),
            "is_active": True,
            "email_verified": True,
        }
    )

    result = service.check_and_expire_trials()

    assert result["message"] == "Auto trial expiration is disabled"
    still_trial = database["users"].find_one({"_id": "pending-user"})
    assert still_trial["subscription_status"] == "trial"
    assert still_trial["is_active"] is True
    assert not email_service.sent_payloads


@pytest.fixture
def auth_context(monkeypatch, mongo_database):
    fake_mongo = FakeMongo(mongo_database)
    monkeypatch.setattr(auth_extended, "mongo", fake_mongo)
    monkeypatch.setattr(
        auth_extended,
        "verify_token",
        lambda token: {"sub": "planner@example.com", "role": "wedding_planner"},
    )
    os.environ.setdefault("ROOT_ADMIN_EMAIL", "root@example.com")
    return mongo_database


def test_authentication_blocks_expired_trials(auth_context):
    users = auth_context["users"]
    users.insert_one(
        {
            "email": "planner@example.com",
            "role": "wedding_planner",
            "subscription_status": "trial",
            "trial_end_date": datetime.utcnow() - timedelta(days=1),
            "is_active": True,
            "email_verified": True,
        }
    )

    credentials = SimpleNamespace(credentials="token")

    with pytest.raises(HTTPException) as exc:
        asyncio.run(auth_extended.get_current_user_extended(credentials))

    assert exc.value.status_code == status.HTTP_402_PAYMENT_REQUIRED

    updated = users.find_one({"email": "planner@example.com"})
    assert updated["subscription_status"] == "expired"
    assert updated["is_active"] is False
    assert "trial_expired_at" in updated


def test_authentication_allows_active_trials(auth_context):
    users = auth_context["users"]
    users.insert_one(
        {
            "email": "planner@example.com",
            "role": "wedding_planner",
            "subscription_status": "trial",
            "trial_end_date": datetime.utcnow() + timedelta(days=5),
            "is_active": True,
            "email_verified": True,
        }
    )

    credentials = SimpleNamespace(credentials="token")

    user = asyncio.run(auth_extended.get_current_user_extended(credentials))

    assert user.email == "planner@example.com"
    assert user.role == "wedding_planner"
    record = users.find_one({"email": "planner@example.com"})
    assert record["subscription_status"] == "trial"
    assert record["is_active"] is True
    assert "trial_expired_at" not in record
