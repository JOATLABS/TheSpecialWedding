"""Shared helpers for deciding whether a team member inherits a subscription
block from their owning planner.

Originally these lived in ``app.dependencies.auth_extended`` alongside the
request-time subscription gate. They now live here so that both the
authenticated-request path (``auth_extended.get_current_user_extended``) and
the login path (``auth_service.login_and_get_token``) can call the same
logic without auth_service pulling in the whole dependency module.

``auth_extended`` re-exports both functions to preserve the existing import
surface (tests reference ``auth_extended.compute_owner_subscription_block``).
"""

from __future__ import annotations

import logging
from typing import Any

from bson import ObjectId

from app.core.database import mongo as default_mongo
from app.models.subscription import (
    PLANNER_BLOCKED_SUBSCRIPTION_STATUSES,
    normalize_subscription_status,
)

logger = logging.getLogger(__name__)


def build_team_member_block_reason(
    owner_sub_status: str | None, owner_email: str | None
) -> str:
    """Build a 402 detail string for a team member whose owning planner is blocked.

    Team members cannot pay on the planner's behalf, so the message directs
    them to contact the planner instead of taking a billing action themselves.
    """
    contact_hint = f" at {owner_email}" if owner_email else ""
    status_hint = f" (status: {owner_sub_status})" if owner_sub_status else ""
    return (
        f"Your team's subscription requires attention{status_hint}. "
        f"Please contact your planner{contact_hint} to restore access."
    )


async def compute_owner_subscription_block(
    owner_id: str | None,
    owner_email: str | None,
    mongo_client: Any = None,
) -> tuple[bool, str | None]:
    """Decide whether a team member should inherit a billing block from their owning planner.

    Returns ``(is_blocked, owner_sub_status)``.

    A team member is blocked when their owning planner's subscription is in any
    of :data:`PLANNER_BLOCKED_SUBSCRIPTION_STATUSES`. This mirrors the
    planner-side gate so that planners cannot keep managing weddings for free
    by routing work through their team when their own subscription is
    past_due / suspended / expired.

    Looks up the owner document by ``_id`` first, then falls back to email.
    Also cross-checks ``user_subscriptions`` to catch the webhook race where
    the ``users`` collection has not yet received the newer status.

    Returns ``(False, None)`` when:
      - both ``owner_id`` and ``owner_email`` are missing
      - the owner document cannot be located (orphaned team member — handled
        by the team-deactivation lifecycle elsewhere)
      - the owner's status is active/trial/trial_expiring or otherwise not in
        :data:`PLANNER_BLOCKED_SUBSCRIPTION_STATUSES`
    """
    if not owner_id and not owner_email:
        return False, None

    # Default to the real Mongo handle, but allow callers like
    # auth_extended/tests to inject the module-local handle they already
    # patch or scope.
    mongo_handle = mongo_client or default_mongo

    owner_doc = None
    try:
        users_coll = mongo_handle.get_users_collection()
        # Prefer lookup by _id (ObjectId) since that's the canonical key
        if owner_id:
            try:
                owner_doc = await users_coll.find_one({"_id": ObjectId(owner_id)})
            except Exception:
                # owner_id may already be a plain string or malformed — fall through
                owner_doc = await users_coll.find_one({"_id": owner_id})
        if not owner_doc and owner_email:
            owner_doc = await users_coll.find_one({"email": owner_email})
    except Exception as e:
        # Database errors are non-fatal: fail open (don't block) and let the
        # request proceed. The planner gate will catch any still-broken
        # subscriptions on the planner's own next request.
        logger.warning(
            "compute_owner_subscription_block: failed to load owner "
            f"(id={owner_id}, email={owner_email}): {e}"
        )
        return False, None

    if not owner_doc:
        return False, None

    owner_sub_status = normalize_subscription_status(
        owner_doc.get("subscription_status")
    )

    # Cross-check user_subscriptions for webhook race (same pattern as planner self-check)
    owner_id_str = str(owner_doc.get("_id", ""))
    if owner_id_str:
        try:
            subscription_record = await mongo_handle.db["user_subscriptions"].find_one(
                {"user_id": owner_id_str}, {"status": 1}
            )
            if subscription_record:
                sub_record_status = normalize_subscription_status(
                    subscription_record.get("status")
                )
                if (
                    sub_record_status in PLANNER_BLOCKED_SUBSCRIPTION_STATUSES
                    and owner_sub_status not in PLANNER_BLOCKED_SUBSCRIPTION_STATUSES
                ):
                    logger.info(
                        "Owner webhook race detected: user_subscriptions has "
                        f"'{sub_record_status}' but users has '{owner_sub_status}' "
                        f"for owner {owner_email}. Trusting user_subscriptions."
                    )
                    owner_sub_status = sub_record_status
        except Exception as e:
            logger.warning(
                "compute_owner_subscription_block: user_subscriptions cross-check "
                f"failed for owner {owner_email}: {e}"
            )

    is_blocked = owner_sub_status in PLANNER_BLOCKED_SUBSCRIPTION_STATUSES
    return is_blocked, owner_sub_status
