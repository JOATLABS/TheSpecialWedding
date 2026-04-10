import asyncio
import os
import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from bson import ObjectId

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import app.services.planner_onboarding_email_service as onboarding_module


def _resolve_dotted(document, dotted_key):
    """Resolve a dotted key path like 'a.b.c' against a nested dict."""
    actual = document
    for part in dotted_key.split("."):
        if isinstance(actual, dict) and part in actual:
            actual = actual[part]
        else:
            return None
    return actual


def _matches(document, query):
    for key, expected in query.items():
        # Handle $or operator
        if key == "$or":
            if not any(_matches(document, sub_query) for sub_query in expected):
                return False
            continue

        actual = _resolve_dotted(document, key)

        if isinstance(expected, dict):
            if "$exists" in expected:
                exists = actual is not None
                if exists != expected["$exists"]:
                    return False
            if "$in" in expected and actual not in expected["$in"]:
                return False
            if "$lt" in expected:
                if actual is None or actual >= expected["$lt"]:
                    return False
            continue

        if actual != expected:
            return False
    return True


class AsyncCursor:
    def __init__(self, documents):
        self.documents = [deepcopy(document) for document in documents]

    def __aiter__(self):
        self._iter = iter(self.documents)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration as exc:  # pragma: no cover - iterator protocol
            raise StopAsyncIteration from exc


class AsyncCollection:
    def __init__(self, storage):
        self.storage = storage

    async def find_one(self, query, *_args, **_kwargs):
        for document in self.storage:
            if _matches(document, query):
                return deepcopy(document)
        return None

    def find(self, query, *_args, **_kwargs):
        return AsyncCursor(
            [document for document in self.storage if _matches(document, query)]
        )

    async def update_one(self, query, update, *_args, **_kwargs):
        for document in self.storage:
            if _matches(document, query):
                for key, value in update.get("$set", {}).items():
                    target = document
                    parts = key.split(".")
                    for part in parts[:-1]:
                        target = target.setdefault(part, {})
                    target[parts[-1]] = value
                for key in update.get("$unset", {}):
                    target = document
                    parts = key.split(".")
                    for part in parts[:-1]:
                        if isinstance(target, dict) and part in target:
                            target = target[part]
                        else:
                            target = None
                            break
                    if (
                        target is not None
                        and isinstance(target, dict)
                        and parts[-1] in target
                    ):
                        del target[parts[-1]]
                return SimpleNamespace(modified_count=1)
        return SimpleNamespace(modified_count=0)

    async def count_documents(self, query):
        return sum(1 for document in self.storage if _matches(document, query))


class AsyncDatabase:
    def __init__(self, storage_map):
        self.storage_map = storage_map

    def __getitem__(self, name):
        self.storage_map.setdefault(name, [])
        return AsyncCollection(self.storage_map[name])


class FakeMongo:
    def __init__(self, storage_map):
        self.storage_map = storage_map
        self.db = AsyncDatabase(storage_map)

    def get_users_collection(self):
        self.storage_map.setdefault("users", [])
        return AsyncCollection(self.storage_map["users"])


class DummyEmailService:
    def __init__(self):
        self.configured = True
        self.sent = []

    async def send_email(self, **kwargs):
        self.sent.append(kwargs)
        return {"success": True, "id": f"email_{len(self.sent)}"}


def build_service(storage):
    fake_mongo = FakeMongo(storage)
    onboarding_module.mongo = fake_mongo
    service = onboarding_module.PlannerOnboardingEmailService()
    service.email_service = DummyEmailService()
    return service


def test_start_sequence_sends_welcome_and_persists_state():
    user_id = ObjectId()
    storage = {
        "users": [
            {
                "_id": user_id,
                "email": "planner@example.com",
                "role": "wedding_planner",
                "first_name": "Ava",
                "company_name": "Ava Events",
                "email_verified": True,
                "is_active": True,
                "created_at": datetime.now(timezone.utc),
            }
        ],
        "weddings": [],
        "team_members": [],
        "user_subscriptions": [],
    }
    service = build_service(storage)

    result = asyncio.run(service.start_sequence(str(user_id)))

    assert result["started"] is True
    assert len(service.email_service.sent) == 1
    sent = service.email_service.sent[0]
    assert sent["email_type"] == "planner_onboarding_day0_welcome"
    user = storage["users"][0]
    assert user["planner_onboarding_email"]["status"] == "active"
    assert user["planner_onboarding_email"]["welcome_sent_at"] is not None


