from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.services import meeting_invite_service as meeting_invite_module


class _FakeInvitesCollection:
    async def find_one_and_update(self, *_args, **_kwargs):
        return {"_id": "invite-1"}

    async def update_one(self, *_args, **_kwargs):
        return SimpleNamespace()

    async def find_one(self, *_args, **_kwargs):
        return {"_id": "invite-1"}


class _FakeWeddingsCollection:
    async def find_one(self, query):
        assert query == {"_id": "wedding-1"}
        return {"_id": "wedding-1", "couple_names": "Alex & Jordan"}


@pytest.mark.asyncio
async def test_meeting_invites_link_to_dashboard_meetings_section(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_html: dict[str, str] = {}

    class _FakeEmailService:
        async def send_email(self, **kwargs):
            captured_html["html"] = kwargs["html_content"]
            return {"success": True, "id": "message-1"}

    service = meeting_invite_module.MeetingInviteService.__new__(
        meeting_invite_module.MeetingInviteService
    )
    service.invites_collection = _FakeInvitesCollection()
    service.weddings_collection = _FakeWeddingsCollection()

    monkeypatch.setattr(meeting_invite_module, "ResendEmailService", _FakeEmailService)
    monkeypatch.setattr(
        meeting_invite_module.settings,
        "FRONTEND_URL",
        "http://localhost:3000",
    )

    await service.send_invites(
        {
            "_id": "meeting-1",
            "title": "Planning Call",
            "description": "Review the checklist",
            "wedding_id": "wedding-1",
            "owner_planner_id": "planner-1",
            "owner_planner_email": "planner@example.com",
            "couple_attendee_emails": ["couple@example.com"],
            "start_date": datetime(2026, 4, 10, 15, 0, tzinfo=UTC),
            "end_date": datetime(2026, 4, 10, 16, 0, tzinfo=UTC),
            "conference_url": "https://meet.example.com/abc",
        }
    )

    assert "/couple/dashboard?section=meetings" in captured_html["html"]
    assert "/couple/portal/meetings" not in captured_html["html"]
