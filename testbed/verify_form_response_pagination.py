#!/usr/bin/env python3
"""
Form Response Pagination — Live Verification
============================================

Seeds a form with 250 form_responses and verifies the new paginated
``GET /admin/forms/{form_id}/responses`` envelope (Phase 1 F4).

Pair: cleanup_form_response_pagination_state.py
"""

from __future__ import annotations

import asyncio
import sys
from datetime import timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from testbed._form_lifecycle_common import (  # noqa: E402
    PAGINATION,
    banner,
    checkpoint_pause,
    count_documents,
    insert_one,
    now_utc,
    short_token,
)


FORM_ID_PREFIX = "verify_pagination"


async def seed_form_with_responses(count: int) -> str:
    form_id = f"{FORM_ID_PREFIX}_{short_token()}"
    await insert_one(
        "forms",
        {
            "_id": form_id,
            "name": "Pagination Verifier",
            "form_type": "general",
            "settings": {
                "title": "Pagination",
                "description": "Verifier-seeded — pagination envelope.",
                "submit_button_text": "Submit",
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
            "created_by": PAGINATION.email,
            "is_active": True,
            "created_at": now_utc(),
            "updated_at": now_utc(),
            "submission_count": count,
            "planner_state": {},
        },
    )

    base = now_utc()
    for i in range(count):
        await insert_one(
            "form_responses",
            {
                "_id": f"{form_id}_resp_{i}",
                "form_id": form_id,
                "responses": {"name": f"Guest {i:03d}"},
                "submitted_at": base - timedelta(minutes=count - i),
                "submitted_by_email": None,
                "submitted_by_name": f"Guest {i:03d}",
            },
        )
    return form_id


async def main() -> None:
    banner("verify_form_response_pagination — SEED")
    print(f"Planner: {PAGINATION.email}")
    form_id = await seed_form_with_responses(250)
    rows = await count_documents("form_responses", {"form_id": form_id})
    print(f"Seeded form: {form_id}, response count in Mongo: {rows}")

    checkpoint_pause(
        "Pagination envelope lifecycle",
        [
            f"Login as {PAGINATION.email} and open /admin/forms/{form_id}/responses.",
            "Confirm the responses table renders without OOM (Phase 1 F4 — paginated reads).",
            f"curl -H 'Authorization: Bearer <token>' .../admin/forms/{form_id}/responses?skip=0&limit=100 → JSON envelope {{ items, total: 250, skip: 0, limit: 100, has_more: true }}.",
            "Skip 100, limit 100 → second page with has_more: true.",
            "Skip 200, limit 100 → page with 50 items, has_more: false.",
            "Skip 5000 → empty items, has_more: false.",
            "Try limit=1000 → effective limit clamped at RESPONSE_PAGE_MAX_LIMIT (500) by FormService.get_form_responses.",
        ],
    )
    print("  ↳ run cleanup: python testbed/cleanup_form_response_pagination_state.py")


if __name__ == "__main__":
    asyncio.run(main())
