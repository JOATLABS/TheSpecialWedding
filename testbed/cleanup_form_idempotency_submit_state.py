#!/usr/bin/env python3
"""Cleanup paired with verify_form_idempotency_submit.py.

Drops every Mongo row tagged with the verifier's planner email so a
fresh SEED phase starts from zero. Idempotent — safe to re-run.

Sweeps:

    forms / form_distributions / form_responses / form_uploads /
    marketing_leads / planner_notifications  (via the shared helper)

    users / user_subscriptions / team_members  (planner-scoped extras
    that ops sometimes registers via /public/register before running
    the verifier).
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
    IDEMPOTENCY,
    banner,
    delete_many,
    get_async_mongo,
    purge_form_rows_for_planner,
)


async def _purge_planner_user_chain(planner_email: str) -> Dict[str, int]:
    """Drop user-side rows the verifier may have created via the harness.

    The idempotency verifier itself only seeds form rows, but ops
    sometimes registers the planner via /public/register before
    running it; this sweeps those leftovers too. Idempotent — empty
    matches return 0.
    """
    mongo = get_async_mongo()
    deleted: Dict[str, int] = {}

    users_coll = mongo.db["users"]
    user_ids: List = []
    async for doc in users_coll.find({"email": planner_email}, {"_id": 1}):
        user_ids.append(doc["_id"])

    deleted["users"] = await delete_many("users", {"email": planner_email})
    if user_ids:
        # user_subscriptions stores user_id as a string of the ObjectId.
        str_ids = [str(uid) for uid in user_ids]
        deleted["user_subscriptions"] = await delete_many(
            "user_subscriptions", {"user_id": {"$in": str_ids}}
        )
        deleted["team_members"] = await delete_many(
            "team_members", {"owner_id": {"$in": str_ids}}
        )
    else:
        deleted["user_subscriptions"] = 0
        deleted["team_members"] = 0

    # Also sweep team_members keyed on the planner's email directly
    # (invite rows where owner_id was never resolved).
    extra_team = await delete_many("team_members", {"email": planner_email})
    deleted["team_members"] += extra_team

    return deleted


async def main() -> None:
    banner("cleanup_form_idempotency_submit_state")
    form_deleted = await purge_form_rows_for_planner(IDEMPOTENCY.email)
    user_deleted = await _purge_planner_user_chain(IDEMPOTENCY.email)

    print(f"  Planner: {IDEMPOTENCY.email}")
    for collection, count in form_deleted.items():
        print(f"    • {collection}: {count} deleted")
    for collection, count in user_deleted.items():
        print(f"    • {collection}: {count} deleted")


if __name__ == "__main__":
    asyncio.run(main())
