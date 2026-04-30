import os
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import mongomock
import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("API_KEY", "test-api-key")

import app.dependencies.auth_extended as auth_extended  # noqa: E402
import app.services.trial_expiration_service as trial_service_module  # noqa: E402


class DummyEmailService:
    def __init__(self):
        self.configured = True
        self.sent_payloads = []

    async def send_email(self, **payload):
        self.sent_payloads.append(payload)
        return {"success": True}


class FakeMongo:
    def __init__(self, database):
        self.db = AsyncMockDatabase(database)

    def get_users_collection(self):
        return self.db["users"]

    def get_admin_users_collection(self):
        return self.db["admin_users"]


class AsyncMockCursor:
    def __init__(self, cursor):
        self.cursor = cursor

    def sort(self, *args, **kwargs):
        self.cursor.sort(*args, **kwargs)
        return self

    def limit(self, *args, **kwargs):
        self.cursor.limit(*args, **kwargs)
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

    async def insert_many(self, *args, **kwargs):
        return self.collection.insert_many(*args, **kwargs)

    async def update_one(self, *args, **kwargs):
        return self.collection.update_one(*args, **kwargs)

    async def update_many(self, *args, **kwargs):
        return self.collection.update_many(*args, **kwargs)


class AsyncMockDatabase:
    def __init__(self, database):
        self.db = database
        self.collections = {}

    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = AsyncMockCollection(self.db[name])
        return self.collections[name]


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


@pytest.mark.asyncio
async def test_expired_trials_are_deactivated_and_notified(trial_service):
    service, database, email_service = trial_service
    users = database["users"]
    now = datetime.now(timezone.utc)

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
            {
                "_id": "expiring-user",
                "email": "expiring@example.com",
                "subscription_status": "trial_expiring",
                "trial_end_date": now - timedelta(days=1),
                "is_active": True,
                "email_verified": True,
            },
        ]
    )
    database["user_subscriptions"].insert_many(
        [
            {
                "_id": "sub-expired-primary",
                "user_id": "expired-user",
                "status": "trial",
            },
            {
                "_id": "sub-expired-duplicate",
                "user_id": "expired-user",
                "status": "trial_expiring",
            },
            {
                "_id": "sub-active",
                "user_id": "active-user",
                "status": "trial",
            },
        ]
    )

    result = await service.check_and_expire_trials()

    assert result["expired_trials"] == 2
    expired_record = users.find_one({"_id": "expired-user"})
    assert expired_record["subscription_status"] == "expired"
    assert expired_record["is_active"] is True
    assert "trial_expired_at" in expired_record

    expiring_record = users.find_one({"_id": "expiring-user"})
    assert expiring_record["subscription_status"] == "expired"
    assert expiring_record["is_active"] is True
    assert "trial_expired_at" in expiring_record

    active_record = users.find_one({"_id": "active-user"})
    assert active_record["subscription_status"] == "trial"
    assert active_record["is_active"] is True

    expired_subscription_statuses = {
        sub["_id"]: sub["status"]
        for sub in database["user_subscriptions"].find({"user_id": "expired-user"})
    }
    assert expired_subscription_statuses == {
        "sub-expired-primary": "expired",
        "sub-expired-duplicate": "expired",
    }
    assert (
        database["user_subscriptions"].find_one({"_id": "sub-active"})["status"]
        == "trial"
    )

    assert len(email_service.sent_payloads) == 2
    assert email_service.sent_payloads[0]["to_email"] == "expired@example.com"
    assert email_service.sent_payloads[0]["email_type"] == "trial_expired"


