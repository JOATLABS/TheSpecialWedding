from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import (
    couple_portal,
    email_reminders,
    inbound_emails,
    reminder,
    reminder_telnyx,
    reminder_twilio,
    reminder_utilities,
    support_management,
)


PLANNER_COMMUNICATION_ROUTES = [
    (inbound_emails.router, "/inbound-emails/inbox", "GET"),
    (inbound_emails.router, "/inbound-emails/unread-count", "GET"),
    (inbound_emails.router, "/inbound-emails/{email_id}", "GET"),
    (inbound_emails.router, "/inbound-emails/threads/{thread_id}", "GET"),
    (inbound_emails.router, "/inbound-emails/{email_id}/read", "PUT"),
    (inbound_emails.router, "/inbound-emails/read-all", "PUT"),
    (inbound_emails.router, "/inbound-emails/{email_id}/reply", "POST"),
    (support_management.router, "/sms-tickets", "GET"),
    (support_management.router, "/sms-tickets/{ticket_id}", "GET"),
    (support_management.router, "/sms-tickets/{ticket_id}/respond", "POST"),
    (support_management.router, "/sms-tickets/{ticket_id}/status", "PUT"),
    (support_management.router, "/sms-tickets/stats/summary", "GET"),
    (couple_portal.router, "/couple-portal/messages", "POST"),
    (couple_portal.router, "/couple-portal/messages", "GET"),
    (couple_portal.router, "/couple-portal/messages/read", "POST"),
    (couple_portal.router, "/couple-portal/messages/unread-count", "GET"),
    (couple_portal.router, "/couple-portal/conversations", "GET"),
    (couple_portal.router, "/couple-portal/send-digest", "POST"),
    (reminder.router, "/reminders/send", "POST"),
    (reminder.router, "/reminders/logs", "GET"),
    (reminder_utilities.router, "/reminders/send-personalized-links", "POST"),
    (reminder_utilities.router, "/reminders/simulate-rsvp", "POST"),
    (reminder_twilio.router, "/reminders/twilio/send", "POST"),
    (reminder_twilio.router, "/reminders/twilio/send-invites", "POST"),
    (reminder_twilio.router, "/reminders/send-to-guests", "POST"),
    (reminder_twilio.router, "/reminders/send-to-plus-ones", "POST"),
    (reminder_twilio.router, "/reminders/logs", "GET"),
    (reminder_telnyx.router, "/reminders/telnyx/send", "POST"),
    (reminder_telnyx.router, "/reminders/telnyx/send-invites", "POST"),
    (reminder_telnyx.router, "/reminders/telnyx/logs", "GET"),
    (email_reminders.router, "/email/send-invites", "POST"),
    (email_reminders.router, "/email/send-invites-with-attachment", "POST"),
    (email_reminders.router, "/email/send-reminders", "POST"),
    (email_reminders.router, "/email/send-reminder-individual", "POST"),
    (email_reminders.router, "/email/logs", "GET"),
    (email_reminders.router, "/email/preview-invitation", "GET"),
    (email_reminders.router, "/email/preview-reminder", "GET"),
]


def _user(*, root: bool = False, planner: bool = False):
    return SimpleNamespace(
        is_root_admin=root,
        is_wedding_planner=planner,
        is_team_member=False,
        is_advertising_vendor=False,
        team_permissions=None,
    )


def _current_user_dependency(router, path: str, method: str):
    route = next(
        candidate
        for candidate in router.routes
        if candidate.path == path and method in candidate.methods
    )
    return next(
        dependency.call
        for dependency in route.dependant.dependencies
        if dependency.name == "current_user"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(("router", "path", "method"), PLANNER_COMMUNICATION_ROUTES)
async def test_root_is_denied_before_planner_communication_route_body(
    router, path: str, method: str
) -> None:
    dependency = _current_user_dependency(router, path, method)

    with pytest.raises(HTTPException) as exc_info:
        await dependency(_user(root=True))

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize(("router", "path", "method"), PLANNER_COMMUNICATION_ROUTES)
async def test_planner_retains_direct_communication_route_access(
    router, path: str, method: str
) -> None:
    dependency = _current_user_dependency(router, path, method)
    planner = _user(planner=True)

    assert await dependency(planner) is planner


@pytest.mark.asyncio
async def test_root_and_planner_retain_platform_support_route_access() -> None:
    dependency = _current_user_dependency(support_management.router, "/tickets", "GET")

    root = _user(root=True)
    planner = _user(planner=True)
    assert await dependency(root) is root
    assert await dependency(planner) is planner


def test_orphaned_root_global_twilio_message_log_route_is_removed() -> None:
    assert not any(
        route.path == "/reminders/twilio/logs"
        for route in reminder_twilio.router.routes
    )
