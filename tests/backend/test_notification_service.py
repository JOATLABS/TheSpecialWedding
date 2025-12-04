"""Tests for the notification service email delivery workflow."""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict

import mongomock
import pytest
from bson import ObjectId
from fastapi import HTTPException

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure deterministic environment for email templates
os.environ.setdefault("RESEND_FROM_EMAIL", "noreply@example.com")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("API_KEY", "test-api-key")

import app.services.notification_service as notification_module


class DummyEmailService:
    """Minimal stand-in for the production Resend email client."""

    def __init__(self, configured: bool = True, fail_recipients: Optional[List[str]] = None):
        self.configured = configured
        self.fail_recipients = set(fail_recipients or [])
        self.calls: List[Dict[str, str]] = []

    def send_email(self, *, to_email: str, subject: str, html_content: str, email_type: str):
        payload = {
            "to_email": to_email,
            "subject": subject,
            "html_content": html_content,
            "email_type": email_type,
        }
        self.calls.append(payload)

        if to_email in self.fail_recipients:
            return {"success": False, "error": "Simulated delivery failure"}

        return {"success": True, "id": "mock-email-id"}


class FakeMongo:
    """In-memory Mongo replacement for unit tests."""

    def __init__(self, database):
        self.db = database


@pytest.fixture
def notification_service(monkeypatch):
    client = mongomock.MongoClient()
    database = client["wedding_notifications"]
    fake_mongo = FakeMongo(database)
    monkeypatch.setattr(notification_module, "mongo", fake_mongo)

    service = notification_module.NotificationService()
    dummy_email = DummyEmailService()
    service.email_service = dummy_email
    return service, database, dummy_email


def test_send_notification_dispatches_and_updates_delivery_summary(notification_service):
    service, database, email_service = notification_service

    database["users"].insert_many(
        [
            {
                "_id": ObjectId(),
                "email": "planner@example.com",
                "first_name": "Paige",
                "role": "wedding_planner",
                "is_active": True,
            },
            {
                "_id": ObjectId(),
                "email": "vendor@example.com",
                "role": "vendor",
                "is_active": True,
            },
            {
                "_id": ObjectId(),
                "email": "inactive@example.com",
                "role": "wedding_planner",
                "is_active": False,
            },
        ]
    )

    create_result = asyncio.run(
        service.create_notification(
        {
            "title": "Planned Maintenance",
            "message": "We will perform infrastructure maintenance on Saturday at 9 PM UTC.",
            "type": "warning",
            "target_audience": "wedding_planners",
            "is_dismissible": True,
            "priority": "high",
        },
        created_by="root@example.com",
        )
    )
    notification_id = create_result["id"]

    result = asyncio.run(service.send_notification(notification_id))

    assert result == {
        "message": "Notification sent successfully",
        "attempted": 1,
        "sent": 1,
        "failed": 0,
        "failed_recipients": [],
    }
    assert len(email_service.calls) == 1
    assert email_service.calls[0]["to_email"] == "planner@example.com"
    assert "infrastructure maintenance" in email_service.calls[0]["html_content"]

    stored = database["notifications"].find_one({"_id": ObjectId(notification_id)})
    assert stored["status"] == "sent"
    assert stored["delivery_summary"]["sent"] == 1
    assert stored["delivery_summary"]["failed"] == 0
    assert stored["delivery_summary"]["attempted"] == 1
    assert stored["delivery_summary"]["last_attempt_at"].date() == datetime.utcnow().date()
    assert stored["total_recipients"] == 1
    assert stored["delivery_logs"][-1]["attempted"] == 1


def test_send_notification_without_recipients_raises(notification_service):
    service, database, _ = notification_service

    create_result = asyncio.run(
        service.create_notification(
        {
            "title": "Vendor Alert",
            "message": "Update your insurance documents.",
            "type": "info",
            "target_audience": "vendors",
            "is_dismissible": True,
            "priority": "medium",
        },
        created_by="root@example.com",
        )
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.send_notification(create_result["id"]))

    assert exc.value.status_code == 400
    assert "No active recipients" in exc.value.detail


def test_send_notification_requires_configured_email_service(notification_service):
    service, database, _ = notification_service
    service.email_service = DummyEmailService(configured=False)

    database["users"].insert_one(
        {
            "_id": ObjectId(),
            "email": "planner@example.com",
            "first_name": "Pat",
            "role": "wedding_planner",
            "is_active": True,
        }
    )

    create_result = asyncio.run(
        service.create_notification(
        {
            "title": "Test",
            "message": "Testing configuration gate.",
            "type": "info",
            "target_audience": "wedding_planners",
            "is_dismissible": True,
            "priority": "low",
        },
        created_by="root@example.com",
        )
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.send_notification(create_result["id"]))

    assert exc.value.status_code == 503
    assert "Email service not configured" in exc.value.detail
