#!/usr/bin/env python3
"""
Form Conditional Logic Runtime — Live Verification
==================================================

Verifies that ``conditional_logic.show_when`` actually drives the
client-side render AND the server-side submit path. Hidden-field
values must be stripped on submit (Item 5 audit fix), required-yet-
hidden fields must not block submission, and the planner-facing CSV
export must respect visibility.

Pair: cleanup_form_conditional_logic_state.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from testbed._form_lifecycle_common import (  # noqa: E402
    CONDITIONAL,
    banner,
    checkpoint_pause,
    insert_one,
    now_utc,
    short_token,
)


FORM_ID_PREFIX = "verify_cond"


async def seed_form() -> str:
    form_id = f"{FORM_ID_PREFIX}_{short_token()}"
    await insert_one(
        "forms",
        {
            "_id": form_id,
            "name": "Conditional Logic Verifier",
            "form_type": "general",
            "settings": {
                "title": "Diet Survey",
                "description": "show_when on diet_main='vegetarian'",
                "submit_button_text": "Submit",
                "success_message": "Thanks!",
                "allow_multiple_submissions": True,
                "collect_email": True,
                "is_public": True,
                "requires_auth": False,
            },
            "fields": [
                {
                    "id": "diet_main",
                    "label": "Dietary preference",
                    "type": "select",
                    "options": ["meat", "vegetarian", "vegan"],
                    "required": True,
                    "order": 1,
                },
                {
                    "id": "veg_kind",
                    "label": "If vegetarian, which kind?",
                    "type": "select",
                    "options": ["lacto", "ovo", "lacto-ovo"],
                    "required": True,  # required + hidden — Item 5 must not block
                    "order": 2,
                    "conditional_logic": {
                        "show_when": {
                            "all": [
                                {
                                    "field_id": "diet_main",
                                    "operator": "equals",
                                    "value": "vegetarian",
                                }
                            ]
                        }
                    },
                },
            ],
            "created_by": CONDITIONAL.email,
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
    banner("verify_form_conditional_logic_runtime — SEED")
    print(f"Planner: {CONDITIONAL.email}")
    form_id = await seed_form()
    print(f"Seeded form: {form_id}")

    checkpoint_pause(
        "Conditional logic runtime",
        [
            f"Open /forms/{form_id}. Initially ``veg_kind`` should be hidden.",
            "Pick diet=meat → veg_kind stays hidden → submit succeeds (required check skipped per Item 5).",
            "Refresh, pick diet=vegetarian → veg_kind reveals. Submit without filling it → expect a required-field error citing veg_kind.",
            "Pick veg_kind=lacto → submit → succeeds. Inspect the response in the planner UI; veg_kind=lacto stored.",
            "Maliciously POST {diet=meat, veg_kind=ghost} via curl/postman → response stores diet=meat ONLY (Item 5: hidden values stripped server-side).",
            "Hit GET /admin/forms/{form_id}/responses — the meat-with-ghost row should NOT contain a veg_kind column value.",
        ],
    )
    print("  ↳ run cleanup: python testbed/cleanup_form_conditional_logic_state.py")


if __name__ == "__main__":
    asyncio.run(main())