@pytest.mark.asyncio
async def test_warning_emails_sent_within_window(trial_service, monkeypatch):
    service, database, email_service = trial_service
    users = database["users"]
    now = datetime.now(timezone.utc)

    class _NaiveDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.utcnow()

    monkeypatch.setattr(trial_service_module, "datetime", _NaiveDateTime)

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
            {
                "_id": "expiring-user",
                "email": "expiring@example.com",
                "subscription_status": "trial_expiring",
                "trial_end_date": now + timedelta(days=3),
                "is_active": True,
                "email_verified": True,
            },
            {
                "_id": "legacy-user",
                "email": "legacy@example.com",
                "subscription_status": "trial",
                "trial_end_date": now + timedelta(days=3),
                "is_active": True,
            },
            {
                "_id": "unverified-public-user",
                "email": "unverified-public@example.com",
                "subscription_status": "trial",
                "trial_end_date": now + timedelta(days=3),
                "is_active": True,
                "email_verified": False,
                "registration_source": "public_signup",
            },
        ]
    )

    result = await service.send_trial_warning_emails()

    assert result["warnings_sent"] == 3

    warned = users.find_one({"_id": "warn-user"})
    assert warned.get("trial_countdown_last_day") in {1, 2, 3}
    assert "trial_countdown_last_sent" in warned

    not_warned = users.find_one({"_id": "far-user"})
    assert not_warned.get("trial_warning_sent") is None

    assert len(email_service.sent_payloads) == 3
    sent_to = {payload["to_email"] for payload in email_service.sent_payloads}
    assert "legacy@example.com" in sent_to
    assert "unverified-public@example.com" not in sent_to
    assert email_service.sent_payloads[0]["email_type"] == "trial_warning"


@pytest.mark.asyncio
async def test_expiration_respects_disabled_setting(trial_service):
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
            "trial_end_date": datetime.now(timezone.utc) - timedelta(days=2),
            "is_active": True,
            "email_verified": True,
        }
    )

    result = await service.check_and_expire_trials()

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


@pytest.mark.asyncio
async def test_authentication_blocks_expired_trials(auth_context):
    users = auth_context["users"]
    users.insert_one(
        {
            "email": "planner@example.com",
            "role": "wedding_planner",
            "subscription_status": "trial",
            "trial_end_date": datetime.now(timezone.utc) - timedelta(days=1),
            "is_active": True,
            "email_verified": True,
        }
    )

    credentials = SimpleNamespace(credentials="token")

    user = await auth_extended.get_current_user_extended(credentials)
    assert user.user_data["subscription_status"] == "expired"
    assert user.user_data.get("_subscription_blocked") is True

    updated = users.find_one({"email": "planner@example.com"})
    assert updated["subscription_status"] == "expired"
    assert "trial_expired_at" in updated


@pytest.mark.asyncio
async def test_authentication_blocks_expired_trial_expiring_status(auth_context):
    users = auth_context["users"]
    users.insert_one(
        {
            "email": "planner@example.com",
            "role": "wedding_planner",
            "subscription_status": "trial_expiring",
            "trial_end_date": datetime.now(timezone.utc) - timedelta(days=1),
            "is_active": True,
            "email_verified": True,
        }
    )

    credentials = SimpleNamespace(credentials="token")

    user = await auth_extended.get_current_user_extended(credentials)
    assert user.user_data["subscription_status"] == "expired"
    assert user.user_data.get("_subscription_blocked") is True

    updated = users.find_one({"email": "planner@example.com"})
    assert updated["subscription_status"] == "expired"
    assert "trial_expired_at" in updated


@pytest.mark.asyncio
async def test_authentication_allows_active_trials(auth_context):
    users = auth_context["users"]
    users.insert_one(
        {
            "email": "planner@example.com",
            "role": "wedding_planner",
            "subscription_status": "trial",
            "trial_end_date": datetime.now(timezone.utc) + timedelta(days=5),
            "is_active": True,
            "email_verified": True,
        }
    )

    credentials = SimpleNamespace(credentials="token")

    user = await auth_extended.get_current_user_extended(credentials)

    assert user.email == "planner@example.com"
    assert user.role == "wedding_planner"
    record = users.find_one({"email": "planner@example.com"})
    assert record["subscription_status"] == "trial"
    assert record["is_active"] is True
    assert "trial_expired_at" not in record
