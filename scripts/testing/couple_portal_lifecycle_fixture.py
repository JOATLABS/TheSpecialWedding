from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from bson import ObjectId
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.utils.auth_utils import get_password_hash

DEFAULT_FIXTURE = {
    "weddingId": "wedding_1775700014748",
    "plannerEmail": "test_planner2@thespecialwedding.io",
    "plannerPassword": "testPass123!",
    "plannerId": "69d705077174afc30187a408",
    "coupleEmail": "qa_pr2_frontend@thespecialwedding.io",
    "couplePassword": "QaCouplePass123!!",
    "eventLabel": "PR2 Timeline Event",
    "formTitle": "PR2 Archived QA Form",
    "meetingTitle": "PR2 Planning Session",
}


def load_fixture(raw_fixture: str | None) -> dict[str, Any]:
    fixture = DEFAULT_FIXTURE.copy()
    if raw_fixture:
        fixture.update(json.loads(raw_fixture))
    return fixture


def get_db():
    mongo_uri = os.getenv(
        "COUPLE_PORTAL_LIFECYCLE_MONGO_URI", "mongodb://localhost:27017"
    )
    db_name = os.getenv("COUPLE_PORTAL_LIFECYCLE_DB", "wedding")
    return MongoClient(mongo_uri)[db_name]


def cleanup_fixture(db, fixture: dict[str, Any]) -> dict[str, Any]:
    db["couple_users"].delete_many(
        {
            "email": {
                "$in": [fixture["coupleEmail"], "qa_pr2_couple@thespecialwedding.io"]
            },
            "wedding_id": fixture["weddingId"],
        }
    )
    db["forms"].delete_many(
        {"title": fixture["formTitle"], "wedding_id": fixture["weddingId"]}
    )
    db["form_submissions"].delete_many(
        {
            "submitted_by": fixture["coupleEmail"],
            "wedding_id": fixture["weddingId"],
        }
    )
    db["planner_tasks"].delete_many(
        {"title": fixture["meetingTitle"], "wedding_id": fixture["weddingId"]}
    )

    wedding = db["weddings"].find_one({"_id": fixture["weddingId"]}, {"events": 1})
    if wedding:
        events = list(wedding.get("events") or [])
        filtered = [
            event
            for event in events
            if event.get("custom_type_label") != fixture["eventLabel"]
        ]
        db["weddings"].update_one(
            {"_id": fixture["weddingId"]}, {"$set": {"events": filtered}}
        )

    return {"ok": True}