def test_process_due_emails_sends_day_one_when_no_wedding_exists():
    user_id = ObjectId()
    started_at = datetime.now(timezone.utc) - timedelta(days=2)
    storage = {
        "users": [
            {
                "_id": user_id,
                "email": "planner@example.com",
                "role": "wedding_planner",
                "first_name": "Ava",
                "email_verified": True,
                "is_active": True,
                "created_at": started_at,
                "planner_onboarding_email": {
                    "status": "active",
                    "started_at": started_at,
                    "welcome_sent_at": started_at,
                },
            }
        ],
        "weddings": [],
        "team_members": [],
        "user_subscriptions": [],
    }
    service = build_service(storage)

    result = asyncio.run(service.process_due_emails())

    assert result["sent"] == 1
    sent = service.email_service.sent[0]
    assert sent["email_type"] == "planner_onboarding_day1_first_wedding"
    state = storage["users"][0]["planner_onboarding_email"]
    assert state["first_wedding_sent_at"] is not None
    assert state.get("first_wedding_skipped_at") is None


def test_process_due_emails_skips_day_one_when_wedding_already_exists():
    user_id = ObjectId()
    started_at = datetime.now(timezone.utc) - timedelta(days=2)
    storage = {
        "users": [
            {
                "_id": user_id,
                "email": "planner@example.com",
                "role": "wedding_planner",
                "email_verified": True,
                "is_active": True,
                "created_at": started_at,
                "planner_onboarding_email": {
                    "status": "active",
                    "started_at": started_at,
                    "welcome_sent_at": started_at,
                },
            }
        ],
        "weddings": [{"_id": "wed_1", "assigned_planner_id": str(user_id)}],
        "team_members": [],
        "user_subscriptions": [],
    }
    service = build_service(storage)

    result = asyncio.run(service.process_due_emails())

    assert result["sent"] == 0
    assert result["skipped"] == 1
    assert service.email_service.sent == []
    state = storage["users"][0]["planner_onboarding_email"]
    assert state["first_wedding_skipped_at"] is not None
    assert state["first_wedding_skip_reason"] == "wedding_already_created"


def test_process_due_emails_exits_when_signature_is_active():
    user_id = ObjectId()
    started_at = datetime.now(timezone.utc) - timedelta(days=4)
    storage = {
        "users": [
            {
                "_id": user_id,
                "email": "planner@example.com",
                "role": "wedding_planner",
                "first_name": "Ava",
                "email_verified": True,
                "is_active": True,
                "created_at": started_at,
                "planner_onboarding_email": {
                    "status": "active",
                    "started_at": started_at,
                    "welcome_sent_at": started_at,
                },
            }
        ],
        "weddings": [],
        "team_members": [],
        "user_subscriptions": [
            {
                "_id": "sub_1",
                "user_id": str(user_id),
                "status": "active",
                "plan_snapshot": {"plan_name": "Signature"},
            }
        ],
    }
    service = build_service(storage)

    result = asyncio.run(service.process_due_emails())

    assert result["sent"] == 1
    assert result["exited"] == 1
    sent = service.email_service.sent[0]
    assert sent["email_type"] == "planner_onboarding_signature_exit"
    state = storage["users"][0]["planner_onboarding_email"]
    assert state["status"] == "exited"
    assert state["exit_reason"] == "upgraded_to_signature"


def test_start_sequence_generates_unsubscribe_token_and_footer_link():
    user_id = ObjectId()
    storage = {
        "users": [
            {
                "_id": user_id,
                "email": "planner@example.com",
                "role": "wedding_planner",
                "first_name": "Ava",
                "email_verified": True,
                "is_active": True,
                "created_at": datetime.now(timezone.utc),
            }
        ],
        "weddings": [],
        "team_members": [],
        "user_subscriptions": [],
    }
    service = build_service(storage)

    asyncio.run(service.start_sequence(str(user_id)))

    state = storage["users"][0]["planner_onboarding_email"]
    assert state["unsubscribe_token"]
    sent = service.email_service.sent[0]
    assert "/unsubscribe/planner-onboarding?token=" in sent["html_content"]


