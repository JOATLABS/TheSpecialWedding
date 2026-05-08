#!/usr/bin/env python3
"""Cleanup paired with verify_planner_two_stage_toast.py.

Drops every row owned by the 5 plus-tag emails the verifier seeds
across the collections it touches. Idempotent — re-runs on a clean
state log zeros across the board.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from testbed._form_lifecycle_common import (  # noqa: E402
    banner,
    delete_many,
    get_async_mongo,
)


PLANNER_EMAIL = "test_planner+toast_lifecycle@thespecialwedding.io"
PLANNER_B_EMAIL = "test_planner+toast_lifecycle_other@thespecialwedding.io"
TEAM_FORMS_EMAIL = "test_team_forms+toast_lifecycle@thespecialwedding.io"
TEAM_PORTAL_EMAIL = "test_team_portal+toast_lifecycle@thespecialwedding.io"
TEAM_NEITHER_EMAIL = "test_team_neither+toast_lifecycle@thespecialwedding.io"
COUPLE_EMAIL = "test_couple+toast_lifecycle@thespecialwedding.io"


PLANNER_EMAILS: List[str] = [PLANNER_EMAIL, PLANNER_B_EMAIL]
TEAM_EMAILS: List[str] = [TEAM_FORMS_EMAIL, TEAM_PORTAL_EMAIL, TEAM_NEITHER_EMAIL]
ALL_USER_EMAILS: List[str] = PLANNER_EMAILS + TEAM_EMAILS + [COUPLE_EMAIL]


async def _delete_form_distributions_for_planners() -> int:
    """form_distributions rows are joined to forms via form_id; sweep
    by every form created_by any of the planner emails this driver
    seeds, plus a direct ``recipient_email`` match against the couple
    so a stranded distribution that lost its parent form still gets
    cleaned up."""
    mongo = get_async_mongo()
    cursor = mongo.db["forms"].find(
        {"created_by": {"$in": PLANNER_EMAILS}}, {"_id": 1}
    )
    form_ids = [doc["_id"] async for doc in cursor]
    deleted = 0
    if form_ids:
        deleted += await delete_many(
            "form_distributions", {"form_id": {"$in": form_ids}}
        )
    deleted += await delete_many(
        "form_distributions", {"recipient_email": COUPLE_EMAIL}
    )
    return deleted


async def main() -> None:
    banner("cleanup_planner_two_stage_toast_state")
    deleted: Dict[str, int] = {}

    # form_distributions first — must precede the forms drop so the
    # join lookup still finds the parent form_ids.
    deleted["form_distributions"] = await _delete_form_distributions_for_planners()
    deleted["forms"] = await delete_many(
        "forms", {"created_by": {"$in": PLANNER_EMAILS}}
    )

    deleted["planner_notifications"] = await delete_many(
        "planner_notifications", {"planner_id": {"$in": ALL_USER_EMAILS}}
    )
    deleted["team_members"] = await delete_many(
        "team_members",
        {
            "$or": [
                {"owner_email": {"$in": PLANNER_EMAILS}},
                {"email": {"$in": TEAM_EMAILS}},
            ]
        },
    )
    deleted["weddings"] = await delete_many(
        "weddings",
        {
            "$or": [
                {"assigned_planner_email": {"$in": PLANNER_EMAILS}},
                {"owner_email": {"$in": PLANNER_EMAILS}},
                {"created_by": {"$in": PLANNER_EMAILS}},
            ]
        },
    )
    deleted["couples"] = await delete_many("couples", {"email": COUPLE_EMAIL})
    # The couple-portal lifecycle code uses ``couple_users`` for the
    # actual setup-password row. Sweep both spellings so a schema
    # rename can't strand state.
    deleted["couple_users"] = await delete_many(
        "couple_users", {"email": COUPLE_EMAIL}
    )
    deleted["user_subscriptions"] = await delete_many(
        "user_subscriptions", {"email": {"$in": ALL_USER_EMAILS}}
    )
    deleted["users"] = await delete_many(
        "users", {"email": {"$in": ALL_USER_EMAILS}}
    )

    for collection, count in deleted.items():
        print(f"  - {collection}: {count} deleted")


if __name__ == "__main__":
    asyncio.run(main())
