from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

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