def test_unsubscribe_by_token_marks_sequence_exited():
    user_id = ObjectId()
    unsubscribe_token = "token_1234567890abcdefghijklmnop"
    started_at = datetime.now(timezone.utc) - timedelta(days=1)
    storage = {
        "users": [
            {
                "_id": user_id,
                "email": "planner@example.com",
                "role": "wedding_planner",
                "first_name": "Ava",
                "email_verified": True,
                "is_active": True,
                "created_at": started_at,
                "planner_onboarding_email": {
                    "status": "active",
                    "started_at": started_at,
                    "welcome_sent_at": started_at,
                    "unsubscribe_token": unsubscribe_token,
                    "unsubscribe_token_created_at": datetime.now(timezone.utc),
                },
            }
        ],
        "weddings": [],
        "team_members": [],
        "user_subscriptions": [],
    }
    service = build_service(storage)

    result = asyncio.run(service.unsubscribe_by_token(unsubscribe_token))

    assert result is not None
    assert result["email"] == "p*****r@example.com"
    state = storage["users"][0]["planner_onboarding_email"]
    assert state["status"] == "exited"
    assert state["exit_reason"] == "explicit_unsubscribe"
    assert state["unsubscribed_at"] is not None


def test_unsubscribe_rejects_expired_token():
    """Tokens older than 90 days should be rejected."""
    user_id = ObjectId()
    unsubscribe_token = "token_expired_1234567890abcdefgh"
    started_at = datetime.now(timezone.utc) - timedelta(days=100)
    storage = {
        "users": [
            {
                "_id": user_id,
                "email": "planner@example.com",
                "role": "wedding_planner",
                "first_name": "Ava",
                "email_verified": True,
                "is_active": True,
                "created_at": started_at,
                "planner_onboarding_email": {
                    "status": "active",
                    "started_at": started_at,
                    "welcome_sent_at": started_at,
                    "unsubscribe_token": unsubscribe_token,
                    "unsubscribe_token_created_at": datetime.now(timezone.utc)
                    - timedelta(days=91),
                },
            }
        ],
        "weddings": [],
        "team_members": [],
        "user_subscriptions": [],
    }
    service = build_service(storage)

    result = asyncio.run(service.unsubscribe_by_token(unsubscribe_token))
    assert result is None, "Expired token should be rejected"

    status = asyncio.run(service.get_unsubscribe_status(unsubscribe_token))
    assert status is None, "Expired token status should return None"


def test_unsubscribe_token_created_at_set_on_start():
    """Starting the sequence should set unsubscribe_token_created_at alongside the token."""
    user_id = ObjectId()
    storage = {
        "users": [
            {
                "_id": user_id,
                "email": "planner@example.com",
                "role": "wedding_planner",
                "first_name": "Ava",
                "email_verified": True,
                "is_active": True,
                "created_at": datetime.now(timezone.utc),
            }
        ],
        "weddings": [],
        "team_members": [],
        "user_subscriptions": [],
    }
    service = build_service(storage)

    asyncio.run(service.start_sequence(str(user_id)))

    state = storage["users"][0]["planner_onboarding_email"]
    assert state.get("unsubscribe_token") is not None
    assert state.get("unsubscribe_token_created_at") is not None


def test_html_escaping_in_display_name():
    """User-supplied names should be HTML-escaped in email templates."""
    user_id = ObjectId()
    storage = {
        "users": [
            {
                "_id": user_id,
                "email": "planner@example.com",
                "role": "wedding_planner",
                "first_name": '<script>alert("xss")</script>',
                "company_name": "<img src=x onerror=alert(1)>",
                "email_verified": True,
                "is_active": True,
                "created_at": datetime.now(timezone.utc),
            }
        ],
        "weddings": [],
        "team_members": [],
        "user_subscriptions": [],
    }
    service = build_service(storage)

    asyncio.run(service.start_sequence(str(user_id)))

    sent = service.email_service.sent[0]
    html = sent["html_content"]
    assert "<script>" not in html, "Script tags should be escaped"
    assert "<img src=x" not in html, "HTML injection via company_name should be escaped"
    assert "&lt;script&gt;" in html, "Name should be HTML-escaped"


def test_process_due_emails_sends_day3_couple_portal():
    """Day 3 couple_portal email should fire when day 1 is already sent."""
    user_id = ObjectId()
    started_at = datetime.now(timezone.utc) - timedelta(days=4)
    storage = {
        "users": [
            {
                "_id": user_id,
                "email": "planner@example.com",
                "role": "wedding_planner",
                "first_name": "Ava",
                "email_verified": True,
                "is_active": True,
                "created_at": started_at,
                "planner_onboarding_email": {
                    "status": "active",
                    "started_at": started_at,
                    "welcome_sent_at": started_at,
                    "first_wedding_sent_at": started_at + timedelta(days=1),
                },
            }
        ],
        "weddings": [],
        "team_members": [],
        "user_subscriptions": [],
    }
    service = build_service(storage)
    result = asyncio.run(service.process_due_emails())
    assert result["sent"] >= 1
    email_types = [s["email_type"] for s in service.email_service.sent]
    assert "planner_onboarding_day3_couple_portal" in email_types
    state = storage["users"][0]["planner_onboarding_email"]
    assert state.get("couple_portal_sent_at") is not None


