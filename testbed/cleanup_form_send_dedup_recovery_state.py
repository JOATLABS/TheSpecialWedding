#!/usr/bin/env python3
"""Cleanup paired with verify_form_send_dedup_recovery.py.

Drops every Mongo row tagged with the verifier's planner email (and
the verifier's seeded recipient) so a fresh SEED phase starts from
zero. Idempotent — safe to re-run.

Sweeps:

    forms / form_distributions / form_responses / form_uploads /
    marketing_leads / planner_notifications  (via the shared helper)

    users / user_subscriptions / team_members  (planner-scoped extras
    that the dedup verifier may register through the harness)
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from testbed._form_lifecycle_common import (  # noqa: E402
    DEDUP_RECOVERY,
    banner,
    delete_many,
    get_async_mongo,
    purge_form_rows_for_planner,
)


# Recipient seeded by the verifier — included so a stray
# marketing_leads / form_responses row keyed on the recipient email
# (rather than the planner) gets reaped too.
RECIPIENT_EMAIL = "test_recipient+dedup@thespecialwedding.io"


async def _purge_planner_user_chain(planner_email: str) -> dict[str, int]:
    """Drop user-side rows the verifier may have created via the harness.

    The dedup verifier itself only seeds form rows, but ops sometimes
    registers the planner via /public/register before running it; this
    sweeps those leftovers too. Idempotent — empty matches return 0.
    """
    mongo = get_async_mongo()
    deleted: dict[str, int] = {}

    # Resolve user_id(s) so subscription / team_member sweeps are scoped.
    users_coll = mongo.db["users"]
    user_ids: list = []
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
    banner("cleanup_form_send_dedup_recovery_state")
    form_deleted = await purge_form_rows_for_planner(DEDUP_RECOVERY.email)
    user_deleted = await _purge_planner_user_chain(DEDUP_RECOVERY.email)

    # Recipient-scoped extras (marketing_leads is keyed on submitter email).
    recipient_marketing = await delete_many(
        "marketing_leads", {"email": RECIPIENT_EMAIL}
    )

    print(f"  Planner: {DEDUP_RECOVERY.email}")
    for collection, count in form_deleted.items():
        print(f"    • {collection}: {count} deleted")
    for collection, count in user_deleted.items():
        print(f"    • {collection}: {count} deleted")
    print(f"    • marketing_leads ({RECIPIENT_EMAIL}): "
          f"{recipient_marketing} deleted")


if __name__ == "__main__":
    asyncio.run(main())
