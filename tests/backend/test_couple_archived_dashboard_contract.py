from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api import behavioral_analytics as behavioral_analytics_api
from app.api import couple_portal as couple_portal_api


class _ArchivedCollection:
    def __init__(self, archive_doc: dict | None):
        self.archive_doc = archive_doc

    async def find_one(self, query):
        assert query == {"original_wedding_id": "wedding-1"}
        return self.archive_doc


class _FormsCollection:
    def __init__(self, form_doc: dict | None):
        self.form_doc = form_doc

    async def find_one(self, query):
        if not self.form_doc:
            return None
        if query["_id"] != self.form_doc["_id"]:
            return None
        if query["wedding_id"] != self.form_doc["wedding_id"]:
            return None
        return self.form_doc.copy()


class _FormSubmissionsCollection:
    def __init__(self, submission: dict | None):
        self.submission = submission

    async def find_one(self, query):
        if not self.submission:
            return None
        if (
            query["form_id"] == self.submission["form_id"]
            and query["submitted_by"] == self.submission["submitted_by"]
        ):
            return self.submission.copy()
        return None


@pytest.mark.asyncio
async def test_archived_dashboard_response_keeps_full_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive_time = datetime(2026, 4, 9, 15, 30, tzinfo=timezone.utc)
    dashboard_payload = {
        "wedding": {
            "id": "wedding-1",
            "couple_names": "Alex & Jordan",
            "date": "2026-10-12",
            "timezone": "America/Chicago",
            "venue": "The Grand Hall",
            "cultural_style": None,
            "theme_config": {},
            "events": [],
            "registries": [],
            "faqs": [],
        },
        "planner": None,
        "guest_stats": {
            "planned_total": 120,
            "guest_list_total": 120,
            "invited": 110,
            "responded": 100,
            "confirmed": 90,
            "declined": 10,
            "pending": 10,
            "not_invited": 10,
            "response_rate": 90.9,
            "event_breakdown": [],
        },
        "budget_summary": {
            "total_budget": 10000,
            "total_spent": 8000,
            "remaining": 2000,
        },
        "contract": None,
        "forms": [],
        "updates": [],
        "memories_summary": {
            "pending_count": 0,
            "kept_count": 0,
            "rejected_count": 0,
            "processing_videos": 0,
            "enabled": False,
            "link_status": "closed",
            "upload_closes_at": None,
            "storage_ready": False,
            "stream_configured": False,
        },
    }

    fake_mongo = SimpleNamespace(
        db={"archived_weddings": _ArchivedCollection({"archived_at": archive_time})}
    )

    monkeypatch.setattr(couple_portal_api, "mongo", fake_mongo)
    monkeypatch.setattr(
        couple_portal_api,
        "get_archived_wedding_record",
        AsyncMock(return_value={"archived_at": archive_time}),
    )
    monkeypatch.setattr(
        couple_portal_api.couple_portal_service,
        "get_portal_dashboard",
        AsyncMock(return_value=dashboard_payload),
    )

    result = await couple_portal_api.get_dashboard(
        couple={
            "email": "couple@example.com",
            "wedding_id": "wedding-1",
            "wedding_archived": True,
        }
    )

    assert result["archived"] is True
    assert result["archived_at"] == archive_time.isoformat()
    assert result["guest_stats"]["planned_total"] == 120
    assert result["budget_summary"]["total_budget"] == 10000
    assert result["forms"] == []
    assert result["updates"] == []
    assert result["memories_summary"]["link_status"] == "closed"