def test_process_due_emails_sends_day5_ai_paperwork():
    """Day 5 ai_paperwork email should fire when days 1 and 3 are already sent."""
    user_id = ObjectId()
    started_at = datetime.now(timezone.utc) - timedelta(days=6)
    storage = {
        "users": [
            {
                "_id": user_id,
                "email": "planner@example.com",
                "role": "wedding_planner",
                "first_name": "Ava",
                "email_verified": True,
                "is_active": True,
                "created_at": started_at,
                "planner_onboarding_email": {
                    "status": "active",
                    "started_at": started_at,
                    "welcome_sent_at": started_at,
                    "first_wedding_sent_at": started_at + timedelta(days=1),
                    "couple_portal_sent_at": started_at + timedelta(days=3),
                },
            }
        ],
        "weddings": [],
        "team_members": [],
        "user_subscriptions": [],
    }
    service = build_service(storage)
    result = asyncio.run(service.process_due_emails())
    assert result["sent"] >= 1
    email_types = [s["email_type"] for s in service.email_service.sent]
    assert "planner_onboarding_day5_ai_paperwork" in email_types
    state = storage["users"][0]["planner_onboarding_email"]
    assert state.get("ai_paperwork_sent_at") is not None


def test_process_due_emails_skips_day8_when_team_exists():
    """Day 8 team_rules should be skipped when the planner already has team members."""
    user_id = ObjectId()
    started_at = datetime.now(timezone.utc) - timedelta(days=9)
    storage = {
        "users": [
            {
                "_id": user_id,
                "email": "planner@example.com",
                "role": "wedding_planner",
                "first_name": "Ava",
                "email_verified": True,
                "is_active": True,
                "created_at": started_at,
                "planner_onboarding_email": {
                    "status": "active",
                    "started_at": started_at,
                    "welcome_sent_at": started_at,
                    "first_wedding_sent_at": started_at + timedelta(days=1),
                    "couple_portal_sent_at": started_at + timedelta(days=3),
                    "ai_paperwork_sent_at": started_at + timedelta(days=5),
                },
            }
        ],
        "weddings": [],
        "team_members": [{"_id": "tm_1", "owner_id": str(user_id), "status": "active"}],
        "user_subscriptions": [],
    }
    service = build_service(storage)
    result = asyncio.run(service.process_due_emails())
    state = storage["users"][0]["planner_onboarding_email"]
    assert state.get("team_rules_skipped_at") is not None
    assert state.get("team_rules_skip_reason") == "team_members_already_exist"
    email_types = [s["email_type"] for s in service.email_service.sent]
    assert "planner_onboarding_day8_team_rules" not in email_types


def test_process_due_emails_sends_day12_and_completes_sequence():
    """Day 12 social proof should send and mark the sequence as completed."""
    user_id = ObjectId()
    started_at = datetime.now(timezone.utc) - timedelta(days=13)
    storage = {
        "users": [
            {
                "_id": user_id,
                "email": "planner@example.com",
                "role": "wedding_planner",
                "first_name": "Ava",
                "email_verified": True,
                "is_active": True,
                "created_at": started_at,
                "planner_onboarding_email": {
                    "status": "active",
                    "started_at": started_at,
                    "welcome_sent_at": started_at,
                    "first_wedding_sent_at": started_at + timedelta(days=1),
                    "couple_portal_sent_at": started_at + timedelta(days=3),
                    "ai_paperwork_sent_at": started_at + timedelta(days=5),
                    "team_rules_sent_at": started_at + timedelta(days=8),
                },
            }
        ],
        "weddings": [],
        "team_members": [],
        "user_subscriptions": [],
    }
    service = build_service(storage)
    result = asyncio.run(service.process_due_emails())
    assert result["sent"] >= 1
    email_types = [s["email_type"] for s in service.email_service.sent]
    assert "planner_onboarding_day12_social_proof" in email_types
    state = storage["users"][0]["planner_onboarding_email"]
    assert state.get("planners_love_sent_at") is not None
    assert state.get("status") == "completed"
