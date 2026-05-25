#!/usr/bin/env python3
"""
Communication Reminder "All Events" — Live Mongo Verification
=============================================================

Seeds a wedding with guests/plus-ones attending multiple events, then verifies
that the event-reminder services treat event_type="all" as "attending at least
one event" and send only once per recipient record.

Pair: cleanup_communication_reminder_all_events_state.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services import email_service_resend  # noqa: E402
from app.services.email_service_resend import ResendEmailService  # noqa: E402
from app.services.reminder_service_twilio import TwilioReminderService  # noqa: E402
from app.utils.wedding_event_types import ALL_WEDDING_EVENTS  # noqa: E402
from testbed._form_lifecycle_common import (  # noqa: E402
    banner,
    delete_many,
    get_async_mongo,
    now_utc,
)


WEDDING_ID = "verify_comm_reminder_all_events_wedding"
WEDDING_SLUG = "verify-comm-reminder-all-events"
GUEST_ONE_ID = "verify_comm_reminder_guest_one"
GUEST_TWO_ID = "verify_comm_reminder_guest_two"
OTHER_WEDDING_ID = "verify_comm_reminder_other_wedding"
OTHER_GUEST_ID = "verify_comm_reminder_guest_other"


async def cleanup_state() -> dict[str, int]:
    deleted = {
        "weddings": await delete_many(
            "weddings", {"_id": {"$in": [WEDDING_ID, OTHER_WEDDING_ID]}}
        ),
        "guests": await delete_many(
            "guests",
            {
                "_id": {
                    "$in": [GUEST_ONE_ID, GUEST_TWO_ID, OTHER_GUEST_ID],
                }
            },
        ),
        "rsvps": await delete_many(
            "rsvps",
            {
                "guest_id": {
                    "$in": [GUEST_ONE_ID, GUEST_TWO_ID, OTHER_GUEST_ID],
                }
            },
        ),
        "plus_ones": await delete_many(
            "plus_ones",
            {
                "guest_id": {
                    "$in": [GUEST_ONE_ID, GUEST_TWO_ID, OTHER_GUEST_ID],
                }
            },
        ),
        "reminders_sent": await delete_many(
            "reminders_sent",
            {
                "$or": [
                    {"wedding_id": {"$in": [WEDDING_ID, OTHER_WEDDING_ID]}},
                    {
                        "guest_id": {
                            "$in": [GUEST_ONE_ID, GUEST_TWO_ID, OTHER_GUEST_ID],
                        }
                    },
                ]
            },
        ),
    }
    return deleted


async def seed_state() -> None:
    mongo = get_async_mongo()
    now = now_utc()
    await mongo.db["weddings"].insert_many(
        [
            {
                "_id": WEDDING_ID,
                "slug": WEDDING_SLUG,
                "couple_names": "Communication Reminder All Events",
                "date": "2027-08-14",
                "events": [
                    {"type": "traditional", "date": "2027-08-13"},
                    {"type": "white_wedding", "date": "2027-08-14"},
                    {"type": "reception", "date": "2027-08-14"},
                ],
                "created_at": now,
            },
            {
                "_id": OTHER_WEDDING_ID,
                "slug": "verify-comm-reminder-other-wedding",
                "couple_names": "Other Wedding",
                "date": "2027-09-01",
                "events": [{"type": "traditional", "date": "2027-09-01"}],
                "created_at": now,
            },
        ]
    )
    await mongo.db["guests"].insert_many(
        [
            {
                "_id": GUEST_ONE_ID,
                "wedding_id": WEDDING_ID,
                "name": "Multi Event Guest",
                "phone": "+15555550101",
                "email": "multi-event@example.com",
                "token": "verify_comm_reminder_token_one",
                "sms_opt_in": True,
                "email_opt_in": True,
            },
            {
                "_id": GUEST_TWO_ID,
                "wedding_id": WEDDING_ID,
                "name": "Declined Guest",
                "phone": "+15555550102",
                "email": "declined@example.com",
                "token": "verify_comm_reminder_token_two",
                "sms_opt_in": True,
                "email_opt_in": True,
            },
            {
                "_id": OTHER_GUEST_ID,
                "wedding_id": OTHER_WEDDING_ID,
                "name": "Other Wedding Guest",
                "phone": "+15555550103",
                "email": "other-wedding@example.com",
                "token": "verify_comm_reminder_token_other",
                "sms_opt_in": True,
                "email_opt_in": True,
            },
        ]
    )
    await mongo.db["rsvps"].insert_many(
        [
            {
                "guest_id": GUEST_ONE_ID,
                "wedding_id": WEDDING_ID,
                "attending": ["traditional", "white_wedding", "reception"],
            },
            {"guest_id": GUEST_TWO_ID, "wedding_id": WEDDING_ID, "attending": []},
            {
                "guest_id": OTHER_GUEST_ID,
                "wedding_id": OTHER_WEDDING_ID,
                "attending": ["traditional"],
            },
        ]
    )
    await mongo.db["plus_ones"].insert_many(
        [
            {
                "guest_id": GUEST_ONE_ID,
                "name": "Multi Event Plus One",
                "phone": "+15555550104",
                "email": "plus-one@example.com",
                "sms_opt_in": True,
                "email_opt_in": True,
                "attending": ["white_wedding", "reception"],
            },
            {
                "guest_id": OTHER_GUEST_ID,
                "name": "Other Wedding Plus One",
                "phone": "+15555550105",
                "email": "other-plus-one@example.com",
                "sms_opt_in": True,
                "email_opt_in": True,
                "attending": ["traditional"],
            },
        ]
    )


async def verify_sms_all_events() -> None:
    mongo = get_async_mongo()
    service = TwilioReminderService.__new__(TwilioReminderService)
    service.guest_collection = mongo.get_guest_collection()
    service.rsvp_collection = mongo.db["rsvps"]
    service.plus_one_collection = mongo.db["plus_ones"]
    service.log_collection = mongo.db["reminders_sent"]
    sent_to: list[str] = []

    def fake_send_sms(phone: str, message: str) -> dict[str, Any]:
        sent_to.append(phone)
        return {"status": "success", "message_sid": None, "initial_status": "queued"}

    service._send_sms = fake_send_sms

    result = await service.send_reminders(
        ALL_WEDDING_EVENTS,
        "All events reminder",
        "all",
        WEDDING_ID,
    )

    expected = ["+15555550101", "+15555550104"]
    if result["sent"] != len(expected) or sent_to != expected:
        raise RuntimeError(
            f"SMS all-events mismatch: result={result}, sent_to={sent_to}"
        )

    logs = (
        await mongo.db["reminders_sent"]
        .find({"wedding_id": WEDDING_ID})
        .to_list(length=None)
    )
    if len(logs) != 2:
        raise RuntimeError(f"Expected 2 reminder logs, found {len(logs)}: {logs}")
    if {log["event_type"] for log in logs} != {ALL_WEDDING_EVENTS}:
        raise RuntimeError(f"Expected all-event logs, found: {logs}")


async def verify_email_all_events() -> None:
    mongo = get_async_mongo()
    service = ResendEmailService.__new__(ResendEmailService)
    service.wedding_collection = mongo.db["weddings"]
    service.guest_collection = mongo.get_guest_collection()
    service.rsvp_collection = mongo.db["rsvps"]
    sent_to: list[str] = []

    async def fake_send_email(**kwargs: Any) -> dict[str, Any]:
        sent_to.append(kwargs["to_email"])
        return {"success": True, "id": f"fake-{len(sent_to)}"}

    async def no_sleep(_seconds: float) -> None:
        return None

    original_sleep = email_service_resend.asyncio.sleep
    email_service_resend.asyncio.sleep = no_sleep
    service.send_email = fake_send_email
    try:
        result = await service.send_reminders(
            wedding_slug=WEDDING_SLUG,
            event_type=ALL_WEDDING_EVENTS,
            custom_html="Hi {name}, reminder for {event_type}.",
            target_group="all",
        )
    finally:
        email_service_resend.asyncio.sleep = original_sleep

    expected = ["multi-event@example.com", "plus-one@example.com"]
    if result["sent"] != len(expected) or sent_to != expected:
        raise RuntimeError(
            f"Email all-events mismatch: result={result}, sent_to={sent_to}"
        )


async def main() -> None:
    banner("verify_communication_reminder_all_events — CLEAN")
    print(await cleanup_state())

    banner("verify_communication_reminder_all_events — SEED")
    await seed_state()
    print(f"Seeded wedding {WEDDING_ID} with multi-event guest and plus-one.")

    banner("VERIFY SMS")
    await verify_sms_all_events()
    print("  ✅ SMS all-events reminder sent once per selected recipient.")

    banner("VERIFY EMAIL")
    await verify_email_all_events()
    print("  ✅ Email all-events reminder sent once per selected recipient.")

    banner("CLEANUP")
    print(await cleanup_state())


if __name__ == "__main__":
    asyncio.run(main())
