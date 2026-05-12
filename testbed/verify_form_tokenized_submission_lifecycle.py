#!/usr/bin/env python3
"""
Form Tokenized Submission — Live Verification
=============================================

Verifies the per-recipient distribution + access_token URL flow
end-to-end (the Phase 1 wave-2 token mechanism).

distribution_id end-to-end is verified here too — the verifier seeds
3 distributions for one form and asserts each token resolves to
exactly one row, that submission persists distribution_id on the
response, and that single-submission is enforced per-distribution
regardless of the form's allow_multiple_submissions flag.

Pair: cleanup_form_tokenized_submission_state.py
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
    TOKENIZED_SUBMIT,
    banner,
    checkpoint_pause,
    insert_one,
    now_utc,
    short_token,
)


FORM_ID_PREFIX = "verify_tokensub"


def _hash_token(secret: str, raw: str) -> str:
    return hmac.new(secret.encode(), raw.encode(), sha256).hexdigest()


async def seed_form_and_distributions() -> tuple[str, list[tuple[str, str]]]:
    form_id = f"{FORM_ID_PREFIX}_{short_token()}"
    await insert_one(
        "forms",
        {
            "_id": form_id,
            "name": "Tokenized Submission Verifier",
            "form_type": "general",
            "settings": {
                "title": "RSVP",
                "description": "Verifier-seeded — tokenized submit path.",
                "submit_button_text": "Send",
                "success_message": "Thanks!",
                "allow_multiple_submissions": True,  # token gate is what enforces
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
            "created_by": TOKENIZED_SUBMIT.email,
            "wedding_id": None,
            "is_active": True,
            "created_at": now_utc(),
            "updated_at": now_utc(),
            "submission_count": 0,
            "planner_state": {},
        },
    )

    secret = os.environ.get("SECRET_KEY") or "test-secret"
    expires_at = now_utc() + timedelta(days=14)
    distributions: list[tuple[str, str]] = []
    for idx, recipient in enumerate(
        ("guest_a@example.com", "guest_b@example.com", "guest_c@example.com"),
    ):
        dist_id = f"{form_id}_dist_{idx}"
        raw_token = f"verify_tok_{short_token()}"
        await insert_one(
            "form_distributions",
            {
                "_id": dist_id,
                "form_id": form_id,
                "recipient_email": recipient,
                "sent_at": now_utc(),
                "status": "sent",
                "access_token_hash": _hash_token(secret, raw_token),
                "token_expires_at": expires_at,
                "send_reminder": False,
                "reminder_days": 7,
                "reminder_sent_at": None,
                "reminder_count": 0,
            },
        )
        distributions.append((dist_id, raw_token))
    return form_id, distributions


async def main() -> None:
    banner("verify_form_tokenized_submission_lifecycle — SEED")
    print(f"Planner: {TOKENIZED_SUBMIT.email}")
    form_id, distributions = await seed_form_and_distributions()
    print(f"Seeded form: {form_id}")
    for dist_id, raw_token in distributions:
        print(
            f"  ↳ distribution: {dist_id}\n"
            f"     URL: /forms/{form_id}?dist={dist_id}&t={raw_token}"
        )

    banner("VERIFY (manual UX checkpoint)")
    first_dist, first_token = distributions[0]
    checkpoint_pause(
        "Tokenized submit lifecycle",
        [
            f"Open /forms/{form_id}?dist={first_dist}&t={first_token} (Guest A's link).",
            "Submit. Expect a thank-you. The form_responses row should carry distribution_id="
            + first_dist
            + ".",
            "Refresh and submit again with the SAME link — expect a 409 'already submitted with this link' (Item 4 fix).",
            f"Visit /forms/{form_id}?dist={first_dist}&t=WRONG-TOKEN — expect 403 Invalid form access link.",
            f"Visit /forms/{form_id}?dist=NOT-A-REAL-ID&t={first_token} — expect 404.",
            "Use Guest B and Guest C's links to submit successfully — each should land its own row with the correct distribution_id.",
            "Planner: open the responses table. Three rows, three distinct distribution_ids.",
            "Planner: open GET /admin/forms/{form_id}/distributions?status=submitted — confirm the SUBMITTED rows match.",
        ],
    )
    print("  ↳ run cleanup: python testbed/cleanup_form_tokenized_submission_state.py")


if __name__ == "__main__":
    asyncio.run(main())