def seed_fixture(db, fixture: dict[str, Any], state: str) -> dict[str, Any]:
    cleanup_fixture(db, fixture)

    now = datetime.now(timezone.utc)
    form_id = ObjectId()
    meeting_id = ObjectId()

    wedding = db["weddings"].find_one({"_id": fixture["weddingId"]}, {"events": 1})
    if not wedding:
        raise SystemExit(f"Wedding {fixture['weddingId']} was not found")

    events = list(wedding.get("events") or [])
    events = [
        event
        for event in events
        if event.get("custom_type_label") != fixture["eventLabel"]
    ]
    events.append(
        {
            "type": "custom",
            "custom_type_label": fixture["eventLabel"],
            "date": (now + timedelta(days=1)).date().isoformat(),
            "details": {
                "time": "4:00 PM",
                "venue_name": "QA Ballroom",
                "location": "QA Suite",
                "attire": "Formal",
            },
            "event_notes": [
                {
                    "id": "pr2-event-note",
                    "author_role": "couple",
                    "author_name": "QA & Couple",
                    "text": "Existing archived event note",
                    "status": "pending",
                    "created_at": now.isoformat(),
                }
            ],
            "order_of_events": [
                {
                    "id": "pr2-item-1",
                    "title": "Grand entrance",
                    "description": "Couple entrance for verification",
                    "time": "4:30 PM",
                    "order": 0,
                    "duration_minutes": 10,
                    "notes": [
                        {
                            "id": "pr2-item-note",
                            "author_role": "couple",
                            "author_name": "QA & Couple",
                            "text": "Archived item note",
                            "status": "pending",
                            "created_at": now.isoformat(),
                        }
                    ],
                }
            ],
        }
    )
    db["weddings"].update_one(
        {"_id": fixture["weddingId"]}, {"$set": {"events": events}}
    )

    db["forms"].insert_one(
        {
            "_id": form_id,
            "title": fixture["formTitle"],
            "description": "Temporary QA form for PR2 lifecycle verification.",
            "wedding_id": fixture["weddingId"],
            "created_by": fixture["plannerEmail"],
            "shared_with_couple": True,
            "fields": [
                {
                    "id": "song",
                    "label": "Entrance song",
                    "type": "text",
                    "required": False,
                },
                {
                    "id": "notes",
                    "label": "Planner notes",
                    "type": "textarea",
                    "required": False,
                },
            ],
            "created_at": now,
            "updated_at": now,
        }
    )

    db["form_submissions"].insert_one(
        {
            "form_id": str(form_id),
            "wedding_id": fixture["weddingId"],
            "submitted_by": fixture["coupleEmail"],
            "submitted_by_name": "QA & Couple",
            "submitted_by_type": "couple",
            "responses": {
                "song": "Best Day Ever",
                "notes": "Ready for archived verification",
            },
            "submitted_at": now,
            "updated_at": now,
        }
    )

    db["planner_tasks"].insert_one(
        {
            "_id": meeting_id,
            "wedding_id": fixture["weddingId"],
            "owner_planner_id": fixture["plannerId"],
            "owner_planner_email": fixture["plannerEmail"],
            "planner_email": fixture["plannerEmail"],
            "title": fixture["meetingTitle"],
            "description": "Temporary PR2 meeting for browser verification.",
            "category": "meeting",
            "status": "scheduled",
            "start_date": now + timedelta(days=1),
            "end_date": now + timedelta(days=1, hours=1),
            "conference_url": "https://meet.example.com/pr2-playwright",
            "couple_attendee_emails": [fixture["coupleEmail"]],
            "is_recurring": False,
            "created_at": now,
            "updated_at": now,
        }
    )

    couple_update = {
        "email": fixture["coupleEmail"],
        "wedding_id": fixture["weddingId"],
        "partner1_name": "QA",
        "partner2_name": "Couple",
        "password_hash": get_password_hash(fixture["couplePassword"]),
        "setup_completed": True,
        "onboarding_completed": True,
        "onboarding_completed_at": now,
        "onboarding_steps_completed": [
            "welcome",
            "overview",
            "guest_tracker",
            "messages",
        ],
        "invite_token": None,
        "invite_token_expires": None,
        "updated_at": now,
    }

    if state == "archived":
        couple_update.update(
            {
                "access_state": "active",
                "is_active": True,
                "wedding_archived": True,
                "archived_at": now,
                "owner_cancelled_at": None,
                "owner_cancelled_by_planner_id": None,
                "owner_cancelled_by_planner_email": None,
                "revoked_at": None,
                "revoked_by": None,
            }
        )
    elif state == "owner_cancelled":
        couple_update.update(
            {
                "access_state": "owner_cancelled",
                "is_active": False,
                "wedding_archived": False,
                "archived_at": None,
                "owner_cancelled_at": now,
                "owner_cancelled_by_planner_id": fixture["plannerId"],
                "owner_cancelled_by_planner_email": fixture["plannerEmail"],
                "revoked_at": None,
                "revoked_by": None,
            }
        )
    else:
        couple_update.update(
            {
                "access_state": "active",
                "is_active": True,
                "wedding_archived": False,
                "archived_at": None,
                "owner_cancelled_at": None,
                "owner_cancelled_by_planner_id": None,
                "owner_cancelled_by_planner_email": None,
                "revoked_at": None,
                "revoked_by": None,
            }
        )

    db["couple_users"].update_one(
        {"email": fixture["coupleEmail"], "wedding_id": fixture["weddingId"]},
        {"$set": couple_update},
        upsert=True,
    )

    return {
        "formId": str(form_id),
        "meetingId": str(meeting_id),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed or clean up the PR2 couple portal lifecycle Playwright fixture."
    )
    parser.add_argument("command", choices=["seed", "cleanup"])
    parser.add_argument("--state", choices=["active", "archived", "owner_cancelled"])
    parser.add_argument("--fixture")
    args = parser.parse_args()

    fixture = load_fixture(args.fixture)
    db = get_db()
    if args.command == "cleanup":
        result = cleanup_fixture(db, fixture)
    else:
        if not args.state:
            raise SystemExit("--state is required when seeding the fixture")
        result = seed_fixture(db, fixture, args.state)

    print(json.dumps(result))


if __name__ == "__main__":
    main()
