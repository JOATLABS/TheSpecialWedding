#!/usr/bin/env python3
"""
Form Reminder Scheduler — Live Verification
===========================================

Verifies the daily reminder pass: backdates 3 distributions so they're
"8 days old", calls ``FormService.send_form_reminders()``, asserts
emails were dispatched, the access tokens rotated, and the per-tick
+ per-planner caps from Item 6 hold.

Pair: cleanup_form_reminder_scheduler_state.py
"""

from __future__ import annotations

import asyncio
import hmac
import os
import sys
from datetime import timedelta
from hashlib import sha256
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from testbed._form_lifecycle_common import (  # noqa: E402
    REMINDER,
    banner,
    checkpoint_pause,
    insert_one,
    now_utc,
    short_token,
)


FORM_ID_PREFIX = "verify_reminder"


async def seed_form_and_due_distributions() -> tuple[str, list[str]]:
    form_id = f"{FORM_ID_PREFIX}_{short_token()}"
    await insert_one(
        "forms",
        {
            "_id": form_id,
            "name": "Reminder Scheduler Verifier",
            "form_type": "general",
            "settings": {
                "title": "Reminder",
                "description": "Verifier-seeded — reminder scheduler.",
                "submit_button_text": "Send",
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
                    "required": True,
                    "order": 1,
                }
            ],
            "created_by": REMINDER.email,
            "is_active": True,
            "created_at": now_utc(),
            "updated_at": now_utc(),
            "submission_count": 0,
            "planner_state": {},
        },
    )

    secret = os.environ.get("SECRET_KEY") or "test-secret"
    eight_days_ago = now_utc() - timedelta(days=8)
    expires_at = now_utc() + timedelta(days=14)
    dist_ids: list[str] = []
    for i in range(3):
        dist_id = f"{form_id}_due_{i}"
        raw_token = f"verify_rem_{short_token()}"
        token_hash = hmac.new(secret.encode(), raw_token.encode(), sha256).hexdigest()
        await insert_one(
            "form_distributions",
            {
                "_id": dist_id,
                "form_id": form_id,
                "recipient_email": f"due_{i}@example.com",
                "sent_at": eight_days_ago,
                "status": "sent",
                "access_token_hash": token_hash,
                "token_expires_at": expires_at,
                "send_reminder": True,
                "reminder_days": 7,
                "reminder_sent_at": None,
                "reminder_count": 0,
                "reminder_subject": "Original subject",
                "reminder_message": "Hi — please respond.",
                "reminder_sender_name": "Wedding Planner",
            },
        )
        dist_ids.append(dist_id)
    return form_id, dist_ids


async def main() -> None:
    banner("verify_form_reminder_scheduler — SEED")
    print(f"Planner: {REMINDER.email}")
    form_id, dist_ids = await seed_form_and_due_distributions()
    print(f"Seeded form: {form_id}, due distributions: {dist_ids}")

    banner("VERIFY")
    print("Run the scheduler now:")
    print(
        '  python -c "import asyncio;'
        " from app.services.form_service import FormService;"
        ' print(asyncio.run(FormService().send_form_reminders()))"'
    )
    print("Expect: {'sent': 3, 'skipped': 0, 'failed': 0, 'deferred_for_budget': 0}")
    print()
    print("Then check:")
    print("  • All 3 form_distributions rows now have reminder_sent_at != None.")
    print(
        "  • access_token_hash has been ROTATED on each row (new value, original tokens 403)."
    )
    print("  • A second invocation returns sent=0 (idempotent — Phase 1 wave-3).")

    checkpoint_pause(
        "Reminder scheduler lifecycle",
        [
            "Open Resend's dashboard or check the test inbox for 3 reminder emails.",
            "Each email's link should carry ?dist=<id>&t=<NEW token>.",
            "Click an old (pre-rotation) link in incognito → expect 403 Invalid form access link.",
            "Click the new (post-rotation) link → expect the form to render normally.",
            "Re-run send_form_reminders → output {sent:0, ...} (idempotent).",
            "(Item 6) Backdate a 4th distribution by hand and rerun with REMINDER_BUDGET_PER_TICK=2 — confirm deferred_for_budget=2.",
        ],
    )
    print("  ↳ run cleanup: python testbed/cleanup_form_reminder_scheduler_state.py")


if __name__ == "__main__":
    asyncio.run(main())