@pytest.mark.asyncio
async def test_archived_form_detail_returns_read_only_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    form_id = couple_portal_api.ObjectId("507f1f77bcf86cd799439011")
    fake_mongo = SimpleNamespace(
        db={
            "forms": _FormsCollection(
                {
                    "_id": form_id,
                    "wedding_id": "wedding-1",
                    "title": "Planner Intake",
                    "description": "Tell us more",
                    "fields": [
                        {"id": "song", "label": "Favorite song", "type": "text"}
                    ],
                    "shared_with_couple": True,
                    "created_at": datetime.now(timezone.utc),
                }
            ),
            "form_submissions": _FormSubmissionsCollection(
                {
                    "form_id": "507f1f77bcf86cd799439011",
                    "submitted_by": "couple@example.com",
                    "responses": {"song": "At Last"},
                    "submitted_at": datetime.now(timezone.utc),
                }
            ),
        }
    )
    monkeypatch.setattr(couple_portal_api, "mongo", fake_mongo)

    result = await couple_portal_api.get_form_details(
        "507f1f77bcf86cd799439011",
        couple={
            "email": "couple@example.com",
            "wedding_id": "wedding-1",
            "wedding_archived": True,
        },
    )

    assert result["read_only"] is True
    assert result["archived"] is True
    assert "archived" in (result["read_only_reason"] or "").lower()
    assert result["existing_responses"] == {"song": "At Last"}


@pytest.mark.asyncio
async def test_archived_registry_and_faq_reads_use_snapshot_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive_doc = {
        "wedding": {
            "registries": [
                {
                    "name": "Honeyfund",
                    "url": "https://example.com/honeyfund",
                    "color": "bg-indigo-600",
                }
            ],
            "faqs": [
                {
                    "question": "What should we wear?",
                    "answer": "Cocktail attire",
                }
            ],
        }
    }

    monkeypatch.setattr(
        couple_portal_api,
        "get_archived_wedding_record",
        AsyncMock(return_value=archive_doc),
    )

    registries = await couple_portal_api.list_registries_couple(
        couple={"wedding_id": "wedding-1", "wedding_archived": True}
    )
    faqs = await couple_portal_api.list_faqs_couple(
        couple={"wedding_id": "wedding-1", "wedding_archived": True}
    )

    assert registries["archived"] is True
    assert registries["read_only"] is True
    assert registries["registries"][0]["name"] == "Honeyfund"

    assert faqs["archived"] is True
    assert faqs["read_only"] is True
    assert faqs["faqs"][0]["question"] == "What should we wear?"


@pytest.mark.asyncio
async def test_archived_analytics_reads_use_snapshot_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive_doc = {
        "wedding": {
            "guest_count": 4,
            "events": [
                {"type": "ceremony", "date": "2026-10-12"},
                {"type": "reception", "date": "2026-10-12"},
            ],
        },
        "guests": [
            {
                "_id": "guest-1",
                "name": "Jamie Guest",
                "email": "jamie@example.com",
                "invite_sent": True,
                "invite_sent_date": datetime(2026, 4, 1, tzinfo=timezone.utc),
            },
            {
                "_id": "guest-2",
                "name": "Taylor Guest",
                "email": "taylor@example.com",
                "invite_sent": True,
                "invite_sent_date": datetime(2026, 4, 2, tzinfo=timezone.utc),
            },
        ],
        "rsvps": [
            {
                "guest_id": "guest-1",
                "attending": {"ceremony": True, "reception": True},
            }
        ],
        "budget": {
            "total_budget": 10000,
            "total_spent": 4200,
            "categories": [
                {
                    "_id": "budget-1",
                    "name": "Venue",
                    "budgeted_amount": 5000,
                    "actual_spent": 4200,
                    "payment_status": "partial",
                    "priority": 1,
                }
            ],
        },
    }

    monkeypatch.setattr(
        behavioral_analytics_api,
        "get_archived_wedding_record",
        AsyncMock(return_value=archive_doc),
    )

    non_responders = await behavioral_analytics_api.couple_get_non_responders(
        couple={
            "wedding_id": "wedding-1",
            "wedding_archived": True,
        }
    )
    breakdown = await behavioral_analytics_api.couple_get_budget_breakdown(
        couple={
            "wedding_id": "wedding-1",
            "wedding_archived": True,
        }
    )

    assert non_responders["archived"] is True
    assert non_responders["read_only"] is True
    assert non_responders["count"] == 1
    assert non_responders["non_responders"][0]["guest_id"] == "guest-2"

    assert breakdown["archived"] is True
    assert breakdown["read_only"] is True
    assert breakdown["total_budgeted"] == 10000
    assert breakdown["total_spent"] == 4200
    assert breakdown["category_count"] == 1
    assert breakdown["categories"][0]["name"] == "Venue"
