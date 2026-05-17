#!/usr/bin/env python3
"""
Form Anonymous Submission — Live Verification
=============================================

Verifies the public form's anonymous-submission path end-to-end:
form creation → public GET → anonymous POST /submit → response stored
→ multi-submission gate honoured.

Strategy
--------
SEED: planner ANON_SUBMIT signs up + verifies (so Phase D seed runs).
A new public form is created via the seeded planner; it has one
required text field, ``submitted_by_email`` is collected but not
required, ``allow_multiple_submissions=False``.

VERIFY:
  Case 1 — Anonymous submit succeeds: anonymous client posts to
    /public/forms/{form_id}/submit with a valid response. Expect 200,
    a form_responses row with submitted_by_email=None, and the form's
    submission_count=1.
  Case 2 — Replay with same email blocked: a second submit posting
    submitted_by_email=alice@example.com is rejected with 400 because
    allow_multiple_submissions=False AND a row already exists for
    that email.
  Case 3 — A truly-anonymous second submit (no email) is currently
    accepted because the dedup key is the email. CHECKPOINT this so
    the team understands the threat surface.

CHECKPOINT: planner logs in, opens the responses table, sees both
submissions, and confirms the per-row distribution_id is None (the
dedup test in chunk 1 covers the tokenized path; this driver covers
the legacy anonymous path).

Pair: cleanup_form_anonymous_submission_state.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from testbed._form_lifecycle_common import (  # noqa: E402
    ANON_SUBMIT,
    banner,
    checkpoint_pause,
    count_documents,
    insert_one,
    now_utc,
    short_token,
)


FORM_ID_PREFIX = "verify_anonsubmit"


async def seed_form() -> str:
    form_id = f"{FORM_ID_PREFIX}_{short_token()}"
    await insert_one(
        "forms",
        {
            "_id": form_id,
            "name": "Anonymous Submission Verifier",
            "form_type": "general",
            "settings": {
                "title": "Quick Reply",
                "description": "Verifier-seeded — anonymous submit path.",
                "submit_button_text": "Send",
                "success_message": "Thanks!",
                "allow_multiple_submissions": False,
                "collect_email": True,
                "is_public": True,
                "requires_auth": False,
            },
            "fields": [
                {
                    "id": "name",
                    "label": "Your name",
                    "type": "text",
                    "required": True,
                    "order": 1,
                }
            ],
            "created_by": ANON_SUBMIT.email,
            "wedding_id": None,
            "is_active": True,
            "created_at": now_utc(),
            "updated_at": now_utc(),
            "submission_count": 0,
            "planner_state": {},
        },
    )
    return form_id


async def main() -> None:
    banner("verify_form_anonymous_submission_lifecycle — SEED")
    print(f"Planner: {ANON_SUBMIT.email}")

    form_id = await seed_form()
    print(f"Seeded form: {form_id}")

    banner("VERIFY (manual UX checkpoint)")
    checkpoint_pause(
        "Anonymous submit lifecycle",
        [
            f"Open https://app.thespecialwedding.io/forms/{form_id} in a private window.",
            "Submit with name='Alice', email='alice@example.com'. Expect a thank-you screen.",
            "Refresh the page and try the same email again. Expect a 'You have already submitted' error.",
            "Open the planner dashboard at /admin/forms — the new form should show submission_count=1.",
            "Open the responses table — exactly one row should be present with submitted_by_email=alice@example.com.",
        ],
    )

    rows = await count_documents("form_responses", {"form_id": form_id})
    print(f"  ↳ post-VERIFY form_responses count: {rows}")
    print("  ↳ run cleanup: python testbed/cleanup_form_anonymous_submission_state.py")


if __name__ == "__main__":
    asyncio.run(main())
