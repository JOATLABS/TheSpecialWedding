"""Tests for the FormService.send_form_reminders scheduler logic.

Item 6 of the forms gap-closure plan: a daily background pass sends
one-shot reminder emails for unsubmitted form distributions whose
``reminder_days`` window has elapsed. Reminders rotate the access
token (so the link in the new email replaces the original), and the
pass is idempotent — already-reminded / already-submitted /
expired-token / inactive-form distributions are skipped.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
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
from app.models.form import EmailDistributionSettings, SendFormRequest  # noqa: E402


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


def _form_doc(form_id: str = "form_1", is_active: bool = True) -> Dict[str, Any]:
    now = datetime.utcnow()
    return {
        "_id": form_id,
        "name": "Reminder demo",
        "settings": {
            "title": "Reminder demo",
            "description": "",
            "submit_button_text": "Submit",
            "success_message": "Thanks!",
            "allow_multiple_submissions": True,
            "collect_email": True,
            "is_public": True,
            "requires_auth": False,
        },
        "fields": [
            {
                "id": "name",
                "label": "Name",
                "type": "text",
                "required": False,
                "order": 1,
            }
        ],
        "created_by": "planner@example.com",
        "wedding_id": None,
        "is_active": is_active,
        "created_at": now,
        "updated_at": now,
        "submission_count": 0,
        "planner_state": {},
    }


def _distribution_doc(
    *,
    distribution_id: str,
    form_id: str = "form_1",
    sent_days_ago: int,
    submitted: bool = False,
    reminder_already_sent: bool = False,
    send_reminder: bool = True,
    reminder_days: int = 7,
    status: str = "sent",
    token_expires_in_days: int = 30,
    access_token_hash: str = "stale-hash",
) -> Dict[str, Any]:
    sent_at = datetime.now(timezone.utc) - timedelta(days=sent_days_ago)
    return {
        "_id": distribution_id,
        "form_id": form_id,
        "recipient_email": f"{distribution_id}@example.com",
        "wedding_id": None,
        "sent_at": sent_at,
        "submitted_at": datetime.now(timezone.utc) if submitted else None,
        "status": status if not submitted else "submitted",
        "access_token_hash": access_token_hash,
        "token_expires_at": (
            datetime.now(timezone.utc) + timedelta(days=token_expires_in_days)
        ),
        "send_reminder": send_reminder,
        "reminder_days": reminder_days,
        "reminder_subject": "Please respond",
        "reminder_message": "Hi, please fill this out.",
        "reminder_sender_name": "Wedding Planner",
        "reminder_sent_at": (
            datetime.now(timezone.utc) if reminder_already_sent else None
        ),
        "reminder_count": 1 if reminder_already_sent else 0,
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
# Reminder pass behavior
# =============================================================================


@pytest.mark.asyncio
async def test_reminder_sent_when_window_elapsed(configured_form_service):
    service, database = configured_form_service
    database["forms"].insert_one(_form_doc())
    database["form_distributions"].insert_one(
        _distribution_doc(distribution_id="d1", sent_days_ago=8, reminder_days=7)
    )

    result = await service.send_form_reminders()

    assert result == {"sent": 1, "skipped": 0, "failed": 0, "deferred_for_budget": 0}
    sent = service.email_service.sent
    assert len(sent) == 1
    assert sent[0]["to_email"] == "d1@example.com"
    assert sent[0]["subject"].startswith("Reminder:")

    stored = database["form_distributions"].find_one({"_id": "d1"})
    assert stored["reminder_sent_at"] is not None
    assert stored["reminder_count"] == 1
    # Token rotation: the hash should no longer match the stale placeholder.
    assert stored["access_token_hash"] != "stale-hash"


@pytest.mark.asyncio
async def test_reminder_skipped_before_window(configured_form_service):
    service, database = configured_form_service
    database["forms"].insert_one(_form_doc())
    database["form_distributions"].insert_one(
        _distribution_doc(distribution_id="d1", sent_days_ago=3, reminder_days=7)
    )

    result = await service.send_form_reminders()

    assert result == {"sent": 0, "skipped": 1, "failed": 0, "deferred_for_budget": 0}
    assert service.email_service.sent == []


@pytest.mark.asyncio
async def test_reminder_skipped_when_already_submitted(configured_form_service):
    service, database = configured_form_service
    database["forms"].insert_one(_form_doc())
    database["form_distributions"].insert_one(
        _distribution_doc(distribution_id="d1", sent_days_ago=10, submitted=True)
    )

    result = await service.send_form_reminders()
    # Submitted distributions are filtered out at the Mongo query level —
    # they don't even get inspected, so they don't bump 'skipped'.
    assert result == {"sent": 0, "skipped": 0, "failed": 0, "deferred_for_budget": 0}


@pytest.mark.asyncio
async def test_reminder_skipped_when_already_reminded(configured_form_service):
    service, database = configured_form_service
    database["forms"].insert_one(_form_doc())
    database["form_distributions"].insert_one(
        _distribution_doc(
            distribution_id="d1", sent_days_ago=10, reminder_already_sent=True
        )
    )

    result = await service.send_form_reminders()
    assert result == {"sent": 0, "skipped": 0, "failed": 0, "deferred_for_budget": 0}


@pytest.mark.asyncio
async def test_reminder_skipped_when_send_reminder_disabled(configured_form_service):
    service, database = configured_form_service
    database["forms"].insert_one(_form_doc())
    database["form_distributions"].insert_one(
        _distribution_doc(
            distribution_id="d1", sent_days_ago=10, send_reminder=False
        )
    )

    result = await service.send_form_reminders()
    assert result == {"sent": 0, "skipped": 0, "failed": 0, "deferred_for_budget": 0}


@pytest.mark.asyncio
async def test_reminder_skipped_when_token_expired(configured_form_service):
    service, database = configured_form_service
    database["forms"].insert_one(_form_doc())
    database["form_distributions"].insert_one(
        _distribution_doc(
            distribution_id="d1",
            sent_days_ago=10,
            token_expires_in_days=-1,  # already expired
        )
    )

    result = await service.send_form_reminders()
    assert result == {"sent": 0, "skipped": 1, "failed": 0, "deferred_for_budget": 0}
    assert service.email_service.sent == []


@pytest.mark.asyncio
async def test_reminder_skipped_when_form_inactive(configured_form_service):
    service, database = configured_form_service
    database["forms"].insert_one(_form_doc(is_active=False))
    database["form_distributions"].insert_one(
        _distribution_doc(distribution_id="d1", sent_days_ago=10)
    )

    result = await service.send_form_reminders()
    assert result == {"sent": 0, "skipped": 1, "failed": 0, "deferred_for_budget": 0}


@pytest.mark.asyncio
async def test_reminder_url_contains_dist_and_fresh_token(
    configured_form_service,
):
    service, database = configured_form_service
    database["forms"].insert_one(_form_doc())
    database["form_distributions"].insert_one(
        _distribution_doc(distribution_id="d1", sent_days_ago=10)
    )

    await service.send_form_reminders()

    sent = service.email_service.sent[0]
    html = sent["html_content"]
    assert "?dist=d1&t=" in html
    # Token rotation invalidates prior hash; the new hash in DB should
    # match the URL's token.
    raw_token = html.split("&t=", 1)[1].split('"', 1)[0].split("&", 1)[0].split(" ", 1)[0]
    raw_token = raw_token.split("'", 1)[0]
    stored = database["form_distributions"].find_one({"_id": "d1"})
    assert service._verify_form_access_token(raw_token, stored["access_token_hash"])


@pytest.mark.asyncio
async def test_reminder_idempotent_second_pass_does_nothing(
    configured_form_service,
):
    service, database = configured_form_service
    database["forms"].insert_one(_form_doc())
    database["form_distributions"].insert_one(
        _distribution_doc(distribution_id="d1", sent_days_ago=10)
    )

    first = await service.send_form_reminders()
    second = await service.send_form_reminders()

    assert first == {"sent": 1, "skipped": 0, "failed": 0, "deferred_for_budget": 0}
    assert second == {"sent": 0, "skipped": 0, "failed": 0, "deferred_for_budget": 0}
    assert len(service.email_service.sent) == 1


@pytest.mark.asyncio
async def test_send_form_records_reminder_snapshot_on_each_distribution(
    configured_form_service,
):
    """End-to-end: the original send_form path persists reminder context."""
    service, database = configured_form_service
    database["forms"].insert_one(_form_doc())

    request = SendFormRequest(
        recipient_emails=["g@example.com"],
        email_settings=EmailDistributionSettings(
            subject="Original subject",
            message="Hi",
            sender_name="Wedding Planner",
            send_reminder=True,
            reminder_days=3,
        ),
    )
    await service.send_form("form_1", request, "planner@example.com")

    distributions = list(
        database["form_distributions"].find({"form_id": "form_1"})
    )
    assert len(distributions) == 1
    dist = distributions[0]
    assert dist["send_reminder"] is True
    assert dist["reminder_days"] == 3
    assert dist["reminder_subject"] == "Original subject"
    assert dist["reminder_sender_name"] == "Wedding Planner"
    assert dist["reminder_sent_at"] is None
    assert dist["reminder_count"] == 0


# =============================================================================
# Item 6 (audit fix): per-tick + per-planner budget caps
# =============================================================================


@pytest.mark.asyncio
async def test_send_form_reminders_caps_at_global_budget(
    configured_form_service, monkeypatch
):
    """Drop the global cap to a small number, seed more eligible
    distributions than the cap, and assert the overflow is deferred
    rather than dispatched."""
    service, database = configured_form_service
    monkeypatch.setattr(service, "REMINDER_BUDGET_PER_TICK", 3)
    monkeypatch.setattr(service, "REMINDER_BUDGET_PER_PLANNER", 999)
    database["forms"].insert_one(_form_doc())

    for i in range(5):
        database["form_distributions"].insert_one(
            _distribution_doc(distribution_id=f"d{i}", sent_days_ago=10)
        )

    result = await service.send_form_reminders()

    assert result["sent"] == 3
    assert result["deferred_for_budget"] == 2
    # 3 emails dispatched, 2 distributions still pending for the next tick.
    assert len(service.email_service.sent) == 3


@pytest.mark.asyncio
async def test_send_form_reminders_caps_per_planner(
    configured_form_service, monkeypatch
):
    """A single noisy planner cannot crowd out other planners' due
    reminders in the same tick."""
    service, database = configured_form_service
    monkeypatch.setattr(service, "REMINDER_BUDGET_PER_TICK", 999)
    monkeypatch.setattr(service, "REMINDER_BUDGET_PER_PLANNER", 2)

    # Planner A owns form_a with 4 due reminders; Planner B owns form_b
    # with 1 due reminder.
    database["forms"].insert_one(_form_doc(form_id="form_a"))
    database["forms"].insert_one(_form_doc(form_id="form_b"))
    # Planner A doc was inserted via _form_doc default created_by="planner@example.com".
    # Override planner B's doc.
    database["forms"].update_one(
        {"_id": "form_b"}, {"$set": {"created_by": "other@example.com"}}
    )

    for i in range(4):
        database["form_distributions"].insert_one(
            _distribution_doc(
                distribution_id=f"a{i}", form_id="form_a", sent_days_ago=10
            )
        )
    database["form_distributions"].insert_one(
        _distribution_doc(distribution_id="b0", form_id="form_b", sent_days_ago=10)
    )

    result = await service.send_form_reminders()

    # Planner A: capped at 2. Planner B: 1 sent. Total dispatched = 3.
    # 2 of planner A's distributions deferred for budget.
    assert result["sent"] == 3
    assert result["deferred_for_budget"] == 2

    sent_to = sorted(call["to_email"] for call in service.email_service.sent)
    # Planner B's recipient is included; only 2 of A's 4 are.
    assert "b0@example.com" in sent_to
